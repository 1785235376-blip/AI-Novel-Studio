"""Layer persistence and approved ORA through both mounted routes and real owners."""
import copy
import io
import zipfile
import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_comic_independent import original_independent_owner
from test_comic_collections import create_book
from test_comic_layers import layered, blank


def test_native_layers_save_reopen_copy_and_restore(mounted):
    e = mounted
    body = layered(blank())
    body['panels'][0]['bubbles'] = [{'id': 'dialogue', 'text': '原始对白', 'x': 40, 'y': 40, 'width': 300, 'height': 150}]
    body = layered(body)
    body['layer_stack']['items'].reverse()
    body['layer_stack']['items'][0].update(name='Custom text', opacity_percent=40, visible=False)
    page = checked(e.client.post(e.base + '/comic-layouts/records', json=body), 201)
    path = e.base + '/comic-layouts/records/' + page['id']
    changed = copy.deepcopy(page['document']); changed['panels'][0]['bubbles'][0]['text'] = '只改对白'
    edited = checked(e.client.put(path, json={**changed, 'expected_version': 1}))
    listed = checked(e.client.get(e.base + '/comic-layouts/records'))
    assert listed['items'][0]['document'] == edited['document'] == changed
    assert e.client.put(path, json={**changed, 'expected_version': 1}).status_code == 409
    book = create_book(e)
    copied = checked(e.client.post(e.base + '/comic-layouts/books/' + book['id'] + '/pages', json={
        'expected_version': book['version'], 'chapter_id': 'one', 'source_layout_id': page['id'], 'expected_source_version': edited['version']}), 201)['page']
    a, b = edited['document'], copied['document']
    assert {i['id'] for i in a['layer_stack']['items']}.isdisjoint(i['id'] for i in b['layer_stack']['items'])
    assert [i['kind'] for i in a['layer_stack']['items']] == [i['kind'] for i in b['layer_stack']['items']]
    for old, new in zip(a['layer_stack']['items'], b['layer_stack']['items']):
        assert old['target_id'] != new['target_id']
        assert {k:v for k,v in old.items() if k not in ('id', 'target_id')} == {k:v for k,v in new.items() if k not in ('id', 'target_id')}
    assert b['panels'][0]['bubbles'][0]['text'] == '只改对白'
    restored = checked(e.client.post(path + '/restore', json={'expected_version': edited['version'], 'target_version': 1}))
    assert restored['document'] == page['document'] and restored['status'] == 'DRAFT'
    assert e.assets.list(e.nid) == []


def test_mounted_ora_review_cas_privacy_and_native_unchanged(mounted):
    e = mounted
    page = checked(e.client.post(e.base + '/comic-layouts/records', json=layered(blank())), 201)
    path = e.base + '/comic-layouts/records/' + page['id']
    assert e.client.get(path + '/export-ora?expected_version=1').status_code == 422
    report = checked(e.client.post(path + '/preflight', json={'expected_version': 1}))
    approved = checked(e.client.post(path + '/approve', json={'expected_version': 1, 'review_digest': report['review_digest'], 'acknowledge_warnings': True}))
    response = e.client.get(path + '/export-ora?expected_version=2')
    assert response.status_code == 200 and response.headers['content-type'] == 'image/openraster'
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.read('mimetype') == b'image/openraster'
        assert 'data/layer-002.png' in archive.namelist()
    assert checked(e.client.get(e.base + '/comic-layouts/records'))['items'][0] == approved
    assert e.client.get(path + '/export-ora?expected_version=1').status_code == 409


def test_ora_actor_branch_and_flags_fail_closed(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    page = checked(e.client.post(e.base + '/comic-layouts/records', headers=e.headers, json=layered(blank())), 201)
    path = e.base + '/comic-layouts/records/' + page['id']
    report = checked(e.client.post(path + '/preflight', headers=e.headers, json={'expected_version': 1}))
    checked(e.client.post(path + '/approve', headers=e.headers, json={'expected_version': 1, 'review_digest': report['review_digest'], 'acknowledge_warnings': True}))
    for headers in ({}, e.viewer_headers, {**e.headers, 'X-Branch-ID': e.other_branch}):
        response = e.client.get(path + '/export-ora?expected_version=2', headers=headers)
        assert response.status_code in (401, 403, 404)
        assert not response.content.startswith(b'PK')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    denied = e.client.get(path + '/export-ora?expected_version=2', headers=e.headers)
    # Existing authorization fails closed before route flag evaluation.
    assert denied.status_code == 501 and not denied.content.startswith(b'PK')
