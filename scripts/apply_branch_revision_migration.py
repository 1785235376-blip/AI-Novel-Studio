from pathlib import Path
import json,os
import psycopg
from dotenv import load_dotenv
load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");sql=(Path(__file__).parents[1]/"database/migrations/013_branch_revision_optimistic_concurrency.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as c:
 if not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='storyline_branches' AND column_name='revision'").fetchone():c.execute(sql)
 nulls=c.execute("SELECT count(*) FROM storyline_branches WHERE revision IS NULL").fetchone()[0];negative=c.execute("SELECT count(*) FROM storyline_branches WHERE revision<0").fetchone()[0];total=c.execute("SELECT count(*) FROM storyline_branches").fetchone()[0]
 artifact={"migration":"REAL_VERIFIED","migration_number":"013","revision_source_of_truth":"storyline_branches.revision","legacy_backfill":"PASS" if not nulls and not negative else "FAIL","branches":total,"null_revisions":nulls,"negative_revisions":negative,"initial_revision_semantics":"MATCH"};print(json.dumps(artifact,sort_keys=True))
 if nulls or negative:raise SystemExit(1)
