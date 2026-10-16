"""B07 actual composition and trusted authorization against real File/hosted PG."""
import base64
import io
import json
import zipfile

import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from app.experimental.flags import FLAGS


def create(e, headers=None, chapter=True):
    headers = headers or {}; plan = e.base + '/planning'
    graph = checked(e.client.post(plan + '/graphs', headers=headers, json={'title': 'Synthetic interactive plan', 'links': {'chapter_ids': [e.chapter['id']]} if chapter else {}}), 201)
    end = checked(e.client.post(plan + '/nodes', headers=headers, json={'graph_id': graph['id'], 'parent_id': graph['root_node_id'], 'level': 'VOLUME', 'title': 'Ending'}), 201)
    spec = {'title': 'Private interactive adaptation', 'graph_id': graph['id'], 'graph_version': graph['version'], 'entry_node_id': graph['root_node_id'], 'nodes': [
        {'node_id': graph['root_node_id'], 'node_version': 1, 'title': 'Choice', 'dialogue': 'PRIVATE_B07_SENTINEL', 'choices': [{'id': 'finish', 'label': 'Finish', 'target': end['id']}]},
        {'node_id': end['id'], 'node_version': 1, 'title': 'Ending', 'ending': 'Safe home'}]}
    row = checked(e.client.post(e.base + '/interactive-stories', headers=headers, json={'spec': spec}), 201)
    return row, graph


def approve(e, row, headers=None):
    url = e.base + '/interactive-stories/' + row['id']; headers = headers or {}
    row = checked(e.client.post(url + '/review', headers=headers, json={'expected_version': row['version'], 'action': 'submit'}))
    receipt = checked(e.client.post(url + '/review-preview', headers=headers, json={'expected_version': row['version']}))
    return checked(e.client.post(url + '/review', headers=headers, json={'expected_version': row['version'], 'action': 'approve', 'preview_digest': receipt['preview_digest']}))


def test_mounted_authoring_preview_review_bundle_and_no_legacy_mutation(mounted):
    e = mounted; original = e.chapters.get(e.chapter['id']); row, graph = create(e); url = e.base + '/interactive-stories/' + row['id']
    assert checked(e.client.get(e.base + '/interactive-stories/catalog'))['target_runtime'] == 'NOT_RUN'
    play = checked(e.client.post(url + '/preview', json={'expected_version': row['version'], 'choices': ['finish']}))
    assert play['status'] == 'ENDING' and play['node']['ending'] == 'Safe home'
    assert e.client.get(url).headers['cache-control'] == 'no-store'
    row = approve(e, row); p = checked(e.client.post(url + '/export-preview', json={'expected_version': row['version']}))
    out = checked(e.client.post(url + '/export', json={'expected_version': row['version'], 'preview_digest': p['preview_digest']}))
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(out['content_base64']))) as archive:
        neutral = json.loads(archive.read(f"interactive-story-{row['id']}/story.json"))
        assert neutral['spec']['graph_id'] == graph['id']
    assert e.chapters.get(e.chapter['id']) == original
    for suffix in ['/review-inbox', '/world/canon', '/revisions/proposals']:
        response = e.client.get(e.base + suffix); assert response.status_code == 200 and 'PRIVATE_B07_SENTINEL' not in response.text


def test_mounted_off_dependency_v1_every_route_and_malformed_body_are_fail_closed(mounted, monkeypatch):
    e = mounted; row, _ = create(e); url = e.base + '/interactive-stories'; item = url + '/' + row['id']; before = e.store.read(e.nid, e.scope)
    for flags, v1 in [('', 'false'), ('*', 'false'), ('interactive_story_v2', 'false'), (','.join(FLAGS), 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        for path in [url, url + '/catalog', item]:
            response = e.client.get(path); assert response.status_code == 404 and 'PRIVATE_B07_SENTINEL' not in response.text
        for suffix in ['review-preview', 'review', 'preview', 'refresh-preview', 'refresh', 'export-preview', 'export']:
            assert e.client.post(item + '/' + suffix, content='not-json').status_code == 404
        assert e.client.post(url, content='not-json').status_code == 404
        assert e.client.put(item, content='not-json').status_code == 404
    assert e.store.read(e.nid, e.scope) == before


def test_mounted_exact_export_receipt_and_current_source_version(mounted):
    e = mounted; row, _ = create(e); row = approve(e, row); url = e.base + '/interactive-stories/' + row['id']
    preview = checked(e.client.post(url + '/export-preview', json={'expected_version': row['version']}))
    e.chapters.save(e.chapter['id'], {'version': e.chapter['version'], 'content': 'New manuscript source'})
    hidden = checked(e.client.get(url)); assert hidden['stale'] and 'spec' not in hidden
    assert e.client.post(url + '/export', json={'expected_version': row['version'], 'preview_digest': preview['preview_digest']}).status_code == 409
    assert e.client.post(url + '/preview', json={'expected_version': row['version']}).status_code == 409


def test_mounted_trusted_membership_branch_and_revoke(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); row, _ = create(e, e.headers, chapter=False); url = e.base + '/interactive-stories/' + row['id']
    assert e.client.get(url, headers=e.viewer_headers).status_code == 403
    assert e.client.get(url, headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code in {403, 404}
    assert e.client.get(url, headers={'X-Session-Token': 'forged', 'X-Branch-ID': e.branch}).status_code in {401, 403}
    row = approve(e, row, e.headers)
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(url + '/preview', headers=e.headers, json={'expected_version': row['version']}).status_code == 403
    assert e.client.post(url + '/export-preview', headers=e.headers, json={'expected_version': row['version']}).status_code == 403


def test_mounted_input_limits_no_arbitrary_expression_or_scope_override(mounted):
    e = mounted; row, _ = create(e); url = e.base + '/interactive-stories/' + row['id']; body = {'expected_version': row['version'], 'spec': row['spec']}
    body['spec']['nodes'][0]['choices'][0]['condition'] = '__import__("os").system("bad")'
    assert e.client.put(url, json=body).status_code == 422
    assert e.client.put(url, content=b' ' * (2 * 1024 * 1024 + 1)).status_code == 413
    assert e.client.post(url + '/preview', json={'expected_version': row['version'], 'actor': 'other'}).status_code == 422
    assert checked(e.client.get(url))['version'] == row['version']


def test_mounted_flag_revocation_during_save_rolls_back(mounted, monkeypatch):
    e = mounted; row, _ = create(e); url = e.base + '/interactive-stories/' + row['id']; before = e.store.read(e.nid, e.scope)
    service = e.experimental.interactive_story_service; original = service._current; calls = []
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs); calls.append(1)
        if len(calls) == 2: monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        return result
    monkeypatch.setattr(service, '_current', revoke)
    response = e.client.put(url, json={'expected_version': row['version'], 'spec': row['spec']})
    assert response.status_code == 404 and e.store.read(e.nid, e.scope) == before


def test_mounted_rebind_is_explicit_and_reopens_review(mounted):
    e = mounted; row, _ = create(e); row = approve(e, row); url = e.base + '/interactive-stories/' + row['id']
    e.chapters.save(e.chapter['id'], {'version': e.chapter['version'], 'content': 'Changed source'})
    p = checked(e.client.post(url + '/refresh-preview', json={'expected_version': row['version']}))
    assert p['changed_source_count'] == 1 and 'spec' not in p
    fresh = checked(e.client.post(url + '/refresh', json={'expected_version': row['version'], 'preview_digest': p['preview_digest']}))
    assert fresh['status'] == 'DRAFT' and not fresh['stale']
    assert not checked(e.client.post(url + '/export-preview', json={'expected_version': fresh['version']}))['can_export']
