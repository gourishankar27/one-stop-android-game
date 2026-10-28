# One Job development plan

This is the **only development progress ledger**. Phase files define scope and
completion gates; documents define contracts. A checked box requires observed
evidence for every required gate, including manual gates where specified.

## Current state — 2026-10-28

- Current phase: **03 — Server Foundation, complete**.
- Completed phases: **00, 01, 02, 03**. Next eligible phase: **04**, awaiting explicit instruction.
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
| [ ] | [04 — Room and Lobby System](phase-04-room-and-lobby.md) | 03 | Membership/host/ready/credential services |
| [ ] | [05 — Android Foundation](phase-05-android-foundation.md) | 00; default after 04 | Navigation/state boundaries |
| [ ] | [06 — Android Networking](phase-06-android-networking.md) | 03, 04, 05 | Repository and typed socket |
| [ ] | [07 — Lobby UI](phase-07-lobby-ui.md) | 04, 06 | Real multi-phone lobby |
| [ ] | [08 — Role System](phase-08-role-system.md) | 02, 07 | Private station ownership/briefing |
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

After Phase 02 is complete, the next explicit command is:

```text
Implement plans/phase-03-server-foundation.md. Follow AGENTS.md and implement only this phase. Verify dependencies, run the required checks, update plans/plans.md only if all completion criteria are met, report the handoff, and stop.
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
| Toolchain and device coverage | Windows foundation checks and one API 37 emulator verified; physical phones/API 26 and other operating systems remain untested |
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
