"""Production router, original hosted-session auth and File/real-PG contracts."""
from copy import deepcopy
import pytest
from app.actor_context import SessionContext
from app.experimental.flags import FLAGS
from app.repositories.chapter_repository import VersionConflict
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def forks(mounted):
    e = mounted; e.forks = e.experimental.project_forks_service
    e.sessions.register('fork-host', SessionContext('fork-session', 'fork-client', 'fork-actor', 'fork-workspace'))
    e.client.headers['X-Session-Token'] = 'fork-host'; e.fbase = e.base + '/project-forks'
    yield e
    for row in e.store.read(e.nid, e.scope)['collections'].get(e.forks.FORKS, {}).values():
        try: e.novels.delete(row['target_id'])
        except FileNotFoundError: pass


def create(e):
    row = checked(e.client.post(e.fbase + '/preflight', json={'chapter_ids': [e.chapter['id']], 'title': 'B09 selected synthetic'}))
    return checked(e.client.post(e.fbase + f"/{row['id']}/create", json={'expected_version': row['version'], 'preview_digest': row['preview_digest'], 'confirmed': True}))


def edited(e, row):
    target = e.chapters.get(row['id_map']['chapters'][e.chapter['id']]); doc = deepcopy(target['document']); doc['content'].append({'type': 'paragraph', 'content': [{'type': 'text', 'text': 'B09 fork-only addition'}]})
    e.chapters.save(target['id'], {'version': target['version'], 'document': doc})
    preview = checked(e.client.post(e.fbase + f"/{row['id']}/compare", json={'expected_version': row['version']}))
    return {'expected_version': row['version'], 'preview_digest': preview['preview_digest'], 'choices': {}, 'confirmed': True}


def test_mounted_fork_compare_apply_checkpoint_restore_original_writer(forks, monkeypatch):
    e = forks; before = e.chapters.get(e.chapter['id']); row = create(e); body = edited(e, row)
    save = e.api.update_chapter; calls = []
    def original(*args, **kwargs): calls.append((args, kwargs)); return save(*args, **kwargs)
    monkeypatch.setattr(e.api, 'update_chapter', original)
    done = checked(e.client.post(e.fbase + f"/{row['id']}/apply", json=body))
    assert done['status'] == 'COMPLETED' and len(calls) == 1
    assert calls[0][0][1].source == 'PROJECT_FORK_MERGE' and calls[0][0][1].version == before['version']
    assert calls[0][1]['x_session_token'] == 'fork-host'
    assert e.chapters.get(e.chapter['id'])['version'] == before['version'] + 1
    recovery = checked(e.client.post(e.fbase + f"/merges/{done['id']}/recovery", json={'expected_version': done['version']}))
    restored = checked(e.client.post(e.fbase + f"/merges/{done['id']}/restore", json={'expected_version': done['version'], 'preview_digest': recovery['preview_digest'], 'confirmed': True}))
    assert restored['status'] == 'RESTORED' and len(calls) == 2
    assert e.chapters.get(e.chapter['id'])['document'] == before['document']
    assert e.novels.get(e.nid) and e.novels.get(row['target_id'])


def test_mounted_host_flag_dependencies_v1_and_no_wildcard(forks, monkeypatch):
    e = forks; e.client.headers.pop('X-Session-Token')
    assert e.client.get(e.fbase + '/catalog').status_code == 401
    e.client.headers['X-Session-Token'] = 'fork-host'
    for flags, v1 in [('', False), ('*', False), ('project_forks_v2', False), (','.join(FLAGS), True)]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', str(v1))
        assert e.client.get(e.fbase + '/catalog').status_code == 404
        assert e.client.post(e.fbase + '/preflight', json={'chapter_ids': [e.chapter['id']], 'title': 'Denied'}).status_code == 404
    assert not e.store.read(e.nid, e.scope)['collections'].get(e.forks.FORKS)


