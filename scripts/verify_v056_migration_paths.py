from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


ROOT = Path(__file__).parents[1]
MIGRATIONS = sorted((ROOT / "database" / "migrations").glob("*.sql"))


def apply(url: str, migrations: list[Path]) -> None:
    with psycopg.connect(url) as connection:
        for migration in migrations:
            connection.execute(migration.read_text(encoding="utf-8"))


def validate(url: str) -> dict:
    with psycopg.connect(url) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )}
        version = bool(connection.execute(
            "SELECT 1 FROM schema_versions WHERE version='0.5.6-collaboration-runtime-foundation'"
        ).fetchone())
        return {
            "tables": all(name in tables for name in ("users", "workspace_memberships", "chapter_versions", "chapter_context_snapshots")),
            "schema_version": version,
            "legacy_preserved": connection.execute(
                "SELECT count(*) FROM chapter_versions WHERE operator='legacy-v056-probe'"
            ).fetchone()[0] in (0, 1),
        }


def main() -> None:
    load_dotenv(ROOT / ".env")
    raw = (os.getenv("TEST_POSTGRES_DATABASE_URL") or os.environ["DATABASE_URL"]).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    parts = conninfo_to_dict(raw)
    admin_url = make_conninfo(**{**parts, "dbname": "postgres"})
    names = [f"v056_fresh_{uuid4().hex[:10]}", f"v056_upgrade_{uuid4().hex[:10]}"]
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        fresh_url = make_conninfo(**{**parts, "dbname": names[0]})
        upgrade_url = make_conninfo(**{**parts, "dbname": names[1]})
        apply(fresh_url, MIGRATIONS)
        apply(upgrade_url, MIGRATIONS[:-2])
        with psycopg.connect(upgrade_url) as connection:
            novel = connection.execute(
                "INSERT INTO novels(slug,title) VALUES ('legacy-v056','Legacy') RETURNING id"
            ).fetchone()[0]
            chapter = connection.execute(
                "INSERT INTO chapters(novel_id,chapter_number,title,markdown_path,document) "
                "VALUES (%s,1,'Legacy','chapters/legacy.md','{}'::jsonb) RETURNING id", (novel,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO chapter_versions(chapter_id,version,document,operator,source) "
                "VALUES (%s,1,'{}'::jsonb,'legacy-v056-probe','USER')", (chapter,),
            )
        apply(upgrade_url, MIGRATIONS[-2:])
        # Mirror the guarded runner: a second invocation observes the membership table
        # and must leave both schema and existing rows untouched.
        before = validate(upgrade_url)
        with psycopg.connect(upgrade_url) as connection:
            assert connection.execute(
                "SELECT source,actor_id,session_id,scope_type,scope_id,metadata,reason "
                "FROM chapter_versions WHERE operator='legacy-v056-probe'"
            ).fetchone() == ("USER", None, None, None, None, {}, "MANUAL_SAVE")
        with psycopg.connect(upgrade_url) as connection:
            for migration, version in (
                (MIGRATIONS[-2], "0.5.6-collaboration-runtime-foundation"),
                (MIGRATIONS[-1], "0.5.6-generation-snapshot-ownership"),
            ):
                if not connection.execute("SELECT 1 FROM schema_versions WHERE version=%s", (version,)).fetchone():
                    connection.execute(migration.read_text(encoding="utf-8"))
        after = validate(upgrade_url)
        result = {"fresh_001_latest": validate(fresh_url), "upgrade_014_latest": before,
                  "repeat_runner": before == after}
        print(json.dumps(result, sort_keys=True))
        if not all(result[mode]["tables"] and result[mode]["schema_version"] for mode in ("fresh_001_latest", "upgrade_014_latest")) or not result["repeat_runner"]:
            raise SystemExit(1)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            for name in names:
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
