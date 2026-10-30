"""Frozen concrete event traces, replayed in completed tick order."""

import json
from pathlib import Path

import pytest

from one_job.domain.config import GameConfig
from one_job.domain.emergencies import advance_emergencies
from one_job.domain.engine import ENGINE_VERSION
from one_job.domain.models import (
    AsteroidTarget,
    Emergency,
    OverheatingTarget,
    ShieldOverloadTarget,
    ShipState,
)
from one_job.domain.types import EmergencyId, Lane, ShieldFacing

DATA = json.loads((Path(__file__).parents[1] / "fixtures/engine/emergency-cases.json").read_text())


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda case: case["name"])
def test_frozen_event_replay(case):
    assert (
        DATA["engine_version"] == ENGINE_VERSION and DATA["config_version"] == GameConfig().version
    )

    def replay():
        values = dict(case["ship"])
        if "lane" in values:
            values["lane"] = Lane(values["lane"])
        if "shield_facing" in values:
            values["shield_facing"] = ShieldFacing(values["shield_facing"])
        ship = ShipState(**values)
        active = []
        for item in case["events"]:
            if item["kind"] == "asteroid":
                target = AsteroidTarget(Lane(item["lane"]), ShieldFacing(item["facing"]))
            elif item["kind"] == "overheating":
                target = OverheatingTarget()
            else:
                target = ShieldOverloadTarget(45, item["hold"])
            active.append(Emergency(EmergencyId(item["id"]), target, 0, case["ticks"]))
        states = []
        events = []
        for tick in range(1, case["ticks"] + 1):
            step = advance_emergencies(ship, tuple(active), tick, GameConfig())
            ship, active = step.ship, list(step.active)
            states.append((ship, tuple(active)))
            events.extend(step.events)
        assert (
            not active
            and advance_emergencies(ship, (), case["ticks"] + 1, GameConfig()).events == ()
        )
        return states, events, ship

    states, events, ship = replay()
    assert (states, events, ship) == replay()
    expected = case["expected"]
    assert [e.status for e in events] == expected["statuses"]
    assert (ship.hull, ship.shield_energy, ship.temperature) == (
        expected["hull"],
        expected["energy"],
        expected["temperature"],
    )
