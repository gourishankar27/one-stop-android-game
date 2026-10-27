# Phase 06 — Android Networking

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Connect Android to the typed v1 WebSocket protocol through a repository and lifecycle-safe data source.

## Why this phase exists

The lobby UI must receive authoritative session state and actionable connection errors instead of raw socket callbacks.

## Dependencies

Phases 03, 04 and 05 complete.

## In scope

OkHttp WebSocket, kotlinx.serialization DTOs, GameRepository implementation, request correlation/timeouts, session state, ping, basic bounded reconnect and full snapshot recovery.

## Explicitly out of scope

No complete lobby screens, gameplay rules, public display, background service or final resilience matrix. Do not auto-replay player actions after reconnect.

## Architecture considerations

Exactly one active socket per repository session. Strictly type outgoing messages; tolerate additive incoming fields. Clear cached private views on reconnect, fence old callbacks and apply revisions per room/round. Keep tokens private and out of logs/navigation.

## Files likely to be created or modified

android/app/build.gradle.kts; AndroidManifest.xml and debug-only network security resources; data/{network,protocol,repository}; ViewModel mapping; tests/data/*; protocol fixture files shared from docs/protocol-fixtures/.

## Data models / APIs involved

Sealed ClientMessage/ServerMessage, DTO payloads, ConnectionState, pending-request map and session credential store. Public GameRepository methods submit intents and expose immutable session/connection StateFlows.

## Implementation tasks

1. Add network/serialization plugins and dependencies; create a configurable endpoint provider without hardcoded public credentials. Default release to WSS-only; add INTERNET permission.
2. Provide explicit debug endpoint configuration for emulator 10.0.2.2 or a trusted reachable LAN address, with debug-only cleartext policy. Explain physical-phone addressing; localhost on a phone is not the PC.
3. Implement typed encode/decode and contract fixtures checked by Python and Kotlin. Map errors/close codes without exposing raw secret-bearing frames.
4. Implement open/close, ping watchdog, correlated replies with five-second timeout, bounded sends and request-state reconciliation. Treat a timed-out command as uncertain, not automatically rejected.
5. Implement credential-backed resume with bounded 1/2/4/8-second retry delays within grace. Do not retry create/join blindly or resend actions; replace state from a full snapshot.
6. Handle app owner cancellation/rotation without duplicate sockets. Clear credentials on explicit leave or session_expired; surface unavailable server and protocol errors as distinct states.

## Testing requirements

JVM tests with fake socket/virtual time cover codec fixtures, unknown fields/types, correlation, timeouts, stale generations, equal-revision distinct messages, reconnect bounds, credential clearing and no action replay. Run backend fixture tests plus Gradle build/lint/tests and instrumented connection feedback check.

## Manual verification

Connect an emulator and then a physical phone to a local server using a debug endpoint. Ping/create/join via a development harness or repository caller; stop the server and observe recoverable connection state without a crash or secret logs.

## Completion criteria

Repository works against the real server, codec fixtures agree across languages, reconnect foundation is bounded, and UI/network separation is maintained. No complete lobby UI is claimed.

## Documentation updates

Update NETWORK_PROTOCOL.md fixtures/compatibility notes, Android README endpoint instructions and TESTING.md transport checks. Document any dependency choice deviation.

## Handoff notes for next phase

Phase 07 binds usable create/join/lobby screens to these repository APIs. Phase 14 later hardens backgrounding/process-death behavior.

