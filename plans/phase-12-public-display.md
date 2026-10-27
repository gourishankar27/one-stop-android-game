# Phase 12 — Public Display

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Let an extra Android phone/tablet show shared round information without private station data.

## Why this phase exists

A common screen can help the group coordinate while keeping asymmetric station information meaningful.

## Dependencies

Phase 11 complete. Optional; not a prerequisite for the MVP resilience path.

## In scope

Observer admission, maximum two display sessions, public projections, display lobby/game/results UI and safe reconnect using observer credentials.

## Explicitly out of scope

No Android TV, casting, web display, new controller slots, host permission or access to private role instructions.

## Architecture considerations

Display membership is a distinct session kind, not a player with an empty role. It consumes no controller slot, cannot satisfy readiness and cannot acquire host. Construct public projection independently; UI hiding is insufficient.

## Files likely to be created or modified

application/sessions.py and projections.py; protocol join_display/public_state; server privacy/admission tests; Android display route/ViewModel and tests.

## Data models / APIs involved

join_display{room_code}; session_accepted{kind=display,player_id=null,resume_token}; public_state{public:PublicRoundView}. Observer actions allowed: ping, request_state, resume_session and leave_room only.

## Implementation tasks

1. Add observer admission with separate capacity/credentials and full public snapshot for any room stage. Do not expose room player credentials to displays.
2. Enforce observer permissions before dispatch; crafted player_action/start/ready requests must fail without changing room state.
3. Build a public-only projection with time, hull/shield percentages, shared warning labels and result. Prove seed, private targets and station objects are absent.
4. Add an Android display entry/join path using an existing device, with large readable information and no role controls.
5. Ensure display disconnect never pauses gameplay, deletes player readiness or transfers host. Support observer resume and room deletion/expiry feedback.
6. Check tablet sizing and shared-screen readability, retaining normal Android lifecycle behavior and reduced-motion support where already available.

## Testing requirements

Server tests inspect public projection absence using secret sentinels and reject every observer-only permission violation. Test display capacity and reconnect independently of controllers. Android tests render only public state. Run real observer-plus-players integration.

## Manual verification

Join an extra phone/tablet as display during lobby and running, watch warnings/results, disconnect it and verify the round continues. Inspect its frames to confirm private details never arrived.

## Completion criteria

An Android observer screen works without consuming controller slots or revealing private role data; observer permission/privacy tests pass; no TV/casting work is added.

## Documentation updates

Update protocol/UI/architecture docs for implemented observer behavior and master progress. If Phase 12 is skipped, keep its checkbox open and MVP path unblocked.

## Handoff notes for next phase

Phase 13 may enhance this screen if implemented, but Phase 14 can proceed without it. Do not expand to casting as part of this phase.

