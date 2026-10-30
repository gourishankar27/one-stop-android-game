"""Mailbox timing, action correlation, overload, private queues and resume fencing."""

from uuid import UUID

from one_job.application.outbox import Outbox
from one_job.domain.types import Role
from tests.application.test_briefing_rounds import started as started
from tests.application.test_rooms import Peer, command


async def live(started, count=3):
    registry, room, peers, session = await started(count)
    for index, peer in enumerate(peers):
        await command(
            registry, peer, "briefing_ready", f"read-{index}", round_id=str(room.round.round_id)
        )
    assert room.stage == "countdown"
    for _ in range(30):
        await registry.clock.advance(0.1)
        await registry.synchronize()
    assert room.stage == "running"
    for peer in peers:
        peer.messages.clear()
    return registry, room, peers, session


async def test_exact_fixed_steps_and_five_hz_private_publication(clock, started):
    registry, room, peers, _ = await live(started)
    await clock.advance(0.099)
    await registry.synchronize()
    assert room.round.engine.snapshot().tick_index == 0
    await clock.advance(0.001)
    await registry.synchronize()
    assert room.round.engine.snapshot().tick_index == 1
    assert all(not peer.messages for peer in peers)
    for _ in range(9):
        await clock.advance(0.1)
        await registry.synchronize()
    assert room.round.engine.snapshot().tick_index == 10
    for peer in peers:
        assert [message.payload.public.tick_index for message in peer.messages] == [2, 4, 6, 8, 10]
        assert all(message.type == "role_state" for message in peer.messages)


async def test_ordered_actions_have_correlated_ack_and_rejection_and_bounded_sequences(started):
    registry, room, peers, _ = await live(started)
    ids = tuple(room.members)
    engineer = peers[ids.index(room.round.engine.snapshot().assignments.owners[Role.ENGINEER])]
    pilot = peers[ids.index(room.round.engine.snapshot().assignments.owners[Role.PILOT])]
    round_id = str(room.round.round_id)
    assert (
        await command(
            registry,
            engineer,
            "player_action",
            "power",
            round_id=round_id,
            client_action_seq=1,
            action={"type": "set_engine_power", "value": 60},
        )
        is None
    )
    ack = engineer.messages[-1]
    assert ack.type == "ack" and ack.reply_to == "power"
    assert ack.payload.client_action_seq == 1 and ack.payload.applied_tick == 0
    await command(
        registry,
        engineer,
        "player_action",
        "power",
        round_id=round_id,
        client_action_seq=1,
        action={"type": "set_engine_power", "value": 60},
    )
    assert engineer.messages[-1] == ack and len(room.round.engine.accepted_actions) == 1
    assert (
        await command(
            registry,
            engineer,
            "player_action",
            "old",
            round_id=round_id,
            client_action_seq=1,
            action={"type": "engine_boost"},
        )
        == "stale_action"
    )
    rejected = engineer.messages[-1]
    assert rejected.type == "action_rejected" and rejected.payload.round_id == round_id
    assert rejected.payload.client_action_seq == 1
    assert (
        await command(
            registry,
            pilot,
            "player_action",
            "evade",
            round_id=round_id,
            client_action_seq=1,
            action={"type": "evade"},
        )
        is None
    )
    assert [event.order for event in room.round.engine.accepted_actions] == [1, 2]
    assert all(event.tick_index == 0 for event in room.round.engine.accepted_actions)
    assert (
        await command(
            registry,
            pilot,
            "player_action",
            "wrong",
            round_id=round_id,
            client_action_seq=2,
            action={"type": "coolant"},
        )
        == "not_role_owner"
    )
    assert (
        await command(
            registry,
            pilot,
            "player_action",
            "wrong-again",
            round_id=round_id,
            client_action_seq=2,
            action={"type": "evade"},
        )
        == "stale_action"
    )
    assert len(room.round._sequences) == 2


