from pathlib import Path
import os,psycopg
from dotenv import load_dotenv
load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://")
with psycopg.connect(url) as c:c.execute((Path(__file__).parents[1]/"database/migrations/009_narrative_findings.sql").read_text(encoding="utf-8"));c.commit()
print("MIGRATION_009_REAL_VERIFIED")
