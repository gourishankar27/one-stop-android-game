# Foundation validation — 2026-10-27

This record distinguishes observed checks from pending local checks. Phase 00
remains open in plans/plans.md until all required gates are verified.

## Observed environment

Python 3.12.14 and OpenJDK 17.0.20 are available. No Android SDK, Android Studio,
emulator or attached Android device is configured in this environment. Dependencies
were resolved into server/uv.lock and installed in an ignored local environment.

## Executed checks

| Check | Observed result |
| --- | --- |
| `uv sync --locked --extra dev` in server/ | Passed; package installed successfully |
| `python scripts/dev.py check-server` | Passed: 2 pytest tests, Ruff lint/format and strict mypy |
| `uv build` in server/ | Passed; source distribution and wheel built successfully |
| `python scripts/check_repository.py` | Passed; 19 briefs, local links, packaging/XML and wrapper structure |
| Ruff format/lint and mypy on `scripts/` | Passed; both developer helpers checked |
| Live Uvicorn process + HTTP `GET /health` | Passed; real local HTTP 200 and expected JSON, followed by clean shutdown |
| Wrapper JAR published SHA-256 verification | Passed; official digest matches bundled JAR |
| Android wrapper build/lint/unit-test command | Blocked during Gradle distribution download: `java.net.SocketException: Network is unreachable` |
| Retry with environment-provided Java proxy settings | Same network error; compilation never began |
| Android instrumented smoke test / launch | Not run; no SDK/device/emulator available |

The two Python tests verify the health response and the absence of premature
gameplay transport. The initial test run reported an upstream Starlette warning
about HTTPX TestClient deprecation; it did not fail. No warning is suppressed.
Repository/XML/wrapper inspection cannot establish that Kotlin compiled.

## Required local finish

At repository root on Windows:

```powershell
python scripts/check_repository.py
python scripts/dev.py setup-server
python scripts/dev.py check-server
cd server
uv build
cd ..\android
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
.\gradlew.bat :app:connectedDebugAndroidTest
```

Use JDK 17, Platform 36, Build Tools 35.0.0 and an API 26+ emulator/device. The
unit-test task may be NO-SOURCE because no Android stateful logic exists yet;
record it as such. Run the app through Android Studio and inspect the foundation
screen in light/dark themes. Do not count a blocked download as a code failure
or a successful build. Update this record with exact local evidence.

Backend manual check: run `python scripts/dev.py run-server`, then request
`http://127.0.0.1:8000/health` in a second terminal. This validates live HTTP
serving separately from the in-process tests.

No phase beyond the foundation is implemented. No gameplay, live multiplayer,
Android build, fun/balance or external deployment is claimed by this record.
