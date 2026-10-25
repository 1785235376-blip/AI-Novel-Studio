"""Independent fixed-baseline probes: pass means risk reproduced, not repaired."""
import json
import pytest
from app.experimental.store import ExperimentalStore, canonical
from app.creative.project_store import CreativeProjectStore
from test_studio_asset_query import rig
from test_taskcenter_query_backend import mounted, get

SCOPE = {'mode': 'local', 'novel_id': 'book'}

def test_cross_instance_reentry_loses_committed_inner_update(tmp_path):
    a, b = ExperimentalStore(tmp_path), ExperimentalStore(tmp_path)
    with a.transaction('book', SCOPE) as outer:
        outer['collections']['outer'] = {'outer': {'value': 1}}
        with b.transaction('book', SCOPE) as inner:
            inner['collections']['inner'] = {'inner': {'value': 2}}
        inner_disk = b.read('book', SCOPE)
        assert 'inner' in inner_disk['collections']
    final = b.read('book', SCOPE)
    print('REENTRY', json.dumps({'inner_committed': inner_disk, 'final': final}))
    assert 'outer' in final['collections'] and 'inner' not in final['collections']

def test_generic_read_returns_uncommitted_value_then_rolls_back(tmp_path):
    a, b = ExperimentalStore(tmp_path), ExperimentalStore(tmp_path)
    with pytest.raises(RuntimeError, match='rollback'):
        with a.transaction('book', SCOPE) as tx:
            tx['collections']['pending'] = {'x': {'value': 'uncommitted'}}
            visible = a.read('book', SCOPE)
            committed = b.read('book', SCOPE)
            assert visible != committed
            print('UNCOMMITTED', json.dumps({'same_instance': visible, 'physical': committed}))
            raise RuntimeError('rollback')
    assert not a.path('book', SCOPE).exists()

def test_cross_instance_write_inside_source_lease_is_not_detected(tmp_path):
    (tmp_path / 'novels' / 'book').mkdir(parents=True)
    a, b = ExperimentalStore(tmp_path), ExperimentalStore(tmp_path)
    creative = CreativeProjectStore(a)
    creative.incarnation('book')
    with creative.source_lease('book', SCOPE):
        with b.transaction('book', SCOPE) as tx:
            tx['collections']['inner'] = {'x': {'value': 'committed-under-read-lease'}}
    assert 'inner' in b.read('book', SCOPE)['collections']
    print('SOURCE_LEASE inner independent write committed without lease rejection')

def test_noop_and_existing_owner_source_lease_do_not_create_scope(tmp_path):
    (tmp_path / 'novels' / 'book').mkdir(parents=True)
    a = ExperimentalStore(tmp_path)
    creative = CreativeProjectStore(a)
    creative.incarnation('book')
    with a.transaction('book', SCOPE):
        pass
    assert not a.path('book', SCOPE).exists()
    with creative.existing_owner_only(), creative.source_lease('book', SCOPE):
        pass
    assert not a.path('book', SCOPE).exists()

def test_recreated_project_legacy_first_page_adopts_old_scope_but_cursor_501(mounted):
    r = mounted.rig
    owner = CreativeProjectStore(mounted.store)
    before_owner = owner.incarnation(r.nid)
    before_bytes = mounted.store.path(r.nid, r.scope).read_bytes()
    response = get(mounted, {'authority': 'semantic_import', 'limit': 1})
    assert response.status_code == 200, response.text
    before_id = response.json()['items'][0]['id']
    r.novels.delete(r.nid)
    assert mounted.store.path(r.nid, r.scope).read_bytes() == before_bytes
    r.project(r.nid)
    after_owner = owner.incarnation(r.nid)
    assert after_owner != before_owner
    for prefix in ('/api', '/api/v1'):
        page = get(mounted, {'authority': 'semantic_import', 'limit': 1}, prefix=prefix)
        assert page.status_code == 200, page.text
        assert page.json()['items'][0]['id'] == before_id
        cursor = get(mounted, {'authority': 'semantic_import', 'page_mode': 'cursor', 'limit': 1}, prefix=prefix)
        assert cursor.status_code == 501, cursor.text
        print('RECREATION', json.dumps({'prefix': prefix, 'old_owner': before_owner, 'new_owner': after_owner, 'legacy_page': page.json(), 'cursor_status': cursor.status_code, 'cursor': cursor.json()}))
