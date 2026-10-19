"""Original trusted-session/membership routes on both aliases, no model calls."""
import copy

from test_r3_mounted_contracts import mounted, prefix, checked, scoped


def setup(e, monkeypatch, headers=None):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'change_impact_v2,temporal_story_graph_v2,world_character_engines_v2,asset_lineage_v2,advanced_planning_v2')
    headers = headers or {}
    source = {'kind': 'CHAPTER', 'id': e.chapter['id']}
    links = {'chapter_ids': [e.chapter['id']]}
    if headers:
        # Reuse an original branch-owned character; no branch manuscript adapter is fabricated.
        e.novels.upsert_character(e.nid, 'intent-character', {'name': 'Scoped author source', 'branch_id': e.branch})
        source = {'kind': 'CHARACTER', 'id': 'intent-character'}
        links = {'character_ids': ['intent-character']}
    graph = checked(e.client.post(e.base + '/planning/graphs', headers=headers,
        json={'title': 'Original bounded plan', 'links': links}), 201)
    result = checked(e.client.post(e.base + '/change-impact/query', headers=headers,
        json={'source': source}))
    node = next(n for n in result['items'] if n['id'] == graph['root_node_id'])
    return {'source': source,
        'selected': [{'key': node['key'], 'expected_version': node['version'], 'choice': 'KEEP'}]}


def test_actual_alias_preview_save_reopen_no_store_no_execution_and_conflict(mounted, monkeypatch):
    e = mounted; body = setup(e, monkeypatch); base = e.base + '/change-impact'
    before = copy.deepcopy(e.experimental.change_impact_service.store.read(e.nid, e.scope))
    preview_response = e.client.post(base + '/decisions/preview', json=body)
    preview = checked(preview_response); assert preview_response.headers['cache-control'] == 'no-store'
    assert e.experimental.change_impact_service.store.read(e.nid, e.scope) == before
    request = {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'mounted-intent'}
    response = e.client.post(base + '/decisions', json=request); saved = checked(response, 201)
    assert response.headers['cache-control'] == 'no-store'
    params = {'source_kind': body['source']['kind'], 'source_id': body['source']['id']}
    assert checked(e.client.get(base + '/decisions', params=params)) == {'items': [saved]}
    assert checked(e.client.post(base + '/decisions', json=request), 201) == saved
    request['selected'][0]['choice'] = 'REBUILD'
    assert e.client.post(base + '/decisions', json=request).status_code == 422
    assert checked(e.client.get(base + '/refreshes')) == {'items': []}
    e.chapters.save(e.chapter['id'], {'content': 'Changed after saved intent'})
    assert not checked(e.client.get(base + '/decisions', params=params))['items'][0]['current']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert e.client.get(base + '/decisions', params=params).status_code == 404


def test_original_scoped_reader_and_foreign_branch_cannot_enumerate_or_save_private_intent(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); body = setup(e, monkeypatch, e.headers)
    base = e.base + '/change-impact'; params = {'source_kind': body['source']['kind'], 'source_id': body['source']['id']}
    preview = checked(e.client.post(base + '/decisions/preview', headers=e.headers, json=body))
    saved = checked(e.client.post(base + '/decisions', headers=e.headers, json={**body, 'preview_digest': preview['preview_digest'], 'request_id': 'private-intent'}), 201)
    for method, suffix, payload in [('GET', '/decisions', None), ('POST', '/decisions/preview', body), ('POST', '/decisions', {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'denied'})]:
        response = e.client.request(method, base + suffix, headers=e.viewer_headers, params=params if method == 'GET' else None, json=payload)
        assert response.status_code == 403 and saved['id'] not in response.text
    foreign = {**e.headers, 'X-Branch-ID': e.other_branch}
    response = e.client.get(base + '/decisions', headers=foreign, params=params)
    assert response.status_code in {403, 404} and saved['id'] not in response.text
