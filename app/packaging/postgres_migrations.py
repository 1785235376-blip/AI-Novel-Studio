from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


MIGRATION_FAILURE = "小说数据升级未完成，程序已停止启动。你的原始数据仍保留。"
MIGRATION_LOCK_KEY = "ai-novel-studio:packaged-schema-migrations:v1"
BASELINE_ID = "0000_packaged_v070_baseline"


class PackagedMigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PackagedMigration:
    migration_id: str
    name: str
    sql: str
    checksum: str

    @classmethod
    def from_file(cls, migration_id: str, name: str, path: Path) -> "PackagedMigration":
        sql = path.read_text(encoding="utf-8").strip()
        if not sql or "BEGIN" in sql.upper() or "COMMIT" in sql.upper():
            raise PackagedMigrationError("packaged migration must contain transaction-neutral SQL")
        return cls(migration_id, name, sql, hashlib.sha256(sql.encode("utf-8")).hexdigest())


def baseline_checksum() -> str:
    return hashlib.sha256(json.dumps(
        _BASELINE_FINGERPRINT, ensure_ascii=True, separators=(",", ":"), sort_keys=True,
    ).encode("ascii")).hexdigest()


def load_packaged_migrations(migrations: Path) -> tuple[PackagedMigration, ...]:
    return (PackagedMigration.from_file(
        "0001_chapter_archive_state", "chapter archive state",
        migrations / "017_chapter_archive_state.sql",
    ),)


_BASELINE_FINGERPRINT = {
    "required_tables": (
        "novels", "chapters", "chapter_versions", "chapter_summaries",
        "chapter_context_snapshots", "generation_jobs", "workspaces", "users",
        "workspace_memberships", "project_workspaces", "storylines",
        "storyline_branches", "authorization_audit_events",
    ),
    "required_columns": (
        ("novels", "id", "uuid", "NO"),
        ("novels", "slug", "text", "NO"),
        ("chapters", "id", "uuid", "NO"),
        ("chapters", "novel_id", "uuid", "NO"),
        ("chapters", "chapter_number", "int4", "NO"),
        ("chapters", "workflow_status", "text", "NO"),
        ("chapters", "document", "jsonb", "YES"),
        ("chapters", "version", "int4", "NO"),
        ("chapter_versions", "chapter_id", "uuid", "NO"),
        ("chapter_summaries", "chapter_id", "uuid", "NO"),
        ("chapter_context_snapshots", "chapter_id", "uuid", "NO"),
        ("generation_jobs", "chapter_id", "uuid", "YES"),
        ("generation_jobs", "context_snapshot_id", "uuid", "YES"),
        ("workspace_memberships", "user_id", "text", "NO"),
        ("workspace_memberships", "workspace_id", "text", "NO"),
        ("project_workspaces", "project_id", "text", "NO"),
        ("project_workspaces", "workspace_id", "text", "NO"),
    ),
    "required_constraints": (
        ("chapters", "FOREIGN KEY", "novel_id", "novels", "CASCADE"),
        ("chapter_versions", "FOREIGN KEY", "chapter_id", "chapters", "CASCADE"),
        ("chapter_summaries", "FOREIGN KEY", "chapter_id", "chapters", "CASCADE"),
        ("chapter_context_snapshots", "FOREIGN KEY", "chapter_id", "chapters", "CASCADE"),
        ("generation_jobs", "FOREIGN KEY", "chapter_id", "chapters", "SET NULL"),
        ("generation_jobs", "FOREIGN KEY", "context_snapshot_id", "chapter_context_snapshots", "RESTRICT"),
    ),
}


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _values(rows: Iterable[tuple[str, ...]]) -> str:
    return ",\n".join("(" + ",".join(_literal(value) for value in row) + ")" for row in rows)


def _lock_sql() -> str:
    return f"SELECT pg_advisory_xact_lock(hashtextextended({_literal(MIGRATION_LOCK_KEY)},0));"


