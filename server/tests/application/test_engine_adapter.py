import asyncio
import json
from uuid import UUID

import pytest

from one_job.application.engine_adapter import EngineAdapter
from one_job.application.timing import FixedStepTicker
from one_job.domain.actions import Coolant, MoveLane, SetEnginePower
from one_job.domain.engine import ActionCode
from one_job.domain.types import MoveDirection, PlayerId, Role
from one_job.protocol.mapping import action_error, domain_action, public_view
from one_job.protocol.messages import CoolantInput, MoveLaneInput, SetEnginePowerInput
from tests.support import owned_tasks

PUBLIC_KEYS = {
    "round_id",
    "stage",
    "tick_index",
    "remaining_ms",
    "countdown_remaining_ms",
    "paused_from",
    "hull_percent",
    "shield_percent",
    "warnings",
    "result",
}


@pytest.mark.parametrize(
    "value,expected",
    [
        (SetEnginePowerInput(type="set_engine_power", value=40), SetEnginePower(40)),
        (MoveLaneInput(type="move_lane", direction="left"), MoveLane(MoveDirection.LEFT)),
        (CoolantInput(type="coolant"), Coolant()),
    ],
)
def test_typed_action_mapping(value, expected):
    assert domain_action(value) == expected


@pytest.mark.parametrize(
    "code,expected",
    [
        (ActionCode.ACCEPTED, None),
        (ActionCode.INVALID_STAGE, "invalid_stage"),
        (ActionCode.NOT_PARTICIPANT, "not_authenticated"),
        (ActionCode.INVALID_ACTION, "invalid_action"),
        (ActionCode.FEATURE_UNAVAILABLE, "feature_unavailable"),
        (ActionCode.NOT_ROLE_OWNER, "not_role_owner"),
        (ActionCode.INSUFFICIENT_POWER, "insufficient_power"),
        (ActionCode.COOLDOWN, "cooldown"),
        (ActionCode.LANE_BOUNDARY, "invalid_action"),
    ],
)
def test_all_domain_result_codes_have_safe_wire_mapping(code, expected):
    mapped = action_error(code)
    assert (mapped.code if mapped else None) == expected
    if mapped:
        assert set(mapped.model_dump()) == {"code", "message", "retryable"}


async def test_adapter_calls_fixture_and_fixed_step_source_without_orphan_task(engine, clock):
    before = owned_tasks()
    adapter = EngineAdapter(engine, FixedStepTicker(clock))
    assert owned_tasks() == before
    assert adapter.view().stage == "briefing"
    assert adapter.start().stage == "running"
    owner = engine.snapshot().assignments.owners[Role.ENGINEER]
    action = SetEnginePowerInput(type="set_engine_power", value=40)
    feedback = adapter.apply_action(owner, action)
    assert feedback.error is None
    assert feedback.applied_tick == 0
    assert engine.snapshot().ship.engine_output == 40
    step = asyncio.create_task(adapter.step())
    await clock.wait_registered(0.1)
    assert not step.done()
    assert engine.snapshot().tick_index == 0
    await clock.advance(0.1)
    projected = await step
    assert projected.tick_index == 1
    assert projected.remaining_ms == 89900
    assert owned_tasks() == before
    assert clock.waiters == []


def test_adapter_rejection_cannot_mutate_engine_or_return_internal_state(engine, clock):
    adapter = EngineAdapter(engine, FixedStepTicker(clock))
    action = SetEnginePowerInput(type="set_engine_power", value=40)
    assert adapter.apply_action(PlayerId(UUID(int=99)), action).error.code == "invalid_stage"
    adapter.start()
    before = engine.snapshot()
    outsider = adapter.apply_action(PlayerId(UUID(int=99)), action)
    assert outsider.error.code == "not_authenticated"
    assert outsider.applied_tick is None
    wrong_owner = adapter.apply_action(before.assignments.owners[Role.PILOT], action)
    assert wrong_owner.error.code == "not_role_owner"
    assert engine.snapshot() is before
    assert set(wrong_owner.public.model_dump()) == PUBLIC_KEYS


def test_projection_allowlists_fields_and_converts_fixed_units(engine):
    state = engine.snapshot()
    projected = public_view(state)
    assert set(projected.model_dump()) == PUBLIC_KEYS
    assert projected.hull_percent == 100
    assert projected.shield_percent == 60
    assert projected.warnings == ()
    assert projected.result is None
    wire = projected.model_dump_json()
    for forbidden in [
        "seed",
        "827364",
        "engine_output",
        "temperature",
        "lane",
        "assignments",
        "cooldowns",
        "available_power",
        "station",
        "resume_token",
        "config",
        "Crew",
    ]:
        assert forbidden not in wire


def test_terminal_projection_contains_only_public_result(engine):
    engine.start()
    owner = engine.snapshot().assignments.owners[Role.ENGINEER]
    engine.apply_action(owner, SetEnginePower(40))
    state = engine.tick(900).state
    result = json.loads(public_view(state).model_dump_json())["result"]
    assert set(result) == {
        "outcome",
        "reason",
        "survived_ms",
        "final_hull_percent",
        "resolved_count",
        "failed_count",
        "players",
    }
    assert result["outcome"] == "victory"
    assert result["survived_ms"] == 90000
    assert result["final_hull_percent"] == state.round.result.final_hull_percent
    assert all(set(player) == {"player_id", "name"} for player in result["players"])


async def test_cancel_awaited_adapter_step_does_not_tick_or_leak(engine, clock):
    adapter = EngineAdapter(engine, FixedStepTicker(clock))
    adapter.start()
    task = asyncio.create_task(adapter.step())
    await clock.wait_registered(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert engine.snapshot().tick_index == 0
    assert clock.waiters == []
    assert owned_tasks() == []
