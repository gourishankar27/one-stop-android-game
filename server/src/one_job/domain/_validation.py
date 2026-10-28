"""Small constructor checks shared by the pure domain value objects."""

from collections.abc import Mapping, Sequence
from enum import Enum
from uuid import UUID


def integer(value: object, name: str, minimum: int = 0, maximum: int | None = None) -> None:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer, not a boolean or coerced value")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside its allowed range")


def boolean(value: object, name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")


def enumeration(value: object, enum_type: type[Enum], name: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{name} must be a {enum_type.__name__}")


def identifier(value: object, name: str) -> None:
    if not isinstance(value, UUID):
        raise ValueError(f"{name} must be a UUID value")


def frozen_sequence[T](value: Sequence[T], item_type: type[T], name: str) -> tuple[T, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    items = tuple(value)
    if any(not isinstance(item, item_type) for item in items):
        raise ValueError(f"{name} contains an invalid item")
    return items


def mapping(value: object, name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
