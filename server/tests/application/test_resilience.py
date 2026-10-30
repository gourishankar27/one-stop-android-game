"""Phase 14 interruption matrix using monotonic fake time and mailbox fencing."""

import asyncio
import json

import pytest

from one_job.application.rooms import RoomRegistry
from one_job.protocol.envelopes import parse_text
from tests.application.test_briefing_rounds import started as started
from tests.application.test_room_runner import live
from tests.application.test_rooms import Peer, command, create
from tests.support import frame


@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("stage", ["briefing", "countdown", "running"])
@pytest.mark.parametrize("host", [False, True])
@pytest.mark.parametrize("expire", [False, True])
async def test_controller_matrix_freezes_recovers_or_aborts(
    clock, started, count, stage, host, expire
):
    if stage == "running":
        registry, room, peers, session = await live(started, count)
    else:
        registry, room, peers, session = await started(count)
        if stage == "countdown":
            for i, peer in enumerate(peers):
                await command(
                    registry, peer, "briefing_ready", f"read-{i}", round_id=str(room.round.round_id)
                )
    ids = tuple(room.members)
    index = 0 if host else 1
    absent = ids[index]
    original_host = room.host_id
    before = room.round.view(absent, clock.now())
    peers[index].active = False
    await registry.disconnect(peers[index])
    assert room.stage == "paused" and room.host_id == original_host
    await clock.advance(29)
    await registry.synchronize()
    frozen = room.round.view(absent, clock.now())
    assert frozen.public.tick_index == before.public.tick_index
    assert frozen.public.remaining_ms == before.public.remaining_ms
    assert frozen.stations == before.stations
    assert frozen.briefing.remaining_ms == before.briefing.remaining_ms
    replacement = Peer(100)
    if expire:
        await clock.advance(1)
        await registry.synchronize()
        assert room.stage == "aborted" and absent not in room.members
        survivor = next(i for i, peer in enumerate(peers) if i != index)
        assert room.host_id in {ids[i] for i in range(count) if i != index}
        await command(registry, peers[survivor], "request_state", "result")
        result = peers[survivor].messages[-1].payload.public.result
        assert result.outcome == "aborted" and result.reason == "disconnect_timeout"
        assert (
            await command(
                registry, replacement, "resume_session", resume_token=registry.issuer.token(absent)
            )
            == "session_expired"
        )
        if count == 2:
            assert await command(registry, peers[survivor], "play_again", "again") == "not_ready"
        host_peer = peers[ids.index(room.host_id)]
        assert await command(registry, host_peer, "return_to_lobby", "return") is None
        assert room.stage == "lobby"
    else:
        assert (
            await command(
                registry, replacement, "resume_session", resume_token=registry.issuer.token(absent)
            )
            is None
        )
        assert room.stage == stage and room.host_id == original_host
        assert room.round.engine.snapshot().tick_index == before.public.tick_index
        assert room.members[absent].session.peer is replacement
        assert registry.session_count == count


@pytest.mark.parametrize("count", [2, 3])
async def test_concurrent_takeovers_fence_queued_actions_preserve_sequence_cache_and_cleanup(
    started, count
):
    registry, room, peers, _ = await live(started, count)
    player = next(iter(room.members))
    original = peers[0]
    round_id = str(room.round.round_id)
    # A valid envelope consumes the sequence even if this station cannot perform it.
    await command(
        registry,
        original,
        "player_action",
        "first",
        round_id=round_id,
        client_action_seq=17,
        action={"type": "coolant"},
    )
    first_reply = original.messages[-1]
    assert room.round.view(player, registry.clock.now()).last_client_action_seq == 17
    old_action = parse_text(
        json.dumps(
            frame(
                "player_action",
                request_id="queued-old",
                payload={
                    "round_id": round_id,
                    "client_action_seq": 999,
                    "action": {"type": "coolant"},
                },
            )
        )
    )
    current = original
    for cycle in range(20):
        contenders = [Peer(100 + cycle * 2), Peer(101 + cycle * 2)]
        await asyncio.gather(
            *(
                command(
                    registry,
                    peer,
                    "resume_session",
                    f"resume-{cycle}-{i}",
                    resume_token=registry.issuer.token(player),
                )
                for i, peer in enumerate(contenders)
            )
        )
        winner = room.members[player].session.peer
        assert winner in contenders and sum(peer.active for peer in contenders) == 1
        assert current.close_code == 1008
        await registry.disconnect(current)
        assert (
            await room.submit(lambda old_peer=current: room.command(player, old_peer, old_action))
            == "session_expired"
        )
        assert room.round.view(player, registry.clock.now()).last_client_action_seq == 17
        assert room.stage == "running" and registry.session_count == count
        assert len(registry._bindings) == count
        current = winner
    await command(
        registry,
        current,
        "player_action",
        "first",
        round_id=round_id,
        client_action_seq=17,
        action={"type": "coolant"},
    )
    assert current.messages[-1] == first_reply
    await command(registry, current, "request_state", "full")
    assert current.messages[-1].payload.last_client_action_seq == 17
    for other in tuple(room.members)[1:]:
        assert room.round.view(other, registry.clock.now()).last_client_action_seq == 0
    await registry.aclose()
    assert registry.session_count == 0 and not registry._bindings


async def test_server_restart_cannot_restore_or_cross_bind_previous_credentials(clock, started):
    old, room, peers, admission = await started(2)
    await old.aclose()
    assert not old._bindings and old.session_count == 0
    fresh = RoomRegistry(clock)
    try:
        returning = Peer(101)
        assert (
            await command(fresh, returning, "resume_session", resume_token=admission.resume_token)
            == "session_expired"
        )
        assert returning.close_code == 1008 and not returning.admitted
        assert fresh.room_count == 0 and fresh.session_count == 0
        new = await create(fresh, Peer(102))
        assert new.resume_token != admission.resume_token
    finally:
        await fresh.aclose()
