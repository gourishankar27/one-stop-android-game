# Phase 08 — Role System

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Assign Pilot/Engineer/Shields privately and enforce station ownership through engine and server boundaries.

## Why this phase exists

Asymmetric information and controls are the central cooperative mechanic; privacy cannot wait until UI polish.

## Dependencies

Phases 02 and 07 complete.

## In scope

Seeded 2/3-player assignment, role metadata, round ID creation, host start to briefing, private role_assigned/role_state, acknowledgement, role reveal/instructions and permission validation.

## Explicitly out of scope

No random emergency framework, full control panels, final countdown/results/rematch UI or extra roles. Public observer join is Phase 12.

## Architecture considerations

Use the same seeded assignment order in GAME_DESIGN.md. In two-player mode assign Pilot and Engineer+Shields. Never send all station details to all phones. Host status does not grant private role access. Keep role metadata separate from mutable ship rules.

## Files likely to be created or modified

domain/roles.py; application/round_service.py and projections.py; protocol messages; server/tests/domain and privacy tests; Android role reveal/instruction UI/ViewModels and tests.

## Data models / APIs involved

RoleAssignment, StationMetadata, PublicRoundView/PlayerRoundView, role_assigned and briefing_ready. Round context gets a new ID/config/seed; resume token stays room-local.

## Implementation tasks

1. Replace the start feature gate with server eligibility checks and round construction. Freeze the participant roster and seed-shuffle station owners.
2. Construct allowlisted role projections and metadata with short primary control instructions. Include only owned station views, including both views for the two-station participant.
3. Send targeted role_assigned and briefing state, collect per-player briefing acknowledgements for all owned stations, enforce the 60-second briefing timeout and safe disconnect pause policy.
4. Enforce role ownership in the engine on each action using authenticated actor identity. Do not trust a role/player field supplied by Android.
5. Build Android reveal/instructions and Engineer/Shields station switching skeleton. Acknowledge only after both owned station briefings are visible.
6. Until Phase 09 integrates running controls, hold after acknowledged briefing with a clear development-stage status; do not invent a client-driven start. Phase 11 later completes timed orchestration.

## Testing requirements

Test reproducible assignments for 2 and 3 players, unique station coverage, invalid roster sizes, stale round IDs, wrong-role rejection, host privacy and projection absence with sentinels. JVM/UI tests verify own station metadata only. Run a real start/briefing on multiple phones.

## Manual verification

Start rooms with 2 and 3 phones; each sees correct station(s). Capture test frames and prove no other station details arrive. Non-host start and wrong-role actions are rejected. Let a briefing timeout and verify an explicit abort.

## Completion criteria

Server role ownership and private reveal work end-to-end with deterministic and privacy tests; two-player mode is accessible; no future emergency/gameplay UI is implemented.

## Documentation updates

Update GAME_STATE.md and UI_UX.md for final role metadata/projection APIs, NETWORK_PROTOCOL.md implemented subset, and the master ledger.

## Handoff notes for next phase

Phase 09 activates control panels and running simulation behind the acknowledged briefing. Phase 11 completes countdown/results/rematch orchestration.

