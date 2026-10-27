# Phase 15 — Playtesting and Balancing

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Create a repeatable playtest process and tune the spaceship using observed group sessions.

## Why this phase exists

Deterministic correctness cannot establish whether friends understand, coordinate or enjoy the game.

## Dependencies

Phase 14 complete; optional 12/13 may be included if present.

## In scope

Validated balance presets, configurable duration/events/damage/heat/cooling/shield rates/cooldowns, test checklist, structured observation records and conservative evidence-based tuning.

## Explicitly out of scope

No imaginary player feedback, advanced analytics service, new scenario, new account system or tuning that bypasses authoritative rules.

## Architecture considerations

Keep a single immutable validated GameConfig per round, with config version in reproduction data. Presets stay server-side; clients cannot submit arbitrary balance values. Mechanical tests should assert invariants and exact selected fixtures, not lock every tunable constant forever.

## Files likely to be created or modified

server config/presets; domain validation and regression fixtures; docs/playtests/{CHECKLIST,TEMPLATE,OBSERVATIONS}.md; local replay harness if needed; docs/GAME_DESIGN.md.

## Data models / APIs involved

Named versioned presets cover 60/90/120-second rounds and provisional difficulty intervals. Observation fields include build/config version, seed, player count, familiarity, outcome, setup friction and actual communication examples.

## Implementation tasks

1. Extract all existing provisional constants into validated config fields without changing mechanics. Add coherent preset validation for thresholds, durations, intervals and action costs.
2. Create a checklist covering joining, first briefing, station comprehension, cross-station requests, recoveries, overload, results and rematch. Include two-station workload explicitly.
3. Create structured observation/reproduction templates with no fabricated entries. Keep credentials and real personal names out of committed traces.
4. Run at least one 2-player and one 3-player session with human participants, recording multiple rounds and which observations are firsthand. Ask whether they want another round; do not infer motivation.
5. Change only values supported by observations, one reasoned set at a time; preserve before/after config version and replay traces where useful. Recheck mechanical invariants after tuning.
6. Summarize unresolved experience issues and propose a follow-up scoped tuning session if needed. If humans are unavailable, finish templates/config work and leave the playtest gate pending.

## Testing requirements

Run config boundary/preset tests, deterministic replay and full-round integration for each shipped preset, plus relevant client builds/tests if UI changes. Validate results/loop timing remain correct at 60 and 120 seconds. Manual human sessions are a completion requirement, not replaceable by simulated clients.

## Manual verification

Use the checklist with actual friends in the same room for both player counts. Record setup time, confusion, coordination and outcome without inventing quotes. Compare observed two-station load to the stated assumption.

## Completion criteria

Config/presets are validated, real 2/3-player observations exist, changes cite actual evidence and regressions pass. The MVP is ready for a bounded external-testing preparation phase only once these gates are met.

## Documentation updates

Update GAME_DESIGN.md provisional assumptions with observed findings, playtest records, technical risks and master ledger. Keep raw identifying feedback private unless permission exists.

## Handoff notes for next phase

Phase 18 can prepare external testing now; Phase 16 LAN investigation and Phase 17 second scenario are optional and do not block it.

