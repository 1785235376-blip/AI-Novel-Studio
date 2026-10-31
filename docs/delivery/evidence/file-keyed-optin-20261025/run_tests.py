import os, socket, sys
from pathlib import Path
root = next(parent for parent in Path(__file__).resolve().parents
    if (parent / 'pyproject.toml').is_file() and (parent / 'app/jobs.py').is_file())
run = root / '.runtime/file-keyed-optin/mock-mode'
for folder in ('home', 'xdg', 'data', 'tmp'):
    (run / folder).mkdir(parents=True, exist_ok=True)
for key in tuple(os.environ):
    if key.endswith('_API_KEY') or key in {'DATABASE_URL','TEST_POSTGRES_DATABASE_URL','E2E_DATABASE_URL'}:
        os.environ.pop(key)
# Exercise the shipped default; only activation fixtures opt in explicitly.
os.environ.pop('ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION', None)
os.environ.update(PROJECT_ROOT=str(root), PYTHONPATH=str(root), HOME=str(run/'home'),
    XDG_CONFIG_HOME=str(run/'xdg'), XDG_CACHE_HOME=str(run/'xdg/cache'), XDG_DATA_HOME=str(run/'xdg/data'),
    NOVEL_DATA_PATH=str(run/'data'), TMPDIR=str(run/'tmp'), STORAGE_BACKEND='file', CREDENTIAL_VAULT_BACKEND='memory',
    MOCK_PROVIDER='true', ENABLE_PACKAGED_RUNTIME='false', ENABLE_CLOUD='false', CREATION_PROFILE='LOCAL_ONLY')
os.chdir(root)
sys.path.insert(0,str(root))
sys.path.insert(0,str(root / "tests"))
def blocked(*args, **kwargs):
    raise RuntimeError('network blocked for isolated review port blocker tests')
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
import json
from app.config import settings
from app.dependencies import adaptation_service
from app.providers import MockProvider
actual = getattr(getattr(adaptation_service.runtime, '_deepseek_provider_adapter', None), 'provider', None)
predicate = dict(mock_provider=settings.mock_provider, packaged=settings.enable_packaged_runtime,
    actual_provider_type=type(actual).__module__+'.'+type(actual).__name__,
    actual_mock=isinstance(actual, MockProvider), remote=adaptation_service.runtime.is_remote_text_provider('deepseek'))
print('ACTUAL_ORIGINAL_SYNTHETIC_PREDICATE '+json.dumps(predicate, sort_keys=True), flush=True)
assert predicate['mock_provider'] and not predicate['packaged'] and predicate['actual_mock'] and not predicate['remote']
import pytest
if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
