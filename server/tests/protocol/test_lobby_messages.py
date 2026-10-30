import json
from pathlib import Path

import pytest
from pydantic import RootModel, ValidationError

from one_job.protocol.envelopes import (
    LOBBY_TYPES,
    RESERVED_TYPES,
    CreateRoomEnvelope,
    FrameError,
    JoinRoomEnvelope,
    LeaveRoomEnvelope,
    PlayerReadyEnvelope,
    RequestStateEnvelope,
    ResumeSessionEnvelope,
    ServerMessage,
    StartGameEnvelope,
    ack,
    encode_message,
    error_message,
    lobby_state,
    parse_text,
    session_accepted,
)
from one_job.protocol.messages import (
    ERROR_MESSAGES,
    ErrorCode,
    LobbyPlayer,
    LobbyStatePayload,
    SessionAcceptedPayload,
)
from tests.support import frame

PLAYER_ID = "00000000-0000-0000-0000-000000000001"


class FixtureReply(RootModel[ServerMessage]):
    pass


@pytest.mark.parametrize("filename", ["phase04.json", "phase06.json"])
def test_shared_lobby_contract_fixtures(filename):
    path = Path(__file__).resolve().parents[3] / "docs/protocol-fixtures" / filename
    for case in json.loads(path.read_text(encoding="utf-8")):
        request = parse_text(json.dumps(case["request"]))
        reply = FixtureReply.model_validate_json(json.dumps(case["response"])).root
        assert request.request_id == reply.reply_to
        assert json.loads(encode_message(reply)) == case["response"]


@pytest.mark.parametrize(
    "kind,payload,expected",
    [
        ("create_room", {"name": "Crew"}, CreateRoomEnvelope),
        ("join_room", {"room_code": "ABCD23", "name": "Crew"}, JoinRoomEnvelope),
        (
            "resume_session",
            {"resume_token": "invalid-but-syntactically-valid"},
            ResumeSessionEnvelope,
        ),
        ("leave_room", {}, LeaveRoomEnvelope),
        ("player_ready", {"ready": True}, PlayerReadyEnvelope),
        ("start_game", {}, StartGameEnvelope),
        ("request_state", {}, RequestStateEnvelope),
    ],
)
def test_lobby_operations_decode_to_distinct_strict_types(kind, payload, expected):
    message = parse_text(json.dumps(frame(kind, payload=payload)))
    assert isinstance(message, expected)
    assert message.type == kind
    assert message.request_id == "p-1"


def test_lobby_and_reserved_operation_sets_do_not_overlap():
    assert LOBBY_TYPES == {
        "create_room",
        "join_room",
        "join_display",
        "resume_session",
        "leave_room",
        "player_ready",
        "start_game",
        "request_state",
    }
    assert RESERVED_TYPES == set()
    assert not LOBBY_TYPES & RESERVED_TYPES


@pytest.mark.parametrize(
    "name,expected",
    [
        (" Crew ", "Crew"),
        ("\u2003Crew\u2003", "Crew"),
        ("🚀" * 20, "🚀" * 20),
        ("A", "A"),
        ("Captain Zoë", "Captain Zoë"),
    ],
)
@pytest.mark.parametrize("kind", ["create_room", "join_room"])
def test_names_trim_without_losing_unicode_characters(name, expected, kind):
    payload = {"name": name}
    if kind == "join_room":
        payload["room_code"] = "ABCD23"
    assert parse_text(json.dumps(frame(kind, payload=payload))).payload.name == expected


@pytest.mark.parametrize(
    "name",
    [
        "",
        " " * 3,
        "a" * 21,
        "🚀" * 21,
        "a\nb",
        "\tCrew",
        "Crew\r",
        "x\x00y",
        "x\x7fy",
        "x\x85y",
        "\ud800",
        1,
        True,
        None,
        [],
        {},
    ],
)
def test_invalid_names_are_safe_validation_errors(name):
    with pytest.raises(FrameError) as caught:
        parse_text(json.dumps(frame("create_room", payload={"name": name})))
    error = caught.value
    assert error.code == ErrorCode.INVALID_MESSAGE
    assert error.reply_to == "p-1"
    assert error.close_code is None
    assert error.operation == "create_room"


@pytest.mark.parametrize("code", ["ABCD23", "abcd23", " aBcD23 "])
def test_room_codes_normalize_ascii_case_and_outer_whitespace(code):
    message = parse_text(
        json.dumps(frame("join_room", payload={"room_code": code, "name": "Crew"}))
    )
    assert message.payload.room_code == "ABCD23"


@pytest.mark.parametrize(
    "code",
    [
        "",
        "ABC23",
        "ABCDEFG",
        "ABCD20",
        "ABCD21",
        "ABCD2I",
        "ABCD2O",
        "AB CD2",
        "ＡBCD23",
        "ßBCD2",
        "ABCD2é",
        123456,
        True,
        None,
        [],
    ],
)
def test_invalid_room_codes_do_not_reach_admission(code):
    with pytest.raises(FrameError) as caught:
        parse_text(json.dumps(frame("join_room", payload={"room_code": code, "name": "Crew"})))
    assert caught.value.code == ErrorCode.INVALID_MESSAGE
    assert caught.value.close_code is None


