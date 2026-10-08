"""Public FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from electricity_map_api.config import Settings
from electricity_map_api.database import create_database_engine, create_turso_engine
from electricity_map_api.distribution.router import router as distribution_router
from electricity_map_api.exceptions import APIError, api_error_handler, validation_error_handler
from electricity_map_api.market.router import router as market_router
from electricity_map_api.metadata.router import router as metadata_router
from electricity_map_api.rate_limit import InMemoryRateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, allowing tests to inject explicit settings."""
    app_settings = settings or Settings.from_environment()
    engine = (
        create_database_engine(app_settings.database)
        if app_settings.development_mode
        else create_turso_engine(app_settings.turso_url, app_settings.turso_auth_token)
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    application = FastAPI(
        title="Electricity Map API",
        version=version("electricity-map-api"),
        description="Public API for Spanish electricity data from official sources.",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.rate_limiter = InMemoryRateLimiter(app_settings.window_seconds)

    application.state.database_engine = engine
    if app_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(app_settings.cors_origins),
            allow_methods=["GET"],
        )
    application.add_exception_handler(APIError, api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.include_router(metadata_router)
    application.include_router(market_router)
    application.include_router(distribution_router)
    return application


app = create_app()
