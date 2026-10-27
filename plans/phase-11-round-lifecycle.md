# Phase 11 — Round Lifecycle

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Finish the full lobby-to-round-to-results-to-rematch session loop.

## Why this phase exists

The first complete gameplay loop needs clear transitions and terminal behavior across all phones.

## Dependencies

Phase 10 complete.

## In scope

Server briefing acknowledgement timeout, 3-second countdown, 60–120-second timer, difficulty thirds, victory/defeat/abort results, host rematch/return-to-lobby and cleanup.

## Explicitly out of scope

No observer display, audio polish, production deployment or complete Phase 14 resilience matrix. Basic safe pause/resume behavior must remain functional.

## Architecture considerations

The server stages transitions; Android navigates from authoritative stage and round ID. Reuse engine terminal rules, reset all round-specific state for rematches, preserve room identity and never reuse stale command queues.

## Files likely to be created or modified

application/round_service.py and room_runner.py; domain terminal/result code if needed; protocol lifecycle payloads; Android countdown/results/navigation; server integration tests and Android tests.

## Data models / APIs involved

Lobby/briefing/countdown/running/paused/finished/aborted transitions from GAME_STATE.md. game_over result has outcome/reason/survival/final-hull/event counts; play_again and return_to_lobby are host-only.

## Implementation tasks

1. Replace the Phase 09 direct-running transition with server-owned briefing completion and countdown. Freeze countdown/briefing correctly under disconnect grace.
2. Publish countdown and running time from server state. Keep the 60-second briefing limit separate from the 90-second default gameplay duration.
3. Finalize simultaneous loss/time-expiry precedence and emit one stable result; stop/cancel the runner after terminal state. Complete the emergency interval changes across thirds.
4. Build countdown/results screens and navigate from snapshots, including a terminal snapshot reached after reconnect. Do not rely on receiving a one-shot game_over event to show results.
5. Implement host play_again and return_to_lobby. Rematch creates fresh seed/round/assignments/cooldowns/events; return resets ready flags. Reject old-round actions and unauthorized requests.
6. Run repeated victory, defeat and aborted rounds against the same room; prove task/queue counts do not grow. Record multi-device end-to-end evidence.

## Testing requirements

Pure tests cover exact duration, hull/timer tie, brief/countdown pause and stable terminal state. Server tests cover host permissions, one result event, rematch/reset, stale messages and repeated cycles. Android tests cover authoritative navigation and results. Run seeded 2/3-player full-round integration checks.

## Manual verification

Create/join on real phones, ready, start, read briefings, count down, win or lose, view matching results and rematch twice. Return to lobby and confirm readiness resets. Interrupt one connection briefly and verify safe pause/recovery.

## Completion criteria

The complete playable loop exists with automated and real-device evidence. MVP gameplay is complete, but the full MVP gate remains Phase 14 resilience plus Phase 15 human playtesting.

## Documentation updates

Update lifecycle/navigation/protocol documents, TESTING.md with round-cycle evidence and plans.md. Clearly separate complete gameplay from optional presentation and pending resilience.

## Handoff notes for next phase

Next optional work is Phase 12 or 13; the MVP-critical path continues with Phase 14 then Phase 15. Do not assume the optional display blocks reconnection work.

