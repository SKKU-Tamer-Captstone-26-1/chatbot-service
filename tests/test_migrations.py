from __future__ import annotations

from pathlib import Path

import pytest

from chatbot_service.storage.migrations import (
    Migration,
    MigrationError,
    _apply_migrations_on_connection,
    discover_migrations,
)


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self, applied: dict[str, str] | None = None) -> None:
        self.applied = applied or {}
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append((sql, args))
        if "INSERT INTO chatbot_schema_migrations" in sql:
            self.applied[str(args[0])] = str(args[1])

    async def fetch(self, sql: str):
        self.executed.append((sql, ()))
        return [
            {"version": version, "checksum": checksum}
            for version, checksum in self.applied.items()
        ]


def test_discover_migrations_returns_sorted_checksummed_files(tmp_path):
    (tmp_path / "002_second.sql").write_text("SELECT 2;\n", encoding="utf-8")
    (tmp_path / "001_first.sql").write_text("SELECT 1;\n", encoding="utf-8")

    migrations = discover_migrations(tmp_path)

    assert [migration.version for migration in migrations] == ["001_first", "002_second"]
    assert all(len(migration.checksum) == 64 for migration in migrations)


def test_discover_migrations_rejects_invalid_filename(tmp_path):
    (tmp_path / "first.sql").write_text("SELECT 1;\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="Invalid migration filename"):
        discover_migrations(tmp_path)


@pytest.mark.anyio
async def test_apply_migrations_records_only_pending_versions():
    first = Migration("001_first", path=Path("001_first.sql"), sql="SELECT 1;", checksum="same")
    second = Migration("002_second", path=Path("002_second.sql"), sql="SELECT 2;", checksum="new")
    connection = FakeConnection(applied={"001_first": "same"})

    applied = await _apply_migrations_on_connection(connection, [first, second])

    assert applied == ["002_second"]
    assert connection.applied["002_second"] == "new"
    assert any(sql == "SELECT 2;" for sql, _ in connection.executed)
    assert not any(sql == "SELECT 1;" for sql, _ in connection.executed)


@pytest.mark.anyio
async def test_apply_migrations_rejects_changed_applied_checksum():
    migration = Migration(
        "001_first",
        path=Path("001_first.sql"),
        sql="SELECT 1;",
        checksum="changed",
    )
    connection = FakeConnection(applied={"001_first": "old"})

    with pytest.raises(MigrationError, match="checksum changed"):
        await _apply_migrations_on_connection(connection, [migration])
