# One Job development plan

This is the **only development progress ledger**. Phase files define scope and
completion gates; documents define contracts. A checked box requires observed
evidence for every required gate, including manual gates where specified.

## Current state — 2026-10-28

- Current phase: **08 — Role System, complete**.
- Completed phases: **00, 01, 02, 03, 04, 05, 06, 07, 08**. Next eligible phase: **09**, awaiting explicit instruction.
- Delivered foundation: Python health service/package/tests, Compose placeholder,
  wrapper/tooling, architecture/game/protocol documents and all phase briefs.
- Phase 00 evidence: repository checker; Python 3.12 locked setup, 2 tests,
  Ruff/mypy and package build; Android debug build/lint; successful Studio sync
  and emulator launch in both themes; included instrumented smoke test passed.
- Foundation smoke-test fix: explicit Espresso 3.7.0 replaces the incompatible
  transitive 3.5.0 in tests only (ADR-012). No gameplay implementation was added.
- Delivered Phase 01: frozen validated config, participants and explicit station
  ownership, nine action shapes, ship/round/emergency/result records and a limited
  pure Python package API, used by the Phase 02 engine.
- Phase 01 evidence: 487 backend tests passed (485 domain + 2 health); Ruff/mypy
  and package build passed; clean wheel works without web dependencies; manual
  2/3-player snapshot construction passed. Android build/lint and the unchanged
  instrumented smoke test passed; placeholder launch checked in both themes.
- Delivered Phase 02: synchronous fixed-step baseline, power/lane/coolant actions,
  heat/critical damage, cooldowns, immutable snapshots, accepted action order,
  terminal results/events and three deterministic replay fixtures.
- Phase 02 evidence: 557 backend tests passed; Ruff lint/format, strict mypy,
  repository and package checks passed. Fixed-seed manual loops and clean wheel
  runs reproduced victory at tick 900 and heat defeat at tick 549.
- Remaining Phase 02 gates: none. Exact commands and scoped limitations:
  [ENGINE_VALIDATION.md](../docs/ENGINE_VALIDATION.md). No Android or transport
  changes were made or claimed. Prior model/device evidence:
  [DOMAIN_MODEL_VALIDATION.md](../docs/DOMAIN_MODEL_VALIDATION.md).
  Original foundation evidence: [FOUNDATION_VALIDATION.md](../docs/FOUNDATION_VALIDATION.md).
- Session prompts: [START_HERE.md](START_HERE.md).
- Delivered Phase 03: strict v1 `/ws` ping/pong/errors, future-command gates,
  injected admission/send deadlines, bounded/coalescing outbox, connection
  generations, lifecycle cleanup/redacted logs and a fixture-only engine adapter.
- Phase 03 evidence: 708 backend tests passed; Ruff lint/format, strict mypy,
  repository/helper checks and package build passed. Extracted-wheel health/pong
  passed. A live local client verified health, pong, future/unknown errors,
  malformed JSON/1007, unsupported version/1002 and oversize/1009; clean shutdown
  was observed. Ten targeted cleanup repetitions passed before final hardening.
- Remaining Phase 03 gates: none. Exact commands, warnings and scoped limitations:
  [SERVER_FOUNDATION_VALIDATION.md](../docs/SERVER_FOUNDATION_VALIDATION.md).
  Android toolchain presence was verified; Android builds/device checks were not
  rerun in this backend-only phase. No rooms, credentials, live game tasks or
  Android networking were added. Prior uncommitted Phase 02 work was preserved.
- Delivered Phase 04: authoritative room owners, secure codes/UUID memberships,
  private stable credentials, create/join/ready/leave/state, generation-fenced
  resume, bounded terminal replay, disconnect grace, host transfer and idle expiry.
  Start checks eligibility but remains explicitly unavailable; no game is launched.
- Phase 04 evidence: 851 backend tests passed; locked setup, Ruff lint/format,
  strict mypy, repository/helper checks and wheel/sdist passed. Final extracted
  wheel admission/lobby/leave/cleanup passed. Three live Python sockets agreed on
  roster/revisions through joins, readiness, unavailable start, leave, resume and
  host transfer; credential-free logs and clean server shutdown were observed.
