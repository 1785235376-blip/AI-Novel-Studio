"""Wave5 mounted production API, permissions, default-OFF/V1 and original ownership."""
from uuid import uuid4
import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_r5_project_forks_mounted import forks


def edition(e, title):
    return checked(e.client.post(e.base + '/language-editions', json={'title': title, 'source_language': 'en', 'target_language': 'ar', 'chapters': [{'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version']}]}), 201)


def test_actual_memory_review_reuse_and_history_keep_manuscript_unchanged(mounted):
    e = mounted; original = e.chapters.get(e.chapter['id']); source = edition(e, 'Memory source'); dest = edition(e, 'Memory destination')
    item = e.base + f"/language-editions/{source['id']}/segments/{source['segments'][0]['id']}"
    source = checked(e.client.put(item, json={'expected_version': source['version'], 'text': 'Human reviewed memory'}))
    source = checked(e.client.post(item + '/review', json={'expected_version': source['version'], 'action': 'submit'}))
    preview = checked(e.client.post(item + '/preview', json={'expected_version': source['version']}))
    source = checked(e.client.post(item + '/review', json={'expected_version': source['version'], 'action': 'accept', 'preview_digest': preview['preview_digest']}))
    target = e.base + f"/language-editions/{dest['id']}/segments/{dest['segments'][0]['id']}"
    response = e.client.post(target + '/memory', json={'expected_version': dest['version']}); candidate = checked(response)['items'][0]
    assert response.headers['cache-control'] == 'no-store'
    updated = checked(e.client.post(target + '/memory-adopt', json={'expected_version': dest['version'], **{k: candidate[k] for k in ('source_edition_id', 'source_segment_id', 'preview_digest')}}))
    assert updated['segments'][0]['status'] == 'DRAFT'
    old = checked(e.client.post(target + '/history', json={'expected_version': updated['version']}))['items'][0]
    restored = checked(e.client.post(target + '/restore', json={'expected_version': updated['version'], 'restore_version': old['version'], 'preview_digest': old['preview_digest']}))
    assert restored['segments'][0]['target_text'] == '' and e.chapters.get(e.chapter['id']) == original


def test_actual_shared_universe_pin_source_privacy_and_session_revocation(forks):
    e = forks; path = e.fbase + '/universe'; e.novels.upsert_location(e.nid, 'port', {'name': 'Universe port', 'privacy_level': 'CLOUD_ALLOWED'})
    source = next(r for r in checked(e.client.get(path + '/catalog'))['records'] if r['key'] == 'locations:port')
    body = {'universe_key': 'series', 'title': 'Universe snapshot', 'license': 'Synthetic owned', 'allow_local_copy': True, 'records': [{'key': source['key'], 'source_digest': source['source_digest']}]}
    preview = checked(e.client.post(path + '/snapshot-preview', json=body))
    row = checked(e.client.post(path + '/snapshots', json={**body, 'preview_digest': preview['preview_digest'], 'request_id': uuid4().hex}), 201)
    pin = {'snapshot_id': row['id'], 'target_project_id': e.nid, 'role': 'MAIN_NOVEL', 'expected_version': 0}
    pp = checked(e.client.post(path + '/pin-preview', json=pin))
    saved = checked(e.client.post(path + '/pins', json={**pin, 'preview_digest': pp['preview_digest'], 'confirmed': True}))
    assert saved['snapshot_digest'] == row['snapshot_digest']
    incoming = checked(e.client.get(path + '/incoming'))['items'][0]
    assert incoming['pin_id'] == saved['id']
    read = e.client.get(path + '/incoming/' + e.nid + '/' + saved['id'])
    assert checked(read)['snapshot']['records']['locations:port']['name'] == 'Universe port'
    assert read.headers['cache-control'] == 'no-store'
    e.novels.upsert_location(e.nid, 'port', {'name': 'Restricted port', 'privacy_level': 'LOCAL_ONLY'})
    assert checked(e.client.get(path + '/snapshots'))['items'][0]['content_withheld']
    assert checked(e.client.get(path + '/pins'))['items'][0]['content_withheld']
    e.sessions.revoke('fork-host')
    response = e.client.get(path + '/snapshots'); assert response.status_code == 401 and 'Universe snapshot' not in response.text


@pytest.mark.parametrize('cutoff', ['off', 'v1', 'world_missing'])
def test_actual_universe_server_gates_cannot_bypass_through_nested_routes(forks, monkeypatch, cutoff):
    from app.experimental.flags import FLAGS
    e = forks; before = e.store.read(e.nid, e.scope)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '' if cutoff == 'off' else ','.join(f for f in FLAGS if cutoff != 'world_missing' or f != 'world_character_engines_v2'))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', str(cutoff == 'v1'))
    for suffix in ['catalog', 'snapshots', 'pins', 'pins/unknown/history', 'incoming', 'incoming/unknown/unknown']:
        assert e.client.get(e.fbase + '/universe/' + suffix).status_code == 404
    for suffix in ['snapshot-preview', 'snapshots', 'pin-preview', 'pins', 'pins/unknown/release']:
        assert e.client.post(e.fbase + '/universe/' + suffix, json={}).status_code == 404
    assert e.store.read(e.nid, e.scope) == before


def test_actual_presence_interface_does_not_infer_online_members_or_write(mounted):
    e = mounted; before = e.store.read(e.nid, e.scope)
    response = e.client.get(e.base + '/writer-room/presence-contract'); contract = checked(response)
    assert response.headers['cache-control'] == 'no-store'
    assert contract['state'] == 'NOT_CONFIGURED' and contract['occupants'] == [] and contract['realtime'] is False
    assert contract['transport'] is None and e.store.read(e.nid, e.scope) == before
    assert checked(e.client.get(e.base + '/writer-room'))['presence'] == 'NOT_IMPLEMENTED'


def test_actual_reader_and_wrong_branch_cannot_access_private_memory_or_universe(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    for headers in [e.viewer_headers, {}, {**e.headers, 'X-Branch-ID': e.other_branch}]:
        response = e.client.post(e.base + '/language-editions/unknown/segments/unknown/memory', headers=headers, json={'expected_version': 1})
        assert response.status_code in {401, 403, 404}
        response = e.client.get(e.base + '/project-forks/universe/snapshots', headers=headers)
        if response.status_code == 422:
            assert response.json()['detail']['message'] == 'FORK_COLLABORATION_BRANCH_WRITER_UNAVAILABLE'
            assert 'items' not in response.json()
        else: assert response.status_code in {401, 403, 404}


def test_actual_interactive_history_restore_and_adapter_boundary_remain_review_only(mounted):
    from test_r5_interactive_story_mounted import create, approve
    e = mounted; original = e.chapters.get(e.chapter['id']); row, _ = create(e); row = approve(e, row)
    base = e.base + '/interactive-stories'; item = base + '/' + row['id']
    contract = checked(e.client.get(base + '/engine-contract'))
    assert contract['third_party_execution'] == 'DENY_ALL' and contract['runtime_status'] == 'NOT_RUN'
    history = checked(e.client.post(item + '/history', json={'expected_version': row['version']}))
    old = history['items'][0]
    restored = checked(e.client.post(item + '/restore-revision', json={'expected_version': row['version'], 'restore_version': old['version'], 'preview_digest': old['preview_digest']}))
    assert restored['status'] == 'DRAFT' and restored['version'] == row['version'] + 1
    assert e.chapters.get(e.chapter['id']) == original
