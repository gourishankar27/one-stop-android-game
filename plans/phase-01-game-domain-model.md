# Phase 01 — Game Domain Model

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Define the pure Python vocabulary, value constraints and state ownership for the spaceship simulation.

## Why this phase exists

The engine and network DTOs must share clear meanings without coupling rules to FastAPI or serialization.

## Dependencies

Phase 00 complete, including local Android verification.

## In scope

PlayerId/Player, Role, RoleAssignment, GameConfig, ShipState, RoundState, GameState, action variants, EmergencyType/EmergencyState records and GameResult.

## Explicitly out of scope

No ticking, emergency scheduler/resolvers, WebSocket DTOs, room registry, Android gameplay or generic scenario framework.

## Architecture considerations

Use dataclasses, enums and explicit typed IDs in one_job/domain. Keep room membership credentials and connection state outside domain models. A player can own multiple stations. Make exposed state snapshots immutable or defensive copies. Use integer units and ticks.

## Files likely to be created or modified

server/src/one_job/domain/{models,actions,config}.py and __init__.py; server/tests/domain/test_models.py; docs/GAME_STATE.md; docs/GAME_DESIGN.md.

## Data models / APIs involved

GameConfig contains the initial values/ranges in GAME_DESIGN.md. Typed actions carry intent parameters; actor identity is a separate trusted input. RoleAssignment maps each of three stations to one existing participant. GameResult distinguishes victory, defeat and aborted.

## Implementation tasks

1. Read GAME_STATE.md and GAME_DESIGN.md; map each term to a class or documented simple type. Keep ShipSystem conceptual unless a concrete class is useful.
2. Implement constructor validation for hull/energy/heat/output bounds, configured 60–120 second duration in 100ms increments, unique participant IDs, and complete station ownership for 2 or 3 players.
3. Define action variants with exact parameter domains matching the planned protocol, without importing transport models. Reject invalid boolean-as-integer inputs where relevant.
4. Define snapshot and emergency records with stable identifiers, ticks and enums. Model result/terminal states so invalid combinations cannot silently pass.
5. Keep balance defaults in one config module, with docs referring to it after implementation. Export a small documented package surface, not every internal helper.

## Testing requirements

Pytest tests valid three-player and two-player ownership, each boundary/invalid configuration, inconsistent IDs, invalid action parameters, result invariants and snapshot aliasing. Run mypy, Ruff and repository checker. Importing the domain must not load FastAPI/Pydantic/asyncio.

## Manual verification

Use a Python REPL to construct a valid config/state and inspect station ownership for 2 and 3 players. Confirm no server process, environment variables or Android is required.

## Completion criteria

Domain types construct valid documented states and reject invalid ones; snapshots cannot mutate internal state; tests and static checks pass; no transport dependency enters the domain.

## Documentation updates

Update GAME_STATE.md with final type names and config ownership. Record only significant deviations in DECISIONS.md; retain the master ledger as the sole progress source.

## Handoff notes for next phase

Phase 02 will consume these models. Do not implement simulation just to demonstrate a model.

