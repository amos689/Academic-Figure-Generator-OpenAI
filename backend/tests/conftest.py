import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import configure_sqlite, migrate_database


@pytest_asyncio.fixture
async def sessions(tmp_path):
    path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    configure_sqlite(engine)
    await migrate_database(engine, str(path))
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    yield factory
    await engine.dispose()
