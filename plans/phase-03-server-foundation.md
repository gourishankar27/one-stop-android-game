# Phase 03 — Server Foundation

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Wrap the pure engine with typed WebSocket transport, application lifespan and connection infrastructure.

## Why this phase exists

Rooms need a predictable, testable transport contract and cleanup behavior before they manage players.

## Dependencies

Phase 02 complete.

## In scope

/ws endpoint; typed v1 envelopes; ping/pong; structured errors; bounded socket sends; session/task scaffolding; engine adapter; redacted logs.

## Explicitly out of scope

No full create/join/lobby behavior, gameplay screens, deploy, database or public observer join. Reserved message types return feature_unavailable until their phases.

## Architecture considerations

Keep routes thin and Pydantic DTOs outside domain. Construct services in create_app/lifespan, not module-global room state. Use bounded send queues; socket writes must never stall a room owner. Prepare an injected clock/ticker interface without starting orphan game tasks.

## Files likely to be created or modified

server/src/one_job/protocol/{envelopes,messages,mapping}.py; api/websocket.py; application/{connections,engine_adapter}.py; main.py; server/tests/protocol/* and tests/api/test_websocket.py.

## Data models / APIs involved

ClientEnvelope discriminates type and version; ServerEnvelope carries reply_to/room_revision. Decode only the message subset currently implemented; recognized later commands return feature_unavailable. Adapter maps typed domain errors without exposing internal state.

## Implementation tasks

1. Implement v1 frame parsing and strict field/size/version validation using NETWORK_PROTOCOL.md. Add serializer helpers rather than scattered dict literals.
2. Expose /ws; handle ping before admission; enforce the 10-second admission deadline with an injectable clock and safe close codes.
3. Build a connection object with bounded outbound queue, generation ID, cancellation and safe cleanup. Coalesce snapshots only; do not silently discard terminal replies.
4. Create an application service adapter capable of calling an engine fixture and projecting a minimal test state without gameplay rules in the route. Full live room engine tasks wait for later phases.
5. Log connection lifecycle, request ID, safe operation/error codes and durations. Explicitly redact payload credentials and private views.
6. Cancel and await reader/writer/adapter tasks on disconnect and application shutdown. Preserve the independent health endpoint.

## Testing requirements

Test valid ping/pong, malformed JSON, oversized frames, unknown fields/types, unsupported version, future feature errors, slow consumers and task cleanup. Use FastAPI TestClient plus async tests where needed. Assert error payloads cannot leak test sentinels or resume-token strings. Run backend/static/repository checks.

## Manual verification

Connect with a small local Python WebSocket client, ping, send one malformed/unsupported message and observe the documented response/close. Confirm /health still works. A room is not expected to exist.

## Completion criteria

Typed transport works end-to-end for implemented operations; no full lobby is accidentally implemented; connection tasks close cleanly and logs/errors are redacted; engine remains pure.

## Documentation updates

Update NETWORK_PROTOCOL.md with exact implemented subset, frame limits and close/error behavior; TESTING.md with runnable transport tests; ARCHITECTURE.md for service assembly.

## Handoff notes for next phase

Phase 04 will add the room registry and admission credentials. Do not turn placeholder handlers into rooms in this phase.

