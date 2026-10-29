"""Phase 04 wire behavior through real ASGI WebSocket sessions."""

import asyncio
import json
import logging
from contextlib import ExitStack
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from one_job.application.connections import ConnectionSettings
from one_job.application.rooms import RoomSettings
from one_job.main import create_app
from tests.support import frame

CODE_ALPHABET = frozenset("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


def receive(socket):
    """Bound test-harness I/O; no wall-clock waits simulate game/expiry time."""

    async def next_frame():
        async with asyncio.timeout(3):
            return await socket._send_rx.receive()

    message = socket.portal.call(next_frame)
    if message["type"] == "websocket.close":
        raise WebSocketDisconnect(message.get("code", 1000), message.get("reason", ""))
    assert message["type"] == "websocket.send"
    return json.loads(message["text"])


def send(socket, operation, request_id, payload=None):
    socket.send_json(frame(operation, request_id=request_id, payload=payload or {}))


def error(socket, code, request_id):
    response = receive(socket)
    assert response["type"] == "error"
    assert response["reply_to"] == request_id
    assert response["payload"]["code"] == code
    assert set(response["payload"]) == {"code", "message", "retryable"}
    return response


def closed(socket, code):
    with pytest.raises(WebSocketDisconnect) as caught:
        receive(socket)
    assert caught.value.code == code


def lobby(socket, reply_to=None, stage="lobby"):
    response = receive(socket)
    assert response["version"] == 1
    assert response["type"] == "lobby_state"
    assert response["reply_to"] == reply_to
    assert type(response["room_revision"]) is int
    assert response["room_revision"] >= 0
    payload = response["payload"]
    assert set(payload) == {"room_code", "stage", "host_player_id", "players", "can_start"}
    assert payload["stage"] == stage
    assert all(
        set(player) == {"player_id", "name", "connected", "ready"} for player in payload["players"]
    )
    return response


def admit(socket, operation="create_room", *, name="Crew", code=None, request_id="admit"):
    payload = {"name": name}
    if code is not None:
        payload["room_code"] = code
    send(socket, operation, request_id, payload)
    accepted = receive(socket)
    assert accepted["type"] == "session_accepted"
    assert accepted["reply_to"] == request_id
    assert set(accepted["payload"]) == {"room_code", "kind", "player_id", "resume_token"}
    assert accepted["payload"]["kind"] == "player"
    UUID(accepted["payload"]["player_id"])
    assert len(accepted["payload"]["room_code"]) == 6
    assert set(accepted["payload"]["room_code"]) <= CODE_ALPHABET
    assert len(accepted["payload"]["resume_token"]) >= 43
    state = lobby(socket)
    assert accepted["room_revision"] == state["room_revision"]
    return accepted["payload"], state


def same_lobby(*states):
    assert all(state["payload"] == states[0]["payload"] for state in states)
    assert all(state["room_revision"] == states[0]["room_revision"] for state in states)


def ready(socket, value, request_id):
    send(socket, "player_ready", request_id, {"ready": value})
    response = receive(socket)
    assert response["type"] == "ack"
    assert response["reply_to"] == request_id
    assert response["payload"] == {"operation": "player_ready"}
    return response


def request_state(socket, request_id="state"):
    send(socket, "request_state", request_id)
    return lobby(socket, request_id)


def test_three_clients_share_roster_revisions_and_start_enters_private_briefing(clock):
    with TestClient(create_app(clock=clock)) as client, ExitStack() as stack:
        host, second, third = [
            stack.enter_context(client.websocket_connect("/ws")) for _ in range(3)
        ]
        host_session, first = admit(host, name=" Captain ")
        code = host_session["room_code"]
        assert first["payload"]["host_player_id"] == host_session["player_id"]
        assert first["payload"]["players"][0]["name"] == "Captain"
        assert not first["payload"]["can_start"]
        second_session, second_join = admit(second, "join_room", code=code.lower(), name="Crew")
        same_lobby(second_join, lobby(host))
        third_session, third_join = admit(third, "join_room", code=code, name="Crew")
        same_lobby(third_join, lobby(host), lobby(second))
        assert third_join["room_revision"] == first["room_revision"] + 2
        assert (
            len({session["player_id"] for session in (host_session, second_session, third_session)})
            == 3
        )
        assert (
            len(
                {
                    session["resume_token"]
                    for session in (host_session, second_session, third_session)
                }
            )
            == 3
        )
        state = third_join
        for index, socket in enumerate((host, second, third)):
            ack = ready(socket, True, f"ready-{index}")
            states = [lobby(peer) for peer in (host, second, third)]
            same_lobby(*states)
            assert states[0]["room_revision"] == state["room_revision"] + 1
            assert ack["room_revision"] == states[0]["room_revision"]
            state = states[0]
        assert state["payload"]["can_start"]
        send(second, "start_game", "not-host")
        error(second, "not_host", "not-host")
        send(host, "start_game", "start")
        started = receive(host)
        assert started["type"] == "ack" and started["payload"]["operation"] == "start_game"
        assert started["room_revision"] == state["room_revision"] + 1
        snapshots = []
        owned_roles = []
        for peer in (host, second, third):
            snapshots.append(lobby(peer, stage="briefing"))
            assignment, private = receive(peer), receive(peer)
            assert assignment["type"] == "role_assigned"
            assert private["type"] == "role_state"
            assert set(private["payload"]["stations"]) == set(assignment["payload"]["roles"])
            assert len(assignment["payload"]["roles"]) == 1
            owned_roles.extend(assignment["payload"]["roles"])
        same_lobby(*snapshots)
        assert set(owned_roles) == {"pilot", "engineer", "shields"}


@pytest.mark.parametrize("name", ["", "   ", "x" * 21, "A\nB", "A\x00B", 123, True, None])
def test_invalid_names_do_not_create_membership(name, clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            send(socket, "create_room", "bad-name", {"name": name})
            response = error(socket, "invalid_message", "bad-name")
            assert response["room_revision"] is None
            session, state = admit(socket, name="Valid", request_id="valid-name")
            assert state["payload"]["players"] == [
                {
                    "player_id": session["player_id"],
                    "name": "Valid",
                    "connected": True,
                    "ready": False,
                }
            ]


@pytest.mark.parametrize(
    "code", ["ABC", "ABCDEFG", "ABC0EF", "ABCDI2", "ABCDO2", "ABC 23", 123, None]
)
def test_invalid_room_codes_are_rejected(code, clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            send(socket, "join_room", "bad-code", {"name": "Crew", "room_code": code})
            error(socket, "invalid_message", "bad-code")


def test_unknown_room_and_fourth_controller_errors(clock):
    with TestClient(create_app(clock=clock)) as client, ExitStack() as stack:
        sockets = [stack.enter_context(client.websocket_connect("/ws")) for _ in range(4)]
        send(sockets[3], "join_room", "unknown", {"room_code": "AAAAAA", "name": "Crew"})
        error(sockets[3], "room_not_found", "unknown")
        session, _ = admit(sockets[0])
        for index in (1, 2):
            _, joined = admit(sockets[index], "join_room", code=session["room_code"])
            same_lobby(joined, *(lobby(peer) for peer in sockets[:index]))
        send(sockets[3], "join_room", "full", {"room_code": session["room_code"], "name": "Fourth"})
        assert error(sockets[3], "room_full", "full")["room_revision"] is None
        assert len(request_state(sockets[0])["payload"]["players"]) == 3


def test_membership_join_and_explicit_leave_reset_ready_and_transfer_host(clock):
    with TestClient(create_app(clock=clock)) as client, ExitStack() as stack:
        host, guest, third = [
            stack.enter_context(client.websocket_connect("/ws")) for _ in range(3)
        ]
        host_session, _ = admit(host)
        guest_session, joined = admit(guest, "join_room", code=host_session["room_code"])
        same_lobby(joined, lobby(host))
        for index, socket in enumerate((host, guest)):
            ready(socket, True, f"ready-{index}")
            same_lobby(lobby(host), lobby(guest))
        _, joined = admit(third, "join_room", code=host_session["room_code"])
        same_lobby(joined, lobby(host), lobby(guest))
        assert not any(player["ready"] for player in joined["payload"]["players"])
        ready(guest, True, "ready-again")
        same_lobby(lobby(host), lobby(guest), lobby(third))
        send(host, "leave_room", "leave")
        acknowledgment = receive(host)
        assert acknowledgment["type"] == "ack"
        assert acknowledgment["reply_to"] == "leave"
        assert acknowledgment["payload"] == {"operation": "leave_room"}
        closed(host, 1000)
        left = lobby(guest)
        same_lobby(left, lobby(third))
        assert left["payload"]["host_player_id"] == guest_session["player_id"]
        assert len(left["payload"]["players"]) == 2
        assert not any(player["ready"] for player in left["payload"]["players"])
        with client.websocket_connect("/ws") as former:
            send(
                former, "resume_session", "expired", {"resume_token": host_session["resume_token"]}
            )
            error(former, "session_expired", "expired")
            closed(former, 1008)


def test_start_checks_membership_host_and_readiness_before_briefing(clock):
    with TestClient(create_app(clock=clock)) as client, ExitStack() as stack:
        host, guest = [stack.enter_context(client.websocket_connect("/ws")) for _ in range(2)]
        send(guest, "start_game", "unadmitted")
        error(guest, "not_authenticated", "unadmitted")
        session, _ = admit(host)
        send(host, "start_game", "alone")
        error(host, "not_ready", "alone")
        _, joined = admit(guest, "join_room", code=session["room_code"])
        same_lobby(joined, lobby(host))
        send(guest, "start_game", "guest-start")
        error(guest, "not_host", "guest-start")
        ready(host, True, "host-ready")
        same_lobby(lobby(host), lobby(guest))
        send(host, "start_game", "guest-unready")
        error(host, "not_ready", "guest-unready")
        ready(guest, True, "guest-ready")
        eligible = lobby(host)
        same_lobby(eligible, lobby(guest))
        assert eligible["payload"]["can_start"]
        send(host, "start_game", "eligible")
        assert receive(host)["payload"] == {"operation": "start_game"}
        for peer in (host, guest):
            lobby(peer, stage="briefing")
            assert receive(peer)["type"] == "role_assigned"
            assert receive(peer)["type"] == "role_state"
        send(host, "start_game", "start-again")
        error(host, "invalid_stage", "start-again")


def test_ready_replay_conflict_and_request_state_are_side_effect_free(clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            _, initial = admit(socket)
            accepted = ready(socket, True, "ready-once")
            changed = lobby(socket)
            assert changed["room_revision"] == initial["room_revision"] + 1
            assert ready(socket, True, "ready-once") == accepted
            fresh = request_state(socket, "fresh-after-replay")
            same_lobby(fresh, changed)
            send(socket, "player_ready", "ready-once", {"ready": False})
            error(socket, "request_id_conflict", "ready-once")
            same_lobby(request_state(socket, "fresh-after-conflict"), changed)


def test_session_tokens_only_appear_in_targeted_admission_not_lobby_or_logs(clock, caplog):
    caplog.set_level(logging.INFO, logger="one_job.connections")
    with TestClient(create_app(clock=clock)) as client, ExitStack() as stack:
        host, guest = [stack.enter_context(client.websocket_connect("/ws")) for _ in range(2)]
        first, initial = admit(host)
        second, joined = admit(guest, "join_room", code=first["room_code"])
        broadcast = lobby(host)
        same_lobby(broadcast, joined)
        ready(guest, True, "ready")
        snapshots = [initial, joined, broadcast, lobby(host), lobby(guest)]
        shared = json.dumps(snapshots)
        records = str([record.__dict__ for record in caplog.records])
        for token in (first["resume_token"], second["resume_token"]):
            assert token not in shared
            assert token not in records
        for forbidden in ("resume_token", "token_digest", "generation", "engine", "stations"):
            assert forbidden not in shared


def test_admission_cancels_ten_second_deadline(clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            _, initial = admit(socket)
            socket.portal.call(clock.advance, 11)
            fresh = request_state(socket)
            same_lobby(initial, fresh)


def test_invalid_token_does_not_leak_input_and_closes(clock, caplog):
    caplog.set_level(logging.INFO, logger="one_job.connections")
    token = "TOKEN_SECRET_SENTINEL_" + "x" * 43
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            send(socket, "resume_session", "invalid-token", {"resume_token": token})
            response = error(socket, "session_expired", "invalid-token")
            assert token not in json.dumps(response)
            closed(socket, 1008)
    assert token not in str([record.__dict__ for record in caplog.records])


def synchronize(application, socket):
    async def flush():
        async with asyncio.timeout(3):
            await application.state.rooms.synchronize()

    socket.portal.call(flush)


def ping(socket, request_id):
    socket.send_json(frame("ping", request_id=request_id))
    response = receive(socket)
    assert response["type"] == "pong"
    assert response["reply_to"] == request_id


def resume(socket, session, request_id="resume"):
    send(socket, "resume_session", request_id, {"resume_token": session["resume_token"]})
    accepted = receive(socket)
    assert accepted["type"] == "session_accepted"
    assert accepted["reply_to"] == request_id
    assert accepted["payload"] == session
    snapshot = lobby(socket)
    assert accepted["room_revision"] == snapshot["room_revision"]
    return snapshot


def test_disconnected_host_keeps_seat_then_resumes_stable_identity_before_grace(clock):
    application = create_app(clock=clock)
    with TestClient(application) as client, ExitStack() as stack:
        host, guest = [stack.enter_context(client.websocket_connect("/ws")) for _ in range(2)]
        session, _ = admit(host, name="Captain")
        _, joined = admit(guest, "join_room", code=session["room_code"])
        same_lobby(joined, lobby(host))
        for index, socket in enumerate((host, guest)):
            ready(socket, True, f"ready-{index}")
            same_lobby(lobby(host), lobby(guest))
        host.close()
        disconnected = lobby(guest)
        assert disconnected["payload"]["host_player_id"] == session["player_id"]
        assert not any(player["ready"] for player in disconnected["payload"]["players"])
        by_id = {player["player_id"]: player for player in disconnected["payload"]["players"]}
        assert not by_id[session["player_id"]]["connected"]
        guest.portal.call(clock.advance, 29)
        synchronize(application, guest)
        ping(guest, "keep-guest")
        same_lobby(disconnected, request_state(guest, "before-resume"))
        replacement = stack.enter_context(client.websocket_connect("/ws"))
        resumed = resume(replacement, session)
        same_lobby(resumed, lobby(guest))
        assert resumed["room_revision"] == disconnected["room_revision"] + 1
        assert all(player["connected"] for player in resumed["payload"]["players"])
        assert not any(player["ready"] for player in resumed["payload"]["players"])
        guest.portal.call(clock.advance, 2)
        synchronize(application, guest)
        same_lobby(resumed, request_state(replacement, "past-old-deadline"))


def test_grace_expiry_transfers_host_to_earliest_connected_member_and_invalidates_token(clock):
    application = create_app(clock=clock)
    with TestClient(application) as client, ExitStack() as stack:
        host, second, third = [
            stack.enter_context(client.websocket_connect("/ws")) for _ in range(3)
        ]
        host_session, _ = admit(host)
        second_session, joined = admit(second, "join_room", code=host_session["room_code"])
        same_lobby(joined, lobby(host))
        _, joined = admit(third, "join_room", code=host_session["room_code"])
        same_lobby(joined, lobby(host), lobby(second))
        host.close()
        disconnected = lobby(second)
        same_lobby(disconnected, lobby(third))
        second.portal.call(clock.advance, 29)
        synchronize(application, second)
        ping(second, "keep-second")
        ping(third, "keep-third")
        assert (
            request_state(second, "before-expiry")["payload"]["host_player_id"]
            == host_session["player_id"]
        )
        second.portal.call(clock.advance, 1)
        synchronize(application, second)
        expired = lobby(second)
        same_lobby(expired, lobby(third))
        assert expired["room_revision"] == disconnected["room_revision"] + 1
        assert expired["payload"]["host_player_id"] == second_session["player_id"]
        assert len(expired["payload"]["players"]) == 2
        with client.websocket_connect("/ws") as stale:
            send(stale, "resume_session", "expired", {"resume_token": host_session["resume_token"]})
            error(stale, "session_expired", "expired")
            closed(stale, 1008)


def test_active_resume_fences_old_socket_and_preserves_cached_reply(clock):
    application = create_app(clock=clock)
    with TestClient(application) as client, ExitStack() as stack:
        old = stack.enter_context(client.websocket_connect("/ws"))
        session, _ = admit(old)
        original_ack = ready(old, True, "ready-before-resume")
        previous = lobby(old)
        current = stack.enter_context(client.websocket_connect("/ws"))
        resumed = resume(current, session)
        closed(old, 1008)
        assert resumed["payload"]["players"][0]["player_id"] == session["player_id"]
        # Even a frame queued on the fenced transport cannot act as the replacement.
        send(old, "leave_room", "stale-leave")
        synchronize(application, current)
        fresh = request_state(current, "after-stale")
        same_lobby(fresh, resumed)
        assert len(fresh["payload"]["players"]) == 1
        assert ready(current, True, "ready-before-resume") == original_ack
        same_lobby(request_state(current, "after-replayed-ready"), resumed)
        assert resumed["room_revision"] >= previous["room_revision"]


def test_empty_disconnected_room_expires_and_cannot_be_joined_or_resumed(clock):
    application = create_app(clock=clock)
    with TestClient(application) as client, ExitStack() as stack:
        owner = stack.enter_context(client.websocket_connect("/ws"))
        session, _ = admit(owner)
        owner.close()
        synchronize(application, owner)
        owner.portal.call(clock.advance, 30)
        synchronize(application, owner)
        with client.websocket_connect("/ws") as stranger:
            send(
                stranger,
                "join_room",
                "gone-room",
                {"room_code": session["room_code"], "name": "Crew"},
            )
            error(stranger, "room_not_found", "gone-room")
        with client.websocket_connect("/ws") as previous:
            send(
                previous,
                "resume_session",
                "gone-session",
                {"resume_token": session["resume_token"]},
            )
            error(previous, "session_expired", "gone-session")
            closed(previous, 1008)


def test_idle_room_expiry_closes_members_and_clears_registry(clock):
    app = create_app(
        clock=clock,
        rooms=RoomSettings(idle_timeout=60),
        connections=ConnectionSettings(inactivity_timeout=120),
    )
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as socket:
            session, _ = admit(socket)
            socket.portal.call(clock.advance, 59)
            ping(socket, "heartbeat-does-not-refresh-lobby")
            socket.portal.call(clock.advance, 1)
            synchronize(app, socket)
            error(socket, "session_expired", None)
            closed(socket, 1008)
            assert app.state.rooms.room_count == app.state.rooms.session_count == 0
            with client.websocket_connect("/ws") as previous:
                send(
                    previous, "resume_session", "expired", {"resume_token": session["resume_token"]}
                )
                error(previous, "session_expired", "expired")
                closed(previous, 1008)
    assert app.state.rooms.task_count == 0


def test_inbound_inactivity_is_followed_by_separate_membership_grace(clock):
    app = create_app(clock=clock)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as socket:
            session, _ = admit(socket)
            socket.portal.call(clock.wait_registered, 30)
            socket.portal.call(clock.advance, 30)
            closed(socket, 1001)
            synchronize(app, socket)
            assert app.state.rooms.session_count == 1
            replacement = client.websocket_connect("/ws")
            with replacement as fresh:
                snapshot = resume(fresh, session)
                assert snapshot["payload"]["players"][0]["connected"]
    assert app.state.rooms.session_count == app.state.rooms.task_count == 0


def test_application_shutdown_clears_live_rooms_sessions_and_owned_tasks(clock):
    app = create_app(clock=clock)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as socket:
            admit(socket)
            assert app.state.rooms.room_count == 1
    assert app.state.rooms.room_count == app.state.rooms.session_count == 0
    assert app.state.rooms.task_count == app.state.connections.task_count == 0
