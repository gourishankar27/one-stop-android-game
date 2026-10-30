# Audio, haptics and presentation validation

Observed 2026-10-29 (America/Phoenix). Phase 13 began with the uncommitted Phase 12
implementation and unrelated `plans/START_HERE.md` edit; both were preserved.
The user explicitly selected Phase 13 while physical-phone testing remains
deferred. Phase 10's human and Phase 11/12's physical-device gates remain open.
ADR-022 records proceeding with this scope/dependency exception, without claiming
the required current-phone baseline or group listening check passed.

## Baseline and delivered boundary

Before adding effects, reviewed the historical real-phone Phase 09 accepted-action
screenshot/evidence and launched the existing Phase 12 APK on an owned emulator.
Text feedback/readability existed; role identity was a plain label and there were
no feedback settings. The first emulator install was attempted before boot
completed; after `sys.boot_completed=1`, installation and launch passed. Historical
phone evidence is not a current Phase 13 physical-phone assessment.

The implementation adds optional local FeedbackPreferences with sound/haptics off
and reduced motion on by default. Exactly three private booleans persist, without
credentials, room/round state or private projections. Settings are reachable
during a session, remain open across server updates and never issue game commands.

One application-owned controller consumes authoritative public timing/warning
snapshots and validated correlated action receipts. The pure mapper deduplicates
round/emergency/countdown/action identity, retains at most 16 rounds and establishes
a silent baseline for initial/recovery/paused/background snapshots. Muted/hidden
events are consumed without later replay. A replacement activity keeps mapper
history but replaces/closes the platform sink; an old owner cannot detach it.

One SoundPool stream, nonlooping generated 55–120ms tones, 350ms global spacing,
1200ms urgency spacing and at most three cues per five seconds bound output.
There is no queued catch-up sound, delayed sample/focus playback or audio service.
The activity must be resumed/focused; settings and visibility/focus loss stop
sound and suppress future cues. Brief system haptic pulses may finish normally;
no new pulse is scheduled after suppression. Ringer/focus/system haptic policy
is respected. No vibration permission was added.

Owned roles now have P/E/S monograms, explicit text and light/dark tints with
contrast ratios Pilot 11.13, Engineer 9.89 and Shields 11.59. Decorative letters
are omitted from accessibility speech; role labels/screen titles are headings.
Body text scales from 18sp/26sp; slider naming and polite warning/action-result
semantics improve accessibility without announcing private deadlines every tick.
Reduced motion uses instant navigation; optional fades are 120ms/90ms. No flashes,
continuous animation, external art or final marketing design was added.

No server/domain/rule/balance, wire DTO, dependency pin, TV/casting or Phase 14
fault-matrix change was made. Existing Phase 12 behavior remains included.

## Toolchains and dependencies

| Check | Observed |
| --- | --- |
| `python --version` | Launcher 3.14.0 |
| Backend interpreter | Python 3.12.10 |
| `uv --version` | 0.13.6 |
| `java -version` | Temurin 17.0.18+8 |
| `gradlew.bat --version` from android/ | Gradle 8.13, Java 17 launcher and Temurin daemon criteria |
| SDK source.properties | Platform 36 revision 2; Build Tools 35.0.0 installed |
| Existing build pins | AGP 8.13.2, Kotlin/Compose compiler 2.2.21, Compose BOM 2025.10.01 |
| `uv sync --locked --extra dev` | 31 packages resolved/checked; lock unchanged |
| `:app:dependencyInsight --configuration debugRuntimeClasspath --dependency core-ktx` | Existing Core KTX 1.15.0 reused; no new dependency |

Commands sourced the existing ignored `artifacts/foundation/environment.ps1`.
Backend sync/run used `artifacts/phase04/uv-cache`; package build used the normal
local uv cache. No local path was added to committed setup. The Gradle version
check uses android/ so its project-specific Java 17 daemon criteria apply.

## Automated checks

From root, `python scripts/check_repository.py` passed all 19 phase briefs,
local links, package/XML and wrapper structure. `git diff --check` exited 0.
Existing Windows line-ending conversion warnings are nonblocking. Generated
build/test artifacts and local SDK settings stay ignored; the four named WAVs
are intentional source resources.

From `server/`:

```powershell
uv sync --locked --extra dev
uv run pytest -q --tb=short
uv run ruff check .
uv run ruff format --check .
uv run mypy src examples
uv build
uv run ruff check ../scripts
uv run ruff format --check ../scripts
uv run mypy ../scripts
```

**1,080 backend tests passed, no skips/failures.** Ruff passed for the 79 existing
server/example/test files; mypy passed for 33 source and 9 example files. All three
root helper scripts passed lint/format/mypy, including the new tone generator.
Both wheel and sdist built (`one_job_server-0.1.0-py3-none-any.whl` and `.tar.gz`).
The existing Starlette/httpx deprecation warning remains.

From `android/`:

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug `
  :app:testDebugUnitTest :app:compileReleaseKotlin `
  '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' '-PoneJobAllowDebugCleartext=true' --console=plain
