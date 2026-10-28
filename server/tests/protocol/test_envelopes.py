import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from one_job.protocol.envelopes import (
    MAX_FRAME_BYTES,
    RESERVED_TYPES,
    FrameError,
    encode_message,
    error_message,
    parse_text,
    pong,
)
from one_job.protocol.messages import ErrorCode, SetEnginePowerInput
from tests.support import frame


def failure(value):
    with pytest.raises(FrameError) as caught:
        parse_text(json.dumps(value))
    return caught.value


def test_ping_pong_exact_contract():
    request = parse_text(json.dumps(frame()))
    assert json.loads(encode_message(pong(request))) == {
        "version": 1,
        "type": "pong",
        "reply_to": "p-1",
        "room_revision": None,
        "payload": {"nonce": "hello"},
    }


@pytest.mark.parametrize("kind", sorted(RESERVED_TYPES))
def test_reserved_payload_is_not_business_decoded(kind):
    payload = {"future_unknown": [None, True, 1, {"resume_token": "PRIVATE_SENTINEL"}]}
    parsed = parse_text(json.dumps(frame(kind, payload=payload)))
    assert parsed.type == kind
    assert parsed.payload == payload


@pytest.mark.parametrize("key", ["version", "type", "request_id", "payload"])
def test_missing_envelope_fields(key):
    value = frame()
    del value[key]
    assert failure(value).code == ErrorCode.INVALID_MESSAGE


@pytest.mark.parametrize("version", [True, False, 1.0, "1", None])
def test_strict_version_no_coercion(version):
    error = failure(frame(version=version))
    assert error.code == ErrorCode.INVALID_MESSAGE
    assert error.close_code is None


@pytest.mark.parametrize("version", [0, -1, 2, 100])
def test_unsupported_version(version):
    error = failure(frame(version=version))
    assert (error.code, error.reply_to, error.close_code) == (
        ErrorCode.UNSUPPORTED_VERSION,
        "p-1",
        1002,
    )


@pytest.mark.parametrize("payload", [None, [], "secret", 1, True])
def test_payload_must_be_object(payload):
    value = frame()
    value["payload"] = payload
    assert failure(value).code == ErrorCode.INVALID_MESSAGE


@pytest.mark.parametrize("value", [None, [], 12, "sentinel"])
def test_root_must_be_object(value):
    assert failure(value).reply_to is None


@pytest.mark.parametrize("request_id", ["", "x" * 65, "a b", "é", "a\n", 1, True, None])
def test_unsafe_request_id_is_never_echoed(request_id):
    assert failure(frame(request_id=request_id)).reply_to is None


@pytest.mark.parametrize("request_id", ["a", "_-012AbZ", "a" * 64])
def test_request_id_bounds(request_id):
    assert parse_text(json.dumps(frame(request_id=request_id))).request_id == request_id


@pytest.mark.parametrize("nonce", ["", "x" * 65, 1, True, None, "\ud800"])
def test_nonce_strict_bounds(nonce):
    assert failure(frame(payload={"nonce": nonce})).code == ErrorCode.INVALID_MESSAGE


@pytest.mark.parametrize("nonce", ["x", "x" * 64, "🚀" * 64])
def test_nonce_counts_unicode_characters(nonce):
    assert parse_text(json.dumps(frame(payload={"nonce": nonce}))).payload.nonce == nonce


@pytest.mark.parametrize("level", ["envelope", "payload"])
def test_unknown_fields_rejected(level):
    value = frame()
    (value if level == "envelope" else value["payload"])["resume_token"] = "SECRET_SENTINEL"
    error = failure(value)
    wire = encode_message(error_message(error.code, error.reply_to))
    assert error.code == ErrorCode.INVALID_MESSAGE
    assert "SECRET_SENTINEL" not in wire
    assert "resume_token" not in wire
    assert "SECRET_SENTINEL" not in str(error)


def test_unknown_type_is_not_echoed_as_operation():
    error = failure(frame("PRIVATE_SENTINEL"))
    assert error.code == ErrorCode.UNKNOWN_TYPE
    assert error.operation is None
    assert error.reply_to == "p-1"


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "{}{}",
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":1e9999}',
        '{"x":1,"x":2}',
        '{"payload":{"x":1,"x":2}}',
        '{"version":' + "1" * 4500 + "}",
        "\ud800",
    ],
)
def test_invalid_json_closes_1007(text):
    with pytest.raises(FrameError) as caught:
        parse_text(text)
    assert caught.value.close_code == 1007
    assert caught.value.reply_to is None


def test_deep_invalid_root_is_bounded_and_redacted():
    with pytest.raises(FrameError) as caught:
        parse_text("[" * 6000 + "]" * 6000)
    assert caught.value.code == ErrorCode.INVALID_MESSAGE
    assert caught.value.reply_to is None


def test_utf8_byte_limit_exact_boundary():
    value = frame("create_room", payload={"padding": ""})
    baseline = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    value["payload"]["padding"] = "é" * ((MAX_FRAME_BYTES - len(baseline)) // 2)
    text = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    text += " " * (MAX_FRAME_BYTES - len(text.encode("utf-8")))
    assert len(text.encode("utf-8")) == MAX_FRAME_BYTES
    assert parse_text(text).type == "create_room"
    with pytest.raises(FrameError) as caught:
        parse_text(text + " ")
    assert caught.value.close_code == 1009


@pytest.mark.parametrize("value", [True, "40", 40.0, -1, 101])
def test_adapter_action_dto_is_strict(value):
    with pytest.raises(ValidationError):
        SetEnginePowerInput(type="set_engine_power", value=value)


def test_shared_ping_fixture():
    path = Path(__file__).resolve().parents[3] / "docs/protocol-fixtures/phase03.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    for case in cases:
        if case["request"]["type"] == "ping":
            response = pong(parse_text(json.dumps(case["request"])))
        else:
            request = parse_text(json.dumps(case["request"]))
            response = error_message(ErrorCode.FEATURE_UNAVAILABLE, request.request_id)
        assert json.loads(encode_message(response)) == case["response"]
