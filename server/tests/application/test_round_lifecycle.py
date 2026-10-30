"""Countdown, shared stable results and repeated current-membership room cycles."""

from itertools import count
from uuid import UUID

import pytest

from one_job.domain.config import GameConfig
from tests.application.test_briefing_rounds import started as started
from tests.application.test_rooms import Peer, command
from tests.support import owned_tasks


async def steps(clock, registry, n):
    for _ in range(n):
        await clock.advance(0.1)
        await registry.synchronize()


async def acknowledge(registry, room, peers, prefix="read"):
    for index, peer in enumerate(peers):
        assert (
            await command(
                registry,
                peer,
                "briefing_ready",
                f"{prefix}-{index}",
                round_id=str(room.round.round_id),
            )
            is None
        )
    assert room.stage == "countdown"


async def ready(registry, peers, prefix):
    for index, peer in enumerate(peers):
        assert (
            await command(registry, peer, "player_ready", f"{prefix}-{index}", ready=True) is None
        )


def fresh_factories(registry):
    ids = count(100)
    seeds = count(1000)
    registry.round_id_factory = lambda: UUID(int=next(ids))
    registry.seed_factory = lambda: next(seeds)


@pytest.mark.parametrize("players", [2, 3])
async def test_countdown_exact_publication_pause_and_no_gameplay_backlog(clock, started, players):
    registry, room, peers, _ = await started(players)
    await acknowledge(registry, room, peers)
    initial = room.round.engine.snapshot()
    assert initial.round.countdown_remaining_ms == 3000 and room.round.deadline is None
    assert all(not member.ready for member in room.members.values())
    for peer in peers:
        peer.messages.clear()
    await steps(clock, registry, 11)
    frozen = room.round.engine.snapshot()
    assert frozen.tick_index == 0 and frozen.round.countdown_remaining_ms == 1900
    assert frozen.ship == initial.ship and frozen.emergencies == ()
    assert [
        m.payload.public.countdown_remaining_ms for m in peers[0].messages if m.type == "role_state"
    ] == [2800, 2600, 2400, 2200, 2000]
    actor = tuple(room.members)[-1]
    token = registry.issuer.token(actor)
    peers[-1].active = False
    await registry.disconnect(peers[-1])
    assert room.stage == "paused" and room.round.engine.snapshot().round.paused_from == "countdown"
    assert room.round.runner.next_deadline is None
    await clock.advance(25)
    await registry.synchronize()
    assert room.round.engine.snapshot().round.countdown_remaining_ms == 1900
    replacement = Peer(50)
    assert (
        await command(registry, replacement, "resume_session", "resume", resume_token=token) is None
    )
    peers[-1] = replacement
    assert room.stage == "countdown"
    await steps(clock, registry, 18)
    assert room.round.engine.snapshot().round.countdown_remaining_ms == 100
    await clock.advance(0.099)
    await registry.synchronize()
    assert room.stage == "countdown"
    await clock.advance(0.001)
    await registry.synchronize()
    assert room.stage == "running" and room.round.engine.snapshot().tick_index == 0
    await steps(clock, registry, 1)
    assert room.round.engine.snapshot().tick_index == 1


async def test_one_result_event_snapshot_recovery_and_host_actions(clock, started):
    registry, room, peers, _ = await started(
        2, config=GameConfig(emergencies_enabled=False, round_duration_ms=60000)
    )
    fresh_factories(registry)
    await acknowledge(registry, room, peers)
    await steps(clock, registry, 630)
    assert room.stage == "finished"
    result = room.round.engine.snapshot().round.result
    previous = room.round
    for peer in peers:
        over = [m for m in peer.messages if m.type == "game_over"]
        assert len(over) == 1 and over[0].payload.result.survived_ms == 60000
        assert over[0].payload.result.outcome == "victory"
    room.broadcast()
    await clock.advance(5)
    await registry.synchronize()
    assert room.round.engine.snapshot().round.result is result
    assert room.round.runner.next_deadline is None
    guest_id = tuple(room.members)[1]
    token = registry.issuer.token(guest_id)
    peers[1].active = False
    await registry.disconnect(peers[1])
    resumed = Peer(51)
    assert (
        await command(registry, resumed, "resume_session", "terminal-resume", resume_token=token)
        is None
    )
    peers[1] = resumed
    assert not [m for m in resumed.messages if m.type == "game_over"]
    assert [m for m in resumed.messages if m.type == "role_state"][
        -1
    ].payload.public.result.outcome == "victory"
    assert await command(registry, peers[1], "play_again", "not-host") == "not_host"
    assert await command(registry, peers[1], "return_to_lobby", "not-host-lobby") == "not_host"
    assert await command(registry, peers[0], "play_again", "not-ready") == "not_ready"
    await command(registry, peers[0], "request_state", "reused-state")
    await ready(registry, peers, "again-ready")
    assert room.view().can_start
    assert await command(registry, peers[0], "play_again", "again") is None
    current = room.round
    assert (
        current is not previous
        and current.round_id != previous.round_id
        and current.seed != previous.seed
    )
    assert current.stage == "briefing" and current.deadline == clock.now() + 60
    assert current.engine.accepted_actions == () and not current.engine.snapshot().emergencies
    assert current.engine.snapshot().ship == previous.engine.snapshot().ship.__class__.from_config(
        registry.game_config
    )
    assert not any(member.ready for member in room.members.values())
    assert (
        await command(
            registry,
            peers[0],
            "player_action",
            "old-action",
            round_id=str(previous.round_id),
            client_action_seq=99,
            action={"type": "coolant"},
        )
        == "stale_round"
    )
    assert (
        await command(
            registry, peers[0], "briefing_ready", "old-read", round_id=str(previous.round_id)
        )
        == "stale_round"
    )
    assert await command(registry, peers[0], "play_again", "again") is None
    assert room.round is current
    await command(registry, peers[0], "request_state", "reused-state")
    assert peers[0].messages[-1].payload.public.round_id == str(current.round_id)
    assert peers[0].messages[-1].payload.public.stage == "briefing"
    assert await command(registry, peers[0], "return_to_lobby", "too-soon") == "invalid_stage"
    await clock.advance(60)
    await registry.synchronize()
    assert room.stage == "aborted"
    assert await command(registry, peers[0], "return_to_lobby", "back") is None
    assert room.stage == "lobby" and room.round is None
    await command(registry, peers[0], "request_state", "reused-state")
    assert peers[0].messages[-1].type == "lobby_state"
    assert all(not member.ready for member in room.members.values())
    assert await command(registry, peers[0], "request_state", "lobby-view") is None
    assert peers[0].messages[-1].type == "lobby_state"
    newcomer = Peer(52)
    assert (
        await command(
            registry, newcomer, "join_room", "join-lobby", room_code=room.code, name="New crew"
        )
        is None
    )
    assert len(room.members) == 3


