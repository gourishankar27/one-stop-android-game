# WebSocket protocol v1

## Implemented Phase 08 subset

The server exposes independent `GET /health` and `/ws`. WebSockets use JSON text
frames only, one message per frame, maximum UTF-8 size 16 KiB (16,384 bytes).
The Python boundary uses strict Pydantic discriminated unions; Android mirrors
the implemented subset with sealed serializable types. No arbitrary dictionaries should
define gameplay payloads.

Implemented commands: `ping`, `create_room`, `join_room`, `resume_session`,
`leave_room`, `player_ready`, `request_state`, `start_game`, `briefing_ready` and
the typed ownership boundary for `player_action`. Their payload DTOs reject
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
reports lobby eligibility. `player_ready` returns `ack` before any changed lobby snapshot;
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
All acknowledged participants remain in briefing with `held_for_gameplay=true`;
no countdown, engine start, simulation tick or control panel is enabled.

All nine `player_action` shapes are validated. A mismatched round returns
`stale_round`; authenticated ownership is checked before the held-stage gate,
returning `not_role_owner` for another station and `invalid_stage` for one's own.
These are ordinary correlated `error` replies in Phase 08. No action is applied.
The running action acknowledgements/sequencing and `action_rejected` catalog below
belong to later gameplay. `play_again`, `return_to_lobby` and `join_display` remain
reserved with `feature_unavailable` before business payload decoding. No observer
membership or `public_state` broadcast is exposed.

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

Android accepts additive incoming fields while requiring the typed known fields
and strict primitive types. Malformed/oversize/duplicate-key frames and unsupported
versions produce safe protocol feedback; unknown message kinds discard cached
views and request a fresh snapshot, or close if recovery cannot be established.
The decoder bounds JSON nesting to 64 containers. No raw error message, close
reason, frame or token reaches public connection/command state or UI diagnostics.
The current decoder supports `pong`, `session_accepted`, `ack`, `error`,
`lobby_state`, `role_assigned`, `role_state` and the reserved `public_state`.
Role decoding requires exactly one station or Engineer+Shields, matching metadata
and station keys. Unknown station keys, null station values or inconsistent
ownership/acknowledgement are protocol failures; private caches are cleared.
Recovery completes only after the fresh correlated private snapshot. Equal
revisions across distinct message kinds are valid. Later event kinds need DTOs
and fixture updates in their selected phases.

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
(Phase 12) `join_display` are allowed. Require membership within 10 seconds.
Limit controllers to 3, rooms to 100 per process, future displays to 2 per room.
Provisional limits are configurable server settings, not balance config.

`create_room`/`join_room` return a targeted `session_accepted` containing a secure
256-bit opaque resume token. A room code is discovery, not proof of identity.
Store only a token digest in the registry and compare safely. Never put tokens
in query strings, public lobby state, results, logs or screenshots. There are no
accounts. Keep tokens stable for one membership initially; erase on explicit
leave, expiry, room deletion or server restart. WSS protects credentials outside
opt-in trusted development. Do not retry a lost create/join blindly; show an
uncertain result and let the user retry (unclaimed rooms expire).

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
| `join_display` (12) | `room_code: string` | Observer `session_accepted` and public snapshot; not a player slot |

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
| `public_state` (12) | `public: PublicRoundView`; observers only |
| `emergency_event` | `round_id, emergency_id, kind, status: started|resolved|failed`; shared labels only, no private targets |
| `game_over` | `round_id, result: {outcome,reason,survived_ms,final_hull_percent,resolved_count,failed_count,players:[{player_id,name}]}`; all room members |
| `action_rejected` | `code, message, client_action_seq, round_id`; requester only |
| `error` | `code, message, retryable: boolean`; requester, or unsolicited connection error |
| `pong` | `nonce`; requester |

In `lobby_state`, `stage` is lobby/briefing/countdown/running/paused/finished/aborted;
`can_start` is common start eligibility, not a substitute for checking host ID.
`host_player_id` is UUID|null, temporarily null if no connected successor exists.
Shared membership is sent even during a round to show connection state.

`PublicRoundView` fields: `round_id`, `stage`, `tick_index`, `remaining_ms`,
`countdown_remaining_ms` (null outside countdown), `paused_from` (stage|null),
`hull_percent`, `shield_percent`, `warnings: [{emergency_id,kind,label}]`,
`result` (the game_over result or null). Percentages are integer 0..100.
Warning labels have no hidden target/direction/countdown. Shared stage/timing is
inside each private role snapshot so a client can reconcile it atomically.

`BriefingStatus` contains `acknowledged: boolean` for the recipient,
`waiting_player_ids: [UUID]` from the frozen roster, `remaining_ms: integer>=0`,
`complete: boolean` and `held_for_gameplay: boolean`. Completion means no waiting
participants. Held means complete and nonterminal in this phase. The briefing
budget is distinct from the unchanged round `public.remaining_ms`; the UI does
not run either clock locally. Aborts are conveyed in `public.result`, not a new
results route or `game_over` orchestration.

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
Phase 08 emits empty emergency arrays
and `maneuver_ready=false` because controls are held.

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