@pytest.mark.parametrize("ready", [0, 1, "true", "false", None, [], {}])
def test_ready_is_strict_boolean(ready):
    with pytest.raises(FrameError) as caught:
        parse_text(json.dumps(frame("player_ready", payload={"ready": ready})))
    assert caught.value.code == ErrorCode.INVALID_MESSAGE


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("create_room", {}),
        ("join_room", {"name": "Crew"}),
        ("join_room", {"room_code": "ABCD23"}),
        ("resume_session", {}),
        ("player_ready", {}),
        ("create_room", {"name": "Crew", "host": True}),
        ("join_room", {"room_code": "ABCD23", "name": "Crew", "player_id": PLAYER_ID}),
        ("resume_session", {"resume_token": "TOKEN_SENTINEL", "name": "Crew"}),
        ("leave_room", {"player_id": PLAYER_ID}),
        ("start_game", {"seed": 1}),
        ("request_state", {"host": True}),
        ("player_ready", {"ready": True, "player_id": PLAYER_ID}),
    ],
)
def test_required_and_allowlisted_lobby_fields(kind, payload):
    with pytest.raises(FrameError) as caught:
        parse_text(json.dumps(frame(kind, payload=payload)))
    error = caught.value
    assert error.code == ErrorCode.INVALID_MESSAGE
    assert "TOKEN_SENTINEL" not in str(error)
    assert "TOKEN_SENTINEL" not in encode_message(error_message(error.code, error.reply_to))


@pytest.mark.parametrize("token", ["", "x" * 257, "\ud800", 1, True, None, [], {}])
def test_resume_token_requires_bounded_valid_string(token):
    with pytest.raises(FrameError) as caught:
        parse_text(json.dumps(frame("resume_session", payload={"resume_token": token})))
    assert caught.value.code == ErrorCode.INVALID_MESSAGE


@pytest.mark.parametrize("token", ["x", "x" * 256, "not-a-session-token"])
def test_unknown_bounded_tokens_reach_service_and_are_hidden_in_repr(token):
    message = parse_text(json.dumps(frame("resume_session", payload={"resume_token": token})))
    assert message.payload.resume_token == token
    assert token not in repr(message.payload)
    assert token not in repr(message)


def test_session_accepted_is_targeted_and_hides_token_in_repr_only():
    payload = SessionAcceptedPayload(
        room_code="ABCD23",
        player_id=PLAYER_ID,
        resume_token="TOKEN_SENTINEL",
    )
    message = session_accepted("admit-1", 1, payload)
    assert "TOKEN_SENTINEL" not in repr(message)
    assert json.loads(encode_message(message)) == {
        "version": 1,
        "type": "session_accepted",
        "reply_to": "admit-1",
        "room_revision": 1,
        "payload": {
            "room_code": "ABCD23",
            "kind": "player",
            "player_id": PLAYER_ID,
            "resume_token": "TOKEN_SENTINEL",
        },
    }


def test_lobby_projection_shape_has_no_credential_fields():
    payload = LobbyStatePayload(
        room_code="ABCD23",
        stage="lobby",
        host_player_id=PLAYER_ID,
        players=(LobbyPlayer(player_id=PLAYER_ID, name="Crew", connected=True, ready=False),),
        can_start=False,
    )
    unsolicited = json.loads(encode_message(lobby_state(payload, 2)))
    targeted = json.loads(encode_message(lobby_state(payload, 2, "state-1")))
    assert unsolicited["reply_to"] is None
    assert targeted["reply_to"] == "state-1"
    assert unsolicited["room_revision"] == targeted["room_revision"] == 2
    assert (
        unsolicited["payload"]
        == targeted["payload"]
        == {
            "room_code": "ABCD23",
            "stage": "lobby",
            "host_player_id": PLAYER_ID,
            "players": [
                {"player_id": PLAYER_ID, "name": "Crew", "connected": True, "ready": False}
            ],
            "can_start": False,
        }
    )
    assert "resume_token" not in encode_message(lobby_state(payload, 2))
    with pytest.raises(ValidationError):
        LobbyPlayer(
            player_id=PLAYER_ID,
            name="Crew",
            connected=True,
            ready=False,
            resume_token="TOKEN_SENTINEL",
        )


def test_temporarily_vacant_host_seat_is_nullable():
    payload = LobbyStatePayload(
        room_code="ABCD23",
        stage="lobby",
        host_player_id=None,
        players=(LobbyPlayer(player_id=PLAYER_ID, name="Crew", connected=False, ready=False),),
        can_start=False,
    )
    assert json.loads(encode_message(lobby_state(payload, 2)))["payload"]["host_player_id"] is None


@pytest.mark.parametrize("operation", ["leave_room", "player_ready"])
def test_ack_envelope_is_correlated(operation):
    assert json.loads(encode_message(ack("command-1", 8, operation))) == {
        "version": 1,
        "type": "ack",
        "reply_to": "command-1",
        "room_revision": 8,
        "payload": {"operation": operation},
    }


@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.ROOM_NOT_FOUND,
        ErrorCode.ROOM_FULL,
        ErrorCode.ROOM_STARTED,
        ErrorCode.CAPACITY,
        ErrorCode.NOT_HOST,
        ErrorCode.NOT_READY,
        ErrorCode.REQUEST_ID_CONFLICT,
        ErrorCode.SESSION_EXPIRED,
    ],
)
def test_lobby_error_codes_have_static_safe_messages(code):
    response = json.loads(encode_message(error_message(code, "request-1", 3)))
    assert response["payload"]["code"] == code.value
    assert response["payload"]["message"] == ERROR_MESSAGES[code]
    assert response["reply_to"] == "request-1"
    assert response["room_revision"] == 3
