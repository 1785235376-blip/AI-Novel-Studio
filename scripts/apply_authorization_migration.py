from pathlib import Path
import json,os
import psycopg
from dotenv import load_dotenv

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://")
sql=(Path(__file__).parents[1]/"database/migrations/014_scope_authorization_foundation.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as c:
 if not c.execute("SELECT 1 FROM information_schema.tables WHERE table_name='domain_role_assignments'").fetchone():c.execute(sql)
 tables=("domain_role_assignments","permission_assignments","authorization_audit_events")
 missing=[table for table in tables if not c.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s",(table,)).fetchone()]
 version=bool(c.execute("SELECT 1 FROM schema_versions WHERE version='0.5.5-scope-authorization-foundation'").fetchone())
 artifact={"migration":"REAL_VERIFIED" if not missing and version else "FAIL","migration_number":"014","missing_tables":missing,"schema_version":version};print(json.dumps(artifact,sort_keys=True))
 if missing or not version:raise SystemExit(1)