- Remaining Phase 04 gates: none. Exact commands, policy decisions and scoped
  limitations: [LOBBY_VALIDATION.md](../docs/LOBBY_VALIDATION.md). Dependency pins,
  pure engine and Android sources were preserved. Android builds/device checks
  were not rerun for this backend-only phase. No later phase was started.
- Delivered Phase 05: single-Activity navigation shell, explicit Home/Create/Join/
  Lobby/Role/Gameplay/Results routes, constructor wiring/unavailable repository,
  local draft ViewModels, immutable/lifecycle-aware StateFlow and nonsecret saved
  inputs. Future flows are truthful previews; no Android transport was added.
- Phase 05 evidence: Android debug build/lint passed; 8 JVM and 5 instrumented
  tests passed on the API 37 emulator. All routes/Back, actual rotation and font
  scale 2.0 were checked; draft inputs survived and controls remained reachable.
  Repository checks and backend regressions passed (851 tests, Ruff, strict mypy).
  Pinned Gradle/AGP/Kotlin/Compose/SDK baseline and prior Phase 04 work were preserved.
- Remaining Phase 05 gates: none. Exact commands, 11 lint warnings, device scope
  and screenshots: [ANDROID_FOUNDATION_VALIDATION.md](../docs/ANDROID_FOUNDATION_VALIDATION.md).
  Emulator settings were restored and the verification emulator stopped. No
  networking, live lobby/gameplay, assets or Phase 06 behavior was implemented.
- Delivered Phase 06: typed OkHttp/serialization transport, one application-owned
  repository/socket, private endpoint-bound memory credentials, correlated typed
  outcomes, five-second uncertainty and bounded resume/full-snapshot recovery.
  Debug endpoints require explicit configuration/cleartext opt-in; release requires
  WSS. A development connection/test-membership panel leaves the normal forms local.
- Phase 06 evidence: toolchains verified; repository checks, locked backend setup,
  852 tests, Ruff/format/mypy and package builds passed. Android debug build/lint,
  30 JVM tests, release Kotlin/manifest checks and 8 instrumented tests on each of
  the API 37 emulator and API 36 physical phone passed, including real LAN
  ping/create/join/resume/leave. Both UIs showed bounded recovery and safe
  server-unavailable feedback after server shutdown. Sessions/server/emulator closed.
- Remaining Phase 06 gates: none. Exact commands, 14 lint warnings, the existing
  TestClient warning and an observed phone background LOW_MEMORY reclamation are
  recorded in [ANDROID_NETWORKING_VALIDATION.md](../docs/ANDROID_NETWORKING_VALIDATION.md).
  Credentials intentionally do not survive process death; durable/background
  resilience remains Phase 14. No usable lobby UI, gameplay or Phase 07 work was added.
- Delivered Phase 07: real name/code submission, identity-gated lobby navigation,
  retained errors/explicit uncertain-attempt reset, ID-keyed roster/host/ready
  controls, server-hinted start, confirmed leave and expiry/recovery feedback.
  No role reveal, game start or gameplay was added; eligible Start stays explicit
  about feature unavailability. Prior uncommitted Phase 06 work was preserved.
- Phase 07 evidence: locked backend setup, 852 tests, Ruff/format/mypy and
  package builds passed. Android build/lint (0 errors, 14 retained warnings),
  43 JVM tests, release compilation and 12 instrumented tests on each of one
  physical phone and two emulators passed. Real two-client code/roster/readiness/
  gated Start, duplicate-name admission, emulator recovery/expiry and font scale
  2.0 were observed. The user explicitly selected the phone-plus-two-emulator mix.
  After the phone was ready again, a fresh three-client session agreed on code,
  three distinct connected/ready IDs and host-only Start. Eligible Start stayed
  unavailable. Confirmed phone leave/rejoin removed the old ID, restored exactly
  three current members and reset readiness on every client.
