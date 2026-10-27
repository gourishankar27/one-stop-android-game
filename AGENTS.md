# One Job repository instructions

One Job is an Android party game for friends in the same room. Players control
different spaceship stations and communicate aloud to survive together.

## Architecture

- The Python server owns rooms, permissions, simulation time, actions and results.
  A host is a player with room-management permissions, never a network authority.
- `server/src/one_job/domain/` will contain synchronous, typed, pure Python game
  models and rules. It must not import FastAPI, Pydantic, sockets, asyncio, clocks,
  environment configuration, or Android concepts. Pass configuration and a seed.
- Transport validates typed DTOs and maps them into domain inputs. Do not put
  gameplay rules in routes, serializers, Compose functions, or ViewModels.
- Emit allowlisted public and per-player projections. Never serialize the full
  internal state and ask Android to hide private fields. Hosts see their own roles.
- Use the versioned contract in `docs/NETWORK_PROTOCOL.md`. Update the document,
  fixtures and both implementations together when the contract changes.
- Use an injected seeded random generator, fixed simulation steps and recorded
  action order for reproducibility. Tests must not sleep for simulated game time.
- Use one server process while rooms live in memory. Do not add a database,
  generic scenario framework, dependency-injection framework or service fleet
  without a concrete need and a decision entry.

## Coding

Python: Python 3.12+, type hints on public functions, clear dataclasses/enums in
the domain, Pydantic at boundaries, pytest, and async only for I/O/orchestration.
Use the `src/` package layout. Keep mutable state owned by one room task.

Android: Kotlin, Compose, Material 3, coroutines, StateFlow and ViewModel.
Collect state with lifecycle awareness. UI emits intents; repositories own
connection state; a network data source owns sockets. Use ordinary constructor
injection initially. Never simulate authoritative ship state on a phone.

## One-phase session workflow

1. Read this file, `plans/plans.md`, the selected phase and relevant documents/code.
2. Inspect git status and prerequisites before editing. Preserve unrelated work.
   Report real discrepancies. Resolve routine implementation choices within scope;
   record significant deviations in `docs/DECISIONS.md` before implementing them.
3. Implement only the selected phase. Do not redesign the repository, implement
   later-phase features, or refactor unrelated code.
4. Add meaningful tests with new behavior. Run relevant tests, builds and configured
   checks. Report exact commands and observed results; never claim an unrun check
   passed. Record environment limitations separately from code failures.
5. Perform the phase's manual verification where possible. State what remains unrun.
6. Update affected contracts, decisions and setup documentation.
7. Update `plans/plans.md` only when all completion gates have evidence. Otherwise
   leave the checkbox open and record the specific pending gate. The master plan
   is the only progress ledger; individual phase files define scope and gates.
8. End with: Phase completed; Files changed; Tests run; Results; Manual verification;
   Architecture decisions; Known limitations; Recommended next phase.
9. STOP. Wait for another instruction before starting another phase.

## Verification commands

From the repository root: `python scripts/check_repository.py`.
From `server/`: `uv sync --locked --extra dev`, `uv run pytest`,
`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`.
From `android/`: `./gradlew :app:assembleDebug :app:lintDebug :app:testDebugUnitTest`
(Windows: `./gradlew.bat`). Use a device for `:app:connectedDebugAndroidTest`.
See `docs/TESTING.md` for layered checks and the currently observed evidence.

## Repository actions

Unless explicitly requested, do not push, deploy, publish builds, alter external
services or introduce credentials. Never commit secrets, local SDK paths, signing
keys, session tokens, raw private projections or generated build directories.
Do not change the license or assign copyright ownership on the user's behalf.
