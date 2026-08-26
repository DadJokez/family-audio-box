"""FamilyBox executable and FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from familybox.config import Settings
from familybox.logging_config import configure_logging
from familybox.runtime import build_runtime
from familybox.web.app import create_web_app


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(
            resolved_settings.log_level,
            json_output=resolved_settings.json_logs,
        )
        runtime = build_runtime(resolved_settings)
        application.state.runtime = runtime
        try:
            await runtime.start()
            yield
        finally:
            await runtime.stop()

    return create_web_app(lifespan=lifespan)


app = create_app()


def run() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings),
        host=settings.web_host,
        port=settings.web_port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    run()