- Remaining Phase 07 gates: none. Exact commands, device mix, retained warnings,
  recovery/expiry and screenshot evidence are in
  [LOBBY_UI_VALIDATION.md](../docs/LOBBY_UI_VALIDATION.md). All test memberships were
  left, app-only logs showed no crash/secret-frame markers, and the server and
  both verification emulators were stopped. Phase 08 was not started.
- Delivered Phase 08: deterministic seeded two-/three-player assignment, immutable
  station metadata, frozen round context inside the existing room owner, owned
  role projections/replay, authenticated nine-action ownership and private
  Android reveal/read/acknowledgement with Engineer/Shields switching. The
  60-second budget suspends for disconnect grace; leave/grace/briefing expiry
  abort. All acknowledged briefings hold at tick zero without gameplay.
- Phase 08 evidence: verified toolchains and locked dependencies; repository
  checks, 897 backend tests, Ruff/format/strict mypy and wheel/sdist passed.
  Android debug build/lint (0 errors, 14 retained warnings), release compilation,
  52 JVM tests and 15 instrumented tests on each of the physical phone and two
  emulators passed, including real private-state recovery. Two-/three-controller
  socket captures passed owned-only field allowlists and non-host/wrong-role
  rejection. Actual two-client UI required both Engineer/Shields reads before
  acknowledgement and held after all acknowledged. Three-client UI showed one
  distinct owned station each; withholding acknowledgements produced an explicit
  real 60-second timeout abort on all three screens.
- Remaining Phase 08 gates: none. Exact commands, resolved verification issues,
  the unobserved radio-pause attempt, warnings and scoped limitations are in
  [ROLE_SYSTEM_VALIDATION.md](../docs/ROLE_SYSTEM_VALIDATION.md); ADR-017 records
  the owned briefing/hold policy and approved device mix. Earlier Phase 06/07
  changes were preserved. All memberships were left, emulator settings restored,
  app-scoped logs checked, and server/emulators stopped. The phone has the final
  APK at Home. Phase 09 was not started.

## Product goal and MVP

Friends in the same room use Android phones to operate different spaceship
stations and survive together. The server is authoritative. Players talk aloud.
The initial target is 2–3 players, three stations and 60–120-second rounds.
Three players get one station each; two players split Pilot / Engineer+Shields.

MVP gameplay: rooms, names/codes, host/ready lobby, seeded roles, briefing/countdown,
private station panels, authoritative spaceship rules, three emergencies,
victory/defeat/abort results, rematch and return to lobby. This reaches Phase 11.
The full MVP also needs Phase 14 recovery checks and Phase 15 real group playtests.
Public display (12), audio/presentation polish (13), easier LAN discovery (16)
and a second scenario (17) do not block that definition.

## Architecture summary

Python 3.12+/FastAPI/Pydantic/WebSockets, in-memory rooms and one worker. The pure
Python engine owns rules, seeded randomness and fixed 100ms ticks. The application
serializes commands and schedules ticks; transport only validates/maps/messages.
Per-player allowlisted projections protect private station information.
Android uses Kotlin/Compose/Material 3, ViewModel/StateFlow/coroutines, a repository
and a WebSocket data source. The phone host is a room permission, not authority.

## Phase roadmap and dependencies

Default sequence is 00 through 11, then 14 and 15 for the MVP. A user can select
another ready phase explicitly; never execute more than the selected phase.

