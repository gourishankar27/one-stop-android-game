"""Concrete internal replay harness; JSON parsing here is test data, not transport."""

import json
from pathlib import Path
from typing import Any, NamedTuple
from uuid import UUID

import pytest

from one_job.domain import GameConfig, GameEngine, GameState, Player, PlayerId, Role, RoleAssignment
from one_job.domain.actions import Coolant, MoveLane, SetEnginePower
from one_job.domain.engine import (
    ENGINE_VERSION,
    ActionApplied,
    ActionResult,
    EngineAction,
    RoundEnded,
)
from one_job.domain.types import MoveDirection, RoundId

FIXTURES = Path(__file__).parents[1] / "fixtures" / "engine"


class ReplayRun(NamedTuple):
    states: tuple[GameState, ...]
    boundaries: tuple[GameState, ...]
    results: tuple[ActionResult, ...]
    actions: tuple[ActionApplied, ...]
    events: tuple[RoundEnded, ...]


def engine_for(data: dict[str, Any]) -> GameEngine:
    config = GameConfig(**data["config"])
    assert data["engine_version"] == ENGINE_VERSION
    assert data["config_version"] == config.version
    assert data["python_version"] == "3.12.10"  # Fixture provenance; no cross-version RNG claim.
    players = tuple(Player(PlayerId(UUID(item["id"])), item["name"]) for item in data["players"])
    ids = tuple(player.player_id for player in players)
    assignments = RoleAssignment(
        ids, {Role(role): ids[index] for role, index in data["owners"].items()}
    )
    return GameEngine(
        config, data["seed"], players, assignments, round_id=RoundId(UUID(data["round_id"]))
    )


def action_for(request: dict[str, Any]) -> EngineAction:
    match request["type"]:
        case "set_engine_power":
            return SetEnginePower(request["value"])
        case "move_lane":
            return MoveLane(MoveDirection(request["direction"]))
        case "coolant":
            return Coolant()
        case _:
            raise AssertionError("fixture contains a non-Phase-02 action")


def run_fixture(data: dict[str, Any]) -> ReplayRun:
    engine = engine_for(data)
    states = [engine.start()]
    boundaries: list[GameState] = []
    results: list[ActionResult] = []
    events: list[RoundEnded] = []
    handled = 0
    while engine.snapshot().round.result is None:
        tick = engine.snapshot().tick_index
        for request in data["requests"]:
            if request["tick"] != tick:
                continue
            actor = engine.snapshot().players[request["actor"]].player_id
            result = engine.apply_action(actor, action_for(request))
            assert result.code == request["code"]
            if result.accepted:
                assert result.events[0].order == request["order"]
                assert result.events[0].tick_index == tick
            results.append(result)
            states.append(engine.snapshot())
            handled += 1
        boundaries.append(engine.snapshot())
        for expected in data["checkpoints"]:
            if expected["tick"] == tick:
                ship = engine.snapshot().ship
                assert (ship.temperature, ship.hull, ship.lane) == (
                    expected["temperature"],
                    expected["hull"],
                    expected["lane"],
                )
        update = engine.tick()
        states.append(update.state)
        events.extend(update.events)
    assert handled == len(data["requests"])
    expected = data["expected_end"]
    final = engine.snapshot()
    assert (
        final.tick_index,
        final.round.result.outcome,
        final.ship.hull,
        final.ship.temperature,
    ) == (
        expected["tick"],
        expected["outcome"],
        expected["hull"],
        expected["temperature"],
    )
    assert len(events) == 1
    return ReplayRun(
        tuple(states), tuple(boundaries), tuple(results), engine.accepted_actions, tuple(events)
    )


@pytest.mark.parametrize("name", ["ordered-victory", "heat-defeat", "hull-timer-tie"])
def test_replay_compares_every_snapshot_and_accepted_order(name: str) -> None:
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    original = run_fixture(data)
    assert original == run_fixture(data)
    # Replaying only accepted records reproduces each boundary despite rejected requests.
    replay = engine_for(data)
    replay.start()
    replay_events: list[RoundEnded] = []
    for state in original.boundaries:
        for record in original.actions:
            if record.tick_index == state.tick_index:
                assert replay.apply_action(record.actor_id, record.action).events == (record,)
        assert replay.snapshot() == state
        replay_events.extend(replay.tick().events)
    assert replay.snapshot() == original.states[-1]
    assert replay.accepted_actions == original.actions
    assert tuple(replay_events) == original.events


def test_replay_observes_a_changed_valid_action_and_no_randomness_yet() -> None:
    data = json.loads((FIXTURES / "ordered-victory.json").read_text(encoding="utf-8"))
    one, two, other_seed = engine_for(data), engine_for(data), engine_for({**data, "seed": -999})
    for engine in (one, two, other_seed):
        actor = engine.start().assignments.owners[Role.ENGINEER]
        assert engine.apply_action(actor, SetEnginePower(60 if engine is two else 40)).accepted
        engine.tick(10)
    assert one.snapshot() == other_seed.snapshot()
    assert one.snapshot().ship.temperature == 290
    assert two.snapshot().ship.temperature == 320
    assert one.snapshot() != two.snapshot()
