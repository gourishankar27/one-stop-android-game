"""Explicit transport/domain mappings; internal snapshots are never serialized."""

from one_job.domain.actions import (
    Coolant,
    EmergencyShutdown,
    EngineBoost,
    Evade,
    MoveLane,
    PlayerAction,
    RechargeShield,
    SetEnginePower,
    SetShield,
    ShieldBoost,
)
from one_job.domain.config import RESOURCE_MAX
from one_job.domain.engine import ActionCode
from one_job.domain.models import GameState
from one_job.domain.types import MoveDirection, ShieldFacing
from one_job.protocol.messages import (
    ActionInput,
    CoolantInput,
    EmergencyShutdownInput,
    EngineBoostInput,
    ErrorCode,
    ErrorPayload,
    EvadeInput,
    MoveLaneInput,
    PlayerSummary,
    PublicRoundView,
    RechargeShieldInput,
    ResultView,
    SetEnginePowerInput,
    SetShieldInput,
    ShieldBoostInput,
    error_payload,
)

ACTION_ERRORS: dict[ActionCode, ErrorCode] = {
    ActionCode.INVALID_STAGE: ErrorCode.INVALID_STAGE,
    ActionCode.NOT_PARTICIPANT: ErrorCode.NOT_AUTHENTICATED,
    ActionCode.INVALID_ACTION: ErrorCode.INVALID_ACTION,
    ActionCode.FEATURE_UNAVAILABLE: ErrorCode.FEATURE_UNAVAILABLE,
    ActionCode.NOT_ROLE_OWNER: ErrorCode.NOT_ROLE_OWNER,
    ActionCode.INSUFFICIENT_POWER: ErrorCode.INSUFFICIENT_POWER,
    ActionCode.COOLDOWN: ErrorCode.COOLDOWN,
    ActionCode.LANE_BOUNDARY: ErrorCode.INVALID_ACTION,
}


def domain_action(action: ActionInput) -> PlayerAction:
    if isinstance(action, SetEnginePowerInput):
        return SetEnginePower(action.value)
    if isinstance(action, MoveLaneInput):
        return MoveLane(MoveDirection(action.direction))
    if isinstance(action, CoolantInput):
        return Coolant()
    if isinstance(action, EvadeInput):
        return Evade()
    if isinstance(action, EngineBoostInput):
        return EngineBoost()
    if isinstance(action, EmergencyShutdownInput):
        return EmergencyShutdown()
    if isinstance(action, SetShieldInput):
        return SetShield(action.active, ShieldFacing(action.facing))
    if isinstance(action, RechargeShieldInput):
        return RechargeShield()
    if isinstance(action, ShieldBoostInput):
        return ShieldBoost()
    raise ValueError("unsupported typed action")


def action_error(code: ActionCode) -> ErrorPayload | None:
    return None if code == ActionCode.ACCEPTED else error_payload(ACTION_ERRORS[code])


def public_view(state: GameState) -> PublicRoundView:
    """Phase 02 baseline only: no emergencies or private role projections yet."""
    result = state.round.result
    result_view = None
    if result is not None:
        result_view = ResultView.model_validate(
            {
                "outcome": result.outcome.value,
                "reason": result.reason.value,
                "survived_ms": result.survived_ms,
                "final_hull_percent": result.final_hull_percent,
                "resolved_count": result.resolved_count,
                "failed_count": result.failed_count,
                "players": tuple(
                    PlayerSummary(player_id=str(player.player_id), name=player.name)
                    for player in result.players
                ),
            }
        )
    return PublicRoundView.model_validate(
        {
            "round_id": str(state.round.round_id),
            "stage": state.round.stage.value,
            "tick_index": state.tick_index,
            "remaining_ms": state.round.remaining_ms,
            "countdown_remaining_ms": state.round.countdown_remaining_ms,
            "paused_from": state.round.paused_from.value if state.round.paused_from else None,
            "hull_percent": state.ship.hull * 100 // RESOURCE_MAX,
            "shield_percent": state.ship.shield_energy * 100 // RESOURCE_MAX,
            "warnings": (),
            "result": result_view,
        }
    )
