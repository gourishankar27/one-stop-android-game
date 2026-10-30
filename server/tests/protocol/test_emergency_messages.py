"""Shared synthetic emergency fixtures agree with typed recipient allowlists."""

import json
from pathlib import Path

from pydantic import RootModel

from one_job.protocol.envelopes import ServerMessage, encode_message, parse_text


class Reply(RootModel[ServerMessage]):
    pass


def test_emergency_fixtures_round_trip_without_shared_targets():
    path = Path(__file__).parents[3] / "docs/protocol-fixtures/phase10.json"
    for case in json.loads(path.read_text(encoding="utf-8")):
        parse_text(json.dumps(case["request"]))
        for frame in [case["response"], *case["events"]]:
            assert (
                json.loads(encode_message(Reply.model_validate_json(json.dumps(frame)).root))
                == frame
            )
            if frame["type"] == "emergency_event":
                assert set(frame["payload"]) == {"round_id", "emergency_id", "kind", "status"}
        state = case["response"]["payload"]
        assert set(state["stations"]) == set(case["events"][0]["payload"]["roles"])
        for warning in state["public"]["warnings"]:
            assert set(warning) == {"emergency_id", "kind", "label"}
        for role, view in state["stations"].items():
            if role == "pilot":
                assert "instructions" not in view
                assert all("required_facing" not in hazard for hazard in view["hazards"])
            else:
                assert "hazards" not in view
                assert all("impact_lane" not in item for item in view["instructions"])
