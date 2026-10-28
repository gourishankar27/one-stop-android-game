from dataclasses import FrozenInstanceError, fields

import pytest

from one_job.domain.actions import (
    Coolant,
    EmergencyShutdown,
    EngineBoost,
    Evade,
    MoveLane,
    PlayerAction,
    RechargeShield,
    SetEnginePower,
    SetShield,
    ShieldBoost,
)
from one_job.domain.types import ActionType, MoveDirection, Role, ShieldFacing


@pytest.mark.parametrize(
    ("action", "kind", "role"),
    [
        (MoveLane(MoveDirection.LEFT), "move_lane", Role.PILOT),
        (MoveLane(MoveDirection.RIGHT), "move_lane", Role.PILOT),
        (Evade(), "evade", Role.PILOT),
        (SetEnginePower(0), "set_engine_power", Role.ENGINEER),
        (SetEnginePower(100), "set_engine_power", Role.ENGINEER),
        (EngineBoost(), "engine_boost", Role.ENGINEER),
        (Coolant(), "coolant", Role.ENGINEER),
        (EmergencyShutdown(), "emergency_shutdown", Role.ENGINEER),
        (SetShield(True, ShieldFacing.LEFT), "set_shield", Role.SHIELDS),
        (SetShield(False, ShieldFacing.REAR), "set_shield", Role.SHIELDS),
        (RechargeShield(), "recharge_shield", Role.SHIELDS),
        (ShieldBoost(), "shield_boost", Role.SHIELDS),
    ],
)
def test_actions_have_contract_kinds_and_station_metadata(
    action: PlayerAction,
    kind: str,
    role: Role,
) -> None:
    assert action.kind == ActionType(kind)
    assert action.role == role
    assert not {"actor_id", "player_id", "role", "kind"} & {item.name for item in fields(action)}


@pytest.mark.parametrize(
    "value", [-1, 101, True, False, 1.0, float("nan"), float("inf"), "60", None]
)
def test_engine_power_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        SetEnginePower(value)


@pytest.mark.parametrize("direction", ["left", "right", "center", 0, True, None, ShieldFacing.LEFT])
def test_lane_action_requires_a_move_direction(direction: object) -> None:
    with pytest.raises(ValueError):
        MoveLane(direction)


@pytest.mark.parametrize("active", [0, 1, "true", None])
def test_shield_action_requires_boolean_active(active: object) -> None:
    with pytest.raises(ValueError):
        SetShield(active, ShieldFacing.FRONT)


@pytest.mark.parametrize("facing", ["front", "up", 1, True, None, MoveDirection.LEFT])
def test_shield_action_requires_a_shield_facing(facing: object) -> None:
    with pytest.raises(ValueError):
        SetShield(True, facing)


@pytest.mark.parametrize("facing", list(ShieldFacing))
def test_shield_accepts_every_declared_facing(facing: ShieldFacing) -> None:
    assert SetShield(False, facing).facing == facing


def test_actions_are_immutable_and_cannot_supply_identity_or_omit_required_fields() -> None:
    action = SetEnginePower(60)
    with pytest.raises(FrozenInstanceError):
        action.value = 100
    with pytest.raises(TypeError):
        Coolant(player_id="claimed-player")
    with pytest.raises(TypeError):
        SetShield(active=True)
    with pytest.raises(TypeError):
        Evade(kind=ActionType.COOLANT)
