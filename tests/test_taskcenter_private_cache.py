"""No-store coverage includes original pre-route authority failures."""
import pytest
from fastapi.testclient import TestClient
from test_studio_asset_query import rig, shared_scope
from test_taskcenter_query_backend import mounted, get

pytestmark = pytest.mark.file_backend_only

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('params', [{'authority': 'semantic_import'}, {'page_mode': 'cursor'}])
def test_opt_in_global_loopback_denial_is_private(mounted, prefix, params):
    from app.main import app
    with TestClient(app, client=('192.0.2.2', 50000)) as client:
        response = client.get(f'{prefix}/novels/{mounted.rig.nid}/experimental/workspace/tasks', params=params)
    assert response.status_code == 403
    assert response.json()['detail']['code'] == 'LOCAL_RUNTIME_LOOPBACK_REQUIRED'
    assert response.headers['cache-control'] == 'no-store'

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_opt_in_packaged_missing_session_is_private(mounted, prefix):
    shared_scope(mounted.rig)
    object.__setattr__(mounted.rig.settings, 'enable_packaged_runtime', True)
    response = mounted.rig.client.get(f'{prefix}/novels/{mounted.rig.nid}/experimental/workspace/tasks', params={'page_mode': 'cursor'})
    assert response.status_code == 401
    assert response.json()['detail']['code'] == 'SESSION_REQUIRED'
    assert response.headers['cache-control'] == 'no-store'

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_legacy_global_denial_keeps_cache_contract(mounted, prefix):
    from app.main import app
    with TestClient(app, client=('192.0.2.2', 50000)) as client:
        response = client.get(f'{prefix}/novels/{mounted.rig.nid}/experimental/workspace/tasks', params={'limit': 'bad'})
    assert response.status_code == 403
    assert 'cache-control' not in response.headers
