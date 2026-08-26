from __future__ import annotations

from pathlib import Path

import pytest

from app.packaging.postgres_migrations import (
    BASELINE_ID,
    PackagedMigration,
    PackagedMigrationError,
    PackagedPostgresMigrationRunner,
    baseline_adoption_sql,
    baseline_checksum,
    load_packaged_migrations,
    migration_apply_sql,
    readiness_sql,
)


ROOT = Path(__file__).resolve().parents[1]


def test_registry_is_stable_and_checksummed():
    migrations = load_packaged_migrations(ROOT / "database" / "migrations")
    assert [item.migration_id for item in migrations] == ["0001_chapter_archive_state"]
    assert len(migrations[0].checksum) == 64
    assert len(baseline_checksum()) == 64
    assert "is_archived" in migrations[0].sql


def test_baseline_requires_lock_and_adopts_only_ledger():
    sql = baseline_adoption_sql()
    assert "pg_advisory_xact_lock" in sql
    assert "CREATE TABLE schema_migrations" in sql
    assert "chapters" in sql and "is_archived" in sql
    assert "DROP TABLE" not in sql.upper()
    assert "DELETE FROM" not in sql.upper()


def test_apply_is_transactional_and_checksum_guarded():
    migration = load_packaged_migrations(ROOT / "database" / "migrations")[0]
    sql = migration_apply_sql(migration, BASELINE_ID)
    assert sql.startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "checksum mismatch" in sql
    assert "INSERT INTO schema_migrations" in sql


def test_readiness_checks_all_registered_migrations():
    migrations = load_packaged_migrations(ROOT / "database" / "migrations")
    sql = readiness_sql(migrations)
    assert BASELINE_ID in sql
    assert migrations[0].migration_id in sql
    assert "is_archived" in sql


def test_runner_applies_in_order_and_is_fail_closed():
    migrations = (
        PackagedMigration("0001", "one", "SELECT 1", "one-checksum"),
        PackagedMigration("0002", "two", "SELECT 2", "two-checksum"),
    )
    calls: list[str] = []
    runner = PackagedPostgresMigrationRunner(
        migrations_path=ROOT / "database" / "migrations",
        migrations=migrations,
        execute_sql=calls.append,
    )
    runner.run()
    assert len(calls) == 4
    assert "0001" in calls[1]
    assert "0002" in calls[2]
    assert "0000_packaged_v070_baseline" in calls[0]

    failed = PackagedPostgresMigrationRunner(
        migrations_path=ROOT / "database" / "migrations",
        migrations=(migrations[0],),
        execute_sql=lambda _sql: (_ for _ in ()).throw(RuntimeError("forced migration failure")),
    )
    with pytest.raises(PackagedMigrationError, match="小说数据升级未完成"):
        failed.run()
