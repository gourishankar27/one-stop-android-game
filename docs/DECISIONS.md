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

## ADR-013 — Phase 03 transport subset and bounded connection ownership

Date: 2026-10-27

Status: Accepted

Context: Transport must be executable before rooms exist, while the designed v1
catalog already reserves room/gameplay commands and private views.

Decision: Expose ping/pong and typed errors on `/ws`. Validate strict envelopes
for every frame and the implemented ping payload. Recognized future commands
require an object payload but return `feature_unavailable` before business-payload
decoding or admission checks; their complete DTOs/permissions arrive in their
selected phases. No socket operation creates an engine fixture or membership.
Keep the engine adapter testable through explicit supplied engine/actor inputs.

Each connection owns its reader, writer and admission deadline under one
supervisor. A 32-item outbox coalesces only unsolicited snapshots of the same
kind/round, moving the replacement to the tail to preserve reply order. Full
queues close with 1013 instead of silently dropping a reply. Bound send/close
I/O and cancel/await owned tasks on every exit. Inject monotonic deadline/tick
sources; do not launch a live game runner.

ASGI cancellation can interrupt cleanup repeatedly (observed as an intermittent
TestClient exit cancellation). Shield the bounded cancel/await/close cleanup
with AnyIO's cancellation scope. Declare AnyIO as a direct runtime dependency;
retain its already locked version and the rest of the dependency baseline.

The 10-second admission deadline never resets on ping or unavailable commands.
Use the designed command rate (20/s, burst 40), a separate ping budget (1/s,
burst 3), and close with 1008 after five rate violations within ten seconds.
Other rejected well-framed requests keep the connection open. Logging includes
only generation, validated request ID, allowlisted operation/error code and
duration, without payloads, tokens, views or exception text.

Alternatives considered: Implement future room DTOs/behavior early; expose a
debug gameplay socket; use unbounded writes; log raw validation errors. These
would expand scope, blur authority or expose private input.

Consequences: Phase 03 can verify real transport and cleanup without claiming
admission or gameplay. NETWORK_PROTOCOL.md and fixtures distinguish this subset
from planned v1 behavior. Android networking/codec fixtures remain Phase 06;
there is no current Android socket implementation to change.

## ADR-014 — Lobby ownership, credential replay and expiry boundaries

Date: 2026-10-28

Status: Accepted

Context: Phase 04 needs serialized admissions, stable credentials and bounded
request replay without retaining plaintext tokens in membership or reply caches.
The planned host-transfer policy also needs a valid representation when every
remaining member is disconnected.

Decision: Each room has one mailbox/owner task. A registry admission lock
serializes code allocation and admission lookup; room owners mutate members and
update registry indexes synchronously, without socket I/O or awaiting that lock.
Expiry is checked before each command as well as on injected-clock deadlines.
One logical mutation increments the revision once, including ready resets and
host transfer. No-op commands/replays do not increment it.

Use an ephemeral 256-bit process key and HMAC-SHA256 of a versioned prefix plus
the secure membership UUID to issue a stable opaque 256-bit resume token. Store
only its SHA256 digest in membership/indexes. Cached admission receipts hold
credential-free identifiers/revision; reconstruct the token only into targeted
outgoing replies. Cache SHA256 signatures of normalized commands and at most
128 terminal replies for 30 seconds, preserving the original reply revision.
The key, credential input and targeted outbox frames remain private; neither the
registry nor replay records retain plaintext credentials. Restart discards the
key and all memberships. Compare token digests using constant-time comparison.
This uses standard-library secrets/hmac primitives, not game randomness.

Disconnected members reserve their seat and host identity for 30 seconds. Remove
expired memberships before processing a resume at that exact boundary. Transfer
an absent host to the earliest joined connected member (UUID tie-break). If none
is connected, `host_player_id` is null until the first eligible resume. Joining,
leaving, disconnecting and reconnecting clear all ready flags. Valid fresh lobby
commands/admissions refresh the 30-minute idle deadline; ping, rejected commands
and cached replays do not. Inbound inactivity is a separate 30-second connection
deadline, followed by membership grace. Timer tasks and room owners are awaited
at shutdown. Start checks host/stage/connected-ready count but stays unavailable.

Consequences: The initial implemented v1 lobby schema permits a temporarily
vacant host; no Android codec exists to migrate before Phase 06. All session
errors are safe and targeted. No game runner, roles or observer membership is
created. Later phases can reuse eligibility and room ownership.

## ADR-015 — Android transport ownership and debug endpoint opt-in

