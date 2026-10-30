"""Shared synthetic countdown/results/lifecycle contract, including lossy hull percent."""

import json
from pathlib import Path

import pytest
from pydantic import RootModel, ValidationError

from one_job.protocol.envelopes import FrameError, ServerMessage, encode_message, parse_text


class Reply(RootModel[ServerMessage]):
    pass


def cases():
    return json.loads(
        (Path(__file__).parents[3] / "docs/protocol-fixtures/phase11.json").read_text()
    )


def test_shared_lifecycle_fixtures_round_trip_and_keep_results_public():
    outcomes = set()
    for case in cases():
        parse_text(json.dumps(case["request"]))
        for frame in [case["response"], *case.get("events", [])]:
            assert (
                json.loads(encode_message(Reply.model_validate_json(json.dumps(frame)).root))
                == frame
            )
            if frame["type"] == "game_over":
                payload = frame["payload"]
                assert set(payload) == {"round_id", "result"}
                assert set(payload["result"]) == {
                    "outcome",
                    "reason",
                    "survived_ms",
                    "final_hull_percent",
                    "resolved_count",
                    "failed_count",
                    "players",
                }
                outcomes.add(payload["result"]["outcome"])
    assert outcomes == {"victory", "defeat", "aborted"}


@pytest.mark.parametrize("kind", ["play_again", "return_to_lobby"])
def test_lifecycle_commands_are_typed_empty_payloads(kind):
    with pytest.raises(FrameError) as error:
        parse_text(
            json.dumps({"version": 1, "type": kind, "request_id": "action", "payload": {"seed": 7}})
        )
    assert error.value.code == "invalid_message"


def test_result_consistency_roster_and_zero_percent_victory():
    frame = next(
        event
        for case in cases()
        for event in case.get("events", [])
        if event["type"] == "game_over" and event["payload"]["result"]["outcome"] == "victory"
    )
    assert frame["payload"]["result"]["final_hull_percent"] == 0
    Reply.model_validate_json(json.dumps(frame))
    for change in (
        {"reason": "player_left"},
        {"survived_ms": 1},
        {"players": [frame["payload"]["result"]["players"][0]] * 2},
    ):
        invalid = json.loads(json.dumps(frame))
        invalid["payload"]["result"].update(change)
        with pytest.raises(ValidationError):
            Reply.model_validate_json(json.dumps(invalid))
