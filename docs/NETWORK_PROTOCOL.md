# WebSocket protocol v1

## Implemented Phase 12 subset

Phase 13 does not change the wire contract. Its optional local feedback uses the
existing round/emergency IDs, server countdown snapshots and correlated action
reply sequences. Android action receipts are process-local presentation events,
not a new DTO, command, broadcast or source of game authority.

The server exposes independent `GET /health` and `/ws`. WebSockets use JSON text
frames only, one message per frame, maximum UTF-8 size 16 KiB (16,384 bytes).
The Python boundary uses strict Pydantic discriminated unions; Android mirrors
the implemented subset with sealed serializable types. No arbitrary dictionaries should
define gameplay payloads.

Implemented commands: `ping`, `create_room`, `join_room`, `resume_session`,
`leave_room`, `player_ready`, `request_state`, `start_game`, `briefing_ready`,
`play_again`, `return_to_lobby`, `join_display` and
all nine authoritative `player_action` controls. Their payload DTOs reject
unknown fields/coercion. Names are trimmed
1–20 Unicode scalar characters without control characters; duplicate names are
allowed. Codes trim outer whitespace and uppercase six ASCII symbols from
`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`. Unknown/started/full rooms produce safe errors;
disconnected seats still count against capacity. Admission emits targeted
`session_accepted`, then an unsolicited full `lobby_state` to connected members.
The snapshot contains only code/stage/host ID/roster connectivity/readiness and
common `can_start` eligibility. Tokens never appear in broadcasts.

`start_game` checks membership, host, lobby stage and exactly 2 or 3 connected
ready players, in that order. An eligible request returns `ack`, freezes the
roster/config/seed under a new round UUID and changes stage to `briefing`.
Each player receives only their `role_assigned` and `role_state`, alongside the
shared lobby snapshot. Host status never widens private access. `can_start`
reports eligibility in lobby and terminal stages. `player_ready` is accepted in
lobby/finished/aborted and returns `ack` before any changed lobby snapshot;
an unchanged ready value returns only the ack. In lobby, `request_state` returns
a correlated `lobby_state`. During a round it sends unsolicited lobby and owned
assignment snapshots followed by the correlated full `role_state` as its terminal
reply. Resume sends fresh owned assignment/state too; the token remains room-local.
Leave returns `ack`, invalidates the membership and closes 1000.
All membership/connectivity changes clear readiness and advance revision once;
no-op commands and cached replays do not advance it.

`briefing_ready` accepts a canonical round UUID and acknowledges all of that
authenticated participant's stations. Repeated acknowledgement is a no-op ack.
The initial deadline is 60 seconds; disconnect suspends its remaining budget
during the existing 30-second grace. Only reconnection of all frozen participants
resumes it. Explicit leave, grace expiry or briefing expiry abort with
`player_left`, `disconnect_timeout` or `briefing_timeout` in the public result.
All acknowledged participants enter a server-owned 3000ms countdown. The same
100ms runner advances countdown without changing gameplay time, resources,
cooldowns, emergencies or RNG. Countdown publishes at 5Hz and transitions
immediately to running at tick zero. `held_for_gameplay` is false. Countdown
and running disconnects pause until every frozen participant returns; paused
wall time creates no catch-up backlog. Countdown resumes from its last completed
100ms step. The separate gameplay timer remains the configured 60–120 seconds
(90 seconds by default), with the existing seeded difficulty thirds.

All nine `player_action` shapes are validated. A mismatched round returns
`stale_round`; authenticated ownership is checked before the running-stage gate,
returning `not_role_owner` for another station and `invalid_stage` outside running.
Accepted commands receive correlated `ack` with `operation=player_action`,
`client_action_seq` and authoritative `applied_tick`. Rejections receive correlated
`action_rejected` with safe code/message, sequence and supplied round UUID.
Malformed messages still use ordinary `error`. Authenticated typed current-round
attempts consume their sequence even on rejection; sequences must strictly
increase. Stale-round attempts do not consume current-round sequence. Cached
request replay precedes sequence validation, returning the original terminal reply
without applying again. A new ID with an old sequence returns `stale_action`.
There is no sequence reset on resume; a new round resets it. All declared v1
commands are now implemented. Phase 10 schedules asteroid,
overheating and shield-overload events inside the pure engine.

