# Phase 18 — Release Foundation

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Prepare a reviewable Android/backend package and instructions for limited external testing without publishing it.

## Why this phase exists

External testing needs configuration, signing, privacy and operating instructions beyond a local debug build.

## Dependencies

Phase 15 complete. Optional Phases 12, 13, 16 and 17 are included only if selected and verified.

## In scope

Debug/release configuration, environment handling, logging policy, crash-reporting decision, signing guide, backend deployment guide, privacy review and Play internal-test checklist.

## Explicitly out of scope

No automatic upload, signing-key generation without explicit instruction, production deployment, public listing, store policy assumptions from old dates, monetization or analytics expansion.

## Architecture considerations

Keep WSS, single-process room ownership and no-persistence limitations explicit. Release artifacts cannot use debug cleartext/localhost defaults. Operational crash reporting is optional and needs a documented minimal-data decision before adding a vendor SDK.

## Files likely to be created or modified

Android variants/config and release build settings; docs/release/{CHECKLIST,SIGNING,BACKEND,PRIVACY}.md; config validation; safe backend logging; build/test scripts only where useful.

## Data models / APIs involved

Environment-specific endpoint configuration, build/version metadata and safe diagnostics; no new gameplay models. Signing credentials remain outside the source tree and are never requested into chat or committed.

## Implementation tasks

1. Read current official Android/Play external-test requirements when executing this phase; record retrieval date and applicable gates instead of assuming the foundation target SDK is sufficient forever.
2. Separate debug/test/release endpoint and logging configuration. Fail an external build with unset backend URL, debug cleartext policy or secret-bearing diagnostics.
3. Document Android signing with an external keystore, backups and environment/property references. Prepare commands and checks without creating or uploading credentials.
4. Document one-worker backend operation behind WSS, process restarts losing rooms, resource/idle limits, health checks and rollback. Do not provision or deploy services.
5. Inventory collected data (names, session tokens, network diagnostics), retention and transport. Decide whether crash reporting is needed and add no vendor until the decision warrants it.
6. Create a release checklist with tested device/API matrix, reconnect/full-loop smoke tests, versioning, internal-testing preparation and explicit human publication approval step. Produce reviewable unsigned artifacts when credentials are absent.

## Testing requirements

Run backend/package/static checks, full-loop/reconnect/privacy integration, Android lint/tests and release assembly. Inspect merged release manifest/config and packaged resources for debug endpoints/secrets. Confirm release logs redact credentials/private views and that no upload/deploy command ran.

## Manual verification

Install a review build on selected devices, point at an explicitly prepared test backend if one exists, and run the checklist. If backend/signing credentials are unavailable, mark those verification gates pending and deliver documented local artifacts only.

## Completion criteria

Release foundation and reviewable artifacts/checklist exist with observed build/security/privacy evidence. Unavailable external credentials or live testing are explicit pending gates. No external publication/deployment occurs as a side effect.

## Documentation updates

Update release guides, toolchain requirements, architecture/operations limitations, privacy decision and master progress ledger. Record the exact included feature/scenario scope.

## Handoff notes for next phase

Hand the user the artifacts and a concrete checklist for any later authorized external action. Stop; do not publish or create a new phase implicitly.

