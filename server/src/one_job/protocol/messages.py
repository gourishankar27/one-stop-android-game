"""Allowlisted v1 payloads; planned gameplay is not dispatched by the socket yet."""

from enum import StrEnum
from typing import Annotated, Literal
from unicodedata import category

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
)

RequestId = Annotated[str, StringConstraints(strict=True, pattern=r"\A[A-Za-z0-9_-]{1,64}\z")]
NonnegativeInt = Annotated[StrictInt, Field(ge=0)]
Percent = Annotated[StrictInt, Field(ge=0, le=100)]
Stage = Literal["briefing", "countdown", "running", "paused", "finished", "aborted"]
LobbyStage = Literal["lobby", "briefing", "countdown", "running", "paused", "finished", "aborted"]
AckOperation = Literal["leave_room", "player_ready", "start_game", "briefing_ready"]
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def normalize_name(value: str) -> str:
    if any(category(character) == "Cc" for character in value):
        raise ValueError("name must not contain control characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("name must contain Unicode scalar values") from None
    value = value.strip()
    if not 1 <= len(value) <= 20:
        raise ValueError("trimmed name must contain 1 to 20 characters")
    return value


def normalize_room_code(value: str) -> str:
    value = value.strip()
    if not value.isascii():
        raise ValueError("room code must use ASCII symbols")
    value = value.upper()
    if len(value) != 6 or any(character not in ROOM_CODE_ALPHABET for character in value):
        raise ValueError("room code must contain six allowed symbols")
    return value


Name = Annotated[StrictStr, AfterValidator(normalize_name)]
RoomCode = Annotated[StrictStr, AfterValidator(normalize_room_code)]


def validate_resume_token(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("resume token must contain Unicode scalar values") from None
    return value


ResumeToken = Annotated[
    StrictStr, Field(min_length=1, max_length=256), AfterValidator(validate_resume_token)
]


class DTO(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class ErrorCode(StrEnum):
    INVALID_MESSAGE = "invalid_message"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNKNOWN_TYPE = "unknown_type"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    NOT_AUTHENTICATED = "not_authenticated"
    ROOM_NOT_FOUND = "room_not_found"
    ROOM_FULL = "room_full"
    ROOM_STARTED = "room_started"
    CAPACITY = "capacity"
    NOT_HOST = "not_host"
    NOT_READY = "not_ready"
    REQUEST_ID_CONFLICT = "request_id_conflict"
    SESSION_EXPIRED = "session_expired"
    INVALID_STAGE = "invalid_stage"
    INVALID_ACTION = "invalid_action"
    STALE_ROUND = "stale_round"
    NOT_ROLE_OWNER = "not_role_owner"
    INSUFFICIENT_POWER = "insufficient_power"
    COOLDOWN = "cooldown"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_MESSAGE: "The message does not match protocol v1.",
    ErrorCode.UNSUPPORTED_VERSION: "Protocol version 1 is required.",
    ErrorCode.UNKNOWN_TYPE: "The message type is not recognized.",
    ErrorCode.FEATURE_UNAVAILABLE: "This feature is not implemented yet.",
    ErrorCode.NOT_AUTHENTICATED: "Room membership is required.",
    ErrorCode.ROOM_NOT_FOUND: "The room was not found.",
    ErrorCode.ROOM_FULL: "The room has no available player seats.",
    ErrorCode.ROOM_STARTED: "The room has already started.",
    ErrorCode.CAPACITY: "The server cannot create another room right now.",
    ErrorCode.NOT_HOST: "Only the room host can perform this operation.",
    ErrorCode.NOT_READY: "Two or three connected, ready players are required.",
    ErrorCode.REQUEST_ID_CONFLICT: "The request ID was already used for another command.",
    ErrorCode.SESSION_EXPIRED: "The session is invalid or has expired.",
    ErrorCode.INVALID_STAGE: "The action is unavailable at this stage.",
    ErrorCode.INVALID_ACTION: "The action is invalid.",
    ErrorCode.STALE_ROUND: "The action belongs to a different round.",
    ErrorCode.NOT_ROLE_OWNER: "The station is not owned by this player.",
    ErrorCode.INSUFFICIENT_POWER: "There is insufficient available power.",
    ErrorCode.COOLDOWN: "The action is cooling down.",
    ErrorCode.RATE_LIMITED: "Too many messages; wait before retrying.",
    ErrorCode.INTERNAL_ERROR: "The server could not process the message.",
}


class PingPayload(DTO):
    nonce: Annotated[StrictStr, Field(min_length=1, max_length=64)]

    @field_validator("nonce")
    @classmethod
    def valid_unicode(cls, value: str) -> str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("nonce must contain Unicode scalar values") from error
        return value


class CreateRoomPayload(DTO):
    name: Name


class JoinRoomPayload(DTO):
    room_code: RoomCode
    name: Name


class ResumeSessionPayload(DTO):
    resume_token: ResumeToken = Field(repr=False)


class EmptyPayload(DTO):
    """Strict empty payload for commands with no client-owned parameters."""


class PlayerReadyPayload(DTO):
    ready: StrictBool


class SessionAcceptedPayload(DTO):
    room_code: RoomCode
    kind: Literal["player"] = "player"
    player_id: StrictStr
    resume_token: ResumeToken = Field(repr=False)


class AckPayload(DTO):
    operation: AckOperation


class LobbyPlayer(DTO):
    player_id: StrictStr
    name: Name
    connected: StrictBool
    ready: StrictBool


class LobbyStatePayload(DTO):
    room_code: RoomCode
    stage: LobbyStage
    host_player_id: StrictStr | None
    players: tuple[LobbyPlayer, ...]
    can_start: StrictBool


class ErrorPayload(DTO):
    code: ErrorCode
    message: StrictStr
    retryable: bool


def error_payload(code: ErrorCode) -> ErrorPayload:
    return ErrorPayload(
        code=code,
        message=ERROR_MESSAGES[code],
        retryable=code
        in {
            ErrorCode.RATE_LIMITED,
            ErrorCode.INTERNAL_ERROR,
        },
    )


class PlayerSummary(DTO):
    player_id: StrictStr
    name: StrictStr


class ResultView(DTO):
    outcome: Literal["victory", "defeat", "aborted"]
    reason: Literal[
        "survived",
        "hull_destroyed",
        "disconnect_timeout",
        "player_left",
        "briefing_timeout",
        "server_overload",
    ]
    survived_ms: NonnegativeInt
    final_hull_percent: Percent
    resolved_count: NonnegativeInt
    failed_count: NonnegativeInt
    players: tuple[PlayerSummary, ...]


class PublicWarning(DTO):
    emergency_id: Annotated[StrictInt, Field(ge=1)]
    kind: Literal["asteroid", "overheating", "shield_overload"]
    label: StrictStr


class PublicRoundView(DTO):
    round_id: StrictStr
    stage: Stage
    tick_index: NonnegativeInt
    remaining_ms: NonnegativeInt
    countdown_remaining_ms: NonnegativeInt | None
    paused_from: Stage | None
    hull_percent: Percent
    shield_percent: Percent
    warnings: tuple[PublicWarning, ...]
    result: ResultView | None


class PublicStatePayload(DTO):
    public: PublicRoundView


class SetEnginePowerInput(DTO):
    type: Literal["set_engine_power"]
    value: Percent


class MoveLaneInput(DTO):
    type: Literal["move_lane"]
    direction: Literal["left", "right"]


class CoolantInput(DTO):
    type: Literal["coolant"]


class EvadeInput(DTO):
    type: Literal["evade"]


class EngineBoostInput(DTO):
    type: Literal["engine_boost"]


class EmergencyShutdownInput(DTO):
    type: Literal["emergency_shutdown"]


class SetShieldInput(DTO):
    type: Literal["set_shield"]
    active: StrictBool
    facing: Literal["front", "left", "right", "rear"]


class RechargeShieldInput(DTO):
    type: Literal["recharge_shield"]


class ShieldBoostInput(DTO):
    type: Literal["shield_boost"]


ActionInput = Annotated[
    SetEnginePowerInput
    | MoveLaneInput
    | CoolantInput
    | EvadeInput
    | EngineBoostInput
    | EmergencyShutdownInput
    | SetShieldInput
    | RechargeShieldInput
    | ShieldBoostInput,
    Field(discriminator="type"),
]