Date: 2026-10-28

Status: Accepted

Context: Phase 06 adds real transport without advancing into the usable lobby UI.
Rotation, uncertain replies and stale callbacks must not create duplicate sockets
or repeated admissions/actions. Debug LAN testing must not weaken release policy.

Decision: An application-owned repository serializes commands/callbacks through
one coroutine owner. A data source owns one OkHttp socket and bounded receive/send
queues. Every connection has a generation; old callbacks/timers are fenced. There
are at most 32 pending requests with five-second reply deadlines. Timeout/loss is
uncertain, never an automatic command rejection or resend. Only credential resume,
ping and a fresh full-state request are automatic recovery operations.

Keep credentials private in process memory, bound to their endpoint. Public flows,
results, logs, navigation and SavedStateHandle contain no token/raw error frame.
Clear cached snapshots on recovery; accept distinct message types at equal
revisions. Resume uses 1/2/4/8-second delays with an absolute 30-second recovery
budget; successful resume requests a new correlated full snapshot before declaring
recovery complete. Explicit leave/expiry/owner shutdown clear credentials.

Release accepts WSS only and has no default endpoint. Debug also has no implicit
connection: Gradle properties explicitly select an endpoint and opt into cleartext
for emulator/loopback or literal private LAN addresses. The debug-only network
security resource permits that transport; the typed endpoint validator restricts
its actual use. No TLS trust bypass or logging interceptor is installed. Existing
toolchain pins remain; add OkHttp 4.12.0 and serialization 1.9.0 with compiler plugin
2.2.21. A debug-only Connect/Ping/Create test membership/Disconnect panel supplies
connection feedback and a disposable membership for recovery checks; repository
callers exercise join/resume without implementing Phase 07 UI.

Consequences: The shell's draft forms remain local and no game authority moves
to Android. Process death loses the in-memory credential; durable storage and the
full background/recovery matrix remain Phase 14. Shared v1 fixtures run in both
languages; no wire version or room policy change is required.

## ADR-016 — Admission-driven lobby UI and explicit uncertain attempts

Date: 2026-10-28

Status: Accepted

Context: Phase 07 binds usable forms and lobby controls to the Phase 06 owner.
An acknowledgement cannot invent a member, readiness or a successful round start.
Back/cancellation and uncertain admission must not leave a live, forgotten socket
or silently submit another create/join.

Decision: Keep one application repository and navigation-entry form ViewModels.
Navigate to Lobby only from an authoritative session identity. Preserve nonsecret
raw inputs on rejection; normalize only the submitted name/code. Guard commands
synchronously while pending. An uncertain admission requires an explicit reset
before a new submit. Cancel closes the attempt, or leaves if admission already
succeeded. No automatic retry of admissions is introduced.

A shared lobby ViewModel renders IDs, host/ready/connected flags and `can_start`
from snapshots. It retains only presentation membership through bounded recovery,
not an old roster. Readiness is never optimistic. Both Back controls ask before
leave; expiry/removal returns Home. Eligible host Start sends the ordinary typed
intent and displays the server's planned feature-unavailable response. No role
screen or gameplay transition is implemented. Home's development transport panel
is superseded by the real forms; its debug implementation remains available.

Verification uses one physical phone plus two separately running Android emulator
clients, as explicitly selected by the user for this session. Record that device
mix rather than claiming three physical phones.

Consequences: No new library or wire change is needed. Saved state contains only
form inputs/validation presentation. The Phase 14 process-death/background matrix
remains deferred; process death still requires fresh admission.

## ADR-017 — Private briefing rounds held before gameplay

Date: 2026-10-28

Status: Accepted

Phase 08 replaces eligible Start with a round context owned by the existing room
mailbox. Freeze the roster, generate a round ID/seed, and seed-shuffle players in
Pilot/Engineer/Shields order. Two players split Pilot / Engineer+Shields. The
engine copies the post-assignment Random state for a private, reproducible stream.
Only owned metadata/station views are targeted to each authenticated player;
neither host status nor resume grants access to another station's details.

Start acknowledges before assignments/full snapshots. State requests and resume
restore assignment plus a fresh correlated private snapshot. Replay stays bounded
and membership-scoped. Briefing acknowledgements cover all owned stations. The
60-second acknowledgement deadline pauses during the existing disconnect grace;
all original participants must reconnect to resume. Explicit leave/grace expiry
aborts the frozen round. After all acknowledgements, stop the deadline and hold
in briefing with an explicit held-for-gameplay flag. No ticks or countdown run.
Abort stays on the briefing screen with Leave; rematch is still Phase 11.

