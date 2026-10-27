# Phase 17 — Second Scenario

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Implement one small submarine scenario to test what architecture should be shared across scenarios.

## Why this phase exists

The second real example should guide extraction; a generic framework designed before it would be guesswork.

## Dependencies

Phase 15 complete and actual spaceship playtests support continuing. Phase 16 is not required.

## In scope

A narrow submarine design, scenario selection, scenario-local roles/systems/actions/emergencies/results and only the shared abstractions proven useful by two implementations.

## Explicitly out of scope

No scenario DSL, plugin marketplace, dozens of scenarios, user-authored content, extra platforms or rewriting the validated spaceship gameplay.

## Architecture considerations

Start with a written submarine mini-spec and acceptance traces before code. Proposed three stations are Helm, Engineer and Ballast, with pressure/leak/oxygen coordination; values and exact mechanics must be decided in that mini-spec, not assumed to already exist.

## Files likely to be created or modified

docs/scenarios/SUBMARINE.md; domain/scenarios/{spaceship,submarine}; narrow shared engine interfaces only as justified; protocol scenario-tagged DTOs; Android scenario panels; regression tests for both.

## Data models / APIs involved

Add a typed ScenarioId in room config and discriminated scenario-specific action/view unions. Preserve protocol compatibility explicitly; a required changed payload needs version negotiation or a major bump. Keep scenario-specific state out of an untyped universal dictionary.

## Implementation tasks

1. Confirm recorded spaceship evidence and identify a concrete question the second scenario will test. Write a mini-spec covering station responsibilities, private/shared data, 2-player assignment, initial constants and two cooperative emergencies before implementation.
2. Design one successful and one failing deterministic acceptance trace for the submarine. Record a decision for any protocol change before writing new message handlers.
3. Implement submarine rules in a separate pure module using the existing fixed-time/seed/replay approach. Extract shared lifecycle/assignment plumbing only when both scenarios need it.
4. Add host scenario selection in lobby with readiness reset and server validation; bind private Android station views/controls to the selected scenario.
5. Keep existing spaceship replay/permission/privacy behavior unchanged. Test no cross-scenario action or view can be accepted on the wrong round.
6. Play both scenarios with humans; document what became shared and what correctly remained scenario-local. Stop after one additional scenario.

## Testing requirements

Both scenarios need pure deterministic success/failure traces, role ownership/privacy checks, protocol compatibility tests and real-client full-loop checks. Run the complete spaceship regression suite after every extraction. Manual submarine 2/3-player sessions verify actual coordination.

## Manual verification

Create spaceship and submarine rooms, play/rematch each and verify station information is scenario-specific. Send a spaceship action to a submarine round and observe a safe rejection. Compare human feedback without inventing conclusions.

## Completion criteria

One specified submarine scenario is playable and tested; spaceship regressions pass; shared abstractions have concrete use in both; no generic content framework is added.

## Documentation updates

Add the mini-spec, update architecture/protocol/decision docs for observed generalization and record actual human findings. Update roadmap without claiming all future scenarios are now supported.

## Handoff notes for next phase

Phase 18 does not depend on this optional scenario. Recheck release scope explicitly if submarine is to be included in an external build.