```

Debug/test APK build, lint, JVM tests and release Kotlin compile passed.
**89 JVM tests passed, zero failures/errors/skips.** New tests cover quiet defaults,
three-boolean persistence, countdown/full-snapshot/action deduplication, simultaneous
warning priority, rate limits/drop-without-replay, recovery/visibility/settings
suppression, activity-owner replacement, muted events, 100 rounds with bounded
history and one-shot correlated repository receipts. Existing networking, private
controls, lifecycle and display tests continue passing.

Final lint: **0 errors, 14 retained warnings** (tool/dependency/target update hints,
opt-in debug cleartext, backup metadata and missing icon). An intermediate KTX
suggestion was fixed using the already-resolved dependency; no warning is suppressed.

With one default seeded local server, restricted to owned emulators:

```powershell
$env:ANDROID_SERIAL = 'emulator-5586,emulator-5588,emulator-5590'
.\gradlew.bat :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:compileReleaseKotlin `
  :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' `
  '-PoneJobAllowDebugCleartext=true' `
  '-Pandroid.testInstrumentationRunnerArguments.oneJobLiveServer=true' --console=plain
```

**35 tests on each API 37/Android 17 emulator passed (105 executions), zero
skips/failures.** This includes both opt-in real-server tests, settings labels/
48dp targets/local persistence, essential warning text with effects off, role
heading/text semantics and native decoding of all four packaged WAVs without
starting playback. No physical phone was selected.

The four new instrumentation cases then passed again at font scale 2.0 in dark
mode (**4/4, zero skips/failures; 109 total observed executions**):

```powershell
$env:ANDROID_SERIAL = 'emulator-5586'
.\gradlew.bat :app:connectedDebugAndroidTest '-PoneJobDebugWsUrl=ws://10.0.2.2:8765/ws' `
  '-PoneJobAllowDebugCleartext=true' `
  '-Pandroid.testInstrumentationRunnerArguments.class=com.onejob.game.FeedbackSettingsTest' --console=plain
```

The new settings test explicitly scrolls to toggles at large text sizes. The full
105-execution count summary/log remain in ignored `artifacts/phase13/`; the latest
Gradle device report contains the separate four-case large/dark run.

## Generated assets and rights

`python scripts/generate_feedback_audio.py` generated four original simple sine
tones. Native Android decoding passed on all three devices and in the large/dark
rerun. A separate WAV inspection verified mono PCM16, 44,100Hz, duration at most
120ms and source peak at most 0.3; durations/peaks/SHA-256 are recorded locally in
`artifacts/phase13/audio-validation.json`. Contrast was calculated from sRGB
luminance for all three light/dark tint pairs. See
[ASSET_ATTRIBUTION.md](ASSET_ATTRIBUTION.md) for source/provenance and reproduction.
No third-party sample/art/font, license grant or ownership assignment was added.

## Observed emulator UI

The final debug APK was installed explicitly after instrumentation. Three owned
emulators used ordinary app UI; all sound outputs were muted by the emulator
launch option and vibration perception was not assessed.

The manual driver toggled preferences, force-stopped/relaunched the app and
observed their persisted values. One device then used font scale 2.0 in a live
three-controller room. Own-role labels/tints and controls were reachable by
scrolling; screenshots of the large Engineer identity/private text were visually
inspected. Real low-power rejection and raised-output accepted Pilot evade stayed
visible as text. A short Home/background/resume restored current server time
(58 seconds before, 53 after). Settings were changed during the live room without
leaving membership; an essential public warning remained visible with effects off.
All memberships were left. Follow-up UI checks restored quiet/reduced-motion
defaults and inspected exactly three boolean preference keys on every emulator.

The local driver initially assumed unchanged defaults always create an XML file.
That cleanup assertion failed on the untouched-default device; no app failure
occurred. The check now permits implicit defaults, and the follow-up explicitly
changed/restored a toggle and verified the resulting three-boolean files. Earlier
live UI assertions had already passed; the full flow is not presented as a single
uninterrupted successful script run.

The included local harness was used as follows:

```powershell
uv run --offline python examples/emergency_harness.py --seed 71 --profile default --host 127.0.0.1
# Default profile for the full connected suite, then stopped/restarted before UI admission:
uv run --offline python examples/emergency_harness.py --seed 71 --profile verification --host 127.0.0.1
```

The existing verification profile gives 120-second UI windows/lower damage and
is documented in EMERGENCY_VALIDATION.md. It is not a production balance change
or human playtest. Normal production defaults were retained for automated live
networking. Large-text/light role and dark settings screenshots are local only.

TalkBack is installed on the emulator. An activation attempt set its service
settings, but TalkBack's permission-request screen took foreground before app
traversal could be checked. The app-only driver stopped, the original null/0
accessibility settings were restored and the trial TalkBack app was stopped.
No permission was granted. This is **not** a TalkBack traversal/spoken-feedback
pass; Compose semantics tests are separate evidence.

After checks, all test memberships were left/closed, original font/night and
accessibility settings were restored, and the owned server was stopped with no
listener on port 8765. All three owned emulator launchers exited and their serials
were absent from ADB. No physical phone or pre-existing external service was used
or stopped.

## Remaining gates and handoff

Current physical-phone readability/input review, real sound/haptic perception,
TalkBack labels/traversal with spoken feedback, and a short friends-in-the-room
round confirming voices remain audible are unrun. Repeat with sound/haptics off,
larger text and resume/reconnect before closing that manual gate. Emulator native
decoding, screenshots, semantics and fake-sink tests cannot establish audibility,
vibration quality, spoken usability or absence of a perceived alarm storm.

`plans/plans.md` remains unchanged this phase (initial/final SHA-256 match), and
Phase 13 stays unchecked. Earlier deferred gates remain open. No later phase was
started. Phase 14 must retest feedback/lifecycle interaction when explicitly
selected; this work does not complete its resilience or Phase 15 playtesting.
