"""Continuous integer ship rules: one fixed step, without clocks or orchestration."""

from dataclasses import replace

from one_job.domain.config import RESOURCE_MAX, GameConfig
from one_job.domain.models import ShipState


def advance_ship(ship: ShipState, config: GameConfig, *, age_timers: bool = True) -> ShipState:
    """Apply active effects, clamp resources, release empty shields, then age timers."""
    heat_delta = (
        config.heat_gain_per_tick
        if ship.engine_output >= config.high_output_threshold
        else -config.cooling_per_tick
    )
    if ship.engine_boost_remaining_ticks:
        heat_delta += config.engine_boost_heat_per_tick
    temperature = min(RESOURCE_MAX, max(0, ship.temperature + heat_delta))
    damage = config.critical_heat_hull_damage if temperature >= config.critical_temperature else 0
    energy_delta = -config.shield_drain_per_tick if ship.shield_active else 0
    if ship.recharge_remaining_ticks:
        energy_delta += config.recharge_energy_per_tick
    if ship.shield_boost_remaining_ticks:
        energy_delta += config.shield_boost_energy_per_tick
    energy = min(RESOURCE_MAX, max(0, ship.shield_energy + energy_delta))
    updated = replace(
        ship,
        temperature=temperature,
        hull=max(0, ship.hull - damage),
        shield_energy=energy,
        shield_active=ship.shield_active and energy > 0,
    )
    return age_ship(updated) if age_timers else updated


def age_ship(ship: ShipState) -> ShipState:
    """Age durations after their last step's resources and emergency protection."""
    return replace(
        ship,
        evade_remaining_ticks=max(0, ship.evade_remaining_ticks - 1),
        engine_boost_remaining_ticks=max(0, ship.engine_boost_remaining_ticks - 1),
        recharge_remaining_ticks=max(0, ship.recharge_remaining_ticks - 1),
        shield_boost_remaining_ticks=max(0, ship.shield_boost_remaining_ticks - 1),
        cooldowns=replace(
            ship.cooldowns,
            move_lane=max(0, ship.cooldowns.move_lane - 1),
            coolant=max(0, ship.cooldowns.coolant - 1),
            evade=max(0, ship.cooldowns.evade - 1),
            engine_boost=max(0, ship.cooldowns.engine_boost - 1),
            recharge_shield=max(0, ship.cooldowns.recharge_shield - 1),
            shield_boost=max(0, ship.cooldowns.shield_boost - 1),
        ),
    )
