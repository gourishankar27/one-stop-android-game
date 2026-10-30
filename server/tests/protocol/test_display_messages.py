"""Shared observer contract and strict identity/payload boundaries."""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from one_job.protocol.envelopes import FrameError, ServerMessage, encode_message, parse_text
from one_job.protocol.messages import SessionAcceptedPayload


def test_shared_display_contract_round_trips():
    path = Path(__file__).resolve().parents[3] / "docs/protocol-fixtures/phase12.json"
    for case in json.loads(path.read_text()):
        assert parse_text(json.dumps(case["request"])).model_dump(mode="json") == case["request"]
        for frame in [case["response"], *case.get("events", [])]:
            assert (
                json.loads(
                    encode_message(TypeAdapter(ServerMessage).validate_json(json.dumps(frame)))
                )
                == frame
            )


@pytest.mark.parametrize(
    "kind,player_id", [("player", None), ("display", "private-id"), ("other", None)]
)
def test_identity_kind_rejects_inconsistent_admission(kind, player_id):
    with pytest.raises(ValidationError):
        SessionAcceptedPayload(room_code="ABCD23", kind=kind, player_id=player_id, resume_token="x")


@pytest.mark.parametrize(
    "payload",
    [{}, {"room_code": "ABCD23", "name": "x"}, {"room_code": 123}, {"room_code": "SECR01"}],
)
def test_join_display_only_accepts_a_valid_code(payload):
    with pytest.raises(FrameError):
        parse_text(
            json.dumps(dict(version=1, type="join_display", request_id="display", payload=payload))
        )