| Status | Phase / brief | Prerequisites | Milestone |
| --- | --- | --- | --- |
| [x] | [00 — Repository Foundation](phase-00-repository-foundation.md) | None | Local projects and verification complete |
| [x] | [01 — Game Domain Model](phase-01-game-domain-model.md) | 00 | Pure validated types |
| [x] | [02 — Core Game Engine](phase-02-game-engine.md) | 01 | Deterministic baseline simulation |
| [x] | [03 — Server Foundation](phase-03-server-foundation.md) | 02 | Typed WS/lifespan adapter |
| [x] | [04 — Room and Lobby System](phase-04-room-and-lobby.md) | 03 | Membership/host/ready/credential services |
| [x] | [05 — Android Foundation](phase-05-android-foundation.md) | 00; default after 04 | Navigation/state boundaries |
| [x] | [06 — Android Networking](phase-06-android-networking.md) | 03, 04, 05 | Repository and typed socket |
| [x] | [07 — Lobby UI](phase-07-lobby-ui.md) | 04, 06 | Real multi-phone lobby |
| [x] | [08 — Role System](phase-08-role-system.md) | 02, 07 | Private station ownership/briefing |
| [ ] | [09 — Core Spaceship Gameplay](phase-09-core-spaceship-gameplay.md) | 02, 06, 08 | Running cooperative controls |
| [ ] | [10 — Emergency System](phase-10-emergency-system.md) | 09 | Seeded coordination emergencies |
| [ ] | [11 — Round Lifecycle](phase-11-round-lifecycle.md) | 10 | Complete gameplay loop |
| [ ] | [12 — Public Display](phase-12-public-display.md) | 11; optional | Extra Android observer |
| [ ] | [13 — Audio, Haptics and Presentation](phase-13-audio-haptics-polish.md) | 11; optional; include 12 only if present | Accessible local feedback |
| [ ] | [14 — Resilience and Reconnection](phase-14-resilience-and-reconnection.md) | 11; include optional features if present | Fault recovery validated |
| [ ] | [15 — Playtesting and Balancing](phase-15-playtesting-balancing.md) | 14 | Actual 2/3-player evidence; full MVP |
| [ ] | [16 — Local Network Mode](phase-16-local-networking.md) | 15; optional | Evidence-based LAN decision/convenience |
| [ ] | [17 — Second Scenario](phase-17-second-scenario.md) | 15 and evidence; optional | One submarine scenario |
| [ ] | [18 — Release Foundation](phase-18-release-foundation.md) | 15; optional features verified if included | Reviewable external-test preparation |

There is no dependency from 14 to 12/13 or from 18 to 16/17. If an optional
phase is deferred, leave it unchecked and state the deferral here. Phase 16 can
close with a documented investigated/deferred outcome if evidence rejects local
mode; that is not an implemented-feature claim. Phase 17 begins with a mini-spec
because a second scenario's mechanics should use actual spaceship findings.

## Integration ownership across phases

- Phase 02 runs pure engine start/tick/end tests with supplied assignments.
- Phase 03 adapts the engine and implements transport, not rooms.
- Phase 04 validates start eligibility but returns `feature_unavailable` for launch.
- Phase 07 makes a real lobby usable; it must not fake a working round start.
- Phase 08 enables start → role briefing; it holds after acknowledgement until
  Phase 09 adds running orchestration. Phase 11 adds the final timed countdown.
- Phase 09 completes control mechanics and live ticking; Phase 10 adds emergencies;
  Phase 11 finishes results/rematch/navigation and tests repeated full cycles.
- Basic credentials, fencing and safe disconnect behavior appear as needed early;
  Phase 14 hardens the full real-device fault matrix rather than replacing them.

## Session workflow

Read AGENTS.md, this ledger, selected phase, relevant docs/code; inspect git status
and dependencies; implement only that scope; run relevant checks and manual steps;
update docs and decisions; mark complete only with evidence; report a concise
handoff; stop. If blocked, leave the checkbox open and record exactly which gate
remains. Do not turn an unavailable emulator or unavailable humans into a pass.

After Phase 08 is complete, the next explicit command is:

```text
Implement plans/phase-09-core-spaceship-gameplay.md. Follow AGENTS.md and implement only this phase. Verify dependencies, run the required checks, update plans/plans.md only if all completion criteria are met, report the handoff, and stop.
```

## Deferred work

No database, accounts, chat, monetization, matchmaking, analytics service, iOS,
desktop/web client, TV/casting or scenario DSL. Other spaceship roles and the
navigation-malfunction/independent-shortage events are future scope. More than
three controllers needs a new role/load design; observer devices do not count.
External deployment, signing keys and publishing require separate user action.
No open-source license has been chosen by the owner.

## Risks and unresolved questions

