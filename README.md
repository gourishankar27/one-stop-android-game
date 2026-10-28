# One Job

An Android multiplayer party game for friends in the same room. Each phone
controls different spaceship stations. Players communicate aloud to survive a
short round together.

> Everyone has one job. Everything goes wrong at the same time.

This repository contains the **initial foundation**, not a playable game.
Implemented: a packaged FastAPI service with `GET /health`, a Compose navigation
shell, developer checks, architecture documents and phase plans 00–18.
Phase 01 adds validated immutable Python domain values, including explicit
station ownership and action shapes. Phase 02 adds the synchronous baseline
engine for power, lane movement, coolant, heat/damage and round timing. Phase 03
adds typed `/ws` ping/pong/errors, bounded connection cleanup and a fixture engine
adapter. Phase 04 adds authoritative rooms/lobbies, admission/resume credentials,
readiness, host transfer and expiry. Phase 05 adds the Android shell, local
Create/Join drafts and explicit future-screen previews with retained input state.
Android networking, live socket gameplay, seeded assignment,
emergencies, remaining controls and gameplay screens are planned.
See [the progress ledger](plans/plans.md) for validation gates and next work.

## Layout

| Path | Contents |
| --- | --- |
| `AGENTS.md` | Durable instructions for Codex sessions |
| `docs/` | Product, rules, state, architecture, protocol, UX and test references |
| `plans/plans.md` | Phase progress, dependencies and deferred work |
| `plans/phase-*.md` | One implementation brief per phase |
| `server/` | Python 3.12+ package, pure engine, typed transport and backend tests |
| `android/` | Independent Gradle Kotlin DSL project; namespace `com.onejob.game` |
| `scripts/` | Cross-platform backend commands and repository consistency checks |

The [full repository tree](docs/REPOSITORY_TREE.md) lists all delivered source files.

The server will own all game rules and time. The pure Python engine will be
separate from FastAPI and sockets. Android will render server projections and
submit player intents. A room host can start a round but cannot own or override
authoritative state. Private station information is projected per recipient.

## Windows setup

Open the existing checkout in Codex. If starting from a source archive, extract
it to a short path such as `G:\Projects\one-job`; archives do not include git
history or installed dependencies. Run `git init` only if that extracted directory
is not already a repository. Do not copy another project's `.venv` or
`local.properties` into this project.

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Use Android Studio that supports AGP 8.13.2, JDK 17, Android SDK Platform 36 and
Build Tools 35.0.0. Versions are pinned deliberately; no automatic upgrade is
required. See [toolchain notes](docs/TOOLCHAIN.md).

From PowerShell at the repository root:

```powershell
python scripts/dev.py setup-server
python scripts/dev.py check-server
python scripts/dev.py run-server
```

The last command runs a development server on `127.0.0.1:8000`; stop with Ctrl+C.
In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
uv run --project server python server/examples/websocket_smoke.py
```

Expected JSON: `{"status":"ok","service":"one-job-server"}`.
No database, Docker, accounts or credentials are needed.

Open **`android/`**, not the repository root, in Android Studio. Select JDK 17
as the Gradle JDK, install the SDK components above and sync. Run the `app`
configuration on an Android 8.0+ device/emulator. The shell explains unavailable
online play and previews future screens; it does not connect to the backend yet.

```powershell
cd android
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
# With an emulator or device connected:
.\gradlew.bat :app:connectedDebugAndroidTest
```

On macOS/Linux, the Python commands are the same and the wrapper is `./gradlew`.
Gradle and dependency downloads need network access the first time. Local SDK
paths belong in ignored `android/local.properties` or `ANDROID_HOME`.
The terminal's `JAVA_HOME` and Android Studio's Gradle JDK are separate settings;
verify both select JDK 17 with `java -version` and `.\gradlew.bat --version`.

## Development

Run `python scripts/check_repository.py` from the root. Backend commands can also
be run directly from `server/`; see its [README](server/README.md).
Android lint is configured through AGP; Kotlin formatting follows `.editorconfig`
and official Kotlin style. A separate Kotlin formatter is not installed yet.

Read [AGENTS.md](AGENTS.md), [the master plan](plans/plans.md) and the selected
phase before editing. Each Codex session implements one phase and stops after
verification and handoff. Do not mark a phase complete while required checks
remain unverified. [docs/FOUNDATION_VALIDATION.md](docs/FOUNDATION_VALIDATION.md)
records actual foundation checks and environment limitations.

Choose the appropriate session prompt in [plans/START_HERE.md](plans/START_HERE.md)
using the current phase in the progress ledger.

## Documents

- [Product and MVP](docs/PRODUCT.md), [spaceship rules](docs/GAME_DESIGN.md)
- [Architecture](docs/ARCHITECTURE.md), [state and terminology](docs/GAME_STATE.md)
- [Network protocol](docs/NETWORK_PROTOCOL.md), [UI and navigation](docs/UI_UX.md)
- [Testing](docs/TESTING.md), [decisions](docs/DECISIONS.md)

No license is selected yet. Choose one before distributing the source publicly.
