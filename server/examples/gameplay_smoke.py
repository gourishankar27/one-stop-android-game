"""Real two/three-controller controls and private synchronized snapshots; no raw logs."""

import argparse
import asyncio
from contextlib import AsyncExitStack
from typing import Any

from role_smoke import receive, send
from websockets.asyncio.client import connect


async def check(url: str, count: int) -> None:
    async with AsyncExitStack() as stack:
        peers = [await stack.enter_async_context(connect(url)) for _ in range(count)]
        await send(peers[0], "create_room", "create", {"name": "Captain"})
        receipt = await receive(peers[0], "session_accepted", "create")
        code = receipt["payload"]["room_code"]
        for index, peer in enumerate(peers[1:]):
            await send(peer, "join_room", f"join-{index}", {"name": "Crew", "room_code": code})
            await receive(peer, "session_accepted", f"join-{index}")
        for index, peer in enumerate(peers):
            await send(peer, "player_ready", f"ready-{index}", {"ready": True})
            await receive(peer, "ack", f"ready-{index}")
        await send(peers[0], "start_game", "start")
        await receive(peers[0], "ack", "start")
        owned = []
        for peer in peers:
            assigned = (await receive(peer, "role_assigned"))["payload"]
            owned.append(set(assigned["roles"]))
        round_id = assigned["round_id"]
        for index, peer in enumerate(peers):
            await send(peer, "briefing_ready", f"read-{index}", {"round_id": round_id})
            await receive(peer, "ack", f"read-{index}")
        for peer in peers:
            while (await receive(peer, "role_state"))["payload"]["public"]["stage"] != "running":
                pass
        owners = {role: index for index, roles in enumerate(owned) for role in roles}
        sequences = [0] * count

        async def action(role: str, value: dict[str, Any], expected: str | None = None) -> None:
            index = owners[role]
            sequences[index] += 1
            sequence = sequences[index]
            request = f"action-{index}-{sequence}"
            await send(
                peers[index],
                "player_action",
                request,
                {
                    "round_id": round_id,
                    "client_action_seq": sequence,
                    "action": value,
                },
            )
            reply = await receive(
                peers[index], "ack" if expected is None else "action_rejected", request
            )
            assert reply["payload"]["client_action_seq"] == sequence
            if expected is None:
                assert reply["payload"]["applied_tick"] >= 0
            else:
                assert reply["payload"]["code"] == expected

        await action("pilot", {"type": "evade"}, "insufficient_power")
        await action("shields", {"type": "set_shield", "active": True, "facing": "left"})
        await action("shields", {"type": "recharge_shield"})
        await action("engineer", {"type": "engine_boost"}, "insufficient_power")
        await action("engineer", {"type": "set_engine_power", "value": 100})
        await action("engineer", {"type": "engine_boost"})
        await action("shields", {"type": "shield_boost"})
        await action("pilot", {"type": "move_lane", "direction": "left"})
        await action("pilot", {"type": "evade"})
        await action("engineer", {"type": "coolant"})
        # Compare common public state at matching revisions, never station details across owners.
        observed: dict[int, dict[str, Any]] = {}
        matched = set()
        for index, peer in enumerate(peers):
            while True:
                frame = await receive(peer, "role_state")
                payload = frame["payload"]
                assert set(payload["stations"]) == owned[index]
                if payload["public"]["stage"] != "running" or payload["public"]["tick_index"] < 2:
                    continue
                revision = frame["room_revision"]
                if index == 0:
                    observed[revision] = payload["public"]
                    if len(observed) >= 4:
                        break
                elif revision in observed:
                    assert payload["public"] == observed[revision]
                    matched.add(index)
                    break
        assert len(matched) == count - 1
        await action("engineer", {"type": "emergency_shutdown"})
        index = owners["engineer"]
        await send(peers[index], "request_state", "shutdown-state")
        state = (await receive(peers[index], "role_state", "shutdown-state"))["payload"]
        assert state["stations"]["engineer"]["output"] == 0
        assert state["stations"]["engineer"]["boost_remaining_ticks"] == 0
        index = owners["shields"]
        await send(peers[index], "request_state", "shield-state")
        state = (await receive(peers[index], "role_state", "shield-state"))["payload"]["stations"][
            "shields"
        ]
        assert (
            not state["active"]
            and state["recharge_remaining_ticks"] == state["boost_remaining_ticks"] == 0
        )
        for index, peer in enumerate(peers):
            await send(peer, "leave_room", f"leave-{index}")
            await receive(peer, "ack", f"leave-{index}")
        print(
            f"{count} controllers: nine actions, power rejection, "
            "private synchronized state and shutdown passed"
        )


async def main(url: str) -> None:
    async with asyncio.timeout(20):
        await check(url, 2)
        await check(url, 3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws")
    asyncio.run(main(parser.parse_args().url))
