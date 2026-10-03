"""FastAPI dependency injection providers — personal-use (no auth)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.database import configure_sqlite

settings = get_settings()

# ---------------------------------------------------------------------------
# Database (SQLite via aiosqlite)
# ---------------------------------------------------------------------------

_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
configure_sqlite(_engine)

_AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, closing it after the request."""
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_async_session_factory():
    """Return the async session factory for use outside of FastAPI DI."""
    return _AsyncSessionLocal
