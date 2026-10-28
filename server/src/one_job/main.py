"""Application composition root; each lifespan owns its connection manager."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anyio import CancelScope
from fastapi import FastAPI

from one_job.api.health import router as health_router
from one_job.api.websocket import router as websocket_router
from one_job.application.connections import ConnectionManager, ConnectionSettings
from one_job.application.rooms import RoomRegistry, RoomSettings
from one_job.application.timing import Clock, SystemClock


def create_app(
    *,
    clock: Clock | None = None,
    connections: ConnectionSettings | None = None,
    rooms: RoomSettings | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        app_clock = clock or SystemClock()
        registry = RoomRegistry(app_clock, rooms)
        manager = ConnectionManager(app_clock, connections or ConnectionSettings(), registry)
        application.state.connections = manager
        application.state.rooms = registry
        try:
            yield
        finally:
            with CancelScope(shield=True):
                try:
                    await manager.aclose()
                finally:
                    await registry.aclose()

    application = FastAPI(title="One Job Server", version="0.1.0", lifespan=lifespan)
    application.include_router(health_router)
    application.include_router(websocket_router)
    return application


app = create_app()
