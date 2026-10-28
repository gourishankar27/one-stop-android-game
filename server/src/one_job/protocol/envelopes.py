"""Strict text-frame parsing and typed envelope serialization; no gameplay rules."""

import json
import math
from typing import Annotated, Literal, get_args

from pydantic import Field, JsonValue, RootModel, StrictInt, StrictStr, TypeAdapter, ValidationError

from one_job.protocol.messages import (
    DTO,
    ErrorCode,
    ErrorPayload,
    NonnegativeInt,
    PingPayload,
    PublicStatePayload,
    RequestId,
    error_payload,
)

MAX_FRAME_BYTES = 16 * 1024
ReservedType = Literal[
    "create_room",
    "join_room",
    "resume_session",
    "leave_room",
    "player_ready",
    "start_game",
    "briefing_ready",
    "player_action",
    "request_state",
    "play_again",
    "return_to_lobby",
    "join_display",
]
RESERVED_TYPES = frozenset(get_args(ReservedType))


class ClientHeader(DTO):
    version: StrictInt
    type: StrictStr
    request_id: RequestId
    payload: dict[str, JsonValue]


class PingEnvelope(DTO):
    version: Literal[1]
    type: Literal["ping"]
    request_id: RequestId
    payload: PingPayload


class ReservedEnvelope(DTO):
    version: Literal[1]
    type: ReservedType
    request_id: RequestId
    payload: dict[str, JsonValue]


type ClientMessage = Annotated[PingEnvelope | ReservedEnvelope, Field(discriminator="type")]


class ClientFrame(RootModel[ClientMessage]):
    """Discriminated message union at the root of one JSON frame."""


ID_ADAPTER: TypeAdapter[RequestId] = TypeAdapter(RequestId)


class PongEnvelope(DTO):
    version: Literal[1] = 1
    type: Literal["pong"] = "pong"
    reply_to: RequestId | None
    room_revision: NonnegativeInt | None
    payload: PingPayload


class ErrorEnvelope(DTO):
    version: Literal[1] = 1
    type: Literal["error"] = "error"
    reply_to: RequestId | None
    room_revision: NonnegativeInt | None
    payload: ErrorPayload


class PublicStateEnvelope(DTO):
    """Reserved DTO used by adapter/outbox tests, never emitted by Phase 03 /ws."""

    version: Literal[1] = 1
    type: Literal["public_state"] = "public_state"
    reply_to: RequestId | None
    room_revision: NonnegativeInt
    payload: PublicStatePayload


ServerMessage = Annotated[
    PongEnvelope | ErrorEnvelope | PublicStateEnvelope, Field(discriminator="type")
]


class FrameError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        reply_to: str | None = None,
        close_code: int | None = None,
        operation: str | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.reply_to = reply_to
        self.close_code = close_code
        self.operation = operation


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def _safe_request_id(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    try:
        return ID_ADAPTER.validate_python(raw.get("request_id"))
    except ValidationError:
        return None


def parse_text(text: str) -> PingEnvelope | ReservedEnvelope:
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        raise FrameError(ErrorCode.INVALID_MESSAGE, close_code=1007) from None
    if size > MAX_FRAME_BYTES:
        raise FrameError(ErrorCode.INVALID_MESSAGE, close_code=1009)
    try:
        raw: object = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except (ValueError, RecursionError):
        raise FrameError(ErrorCode.INVALID_MESSAGE, close_code=1007) from None
    request_id = _safe_request_id(raw)
    try:
        header = ClientHeader.model_validate(raw)
    except ValidationError:
        raise FrameError(ErrorCode.INVALID_MESSAGE, request_id) from None
    operation = header.type if header.type == "ping" or header.type in RESERVED_TYPES else None
    if header.version != 1:
        raise FrameError(ErrorCode.UNSUPPORTED_VERSION, request_id, 1002, operation)
    if operation is None:
        raise FrameError(ErrorCode.UNKNOWN_TYPE, request_id)
    try:
        return ClientFrame.model_validate(header.model_dump()).root
    except ValidationError:
        raise FrameError(ErrorCode.INVALID_MESSAGE, request_id, operation=operation) from None


def pong(request: PingEnvelope) -> PongEnvelope:
    return PongEnvelope(reply_to=request.request_id, room_revision=None, payload=request.payload)


def error_message(
    code: ErrorCode, reply_to: str | None = None, room_revision: int | None = None
) -> ErrorEnvelope:
    return ErrorEnvelope(
        reply_to=reply_to, room_revision=room_revision, payload=error_payload(code)
    )


def encode_message(message: ServerMessage) -> str:
    return message.model_dump_json()
