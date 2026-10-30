"""The three spaceship event rules, using completed ticks and immutable values."""

from dataclasses import dataclass, replace
from typing import Literal

from one_job.domain.config import GameConfig
from one_job.domain.models import (
    AsteroidTarget,
    Emergency,
    OverheatingTarget,
    ShipState,
)
from one_job.domain.types import EmergencyId, EmergencyState, EmergencyType


@dataclass(frozen=True, slots=True)
class EmergencyChanged:
    """Public lifecycle trace. Deliberately contains no private target or seed."""

    emergency_id: EmergencyId
    kind: EmergencyType
    status: Literal["started", "resolved", "failed"]
    tick_index: int


@dataclass(frozen=True, slots=True)
class EmergencyStep:
    ship: ShipState
    active: tuple[Emergency, ...]
    events: tuple[EmergencyChanged, ...]


def advance_emergencies(
    ship: ShipState, active: tuple[Emergency, ...], tick: int, config: GameConfig
) -> EmergencyStep:
    """Evaluate existing events in ID order after resources, before timer ageing."""
    remaining: list[Emergency] = []
    changes: list[EmergencyChanged] = []
    for emergency in sorted(active, key=lambda item: item.emergency_id):
        target = emergency.target
        resolved = False
        if isinstance(target, AsteroidTarget):
            if tick < emergency.deadline_tick:
                remaining.append(emergency)
                continue
            resolved = bool(ship.evade_remaining_ticks) or (
                ship.lane != target.impact_lane and ship.engine_output >= config.evade_min_output
            )
            if not resolved and (
                ship.shield_active
                and ship.shield_facing == target.required_facing
                and ship.shield_energy >= config.asteroid_shield_cost
            ):
                energy = ship.shield_energy - config.asteroid_shield_cost
                ship = replace(ship, shield_energy=energy, shield_active=energy > 0)
                resolved = True
            damage = config.asteroid_hull_damage
        elif isinstance(target, OverheatingTarget):
            resolved = (
                ship.temperature <= target.max_temperature
                and ship.engine_output <= target.max_output
            )
            damage = config.overheat_hull_damage
        else:
            progress = (
                emergency.progress_ticks + 1
                if not ship.shield_active and ship.engine_output <= target.max_output
                else 0
            )
            emergency = replace(emergency, progress_ticks=progress)
            resolved = progress >= target.hold_ticks
            damage = config.overload_hull_damage
        if not resolved and tick < emergency.deadline_tick:
            remaining.append(emergency)
            continue
        status: Literal["resolved", "failed"] = "resolved" if resolved else "failed"
        # Construct the explicit terminal value before removing it from active state.
        completed = replace(
            emergency,
            state=EmergencyState.RESOLVED if resolved else EmergencyState.FAILED,
            finished_tick=tick,
        )
        if not resolved:
            ship = replace(ship, hull=max(0, ship.hull - damage))
            if completed.kind == EmergencyType.OVERHEATING:
                ship = replace(ship, temperature=config.overheat_failure_temperature)
            elif completed.kind == EmergencyType.SHIELD_OVERLOAD:
                ship = replace(ship, shield_energy=0, shield_active=False)
        changes.append(EmergencyChanged(completed.emergency_id, completed.kind, status, tick))
    return EmergencyStep(ship, tuple(remaining), tuple(changes))
