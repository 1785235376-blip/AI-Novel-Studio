from pathlib import Path
import json,os
import psycopg
from dotenv import load_dotenv

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");sql=(Path(__file__).parents[1]/"database/migrations/012_collaboration_scope_foundation.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as connection:
 if not connection.execute("SELECT to_regclass('public.workspaces')").fetchone()[0]:connection.execute(sql)
 connection.execute("ALTER TABLE novels ALTER COLUMN workspace_id SET DEFAULT 'default-workspace'")
 tables={name:bool(connection.execute("SELECT to_regclass(%s)",(f"public.{name}",)).fetchone()[0]) for name in ("workspaces","project_workspaces","storylines","storyline_branches")}
 orphans=connection.execute("SELECT count(*) FROM novels n LEFT JOIN project_workspaces p ON p.project_id=n.slug WHERE p.project_id IS NULL").fetchone()[0]
 scope_columns={table:[x[0] for x in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s AND column_name IN ('storyline_id','branch_id') ORDER BY column_name",(table,)).fetchall()] for table in ("narrative_events","narrative_expectations","narrative_findings","narrative_change_proposals")}
 artifact={"migration":"REAL_VERIFIED","migration_number":"012","tables":tables,"legacy_project_backfill":"PASS" if orphans==0 else "FAIL","orphan_projects":orphans,"scope_columns":scope_columns};print(json.dumps(artifact,sort_keys=True))
 if not all(tables.values()) or orphans or any(len(x)!=2 for x in scope_columns.values()):raise SystemExit(1)