| Risk / question | Initial decision / validation point |
| --- | --- |
| Engineer+Shields workload with two people | Keep stations explicit; test in 15 before claiming it works socially |
| Pilot idle time / difficulty | Three seeded emergencies, provisional defaults; actual observations in 15 |
| Private data leaks | Separate allowlisted projections and absence tests from 08 onward; observer tests in 12 |
| Time/action nondeterminism | Fixed ticks, one room owner, seeded RNG, versioned action traces; tests in 02/09/10 |
| Outages or duplicate sockets | Credential/generation foundation in 04/06; full matrix in 14 |
| In-memory process loss / multi-worker routing | Single process; restart loses rooms; scale only with a later ownership decision |
| Phone networking and Windows setup | Debug endpoint evidence in 06; party discovery decision in 16 |
| Hosting choice for external friends | Unselected; WSS operating guide in 18, no service provisioned now |
| Toolchain and device coverage | Windows, API 37 emulator and one API 36 physical phone verified; API 26, other phones and other operating systems remain untested |
| License and distribution scope | Owner chooses before public source distribution; release review in 18 |

## Handoff history

2026-10-27: Foundation source/documents/plans created. Backend and repository
checks are recorded in FOUNDATION_VALIDATION.md. Phase 00 remains open for
Android validation. No domain/gameplay, WebSocket room behavior, deployment or
later phase has been implemented.

2026-10-27 (local verification): Phase 00 completed after all required gates
passed. Python 3.12.10/uv, JDK 17, SDK Platform 36/Build Tools 35.0.0 verified.
Backend: 2 tests, Ruff/mypy and wheel/sdist passed. Android build/lint passed
(0 errors, 5 warnings; JVM tests NO-SOURCE); the unchanged Compose smoke passed
after the test-only Espresso fix. Studio sync/Run and both system themes were
verified on the API 37 emulator. IDE-generated JDK 17 daemon criteria were
preserved and included in final checks; unrelated editor settings were left
untouched. Exact evidence and limitations are in FOUNDATION_VALIDATION.md.
Phase 01 is recommended but was not started.

2026-10-27 (domain model): Phase 01 completed after all required gates passed.
Implemented pure frozen dataclasses/enums, supplied typed IDs, config validation,
explicit 2/3-player ownership, typed actions and internally consistent immutable
snapshots/results/emergencies. 487 tests passed; Ruff lint/format, strict mypy,
repository checker and wheel/sdist passed. The clean wheel constructed both
rosters without web dependencies; isolated import also passed with an empty
environment. Android build/lint and the original smoke passed, and both themes
were inspected after emulator launch. Existing warnings and single-emulator
coverage remain documented in DOMAIN_MODEL_VALIDATION.md. No engine/scheduler,
room service, wire DTO or Android gameplay was added. Phase 02 was not started.

2026-10-27 (core engine): Phase 02 completed after its required gates passed.
Added a pure synchronous engine with caller-supplied IDs/assignments and private
seeded RNG, three supported actions, fixed 100ms heat/damage/cooldown/timer steps,
atomic rejections and stable terminal results with one event. Accepted commands
record boundary tick/order; replay fixtures compare every snapshot and accepted
trace. 557 backend tests, Ruff lint/format, strict mypy, repository checks and
wheel/sdist passed. Manual and clean-wheel loops reproduced tick-900 victory and
tick-549 heat defeat without wall-clock waits. Engine API, tick order and exact
evidence are in GAME_STATE.md, ARCHITECTURE.md and ENGINE_VALIDATION.md. Remaining
controls, emergencies, room/transport integration and Android gameplay remain
future work. Phase 03 was not started.

2026-10-28 (room/lobby): Phase 04 completed after all required checks and live
manual gates passed. Per-room owners serialize membership and updates; secure
admission/resume credentials remain private, generation checks fence obsolete
sockets, and bounded replay preserves terminal replies without plaintext token
storage. Ready/reset/host/expiry policies and unavailable start match the current
v1 contract (ADR-014). 851 tests, Ruff, strict mypy, repository/helper checks and
package builds passed; the extracted wheel passed admission/leave/cleanup. A live
three-client check agreed on roster/revisions through join/ready/leave/resume/host
transfer; the server shut down cleanly. Exact evidence is in LOBBY_VALIDATION.md.
The existing TestClient warning remains. Android/gameplay were not implemented
or revalidated in this phase. Phase 05 is recommended and was not started.

