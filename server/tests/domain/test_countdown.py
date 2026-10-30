"""Pure countdown boundaries, invalid input and no gameplay/RNG during preparation."""

import pytest

from one_job.domain.actions import Coolant
from one_job.domain.engine import GameEngine
from one_job.domain.types import Role


def test_countdown_is_exact_and_never_consumes_gameplay_state(engine: GameEngine):
    before = engine.snapshot()
    random = engine._rng.getstate()
    countdown = engine.begin_countdown()
    assert countdown.round.countdown_remaining_ms == 3000 and countdown.tick_index == 0
    assert (
        engine.apply_action(before.assignments.owners[Role.ENGINEER], Coolant()).code
        == "invalid_stage"
    )
    assert engine.tick(50).state is countdown
    state = engine.advance_countdown(2999)
    assert state.round.stage == "countdown" and state.round.countdown_remaining_ms == 1
    paused = engine.pause()
    assert paused.round.paused_from == "countdown" and paused.round.countdown_remaining_ms == 1
    assert engine.tick(100).state is paused
    with pytest.raises(ValueError):
        engine.advance_countdown(1)
    engine.resume()
    running = engine.advance_countdown(1)
    assert running.round.stage == "running" and running.round.countdown_remaining_ms is None
    assert running.tick_index == 0 and running.ship == before.ship and running.emergencies == ()
    assert engine._rng.getstate() == random and engine.accepted_actions == ()
    with pytest.raises(ValueError):
        engine.begin_countdown()
    with pytest.raises(ValueError):
        engine.advance_countdown(1)
    assert engine.tick().state.tick_index == 1


@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "1", None])
def test_invalid_countdown_delta_is_atomic(engine: GameEngine, value):
    before = engine.begin_countdown()
    with pytest.raises(ValueError):
        engine.advance_countdown(value)
    assert engine.snapshot() is before
