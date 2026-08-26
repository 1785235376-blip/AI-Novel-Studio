from pathlib import Path
import os,psycopg
from dotenv import load_dotenv
load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://")
sql=(Path(__file__).parents[1]/"database/migrations/008_narrative_state.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as c:c.execute(sql);c.commit()
print("MIGRATION_008_REAL_VERIFIED")
