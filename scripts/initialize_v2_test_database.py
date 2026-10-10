"""Initialize only the disposable V2 test database using existing migrations."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parents[1]
URL = 'postgresql://postgres@127.0.0.1:55432/v2_creative_tests'

def main():
    migrations = sorted((ROOT / 'database' / 'migrations').glob('*.sql'))
    with psycopg.connect(URL) as connection:
        if connection.execute("SELECT to_regclass('public.novels')").fetchone()[0]:
            raise RuntimeError('Owned database already initialized; refusing to replay migrations')
        for migration in migrations:
            connection.execute(migration.read_text(encoding='utf-8'))
    receipt = {'utc': datetime.now(timezone.utc).isoformat(), 'endpoint': '127.0.0.1:55432/v2_creative_tests',
               'exit_code': 0, 'migrations': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in migrations}}
    target = ROOT / 'docs' / 'delivery' / 'v2-development' / 'postgres-initialization.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))

if __name__ == '__main__':
    main()