`emergency_event` is now implemented as a critical, noncoalesced shared lifecycle
message. It has null `reply_to`, a room revision and exactly round ID, emergency
ID, kind and started/resolved/failed status. Each transition is emitted once;
request_state/resume restore current snapshots rather than replaying event history.
No target, seed, future slot or failure predicate enters the shared event. Public
warning labels contain no deadlines or directions. Only the recipient's owned
station views contain the relevant typed instructions and server-computed
remaining milliseconds. Paused deadlines stay fixed; finished warnings disappear.
The Android repository retains only the latest shared lifecycle label per round,
clears it on recovery/round replacement and never derives resources/outcomes from it.

The room owner dispatches queued commands before that turn's fixed 100ms steps.
Owned snapshots target 5Hz; accepted replies need not wait for a snapshot. Each
tick/action advances room revision; skipped snapshot revisions are normal. Lobby
snapshots accompany lifecycle/membership changes, not every tick. At most five
catch-up steps run per turn; if more than five remain due on the next consecutive
turn, abort with `server_overload`. Terminal owned state includes the public
result immediately, bypasses snapshot coalescing, and stops the runner. Exactly
one critical `game_over` with null `reply_to`, room revision and
`{round_id,result}` is emitted to each currently connected player on terminal
transition. Snapshot/resume restores that same result without replaying the event.
Android navigates to Results from the matching full snapshot, never from the event.

`play_again` and `return_to_lobby` accept typed empty payloads and require the
current host in finished/aborted. Play again also requires exactly 2 or 3 connected,
explicitly ready members. It acknowledges before broadcasting a new briefing,
round UUID, seed and shuffled assignments; all per-round state/readiness resets.
The new UUID and seed must differ from the preceding round, even after returning
to lobby (bounded eight factory attempts). Return to lobby clears the round and
all readiness while preserving membership and room code. Old-round action and
briefing commands are rejected. No-op/cached command replies do not repeat these
operations. Client caches, pending inputs and sequence allocation reset on a
fresh round or lobby transition; no gameplay commands are replayed.

Validation order: UTF-8 byte size, JSON, strict required envelope, integer version,
recognized type, then implemented payload. Unknown fields/types, missing fields,
invalid values and bool/string/float versions produce `invalid_message` (or
`unknown_type` for an otherwise valid envelope) without closing. Only a valid
1–64 ASCII request ID is echoed; malformed JSON/oversize errors have null
`reply_to`. Duplicate JSON keys, nonfinite numbers, trailing JSON and binary
frames are invalid framing: safe error where possible then 1007. Oversize closes
1009. A well-formed unsupported integer version receives `unsupported_version`
then 1002. Safe error messages never echo input, validation details or exceptions.
Fatal framing/version errors take precedence over exhausted rate budgets.

Every unadmitted connection expires ten seconds after opening, even after pings
or unavailable commands: unsolicited `not_authenticated` then 1008. Configure the
clock/deadline via `create_app` for tests; successful admission cancels that deadline.
After 30 seconds without inbound activity the connection closes 1001; membership
grace then lasts a separate 30 seconds. The separate ping budget is 1/s, burst 3; commands use 20/s,
burst 40. A fifth rate violation within ten seconds closes 1008 after `rate_limited`.

The bounded outbox holds 32 queued items plus at most one in-flight send. Only
unsolicited snapshots of the same kind/room (lobby) or kind/round (role/public state)
coalesce, at the queue tail; older
revisions are ignored. Correlated responses and critical events never coalesce.
Queue overflow or a five-second blocked send closes 1013, requiring future clients
to recover missing replies/state. Shutdown closes 1001; final close I/O is bounded
to one second. Owned tasks are cancelled/awaited, including on ASGI cancellation.

