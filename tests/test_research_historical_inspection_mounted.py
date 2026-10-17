"""Original mounted routes and fresh authorization for historical inspection."""
import pytest

from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_research_library_mounted import research_mounted
from test_r4_research_library import payload


def prepare(e, headers=None):
    headers = headers or {}
    row = checked(e.client.post(e.path + '/sources/import', json=payload(), headers=headers), 201)
    checked(e.client.put(e.path + f"/sources/{row['id']}/file", json={**payload('Replacement'), 'expected_version': 1}, headers=headers))
    ref = row['paragraphs'][0]['citation']
    path = e.path + f"/sources/{row['id']}/history/1/inspect"
    params = {'expected_current_version': 2, 'paragraph': ref['paragraph'], 'quote_sha256': ref['quote_sha256']}
    return row, ref, path, params


def test_mounted_read_no_write_no_cache_and_current_consumers_stay_stale(research_mounted, monkeypatch):
    e = research_mounted; row, ref, path, params = prepare(e)
    before = e.store.read(e.nid, e.scope)
    def no_write(*args, **kwargs): raise AssertionError('Inspection wrote')
    monkeypatch.setattr('app.experimental.store.atomic_write', no_write)
    response = e.client.get(path, params=params)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert response.json()['text'] == 'Tidal gates close at dusk.'
    assert 'citation' not in response.json() and 'content_base64' not in response.text
    assert e.store.read(e.nid, e.scope) == before
    assert e.client.post(e.path + '/citation', json=ref).status_code == 409
    assert e.client.post(e.path + '/context-preview', json={'citations': [ref]}).status_code == 409


@pytest.mark.parametrize('case', ['hash', 'paragraph', 'page', 'version', 'foreign', 'revoked', 'deleted', 'flag', 'v1'])
def test_mounted_negative_never_discloses_historical_text(research_mounted, monkeypatch, case):
    e = research_mounted; row, ref, path, params = prepare(e)
    if case == 'hash': params['quote_sha256'] = '0' * 64
    if case == 'paragraph': params['paragraph'] = 5000
    if case == 'page': params.update(paragraph=0, page=2)
    if case == 'version': params['expected_current_version'] = 1
    if case == 'foreign': path = path.replace(row['id'], 'foreign')
    if case in {'revoked', 'deleted'}:
        checked(e.client.post(e.path + f"/sources/{row['id']}/" + ('revoke' if case == 'revoked' else 'delete'), json={'expected_version': 2}))
        params['expected_current_version'] = 3
    if case == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    if case == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    response = e.client.get(path, params=params)
    assert response.status_code in {403, 404, 422}
    assert 'Tidal gates' not in response.text and row['title'] not in response.text


def test_mounted_missing_session_reader_wrong_branch_and_project(research_mounted, monkeypatch):
    e = scoped(research_mounted, monkeypatch); row, ref, path, params = prepare(e, e.headers)
    for headers in [{}, e.viewer_headers, {**e.headers, 'X-Branch-ID': e.other_branch}]:
        response = e.client.get(path, params=params, headers=headers)
        assert response.status_code in {401, 403, 404} and 'Tidal gates' not in response.text
    response = e.client.get(path.replace(e.nid, 'foreign-project'), params=params, headers=e.headers)
    assert response.status_code in {401, 403, 404} and 'Tidal gates' not in response.text


@pytest.mark.parametrize('change', ['role', 'session', 'flag', 'v1', 'project'])
def test_mounted_fresh_post_projection_guard_hides_text(research_mounted, monkeypatch, change):
    e = scoped(research_mounted, monkeypatch); row, ref, path, params = prepare(e, e.headers)
    original = e.research.inspect_history
    def projection(*args):
        value = original(*args)
        if change == 'role': e.authorization.revoke_role(e.role, e.lead)
        if change == 'session': e.sessions.revoke(e.lead)
        if change == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        if change == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        if change == 'project':
            title = e.novels.get(e.nid)['title']
            e.novels.delete(e.nid)
            assert e.novels.create({'id': e.nid, 'title': title})['id'] == e.nid
        return value
    monkeypatch.setattr(e.research, 'inspect_history', projection)
    response = e.client.get(path, params=params, headers=e.headers)
    assert response.status_code in {401, 403, 404} and 'Tidal gates' not in response.text


def test_local_recreation_after_projection_cannot_return_old_text(research_mounted, monkeypatch):
    e = research_mounted
    row, ref, path, params = prepare(e)
    original = e.research.inspect_history
    def projection(*args):
        value = original(*args)
        title = e.novels.get(e.nid)['title']
        e.novels.delete(e.nid)
        assert e.novels.create({'id': e.nid, 'title': title})['id'] == e.nid
        # Establish the new owner's marker through the existing identity owner,
        # not by forging a marker or altering retained historical records.
        e.research.history_identity(e.nid, provision=True)
        return value
    monkeypatch.setattr(e.research, 'inspect_history', projection)
    response = e.client.get(path, params=params)
    assert response.status_code == 404
    assert 'Tidal gates' not in response.text
