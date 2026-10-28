"""Room ownership, admission races, credential replay and exact expiry boundaries."""

import asyncio
import json
from uuid import UUID

import pytest

from one_job.application.room_service import Member, start_eligibility
from one_job.application.rooms import RoomRegistry, RoomSettings
from one_job.application.sessions import AdmissionReceipt, Session, token_digest
from one_job.protocol.envelopes import SessionAcceptedEnvelope, parse_text
from tests.support import frame, owned_tasks


class Peer:
    def __init__(self, generation):
        self.generation = generation
        self.active = True
        self.admitted = False
        self.messages = []
        self.close_code = None

    def admit(self):
        if not self.active or self.admitted:
            return False
        self.admitted = True
        return True

    def offer(self, message, delivered=None):
        if not self.active:
            return False
        self.messages.append(message)
        if delivered:
            delivered.set()
        return True

    def finish(self, message, code):
        self.offer(message)
        self.request_close(code)

    def request_close(self, code):
        self.close_code = code
        self.active = False


@pytest.mark.parametrize(
    "count,connected,ready,stage,expected",
    [
        (0, True, True, "lobby", False),
        (1, True, True, "lobby", False),
        (2, True, True, "lobby", True),
        (3, True, True, "lobby", True),
        (4, True, True, "lobby", False),
        (2, False, True, "lobby", False),
        (3, True, False, "lobby", False),
        (2, True, True, "briefing", False),
    ],
)
def test_start_eligibility_exact_counts_connectivity_ready_and_stage(
    count, connected, ready, stage, expected
):
    members = tuple(
        Member(
            UUID(int=index),
            "Crew",
            index,
            Session(b"synthetic-digest", Peer(index) if connected else None),
            ready,
        )
        for index in range(count)
    )
    assert start_eligibility(stage, members) is expected


async def command(registry, peer, kind, request_id="command", **payload):
    message = parse_text(json.dumps(frame(kind, request_id=request_id, payload=payload)))
    return await registry.dispatch(peer, message)


async def create(registry, peer):
    assert await command(registry, peer, "create_room", "admit", name="Crew") is None
    accepted = peer.messages[-2]
    return accepted.payload


@pytest.mark.parametrize("limit", [2, 3])
async def test_simultaneous_joins_never_overfill_room(clock, limit):
    registry = RoomRegistry(clock, RoomSettings(max_players=limit))
    try:
        host = Peer(1)
        session = await create(registry, host)
        peers = [Peer(index) for index in range(2, 8)]
        results = await asyncio.gather(
            *(
                command(registry, peer, "join_room", name="Crew", room_code=session.room_code)
                for peer in peers
            )
        )
        assert results.count(None) == limit - 1
        assert results.count("room_full") == 7 - limit
        assert registry.session_count == limit
        room = registry._rooms[session.room_code]
        assert len(room.members) == limit
        assert len({member.player_id for member in room.members.values()}) == limit
        assert room.revision == limit
    finally:
        await registry.aclose()
    assert registry.room_count == registry.session_count == registry.task_count == 0
    assert clock.waiters == []
    assert owned_tasks() == []


async def test_code_collision_retries_are_bounded_and_do_not_leak_empty_rooms(clock):
    attempts = []

    def code():
        attempts.append(1)
        return "AAAAAA"

    registry = RoomRegistry(clock, code_factory=code)
    try:
        await create(registry, Peer(1))
        peer = Peer(2)
        assert await command(registry, peer, "create_room", name="Crew") == "capacity"
        assert len(attempts) == 11
        assert registry.room_count == registry.session_count == 1
        assert not peer.admitted
    finally:
        await registry.aclose()


async def test_collision_retry_can_choose_a_different_code_and_room_capacity_is_configurable(clock):
    codes = iter(("AAAAAA", "AAAAAA", "BBBBBB"))
    registry = RoomRegistry(clock, RoomSettings(max_rooms=2), code_factory=lambda: next(codes))
    try:
        first, second = await create(registry, Peer(1)), await create(registry, Peer(2))
        assert first.room_code != second.room_code
        assert await command(registry, Peer(3), "create_room", name="Crew") == "capacity"
        assert registry.room_count == 2
    finally:
        await registry.aclose()