The dev launcher also sets Uvicorn's WebSocket limit to 16,384 bytes. Uvicorn may
reject oversize frames before the app can send an error; close 1009 is authoritative.
`server/logging.json` enables allowlisted application log fields (generation,
validated request ID, known operation/error code, close code and duration), never
payloads, tokens, views or exception text. Uvicorn protocol debug logging is not
enabled. Shared [Phase 04 fixtures](protocol-fixtures/phase04.json) validate the
current Python DTOs and are mirrored by Android codec tests.
[Phase 03 fixtures](protocol-fixtures/phase03.json) preserve the earlier subset.
[Phase 06 fixtures](protocol-fixtures/phase06.json) add synthetic join/resume/leave
and expiry cases checked in both languages. No wire version or server behavior
changed in Phase 06.
[Phase 08 fixtures](protocol-fixtures/phase08.json) add synthetic owned assignments,
two-/three-player private states and acknowledgement replies. Both implementations
check these fixtures; no live token or captured private frame is committed.
[Phase 11 fixtures](protocol-fixtures/phase11.json) add two-/three-player countdown,
paused countdown, stable victory/defeat/abort, critical result events, rematch and
return-to-lobby messages. Python and Android validate the same synthetic fixtures.

Android accepts additive incoming fields while requiring the typed known fields
and strict primitive types. Malformed/oversize/duplicate-key frames and unsupported
versions produce safe protocol feedback; unknown message kinds discard cached
views and request a fresh snapshot, or close if recovery cannot be established.
The decoder bounds JSON nesting to 64 containers. No raw error message, close
reason, frame or token reaches public connection/command state or UI diagnostics.
The current decoder supports `pong`, `session_accepted`, `ack`, `error`,
`lobby_state`, `role_assigned`, `role_state`, `public_state`, `emergency_event`
and `game_over`.
Role decoding requires exactly one station or Engineer+Shields, matching metadata
and station keys. Unknown station keys, null station values or inconsistent
ownership/acknowledgement are protocol failures; private caches are cleared.
Player recovery completes only after the fresh correlated private snapshot;
display recovery requires the fresh correlated public snapshot and public lobby.
Equal
revisions across distinct message kinds are valid. Later event kinds need DTOs
and fixture updates in their selected phases.
[Phase 09 fixtures](protocol-fixtures/phase09.json) add running private views,
action acknowledgement and rejection, checked by both codecs. The Kotlin
repository allocates action sequences for normal UI intents, retains them through
resume/ViewModel replacement, and correlates rejection by request/sequence/round.
It never uses an acknowledgement to invent a new ship snapshot. Slider intents
have one in-flight send and one conflated latest value, at most 10 sends/second;
recovery/stage/round changes and shutdown discard stale queued output.

Android uses one socket per repository, 16 KiB accepted text frames, 64 incoming
events and 64 actor events, a 64 KiB outgoing socket queue and 32 pending requests.
Open and correlated request deadlines are five seconds; a missing command reply
is **uncertain**, never automatically rejected or replayed. A ten-second ping
watchdog uses the same five-second reply deadline. Recovery clears cached views,
fences generations and sends only credential resume, then a new correlated
`request_state`. Delays are 1/2/4/8 seconds within an absolute 30-second budget,
including handshakes and snapshot deadlines. There is no automatic create/join
or action resend. Distinct snapshot kinds may share a revision; older/duplicate
same-kind revisions and retired rounds are ignored. Credentials remain private
in process memory and are cleared on explicit leave, expiry or owner closure.

Resume authenticates by digest before binding a connection. It retains identity
and token, replaces/fences the old generation and closes an old active socket
1008. Old queued commands and disconnect callbacks cannot alter its replacement.
Invalid/expired credentials receive `session_expired` then 1008. Grace expires at
the exact deadline, checked before processing commands even if a timer has not
yet run. The host seat is held during grace. On removal, the earliest joined
connected member becomes host; if none is connected the host ID is temporarily
null until an eligible member resumes. Empty rooms disappear; idle lobbies expire
after 30 minutes. Only accepted fresh lobby commands/admission refresh idle time;
pings, errors and cached replays do not. Settings are injectable through
`RoomSettings`; this is process memory, not persistence.

