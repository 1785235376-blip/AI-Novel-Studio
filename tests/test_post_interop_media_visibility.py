"""Missing original sources must not hide independent persisted media work."""
import json
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.media import MediaService
from app.experimental.media_api import create_media_router
from app.experimental.flags import require_flag
from app.storage import atomic_write
from test_r3_media_support import rig


def remove_original_character(e):
    """Withdraw only this synthetic source from its actual File/PG repository."""
    if e.backend == 'file':
        path = e.bundle.novels.backend.novels / e.nid / 'characters' / 'characters.json'
        rows = json.loads(path.read_text())
        atomic_write(path, json.dumps([row for row in rows if row['id'] != 'alice']))
    else:
        from sqlalchemy import delete, select
        from app.repositories.postgres.models import CharacterModel, NovelModel
        with e.bundle.novels.database.session() as session:
            nid = session.scalar(select(NovelModel.id).where(NovelModel.slug == e.nid))
            session.execute(delete(CharacterModel).where(CharacterModel.novel_id == nid, CharacterModel.slug == 'alice'))
    assert not any(row['id'] == 'alice' for row in e.novels.data_set(e.nid, 'characters'))


def candidates(e):
    service = MediaService(e.store, e.novels, e.chapters, e.assets, e.screenplays)
    old = service.create_cover(e.nid, e.scope, e.actor, {'title': 'Character cover', 'character_ids': ['alice']})
    valid = service.create_cover(e.nid, e.scope, e.actor, {'title': 'Independent cover'})
    remove_original_character(e)
    return service, old, valid


def test_missing_character_marks_only_its_cover_stale_and_keeps_queue_fence(rig):
    service, old, valid = candidates(rig)
    before = rig.store.read(rig.nid, rig.scope)
    rows = {row['id']: row for row in service.briefs(rig.nid, rig.scope, 'COVER')}
    assert rows[old['id']]['stale'] is True
    assert rows[valid['id']]['stale'] is False
    assert rig.store.read(rig.nid, rig.scope) == before
    with pytest.raises(ValueError, match='MEDIA_CHARACTER_REFERENCE_INVALID'):
        service.queue(rig.nid, rig.scope, rig.actor, {'brief_id': old['id'], 'expected_brief_version': old['version'], 'adapter_id': 'mock-image-v1'})
    task = service.queue(rig.nid, rig.scope, rig.actor, {'brief_id': valid['id'], 'expected_brief_version': valid['version'], 'adapter_id': 'mock-image-v1'})
    assert task['brief_id'] == valid['id']


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_source_withdrawal_keeps_authorized_mounted_cover_list_available(rig, monkeypatch, prefix):
    service, old, valid = candidates(rig)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'cover_storyboard_generation')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    def authorize(nid, token, branch, permission):
        if token != 'owner' or nid != rig.nid: raise HTTPException(403, 'denied')
        return rig.actor, rig.scope
    app = FastAPI(); app.include_router(create_media_router(service, authorize, require_flag), prefix=prefix)
    client = TestClient(app); url = f'{prefix}/novels/{rig.nid}/experimental/media/cover-briefs'
    assert client.get(url).status_code == 403
    response = client.get(url, headers={'X-Session-Token': 'owner'})
    assert response.status_code == 200
    rows = {row['id']: row for row in response.json()['items']}
    assert rows[old['id']]['stale'] and not rows[valid['id']]['stale']
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.get(url, headers={'X-Session-Token': 'owner'}).status_code == 404


def test_unknown_owner_configuration_error_is_not_falsely_called_source_staleness(rig, monkeypatch):
    service = MediaService(rig.store, rig.novels, rig.chapters, rig.assets, rig.screenplays)
    service.create_cover(rig.nid, rig.scope, rig.actor, {'title': 'Cover'})
    def unavailable(*args): raise ValueError('MEDIA_OWNER_CONFIGURATION_UNAVAILABLE')
    monkeypatch.setattr(service, '_assert_brief', unavailable)
    with pytest.raises(ValueError, match='MEDIA_OWNER_CONFIGURATION_UNAVAILABLE'):
        service.briefs(rig.nid, rig.scope, 'COVER')


def generated_candidates(e):
    """Generate while the original source exists, then withdraw only Alice."""
    service = MediaService(e.store, e.novels, e.chapters, e.assets, e.screenplays)
    briefs = [service.create_cover(e.nid, e.scope, e.actor, body) for body in (
        {'title': 'Generated character cover', 'character_ids': ['alice']},
        {'title': 'Generated independent cover'},
    )]
    tasks = []
    for brief in briefs:
        task = service.queue(e.nid, e.scope, e.actor, {'brief_id': brief['id'], 'expected_brief_version': brief['version'],
                                                     'adapter_id': 'mock-image-v1', 'candidate_count': 2})
        tasks.append(service.execute(e.nid, e.scope, e.actor, task['id'], task['version']))
    remove_original_character(e)
    return service, briefs, tasks


