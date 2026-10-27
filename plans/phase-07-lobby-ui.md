# Phase 07 — Lobby UI

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Make create, join and lobby flows usable on multiple real Android phones.

## Why this phase exists

Friends must reach a shared, understandable lobby before private station assignment is introduced.

## Dependencies

Phases 04 and 06 complete.

## In scope

Name/code forms, create/join submission, room-code display, roster, host marker, ready toggle, start availability, leave confirmation and connection feedback.

## Explicitly out of scope

No role reveal or running gameplay yet. A valid start may still show the planned feature-unavailable response until Phase 08.

## Architecture considerations

UI eligibility mirrors server hints but cannot authorize start. One repository supplies state for all destinations. Use IDs for roster keys; duplicate names are legal. Preserve typed input on rejected submissions and keep server error codes separate from user-facing copy.

## Files likely to be created or modified

android UI/ViewModels for home, create/join and lobby; navigation; repository integration; JVM/UI tests; server tests for any contract discrepancy.

## Data models / APIs involved

CreateJoinUiState and LobbyUiState render lobby_state/session_accepted. Start intent has no client-supplied host/player identity. Name/code validation follows GAME_STATE.md exactly.

## Implementation tasks

1. Implement large create/join controls, player-name input and six-symbol code input with normalization. Prevent double taps while a request is outstanding.
2. Bind repository replies to navigation only after admission succeeds. Handle unknown/full/started rooms and uncertain connection loss without silently creating repeated rooms.
3. Render room code, members, connected/ready state and host label. Enable readiness only for the local controller and start only for the eligible local host.
4. Provide an explicit reason for disabled start. Handle feature_unavailable as a visible planned-stage message, not a fake role screen.
5. Implement leave confirmation, credential cleanup and return home on expiry/room removal. Show reconnect state without duplicating members.
6. Run a real 2- and 3-phone lobby session against one backend and record observed synchronization.

## Testing requirements

ViewModel tests cover admission success/error/pending, name/code validation, duplicate submit and host/non-host eligibility. Compose tests cover form input, roster/ready changes and leave. Integration checks connect multiple real devices; retain server protocol tests.

## Manual verification

Create on phone A, join B and C, toggle ready, disconnect/rejoin one phone and leave. All show one code/roster. Non-host cannot start even via a crafted request. Valid host start remains explicit about feature availability.

## Completion criteria

Two and three real Android clients share a correct lobby with host/ready/leave feedback; automated relevant checks pass; no fake completed round is displayed.

## Documentation updates

Update UI_UX.md screenshots/behavior notes without claiming final visuals, TESTING.md with device evidence and the master ledger. Fix protocol documentation if actual payloads changed.

## Handoff notes for next phase

Phase 08 enables start into the role briefing flow and adds ownership. Stop after the lobby is verified.

