# Phase 10 — Emergency System

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Add deterministic emergency scheduling and cooperative resolve/fail behavior to spaceship rounds.

## Why this phase exists

Players need shared trouble with different station instructions to make verbal coordination necessary.

## Dependencies

Phase 09 complete.

## In scope

Asteroid approach, engine overheating and shield overload; eligibility, deadlines, progress, public labels/private instructions, consequences and seeded schedule.

## Explicitly out of scope

No navigation malfunction, independent shortage emergency, new roles, generic event DSL, presentation polish or new scenario.

## Architecture considerations

Use GAME_DESIGN.md as the initial complete catalog. Core emergency state/rules remain pure Python. The application projects labels and per-station details only. Fixed emergency-ID order resolves simultaneous effects; never use wall time or global RNG.

## Files likely to be created or modified

domain/emergencies.py and scheduler.py; config.py; domain tests/replay traces; application/projections.py; protocol emergency DTOs; Android warning components and state tests.

## Data models / APIs involved

EmergencyType, EmergencyState and deadline/progress tick fields. emergency_event contains only shared kind/status; detailed targets appear solely in the appropriate StationView. GameResult counts resolutions/failures.

## Implementation tasks

1. Implement the three event state machines exactly with explicit start, active progress, resolution, failure and removal. Use stable deterministic IDs within the round.
2. Implement eligibility and max-two-active/max-one-per-kind constraints. Seeded slots start at tick 80; progression intervals follow round thirds. Heat threshold events do not consume random draws.
3. Implement asteroid deadline evaluation with maneuver before shield absorption, overheat success before same-tick timeout, and overload continuous-condition progress reset.
4. Emit public lifecycle events once and private instructions only through role projections. Do not leak hidden lane/facing requirements or next events into shared diagnostics.
5. Render urgent short station warnings and public labels; retain badges on inactive Engineer/Shields tabs. Actions still use the existing union, not a bypass resolve_emergency command.
6. Add replay fixtures for each success/failure and simultaneous-event case. Check that pause and terminal states stop event time.

## Testing requirements

Deterministic unit tests cover trigger eligibility, capped concurrency, thresholds, exact deadlines, reset progress, both asteroid paths, same-tick outcomes, stable event order and seeded schedule. Server tests inspect recipient privacy; Android tests inspect warning visibility. Run a complete fixed-seed integration round.

## Manual verification

Play with 2 and 3 phones through at least one resolution and one failure of each event using a documented local seed harness. Confirm people must exchange private information and that no display/other role receives those instructions.

## Completion criteria

Three tested emergency types produce deterministic pressure with correct effects/privacy; full rounds run without event leaks or duplicate terminal events. No fun/balance claim is made without observed playtests.

## Documentation updates

Update GAME_DESIGN.md with actual implementation names/config defaults and protocol fixtures for warning views. Record any rule change and keep it provisional; update progress.

## Handoff notes for next phase

Phase 11 wraps this gameplay into briefing/countdown/results/rematch. Do not add extra event types just because the framework supports them.

