from pathlib import Path
import os
import psycopg
from dotenv import load_dotenv

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");root=Path(__file__).parents[1]/"database/migrations"
with psycopg.connect(url) as connection:
    for name in ("004_lore_foundation.sql","005_lore_memory.sql"):connection.execute((root/name).read_text(encoding="utf-8"));connection.commit()
print("LORE_MIGRATIONS_004_005_REAL_VERIFIED")
