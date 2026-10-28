# Domain model validation — 2026-10-27

Observed Phase 01 implementation and regression checks on Windows, starting from
commit `37c29b2` with a clean working tree. Phase 00's source, lockfile, toolchain
pins and Android placeholder were preserved. The completion ledger is
[plans/plans.md](../plans/plans.md).

## Toolchains and prerequisites

Phase 00 is checked off with prior evidence in FOUNDATION_VALIDATION.md. These
tools were checked again in this session:

| Check | Observed result |
| --- | --- |
| `python --version`; `py -3.12 --version` | Root launcher 3.14.0; Python 3.12.10 available |
| `uv --version`; `uv run --project server --locked python --version` | uv 0.13.6; backend Python 3.12.10 |
| `java -version`; `javac -version` | Temurin JDK/compiler 17.0.18 using session-local `JAVA_HOME` |
| `gradlew.bat --version` in android/ | Gradle 8.13; launcher 17.0.18; daemon criteria Java 17 / Eclipse Temurin |
| Installed SDK `source.properties` | Platform 36, revision 2; Build Tools 35.0.0 |
| Emulator acceleration / boot | WHPX usable; existing API 37 x86_64 AVD booted with emulator 37.2.12 |

The prior ignored `artifacts/foundation/environment.ps1` supplied local uv/JDK/SDK
paths. No machine-specific paths, credentials or generated outputs were added to
source control. The emulator ran read-only without loading or saving snapshots,
using serial `emulator-5584`. No physical device was attached.

## Automated checks

| Command / inspection | Observed result |
| --- | --- |
| `python scripts/check_repository.py` at root | Passed; 19 briefs, Markdown links, packaging/XML, wrapper and pure-domain import boundary inspection |
| `uv sync --project server --locked --extra dev` at root | Passed; 31 locked packages checked |
| `python scripts/dev.py check-server` at root | Passed; internally runs locked sync and the four commands below |
| `uv run --locked pytest` in server/ | 487 passed (485 domain cases + 2 existing health tests), 1 upstream warning; 1.39s |
| `uv run --locked ruff check .` in server/ | All checks passed |
| `uv run --locked ruff format --check .` in server/ | 19 files already formatted |
| `uv run --locked mypy src` in server/ | Success; 10 source files |
| `uv build` in server/ | Wheel and source distribution built successfully, version 0.1.0 |
| Wheel/source inspection | All six domain modules and `py.typed` present in the wheel; source distribution inspected (25 entries) |
| `uv venv --python 3.12 artifacts/phase-01/wheel-env`, then `uv pip install --python artifacts/phase-01/wheel-env/Scripts/python.exe --no-deps server/dist/one_job_server-0.1.0-py3-none-any.whl` at root | Passed; clean environment contains only the built package; domain construction works without web dependencies installed |
| `uv run --locked ruff check ../scripts`, `uv run --locked ruff format --check ../scripts`, `uv run --locked mypy ../scripts` in server/ | Passed; 2 existing helper files |
| `gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest --console=plain` in android/ | BUILD SUCCESSFUL in 1s; 8 tasks executed / 42 up-to-date. Lint report unchanged at 0 errors / 5 warnings; JVM tests `NO-SOURCE` |
| `gradlew.bat :app:connectedDebugAndroidTest --console=plain` in android/ | BUILD SUCCESSFUL in 11s; original smoke test: 1 passed, 0 failures/errors/skips |
| `git diff --check` | Passed; no whitespace errors |

An initial domain test run caught an implementation error: a generated cooldown
field name did not match `recharge_cooldown_ticks` (409 passed, 2 failed, 24 fixture
errors). It was fixed with an explicit typed config-field mapping before the
passing full run above. This was a code issue, not an environment blocker.

The domain tests exercise strict integer/enum/UUID inputs, config bounds and
coherence, two/three-player ownership, all nine action shapes, ship budgets and
cooldowns, emergency record timing, terminal result consistency and nested
snapshot immutability. The isolated subprocess test runs with an empty environment
and confirms no FastAPI, Pydantic, asyncio, socket, HTTPX or Uvicorn module loads.
Tests do not sleep or advance a simulated game.

## Manual domain verification

From server/:

```powershell
uv run --locked python ../artifacts/phase-01/inspect_domain.py
```

The ignored local script constructs a config and complete snapshots with fixed
supplied IDs. Observed output:

```text
2 players; briefing; tick=0; elapsed=0ms
  Crew 1: pilot
  Crew 2: engineer, shields
3 players; briefing; tick=0; elapsed=0ms
  Crew 1: pilot
  Crew 2: engineer
  Crew 3: shields
Constructed both snapshots without server/Android/environment configuration.
```

The same script passed with the clean wheel environment's Python and `-I`.
The portable construction example is in [GAME_STATE.md](GAME_STATE.md#implemented-python-api).
No web server, Android connection, RNG draw or simulation tick was needed.

## Android manual regression

After instrumented-test cleanup, explicitly installed the APK and launched it:

```powershell
adb -s emulator-5584 install -r android/app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5584 shell cmd uimode night no
adb -s emulator-5584 shell am start -W -n com.onejob.game/.MainActivity
adb -s emulator-5584 shell cmd uimode night yes
adb -s emulator-5584 shell am force-stop com.onejob.game
adb -s emulator-5584 shell am start -W -n com.onejob.game/.MainActivity
```

Install reported `Success`; both launches reported `Status: ok`, and `MainActivity`
was the resumed activity. Light/dark screenshots were visually inspected: readable
foundation text, correct system insets, and no functional create/join controls.
The first direct launch after instrumentation found no installed activity; explicit
reinstallation after the runner's cleanup resolved it without an Android change.
The validation emulator was shut down after the checks; its read-only session
did not save a snapshot or change the original AVD's app data.

Ignored local evidence: `artifacts/phase-01/backend-checks.log`,
`android-smoke.log`, `placeholder-light.png`, `placeholder-dark.png`, and
`inspect_domain.py`. Android's JUnit XML/HTML and lint report remain under ignored
`android/app/build/`. No raw gameplay/private projections exist or were captured.

## Decisions, warnings and remaining limits

The implementation follows ADR-002 and the existing ownership/privacy decisions;
no significant architecture deviation or wire-contract change was needed. Explicit
UUID-backed IDs, positive round-local emergency IDs, frozen records, copied
collections and a limited root export surface are documented implementation
choices. Room connectivity/readiness and the lobby stage remain application data.

No required gate remains blocked. The existing non-failing warnings remain:
one Starlette HTTPX TestClient deprecation and five Android lint warnings
(`OldTargetApi`, `AndroidGradlePluginVersion`, `GradleDependency`,
`DataExtractionRules`, `MissingApplicationIcon`). No warning was suppressed.
uv fell back to file copies across drives; installation succeeded.

Coverage is Windows and one API 37 emulator. Physical devices/API 26 and other
operating systems were not tested. Phase 01 defines data and constructor
invariants only: no engine/ticks, action execution, seeded ownership selection,
emergency scheduler/resolvers, rooms, WebSockets, projections or Android gameplay
were implemented. Dynamic rules and reachability remain for their selected phases.
