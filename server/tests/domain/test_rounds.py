from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from one_job.domain import GameState, Player
from one_job.domain.models import GameResult, RoundState
from one_job.domain.types import Outcome, ResultReason, RoundId, RoundStage


@pytest.mark.parametrize("duration", [60_000, 120_000])
def test_round_time_is_derived_from_integer_ticks(duration: int) -> None:
    state = RoundState(RoundId(UUID(int=1)), RoundStage.RUNNING, duration, 10)
    assert state.elapsed_ms == 1000 and state.remaining_ms == duration - 1000


@pytest.mark.parametrize(
    ("stage", "paused_from", "countdown"),
    [
        (RoundStage.BRIEFING, None, None),
        (RoundStage.COUNTDOWN, None, 3000),
        (RoundStage.COUNTDOWN, None, 0),
        (RoundStage.PAUSED, RoundStage.BRIEFING, None),
        (RoundStage.PAUSED, RoundStage.COUNTDOWN, 1700),
        (RoundStage.PAUSED, RoundStage.RUNNING, None),
    ],
)
def test_prestart_and_paused_states_are_explicit(
    stage: RoundStage,
    paused_from: RoundStage | None,
    countdown: int | None,
) -> None:
    state = RoundState(
        RoundId(UUID(int=1)), stage, paused_from=paused_from, countdown_remaining_ms=countdown
    )
    assert state.elapsed_ms == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"duration_ms": 59_900},
        {"duration_ms": 120_100},
        {"duration_ms": 90_001},
        {"duration_ms": True},
        {"tick_index": -1},
        {"tick_index": 901},
        {"tick_index": True},
        {"tick_index": 1.0},
        {"stage": "running"},
        {"stage": RoundStage.BRIEFING, "tick_index": 1},
        {"stage": RoundStage.COUNTDOWN},
        {"stage": RoundStage.COUNTDOWN, "countdown_remaining_ms": 3001},
        {"stage": RoundStage.COUNTDOWN, "countdown_remaining_ms": True},
        {"stage": RoundStage.RUNNING, "countdown_remaining_ms": 1},
        {"stage": RoundStage.RUNNING, "tick_index": 900},
        {"stage": RoundStage.RUNNING, "paused_from": RoundStage.RUNNING},
        {"stage": RoundStage.PAUSED},
        {"stage": RoundStage.PAUSED, "paused_from": RoundStage.FINISHED},
        {"stage": RoundStage.PAUSED, "paused_from": "running"},
        {"stage": RoundStage.PAUSED, "paused_from": RoundStage.BRIEFING, "tick_index": 1},
        {"stage": RoundStage.FINISHED},
        {"stage": RoundStage.ABORTED},
    ],
)
def test_round_rejects_inconsistent_time_pause_and_terminal_shapes(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        RoundState(RoundId(UUID(int=1)), **changes)


@pytest.mark.parametrize(
    ("outcome", "reason", "ticks", "hull", "stage"),
    [
        (Outcome.VICTORY, ResultReason.SURVIVED, 900, 1, RoundStage.FINISHED),
        (Outcome.DEFEAT, ResultReason.HULL_DESTROYED, 900, 0, RoundStage.FINISHED),
        (Outcome.DEFEAT, ResultReason.HULL_DESTROYED, 1, 0, RoundStage.FINISHED),
        (Outcome.ABORTED, ResultReason.DISCONNECT_TIMEOUT, 100, 1000, RoundStage.ABORTED),
        (Outcome.ABORTED, ResultReason.PLAYER_LEFT, 0, 1000, RoundStage.ABORTED),
        (Outcome.ABORTED, ResultReason.BRIEFING_TIMEOUT, 0, 1000, RoundStage.ABORTED),
        (Outcome.ABORTED, ResultReason.SERVER_OVERLOAD, 30, 1000, RoundStage.ABORTED),
    ],
)
def test_valid_terminal_snapshots_and_hull_loss_at_expiration(
    game_state: GameState,
    outcome: Outcome,
    reason: ResultReason,
    ticks: int,
    hull: int,
    stage: RoundStage,
) -> None:
    result = GameResult(outcome, reason, ticks * 100, hull, game_state.players)
    state = replace(
        game_state,
        ship=replace(game_state.ship, hull=hull),
        round=replace(game_state.round, stage=stage, tick_index=ticks, result=result),
    )
    assert state.round.result == result
    assert result.final_hull_percent == hull // 10


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": "victory"},
        {"reason": "survived"},
        {"survived_ms": True},
        {"survived_ms": 60_001},
        {"survived_ms": 59_900},
        {"survived_ms": 120_100},
        {"final_hull": True},
        {"final_hull": -1},
        {"final_hull": 1001},
        {"resolved_count": -1},
        {"failed_count": True},
        {"outcome": Outcome.VICTORY, "final_hull": 0},
        {"outcome": Outcome.VICTORY, "reason": ResultReason.PLAYER_LEFT},
        {"outcome": Outcome.DEFEAT, "reason": ResultReason.HULL_DESTROYED, "final_hull": 1},
        {"outcome": Outcome.DEFEAT, "final_hull": 0},
        {"outcome": Outcome.ABORTED},
        {"outcome": Outcome.ABORTED, "reason": ResultReason.PLAYER_LEFT, "final_hull": 0},
        {"outcome": Outcome.ABORTED, "reason": ResultReason.BRIEFING_TIMEOUT},
        {"players": ()},
    ],
)
def test_results_reject_inconsistent_outcomes_and_summaries(
    players: tuple[Player, ...],
    changes: dict[str, object],
) -> None:
    valid = GameResult(Outcome.VICTORY, ResultReason.SURVIVED, 90_000, 1000, players)
    with pytest.raises(ValueError):
        replace(valid, **changes)