async def test_uuid_collision_exhaustion_and_rejected_peer_do_not_leave_empty_rooms(clock):
    registry = RoomRegistry(clock, id_factory=lambda: UUID(int=1))
    try:
        await create(registry, Peer(1))
        assert await command(registry, Peer(2), "create_room", name="Crew") == "capacity"
        assert registry.room_count == registry.session_count == 1
        blocked = Peer(3)
        blocked.admitted = True
        assert await command(registry, blocked, "create_room", name="Crew") == "capacity"
        assert registry.room_count == 1
    finally:
        await registry.aclose()


async def test_failed_admission_does_not_retain_new_room(clock):
    registry = RoomRegistry(clock)
    peer = Peer(1)
    peer.admitted = True
    try:
        assert await command(registry, peer, "create_room", name="Crew") == "not_authenticated"
        assert registry.room_count == registry.session_count == 0
    finally:
        await registry.aclose()


async def test_shutdown_serializes_with_in_flight_admissions_and_clears_indexes(clock, monkeypatch):
    registry = RoomRegistry(clock)
    entered, release = asyncio.Event(), asyncio.Event()

    async def paused_synchronize():
        entered.set()
        await release.wait()

    monkeypatch.setattr(registry, "synchronize", paused_synchronize)
    peers = [Peer(i) for i in range(1, 9)]
    admissions = [
        asyncio.create_task(command(registry, peer, "create_room", name="Crew")) for peer in peers
    ]
    await entered.wait()
    shutdown = asyncio.create_task(registry.aclose())
    release.set()
    await asyncio.gather(*admissions, shutdown)
    assert registry.room_count == registry.session_count == registry.task_count == 0
    assert registry._bindings == {}
    assert clock.waiters == []
    assert owned_tasks() == []


async def test_admission_replay_uses_receipts_and_never_persists_plaintext_token(clock):
    registry = RoomRegistry(clock)
    peer = Peer(1)
    try:
        session = await create(registry, peer)
        first = peer.messages[-2]
        count = len(peer.messages)
        assert await command(registry, peer, "create_room", "admit", name=" Crew ") is None
        assert len(peer.messages) == count + 1
        assert peer.messages[-1] == first
        room = registry._rooms[session.room_code]
        member = room.members[UUID(session.player_id)]
        cached = member.session.replies["admit"]
        assert isinstance(cached.reply, AdmissionReceipt)
        assert not isinstance(cached.reply, SessionAcceptedEnvelope)
        assert session.resume_token not in repr(member.session.replies)
        assert session.resume_token not in repr(registry._sessions)
        assert member.session.digest == token_digest(session.resume_token)
        assert len(member.session.digest) == 32
        assert (
            await command(registry, peer, "create_room", "admit", name="Different")
            == "request_id_conflict"
        )
        assert room.revision == 1
        assert registry.room_count == registry.session_count == 1
    finally:
        await registry.aclose()


async def test_cache_bounds_ttl_and_noop_ready_do_not_change_revision(clock):
    registry = RoomRegistry(clock)
    peer = Peer(1)
    try:
        session = await create(registry, peer)
        room = registry._rooms[session.room_code]
        member = next(iter(room.members.values()))
        await command(registry, peer, "player_ready", "ready", ready=True)
        revision = room.revision
        await command(registry, peer, "player_ready", "noop", ready=True)
        assert room.revision == revision
        for index in range(140):
            await command(registry, peer, "request_state", f"state-{index}")
        assert len(member.session.replies) == 128
        assert "admit" not in member.session.replies
        await command(registry, peer, "player_ready", "ttl", ready=False)
        assert (
            await command(registry, peer, "player_ready", "ttl", ready=True)
            == "request_id_conflict"
        )
        await clock.advance(30)
        await command(registry, peer, "player_ready", "ttl", ready=True)
        assert member.ready
        assert len(member.session.replies) == 1
    finally:
        await registry.aclose()


async def test_replaying_failed_resume_does_not_admit_or_replace_connection(clock):
    registry = RoomRegistry(clock)
    try:
        old = Peer(1)
        session = await create(registry, old)
        assert (
            await command(
                registry, old, "resume_session", "failed-resume", resume_token=session.resume_token
            )
            == "invalid_stage"
        )
        await registry.disconnect(old)
        room = registry._rooms[session.room_code]
        revision = room.revision
        replacement = Peer(2)
        assert (
            await command(
                registry,
                replacement,
                "resume_session",
                "failed-resume",
                resume_token=session.resume_token,
            )
            == "invalid_stage"
        )
        assert not replacement.admitted
        assert room.revision == revision
        assert room.members[UUID(session.player_id)].session.peer is None
        assert (
            await command(
                registry,
                replacement,
                "resume_session",
                "fresh-resume",
                resume_token=session.resume_token,
            )
            is None
        )
        assert replacement.admitted
    finally:
        await registry.aclose()


