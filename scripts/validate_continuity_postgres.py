import json
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
with psycopg.connect(url) as conn:
    version = conn.execute("SELECT version()").fetchone()[0]
    columns = conn.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND (table_name LIKE 'continuity_%' OR table_name IN ('timeline_events','character_location_states','relationship_states','canon_dependencies','character_knowledge')) ORDER BY table_name,column_name").fetchall()
print(json.dumps({"version": version.split(",")[0], "columns": columns}, ensure_ascii=False))