Type all nine action shapes and validate authenticated identity, round ID and
engine ownership. Owned actions still reject invalid_stage during briefing,
pause or hold; no control mechanics are activated. Android requires an explicit
read confirmation for every owned station before acknowledging and clears
private presentation on recovery. Continue the user's one-phone/two-emulator
verification preference. Update the v1 role/briefing subset, allowlisted briefing
status, fixtures and both codecs together. No dependency/service is added.

## ADR-018 — Core controls and a mailbox-owned fixed-step runner

Date: 2026-10-28

Status: Accepted

Phase 09 completes the existing integer spaceship rules without emergencies or
new dependencies. Active durations contribute their effects before ageing;
energy gains and shield drain are combined then clamped, and zero energy releases
shield hold. Shutdown cancels the documented consumers but preserves cooldowns
and an existing evade. Active effects cannot stack even with custom shorter
cooldowns. Zero-energy shield activation is invalid_action; unmet output/power
requirements are insufficient_power. Defaults remain provisional and unchanged.
Engine version becomes spaceship-engine-v2; baseline replay fixtures retain their
commands/outcomes and record the new engine version alongside a full-catalog trace.

All briefing acknowledgements enter running directly. Phase 11 adds countdown.
A synchronous RoomRunner is called only by the existing room task; it uses the
injected monotonic clock, fixed 100ms steps and nonblocking 5Hz owned projections.
Commands dispatched in a turn precede its continuous steps and record their
completed tick/order. At most five catch-up steps run per turn; if more than five
are still due on the next consecutive turn, abort server_overload. Pause discards
wall-time backlog and resume establishes a fresh tick origin. Terminal state is
published immediately and is never coalesced away. Slow writers remain bounded
and cannot be awaited by simulation.

Current-round typed action attempts consume a monotonically increasing per-player
sequence even on rejection; stale-round attempts do not consume the current
sequence. Request replay is checked first and remains membership-scoped. Accepted
actions receive correlated ack with sequence/applied tick, rejected attempts get
action_rejected with sequence/round and safe code. No rejected action mutates ship
state, accepted order or RNG. Resume retains sequence; Android never resends actions.

Android renders only owned server views. Discrete actions have bounded pending
guards; output uses one in-flight request plus one conflated latest value, at most
10 sends/second. Recovery/round/stage changes invalidate queued intents. Local
slider preview is distinguished from accepted output. Inactive owned tabs retain
badges for server-provided instruction entries, without creating emergencies.
Terminal summary stays on Gameplay with confirmed Leave; no results/rematch flow.
The phone is currently unavailable: perform two-/three-emulator checks and leave
the real-phone gate pending unless that device becomes available.

2026-10-29 continuation: the phone became available; the user approved finishing
Phase 09 and then starting Phase 10. The prior one-phone/two-emulator preference
was retained. Real LAN UI and instrumentation closed the phone gate, with exact
device mix and results in CORE_GAMEPLAY_VALIDATION.md.

## ADR-019 — Deterministic spaceship emergencies in the existing engine

Date: 2026-10-29

Status: Accepted

Phase 10 implements only the three GAME_DESIGN.md emergencies. Their numeric
defaults are unchanged and provisional. Engine rules become spaceship-engine-v3,
config spaceship-v2: emergencies are enabled by default. An explicit validated
`emergencies_enabled=False` configuration preserves historical core-only replay
and isolated physics fixtures; clients cannot select or bypass this setting.

Each running tick applies continuous resources, evaluates existing emergencies
in ascending ID order, then ages active durations/cooldowns. This preserves the
last active evade tick. Success precedes same-tick timeout, asteroid maneuver
precedes shield payment, and terminal checks follow all simultaneous effects.
Completed events are removed and counted once. Terminal/abort clears remaining
warnings without inventing failures; pause advances neither events nor RNG.

After effects, if still running, reconsider a hot unrepresented overheat before
the scheduled slot. This gives a threshold event priority when only one capacity
slot remains. It uses no random draws. Scheduled slots start at configured tick
80; choose eligible asteroid/overload in their documented order, then any target
draws, then the next third-dependent inclusive integer interval. A skipped slot
draws only its next interval, with no every-tick retries. Stable monotonically
increasing IDs are local to a round; neither RNG/seed nor future slots leave it.

