import json
import logging

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from one_job.application.connections import ConnectionSettings
from one_job.main import create_app
from one_job.protocol.envelopes import MAX_FRAME_BYTES, RESERVED_TYPES
from tests.support import frame, owned_tasks


def assert_error(response, code, reply_to="p-1"):
    assert set(response) == {"version", "type", "reply_to", "room_revision", "payload"}
    assert response["version"] == 1
    assert response["type"] == "error"
    assert response["reply_to"] == reply_to
    assert response["room_revision"] is None
    assert response["payload"]["code"] == code
    assert set(response["payload"]) == {"code", "message", "retryable"}


def assert_closed(socket, code):
    with pytest.raises(WebSocketDisconnect) as caught:
        socket.receive_json()
    assert caught.value.code == code


def test_ping_then_health_still_independent(clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            socket.send_json(frame())
            assert socket.receive_json() == {
                "version": 1,
                "type": "pong",
                "reply_to": "p-1",
                "room_revision": None,
                "payload": {"nonce": "hello"},
            }
            assert client.get("/health").json() == {"status": "ok", "service": "one-job-server"}
            assert client.get("/rooms").status_code == 404


@pytest.mark.parametrize("kind", sorted(RESERVED_TYPES))
def test_future_commands_never_admit_or_call_engine(kind, clock):
    application = create_app(clock=clock)
    with TestClient(application) as client:
        with client.websocket_connect("/ws") as socket:
            socket.send_json(frame(kind, payload={"resume_token": "PRIVATE_TOKEN_SENTINEL"}))
            response = socket.receive_json()
            assert_error(response, "feature_unavailable")
            assert "PRIVATE_TOKEN_SENTINEL" not in json.dumps(response)
            assert not hasattr(application.state, "rooms")
            assert not hasattr(application.state, "engine")


@pytest.mark.parametrize(
    "value,code",
    [
        (frame("unknown-SECRET_SENTINEL"), "unknown_type"),
        ({**frame(), "extra": "SECRET_SENTINEL"}, "invalid_message"),
        (frame(payload={"nonce": "ok", "extra": "SECRET_SENTINEL"}), "invalid_message"),
        (frame(version=True), "invalid_message"),
        (frame(payload={"nonce": 1}), "invalid_message"),
    ],
)
def test_recoverable_errors_then_ping(value, code, clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            socket.send_json(value)
            response = socket.receive_json()
            assert_error(response, code)
            assert "SECRET_SENTINEL" not in json.dumps(response)
            socket.send_json(frame(request_id="next"))
            assert socket.receive_json()["type"] == "pong"


@pytest.mark.parametrize(
    "text,code,error,reply",
    [
        ("{", 1007, "invalid_message", None),
        ("x" * (MAX_FRAME_BYTES + 1), 1009, "invalid_message", None),
        (json.dumps(frame(version=2)), 1002, "unsupported_version", "p-1"),
        ('{"version":1,"version":1}', 1007, "invalid_message", None),
    ],
)
def test_fatal_text_errors_reply_then_close(text, code, error, reply, clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            socket.send_text(text)
            assert_error(socket.receive_json(), error, reply)
            assert_closed(socket, code)


@pytest.mark.parametrize("size,code", [(1, 1007), (MAX_FRAME_BYTES + 1, 1009)])
def test_binary_frames_rejected(size, code, clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            socket.send_bytes(b"x" * size)
            assert_error(socket.receive_json(), "invalid_message", None)
            assert_closed(socket, code)


def test_deadline_is_ten_seconds_and_ping_does_not_extend_it(clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            socket.portal.call(clock.wait_registered, 10)
            socket.portal.call(clock.advance, 9)
            socket.send_json(frame())
            assert socket.receive_json()["type"] == "pong"
            socket.send_json(frame("create_room", request_id="future"))
            assert_error(socket.receive_json(), "feature_unavailable", "future")
            socket.portal.call(clock.advance, 1)
            assert_error(socket.receive_json(), "not_authenticated", None)
            assert_closed(socket, 1008)


def test_heartbeat_budget_is_separate_and_sustained_abuse_closes(clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            for index in range(40):
                socket.send_json(frame("request_state", request_id=f"c-{index}"))
                assert_error(socket.receive_json(), "feature_unavailable", f"c-{index}")
            for index in range(3):
                socket.send_json(frame(request_id=f"p-{index}"))
                assert socket.receive_json()["type"] == "pong"
            for index in range(5):
                socket.send_json(frame("request_state", request_id=f"r-{index}"))
                assert_error(socket.receive_json(), "rate_limited", f"r-{index}")
            assert_closed(socket, 1008)


def test_ping_rate_replenishes_with_injected_time(clock):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            for _ in range(3):
                socket.send_json(frame())
                assert socket.receive_json()["type"] == "pong"
            socket.send_json(frame())
            assert_error(socket.receive_json(), "rate_limited")
            socket.portal.call(clock.advance, 1)
            socket.send_json(frame())
            assert socket.receive_json()["type"] == "pong"


@pytest.mark.parametrize(
    "operation,capacity,bad_frame,code,close",
    [
        ("ping", 3, json.dumps(frame(version=2)), "unsupported_version", 1002),
        ("request_state", 40, "{", "invalid_message", 1007),
    ],
)
def test_fatal_protocol_error_takes_precedence_over_exhausted_rate_budget(
    clock,
    operation,
    capacity,
    bad_frame,
    code,
    close,
):
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            for _ in range(capacity):
                socket.send_json(frame(operation))
                socket.receive_json()
            socket.send_text(bad_frame)
            response = socket.receive_json()
            assert response["payload"]["code"] == code
            assert_closed(socket, close)


def test_lifecycle_logs_are_allowlisted_even_for_malformed_and_secret_payloads(caplog, clock):
    caplog.set_level(logging.INFO, logger="one_job.connections")
    application = create_app(clock=clock)
    with TestClient(application) as client:
        with client.websocket_connect("/ws") as socket:
            socket.send_json(
                frame(
                    "resume_session",
                    payload={
                        "resume_token": "TOKEN_SENTINEL",
                        "stations": {"engineer": "VIEW_SENTINEL"},
                    },
                )
            )
            assert_error(socket.receive_json(), "feature_unavailable")
            socket.send_json(frame("UNKNOWN_OPERATION_SENTINEL"))
            assert_error(socket.receive_json(), "unknown_type")
            socket.send_json(frame(request_id="INVALID ID SENTINEL"))
            assert_error(socket.receive_json(), "invalid_message", None)
            socket.send_text('{"resume_token":"MALFORMED_SENTINEL"')
            assert_error(socket.receive_json(), "invalid_message", None)
            assert_closed(socket, 1007)
    records = [r for r in caplog.records if r.name == "one_job.connections"]
    assert {r.message for r in records} >= {
        "connection_opened",
        "command_completed",
        "connection_closed",
    }
    for record in records:
        serialized = str(record.__dict__)
        assert "SENTINEL" not in serialized
        assert "resume_token" not in serialized
        assert "stations" not in serialized
        assert record.exc_info is None
        assert record.generation == 1
        assert record.duration_ms >= 0
    assert any(r.request_id == "p-1" and r.operation == "resume_session" for r in records)
    assert application.state.connections.active_count == 0
    assert application.state.connections.task_count == 0


def test_unexpected_exception_is_redacted(monkeypatch, caplog, clock):
    def broken_parser(_):
        raise RuntimeError("TOKEN_SENTINEL private state")

    monkeypatch.setattr("one_job.application.connections.parse_text", broken_parser)
    caplog.set_level(logging.INFO, logger="one_job.connections")
    with TestClient(create_app(clock=clock)) as client:
        with client.websocket_connect("/ws") as socket:
            socket.send_json(frame())
            response = socket.receive_json()
            assert_error(response, "internal_error", None)
            assert "SENTINEL" not in json.dumps(response)
            assert_closed(socket, 1011)
    assert "SENTINEL" not in str([record.__dict__ for record in caplog.records])


def test_app_factories_have_independent_managers_and_cleanup(clock):
    apps = [create_app(clock=clock), create_app()]
    for app in apps:
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as socket:
                socket.send_json(frame())
                assert socket.receive_json()["type"] == "pong"
                assert app.state.connections.active_count == 1
            assert client.portal.call(owned_tasks) == []
            assert app.state.connections.active_count == 0
    assert apps[0].state.connections is not apps[1].state.connections
    assert all(app.state.connections._generation == 1 for app in apps)


def test_shutdown_closes_open_connections_and_awaits_tasks(clock):
    application = create_app(clock=clock)
    with TestClient(application) as client:
        with client.websocket_connect("/ws") as socket:
            socket.portal.call(application.state.connections.aclose)
            assert_closed(socket, 1001)
            assert socket.portal.call(owned_tasks) == []
            assert application.state.connections.active_count == 0


def test_configurable_admission_timeout(clock):
    app = create_app(clock=clock, connections=ConnectionSettings(admission_timeout=2))
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as socket:
            socket.portal.call(clock.wait_registered, 2)
            socket.portal.call(clock.advance, 2)
            assert_error(socket.receive_json(), "not_authenticated", None)
            assert_closed(socket, 1008)
