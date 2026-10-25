"""Independent mounted lifecycle probes with real File authorities, no fake epochs."""
from types import SimpleNamespace
from copy import deepcopy
import pytest
from test_studio_asset_query import rig
from app.experimental.store import ExperimentalStore
from app.creative.project_store import CreativeProjectStore
from app.experimental.imports import JOBS

@pytest.fixture
def mounted_owner(rig, monkeypatch):
    from app import api as original_api
    from app.experimental import api
    from app.services import ChapterService
    from app.experimental.taskcenter_cursor import TaskCenterCursorEngine
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2,semantic_import_v2')
    store = ExperimentalStore(rig.root)
    chapters = ChapterService(rig.novels.chapters)
    monkeypatch.setattr(original_api, 'chapter_service', chapters)
    for service in (api.workspace_tools_service, api.import_service):
        for name, value in (('store', store), ('novels', rig.novels), ('chapters', chapters)):
            monkeypatch.setattr(service, name, value)
    monkeypatch.setattr(api.taskcenter_cursor_adapter, 'engine', TaskCenterCursorEngine())
    # Original marker creation is explicit test setup, never a GET side effect.
    owner = CreativeProjectStore(store)
    identity = owner.incarnation(rig.nid)
    def seed(count):
        with store.transaction(rig.nid, rig.scope) as doc:
            doc['collections'][JOBS] = {f'job-{i:03}': {'id': f'job-{i:03}', 'novel_id': rig.nid,
                'scope': deepcopy(rig.scope), 'status': 'QUEUED', 'version': 1} for i in range(count)}
    seed(5)
    def request(prefix='/api', token=None, **params):
        params = {'authority': 'semantic_import', 'page_mode': 'cursor', 'limit': 2, **params}
        if token is not None:
            params['cursor'] = token
        return rig.client.get(f'{prefix}/novels/{rig.nid}/experimental/workspace/tasks', params=params)
    return SimpleNamespace(rig=rig, store=store, owner=owner, identity=identity, seed=seed, request=request)

def ok(response):
    assert response.status_code == 200, response.text
    assert response.headers.get('cache-control') == 'no-store'
    return response.json()

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_real_first_next_replay_last_and_read_zero_scope_write(mounted_owner, prefix):
    m = mounted_owner
    before = m.store.path(m.rig.nid, m.rig.scope).read_bytes()
    first = ok(m.request(prefix))
    second = ok(m.request(prefix, first['next_cursor']))
    assert ok(m.request(prefix, first['next_cursor'])) == second
    last = ok(m.request(prefix, second['next_cursor']))
    assert [r['id'] for p in (first, second, last) for r in p['items']] == [f'job-{i:03}' for i in range(5)]
    assert last['has_more'] is False and last['next_cursor'] is None
    assert m.store.path(m.rig.nid, m.rig.scope).read_bytes() == before

@pytest.mark.parametrize('change', ['aba', 'delete_recreate', 'page_external_observed'])
def test_observed_lifecycle_change_restarts_even_with_equal_page(mounted_owner, change):
    m = mounted_owner
    first = ok(m.request())
    original = m.store.read(m.rig.nid, m.rig.scope)['collections'][JOBS]['job-004']
    with m.store.transaction(m.rig.nid, m.rig.scope) as doc:
        if change == 'delete_recreate':
            del doc['collections'][JOBS]['job-004']
        else:
            doc['collections'][JOBS]['job-004']['version'] = 2
    if change != 'page_external_observed':
        with m.store.transaction(m.rig.nid, m.rig.scope) as doc:
            doc['collections'][JOBS]['job-004'] = original
    response = m.request(token=first['next_cursor'])
    assert response.status_code == 409, response.text
    assert response.headers.get('cache-control') == 'no-store'

@pytest.mark.parametrize('change', ['unselected_collection', 'unobserved_tail'])
def test_unobserved_activity_does_not_invalidate_cursor(mounted_owner, change):
    m = mounted_owner
    m.seed(201)
    first = ok(m.request())
    assert first['observed_total'] == 200 and first['source_truncated'] is True
    before = ok(m.request(token=first['next_cursor']))
    for version in (2, 1):
        with m.store.transaction(m.rig.nid, m.rig.scope) as doc:
            if change == 'unobserved_tail':
                doc['collections'][JOBS]['job-200']['version'] = version
            else:
                doc['collections']['unselected_private'] = {'x': {'v': version}}
        assert ok(m.request(token=first['next_cursor'])) == before

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_project_recreation_blocks_old_token_and_new_first_page(mounted_owner, prefix):
    m = mounted_owner
    first = ok(m.request(prefix))
    before = m.store.path(m.rig.nid, m.rig.scope).read_bytes()
    m.rig.novels.delete(m.rig.nid)
    m.rig.project(m.rig.nid)
    assert m.owner.incarnation(m.rig.nid) != m.identity
    assert m.request(prefix, first['next_cursor']).status_code == 409
    assert m.request(prefix).status_code == 501
    assert m.store.path(m.rig.nid, m.rig.scope).read_bytes() == before

@pytest.mark.parametrize('mode', ['legacy', 'missing_marker'])
def test_first_page_refuses_unbound_source_without_read_side_effect(mounted_owner, mode):
    import json
    m = mounted_owner
    path = m.store.path(m.rig.nid, m.rig.scope)
    marker = m.rig.root / 'novels' / m.rig.nid / 'creative_project_v2.json'
    if mode == 'legacy':
        doc = json.loads(path.read_text())
        doc.pop('_taskcenter_lifecycle_v1')
        path.write_text(json.dumps(doc, sort_keys=True))
    else:
        marker.unlink()
    before = path.read_bytes()
    marker_before = marker.read_bytes() if marker.exists() else None
    for prefix in ('/api', '/api/v1'):
        response = m.request(prefix)
        assert response.status_code == 501, response.text
        assert response.headers.get('cache-control') == 'no-store'
    assert path.read_bytes() == before
    assert (marker.read_bytes() if marker.exists() else None) == marker_before