The existing room owner emits each shared lifecycle event once through the
bounded critical outbox. Regular private snapshots contain only owned typed
instructions and public labels; Android renders them without evaluating success
or running a deadline clock. Android retains only the latest server-provided
shared lifecycle kind/status, clears it with recovery/round replacement and keeps
active warnings driven by snapshots. No resolve command, framework or dependency is added.
New started labels do not immediately replace the last completed outcome text;
active warning labels still arrive in snapshots. This retains at most one shared
feedback item and does not infer a ship or round result on Android.
An explicit local CLI seed/config harness supports repeatable verification without
an HTTP/debug bypass. Retain the user-approved one-phone/two-emulator device mix
and distinguish scripted device checks from human group/balance observations.

## ADR-020 — Authoritative countdown, results and repeated room cycles

Date: 2026-10-29

Status: Accepted

The user explicitly selected Phase 11 while deferring physical-phone testing.
Phase 10's implementation/automated prerequisite is present; its human gate stays
open. This authorizes Phase 11 implementation without claiming Phase 10 complete.
Do not change the progress ledger unless Phase 11's completion gates all pass.

The existing room owner and synchronous runner advance a 3000ms countdown in
fixed 100ms steps, publishing at 5Hz and immediately on stage changes. Countdown
does not consume gameplay ticks, resources or RNG. Pause freezes the completed
countdown step and discards wall-time backlog; resume sets a fresh origin. The
same bounded catch-up/overload policy applies. Pure engine countdown transitions
accept integer elapsed milliseconds; immediate `start()` remains a core-fixture
API. Running physics, emergency defaults and replay versions are unchanged.

All terminal causes publish a stable allowlisted result snapshot and at most one
critical `game_over` event per round. Snapshots, including reconnect snapshots,
drive Android Results navigation; the event cannot manufacture an outcome.
Results readiness is explicit. `can_start` is the shared eligibility hint for
Start in lobby or Play again at terminal; the server checks the operation's stage
and host separately. Any join, resume/disconnect, start/rematch or return resets
readiness. Rematch requires 2–3 connected ready current members, preserves room/
membership identity and creates a fresh private seed/round/assignment/context.
Bounded collision retries reject a repeated previous seed/round safely rather
than reusing it. The local seed harness advances its deterministic seed sequence.
Return-to-lobby clears round ownership/state and readiness; new players can then
join. No finished context or stale input queue is reused.
Replacing/clearing a round invalidates cached private `request_state` replies;
other command terminal replies retain their bounded membership replay semantics.
Reusing an old state-request ID after that boundary therefore returns a current
allowlisted view, rather than retaining a previous station's private snapshot.

Android uses explicit Countdown and Results destinations and the existing shared
room-command ViewModel for readiness/host actions/leave. Recovery clears private
state; stage/round snapshots restore the destination. Returning to lobby or a new
briefing retires the old round on Android and clears cached views/feedback.
No database, framework, library, display/audio or Phase 14 fault matrix is added.

## ADR-021 — Separate public display sessions

Date: 2026-10-29

Status: Accepted

The user explicitly selected Phase 12 while earlier physical-phone/human gates
remain deferred. Implement only observers; do not mark those prerequisites complete.
The commit title mentions Public Display, but observer admission is still reserved.

Keep display sessions in a separate room-owned collection, capped at two including
disconnected seats during 30-second grace. Internal UUIDs/credentials are distinct
from player identity: admission returns kind=display and player_id=null. Reuse the
existing digest/index, bounded replay, generation fencing and recovery machinery.
Displays cannot control, ready, host or keep a controllerless room alive. Their
join/resume/disconnect/leave/expiry never reset player readiness, pause gameplay
or change host. Observer activity does not extend the room's idle deadline.
Deleting a room expires all observers and invalidates their credentials.

Send displays the existing public lobby roster and an independently constructed
public_state, never role assignments/station state. public_state.public is null
in lobby because no round exists; this explicit nullable extension avoids a fake
round ID/timer. During a round it uses the existing allowlisted PublicRoundView.
Snapshots, rather than private or one-shot events, drive the display UI. Final
public snapshots are critical, as player terminal snapshots already are.

Add a code-only Android display admission form and a dedicated public ViewModel/
screen. Membership kind controls routing and rejects private inbound messages;
the repository also blocks display control intents. Credentials remain private,
endpoint-bound and memory-only. No TV/casting, animation, new dependencies, game
rules or later resilience/presentation phase is introduced. Leave completion open
for any deferred real-phone/tablet verification.

## ADR-022 — Optional foreground feedback and restrained role presentation

