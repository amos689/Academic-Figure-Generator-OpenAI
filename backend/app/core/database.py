"""Run packaged migrations and preserve a pre-upgrade SQLite snapshot."""

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, event
from sqlalchemy.ext.asyncio import AsyncEngine


def migration_config() -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
    )
    return config


def upgrade_connection(connection: Connection) -> None:
    config = migration_config()
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


def backup_before_upgrade(database_path: str) -> Path | None:
    database = Path(database_path)
    if not database.is_file() or database.stat().st_size == 0:
        return None
    head = ScriptDirectory.from_config(migration_config()).get_current_head()
    with sqlite3.connect(str(database)) as source:
        exists = source.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'alembic_version'"
        ).fetchone()
        if exists and source.execute("SELECT version_num FROM alembic_version").fetchone() == (
            head,
        ):
            return None
        folder = database.parent / "migration-backups"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{database.stem}-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.sqlite3"
        with sqlite3.connect(str(target)) as destination:
            source.backup(destination)
        target.chmod(0o600)
    return target


async def migrate_database(engine: AsyncEngine, database_path: str) -> None:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(backup_before_upgrade, database_path)
    async with engine.begin() as connection:
        await connection.run_sync(upgrade_connection)


def configure_sqlite(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def sqlite_options(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()
