"""Refresh catalogs from the staged tree, without binding unfinished work."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]

def main():
    tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, text=True).strip()
    folder = ROOT / '.runtime' / 'v2-staged' / uuid4().hex
    folder.mkdir(parents=True)
    archive = subprocess.check_output(['git', 'archive', '--format=tar', tree], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
        contents.extractall(folder, filter='data')
    env = os.environ.copy()
    for key in ('DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'COLLABORATION_DEV_SESSIONS_JSON'):
        env.pop(key, None)
    env.update(PROJECT_ROOT=str(folder), PYTHONPATH=str(folder),
               NOVEL_DATA_PATH=str(folder / '.profile' / 'data'),
               LOCALAPPDATA=str(folder / '.profile' / 'Local'),
               CREDENTIAL_VAULT_BACKEND='memory', STORAGE_BACKEND='file',
               ENABLE_PACKAGED_RUNTIME='false', ENABLE_COLLABORATION_RUNTIME='false',
               PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-B', 'scripts/refresh_product_api_catalog.py'],
                            cwd=folder, env=env, capture_output=True, text=True, encoding='utf-8',
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    print(result.stdout + result.stderr)
    result.check_returncode()
    hashes = {}
    for name in ('API_CATALOG.json', 'API_CATALOG.md', 'API_CATALOG_DETAIL.json.gz', 'API_OPENAPI.json.gz'):
        value = (folder / name).read_bytes()
        (ROOT / name).write_bytes(value)
        hashes[name] = hashlib.sha256(value).hexdigest()
    evidence = ROOT / 'docs' / 'delivery' / 'v2-development' / f'catalog-{tree[:12]}.json'
    evidence.write_text(json.dumps({'staged_tree': tree, 'utc': datetime.now(timezone.utc).isoformat(),
                                   'command': [sys.executable, '-B', 'scripts/refresh_product_api_catalog.py'],
                                   'cwd': str(folder), 'exit_code': result.returncode,
                                   'sha256': hashes}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'snapshot': str(folder), 'receipt': str(evidence)}))

if __name__ == '__main__':
    main()