Date: 2026-10-29

Status: Accepted

The user explicitly selected Phase 13 while physical-phone testing remains
deferred. Preserve the uncommitted Phase 12 implementation and unrelated prompt
edit. Phase 11's phone and Phase 10's human gates remain open. Review historical
phone readability evidence and an available emulator baseline before effects;
current physical-phone review/listening/TalkBack/group gates remain pending.
This is a documented scope/dependency exception, not completion evidence.

Use local FeedbackPreferences(audioEnabled,hapticsEnabled,reducedMotion), stored
as exactly three private booleans without session data. Audio and haptics default
off; reduced motion defaults on. All essential information remains visible text.
Settings are reachable within a session and never send a game command.

One application-owned feedback controller consumes matching authoritative
snapshots and correlated action receipts. A pure bounded mapper remembers round,
emergency ID, countdown step and action sequence; first/full recovery/background
snapshots establish a silent baseline. Hidden/paused/disconnected/settings views
consume events without output; enabling a setting never replays history. Activity
recreation replaces the platform sink while retaining in-memory deduplication.
Process restart has no session credentials and starts from a silent baseline.

Effects are short generated PCM tones and platform View haptics. At most one
sound stream, three cues per five seconds, 350ms global spacing and 1200ms urgent
spacing; no repeated alarm loop or queued catch-up effects. Audio focus/ringer/
device settings are respected. Pause/window focus loss stops sound and prevents
new effects; brief system haptic pulses are not a background service. No sample
or focus callback may play a late cue. Four generated sine-tone assets have a
reproducible stdlib generator and provenance, without adding a license grant or
assigning ownership on the user's behalf.

Role identity uses explicit labels with P/E/S monograms and contrast-tested tints,
never color alone. Navigation is instant by default; optional fades are brief,
without flashes or continuous motion. Improve headings, slider naming and polite
warning/feedback accessibility semantics. No rule/protocol/dependency, background
audio service, marketing art, TV/casting or Phase 14 fault matrix is added.

## ADR-023 — Process-safe recovery without action replay

Date: 2026-10-29

Status: Accepted

The user selected Phase 14 while earlier phone/human gates remain deferred.
Preserve implemented Phases 11–13 and the unrelated prompt edit. The interruption
matrix was written before coding; actual physical cases remain separate gates.

Retain the room owner, stable credentials, generation fencing, monotonic 30-second
grace and server-authoritative pause/abort/host policy. Add private
role_state.last_client_action_seq so process recovery can allocate the next
sequence without persisting game state or resending uncertain actions. It is an
additive v1 recovery field, defaults to zero for older snapshots, and never enters
public_state. Cap wire action sequences at signed 64-bit range on both sides.
Update synthetic fixtures and both implementations together.

A correlated full owned snapshot may refresh an equal room revision, because a
rejected action can consume its sequence without a ship mutation. Unsolicited
duplicates, older revisions and retired rounds remain filtered. This was verified
against the live server rather than inferred from transport acknowledgement.

Persist only endpoint, opaque token and expected membership identity/kind in an
atomic app-private no-backup file. Identity metadata binds a recovered receipt;
no role/ship/roster/action queue or UI bundle contains the credential. Match the
configured endpoint before resume, clear on explicit leave/disconnect/expiry or
unsafe protocol failure, and retain across ordinary process/owner disposal.
Use explicit backup/data-transfer exclusion rules. No account, cloud store,
server persistence or new library is introduced. Storage errors fail closed with
a visible local explanation, never an endless restore loop.

Single-Activity non-configuration onStop suspends transport/retry and clears stale
controls; onStart resumes using the original bounded recovery budget. Rotation
keeps the application repository/socket. Lifecycle requests are conflated and
serialized by the repository owner. No background audio/socket service or automatic
business-command/action replay is added. Initial restored credentials auto-resume
only to the matching endpoint, then require a full correlated private/public
snapshot. Duplicate close 1008 expires the superseded client rather than taking
the session back. Retry/Leave remain available from every recovery stage.

Feedback retains Phase 13's silent recovery baseline. Displays retain separate
public-only membership and cannot pause or host. Test optional features in the
fault matrix; do not implement Phase 15 playtesting/balance or later networking.

## Decisions still deferred

External backend hosting and an open-source license are not selected. Phase 16 must start with an evidence-based local-networking decision. Phase 17 must specify its submarine mechanics after spaceship playtests. Phase 18 reevaluates current store requirements and crash-reporting needs without publishing anything.
