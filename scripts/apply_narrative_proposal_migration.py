from pathlib import Path
import json,os
import psycopg
from dotenv import load_dotenv

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://")
sql=(Path(__file__).parents[1]/"database/migrations/011_narrative_change_proposals.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as connection:
    exists=connection.execute("SELECT to_regclass('public.narrative_change_proposals')").fetchone()[0]
    if not exists:connection.execute(sql)
    columns=[row[0] for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='narrative_change_proposals' ORDER BY ordinal_position").fetchall()]
    unique=connection.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='narrative_change_proposals'::regclass AND contype='u' AND pg_get_constraintdef(oid) LIKE '%project_id, fingerprint%'").fetchone()[0]
artifact={"migration":"REAL_VERIFIED","migration_number":"011","table":"narrative_change_proposals","columns":columns,"project_fingerprint_unique":"PASS" if unique else "FAIL"}
print(json.dumps(artifact,sort_keys=True));
if not columns or not unique:raise SystemExit(1)