async def test_stale_round_does_not_consume_current_sequence(started):
    registry, room, peers, _ = await live(started, 2)
    ids = tuple(room.members)
    engineer = peers[ids.index(room.round.engine.snapshot().assignments.owners[Role.ENGINEER])]
    assert (
        await command(
            registry,
            engineer,
            "player_action",
            "stale-round",
            round_id=str(UUID(int=98)),
            client_action_seq=99,
            action={"type": "coolant"},
        )
        == "stale_round"
    )
    assert (
        await command(
            registry,
            engineer,
            "player_action",
            "fresh",
            round_id=str(room.round.round_id),
            client_action_seq=1,
            action={"type": "coolant"},
        )
        is None
    )


async def test_transient_catchup_is_bounded_and_persistent_lag_aborts(clock, started):
    registry, room, peers, _ = await live(started, 2)
    origin = clock.now()
    advance = room.round.runner.advance(origin + 0.6)
    assert advance.steps == 5 and not advance.terminal
    assert room.round.runner.advance(origin + 0.6).steps == 1
    assert room.round.runner.advance(origin + 2).steps == 5
    final = room.round.runner.advance(origin + 2)
    assert final.terminal and final.publish and final.steps == 0
    assert room.round.engine.snapshot().round.result.reason == "server_overload"
    assert room.round.runner.next_deadline is None
    # Other rooms and the serialized owner remain usable after an overload.
    await registry.synchronize()
    assert room.round.engine.snapshot().tick_index == 11


async def test_running_pause_has_no_backlog_and_resume_preserves_sequence(clock, started):
    registry, room, peers, _ = await live(started, 2)
    ids = tuple(room.members)
    engineer_id = room.round.engine.snapshot().assignments.owners[Role.ENGINEER]
    index = ids.index(engineer_id)
    peer = peers[index]
    await command(
        registry,
        peer,
        "player_action",
        "power",
        round_id=str(room.round.round_id),
        client_action_seq=1,
        action={"type": "set_engine_power", "value": 60},
    )
    await clock.advance(0.5)
    await registry.synchronize()
    tick = room.round.engine.snapshot().tick_index
    peer.active = False
    await registry.disconnect(peer)
    assert room.stage == "paused" and room.round.runner.next_deadline is None
    await clock.advance(20)
    await registry.synchronize()
    assert room.round.engine.snapshot().tick_index == tick
    replacement = Peer(100)
    await command(
        registry,
        replacement,
        "resume_session",
        "resume",
        resume_token=registry.issuer.token(engineer_id),
    )
    assert room.stage == "running" and room.round.engine.snapshot().tick_index == tick
    assert (
        await command(
            registry,
            replacement,
            "player_action",
            "old-seq",
            round_id=str(room.round.round_id),
            client_action_seq=1,
            action={"type": "coolant"},
        )
        == "stale_action"
    )
    await clock.advance(0.1)
    await registry.synchronize()
    assert room.round.engine.snapshot().tick_index == tick + 1
    old_count = len(room.round.engine.accepted_actions)
    await command(
        registry,
        peer,
        "player_action",
        "fenced",
        round_id=str(room.round.round_id),
        client_action_seq=100,
        action={"type": "coolant"},
    )
    assert len(room.round.engine.accepted_actions) == old_count


async def test_slow_outgoing_consumer_cannot_block_ticks_and_terminal_never_coalesces(
    clock, started
):
    registry, room, peers, _ = await live(started, 2)
    box = Outbox(5)
    peers[0].offer = lambda message, delivered=None: box.offer(message, delivered)
    for _ in range(10):
        await clock.advance(0.1)
        await registry.synchronize()
    assert room.round.engine.snapshot().tick_index == 10 and box.size == 1
    latest = (await box.get()).message
    assert latest.payload.public.tick_index == 10
    assert len(latest.payload.stations) in (1, 2)
    # The finished projection is critical, even with a later membership broadcast.
    for _ in range(890):
        await clock.advance(0.1)
        await registry.synchronize()
    assert room.stage == "finished"
    room.broadcast(include_lobby=False)
    messages = [(await box.get()).message for _ in range(box.size)]
    terminal = [
        message
        for message in messages
        if message.type == "role_state" and message.payload.public.result is not None
    ]
    assert len(terminal) == 2
    assert len([message for message in messages if message.type == "game_over"]) == 1
    assert all(message.payload.public.result.outcome == "victory" for message in terminal)
    assert room.round.runner.next_deadline is None
