"""Fresh-process, original main.app mixed query measurement on synthetic data.

Invoked only by the fixture test. OS caches are never cleared or claimed cold.
"""
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
        raise RuntimeError('external network forbidden in synthetic process measurement')
    return original_connect(sock, address)
socket.socket.connect = connect

from types import SimpleNamespace
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from app import main, api
from app.actor_context import SessionContext
from app.experimental import api as experimental
from studio_asset_usage_meter import measured
from studio_asset_usage_fixture import snapshot

api.trusted_session_resolver.register('synthetic-process-host',
    SessionContext('synthetic-process-session', 'synthetic-process-client', 'local-author', 'synthetic-process-workspace'))
e = SimpleNamespace(rig=SimpleNamespace(root=Path(data)), graph=experimental.creative_graph_service,
                    production=experimental.studio_production_service)
before = snapshot(Path(data))
runs = []
with TestClient(main.app) as client:
    for phase in ('cold-process-first-query-warm-os-cache', 'warm-process-repeat-query'):
        cursor, found, pages = None, [], []
        for page in range(100):
            params = {'limit': 100}
            if cursor:
                params['cursor'] = cursor
            response, metrics = measured(e, MonkeyPatch(), lambda: client.get(
                f'/api/novels/{nid}/experimental/production/assets/{aid}/studio-asset-usages',
                params=params, headers={'X-Session-Token': 'synthetic-process-host'}))
            assert response.status_code == 200, response.text
            body = response.json()
            found.extend((r['owner'], r['id'], r.get('node_id', r.get('clip_id'))) for r in body['items'])
            pages.append({'page': page, 'response_bytes': len(response.content),
                'returned': len(body['items']), 'scanned_consumers': body['scanned_consumers'],
                'scanned_references': body['scanned_references'], **metrics})
            assert metrics['write_calls'] == 0
            if not body['has_more']:
                assert body['total'] == 540
                break
            cursor = body['next_cursor']
        assert len(found) == len(set(found)) == 540
        runs.append({'phase': phase, 'pid': os.getpid(), 'entry': 'fresh original main.app mounted HTTP', 'pages': pages})
assert snapshot(Path(data)) == before
Path(output).write_text(json.dumps(runs, indent=2), encoding='utf-8')
print('FRESH_PROCESS_USAGE_MEASUREMENTS ' + json.dumps(runs), flush=True)
