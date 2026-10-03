"""FastAPI application factory — personal-use version."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import setup_middleware
from app.core.privacy import configure_private_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown logic."""
    logger.info("Starting up Academic Figure Generator API (personal-use)...")

    from app.core.database import migrate_database
    from app.dependencies import _engine

    await migrate_database(_engine, get_settings().DATABASE_PATH)
    logger.info("SQLite database migrations applied.")

    # Seed preset color schemes
    try:
        await _seed_preset_color_schemes()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Preset color scheme seeding failed (continuing): %s", exc)

    # Ensure data directories exist
    settings = get_settings()
    data_dir = Path(settings.DATA_DIR)
    (data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (data_dir / "figures").mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Shutting down Academic Figure Generator API...")


async def _seed_preset_color_schemes() -> None:
    """Ensure system preset color schemes exist in the DB (idempotent)."""
    from sqlalchemy import select  # noqa: PLC0415

    from app.core.prompts.color_schemes import (  # noqa: PLC0415
        COLOR_SCHEME_DISPLAY_NAMES,
        DEFAULT_COLOR_SCHEME,
        PRESET_COLOR_SCHEMES,
    )
    from app.dependencies import get_async_session_factory  # noqa: PLC0415
    from app.models.color_scheme import ColorScheme  # noqa: PLC0415

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        for slug, colors in PRESET_COLOR_SCHEMES.items():
            display_name = COLOR_SCHEME_DISPLAY_NAMES.get(slug, slug)
            existing = (
                await session.execute(
                    select(ColorScheme.id).where(
                        ColorScheme.type == "preset",
                        ColorScheme.name == display_name,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            session.add(
                ColorScheme(
                    name=display_name,
                    type="preset",
                    colors=colors,
                    is_default=(slug == DEFAULT_COLOR_SCHEME),
                )
            )

        await session.commit()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    configure_private_logging()
    app = FastAPI(
        title="Academic Figure Generator API",
        version="0.2.0",
        description="AI-powered scientific paper illustration service (personal-use)",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Middleware (CORS, request logging)
    setup_middleware(app)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    _include_routers(app, settings.API_V1_PREFIX)

    return app


def _include_routers(app: FastAPI, prefix: str) -> None:
    """Register all v1 API routers."""
    router_modules = [
        ("app.api.v1.health", "router"),
        ("app.api.v1.projects", "router"),
        ("app.api.v1.documents", "router"),
        ("app.api.v1.prompts", "router"),
        ("app.api.v1.images", "router"),
        ("app.api.v1.color_schemes", "router"),
    ]

    for module_path, attr in router_modules:
        try:
            import importlib  # noqa: PLC0415

            module = importlib.import_module(module_path)
            router = getattr(module, attr)
            app.include_router(router, prefix=prefix)
            logger.debug("Registered router: %s", module_path)
        except (ImportError, AttributeError) as exc:
            logger.warning("Skipping router %s: %s", module_path, exc)


app = create_app()
