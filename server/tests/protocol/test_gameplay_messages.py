"""Shared running-control snapshots and typed terminal action responses."""

import json
from pathlib import Path

from pydantic import RootModel

from one_job.protocol.envelopes import ServerMessage, encode_message, parse_text


class Reply(RootModel[ServerMessage]):
    pass


def test_shared_running_fixtures_round_trip_and_keep_owned_station_keys():
    fixtures = Path(__file__).parents[3] / "docs/protocol-fixtures/phase09.json"
    for case in json.loads(fixtures.read_text(encoding="utf-8")):
        parse_text(json.dumps(case["request"]))
        for frame in [case["response"], *case.get("events", [])]:
            result = Reply.model_validate_json(json.dumps(frame)).root
            assert json.loads(encode_message(result)) == frame
        if case["response"]["type"] == "role_state":
            view = case["response"]["payload"]
            roles = case["events"][0]["payload"]["roles"]
            assert set(view["stations"]) == set(roles)
            assert view["public"]["stage"] == "running"
            assert view["briefing"]["complete"] and not view["briefing"]["held_for_gameplay"]
