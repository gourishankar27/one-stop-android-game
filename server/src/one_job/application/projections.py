"""Allowlist only the requesting participant's stations; host gets no bypass."""

from one_job.domain.models import GameState
from one_job.domain.roles import STATIONS
from one_job.domain.types import PlayerId, Role
from one_job.protocol.mapping import public_view
from one_job.protocol.role_messages import (
    BriefingStatus,
    EngineerView,
    PilotView,
    RoleAssignedPayload,
    RoleInstruction,
    RoleName,
    RoleStatePayload,
    ShieldsView,
    StationView,
)


def assigned_view(state: GameState, player_id: PlayerId) -> RoleAssignedPayload:
    roles = state.assignments.roles_for(player_id)
    return RoleAssignedPayload(
        round_id=str(state.round.round_id),
        roles=tuple(role.value for role in roles),
        instructions=tuple(
            RoleInstruction(
                role=role.value,
                title=STATIONS[role].title,
                steps=STATIONS[role].steps,
            )
            for role in roles
        ),
    )


def player_view(
    state: GameState, player_id: PlayerId, briefing: BriefingStatus
) -> RoleStatePayload:
    ship = state.ship
    stations: dict[RoleName, StationView] = {}
    for role in state.assignments.roles_for(player_id):
        if role == Role.PILOT:
            stations["pilot"] = PilotView.model_validate(
                {
                    "lane": ship.lane.value,
                    "maneuver_ready": False,
                    "evade_remaining_ticks": ship.evade_remaining_ticks,
                    "cooldowns": {
                        "move_lane": ship.cooldowns.move_lane,
                        "evade": ship.cooldowns.evade,
                    },
                    "hazards": (),
                }
            )
        elif role == Role.ENGINEER:
            stations["engineer"] = EngineerView.model_validate(
                {
                    "output": ship.engine_output,
                    "temperature": ship.temperature,
                    "available_power": ship.available_power(state.config),
                    "cooldowns": {
                        "engine_boost": ship.cooldowns.engine_boost,
                        "coolant": ship.cooldowns.coolant,
                    },
                    "boost_remaining_ticks": ship.engine_boost_remaining_ticks,
                    "instructions": (),
                }
            )
        else:
            stations["shields"] = ShieldsView.model_validate(
                {
                    "energy": ship.shield_energy,
                    "active": ship.shield_active,
                    "facing": ship.shield_facing.value,
                    "cooldowns": {
                        "recharge_shield": ship.cooldowns.recharge_shield,
                        "shield_boost": ship.cooldowns.shield_boost,
                    },
                    "recharge_remaining_ticks": ship.recharge_remaining_ticks,
                    "boost_remaining_ticks": ship.shield_boost_remaining_ticks,
                    "instructions": (),
                }
            )
    return RoleStatePayload(public=public_view(state), stations=stations, briefing=briefing)
