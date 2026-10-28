"""Validated station intents only. Actor identity and execution belong to callers."""

from dataclasses import dataclass
from typing import ClassVar

from one_job.domain._validation import boolean, enumeration, integer
from one_job.domain.config import OUTPUT_MAX
from one_job.domain.types import ActionType, MoveDirection, Role, ShieldFacing


@dataclass(frozen=True, slots=True)
class MoveLane:
    direction: MoveDirection
    kind: ClassVar[ActionType] = ActionType.MOVE_LANE
    role: ClassVar[Role] = Role.PILOT

    def __post_init__(self) -> None:
        enumeration(self.direction, MoveDirection, "direction")


@dataclass(frozen=True, slots=True)
class Evade:
    kind: ClassVar[ActionType] = ActionType.EVADE
    role: ClassVar[Role] = Role.PILOT


@dataclass(frozen=True, slots=True)
class SetEnginePower:
    value: int
    kind: ClassVar[ActionType] = ActionType.SET_ENGINE_POWER
    role: ClassVar[Role] = Role.ENGINEER

    def __post_init__(self) -> None:
        integer(self.value, "value", 0, OUTPUT_MAX)


@dataclass(frozen=True, slots=True)
class EngineBoost:
    kind: ClassVar[ActionType] = ActionType.ENGINE_BOOST
    role: ClassVar[Role] = Role.ENGINEER


@dataclass(frozen=True, slots=True)
class Coolant:
    kind: ClassVar[ActionType] = ActionType.COOLANT
    role: ClassVar[Role] = Role.ENGINEER


@dataclass(frozen=True, slots=True)
class EmergencyShutdown:
    kind: ClassVar[ActionType] = ActionType.EMERGENCY_SHUTDOWN
    role: ClassVar[Role] = Role.ENGINEER


@dataclass(frozen=True, slots=True)
class SetShield:
    active: bool
    facing: ShieldFacing
    kind: ClassVar[ActionType] = ActionType.SET_SHIELD
    role: ClassVar[Role] = Role.SHIELDS

    def __post_init__(self) -> None:
        boolean(self.active, "active")
        enumeration(self.facing, ShieldFacing, "facing")


@dataclass(frozen=True, slots=True)
class RechargeShield:
    kind: ClassVar[ActionType] = ActionType.RECHARGE_SHIELD
    role: ClassVar[Role] = Role.SHIELDS


@dataclass(frozen=True, slots=True)
class ShieldBoost:
    kind: ClassVar[ActionType] = ActionType.SHIELD_BOOST
    role: ClassVar[Role] = Role.SHIELDS


type PlayerAction = (
    MoveLane
    | Evade
    | SetEnginePower
    | EngineBoost
    | Coolant
    | EmergencyShutdown
    | SetShield
    | RechargeShield
    | ShieldBoost
)
