"""Phase 02 continuous ship rules: one fixed step, without actions or orchestration."""

from dataclasses import replace

from one_job.domain.config import RESOURCE_MAX, GameConfig
from one_job.domain.models import ShipState


def advance_ship(ship: ShipState, config: GameConfig) -> ShipState:
    """Apply heat, then critical damage, then age supported action cooldowns."""
    heat_delta = (
        config.heat_gain_per_tick
        if ship.engine_output >= config.high_output_threshold
        else -config.cooling_per_tick
    )
    temperature = min(RESOURCE_MAX, max(0, ship.temperature + heat_delta))
    damage = config.critical_heat_hull_damage if temperature >= config.critical_temperature else 0
    return replace(
        ship,
        temperature=temperature,
        hull=max(0, ship.hull - damage),
        cooldowns=replace(
            ship.cooldowns,
            move_lane=max(0, ship.cooldowns.move_lane - 1),
            coolant=max(0, ship.cooldowns.coolant - 1),
        ),
    )
