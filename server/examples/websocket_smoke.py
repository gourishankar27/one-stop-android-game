"""Local Phase 03 transport check; uses synthetic input and never creates a room."""

import argparse
import asyncio
import json
from urllib.request import urlopen

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed


def health(base_url: str) -> None:
    with urlopen(f"{base_url}/health", timeout=3) as response:
        assert response.status == 200
        assert json.load(response) == {"status": "ok", "service": "one-job-server"}
    print("GET /health: 200, expected liveness payload")


def request(kind: str, request_id: str, payload: dict[str, str], version: int = 1) -> str:
    return json.dumps(
        {"version": version, "type": kind, "request_id": request_id, "payload": payload}
    )


async def expect_close(socket: ClientConnection, code: int) -> None:
    try:
        await socket.recv()
    except ConnectionClosed as error:
        assert error.rcvd is not None and error.rcvd.code == code
    else:
        raise AssertionError("expected WebSocket close")


async def check(base_url: str) -> None:
    await asyncio.to_thread(health, base_url)
    socket_url = base_url.replace("http://", "ws://", 1) + "/ws"
    async with connect(socket_url, open_timeout=3, close_timeout=1) as socket:
        await socket.send(request("ping", "ping-1", {"nonce": "hello"}))
        assert json.loads(await socket.recv()) == {
            "version": 1,
            "type": "pong",
            "reply_to": "ping-1",
            "room_revision": None,
            "payload": {"nonce": "hello"},
        }
        print("/ws ping: correlated pong, no room revision")
        await socket.send(request("create_room", "future-1", {"name": "Crew"}))
        response = json.loads(await socket.recv())
        assert response["payload"]["code"] == "feature_unavailable"
        assert response["reply_to"] == "future-1"
        print("create_room: feature_unavailable, no membership")
        await socket.send(request("unknown", "unknown-1", {}))
        response = json.loads(await socket.recv())
        assert response["payload"]["code"] == "unknown_type"
        print("unknown command: unknown_type, connection remains open")
        await socket.send("{")
        response = json.loads(await socket.recv())
        assert response["payload"]["code"] == "invalid_message"
        assert response["reply_to"] is None
        await expect_close(socket, 1007)
        print("malformed JSON: invalid_message then close 1007")
    async with connect(socket_url, open_timeout=3, close_timeout=1) as socket:
        await socket.send(request("ping", "version-1", {"nonce": "hello"}, version=2))
        response = json.loads(await socket.recv())
        assert response["payload"]["code"] == "unsupported_version"
        assert response["reply_to"] == "version-1"
        await expect_close(socket, 1002)
        print("version 2: unsupported_version then close 1002")
    await asyncio.to_thread(health, base_url)


async def main(base_url: str) -> None:
    async with asyncio.timeout(15):
        await check(base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(main(args.base_url.rstrip("/")))
