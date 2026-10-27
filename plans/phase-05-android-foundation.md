# Phase 05 — Android Foundation

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Expand the minimal Compose app into a client architecture and navigation shell with testable UI state.

## Why this phase exists

Networking and multiplayer screens need explicit ownership, lifecycle handling and dependency boundaries.

## Dependencies

Phase 00 complete. Numeric default order reaches this after Phase 04; no server behavior is required to build the shell.

## In scope

Navigation destinations, app-level constructor wiring, theme structure, Home/Create/Join/Lobby/Role/Gameplay/Results placeholders, ViewModels where stateful, coroutine/StateFlow test setup.

## Explicitly out of scope

No sockets, fake working multiplayer, server rules, completed lobby UI, sound assets or final visual design.

## Architecture considerations

Use Compose UI → ViewModel → repository interface → data source boundaries. Add use cases only when they contain reusable client orchestration. The repository interface must model server state, not engine physics. Use one Activity and lifecycle-aware state collection.

## Files likely to be created or modified

android/app/build.gradle.kts; com/onejob/game/{app,ui,navigation,data,domain} packages as needed; local JVM tests and androidTest navigation tests; docs/UI_UX.md.

## Data models / APIs involved

AppDestination and ConnectionStatus are local client concepts; UI state is immutable StateFlow. Define a narrow GameRepository interface for later injection, using explicitly unavailable/fake preview data only in development/tests.

## Implementation tasks

1. Inspect the scaffold and keep its pinned compatible toolchain unless a demonstrated build issue requires a documented update.
2. Add navigation, lifecycle/ViewModel and coroutine dependencies with explicit versions. Build a small composition root with constructor injection and no third-party DI framework.
3. Create screen destinations from UI_UX.md and a truthful placeholder route for each future flow. Keep Home navigation usable without implying rooms already work.
4. Add stateful name/join form ViewModels only where needed. Expose immutable UI state and intent methods; keep validation/presentation separate from networking.
5. Handle system back, insets, configuration changes and state restoration for nonsecret typed form inputs. Never save session tokens in SavedStateHandle.
6. Add coroutine test utilities and navigation/UI checks that demonstrate real behavior rather than one assertion per empty screen.

## Testing requirements

Run Gradle debug build, lint and JVM tests. Test destination/back-stack behavior, StateFlow updates and retained form input with a fake repository. Run instrumented smoke/navigation checks on a device; verify no composable starts network I/O.

## Manual verification

Open all placeholder destinations, use Back, rotate and change font size. The shell must remain readable and label unimplemented flows. Confirm no accidental create/join backend call exists.

## Completion criteria

App builds and launches; navigation/state boundaries are established; ViewModel/navigation tests pass; no authoritative game rules or live networking are added.

## Documentation updates

Update UI_UX.md with actual navigation and ARCHITECTURE.md with package/wiring decisions. Update Android README and test commands if required.

## Handoff notes for next phase

Phase 06 implements the repository/data source behind this shell. Do not implement lobby behavior ahead of it.

