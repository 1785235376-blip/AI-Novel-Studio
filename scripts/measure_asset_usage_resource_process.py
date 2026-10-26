"""Fresh original application process; synthetic initialized data, warm OS cache."""
from pathlib import Path
import json
import os
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
data, nid, aid, output = sys.argv[1:]
os.environ.update(NOVEL_DATA_PATH=data, STORAGE_BACKEND='file', MOCK_PROVIDER='true',
    ENABLE_CLOUD='false', ENABLE_PACKAGED_RUNTIME='false', ENABLE_COLLABORATION_RUNTIME='false',
    EXPERIMENTAL_FEATURES='narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2')
for key in tuple(os.environ):
    if key.endswith('_API_KEY') or key in {'DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'E2E_DATABASE_URL'}:
        os.environ.pop(key, None)
original_connect = socket.socket.connect
def connect(sock, address):
    if sock.family in {socket.AF_INET, socket.AF_INET6} and address[0] not in {'127.0.0.1', '::1', 'localhost'}:
        raise RuntimeError('external networking forbidden in synthetic resource measurement')
    return original_connect(sock, address)
socket.socket.connect = connect

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from app import main, api
from app.actor_context import SessionContext
from studio_asset_usage_fixture import snapshot
from studio_asset_usage_resource_meter import four_page_observations

api.trusted_session_resolver.register('synthetic-resource-host',
    SessionContext('synthetic-resource-session', 'synthetic-resource-client', 'local-author', 'synthetic-resource-workspace'))
before = snapshot(Path(data))
with TestClient(main.app) as client:
    records = four_page_observations(client, Path(data), nid, aid,
        {'X-Session-Token': 'synthetic-resource-host'}, MonkeyPatch())
assert snapshot(Path(data)) == before
Path(output).write_text(json.dumps({'pid': os.getpid(),
    'phase': 'new interpreter original main.app HTTP; imports/startup excluded; OS cache not cleared',
    'records': records}, indent=2), encoding='utf-8')
print('FRESH_RESOURCE_COSTS_JSON ' + output, flush=True)
