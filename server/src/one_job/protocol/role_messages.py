"""Strict owned-station briefing DTOs; no internal state or ownership map."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StrictBool, StrictInt, StrictStr, model_validator

from one_job.protocol.messages import DTO, ActionInput, NonnegativeInt, Percent, PublicRoundView

RoleName = Literal["pilot", "engineer", "shields"]


def canonical_uuid(value: str) -> str:
    from uuid import UUID

    if str(UUID(value)) != value.lower():
        raise ValueError("a canonical UUID is required")
    return value


RoundIdentifier = Annotated[StrictStr, AfterValidator(canonical_uuid)]


class BriefingReadyPayload(DTO):
    round_id: RoundIdentifier


class PlayerActionPayload(DTO):
    round_id: RoundIdentifier
    client_action_seq: Annotated[StrictInt, Field(ge=1)]
    action: ActionInput


class RoleInstruction(DTO):
    role: RoleName
    title: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    steps: tuple[Annotated[StrictStr, Field(min_length=1, max_length=256)], ...]


class RoleAssignedPayload(DTO):
    round_id: RoundIdentifier
    roles: tuple[RoleName, ...]
    instructions: tuple[RoleInstruction, ...] = Field(repr=False)

    @model_validator(mode="after")
    def owned_metadata(self) -> RoleAssignedPayload:
        allowed = ({"pilot"}, {"engineer"}, {"shields"}, {"engineer", "shields"})
        if set(self.roles) not in allowed or len(set(self.roles)) != len(self.roles):
            raise ValueError("invalid owned stations")
        if tuple(instruction.role for instruction in self.instructions) != self.roles:
            raise ValueError("metadata must match owned stations")
        if any(
            not instruction.title.strip()
            or not 1 <= len(instruction.steps) <= 4
            or any(not step.strip() for step in instruction.steps)
            for instruction in self.instructions
        ):
            raise ValueError("short station instructions are required")
        return self


class PilotCooldowns(DTO):
    move_lane: NonnegativeInt
    evade: NonnegativeInt


class EngineerCooldowns(DTO):
    engine_boost: NonnegativeInt
    coolant: NonnegativeInt


class ShieldsCooldowns(DTO):
    recharge_shield: NonnegativeInt
    shield_boost: NonnegativeInt


class PilotHazard(DTO):
    emergency_id: Annotated[StrictInt, Field(ge=1)]
    impact_lane: Literal["left", "center", "right"]
    deadline_remaining_ms: NonnegativeInt


class EngineerInstruction(DTO):
    emergency_id: Annotated[StrictInt, Field(ge=1)]
    target_max_output: Percent | None
    target_max_temperature: Annotated[StrictInt, Field(ge=0, le=1000)] | None
    deadline_remaining_ms: NonnegativeInt


class ShieldsInstruction(DTO):
    emergency_id: Annotated[StrictInt, Field(ge=1)]
    required_facing: Literal["front", "left", "right", "rear"] | None
    deactivate: StrictBool
    deadline_remaining_ms: NonnegativeInt


class PilotView(DTO):
    lane: Literal["left", "center", "right"]
    maneuver_ready: StrictBool
    evade_remaining_ticks: NonnegativeInt
    cooldowns: PilotCooldowns
    hazards: tuple[PilotHazard, ...]


class EngineerView(DTO):
    output: Percent
    temperature: Annotated[StrictInt, Field(ge=0, le=1000)]
    available_power: StrictInt
    cooldowns: EngineerCooldowns
    boost_remaining_ticks: NonnegativeInt
    instructions: tuple[EngineerInstruction, ...]


class ShieldsView(DTO):
    energy: Annotated[StrictInt, Field(ge=0, le=1000)]
    active: StrictBool
    facing: Literal["front", "left", "right", "rear"]
    cooldowns: ShieldsCooldowns
    recharge_remaining_ticks: NonnegativeInt
    boost_remaining_ticks: NonnegativeInt
    instructions: tuple[ShieldsInstruction, ...]


type StationView = PilotView | EngineerView | ShieldsView


class BriefingStatus(DTO):
    acknowledged: StrictBool
    waiting_player_ids: tuple[RoundIdentifier, ...]
    remaining_ms: NonnegativeInt
    complete: StrictBool
    held_for_gameplay: StrictBool

    @model_validator(mode="after")
    def consistent_status(self) -> BriefingStatus:
        if len(self.waiting_player_ids) > 3 or len(set(self.waiting_player_ids)) != len(
            self.waiting_player_ids
        ):
            raise ValueError("invalid waiting participants")
        if self.complete != (not self.waiting_player_ids) or (
            self.held_for_gameplay and not self.complete
        ):
            raise ValueError("inconsistent briefing completion")
        return self


class RoleStatePayload(DTO):
    public: PublicRoundView
    stations: dict[RoleName, StationView] = Field(repr=False)
    briefing: BriefingStatus

    @model_validator(mode="after")
    def matched_stations(self) -> RoleStatePayload:
        expected = {"pilot": PilotView, "engineer": EngineerView, "shields": ShieldsView}
        if set(self.stations) not in (
            {"pilot"},
            {"engineer"},
            {"shields"},
            {"engineer", "shields"},
        ):
            raise ValueError("invalid owned stations")
        if not self.stations or any(
            not isinstance(view, expected[role]) for role, view in self.stations.items()
        ):
            raise ValueError("station key and view must match")
        return self
