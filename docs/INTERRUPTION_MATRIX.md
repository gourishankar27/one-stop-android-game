# Interruption behavior matrix

Written before Phase 14 implementation, 2026-10-29. Expected behavior below is
the contract to test, not a claim of observed success. Actual evidence and pending
physical-device cases are recorded separately in RESILIENCE_VALIDATION.md.

| Interruption | Expected server behavior | Expected Android behavior |
| --- | --- | --- |
| Brief controller disconnect/Wi-Fi loss | On detected disconnect pause briefing/countdown/running; freeze completed simulation/deadline, hold seat/host for 30 monotonic seconds | Clear private controls and unsent input; bounded token resume and fresh correlated owned snapshot; no command replay |
| Controller absent through exact grace deadline | Abort active round with disconnect_timeout, remove expired member, transfer absent host to earliest connected survivor; never award defeat for outage | Expired explanation, erase credential, allow rejoin; remaining host can return to lobby; fewer than two cannot rematch |
| Explicit leave | Remove immediately, abort active round with player_left; invalidate token | Clear private persistent credential before leaving locally, never restore membership after a restart |
| Duplicate resume | Bind replacement atomically, close old socket 1008, reject queued old-generation actions/disconnect callbacks | Superseded client clears credential; replacement restores only its own projection; avoid reconnect takeover loops |
| Android background/lock | Closing controller socket pauses only required stages; grace stays authoritative | On non-configuration activity stop, suspend transport/heartbeat/retry, clear controls, keep minimal credential and original recovery budget; no feedback output |
| Rotation/activity recreation | No membership/host/readiness change or simulation pause from rotation alone | Retain app repository/sequence, replace feedback sink, no duplicate socket or repeated cues |
| Process death/reopen within grace | Same identity/token/roles, frozen stage resumed; authoritative action-sequence high-water mark restored | Read minimal app-private backup-excluded credential; bind only matching configured endpoint; fresh full snapshot before controls; next action sequence is greater than server's |
| Process reopen after grace | Expired token; active round already aborted and seat removed | Clear saved credential and show expiry/restart explanation, never create/join automatically |
| Server restart | In-memory rooms/tokens are gone; invalid resume receives session_expired/1008 | Clear credential and stale UI; explain session unavailable/possible restart, no fabricated recovery |
| Handshake/snapshot loss or retry exhaustion | Existing rate/send/watchdog and grace bounds apply | 5-second request/open/snapshot limits; 1/2/4/8-second backoff within one absolute 30-second budget; Retry never extends it |
| Uncertain ready/start/action/leave | Existing bounded request replay protects explicit duplicate IDs | Do not automatically resend business commands or actions; state recovery reconciles outcome |
| Display disconnect/background/process death | No player pause/ready reset/host change; separate display grace/capacity; controllerless room expires observers | Same public-only credential recovery and terminal/lobby snapshots; no station/action state or stale alarms |
| Terminal recovery | Stable original result, no duplicate one-shot result event | Navigate from full terminal snapshot even if game_over was missed; no replayed feedback |
| Endpoint change/corrupt credential/storage failure | Never trust client state or adopt another membership | Erase/refuse unusable record, expose a bounded local recovery/storage problem, never send a token to a different endpoint |
| Slow client/repeated outages/shutdown | Bounded mailbox/outbox/replies/tasks, old generations fenced, owned tasks closed | Bounded channels/pending requests; no accumulated input/effect queues or late callbacks after close |

Wi-Fi detection is not instantaneous: socket failure or heartbeat/inactivity
watchdogs must first detect loss. Grace begins at server-detected disconnect,
not at an Android toggle timestamp. Human/physical-phone 2/3-player checks remain
required even when deterministic and emulator cases pass. Earlier phone/group
deferrals remain in force; the master ledger is not updated without all gates.