def test_terminal_round_requires_matching_outcome_and_time(game_state: GameState) -> None:
    result = GameResult(Outcome.VICTORY, ResultReason.SURVIVED, 60_000, 1000, game_state.players)
    for changes in (
        {"stage": RoundStage.RUNNING, "tick_index": 600},
        {"stage": RoundStage.FINISHED, "tick_index": 599},
        {"stage": RoundStage.FINISHED, "tick_index": 600},
        {"stage": RoundStage.ABORTED, "tick_index": 600},
    ):
        with pytest.raises(ValueError):
            replace(game_state.round, result=result, **changes)


def test_result_roster_is_frozen_and_copied(players: tuple[Player, ...]) -> None:
    incoming = list(players)
    result = GameResult(Outcome.VICTORY, ResultReason.SURVIVED, 90_000, 1000, incoming)
    incoming.clear()
    assert result.players == players
    with pytest.raises(FrozenInstanceError):
        result.final_hull = 0


def test_abort_cannot_replace_an_expired_timer(game_state: GameState) -> None:
    result = GameResult(Outcome.ABORTED, ResultReason.PLAYER_LEFT, 90_000, 1000, game_state.players)
    with pytest.raises(ValueError):
        replace(game_state.round, stage=RoundStage.ABORTED, tick_index=900, result=result)


@pytest.mark.parametrize("reason", list(ResultReason))
@pytest.mark.parametrize("outcome", list(Outcome))
def test_result_reasons_are_restricted_to_their_outcome(
    players: tuple[Player, ...],
    reason: ResultReason,
    outcome: Outcome,
) -> None:
    permitted = {
        Outcome.VICTORY: {ResultReason.SURVIVED},
        Outcome.DEFEAT: {ResultReason.HULL_DESTROYED},
        Outcome.ABORTED: {
            ResultReason.PLAYER_LEFT,
            ResultReason.DISCONNECT_TIMEOUT,
            ResultReason.BRIEFING_TIMEOUT,
            ResultReason.SERVER_OVERLOAD,
        },
    }
    survived_ms = 90_000 if outcome == Outcome.VICTORY else 0
    hull = 0 if outcome == Outcome.DEFEAT else 1000
    if reason in permitted[outcome]:
        assert GameResult(outcome, reason, survived_ms, hull, players).reason == reason
    else:
        with pytest.raises(ValueError):
            GameResult(outcome, reason, survived_ms, hull, players)
