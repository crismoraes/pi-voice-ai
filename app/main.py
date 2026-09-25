"""FastAPI application entry point for the Phase 1 foundation."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.config import get_settings
from app.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("pi_voice_ai")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("APP_STARTED", extra={"version": __version__})
    yield
    logger.info("APP_STOPPED", extra={"version": __version__})


app = FastAPI(
    title="PiVoice AI",
    version=__version__,
    lifespan=lifespan,
)
app.include_router(health_router)


def run() -> None:
    """Run the application using environment-backed host and port settings."""
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,
    )


if __name__ == "__main__":
    run()