async def test_exact_grace_boundary_rejects_resume_even_before_expiry_task_wakes(clock):
    registry = RoomRegistry(clock)
    try:
        old = Peer(1)
        session = await create(registry, old)
        await registry.disconnect(old)
        await clock.advance(30)
        new = Peer(2)
        assert (
            await command(registry, new, "resume_session", resume_token=session.resume_token)
            == "session_expired"
        )
        assert new.close_code == 1008
        assert registry.room_count == registry.session_count == 0
    finally:
        await registry.aclose()


async def test_vacant_host_is_assigned_when_disconnected_survivor_resumes(clock):
    registry = RoomRegistry(clock)
    try:
        host, guest = Peer(1), Peer(2)
        first = await create(registry, host)
        await command(registry, guest, "join_room", "join", name="Guest", room_code=first.room_code)
        guest_session = guest.messages[-2].payload
        await registry.disconnect(host)
        await clock.advance(10)
        await registry.disconnect(guest)
        await clock.advance(20)
        await registry.synchronize()
        room = registry._rooms[first.room_code]
        assert room.host_id is None
        assert len(room.members) == 1
        replacement = Peer(3)
        await command(
            registry, replacement, "resume_session", resume_token=guest_session.resume_token
        )
        assert room.host_id == UUID(guest_session.player_id)
        assert replacement.messages[-2].payload == guest_session
    finally:
        await registry.aclose()


async def test_stale_disconnect_and_queued_command_cannot_change_replacement(clock):
    registry = RoomRegistry(clock)
    try:
        old = Peer(1)
        session = await create(registry, old)
        current = Peer(2)
        await command(registry, current, "resume_session", resume_token=session.resume_token)
        room = registry._rooms[session.room_code]
        before = room.revision
        await registry.disconnect(old)
        stale_message = parse_text(json.dumps(frame("leave_room")))
        assert (
            await room.submit(lambda: room.command(UUID(session.player_id), old, stale_message))
            == "session_expired"
        )
        assert room.revision == before
        assert room.members[UUID(session.player_id)].session.peer is current
        assert registry.session_count == 1
    finally:
        await registry.aclose()


async def test_idle_expiry_ignores_ping_errors_and_cached_state_replays(clock):
    registry = RoomRegistry(clock, RoomSettings(idle_timeout=60))
    try:
        peer = Peer(1)
        session = await create(registry, peer)
        await command(registry, peer, "request_state", "state")
        await clock.advance(59)
        await command(registry, peer, "ping", "alive", nonce="hello")
        await command(registry, peer, "start_game", "invalid-start")
        # Fresh request_state is valid activity; a cache replay is not.
        await command(registry, peer, "request_state", "fresh")
        await clock.advance(29)
        await command(registry, peer, "request_state", "fresh")
        await clock.advance(31)
        await registry.synchronize()
        assert registry.room_count == registry.session_count == 0
        assert peer.close_code == 1008
        assert peer.messages[-1].payload.code == "session_expired"
        assert session.resume_token not in peer.messages[-1].model_dump_json()
    finally:
        await registry.aclose()


async def test_started_room_rejects_new_join_and_late_start_is_not_launch(clock):
    registry = RoomRegistry(clock)
    try:
        host = Peer(1)
        session = await create(registry, host)
        room = registry._rooms[session.room_code]
        await room.submit(lambda: setattr(room, "stage", "briefing"))
        assert (
            await command(registry, Peer(2), "join_room", name="Guest", room_code=session.room_code)
            == "room_started"
        )
        assert await command(registry, host, "start_game") == "invalid_stage"
        assert registry.session_count == 1
    finally:
        await registry.aclose()


@pytest.mark.parametrize(
    "settings",
    [
        {"max_rooms": 0},
        {"max_rooms": True},
        {"max_players": 4},
        {"max_players": True},
        {"disconnect_grace": 0},
        {"idle_timeout": float("inf")},
    ],
)
def test_invalid_room_settings(settings):
    with pytest.raises(ValueError):
        RoomSettings(**settings)