def test_generated_candidates_survive_character_withdrawal_without_reopening_stale_writes(rig):
    service, (old, valid), (old_task, valid_task) = generated_candidates(rig)
    before = rig.store.read(rig.nid, rig.scope)
    briefs = {row['id']: row for row in service.briefs(rig.nid, rig.scope, 'COVER')}
    assert briefs[old['id']]['stale'] is True and briefs[valid['id']]['stale'] is False
    assert len(service.tasks(rig.nid, rig.scope)) == 2
    proposals = {row['id']: row for row in service.proposals(rig.nid, rig.scope)}
    assert len(proposals) == 4
    assert all(proposals[pid]['stale'] is True for pid in old_task['proposal_ids'])
    assert all(proposals[pid]['stale'] is False for pid in valid_task['proposal_ids'])
    assert all('content_base64' not in row for row in proposals.values())
    for task, stale in ((old_task, True), (valid_task, False)):
        compared = service.compare(rig.nid, rig.scope, task['proposal_ids'])
        assert compared['same_source_version'] is True
        assert compared['approval_requires_current_source'] is True
        assert all(row['stale'] is stale for row in compared['items'])
    inbox = {row['id']: row for row in service.list_review_items(rig.nid, rig.scope)}
    assert len(inbox) == 4 and inbox[old_task['proposal_ids'][0]]['stale'] is True
    assert inbox[valid_task['proposal_ids'][0]]['stale'] is False
    assert rig.store.read(rig.nid, rig.scope) == before
    with pytest.raises(ValueError, match='^MEDIA_CHARACTER_REFERENCE_INVALID$'):
        service.queue(rig.nid, rig.scope, rig.actor, {'brief_id': old['id'], 'expected_brief_version': old['version'], 'adapter_id': 'mock-image-v1'})
    with pytest.raises(ValueError, match='^MEDIA_CHARACTER_REFERENCE_INVALID$'):
        service.review(rig.nid, rig.scope, rig.actor, old_task['proposal_ids'][0], 'approve', 1)
    assert rig.store.read(rig.nid, rig.scope) == before and rig.assets.list(rig.nid) == []
    approved = service.review(rig.nid, rig.scope, rig.actor, valid_task['proposal_ids'][0], 'approve', 1)
    assert approved['status'] == 'APPROVED' and rig.assets.get(approved['asset_id'])['novel_id'] == rig.nid
    next_task = service.queue(rig.nid, rig.scope, rig.actor, {'brief_id': valid['id'], 'expected_brief_version': valid['version'], 'adapter_id': 'mock-image-v1'})
    assert next_task['status'] == 'QUEUED'
    assert service.get(rig.nid, rig.scope, service.PROPOSALS, old_task['proposal_ids'][0])['status'] == 'PENDING_REVIEW'


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_generated_candidate_http_lists_compare_and_promotion_remain_source_fenced(rig, monkeypatch, prefix):
    service, (old, valid), (old_task, valid_task) = generated_candidates(rig)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'cover_storyboard_generation')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    permissions = []
    def authorize(nid, token, branch, permission):
        if token != 'owner' or nid != rig.nid: raise HTTPException(403, 'denied')
        permissions.append(permission)
        return rig.actor, rig.scope
    app = FastAPI(); app.include_router(create_media_router(service, authorize, require_flag), prefix=prefix)
    client = TestClient(app); base = f'{prefix}/novels/{rig.nid}/experimental/media'
    headers = {'X-Session-Token': 'owner'}
    for suffix, count in (('/cover-briefs', 2), ('/storyboard-briefs', 0), ('/tasks', 2), ('/proposals', 4)):
        assert client.get(base + suffix).status_code == 403
        response = client.get(base + suffix, headers=headers)
        assert response.status_code == 200 and len(response.json()['items']) == count
    response = client.post(base + '/proposals/compare', headers=headers, json={'proposal_ids': old_task['proposal_ids']})
    assert response.status_code == 200 and all(row['stale'] for row in response.json()['items'])
    assert client.post(base + '/proposals/compare', json={'proposal_ids': old_task['proposal_ids']}).status_code == 403
    rejected_queue = client.post(base + '/tasks', headers=headers, json={'brief_id': old['id'], 'expected_brief_version': old['version'], 'adapter_id': 'mock-image-v1'})
    assert rejected_queue.status_code == 422 and rejected_queue.json()['detail']['message'] == 'MEDIA_CHARACTER_REFERENCE_INVALID'
    rejected_approval = client.post(base + f'/proposals/{old_task["proposal_ids"][0]}/approve', headers=headers, json={'expected_version': 1})
    assert rejected_approval.status_code == 422 and rejected_approval.json()['detail']['message'] == 'MEDIA_CHARACTER_REFERENCE_INVALID'
    assert rig.assets.list(rig.nid) == []
    approved = client.post(base + f'/proposals/{valid_task["proposal_ids"][0]}/approve', headers=headers, json={'expected_version': 1})
    assert approved.status_code == 200 and approved.json()['status'] == 'APPROVED'
    assert permissions[-1] == 'domain.review'
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.get(base + '/proposals', headers=headers).status_code == 404
    assert client.post(base + '/proposals/compare', headers=headers, json={'proposal_ids': valid_task['proposal_ids']}).status_code == 404


@pytest.mark.parametrize('error_type,message', [
    (ValueError, 'MEDIA_OWNER_CONFIGURATION_UNAVAILABLE'),
    (ValueError, 'MEDIA_CHARACTER_REFERENCE_INVALID_UNEXPECTED_SUFFIX'),
    (PermissionError, 'revoked'),
])
def test_generated_candidate_staleness_does_not_swallow_other_errors(rig, monkeypatch, error_type, message):
    service, _, (old_task, _) = generated_candidates(rig)
    def unavailable(*args): raise error_type(message)
    monkeypatch.setattr(service, '_assert_brief', unavailable)
    for read in (lambda: service.briefs(rig.nid, rig.scope, 'COVER'),
                 lambda: service.proposals(rig.nid, rig.scope),
                 lambda: service.compare(rig.nid, rig.scope, old_task['proposal_ids']),
                 lambda: service.list_review_items(rig.nid, rig.scope)):
        with pytest.raises(error_type, match=f'^{message}$'):
            read()
