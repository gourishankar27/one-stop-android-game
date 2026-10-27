# Phase 00 — Repository Foundation

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Provide independently openable backend and Android projects, durable architecture documents and an executable one-phase development workflow.

## Why this phase exists

Later sessions need a real source tree and honest validation evidence before they add domain behavior.

## Dependencies

None. This is the initial repository handoff.

## In scope

Python packaging and health endpoint; Compose placeholder; official Gradle wrapper; formatter/static-check settings; cross-platform scripts; all required documents and phase plans.

## Explicitly out of scope

No rooms, WebSocket handlers, engine, roles, gameplay, production UI, accounts, database or deployment.

## Architecture considerations

Preserve the server/client authority boundary even in naming. Avoid empty application frameworks; create future packages only when behavior needs them. A dependency download failure is a pending verification gate, not a successful build.

## Files likely to be created or modified

Root README.md, AGENTS.md, .gitignore, .editorconfig, .gitattributes; docs/*; plans/*; server/pyproject.toml and uv.lock; server/src/one_job/main.py and api/health.py; server/tests/test_health.py; android/*; scripts/*.

## Data models / APIs involved

GET /health returns the typed liveness response with status=ok and service=one-job-server. MainActivity renders only the foundation screen. No gameplay API is exposed.

## Implementation tasks

1. Inspect the supplied source, documents and validation record. Retain work already present; do not regenerate the project from an Android Studio template over existing files.
2. Confirm normal src-layout Python installation with uv sync --locked --extra dev. Verify the included Gradle wrapper JAR, scripts and SHA-256-pinned distribution; use JDK 17 and SDK Platform 36/Build Tools 35.0.0.
3. Check that README commands work from a path with ordinary Windows drive letters and that local SDK paths, virtual environments, signing keys and build outputs are ignored.
4. Review all 19 phase briefs, dependencies, protocol payloads, role privacy rules and the two-player station assignment. Fix actual contradictions without implementing later features.
5. Run the checks below and update FOUNDATION_VALIDATION.md with exact evidence. Complete any remaining Android build/device verification on the local machine. Do not invent passed results.

## Testing requirements

Run python scripts/check_repository.py, python scripts/dev.py check-server, and uv build from server/. From android/ run the wrapper assembleDebug, lintDebug and testDebugUnitTest tasks; run connectedDebugAndroidTest on an available device. The unit-test task may be NO-SOURCE at this stage and must be described that way.

## Manual verification

Run the backend and request /health in a separate terminal. Open android/ in Android Studio, sync and launch app on an Android 8.0+ emulator/device; see the foundation text in both system themes. Confirm no create/join flow is advertised as working.

## Completion criteria

All named source/documents/plans exist, the repository checker and backend checks pass, the Android debug build and lint pass, and the placeholder launches on a device/emulator. Missing environment capabilities keep the phase open with a specific pending gate.

## Documentation updates

Update the root and component READMEs, FOUNDATION_VALIDATION.md and the master progress ledger. Record any changed toolchain/architecture decision in DECISIONS.md.

## Handoff notes for next phase

Once every gate is verified, mark Phase 00 complete and recommend Phase 01. Do not create domain types during this session.

