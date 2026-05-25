from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatbot_service.config import load_config

MIGRATION_FILENAME_PATTERN = re.compile(r"^\d{3,}_.+\.sql$")
MIGRATION_LOCK_ID = 704_220_910


class MigrationError(RuntimeError):
    """Raised when chatbot storage migrations cannot be applied safely."""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sql: str
    checksum: str


def default_migrations_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations"


def discover_migrations(migrations_dir: Path | None = None) -> list[Migration]:
    root = migrations_dir or default_migrations_dir()
    if not root.exists():
        raise MigrationError(f"Migration directory does not exist: {root}")

    migrations: list[Migration] = []
    for path in sorted(root.glob("*.sql")):
        if not MIGRATION_FILENAME_PATTERN.match(path.name):
            raise MigrationError(f"Invalid migration filename: {path.name}")
        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            raise MigrationError(f"Migration is empty: {path.name}")
        migrations.append(
            Migration(
                version=path.stem,
                path=path,
                sql=sql,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            )
        )
    return migrations


async def apply_migrations(
    dsn: str,
    migrations_dir: Path | None = None,
) -> list[str]:
    if not dsn:
        raise ValueError("CHATBOT_DB_DSN is required to run migrations")

    try:
        import asyncpg
    except ModuleNotFoundError as exc:
        raise RuntimeError("asyncpg is required to run chatbot storage migrations") from exc

    connection = await asyncpg.connect(dsn=dsn)
    try:
        return await _apply_migrations_on_connection(
            connection,
            discover_migrations(migrations_dir),
        )
    finally:
        await connection.close()


async def _apply_migrations_on_connection(
    connection: Any,
    migrations: list[Migration],
) -> list[str]:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chatbot_schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    applied_versions: list[str] = []
    async with connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock($1)", MIGRATION_LOCK_ID)
        rows = await connection.fetch(
            "SELECT version, checksum FROM chatbot_schema_migrations"
        )
        applied = {str(row["version"]): str(row["checksum"]) for row in rows}

        for migration in migrations:
            current_checksum = applied.get(migration.version)
            if current_checksum == migration.checksum:
                continue
            if current_checksum is not None:
                raise MigrationError(
                    f"Applied migration checksum changed: {migration.version}"
                )

            await connection.execute(migration.sql)
            await connection.execute(
                """
                INSERT INTO chatbot_schema_migrations (version, checksum)
                VALUES ($1, $2)
                """,
                migration.version,
                migration.checksum,
            )
            applied_versions.append(migration.version)

    return applied_versions


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run chatbot-service PostgreSQL migrations")
    parser.add_argument("--dsn", default="", help="PostgreSQL DSN. Defaults to CHATBOT_DB_DSN.")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help="Directory containing chatbot migration SQL files.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List discovered migrations without connecting to PostgreSQL.",
    )
    args = parser.parse_args(argv)

    migrations = discover_migrations(args.migrations_dir)
    if args.list:
        for migration in migrations:
            print(f"{migration.version} {migration.checksum} {migration.path}")
        return

    dsn = args.dsn or load_config().db_dsn
    applied = asyncio.run(apply_migrations(dsn, args.migrations_dir))
    if applied:
        print("Applied chatbot migrations: " + ", ".join(applied))
    else:
        print("No chatbot migrations to apply.")


__all__ = [
    "Migration",
    "MigrationError",
    "apply_migrations",
    "default_migrations_dir",
    "discover_migrations",
]