def test_mounted_collaboration_does_not_read_base_or_claim_branch_isolation(forks, monkeypatch):
    e = scoped(forks, monkeypatch); e.client.headers.pop('X-Session-Token', None)
    # Collaboration member sessions are trusted; catalog truthfully has no
    # usable local fork source and write must fail before base data is read.
    result = e.client.get(e.fbase + '/catalog', headers=e.headers)
    if result.status_code == 200: assert result.json()['chapters'] == [] and not result.json()['available']
    else: assert result.status_code in {401, 403}
    response = e.client.post(e.fbase + '/preflight', headers=e.headers, json={'chapter_ids': [e.chapter['id']], 'title': 'Forbidden branch copy'})
    assert response.status_code in {401, 403, 422}
    assert 'city gate opened' not in response.text
    assert e.client.get(e.fbase + '/catalog').status_code == 401


@pytest.mark.parametrize('fence', ['flag', 'v1', 'session', 'fork_drift'])
def test_mounted_revocation_between_original_writes_is_partial_not_replayed(forks, monkeypatch, fence):
    e = forks; second = e.chapters.create(e.nid, {'title': 'Second', 'content': 'Original second'})
    pre = checked(e.client.post(e.fbase + '/preflight', json={'chapter_ids': [e.chapter['id'], second['id']], 'title': 'Two chapters'}))
    row = checked(e.client.post(e.fbase + f"/{pre['id']}/create", json={'expected_version': pre['version'], 'preview_digest': pre['preview_digest'], 'confirmed': True}))
    for target_id in row['id_map']['chapters'].values():
        current = e.chapters.get(target_id); doc = deepcopy(current['document']); doc['content'].append({'type': 'paragraph', 'content': [{'type': 'text', 'text': 'fork edit'}]})
        e.chapters.save(target_id, {'version': current['version'], 'document': doc})
    preview = checked(e.client.post(e.fbase + f"/{row['id']}/compare", json={'expected_version': row['version']}))
    original = e.api.update_chapter; calls = []
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs); calls.append(args[0])
        if fence == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        elif fence == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        elif fence == 'session': e.sessions.revoke('fork-host')
        else:
            current = e.chapters.get(row['id_map']['chapters'][e.chapter['id']]); e.chapters.save(current['id'], {'version': current['version'], 'content': 'New fork edit'})
        return result
    monkeypatch.setattr(e.api, 'update_chapter', revoke)
    result = e.client.post(e.fbase + f"/{row['id']}/apply", json={'expected_version': row['version'], 'preview_digest': preview['preview_digest'], 'confirmed': True})
    assert result.status_code in {401, 404, 409} and len(calls) == 1
    raw = list(e.store.read(e.nid, e.scope)['collections'][e.forks.MERGES].values())[0]
    assert raw['status'] == 'RECOVERY_REQUIRED' and len(raw['journal']) == 1
    assert 'fork edit' not in e.chapters.get(second['id'])['content']


def test_mounted_original_cas_conflict_sanitized_and_claim_persists(forks, monkeypatch):
    e = forks; row = create(e); body = edited(e, row)
    def conflict(*args, **kwargs): raise VersionConflict({'id': e.chapter['id'], 'version': 999, 'content': 'PRIVATE_CONFLICT_BODY'})
    monkeypatch.setattr(e.api, 'update_chapter', conflict)
    result = e.client.post(e.fbase + f"/{row['id']}/apply", json=body)
    assert result.status_code == 409 and 'PRIVATE_CONFLICT_BODY' not in result.text and 'current' not in result.json()['detail']
    raw = list(e.store.read(e.nid, e.scope)['collections'][e.forks.MERGES].values())[0]
    assert raw['status'] == 'RECOVERY_REQUIRED' and raw['journal'][0]['status'] == 'CLAIMED'
    replay = e.client.post(e.fbase + f"/{row['id']}/apply", json=body)
    assert replay.status_code == 409 and 'city gate opened' not in replay.text


def test_mounted_bounded_input_and_unmapped_reference_fail_closed(forks):
    e = forks
    assert e.client.post(e.fbase + '/preflight', content=b'{' + b' ' * (129 * 1024), headers={'Content-Type': 'application/json'}).status_code == 413
    assert e.client.post(e.fbase + '/preflight', json={'chapter_ids': ['../outside:1'], 'title': 'No traversal'}).status_code == 404
    assert e.client.post(e.fbase + '/preflight', json={'chapter_ids': [e.chapter['id']], 'title': 'No hidden fields', 'target_id': e.nid}).status_code == 422