2026-10-28 (Android foundation): Phase 05 completed after build/lint, 8 JVM tests,
5 device tests and manual navigation/rotation/font gates passed. The shell has
seven explicit destinations, constructor-injected unavailable repository state,
local draft validation and saved nonsecret form inputs. Device recreation and
physical rotation retained the Join draft. System font scale 2.0 stayed readable
and scrollable; original settings were restored and the read-only emulator stopped.
Repository/backend checks also passed, including 851 tests. Exact evidence and
the retained 11 lint warnings are in ANDROID_FOUNDATION_VALIDATION.md. Prior
uncommitted Phase 04 work was preserved. No network call, fake working room or
Android game authority was added. Phase 06 is recommended and was not started.

2026-10-28 (Android networking): Phase 06 completed after every required gate
passed. Added the typed transport/repository, private in-memory credentials,
bounded uncertain requests and 1/2/4/8-second resume with fresh snapshots. Shared
fixtures agree in Python and Kotlin. Repository/backend/static/package checks
passed (852 tests); Android build/lint, 30 JVM tests, release policy/compilation
and 8 instrumented tests on each device passed. Emulator then physical-phone LAN
checks exercised ping/create/join, readiness, gated start, loss/resume and leave.
Server-stop UI feedback was inspected on both devices without a crash or secret
logs. Android later reclaimed the background phone process for low memory;
relaunch correctly required fresh admission. Exact evidence and limits are in
ANDROID_NETWORKING_VALIDATION.md and ADR-015. Normal room forms remain local;
no complete lobby UI or gameplay is claimed. Phase 07 is recommended and was
not started. Verification sessions/server/emulator were closed.

2026-10-28 (lobby UI): Phase 07 completed after automated and shared-client manual
gates passed. Forms submit typed normalized inputs, retain rejected inputs and
require explicit reset after uncertain admission. Admission identity drives lobby
navigation. The ID-keyed roster, host/you labels, local readiness, server-hinted
Start, confirmed leave and recovery/expiry feedback remain authoritative.
852 backend tests/static/package checks, repository checks, Android build/lint,
43 JVM tests and 12 instrumented tests on each of one phone and two emulators
passed. A final emulator rerun also passed after the offline-leave refinement.
The user-approved device mix verified both two- and three-client shared lobbies,
duplicate names, all-ready host Start's planned unavailable response, phone leave/
rejoin without stale IDs, network resume/expiry and large-font controls. Exact
evidence is in LOBBY_UI_VALIDATION.md and ADR-016. Existing Phase 06 changes were
preserved. Sessions/server/emulators were closed and settings restored. No roles,
round start or gameplay were added. Phase 08 is recommended and was not started.

2026-10-28 (role system): Phase 08 completed after automated and real-client gates
passed. The existing room task owns a frozen seeded briefing context; pure
assignment/metadata and engine ownership stay separate from transport. Targeted
owned projections and per-member replay give the host no additional private view.
Android reads each owned station explicitly, handles dual switching, waits for
server acknowledgement and stays in held briefing without ticks/countdown.
Timeout/leave/grace aborts are explicit. A deadline-crossing regression verifies
abort revision/broadcast even when acknowledgement triggers expiry. Repository
checks, 897 backend tests/static/package checks, Android build/lint/release,
52 JVM tests and 15 instrumented tests on each of three approved devices passed.
Two-/three-client private-frame allowlists, ownership rejection, real read/hold
and three-screen timeout abort passed. Evidence and limits are in
ROLE_SYSTEM_VALIDATION.md and ADR-017. Prior Phase 06/07 work was preserved;
memberships, server and verification emulators were closed and settings restored.
No gameplay or Phase 09 work was started. Phase 09 awaits an explicit instruction.
