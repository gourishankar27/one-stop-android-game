from dataclasses import replace

import pytest

from one_job.domain import GameState
from one_job.domain.models import AsteroidTarget, Emergency, OverheatingTarget, ShieldOverloadTarget
from one_job.domain.types import EmergencyId, EmergencyState, EmergencyType, Lane, ShieldFacing


@pytest.fixture
def asteroid() -> Emergency:
    return Emergency(EmergencyId(1), AsteroidTarget(Lane.LEFT, ShieldFacing.FRONT), 80, 160)


def test_typed_targets_fix_the_emergency_kind(asteroid: Emergency) -> None:
    assert asteroid.kind == EmergencyType.ASTEROID
    assert replace(asteroid, target=OverheatingTarget()).kind == EmergencyType.OVERHEATING
    assert replace(asteroid, target=ShieldOverloadTarget()).kind == EmergencyType.SHIELD_OVERLOAD


@pytest.mark.parametrize(
    "changes",
    [
        {"emergency_id": 0},
        {"emergency_id": True},
        {"emergency_id": "1"},
        {"target": {}},
        {"start_tick": -1},
        {"start_tick": 80.0},
        {"deadline_tick": 80},
        {"deadline_tick": True},
        {"state": "active"},
        {"progress_ticks": -1},
        {"progress_ticks": True},
        {"progress_ticks": 1},
        {"finished_tick": 100},
        {"state": EmergencyState.RESOLVED},
        {"state": EmergencyState.RESOLVED, "finished_tick": 79},
        {"state": EmergencyState.RESOLVED, "finished_tick": 161},
        {"state": EmergencyState.FAILED, "finished_tick": 100},
    ],
)
def test_emergency_identity_timing_and_status_are_consistent(
    asteroid: Emergency,
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(asteroid, **changes)


def test_completed_emergency_records_require_explicit_finished_ticks(asteroid: Emergency) -> None:
    resolved = replace(asteroid, state=EmergencyState.RESOLVED, finished_tick=160)
    failed = replace(asteroid, state=EmergencyState.FAILED, finished_tick=160)
    assert resolved.emergency_id == failed.emergency_id == asteroid.emergency_id
    assert asteroid.state == EmergencyState.ACTIVE and asteroid.finished_tick is None


def test_overload_progress_and_window_bounds(asteroid: Emergency) -> None:
    overload = replace(asteroid, target=ShieldOverloadTarget(), progress_ticks=10)
    assert overload.progress_ticks == 10
    with pytest.raises(ValueError):
        replace(overload, progress_ticks=21)
    with pytest.raises(ValueError):
        replace(overload, deadline_tick=99)
    with pytest.raises(ValueError):
        replace(overload, state=EmergencyState.RESOLVED, finished_tick=85)


@pytest.mark.parametrize(
    ("target_type", "changes"),
    [
        (AsteroidTarget, {"impact_lane": "left", "required_facing": ShieldFacing.FRONT}),
        (AsteroidTarget, {"impact_lane": Lane.LEFT, "required_facing": "front"}),
        (OverheatingTarget, {"max_output": 101}),
        (OverheatingTarget, {"max_temperature": True}),
        (OverheatingTarget, {"max_temperature": 1001}),
        (ShieldOverloadTarget, {"max_output": -1}),
        (ShieldOverloadTarget, {"hold_ticks": 0}),
        (ShieldOverloadTarget, {"hold_ticks": True}),
    ],
)
def test_emergency_targets_validate_parameter_domains(
    target_type: type, changes: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        target_type(**changes)


def test_snapshot_rejects_impossible_emergency_collections(
    game_state: GameState, asteroid: Emergency
) -> None:
    state = replace(game_state, round=replace(game_state.round, tick_index=80))
    overload = replace(asteroid, emergency_id=EmergencyId(2), target=ShieldOverloadTarget())
    assert len(replace(state, emergencies=(asteroid, overload)).emergencies) == 2
    for emergencies in (
        (asteroid, asteroid),
        (asteroid, replace(asteroid, emergency_id=EmergencyId(2))),
        (
            asteroid,
            overload,
            replace(asteroid, emergency_id=EmergencyId(3), target=OverheatingTarget()),
        ),
        (replace(asteroid, start_tick=81),),
        (replace(asteroid, state=EmergencyState.RESOLVED, finished_tick=160),),
        (replace(overload, progress_ticks=1),),
    ):
        with pytest.raises(ValueError):
            replace(state, emergencies=emergencies)
    with pytest.raises(ValueError):
        replace(game_state, emergencies=(asteroid,))
    with pytest.raises(ValueError):
        replace(state, round=replace(state.round, tick_index=161), emergencies=(asteroid,))
    with pytest.raises(ValueError):
        replace(
            state,
            config=replace(state.config, max_active_emergencies=1),
            emergencies=(asteroid, overload),
        )
