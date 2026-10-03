import sqlite3

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import backup_before_upgrade, migrate_database


@pytest.mark.asyncio
async def test_fresh_database_and_idempotent_upgrade(tmp_path):
    path = tmp_path / "nested" / "app.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    await migrate_database(engine, str(path))
    await migrate_database(engine, str(path))
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        assert {
            "projects",
            "documents",
            "images",
            "prompts",
            "color_schemes",
            "alembic_version",
        } <= set(names)
    assert not (path.parent / "migration-backups").exists()
    await engine.dispose()


@pytest.mark.asyncio
async def test_unversioned_database_is_preserved_and_backed_up(tmp_path):
    path = tmp_path / "app.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    await migrate_database(engine, str(path))
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO projects (id,name,color_scheme,status) VALUES ('legacy','Keep me','okabe-ito','active')"
            )
        )
        await connection.execute(text("DROP TABLE alembic_version"))
    await migrate_database(engine, str(path))
    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT name FROM projects WHERE id='legacy'"))
        ).scalar_one() == "Keep me"
    backup = next((tmp_path / "migration-backups").glob("*.sqlite3"))
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT name FROM projects").fetchone() == ("Keep me",)
    assert backup.stat().st_mode & 0o777 == 0o600
    assert backup_before_upgrade(str(path)) is None
    await engine.dispose()
