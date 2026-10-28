"""Public FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from electricity_map_api.cache import create_response_cache
from electricity_map_api.config import Settings
from electricity_map_api.database import create_database_engine, create_postgres_engine
from electricity_map_api.distribution.router import router as distribution_router
from electricity_map_api.electricity.router import router as electricity_router
from electricity_map_api.exceptions import APIError, api_error_handler, validation_error_handler
from electricity_map_api.gas.router import router as gas_router
from electricity_map_api.metadata.router import router as metadata_router
from electricity_map_api.rate_limit import InMemoryRateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, allowing tests to inject explicit settings."""
    app_settings = settings or Settings.from_environment()
    engine = (
        create_postgres_engine(app_settings.database_url)
        if app_settings.database_url
        else create_database_engine(app_settings.database)
        if app_settings.development_mode
        else None
    )
    cache_source = (
        app_settings.database_url
        if app_settings.database_url
        else str(app_settings.database.resolve())
        if app_settings.development_mode and app_settings.database
        else "unconfigured"
    )
    response_cache = create_response_cache(app_settings.redis_url, cache_source, app_settings.cache_ttl_seconds)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()
            if response_cache is not None:
                response_cache.close()

    application = FastAPI(
        title="Electricity Map API",
        version=version("electricity-map-api"),
        description="Public API for Spanish electricity data and historical gas distributor network evidence.",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.rate_limiter = InMemoryRateLimiter(app_settings.window_seconds)

    application.state.database_engine = engine
    application.state.response_cache = response_cache
    if app_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(app_settings.cors_origins),
            allow_methods=["GET"],
        )
    application.add_exception_handler(APIError, api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.include_router(metadata_router)
    application.include_router(electricity_router, prefix="/v1/electricity")
    application.include_router(electricity_router, prefix="/v1/market", deprecated=True)
    application.include_router(distribution_router)
    application.include_router(gas_router)
    return application


app = create_app()
