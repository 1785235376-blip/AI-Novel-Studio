"""Original mounted Host/permission/feature guards on disposable File storage."""
from copy import deepcopy

from app.experimental.ux import ReadContext
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_portable_batches_mounted import tools


def test_policy_api_cas_and_source_bound_cleanup_plan_are_private_and_nonexecuting(tools):
    e = tools; base = e.base + '/portable-projects'
    before = deepcopy(e.store.read(e.nid, e.scope))
    response = e.client.get(base + '/cache-policy')
    assert checked(response) == {'version': 0, 'limit_bytes': None} and response.headers['cache-control'] == 'no-store'
    assert e.store.read(e.nid, e.scope) == before
    row = checked(e.client.post(base + '/export', json={'chapter_ids': [e.chapter['id']]}))
    response = e.client.put(base + '/cache-policy', json={'expected_version': 0, 'limit_bytes': 0})
    assert checked(response) == {'version': 1, 'limit_bytes': 0} and response.headers['cache-control'] == 'no-store'
    preview = checked(e.client.get(base + '/storage'))
    assert preview['cache_budget']['plan']['record_ids'] == [row['id']]
    path = e.portable._file(ReadContext(e.nid, e.scope, 'local-author'), row['id'])
    assert path.resolve().is_relative_to(e.root.resolve()) and path.is_file()
    conflict = e.client.put(base + '/cache-policy', json={'expected_version': 0, 'limit_bytes': None})
    assert conflict.status_code == 409 and 'current' not in conflict.json()['detail']
    checked(e.client.put(base + '/cache-policy', json={'expected_version': 1, 'limit_bytes': None}))
    rejected = e.client.post(base + '/cleanup', json={'record_ids': [row['id']], 'preview_digest': preview['preview_digest'], 'confirmed': True})
    assert rejected.status_code == 409 and path.exists()


def test_policy_api_requires_original_host_and_feature_and_rejects_unknown_fields(tools, monkeypatch):
    e = tools; path = e.base + '/portable-projects/cache-policy'
    bad = e.client.put(path, json={'expected_version': 0, 'limit_bytes': 10, 'directory': 'PRIVATE_PATH'})
    assert bad.status_code == 422
    e.sessions.revoke('portable-host')
    assert e.client.get(path).status_code in {401, 403}
    assert e.client.put(path, json={'expected_version': 0, 'limit_bytes': 10}).status_code in {401, 403}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert e.client.get(path).status_code == 404
