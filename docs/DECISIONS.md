# Architecture decisions

Date records use the project decision date. Accepted design does not mean implementation already exists. Later decisions append new entries and mark superseded entries explicitly; do not erase the reasoning.

## ADR-001 — Authoritative Python server

Date: 2026-10-27

Status: Accepted

Context: Phones must agree on one outcome, and room hosting must not shift authority onto a phone.

Decision: Use Python 3.12+, FastAPI and a server-owned simulation. Host privileges are server-checked room permissions.

Alternatives considered: Peer-to-peer state; Android-hosted authoritative Kotlin engine.

Consequences: Clients submit intents and render accepted state. A reachable backend is required; local-host alternatives are evaluated only in Phase 16.

## ADR-002 — Pure synchronous game engine

Date: 2026-10-27

Status: Accepted

Context: Rules need direct deterministic tests without network timing or Android.

Decision: Use plain Python dataclasses/enums and synchronous methods in one_job/domain, with config and RNG seed inputs. Keep Pydantic/FastAPI/asyncio outside.

Alternatives considered: Rules in WebSocket handlers; Pydantic models throughout the engine.

Consequences: Transport mapping costs a small amount of explicit code, while engine tests can advance time instantly and run without a server.

## ADR-003 — Typed WebSocket messages

Date: 2026-10-27

Status: Accepted

Context: A short cooperative round needs duplex messages and understandable recovery behavior.

Decision: Use one versioned /ws connection per client, typed envelopes and discriminated payloads. Full snapshots initially; OkHttp/kotlinx.serialization on Android in Phase 06.

Alternatives considered: Polling HTTP; raw arbitrary dictionaries; premature binary protocol or Socket.IO.

Consequences: Both languages must share fixtures and compatibility tests. Explicit request correlation, backpressure and stale-session handling are necessary.

## ADR-004 — Recipient-specific allowlisted views

Date: 2026-10-27

Status: Accepted

Context: Different information is part of the game, and a host/display must not bypass it.

Decision: Construct public and owned-station projections on the server, field by field. Never broadcast full state for clients to hide.

Alternatives considered: One universal snapshot with UI-only hiding; encrypting fields that should simply be omitted.

Consequences: Projection/privacy tests are mandatory. Public observers can reuse the public projection later without receiving private instructions.

## ADR-005 — In-memory rooms and one server process

Date: 2026-10-27

Status: Accepted

Context: The MVP needs transient sessions, not accounts or durable history.

Decision: Use one registry owned by a single process, with expiry limits and no database. Restart loses rooms and credentials.

Alternatives considered: PostgreSQL/Redis from day one; multiple unrelated worker registries.

Consequences: No multi-worker deployment until shared ownership is designed. Development reload resets rooms; the client explains lost sessions.

## ADR-006 — Fixed ticks and versioned seeded replay

Date: 2026-10-27

Status: Accepted

Context: Timers, effects and random emergencies must be repeatable without real-time waits.

Decision: Use integer 100ms simulation ticks, private seeded RNG and ordered accepted actions. Record config/engine/Python version, seed and tick/order. Wall clocks belong to the room scheduler only.

Alternatives considered: Variable UI delta time; global random state; seed-only replay promises.

Consequences: Same-version semantic replay is testable. Catch-up is bounded and persistent scheduler lag aborts rather than silently changing rules.

## ADR-007 — Kotlin Compose client with manual wiring

Date: 2026-10-27

Status: Accepted

Context: The requested Android stack supports a small, testable presentation client.

Decision: Use Kotlin, Compose, Material 3, ViewModel, StateFlow and coroutines with repository/data-source separation. Begin with constructor injection and one Activity.

Alternatives considered: XML-first screens; game rules in ViewModels; an early DI framework/multi-module graph.

Consequences: Dependencies are added when behavior requires them. Networking never runs inside composables, and local UI cannot determine results.

## ADR-008 — Three stations with explicit two-player ownership

Date: 2026-10-27

Status: Provisional; validate in Phase 15

Context: The requested 2–3-player target has three initial stations and excludes AI players.

Decision: For three players assign one station each. For two assign Pilot to one player and Engineer+Shields to the other after seeded roster shuffle. Provide a station switch with urgent badges.

Alternatives considered: Drop a station; automatic unowned station; create a fourth combined role type.

Consequences: No AI or extra role is needed, but the two-station workload may be too high. Keep the initial assumption visible and revise only with recorded playtest evidence.

## ADR-009 — Bounded recovery and connection fencing

Date: 2026-10-27

Status: Accepted

Context: Outages and duplicated phone connections can otherwise create divergent actions or frozen hosts.

Decision: Use room-scoped opaque credentials, one current connection generation, full-state resume, a 30-second disconnect grace and paused active rounds. Never replay an unsent action queue.

Alternatives considered: Name-based reconnection; trusting a room code as identity; running missing stations indefinitely.

Consequences: A missed grace aborts gameplay. Expired/left members are removed and host transfers among remaining connected members, including results after abort. Credentials expire on leave/restart.

## ADR-010 — Foundation scope and honest completion gates

Date: 2026-10-27

Status: Accepted

Context: The request is a source/document foundation for later single-phase Codex sessions.

Decision: Create minimal executable health/Compose scaffolds now; do not implement engine/rooms. Leave Phase 00 unchecked until local Android build/launch gates run. Master plans.md is the sole progress ledger.

Alternatives considered: Documentation only without runnable scaffolds; silently implementing later features; marking unrun builds passed.

Consequences: The first local Codex session finishes existing Phase 00 verification. Phase 11 is the gameplay loop; 14 and 15 finish the MVP. Optional 12/13/16/17 do not block release preparation.

## ADR-011 — Pinned toolchain and delayed package boundaries

Date: 2026-10-27

Status: Accepted

Context: The repository should open normally on Windows without shipping caches or empty architecture layers.

Decision: Keep independent android/ and server/ projects, the official Gradle wrapper and a Python lockfile. Use the baseline in TOOLCHAIN.md. Add domain/application/protocol packages when their phases implement behavior.

Alternatives considered: A root Gradle multiproject containing Python; invented wrapper binaries; dozens of empty future modules.

Consequences: The requested directory structure is preserved; extra TOOLCHAIN, validation and start-here documents make handoff explicit. No empty future code is mistaken for completed implementation.

## ADR-012 — Explicit Espresso dependency for the foundation smoke test

Date: 2026-10-27

Status: Accepted

Context: The included Compose smoke test failed on the available API 37 emulator
before its assertions, with `NoSuchMethodException: InputManager.getInstance`.
Gradle dependency insight showed that Compose UI test 1.9.4 selected Espresso
3.5.0 transitively. The [official Espresso 3.7.0 release notes](https://developer.android.com/jetpack/androidx/releases/test#espresso-3.7.0)
document replacing that reflective call with a system-service lookup.

Decision: Declare `androidx.test.espresso:espresso-core:3.7.0` explicitly for
instrumented tests. Retain the existing Compose BOM, Kotlin, AGP, Gradle and SDK
baseline, and keep the original smoke-test assertions.

Alternatives considered: Replace the available emulator image; upgrade the full
Compose stack; skip the smoke test. The direct test-only dependency addresses
the observed failure with the smallest change.

Consequences: Re-run Android build/lint and the original instrumented test.
The app's runtime behavior and server/client authority boundary are unchanged.

## Decisions still deferred

External backend hosting and an open-source license are not selected. Phase 16 must start with an evidence-based local-networking decision. Phase 17 must specify its submarine mechanics after spaceship playtests. Phase 18 reevaluates current store requirements and crash-reporting needs without publishing anything.
