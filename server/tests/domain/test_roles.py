from dataclasses import FrozenInstanceError
from random import Random
from uuid import UUID

import pytest

from one_job.domain.actions import (
    Coolant,
    EmergencyShutdown,
    EngineBoost,
    Evade,
    MoveLane,
    RechargeShield,
    SetEnginePower,
    SetShield,
    ShieldBoost,
)
from one_job.domain.config import GameConfig
from one_job.domain.engine import ActionCode, GameEngine
from one_job.domain.models import Player
from one_job.domain.roles import STATIONS, StationMetadata, assign_roles
from one_job.domain.types import (
    MoveDirection,
    PlayerId,
    ResultReason,
    Role,
    RoundId,
    RoundStage,
    ShieldFacing,
)


def players(count=3):
    return tuple(Player(PlayerId(UUID(int=index + 1)), "Crew") for index in range(count))


@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("seed", [0, 1, 2, 17, 999_999])
def test_assignment_reproduces_documented_shuffle_order_and_freezes_roster(count, seed):
    roster = players(count)
    original = list(roster)
    expected = [player.player_id for player in roster]
    Random(seed).shuffle(expected)
    rng = Random(seed)
    assigned = assign_roles(original, rng)
    assert assigned == assign_roles(roster, Random(seed))
    assert assigned.player_ids == tuple(player.player_id for player in roster)
    assert tuple(assigned.owners) == tuple(Role)
    assert assigned.owners[Role.PILOT] == expected[0]
    assert assigned.owners[Role.ENGINEER] == expected[1]
    assert assigned.owners[Role.SHIELDS] == expected[-1]
    original.clear()
    assert len(assigned.player_ids) == count
    with pytest.raises(TypeError):
        assigned.owners[Role.PILOT] = expected[-1]
    if count == 2:
        assert assigned.roles_for(expected[1]) == (Role.ENGINEER, Role.SHIELDS)


@pytest.mark.parametrize(
    "roster", [(), players(1), players(4), (players()[0], players()[0]), ["invalid"], None]
)
def test_invalid_roster_does_not_consume_randomness(roster):
    rng = Random(7)
    before = rng.getstate()
    with pytest.raises(ValueError):
        assign_roles(roster, rng)
    assert rng.getstate() == before


def test_station_metadata_is_immutable_and_separate_from_mutable_rules():
    for role in Role:
        metadata = STATIONS[role]
        assert metadata.role == role and metadata.title and len(metadata.steps) == 2
        with pytest.raises(FrozenInstanceError):
            metadata.title = "changed"
    with pytest.raises(TypeError):
        STATIONS[Role.PILOT] = STATIONS[Role.SHIELDS]
    values = ["Read this"]
    metadata = StationMetadata(Role.PILOT, "Pilot", values)
    values.clear()
    assert metadata.steps == ("Read this",)


@pytest.mark.parametrize(
    "action",
    [
        MoveLane(MoveDirection.LEFT),
        Evade(),
        SetEnginePower(50),
        EngineBoost(),
        Coolant(),
        EmergencyShutdown(),
        SetShield(True, ShieldFacing.LEFT),
        RechargeShield(),
        ShieldBoost(),
    ],
)
def test_every_action_checks_authenticated_station_owner_even_before_running(action):
    roster = players()
    rng = Random(3)
    assignment = assign_roles(roster, rng)
    engine = GameEngine(
        GameConfig(), 3, roster, assignment, round_id=RoundId(UUID(int=99)), rng=rng
    )
    before = engine.snapshot()
    owner = assignment.owners[action.role]
    other = next(player.player_id for player in roster if player.player_id != owner)
    assert engine.authorize_action(owner, action) == ActionCode.ACCEPTED
    assert engine.authorize_action(other, action) == ActionCode.NOT_ROLE_OWNER
    assert engine.snapshot() is before and engine.accepted_actions == ()
    engine.start()
    assert engine.apply_action(other, action).code == ActionCode.NOT_ROLE_OWNER


def test_engine_copies_post_assignment_rng_and_briefing_pause_resume_abort_are_pure():
    roster = players(2)
    rng = Random(5)
    assignment = assign_roles(roster, rng)
    engine = GameEngine(
        GameConfig(), 5, roster, assignment, round_id=RoundId(UUID(int=99)), rng=rng
    )
    expected = rng.getstate()
    rng.random()
    assert engine._rng.getstate() == expected
    first = engine.snapshot()
    paused = engine.pause()
    assert (
        paused.round.stage == RoundStage.PAUSED and paused.round.paused_from == RoundStage.BRIEFING
    )
    assert engine.resume() == first
    aborted = engine.abort(ResultReason.BRIEFING_TIMEOUT)
    assert aborted.round.stage == RoundStage.ABORTED
    assert aborted.round.result.reason == ResultReason.BRIEFING_TIMEOUT
    assert aborted.tick_index == 0 and aborted.ship == first.ship
    assert engine.abort(ResultReason.PLAYER_LEFT) is aborted
    assert engine._rng.getstate() == expected
