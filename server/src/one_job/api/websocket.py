"""Thin transport entry point; membership and gameplay remain future phases."""

from typing import cast

from fastapi import APIRouter, WebSocket

from one_job.application.connections import ConnectionManager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(socket: WebSocket) -> None:
    manager = cast(ConnectionManager, socket.app.state.connections)
    await manager.serve(socket)
