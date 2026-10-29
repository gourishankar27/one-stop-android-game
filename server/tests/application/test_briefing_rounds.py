"""Mailbox-owned private briefing, exact deadlines and frozen participant safety."""

from dataclasses import replace
from uuid import UUID

import pytest

from one_job.application.rooms import RoomRegistry
from one_job.domain.types import PlayerId, Role
from one_job.protocol.envelopes import BriefingReadyEnvelope, encode_message
from one_job.protocol.messages import ErrorCode
from one_job.protocol.role_messages import BriefingReadyPayload
from tests.application.test_rooms import Peer, command, create
from tests.support import owned_tasks


@pytest.fixture
async def started(clock):
    registries = []

    async def start(count=3, seed=7):
        registry = RoomRegistry(
            clock, seed_factory=lambda: seed, round_id_factory=lambda: UUID(int=99)
        )
        registries.append(registry)
        peers = [Peer(index + 1) for index in range(count)]
        session = await create(registry, peers[0])
        for index, peer in enumerate(peers[1:]):
            assert (
                await command(
                    registry,
                    peer,
                    "join_room",
                    f"join-{index}",
                    name="Crew",
                    room_code=session.room_code,
                )
                is None
            )
        for index, peer in enumerate(peers):
            assert (
                await command(registry, peer, "player_ready", f"ready-{index}", ready=True) is None
            )
        for peer in peers:
            peer.messages.clear()
        assert await command(registry, peers[0], "start_game", "start") is None
        room = registry._rooms[session.room_code]
        return registry, room, peers, session

    yield start
    for registry in registries:
        await registry.aclose()
    assert clock.waiters == [] and owned_tasks() == []


def role_frames(peer):
    return [message for message in peer.messages if message.type in ("role_assigned", "role_state")]


def assert_private(room, peer, player_id):
    expected = {
        role.value
        for role in room.round.engine.snapshot().assignments.roles_for(PlayerId(player_id))
    }
    for message in role_frames(peer):
        if message.type == "role_assigned":
            assert set(message.payload.roles) == expected
            assert {item.role for item in message.payload.instructions} == expected
        else:
            assert set(message.payload.stations) == expected
            public = message.payload.public.model_dump()
            assert (
                not {"seed", "owners", "assignments", "stations", "temperature", "lane", "energy"}
                & public.keys()
            )
    return expected


@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("seed", [0, 1, 5])
async def test_start_targets_only_owned_roles_and_request_state_replays_safely(
    started, count, seed
):
    registry, room, peers, _ = await started(count, seed)
    player_ids = tuple(room.members)
    assert peers[0].messages[0].type == "ack"
    assert peers[0].messages[0].payload.operation == "start_game"
    assert room.stage == "briefing" and room.round.engine.snapshot().tick_index == 0
    roles = []
    for peer, player_id in zip(peers, player_ids, strict=True):
        assert [message.type for message in peer.messages if message.type != "ack"] == [
            "lobby_state",
            "role_assigned",
            "role_state",
        ]
        expected = assert_private(room, peer, player_id)
        roles.extend(expected)
        if count == 3:
            assert len(expected) == 1
        await command(registry, peer, "request_state", "state")
        terminal = peer.messages[-1]
        assert terminal.type == "role_state" and terminal.reply_to == "state"
        count_before = len(peer.messages)
        await command(registry, peer, "request_state", "state")
        assert len(peer.messages) == count_before + 1 and peer.messages[-1] == terminal
        assert_private(room, peer, player_id)
    assert sorted(roles) == sorted(role.value for role in Role)
    assert len(room.round.engine.snapshot().players) == count
    before = room.round
    await command(registry, peers[0], "start_game", "start")
    assert room.round is before


async def test_exact_timeout_aborts_without_a_simulation_tick(clock, started):
    registry, room, peers, _ = await started(2)
    await clock.advance(59.999)
    await registry.synchronize()
    assert room.stage == "briefing"
    await clock.advance(0.001)
    await registry.synchronize()
    assert room.stage == "aborted"
    assert room.round.engine.snapshot().round.result.reason == "briefing_timeout"
    assert room.round.engine.snapshot().tick_index == 0
    for peer in peers:
        assert peer.messages[-1].type == "role_state"
        assert peer.messages[-1].payload.public.result.reason == "briefing_timeout"


async def test_acknowledgement_crossing_deadline_broadcasts_abort_before_timer_runs(clock, started):
    registry, room, peers, _ = await started(2)
    revision = room.revision
    for peer in peers:
        peer.messages.clear()
    # Model the boundary between the owner's expiry check and synchronous dispatch.
    # Do not wake the timer: acknowledgement must publish the transition itself.
    clock.time = room.round.deadline
    result = room.command(
        tuple(room.members)[0],
        peers[0],
        BriefingReadyEnvelope(
            version=1,
            type="briefing_ready",
            request_id="boundary-read",
            payload=BriefingReadyPayload(round_id=str(room.round.round_id)),
        ),
    )
    assert result == ErrorCode.INVALID_STAGE
    assert room.stage == "aborted" and room.revision == revision + 1
    for peer in peers:
        state = role_frames(peer)[-1]
        assert state.room_revision == room.revision
        assert state.payload.public.result.reason == "briefing_timeout"
        assert not state.payload.briefing.acknowledged
    assert peers[0].messages[-1].type == "error"
    await registry.synchronize()
    assert room.revision == revision + 1


