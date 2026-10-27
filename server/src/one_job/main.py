"""Application composition root. No rooms or game loop exist in Phase 00."""

from fastapi import FastAPI

from one_job.api.health import router as health_router


def create_app() -> FastAPI:
    application = FastAPI(title="One Job Server", version="0.1.0")
    application.include_router(health_router)
    return application


app = create_app()
