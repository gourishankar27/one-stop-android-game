import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import RootModel

from one_job.protocol.envelopes import FrameError, ServerMessage, encode_message, parse_text
from tests.support import frame


class RoleReply(RootModel[ServerMessage]):
    pass


def test_shared_synthetic_role_fixtures_roundtrip_strict_python_contract():
    path = Path(__file__).resolve().parents[3] / "docs/protocol-fixtures/phase08.json"
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
