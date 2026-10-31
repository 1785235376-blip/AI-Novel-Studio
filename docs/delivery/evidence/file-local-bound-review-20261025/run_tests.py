import os, socket, sys
from pathlib import Path
root = Path(__file__).resolve().parents[4]
run = root / '.runtime/file-local-bound-review'
for folder in ('home', 'xdg', 'data', 'tmp'):
    (run / folder).mkdir(parents=True, exist_ok=True)
for key in tuple(os.environ):
    if key.endswith('_API_KEY') or key in {'DATABASE_URL','TEST_POSTGRES_DATABASE_URL','E2E_DATABASE_URL'}:
        os.environ.pop(key)
os.environ.update(PROJECT_ROOT=str(root), PYTHONPATH=str(root), HOME=str(run/'home'),
    XDG_CONFIG_HOME=str(run/'xdg'), XDG_CACHE_HOME=str(run/'xdg/cache'), XDG_DATA_HOME=str(run/'xdg/data'),
    NOVEL_DATA_PATH=str(run/'data'), TMPDIR=str(run/'tmp'), STORAGE_BACKEND='file', CREDENTIAL_VAULT_BACKEND='memory')
os.chdir(root)
sys.path.insert(0,str(root))
sys.path.insert(0,str(root / "tests"))
def blocked(*args, **kwargs):
    raise RuntimeError('network blocked for isolated review port blocker tests')
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
import pytest
if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
