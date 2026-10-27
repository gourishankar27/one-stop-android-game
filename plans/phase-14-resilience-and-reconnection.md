# Phase 14 — Resilience and Reconnection

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Harden multiplayer behavior against real phone/network interruptions and stale connections.

## Why this phase exists

The full MVP requires recoverable brief outages and predictable behavior when recovery fails.

## Dependencies

Phase 11 complete. Include Phases 12/13 in tests only if implemented.

## In scope

Wi-Fi interruption, Android backgrounding/rotation/process recreation, token-backed resume, full snapshot recovery, duplicate socket fencing, timeout/expiry, host disconnect and server restart feedback.

## Explicitly out of scope

No persistent server recovery, multi-worker scaling, offline authority, accounts, action replay after resume or hidden host migration during active rounds.

## Architecture considerations

Use the existing 30-second disconnect grace. Pause all required-controller stages and resume the remembered stage; expired running sessions abort rather than award defeat. Lobby host transfer occurs only after grace. Tokens stay stable per membership; replace socket generations atomically.

## Files likely to be created or modified

application/{sessions,rooms,room_runner}.py; protocol errors/recovery fixtures; Android repository/session storage/lifecycle wiring; server fault-injection tests; Android virtual-time/UI tests.

## Data models / APIs involved

ConnectionState and session-expired handling; generation-fenced membership, pending request cache, client_action_seq and full role/public snapshots. No client supplies its own authoritative resume state.

## Implementation tasks

1. Write an interruption behavior matrix before coding: brief disconnect, >30s grace, explicit leave, duplicate resume, background suspension, process death and server restart.
2. Close/fence the superseded socket atomically; reject its queued commands and late callbacks. Preserve per-round action sequence and request dedup state during resume.
3. Pause/resume room stage and simulation deadlines correctly. Use monotonic wall time for grace; abort on expiry, remove departed/expired members and transfer a missing host among connected survivors, including on aborted results. Reject rematch with fewer than two; allow return to lobby to recruit again.
4. Persist only the minimal private session credential/endpoint needed for process recreation in app-private, backup-excluded storage. Clear on leave/expiry; never expose it to saved UI bundles or logs.
5. Implement bounded reconnect/backoff and full-state replacement. Clear stale private controls first; render terminal/lobby snapshots even when one-shot events were missed. Do not automatically retry uncertain commands.
6. Run outage tests with multiple clients and check bounded queues/task cleanup across repeated cycles. Give clear retry/leave UI and server-restart explanation.

## Testing requirements

Use fake clocks for grace/watchdogs, concurrent-resume race tests, old-generation actions, stale round/seq handling, slow clients and server shutdown. Android virtual-time tests cover backoff/process recovery/credential clearing. Real-device Wi-Fi, background and process-kill checks are required; verify other players observe correct pause/abort.

## Manual verification

On 2 and 3 phones, interrupt Wi-Fi briefly then beyond grace, background one app, kill/reopen it, connect a duplicate session and restart the server. Repeat for the host. Record expected/actual stage, roster, outcome and explanation for each case.

## Completion criteria

The behavior matrix is implemented and verified, private data never crosses sessions, duplicate sockets cannot mutate state and outages yield clear outcomes. Required real-device cases must run before marking complete.

## Documentation updates

Update architecture/state/protocol policies if changed, TESTING.md with fault evidence, and master ledger. A safe known limitation must be explicit rather than hidden by an endless spinner.

## Handoff notes for next phase

Phase 15 validates actual group play and tuning. Optional LAN and second-scenario work remain deferred until that evidence exists.