@pytest.mark.parametrize("duplicate", ["seed", "id"])
async def test_rematch_collision_is_bounded_and_preserves_terminal_state(clock, started, duplicate):
    registry, room, peers, _ = await started(2)
    await clock.advance(60)
    await registry.synchronize()
    old = room.round
    await ready(registry, peers, "ready")
    attempts = []

    def seed():
        attempts.append(True)
        return old.seed if duplicate == "seed" else old.seed + 1

    registry.seed_factory = seed
    registry.round_id_factory = lambda: old.round_id if duplicate == "id" else UUID(int=101)
    assert await command(registry, peers[0], "play_again", "collision") == "internal_error"
    assert len(attempts) == 8 and room.round is old and room.stage == "aborted"
    assert all(member.ready for member in room.members.values())


async def test_countdown_overload_aborts_with_one_stable_result(clock, started):
    registry, room, peers, _ = await started(2)
    await acknowledge(registry, room, peers)
    await clock.advance(2)
    for _ in range(3):
        await registry.synchronize()
    assert room.stage == "aborted"
    assert room.round.engine.snapshot().round.result.reason == "server_overload"
    assert room.round.engine.snapshot().tick_index == 0
    for peer in peers:
        assert len([m for m in peer.messages if m.type == "game_over"]) == 1


@pytest.mark.parametrize("players", [2, 3])
async def test_repeated_victory_defeat_abort_cycles_do_not_grow_tasks_or_queues(
    clock, started, players
):
    registry, room, peers, _ = await started(players)
    fresh_factories(registry)
    before = {task.get_name() for task in owned_tasks()}
    room_code = room.code
    members = tuple(room.members)
    previous_id = room.round.round_id
    for cycle in range(30):
        mode = cycle % 3
        config = GameConfig(
            emergencies_enabled=False,
            round_duration_ms=60000,
            initial_engine_output=60 if mode == 1 else 40,
            initial_temperature=1000 if mode == 1 else 300,
            critical_heat_hull_damage=1000 if mode == 1 else 5,
        )
        if cycle:
            registry.game_config = config
            await ready(registry, peers, f"ready-{cycle}")
            assert await command(registry, peers[0], "play_again", f"again-{cycle}") is None
            assert room.round.round_id != previous_id
        else:
            # First room was constructed with the ordinary core config; same victory duration.
            config = room.round.engine.snapshot().config
        previous_id = room.round.round_id
        for peer in peers:
            peer.messages.clear()
        if mode == 2:
            await clock.advance(60)
            await registry.synchronize()
            expected = "aborted"
        else:
            await acknowledge(registry, room, peers, f"ack-{cycle}")
            await steps(clock, registry, 30 + (config.duration_ticks if mode == 0 else 1))
            expected = "victory" if mode == 0 else "defeat"
        assert room.round.engine.snapshot().round.result.outcome == expected
        assert room.round.runner.next_deadline is None
        assert room.code == room_code and tuple(room.members) == members
        assert {task.get_name() for task in owned_tasks()} <= before and len(registry._tasks) == 1
        assert len(owned_tasks()) <= 3 and len(clock.waiters) <= 1
        assert room._mailbox.qsize() == 0
        assert all(len(member.session.replies) <= 128 for member in room.members.values())
        for peer in peers:
            assert len([m for m in peer.messages if m.type == "game_over"]) == 1
            assert [m for m in peer.messages if m.type == "role_state"][
                -1
            ].payload.public.result.outcome == expected
