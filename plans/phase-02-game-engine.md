# Phase 02 — Core Game Engine

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Build a synchronous deterministic engine that can run a basic timed spaceship simulation directly in Python tests.

## Why this phase exists

Authoritative rules must be proven independently before connection management can complicate failures.

## Dependencies

Phase 01 complete.

## In scope

Engine construction, start, snapshot, fixed ticks, minimal station actions, resource updates, cooldown support, atomic validation, hull/timer terminal checks and seeded RNG injection.

## Explicitly out of scope

No FastAPI, sockets, room lifecycle, Android, random emergency scheduling or complete cooperative presentation. Phase 09 extends the initial controls; Phase 10 implements emergencies.

## Architecture considerations

Use GameEngine(config, seed, players, assignments), start(), apply_action(actor_id, action) and tick(steps=1), or equivalent documented typed API. Each step is 100ms. Test fixtures supply assignments until Phase 08. start() begins running in isolated engine tests; application briefing/countdown will surround it later.

## Files likely to be created or modified

server/src/one_job/domain/engine.py and supporting rules.py; server/tests/domain/test_engine.py and replay fixtures; docs/ARCHITECTURE.md; docs/GAME_DESIGN.md.

## Data models / APIs involved

ActionResult is an accepted/rejected typed result, with a stable reason code and events. GameState has tick_index and elapsed_ms. RNG is private random.Random(seed); infrastructure identifiers are injected for replay tests.

## Implementation tasks

1. Create the engine from immutable config, a participant roster and validated station assignments; reject repeated starts and invalid participant changes after start.
2. Implement set_engine_power, basic left/right lane movement and coolant with role/stage validation. Add the base heat and critical-heat hull damage rules and fixed timer from the design. Leave remaining boost/shield controls for Phase 09.
3. Apply actions atomically; reject missing ownership, invalid values and cooldown violations without changing state or consuming RNG. Expose copied/immutable snapshots.
4. Advance each step in a documented order: queued commands supplied by caller, continuous effects, then terminal checks. Hull loss wins a tie with time expiration; terminal state is stable under further calls.
5. Own a seeded RNG without generating random emergencies yet. Add a replay harness using fixed IDs, seed, config version, tick-indexed actions and snapshots. Document accepted action order.
6. Run hundreds of simulated ticks without wall-clock waits, then document the public engine API and extension points that Phase 03 will adapt.

## Testing requirements

Cover start/tick validity, default 900-tick victory, forced heat defeat, terminal idempotence, ownership, cooldown boundaries, atomic rejection and snapshot isolation. Replay identical traces twice and compare every semantic snapshot. Run pytest, Ruff, mypy and repository checks.

## Manual verification

Run a short REPL/script round using a fixed seed and explicit tick loop. Change a valid action and observe a deterministic state difference. No web server should be needed.

## Completion criteria

The pure engine runs and ends rounds with deterministic evidence; all implemented actions have validation tests; no network/time dependency exists; unsupported future actions are explicitly absent rather than partly implemented.

## Documentation updates

Update GAME_STATE.md, GAME_DESIGN.md and ARCHITECTURE.md for the actual API/tick rules. Record limitations clearly and update the master ledger only after verification.

## Handoff notes for next phase

Phase 03 may call this API but must not rewrite its rules. The initial engine is deliberately smaller than the Phase 09 action catalog.

