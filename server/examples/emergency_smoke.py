"""Complete real-socket cooperative rounds; print counts, never targets or credentials."""

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from role_smoke import PUBLIC_FIELDS, STATION_FIELDS, receive, send
from websockets.asyncio.client import connect


async def check(url: str, count: int) -> None:
    async with AsyncExitStack() as stack:
        peers = [await stack.enter_async_context(connect(url)) for _ in range(count)]
        await send(peers[0], "create_room", "create", {"name": "Captain"})
        receipt = await receive(peers[0], "session_accepted", "create")
        for index, peer in enumerate(peers[1:]):
            await send(
                peer,
                "join_room",
                f"join-{index}",
                {"name": "Crew", "room_code": receipt["payload"]["room_code"]},
            )
            await receive(peer, "session_accepted", f"join-{index}")
        for index, peer in enumerate(peers):
            await send(peer, "player_ready", f"ready-{index}", {"ready": True})
            await receive(peer, "ack", f"ready-{index}")
        await send(peers[0], "start_game", "start")
        await receive(peers[0], "ack", "start")
        assigned = [(await receive(peer, "role_assigned"))["payload"] for peer in peers]
        round_id = assigned[0]["round_id"]
        for index, peer in enumerate(peers):
            await send(peer, "briefing_ready", f"read-{index}", {"round_id": round_id})
            await receive(peer, "ack", f"read-{index}")
        public: dict[int, dict[str, Any]] = {}
        lifecycle: list[list[tuple[int, str, str]]] = [[] for _ in peers]
        results = []

        async def operate(index: int) -> None:
            peer = peers[index]
            pending: dict[str, str] = {}
            sequence = 0
            heartbeat = 0

            async def act(kind: str, **values: Any) -> None:
                nonlocal sequence
                if kind in pending.values():
                    return
                sequence += 1
                request = f"action-{index}-{sequence}"
                pending[request] = kind
                await send(
                    peer,
                    "player_action",
                    request,
                    {
                        "round_id": round_id,
                        "client_action_seq": sequence,
                        "action": {"type": kind, **values},
                    },
                )

            async for raw in peer:
                frame = json.loads(raw)
                kind = frame["type"]
                payload = frame["payload"]
                if kind in ("ack", "action_rejected"):
                    pending.pop(frame["reply_to"], None)
                elif kind == "emergency_event":
                    assert set(payload) == {"round_id", "emergency_id", "kind", "status"}
                    key = (payload["emergency_id"], payload["kind"], payload["status"])
                    assert key not in lifecycle[index]
                    lifecycle[index].append(key)
                elif kind == "role_state":
                    shared = payload["public"]
                    assert set(shared) == PUBLIC_FIELDS
                    revision = frame["room_revision"]
                    if revision in public:
                        assert public[revision] == shared
                    else:
                        public[revision] = shared
                    assert set(payload["stations"]) == set(assigned[index]["roles"])
                    for role, view in payload["stations"].items():
                        assert set(view) == STATION_FIELDS[role]
                    if shared["result"] is not None:
                        results.append(shared["result"])
                        return
                    if shared["stage"] != "running":
                        continue
                    tick = shared["tick_index"]
                    if tick >= heartbeat:
                        await send(peer, "ping", f"ping-{index}-{tick}", {"nonce": "alive"})
                        heartbeat = tick + 100
                    for role, view in payload["stations"].items():
                        if role == "engineer":
                            target = 40 if view["instructions"] else 60
                            if view["output"] != target:
                                await act("set_engine_power", value=target)
                            if (
                                any(
                                    item["target_max_temperature"] is not None
                                    for item in view["instructions"]
                                )
                                and view["cooldowns"]["coolant"] == 0
                            ):
                                await act("coolant")
                        elif role == "shields":
                            overload = any(item["deactivate"] for item in view["instructions"])
                            asteroid = next(
                                (
                                    item
                                    for item in view["instructions"]
                                    if item["required_facing"] is not None
                                ),
                                None,
                            )
                            active = not overload and asteroid is not None
                            facing = asteroid["required_facing"] if asteroid else view["facing"]
                            if view["active"] != active or view["facing"] != facing:
                                await act("set_shield", active=active, facing=facing)
                            if view["energy"] < 800 and view["cooldowns"]["recharge_shield"] == 0:
                                await act("recharge_shield")
                        elif view["hazards"] and view["cooldowns"]["move_lane"] == 0:
                            danger = view["hazards"][0]["impact_lane"]
                            if view["lane"] == danger:
                                await act(
                                    "move_lane", direction="right" if danger == "left" else "left"
                                )
            raise AssertionError("socket ended before a terminal snapshot")

        async with asyncio.timeout(150):
            await asyncio.gather(*(operate(index) for index in range(count)))
        assert len(results) == count and all(result == results[0] for result in results)
        assert all(events == lifecycle[0] for events in lifecycle)
        result = results[0]
        assert result["resolved_count"] == sum(
            status == "resolved" for _, _, status in lifecycle[0]
        )
        assert result["failed_count"] == sum(status == "failed" for _, _, status in lifecycle[0])
        for index, peer in enumerate(peers):
            await send(peer, "leave_room", f"leave-{index}")
            await receive(peer, "ack", f"leave-{index}")
        print(
            f"{count} controllers: complete {result['outcome']}; private views/public equality; "
            f"resolved={result['resolved_count']} failed={result['failed_count']}; "
            "no duplicate lifecycle events",
            flush=True,
        )


async def main(url: str, players: str) -> None:
    for count in (2, 3) if players == "both" else (int(players),):
        await check(url, count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws")
    parser.add_argument("--players", choices=("2", "3", "both"), default="both")
    args = parser.parse_args()
    asyncio.run(main(args.url, args.players))
