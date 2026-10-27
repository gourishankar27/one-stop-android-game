# Phase 16 — Local Network Mode

Read [AGENTS.md](../AGENTS.md), [the master plan](plans.md) and relevant linked product/architecture documents before implementing. Progress is recorded only in the master plan.

## Objective

Evaluate and, if justified, simplify same-network party setup without an internet-hosted backend.

## Why this phase exists

Friends may prefer a reachable local server, but Android hosting/discovery constraints need evidence before a second authority model is added.

## Dependencies

Phase 15 complete. Optional extension, not required to run the initial development backend on a LAN.

## In scope

Technical decision first; compare LAN Python server, Android host-device server, NSD/mDNS and QR/manual address exchange; implement only the chosen justified minimal path.

## Explicitly out of scope

No automatic rewrite of the Python engine to Kotlin, peer-to-peer authority, WAN NAT traversal, casting, public deployment or multiple simultaneous networking modes.

## Architecture considerations

The Python server remains authoritative by default. A phone being room host never means it becomes the simulator. Manual LAN endpoints already used in Phase 06 are development setup; this phase adds party-friendly discovery/setup only after evaluation.

## Files likely to be created or modified

docs/decisions/ADR-016-local-networking.md; docs/DECISIONS.md index; scripts/local-server helpers if selected; Android debug/config/discovery UI; network setup docs and tests.

## Data models / APIs involved

An endpoint descriptor may contain scheme/host/port/protocol version but never credentials. NSD/QR must be treated as untrusted input and explicitly validated. No new gameplay messages are expected.

## Implementation tasks

1. Write the decision document before implementation with tested options, platform limitations, backend reuse, security, installation burden and expected offline behavior.
2. Prototype the smallest viable choices on real Android/network hardware. Compare one Python LAN process plus manual/QR endpoint against NSD; separately assess whether Android-hosted Python is realistically maintainable.
3. Select and document one approach or a no-go. If no approach is justified, record a reasoned investigated/deferred result with evidence; do not claim an implemented local mode.
4. If justified, implement minimal address discovery/exchange and connection selection with existing authoritative server protocol. Require confirmation of discovered endpoints and avoid token-bearing QR codes.
5. Document trusted debug WS vs WSS, Windows firewall private-network setup, same-subnet requirements and hotspot/AP isolation limitations. Do not automatically change system firewall rules.
6. Test loss/recovery, wrong endpoint/version, malformed QR/discovery, network switches and no-internet operation on the selected topology.

## Testing requirements

Unit tests validate endpoint parsing and discovery errors; integration tests connect multiple phones to the selected LAN server. Real hardware evidence must cover Wi-Fi/hotspot topology and no-internet behavior. Existing engine/protocol/reconnect suites must still pass.

## Manual verification

Follow the setup guide on a Windows PC and Android phones on the same private network without relying on public backend access. Confirm failed discovery leaves manual entry available if that was selected; observe limitations explicitly.

## Completion criteria

A technical decision with actual evidence exists; either a justified minimal LAN convenience works and is tested, or the plan is explicitly closed as investigated/deferred with no fake implementation claim. Authoritative simulation stays intact.

## Documentation updates

Update the decision index, setup/network security documentation and master status with the selected outcome and remaining platform questions.

## Handoff notes for next phase

This optional phase cannot silently expand the MVP or block Phase 18. Any host-device engine port needs a separately authorized plan.

