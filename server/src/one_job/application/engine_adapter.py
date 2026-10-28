"""Explicit fixture adapter, ready for a future single room owner to call."""

from dataclasses import dataclass

from one_job.application.timing import TickSource
from one_job.domain.engine import GameEngine
from one_job.domain.types import PlayerId
from one_job.protocol.mapping import action_error, domain_action, public_view
from one_job.protocol.messages import ActionInput, ErrorPayload, PublicRoundView


@dataclass(frozen=True, slots=True)
class ActionFeedback:
    public: PublicRoundView
    error: ErrorPayload | None
    applied_tick: int | None


class EngineAdapter:
    """Creates no tasks and exposes no engine through the WebSocket endpoint."""

    def __init__(self, engine: GameEngine, ticker: TickSource) -> None:
        self._engine = engine
        self._ticker = ticker

    def view(self) -> PublicRoundView:
        return public_view(self._engine.snapshot())

    def start(self) -> PublicRoundView:
        return public_view(self._engine.start())

    def apply_action(self, actor_id: PlayerId, action: ActionInput) -> ActionFeedback:
        result = self._engine.apply_action(actor_id, domain_action(action))
        return ActionFeedback(
            self.view(),
            action_error(result.code),
            result.events[0].tick_index if result.accepted else None,
        )

    async def step(self) -> PublicRoundView:
        await self._ticker.wait_next()
        return public_view(self._engine.tick().state)
