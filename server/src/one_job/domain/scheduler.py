"""Concrete seeded spaceship scheduling, owned by one engine and no clock."""

from random import Random

from one_job.domain.config import GameConfig
from one_job.domain.emergencies import EmergencyChanged
from one_job.domain.models import (
    AsteroidTarget,
    Emergency,
    EmergencyTarget,
    OverheatingTarget,
    ShieldOverloadTarget,
    ShipState,
)
from one_job.domain.types import EmergencyId, EmergencyType, Lane, ShieldFacing


class EmergencyScheduler:
    def __init__(self, config: GameConfig, rng: Random) -> None:
        self._config = config
        self._rng = rng
        self._next_slot = config.first_emergency_tick
        self._next_id = 1

    def start_due(
        self, tick: int, ship: ShipState, active: tuple[Emergency, ...]
    ) -> tuple[tuple[Emergency, ...], tuple[EmergencyChanged, ...]]:
        config = self._config
        if not config.emergencies_enabled:
            return active, ()
        current = list(active)
        events: list[EmergencyChanged] = []

        def start(target: EmergencyTarget, duration: int) -> None:
            item = Emergency(EmergencyId(self._next_id), target, tick, tick + duration)
            self._next_id += 1
            current.append(item)
            events.append(EmergencyChanged(item.emergency_id, item.kind, "started", tick))

        if (
            ship.temperature >= config.overheat_trigger_temperature
            and len(current) < config.max_active_emergencies
            and not any(item.kind == EmergencyType.OVERHEATING for item in current)
        ):
            start(
                OverheatingTarget(
                    config.overheat_target_max_output, config.overheat_target_temperature
                ),
                config.overheat_deadline_ticks,
            )
        if tick >= self._next_slot:
            kinds = (
                tuple(
                    kind
                    for kind in (EmergencyType.ASTEROID, EmergencyType.SHIELD_OVERLOAD)
                    if not any(item.kind == kind for item in current)
                )
                if len(current) < config.max_active_emergencies
                else ()
            )
            if kinds:
                kind = self._rng.choice(kinds)
                if kind == EmergencyType.ASTEROID:
                    start(
                        AsteroidTarget(
                            self._rng.choice(tuple(Lane)), self._rng.choice(tuple(ShieldFacing))
                        ),
                        config.asteroid_deadline_ticks,
                    )
                else:
                    start(
                        ShieldOverloadTarget(
                            config.overload_target_max_output, config.overload_hold_ticks
                        ),
                        config.overload_deadline_ticks,
                    )
            period = (
                "early"
                if tick * 3 < config.duration_ticks
                else ("middle" if tick * 3 < config.duration_ticks * 2 else "late")
            )
            self._next_slot = tick + self._rng.randint(
                getattr(config, f"{period}_interval_min_ticks"),
                getattr(config, f"{period}_interval_max_ticks"),
            )
        return tuple(sorted(current, key=lambda item: item.emergency_id)), tuple(events)
