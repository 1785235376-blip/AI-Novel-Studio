from pathlib import Path
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
sql = (Path(__file__).parents[1] / "database" / "migrations" / "007_continuity_foundations.sql").read_text(encoding="utf-8")
with psycopg.connect(url) as conn:
    conn.execute(sql)
    conn.commit()
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'continuity_%' ORDER BY table_name").fetchall()
print({"status": "REAL VERIFIED", "tables": [row[0] for row in tables]})
