import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import RootModel

from one_job.protocol.envelopes import FrameError, ServerMessage, encode_message, parse_text
from tests.support import frame


class RoleReply(RootModel[ServerMessage]):
    pass


@pytest.mark.parametrize("phase", ["phase08", "phase14"])
def test_shared_synthetic_role_fixtures_roundtrip_strict_python_contract(phase):
    path = Path(__file__).resolve().parents[3] / f"docs/protocol-fixtures/{phase}.json"
    for case in json.loads(path.read_text(encoding="utf-8")):
        request = parse_text(json.dumps(case["request"]))
        for raw in [case["response"], *case.get("events", [])]:
            message = RoleReply.model_validate_json(json.dumps(raw)).root
            assert json.loads(encode_message(message)) == raw
            if raw is case["response"]:
                assert message.reply_to == request.request_id


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("briefing_ready", {}),
        ("briefing_ready", {"round_id": "bad"}),
        ("briefing_ready", {"round_id": str(UUID(int=99)), "player_id": "forged"}),
        (
            "player_action",
            {
                "round_id": str(UUID(int=99)),
                "client_action_seq": True,
                "action": {"type": "coolant"},
            },
        ),
        (
            "player_action",
            {
                "round_id": str(UUID(int=99)),
                "client_action_seq": 1,
                "action": {"type": "coolant", "role": "pilot"},
            },
        ),
        (
            "player_action",
            {
                "round_id": str(UUID(int=99)),
                "client_action_seq": 1,
                "action": {"type": "set_shield", "active": "true", "facing": "front"},
            },
        ),
    ],
)
def test_round_commands_reject_coercion_and_client_identity_or_role_fields(kind, payload):
    with pytest.raises(FrameError) as caught:
        parse_text(json.dumps(frame(kind, payload=payload)))
    assert caught.value.code == "invalid_message"


@pytest.mark.parametrize("sequence", [0, -1, 2**63, True, "1"])
def test_recovery_action_sequences_fit_android_signed_counter(sequence):
    with pytest.raises(FrameError):
        parse_text(
            json.dumps(
                frame(
                    "player_action",
                    payload={
                        "round_id": str(UUID(int=99)),
                        "client_action_seq": sequence,
                        "action": {"type": "coolant"},
                    },
                )
            )
        )