@pytest.mark.parametrize("count", [2, 3])
async def test_all_acknowledgements_hold_indefinitely_without_running_or_countdown(
    clock, started, count
):
    registry, room, peers, _ = await started(count)
    round_id = str(room.round.round_id)
    for index, peer in enumerate(peers):
        assert (
            await command(registry, peer, "briefing_ready", f"brief-{index}", round_id=round_id)
            is None
        )
    revision = room.revision
    assert room.round.complete and room.round.deadline is None
    assert (
        await command(registry, peers[0], "briefing_ready", "already-read", round_id=round_id)
        is None
    )
    assert room.revision == revision
    await clock.advance(120)
    await registry.synchronize()
    state = room.round.engine.snapshot()
    assert state.round.stage == "briefing" and state.tick_index == 0
    assert state.round.countdown_remaining_ms is None
    for peer in peers:
        await command(registry, peer, "request_state", "held-state")
        briefing = peer.messages[-1].payload.briefing
        assert briefing.acknowledged and briefing.complete and briefing.held_for_gameplay
        assert briefing.waiting_player_ids == ()


async def test_pause_suspends_deadline_and_resume_restores_private_briefing(clock, started):
    registry, room, peers, session = await started(2)
    host_id, guest_id = tuple(room.members)
    round_id = str(room.round.round_id)
    await command(registry, peers[0], "briefing_ready", "host-read", round_id=round_id)
    guest_token = registry.issuer.token(guest_id)
    await clock.advance(15)
    peers[1].active = False
    await registry.disconnect(peers[1])
    assert room.stage == "paused" and room.round.deadline is None
    await clock.advance(25)
    await registry.synchronize()
    assert room.round.view(PlayerId(host_id), clock.now()).briefing.remaining_ms == 45_000
    replacement = Peer(10)
    assert (
        await command(registry, replacement, "resume_session", "resume", resume_token=guest_token)
        is None
    )
    assert room.stage == "briefing" and room.round.deadline == 85
    assert room.round.view(PlayerId(host_id), clock.now()).briefing.acknowledged
    assert_private(room, replacement, guest_id)
    assert replacement.messages[0].payload.player_id == str(guest_id)
    assert replacement.messages[0].payload.resume_token == guest_token
    await clock.advance(44.999)
    await registry.synchronize()
    assert room.stage == "briefing"
    await clock.advance(0.001)
    await registry.synchronize()
    assert room.stage == "aborted"


@pytest.mark.parametrize("leave", [True, False])
async def test_departure_or_grace_expiry_aborts_frozen_round(clock, started, leave):
    registry, room, peers, _ = await started(3)
    frozen = room.round.engine.snapshot().players
    if leave:
        await command(registry, peers[1], "leave_room", "leave")
    else:
        peers[1].active = False
        await registry.disconnect(peers[1])
        await clock.advance(30)
        await registry.synchronize()
    assert room.stage == "aborted"
    assert room.round.engine.snapshot().players == frozen
    assert room.round.engine.snapshot().round.result.reason == (
        "player_left" if leave else "disconnect_timeout"
    )
    assert len(room.members) == 2


async def test_stale_round_wrong_role_and_owned_actions_are_rejected_without_mutation(started):
    registry, room, peers, _ = await started(3)
    ids = tuple(room.members)
    pilot = room.round.engine.snapshot().assignments.owners[Role.PILOT]
    peer = peers[ids.index(pilot)]
    state = room.round.engine.snapshot()
    stale = str(UUID(int=98))
    assert (
        await command(registry, peer, "briefing_ready", "stale-brief", round_id=stale)
        == "stale_round"
    )
    for index, (round_id, action, code) in enumerate(
        [
            (stale, {"type": "move_lane", "direction": "left"}, "stale_round"),
            (str(room.round.round_id), {"type": "coolant"}, "not_role_owner"),
            (str(room.round.round_id), {"type": "move_lane", "direction": "left"}, "invalid_stage"),
        ]
    ):
        assert (
            await command(
                registry,
                peer,
                "player_action",
                f"action-{index}",
                round_id=round_id,
                client_action_seq=1,
                action=action,
            )
            == code
        )
    assert room.round.engine.snapshot() is state and room.round.engine.accepted_actions == ()


async def test_host_and_other_players_never_receive_foreign_station_sentinels(started):
    registry, room, peers, _ = await started(3)
    state = room.round.engine.snapshot()
    room.round.engine._state = replace(
        state, ship=replace(state.ship, temperature=731, shield_energy=997)
    )
    for peer, player_id in zip(peers, room.members, strict=True):
        peer.messages.clear()
        await command(registry, peer, "request_state", "sentinel-state")
        own = assert_private(room, peer, player_id)
        data = peer.messages[-1].payload.model_dump(mode="json")
        assert "owners" not in data and "seed" not in data
        for role in Role:
            if role.value not in own:
                assert role.value not in data["stations"]
        text = encode_message(peer.messages[-1])
        if "engineer" not in own:
            assert '"temperature":731' not in text
        if "shields" not in own:
            assert '"energy":997' not in text
        assert "731" not in repr(peer.messages[-1]) and "997" not in repr(peer.messages[-1])
