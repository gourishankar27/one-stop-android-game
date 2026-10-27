# Phase 04 — Room and Lobby System

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Implement authoritative in-memory room membership, admission credentials and ready/host permissions.

## Why this phase exists

Multiple phones need one consistent lobby before role assignment and gameplay can begin.

## Dependencies

Phase 03 complete.

## In scope

Create/join/leave, six-character codes, names, 2–3-controller capacity, host identity, ready state, lobby snapshots, credentials, resume primitive, lobby disconnect grace and expiry.

## Explicitly out of scope

No Android UI, game launch, role reveal, gameplay tick loop, observer mode, accounts or persistence. Start validates eligibility but returns feature_unavailable until Phase 08.

## Architecture considerations

One process owns the registry; serialize code generation and joins. Room codes discover rooms but never authenticate an existing player. Token digests and connection generations stay outside domain. Enforce the host seat/grace policy in ARCHITECTURE.md.

## Files likely to be created or modified

server/src/one_job/application/{rooms,sessions,room_service}.py; protocol/messages.py; api/websocket.py; server/tests/application/test_rooms.py; tests/api/test_lobby.py.

## Data models / APIs involved

Room contains code, host ID, members, monotonic room_revision and idle-expiry metadata. Session has a secure token digest, membership ID and generation. Start eligibility is a service function that later launch code reuses.

## Implementation tasks

1. Generate collision-checked secure six-symbol codes and UUID memberships. Trim/validate names and normalize codes; allow duplicate names while keeping IDs distinct.
2. Implement create/join and targeted session_accepted, then full lobby snapshots. Enforce room/full/started/capacity errors and reset ready flags on membership changes.
3. Implement ready, leave, request_state and server-side host validation. Unit-test start eligibility for exactly 2 or 3 connected ready players; do not advertise a playable start yet.
4. Add stable resume tokens, digest lookup and connection replacement fencing. Cache bounded recent command replies and reject request-ID conflicts. Do not log secret tokens.
5. On lobby disconnect hold membership/host for 30 seconds, then remove/transfer host to the earliest connected member; expire empty rooms and 30-minute idle lobbies with an injected clock.
6. Broadcast membership changes with one revision per mutation. Ensure simultaneous joins, stale-socket commands and shutdown cannot leave inconsistent registry entries.

## Testing requirements

Test collision retry exhaustion, concurrent joins at capacity, invalid names/codes, non-host start, ready reset, explicit leave, disconnect/resume/expiry, host transfer, invalid token and duplicate connection fencing. Use at least three simulated socket clients. Check no session token appears in shared messages/logs.

## Manual verification

With Python clients create a room, join twice, toggle readiness, leave and resume one membership. Compare lobby code/roster/revision on all sockets. Start must give an explicit unavailable response after valid eligibility.

## Completion criteria

Room and lobby behavior matches the documented policies with integration evidence; credentials stay private; registry cleanup works; no game start or Android flow is claimed.

## Documentation updates

Update protocol implemented-subset notes, room lifecycle docs and test commands. Add an ADR only for a significant policy change, then update the master ledger.

## Handoff notes for next phase

Phase 05 builds the client shell; Phase 06 consumes this admission protocol. Phase 08 replaces the start feature gate after eligibility validation.

