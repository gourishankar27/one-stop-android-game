"""Application composition root; each lifespan owns its connection manager."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from one_job.api.health import router as health_router
from one_job.api.websocket import router as websocket_router
from one_job.application.connections import ConnectionManager, ConnectionSettings
from one_job.application.timing import Clock, SystemClock


def create_app(
    *, clock: Clock | None = None, connections: ConnectionSettings | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        manager = ConnectionManager(clock or SystemClock(), connections or ConnectionSettings())
        application.state.connections = manager
        try:
            yield
        finally:
            await manager.aclose()

    application = FastAPI(title="One Job Server", version="0.1.0", lifespan=lifespan)
    application.include_router(health_router)
    application.include_router(websocket_router)
    return application


app = create_app()
