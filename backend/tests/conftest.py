import httpx
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


@pytest_asyncio.fixture
async def api_client(sessions, tmp_path, monkeypatch):
    from app.config import get_settings
    from app.dependencies import get_db
    from app.main import create_app

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-fixture-only")
    get_settings.cache_clear()
    app = create_app()

    async def database():
        async with sessions() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://localhost"
    ) as client:
        yield client
    get_settings.cache_clear()