Replay is per membership: retain at most 128 terminal replies for 30 seconds.
Signatures use normalized typed commands, never stored raw token payloads. An
identical request ID/signature returns its original reply/revision without
mutation/broadcast; different content returns `request_id_conflict`. Admission
replays return the same targeted session receipt. After resume, use a fresh
`request_state` ID for current state. The cache contains credential-free admission
metadata; a private lifespan key reconstructs the stable token only when sending
targeted admission replies. Membership/indexes store only token digests. See
[ADR-014](DECISIONS.md#adr-014--lobby-ownership-credential-replay-and-expiry-boundaries).
Round-state replies are cached only in the recipient membership's bounded replay
cache; private fields are excluded from DTO/replay representations and logs.
Replacing or clearing a round invalidates cached private `request_state` replies,
so even reuse of their request IDs cannot restore an old private round. Command
replay entries retain the existing bounded semantics.

## Envelope

Client → server:

```json
{"version":1,"type":"ping","request_id":"p-1","payload":{"nonce":"hello"}}
```

Server → client:

```json
{"version":1,"type":"pong","reply_to":"p-1","room_revision":null,"payload":{"nonce":"hello"}}
```

`version` is integer 1. Client `request_id` is a unique 1–64 character ASCII
identifier (`A–Z a–z 0–9 _ -`); payload is always an object. Server `reply_to`
is a request ID or null for unsolicited snapshots/events. `room_revision` is an
integer >=0 for room commands/snapshots, otherwise null. Connection/framing errors
can have null revision even on an admitted connection. Envelope keys are required.
Do not send `player_id`, `host=true`, seed, damage or resource updates as client
authority. The authenticated connection supplies player identity.

Reject unknown client fields, invalid types (including numeric strings/bool-as-int),
unknown action kinds and values outside their ranges. Client handlers may ignore
unknown server fields; unknown server message kinds trigger a protocol error UI
and a fresh state request, without guessing a new state.

## Connection admission and credentials

Before membership, only `ping`, `create_room`, `join_room`, `resume_session`, and
`join_display` are allowed. Require membership within 10 seconds.
Limit controllers to 3, rooms to 100 per process and displays to 2 per room.
Provisional limits are configurable server settings, not balance config.

`create_room`/`join_room` return a targeted `session_accepted` containing a secure
256-bit opaque resume token. A room code is discovery, not proof of identity.
Store only a token digest in the registry and compare safely. Never put tokens
in query strings, public lobby state, results, logs or screenshots. There are no
accounts. Keep tokens stable for one membership initially; erase on explicit
leave, expiry, room deletion or server restart. WSS protects credentials outside
opt-in trusted development. Do not retry a lost create/join blindly; show an
uncertain result and let the user retry (unclaimed rooms expire).

### Public display sessions (Phase 12)

`join_display{room_code}` is a strict code-only admission at any room stage.
It returns a targeted `session_accepted` with `kind=display`, `player_id=null`
and its own opaque credential, then the public `lobby_state` and `public_state`.
The internal display UUID never becomes a player identity. Displays occupy a
separate two-session collection, including disconnected seats during 30-second
grace. A third receives `display_full`; it consumes no controller seat.
Display tokens use the same digest/index/endpoint-bound recovery policy as players.

Displays may only ping, request state, resume their own credential or leave.
Every other typed command, including all nine station actions and all admissions/
host/ready/briefing commands, receives `not_controller` before player dispatch,
without changing room revision/readiness/host/simulation. Duplicate command IDs
retain bounded replay/conflict semantics. A correlated display `request_state`
ends with `public_state`, preceded by unsolicited public lobby state.

`public_state.payload` has exactly `{public: PublicRoundView|null}`. Null means
the lobby has no round; it does not invent a round UUID or gameplay clock.
Otherwise it is constructed directly with the existing public allowlist, never
from a private player projection. Displays receive no assignment, role state,
station objects, seed/config/ownership, private targets, deadlines or credentials
belonging to players. They receive current warning labels and terminal results
through snapshots, without `emergency_event` or `game_over` events. Public
snapshots use 5Hz/coalescing; terminal public snapshots are critical/noncoalesced.

Display join/resume/disconnect/leave/grace expiry never reset player readiness,
pause a round, transfer host or advance revision. Observer activity does not
refresh room idle time. A controllerless/deleted/expired room invalidates all
observer credentials and sends unsolicited `session_expired`/1008 to connected
displays. Shutdown instead closes 1001. Replacing a connection fences its old
generation without affecting players. Round replacement/lobby return invalidates
cached public replies along with cached private state replies.

Android tracks kind with nullable player identity, routes displays to a dedicated
public-only screen, blocks controller intents locally and treats private inbound
messages on a display session as a protocol failure. It hides stale public state
while recovering, and restores only after full correlated public synchronization.
Credentials are never saved in UI/navigation/process state. Shared synthetic
[Phase 12 fixtures](protocol-fixtures/phase12.json) are checked in both languages.

Resume authenticates by token, not a claimed player name/ID. A successful resume
fences and closes the old socket, replaces connection generation, returns
`session_accepted`, then full lobby and current per-player round views. Commands
queued from an obsolete connection generation are rejected. Resume has the
30-second grace policy in ARCHITECTURE.md. Invalid/expired token returns
`session_expired`; return to join/home. No client action queue is replayed.

## Client messages

`{}` means an empty object. All operations require membership except admission
and ping. Observer restrictions apply when Phase 12 is implemented.

| Type | Payload | Success / permission |
| --- | --- | --- |
| `create_room` | `name: string` | `session_accepted`, then `lobby_state`; caller becomes host |
| `join_room` | `room_code: string, name: string` | Same; lobby only; fail full/started/unknown room |
| `resume_session` | `resume_token: string` | Admission above; stable player/observer identity |
| `leave_room` | `{}` | `ack`, credential invalidated, socket normal close; active round aborts |
| `player_ready` | `ready: boolean` | `ack`, then lobby snapshot; controller in lobby/results |
| `start_game` | `{}` | `ack`, then private `role_assigned` and state; host, connected/ready 2–3 players, lobby only |
| `briefing_ready` | `round_id: UUID string` | `ack`; assigned player acknowledges all owned stations |
| `player_action` | `round_id: UUID string, client_action_seq: integer>=1, action: Action` | `ack` after application or `action_rejected`; running, station owner |
| `request_state` | `{}` | Full `lobby_state` and applicable `role_state`; display receives `public_state` |
| `play_again` | `{}` | `ack`, new round/roles/briefing; host at finished/aborted and all connected/ready |
| `return_to_lobby` | `{}` | `ack`, then `lobby_state`; host at finished/aborted; clears readiness |
| `ping` | `nonce: string` (1–64 chars) | `pong`; allowed before admission |
| `join_display` | `room_code: string` | Observer `session_accepted` and public snapshot; not a player slot |

Player name and room-code normalization is defined in GAME_STATE.md. Only an
existing participant can resume after start. Late new controller joins are denied.
`request_state` in a lobby need not emit a round view. Snapshot responses carry
the request's `reply_to`; additional unsolicited broadcasts have null.

### Action discriminated union (Phase 09)

| `action.type` | Additional fields | Station |
| --- | --- | --- |
| `move_lane` | `direction: left|right` | pilot |
| `evade` | none | pilot |
| `set_engine_power` | `value: integer 0..100` | engineer |
| `engine_boost` | none | engineer |
| `coolant` | none | engineer |
| `emergency_shutdown` | none | engineer |
| `set_shield` | `active: boolean, facing: front|left|right|rear` | shields |
| `recharge_shield` | none | shields |
| `shield_boost` | none | shields |

Action schemas define structure; engine validates permissions/resources/cooldowns.
No partial acceptance. A mismatched round ID is `stale_round`. IDs on domain
commands are supplied by the application, not copied from untrusted fields.

## Server messages

| Type | Payload shape / recipient |
| --- | --- |
| `session_accepted` | `room_code, kind: player|display, player_id: UUID|null, resume_token`; only that connection |
| `ack` | `operation: client message type`; player actions also `client_action_seq, applied_tick`; requester only |
| `lobby_state` | `room_code, stage, host_player_id, players: [{player_id,name,connected,ready}], can_start: boolean`; room members |
| `role_assigned` | `round_id, roles: [Role], instructions: [{role,title,steps:[string]}]`; owning player only |
| `role_state` | `public: PublicRoundView, stations: {owned Role: StationView}, briefing: BriefingStatus`; owning player only |
| `public_state` | `public: PublicRoundView|null`; observers only; null in lobby |
| `emergency_event` | `round_id, emergency_id, kind, status: started|resolved|failed`; players only, shared labels without targets |
| `game_over` | `round_id, result: {outcome,reason,survived_ms,final_hull_percent,resolved_count,failed_count,players:[{player_id,name}]}`; players only |
| `action_rejected` | `code, message, client_action_seq, round_id`; requester only |
| `error` | `code, message, retryable: boolean`; requester, or unsolicited connection error |
| `pong` | `nonce`; requester |

In `lobby_state`, `stage` is lobby/briefing/countdown/running/paused/finished/aborted;
`can_start` is common Start eligibility in lobby or Play-again eligibility in
finished/aborted, never a substitute for checking host ID and operation stage.
`host_player_id` is UUID|null, temporarily null if no connected successor exists.
Shared membership is sent even during a round to show connection state.

`PublicRoundView` fields: `round_id`, `stage`, `tick_index`, `remaining_ms`,
`countdown_remaining_ms` (also retained when paused from countdown, otherwise null),
`paused_from` (stage|null),
`hull_percent`, `shield_percent`, `warnings: [{emergency_id,kind,label}]`,
`result` (the game_over result or null). Percentages are integer 0..100.
Warning labels have no hidden target/direction/countdown. Shared stage/timing is
inside each private role snapshot so a client can reconcile it atomically.

`BriefingStatus` contains `acknowledged: boolean` for the recipient,
`waiting_player_ids: [UUID]` from the frozen roster, `remaining_ms: integer>=0`,
`complete: boolean` and `held_for_gameplay: boolean`. Completion means no waiting
participants. The server emits held=false and transitions through countdown;
the earlier held briefing remains readable in historical Phase 08 fixtures. The briefing
budget is distinct from the unchanged round `public.remaining_ms`; the UI does
not run either clock locally. Aborts, including briefing timeout at zero survival
time, use `public.result` and the same Results route/event as gameplay outcomes.
Results contain a frozen 2/3-player roster, whole 100ms survival steps up to
120 seconds, percentages 0..100 and nonnegative counters. Victory requires
`survived` and at least 60 seconds; defeat requires `hull_destroyed` and 0% hull;
abort requires an abort reason. A victory may display 0% hull because a positive
internal hull below 1% rounds down; that lossy percentage cannot determine defeat.

Station views, keyed only by owned roles:

- `pilot`: `lane`, `maneuver_ready`, `evade_remaining_ticks`, `cooldowns`,
  `hazards: [{emergency_id,impact_lane,deadline_remaining_ms}]`.
- `engineer`: `output`, `temperature`, `available_power`, `cooldowns`,
  `boost_remaining_ticks`, `instructions: [{emergency_id,target_max_output,target_max_temperature,deadline_remaining_ms}]`.
  Targets that do not apply to an emergency are nullable.
- `shields`: `energy`, `active`, `facing`, `cooldowns`, `recharge_remaining_ticks`,
  `boost_remaining_ticks`, `instructions: [{emergency_id,required_facing,deactivate,deadline_remaining_ms}]`.
  `required_facing` is nullable. `deactivate` is boolean.

`cooldowns` is a typed object of that station's action keys to nonnegative remaining
ticks, not an open-ended map of arbitrary engine attributes. Before emergencies,
the arrays are empty. `deadline_remaining_ms` is server-computed. A later change
must update these schemas and fixtures, rather than silently adding raw state.
Pilot cooldown keys are `move_lane, evade`; Engineer keys are
`engine_boost, coolant`; Shields keys are `recharge_shield, shield_boost`.
Phase 10 populates these existing emergency arrays. Asteroid lane goes only to
Pilot and required shield facing only to Shields. Overheat output/temperature go
only to Engineer. Overload gives Engineer the output limit and Shields the
deactivate instruction. Progress stays internal; keep the condition until the
server removes the warning. [Phase 10 fixtures](protocol-fixtures/phase10.json)
cover both concurrency pairs, every recipient in 2/3-player mode and each event
kind/status. All fixture identities/targets are synthetic. `maneuver_ready` is computed by the
server from running stage, output requirement, cooldown and active duration.
Zero-energy shield activation returns `invalid_action`; missing output/spare
power returns `insufficient_power`; already active effects or cooldowns return
`cooldown`. Rejections never partially change facing/resources/cooldowns.

## Correlation, ordering and recovery

Each command produces one terminal `ack`, `action_rejected` or `error` carrying
`reply_to`. Admission uses `session_accepted` as its terminal reply. Ping uses
`pong`; `request_state` uses correlated full snapshots instead of a separate ack.
Broadcast events are consequences, not terminal replies. Check timeouts (initially
5 seconds) in the client; a missing reply does not mean the action never happened.

Cache the last 128 command terminal replies per membership for 30 seconds. A
repeated request ID with identical payload returns its cached reply, without
mutation. Reuse with different payload returns `request_id_conflict`. Monotonically
increasing `client_action_seq` per player/round also rejects stale duplicates after
cache eviction. Reset action sequence only for a new round; resume preserves it.
Do not automatically resend actions after reconnect. New `request_state` obtains
authoritative state; irreversible commands are not inferred from UI state.

WebSocket order applies per connection only. Fence obsolete generations. At each
server tick consume queued actions in recorded room order. Coalesce snapshots
to 5 Hz; critical events/replies keep order. Ignore older round snapshots and
older revisions; **do not drop distinct message types at equal revisions**.
On reconnect clear cached private data before accepting full views. A gap in
revisions is normal when snapshots coalesce. No delta replay is required.

Ping every 10 seconds; no inbound activity for 30 seconds marks the connection
dead and begins disconnect grace. Grace is a separate 30 seconds after detection.
Lifecycle backgrounding may cause disconnection; it never makes a phone the clock.

## Errors and compatibility

Codes include `invalid_message`, `unsupported_version`, `unknown_type`,
`not_authenticated`, `room_not_found`, `room_full`, `room_started`, `capacity`,
`not_host`, `not_ready`, `invalid_stage`, `invalid_action`, `not_role_owner`,
`insufficient_power`, `cooldown`, `stale_round`, `stale_action`,
`request_id_conflict`, `rate_limited`, `session_expired`, `feature_unavailable`,
`internal_error`. Messages are safe human-readable text; UI behavior uses codes.
Never send tracebacks, tokens or hidden simulation state in error details.

Malformed frames: error if possible, then close 1007 for invalid JSON or 1009 for
oversize. Unsupported version: `unsupported_version`, then 1002. Invalid session:
1008 after error. Slow consumer: 1013. Normal leave: 1000. Unexpected server error:
1011 after a redacted log. Validly framed invalid commands do not close the socket.
Provisional per-connection limit: 20 commands/second with burst 40; excess commands
are rejected, sustained abuse closes 1008. Heartbeats have a separate small budget.

v1 requires exact major-version agreement. Additive server fields may be ignored
by older clients; newly required fields, changed meanings or new required client
types need a version bump. No implicit downgrade. Check example fixtures against
both implementations from Phase 06 onward. Later phase names in this document
are reserved design: `feature_unavailable` until those handlers exist.
