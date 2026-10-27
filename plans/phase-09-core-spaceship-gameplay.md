# Phase 09 — Core Spaceship Gameplay

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Connect the documented Pilot, Engineer and Shields controls to a live authoritative spaceship simulation.

## Why this phase exists

The crew needs a working cooperative control loop before randomized emergencies add pressure.

## Dependencies

Phases 02, 06 and 08 complete.

## In scope

Complete initial action catalog/physics, private control panels, fixed-step room runner, 5Hz role projections, action feedback and basic start-to-running after briefing.

## Explicitly out of scope

No random emergencies, polished results/rematch, extra stations, public display or sound. Phase 11 owns the final countdown and lifecycle UX.

## Architecture considerations

Extend the existing engine instead of duplicating it in server routes. The room owner serializes commands/ticks; assign authoritative tick/order and fence old connections. Slow sockets cannot delay simulation. Android may preview an input but reconciles accepted state.

## Files likely to be created or modified

domain/{engine,rules,actions}.py; application/{room_runner,projections}.py; protocol action mapping; Android gameplay/role panels; server engine/runner tests; Android intent/state tests.

## Data models / APIs involved

All Action union variants in NETWORK_PROTOCOL.md; integer resource/cooldown state from GAME_DESIGN.md; correlated ack/action_rejected; typed role_state with public strip.

## Implementation tasks

1. Implement remaining evade, engine boost/shutdown, shield facing/active/recharge/boost rules with power reservations, duration, cooldown and all-or-nothing validation.
2. Run a server-owned fixed 100ms ticker per active room after all briefings acknowledge. Add a baseline direct running transition; Phase 11 replaces it with countdown. Never start simulation from a phone clock.
3. Serialize accepted commands before continuous effects, record tick/order, publish role views at 5Hz and terminal state when the existing engine ends. Apply catch-up/overload policy and bounded outgoing queues.
4. Build large Pilot controls, Engineer slider/actions and Shields selectors/actions. Two-station tabs retain urgent badges. Throttle/conflate slider sends to 10Hz; avoid an unbounded send queue.
5. Render server cooldowns, power rejections and connection pauses. Show a minimal truthful terminal panel without completing the future results/rematch navigation.
6. Exercise cross-station power pressure manually and run 2/3-client control tests. No emergency scheduler should be necessary to prove core controls.

## Testing requirements

Parameterize every action for valid/rejected stage, ownership, bounds, cooldown and power. Test shutdown cancellation, zero-energy release, exact resource arithmetic and deterministic traces. Runner tests use a fake monotonic clock and slow consumer. Android tests prove intent emission and reconciliation, not copied physics.

## Manual verification

On three phones, Pilot requests an evade, Engineer changes output and Shields recharges/changes facing. Confirm cross-system effects, accepted/rejected feedback and synchronized time/hull without private information leakage. Repeat with two-station switching.

## Completion criteria

A server-timed control loop works on real phones, all initial action rules are tested, projections remain private, and no client computes game outcomes. Random emergencies remain absent.

## Documentation updates

Update actual engine API, action semantics, runner timing and UI notes in relevant documents; record changed balance defaults as provisional; update the ledger.

## Handoff notes for next phase

Phase 10 adds event pressure using the existing rules and controls. Phase 11 completes the party session loop.

