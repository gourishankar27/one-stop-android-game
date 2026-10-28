"""Allowlisted v1 payloads; planned gameplay is not dispatched by the socket yet."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
)

RequestId = Annotated[str, StringConstraints(strict=True, pattern=r"\A[A-Za-z0-9_-]{1,64}\z")]
NonnegativeInt = Annotated[StrictInt, Field(ge=0)]
Percent = Annotated[StrictInt, Field(ge=0, le=100)]
Stage = Literal["briefing", "countdown", "running", "paused", "finished", "aborted"]


class DTO(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class ErrorCode(StrEnum):
    INVALID_MESSAGE = "invalid_message"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNKNOWN_TYPE = "unknown_type"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    NOT_AUTHENTICATED = "not_authenticated"
    INVALID_STAGE = "invalid_stage"
    INVALID_ACTION = "invalid_action"
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
    ErrorCode.INVALID_STAGE: "The action is unavailable at this stage.",
    ErrorCode.INVALID_ACTION: "The action is invalid.",
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


ActionInput = Annotated[
    SetEnginePowerInput | MoveLaneInput | CoolantInput, Field(discriminator="type")
]