def baseline_adoption_sql() -> str:
    tables = ",".join(_literal(name) for name in _BASELINE_FINGERPRINT["required_tables"])
    columns = _values(_BASELINE_FINGERPRINT["required_columns"])
    constraints = _values(_BASELINE_FINGERPRINT["required_constraints"])
    checksum = baseline_checksum()
    return f"""
BEGIN;
{_lock_sql()}
DO $migration$
DECLARE ledger_exists boolean := to_regclass('public.schema_migrations') IS NOT NULL;
BEGIN
  IF ledger_exists THEN
    IF (SELECT count(*) FROM information_schema.columns
        WHERE table_schema='public' AND table_name='schema_migrations') <> 3
       OR EXISTS (
         SELECT 1 FROM (VALUES
           ('migration_id','text','NO'),('applied_at','timestamp with time zone','NO'),('checksum','text','NO')
         ) expected(column_name,data_type,is_nullable)
         LEFT JOIN information_schema.columns actual
           ON actual.table_schema='public' AND actual.table_name='schema_migrations'
          AND actual.column_name=expected.column_name
         WHERE actual.column_name IS NULL OR actual.data_type<>expected.data_type
            OR actual.is_nullable<>expected.is_nullable
       )
       OR NOT EXISTS (
         SELECT 1 FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
         WHERE t.relname='schema_migrations' AND c.contype='p'
           AND pg_get_constraintdef(c.oid)='PRIMARY KEY (migration_id)'
       ) THEN
      RAISE EXCEPTION 'incompatible schema_migrations ledger';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM schema_migrations
                   WHERE migration_id={_literal(BASELINE_ID)} AND checksum={_literal(checksum)}) THEN
      RAISE EXCEPTION 'missing or mismatched packaged baseline ledger record';
    END IF;
    RETURN;
  END IF;

  IF EXISTS (SELECT required.name FROM unnest(ARRAY[{tables}]) required(name)
             WHERE to_regclass('public.'||required.name) IS NULL) THEN
    RAISE EXCEPTION 'legacy baseline required table missing';
  END IF;
  IF EXISTS (
    SELECT 1 FROM (VALUES
      {columns}
    ) expected(table_name,column_name,udt_name,is_nullable)
    LEFT JOIN information_schema.columns actual
      ON actual.table_schema='public' AND actual.table_name=expected.table_name
     AND actual.column_name=expected.column_name
    WHERE actual.column_name IS NULL OR actual.udt_name<>expected.udt_name
       OR actual.is_nullable<>expected.is_nullable
  ) THEN
    RAISE EXCEPTION 'legacy baseline critical column mismatch';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='chapters' AND column_name='is_archived') THEN
    RAISE EXCEPTION 'ambiguous partially applied chapter archive migration';
  END IF;
  IF EXISTS (
    SELECT 1 FROM (VALUES
      {constraints}
    ) expected(table_name,constraint_type,column_name,foreign_table,delete_rule)
    WHERE NOT EXISTS (
      SELECT 1 FROM information_schema.table_constraints tc
      JOIN information_schema.key_column_usage kcu
        ON kcu.constraint_schema=tc.constraint_schema AND kcu.constraint_name=tc.constraint_name
      JOIN information_schema.referential_constraints rc
        ON rc.constraint_schema=tc.constraint_schema AND rc.constraint_name=tc.constraint_name
      JOIN information_schema.constraint_column_usage ccu
        ON ccu.constraint_schema=rc.unique_constraint_schema AND ccu.constraint_name=rc.unique_constraint_name
      WHERE tc.table_schema='public' AND tc.table_name=expected.table_name
        AND tc.constraint_type=expected.constraint_type AND kcu.column_name=expected.column_name
        AND ccu.table_name=expected.foreign_table AND rc.delete_rule=expected.delete_rule
    )
  ) THEN
    RAISE EXCEPTION 'legacy baseline critical constraint mismatch';
  END IF;

  CREATE TABLE schema_migrations(
    migration_id text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now(),
    checksum text NOT NULL
  );
  INSERT INTO schema_migrations(migration_id,checksum)
  VALUES ({_literal(BASELINE_ID)},{_literal(checksum)});
END
$migration$;
COMMIT;
""".strip()


def migration_apply_sql(migration: PackagedMigration, previous_id: str) -> str:
    escaped_sql = migration.sql.replace("'", "''")
    return f"""
BEGIN;
{_lock_sql()}
DO $migration$
DECLARE recorded text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migrations WHERE migration_id={_literal(migration.migration_id)};
  IF recorded IS NOT NULL THEN
    IF recorded<>{_literal(migration.checksum)} THEN
      RAISE EXCEPTION 'applied migration checksum mismatch: {migration.migration_id}';
    END IF;
    RETURN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE migration_id={_literal(previous_id)}) THEN
    RAISE EXCEPTION 'previous migration missing: {previous_id}';
  END IF;
  EXECUTE '{escaped_sql}';
  INSERT INTO schema_migrations(migration_id,checksum)
  VALUES ({_literal(migration.migration_id)},{_literal(migration.checksum)});
END
$migration$;
COMMIT;
""".strip()


def readiness_sql(migrations: Iterable[PackagedMigration]) -> str:
    checks = [(BASELINE_ID, baseline_checksum()), *(
        (migration.migration_id, migration.checksum) for migration in migrations
    )]
    values = _values(tuple(checks))
    return f"""
BEGIN;
{_lock_sql()}
DO $migration$
BEGIN
  IF EXISTS (
    SELECT 1 FROM (VALUES {values}) expected(migration_id,checksum)
    LEFT JOIN schema_migrations actual USING(migration_id)
    WHERE actual.migration_id IS NULL OR actual.checksum<>expected.checksum
  ) THEN RAISE EXCEPTION 'packaged migration ledger is not ready'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='chapters' AND column_name='is_archived'
      AND udt_name='bool' AND is_nullable='NO'
      AND column_default IN ('false','false::boolean')
  ) THEN RAISE EXCEPTION 'chapter archive schema is not ready'; END IF;
END
$migration$;
COMMIT;
""".strip()


class PackagedPostgresMigrationRunner:
    def __init__(
        self, *, migrations_path: Path,
        execute_sql: Callable[[str], object],
        log: Callable[[str], None] | None = None,
        migrations: tuple[PackagedMigration, ...] | None = None,
    ):
        self.migrations = migrations or load_packaged_migrations(migrations_path)
        self.execute_sql = execute_sql
        self.log = log or (lambda _message: None)

    def run(self) -> None:
        self.log("packaged migration runner start")
        try:
            self.execute_sql(baseline_adoption_sql())
            self.log("packaged migration baseline ready")
            previous = BASELINE_ID
            for migration in self.migrations:
                self.log(f"packaged migration verify/apply {migration.migration_id}")
                self.execute_sql(migration_apply_sql(migration, previous))
                previous = migration.migration_id
            self.execute_sql(readiness_sql(self.migrations))
        except Exception as exc:
            self.log(f"packaged migration failed: {type(exc).__name__}")
            raise PackagedMigrationError(MIGRATION_FAILURE) from exc
        self.log("packaged migration schema ready")
