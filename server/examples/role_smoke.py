"""Capture/check private 2/3-controller test frames; export field names, never raw views."""

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from websockets.asyncio.client import ClientConnection, connect

STATION_FIELDS = {
    "pilot": {"lane", "maneuver_ready", "evade_remaining_ticks", "cooldowns", "hazards"},
    "engineer": {
        "output",
        "temperature",
        "available_power",
        "cooldowns",
        "boost_remaining_ticks",
        "instructions",
    },
    "shields": {
        "energy",
        "active",
        "facing",
        "cooldowns",
        "recharge_remaining_ticks",
        "boost_remaining_ticks",
        "instructions",
    },
}
PUBLIC_FIELDS = {
    "round_id",
    "stage",
    "tick_index",
    "remaining_ms",
    "countdown_remaining_ms",
    "paused_from",
    "hull_percent",
    "shield_percent",
    "warnings",
    "result",
}


async def send(
    socket: ClientConnection, kind: str, request_id: str, payload: dict[str, Any] | None = None
) -> None:
    await socket.send(
        json.dumps({"version": 1, "type": kind, "request_id": request_id, "payload": payload or {}})
    )


async def receive(
    socket: ClientConnection, kind: str, reply_to: str | None = None
) -> dict[str, Any]:
    while True:
        data: dict[str, Any] = json.loads(await socket.recv())
        if data["type"] == kind and (reply_to is None or data["reply_to"] == reply_to):
            return data


async def check(url: str, count: int) -> dict[str, Any]:
    async with AsyncExitStack() as stack:
        peers = [
            await stack.enter_async_context(connect(url, open_timeout=3, close_timeout=1))
            for _ in range(count)
        ]
        await send(peers[0], "create_room", "create", {"name": "Synthetic host"})
        admission = await receive(peers[0], "session_accepted", "create")
        code = admission["payload"]["room_code"]
        for index, peer in enumerate(peers[1:], 1):
            await send(
                peer, "join_room", f"join-{index}", {"room_code": code, "name": "Synthetic crew"}
            )
            await receive(peer, "session_accepted", f"join-{index}")
        for index, peer in enumerate(peers):
            await send(peer, "player_ready", f"ready-{index}", {"ready": True})
            await receive(peer, "ack", f"ready-{index}")
        await send(peers[1], "start_game", "not-host")
        assert (await receive(peers[1], "error", "not-host"))["payload"]["code"] == "not_host"
        await send(peers[0], "start_game", "start")
        assert (await receive(peers[0], "ack", "start"))["payload"]["operation"] == "start_game"
        assignments = []
        proof = []
        round_id = ""
        for index, peer in enumerate(peers):
            assigned = (await receive(peer, "role_assigned"))["payload"]
            private = (await receive(peer, "role_state"))["payload"]
            roles = set(assigned["roles"])
            assert len(roles) in (1, 2) and set(private["stations"]) == roles
            assert {item["role"] for item in assigned["instructions"]} == roles
            assert set(private) == {"public", "stations", "briefing", "last_client_action_seq"}
            assert private["last_client_action_seq"] >= 0
            assert set(private["public"]) == PUBLIC_FIELDS
            assert private["public"]["stage"] == "briefing" and private["public"]["tick_index"] == 0
            assert private["public"]["round_id"] == assigned["round_id"]
            round_id = assigned["round_id"]
            for role, view in private["stations"].items():
                assert set(view) == STATION_FIELDS[role]
            assignments.append(roles)
            proof.append(
                {
                    "controller_index": index,
                    "owned_roles": sorted(roles),
                    "station_keys": sorted(private["stations"]),
                    "field_names": {
                        role: sorted(view) for role, view in private["stations"].items()
                    },
                }
            )
        assert sorted(role for roles in assignments for role in roles) == [
            "engineer",
            "pilot",
            "shields",
        ]
        wrong = (
            {"type": "coolant"}
            if "pilot" in assignments[0]
            else {"type": "move_lane", "direction": "left"}
        )
        await send(
            peers[0],
            "player_action",
            "wrong-role",
            {"round_id": round_id, "client_action_seq": 1, "action": wrong},
        )
        assert (await receive(peers[0], "action_rejected", "wrong-role"))["payload"][
            "code"
        ] == "not_role_owner"
        for index, peer in enumerate(peers):
            await send(peer, "briefing_ready", f"read-{index}", {"round_id": round_id})
            await receive(peer, "ack", f"read-{index}")
        for peer in peers:
            countdown_seen = False
            while True:
                current = (await receive(peer, "role_state"))["payload"]
                if current["public"]["stage"] == "countdown":
                    countdown_seen = True
                    assert current["public"]["tick_index"] == 0
                if current["briefing"]["complete"] and current["public"]["stage"] == "running":
                    assert countdown_seen
                    assert (
                        current["public"]["tick_index"] == 0
                        and not current["briefing"]["held_for_gameplay"]
                    )
                    break
        for index, peer in enumerate(peers):
            await send(peer, "leave_room", f"leave-{index}")
            await receive(peer, "ack", f"leave-{index}")
        print(
            f"{count} controllers: private allowlists, ownership, "
            "acknowledgements, countdown and running tick 0 passed"
        )
        return {
            "controllers": count,
            "private_allowlists_passed": True,
            "captured_field_proof": proof,
        }


async def main(url: str, proof: Path | None) -> None:
    async with asyncio.timeout(20):
        results = [await check(url, count) for count in (2, 3)]
    if proof is not None:
        await asyncio.to_thread(
            proof.write_text, json.dumps(results, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.url, args.proof))
