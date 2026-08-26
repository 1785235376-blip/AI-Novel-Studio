from pathlib import Path
import json
import os

import psycopg
from dotenv import load_dotenv


load_dotenv()
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
sql = (Path(__file__).parents[1] / "database/migrations/015_collaboration_runtime_foundation.sql").read_text(encoding="utf-8")
snapshot_sql = (Path(__file__).parents[1] / "database/migrations/016_generation_snapshot_ownership.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as connection:
    exists = connection.execute("SELECT 1 FROM information_schema.tables WHERE table_name='workspace_memberships'").fetchone()
    if not exists:
        connection.execute(sql)
    snapshot_version = connection.execute("SELECT 1 FROM schema_versions WHERE version='0.5.6-generation-snapshot-ownership'").fetchone()
    if not snapshot_version:
        connection.execute(snapshot_sql)
    tables = ("users", "workspace_memberships", "chapter_versions", "chapter_context_snapshots", "generation_jobs")
    missing = [table for table in tables if not connection.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s", (table,)).fetchone()]
    required_columns = {
        "chapter_versions": ("actor_id", "session_id", "scope_type", "scope_id", "metadata", "reason"),
        "chapter_context_snapshots": ("actor_id", "session_id", "scope_type", "scope_id", "context_mode", "ordering", "budget"),
        "generation_jobs": ("context_snapshot_id",),
    }
    missing_columns = []
    for table, columns in required_columns.items():
        for column in columns:
            if not connection.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column)).fetchone():
                missing_columns.append(f"{table}.{column}")
    version = bool(connection.execute("SELECT 1 FROM schema_versions WHERE version='0.5.6-collaboration-runtime-foundation'").fetchone())
    snapshot_version = bool(connection.execute("SELECT 1 FROM schema_versions WHERE version='0.5.6-generation-snapshot-ownership'").fetchone())
    artifact = {"migration": "REAL_VERIFIED" if not missing and not missing_columns and version and snapshot_version else "FAIL", "migration_number": "016", "missing_tables": missing, "missing_columns": missing_columns, "schema_version": version, "snapshot_ownership_version": snapshot_version}
    print(json.dumps(artifact, sort_keys=True))
    if missing or missing_columns or not version or not snapshot_version:
        raise SystemExit(1)
