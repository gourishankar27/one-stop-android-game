"""Domain identifiers and closed vocabularies; no identifiers are generated here."""

from enum import StrEnum
from typing import NewType
from uuid import UUID

PlayerId = NewType("PlayerId", UUID)
RoundId = NewType("RoundId", UUID)
EmergencyId = NewType("EmergencyId", int)


class Role(StrEnum):
    PILOT = "pilot"
    ENGINEER = "engineer"
    SHIELDS = "shields"


class Lane(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class MoveDirection(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class ShieldFacing(StrEnum):
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"
    REAR = "rear"


class RoundStage(StrEnum):
    BRIEFING = "briefing"
    COUNTDOWN = "countdown"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ABORTED = "aborted"


class EmergencyType(StrEnum):
    ASTEROID = "asteroid"
    OVERHEATING = "overheating"
    SHIELD_OVERLOAD = "shield_overload"


class EmergencyState(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    FAILED = "failed"


class Outcome(StrEnum):
    VICTORY = "victory"
    DEFEAT = "defeat"
    ABORTED = "aborted"


class ResultReason(StrEnum):
    SURVIVED = "survived"
    HULL_DESTROYED = "hull_destroyed"
    DISCONNECT_TIMEOUT = "disconnect_timeout"
    PLAYER_LEFT = "player_left"
    BRIEFING_TIMEOUT = "briefing_timeout"
    SERVER_OVERLOAD = "server_overload"


class ActionType(StrEnum):
    MOVE_LANE = "move_lane"
    EVADE = "evade"
    SET_ENGINE_POWER = "set_engine_power"
    ENGINE_BOOST = "engine_boost"
    COOLANT = "coolant"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"
    SET_SHIELD = "set_shield"
    RECHARGE_SHIELD = "recharge_shield"
    SHIELD_BOOST = "shield_boost"
