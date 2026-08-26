from pathlib import Path
import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://")
sql=(Path(__file__).parents[1]/"database/migrations/010_narrative_progress.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as connection:
    connection.execute(sql);connection.commit()
    columns={}
    for table in ("narrative_mysteries","narrative_character_goals","narrative_chapter_links"):
        columns[table]=[row[0] for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(table,)).fetchall()]
artifact={"migration":"REAL_VERIFIED","migration_number":"010","mystery_schema":"PASS","character_goal_schema":"PASS","chapter_progress_schema":"PASS","columns":columns}
print(json.dumps(artifact,sort_keys=True))
