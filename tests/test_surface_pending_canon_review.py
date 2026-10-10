"""Original Canon owner: no parallel table, project authorization and recoverable CAS."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.experimental.flags import RUNTIME_FLAGS
from app.services.pending_canon_review_service import PendingCanonReviewService, CanonPreviewIn, CanonDecisionIn
from app.services.finding_review_service import FindingReviewConflict
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def canon_env(mounted, monkeypatch):
    e = mounted
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(RUNTIME_FLAGS))
    e.canon_review = PendingCanonReviewService(e.canon, e.chapters, e.novels)
    captured = e.api.pending_canon_review_service
    for key, value in [('canon', e.canon), ('chapters', e.chapters), ('novels', e.novels)]:
        monkeypatch.setattr(captured, key, value)
    e.pending_id = str(uuid4())
    e.pending_row = {'id': e.pending_id, 'novel_id': e.nid, 'chapter': e.chapter['number'], 'status': 'PENDING',
                     'proposals': [{'fact': 'The door is sealed.', 'source_job': 'existing-job', 'privacy_level': 'LOCAL_ONLY'}]}
    e.canon.save_pending(e.pending_row)
    e.canon_base = e.prefix + f'/projects/{e.nid}/pending-canon'
    return e


def preview(e):
    return e.canon_review.preview(e.nid, e.pending_id, CanonPreviewIn(chapter_id=e.chapter['id']))


def decision(row, action='approve'):
    return CanonDecisionIn(expected_version=row['version'], preview_digest=row['preview_digest'],
        chapter_id=(row.get('source') or {}).get('chapter_id'), action=action, reason='Checked the complete candidate and source.',
        operation_id=uuid4().hex, confirmed=True)


def test_canon_preview_cas_source_fence_human_review_no_duplicates_restart(canon_env):
    e = canon_env
    not_configured = e.canon_review.preview(e.nid, e.pending_id, CanonPreviewIn())
    assert not_configured['source_state'] == 'NOT_CONFIGURED' and not_configured['allowed_actions'] == ['reject']
    assert e.canon.list(e.nid) == []
    with pytest.raises(ValueError, match='CANON_SOURCE_REQUIRED'):
        e.canon_review.review(e.nid, e.pending_id, 'author', decision(not_configured))
    row = preview(e); request = decision(row)
    assert row['lineage'] == 'LEGACY_SOURCE_VERSION_NOT_RECORDED'
    approved = e.canon_review.review(e.nid, e.pending_id, 'author', request)
    assert approved['status'] == 'APPROVED' and approved['version'] == 2
    assert approved['history'][0]['reason'] == request.reason
    assert len(e.canon.list(e.nid)) == 1
    assert e.canon.list(e.nid)[0]['privacy_level'] == 'LOCAL_ONLY'
    restarted = PendingCanonReviewService(e.canon, e.chapters, e.novels)
    assert restarted.review(e.nid, e.pending_id, 'author', request)['version'] == 2
    assert len(e.canon.list(e.nid)) == 1
    with pytest.raises(FindingReviewConflict, match='CANON_VERSION_CONFLICT'):
        restarted.review(e.nid, e.pending_id, 'author', decision(row, 'reject'))
    # Legacy clients retain their original methods but cannot overwrite a
    # versioned reviewed candidate or add the same accepted fact again.
    with pytest.raises(ValueError, match='VERSIONED_CANON_REVIEW_REQUIRED'):
        e.canon.approve(e.pending_id)
    with pytest.raises(ValueError, match='VERSIONED_CANON_REVIEW_REQUIRED'):
        e.canon.reject(e.pending_id)


def test_canon_pending_edits_and_source_change_invalidate_preview(canon_env):
    e = canon_env; row = preview(e)
    modified = deepcopy(e.pending_row); modified['proposals'][0]['fact'] = 'The door is open.'
    e.canon.save_pending(modified)
    with pytest.raises(FindingReviewConflict, match='CANON_PREVIEW_STALE'):
        e.canon_review.review(e.nid, e.pending_id, 'author', decision(row))
    row = preview(e)
    e.chapters.save(e.chapter['id'], {'content': 'Changed chapter.', 'version': e.chapter['version']})
    with pytest.raises(FindingReviewConflict, match='CANON_PREVIEW_STALE'):
        e.canon_review.review(e.nid, e.pending_id, 'author', decision(row))
    assert e.canon.list(e.nid) == []
    current = preview(e)
    rejected = e.canon_review.review(e.nid, e.pending_id, 'author', decision(current, 'reject'))
    assert rejected['status'] == 'REJECTED' and e.canon.list(e.nid) == []


def test_canon_concurrent_review_has_one_winner(canon_env):
    e = canon_env; row = preview(e)
    def worker(i):
        try: return e.canon_review.review(e.nid, e.pending_id, f'actor-{i}', decision(row))
        except FindingReviewConflict as exc: return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool: result = list(pool.map(worker, [1, 2]))
    assert sum(isinstance(x, dict) for x in result) == 1
    assert result.count('CANON_VERSION_CONFLICT') == 1 and len(e.canon.list(e.nid)) == 1


def test_actual_main_canon_routes_v1_disable_and_validation(canon_env, monkeypatch):
    e = canon_env; base = e.canon_base; client = e.client
    assert len(checked(client.get(base + '/review'))['items']) == 1
    row = checked(client.post(base + f'/{e.pending_id}/preview', json={'chapter_id': e.chapter['id']}))
    assert client.post(base + f'/{e.pending_id}/review', json={'action': 'approve'}).status_code == 422
    assert client.post(base + f'/{e.pending_id}/review', json=decision(row).model_dump()).status_code == 200
    assert client.post(base + f'/{e.pending_id}/review', json=decision(row).model_dump()).status_code == 409
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.get(base + '/review').status_code == 404
    monkeypatch.delenv('V1_ACCEPTANCE_MODE')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert client.get(base + '/review').status_code == 404


def test_actual_main_canon_branch_role_is_not_project_review_and_revoke(canon_env, monkeypatch):
    e = canon_env; scoped(e, monkeypatch)
    base = e.canon_base; client = e.client
    assert client.get(base + '/review').status_code == 401
    assert client.get(base + '/review', headers=e.headers).status_code == 403
    assert client.post(base + f'/{e.pending_id}/preview', headers=e.headers, json={'chapter_id': e.chapter['id']}).status_code == 403
    role = DomainRoleAssignment('project-canon-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    row = checked(client.post(base + f'/{e.pending_id}/preview', headers=e.headers, json={'chapter_id': e.chapter['id']}))
    # Another project is never selected from the candidate ID.
    assert client.post(e.prefix + f'/projects/other/pending-canon/{e.pending_id}/preview', headers=e.headers, json={}).status_code in {403, 404}
    e.authorization.revoke_role(role.id, e.lead)
    assert client.post(base + f'/{e.pending_id}/review', headers=e.headers, json=decision(row).model_dump()).status_code == 403
    assert e.canon.list(e.nid) == []


def test_file_canon_restart_after_facts_commit_finishes_receipt_without_duplicate(canon_env, monkeypatch):
    e = canon_env
    if e.backend != "file":
        # PostgreSQL is a real transaction: no prepared two-file state exists.
        row = preview(e)
        def interrupted(): raise RuntimeError("interrupted before commit")
        with pytest.raises(RuntimeError): e.canon_review.review(e.nid, e.pending_id, "author", decision(row), interrupted)
        assert e.canon.list(e.nid) == []
        return
    import app.repositories.file.canon as file_canon
    row = preview(e); request = decision(row); original = file_canon.atomic_write
    def fail_final(path, content):
        import json
        if path.name == f'{e.pending_id}.json' and json.loads(content).get('status') == 'APPROVED': raise OSError('simulated process stop before final receipt')
        return original(path, content)
    monkeypatch.setattr(file_canon, 'atomic_write', fail_final)
    with pytest.raises(OSError, match='simulated'):
        e.canon_review.review(e.nid, e.pending_id, 'author', request)
    assert len(e.canon.list(e.nid)) == 1
    assert e.canon.repository.get_pending(e.pending_id)['_review_commit']
    monkeypatch.setattr(file_canon, 'atomic_write', original)
    e.chapters.save(e.chapter['id'], {'content': 'Changed after already committed.', 'version': e.chapter['version']})
    restarted = PendingCanonReviewService(e.canon, e.chapters, e.novels)
    final = restarted.review(e.nid, e.pending_id, 'author', request)
    assert final['status'] == 'APPROVED' and len(e.canon.list(e.nid)) == 1
    assert '_review_commit' not in e.canon.repository.get_pending(e.pending_id)


def test_file_canon_cancel_prepared_write_before_facts_commit_and_resume(canon_env, monkeypatch):
    e = canon_env
    if e.backend != "file":
        # PostgreSQL is a real transaction: no prepared two-file state exists.
        row = preview(e)
        def interrupted(): raise RuntimeError("interrupted before commit")
        with pytest.raises(RuntimeError): e.canon_review.review(e.nid, e.pending_id, "author", decision(row), interrupted)
        assert e.canon.list(e.nid) == []
        return
    import app.repositories.file.canon as file_canon
    row = preview(e); request = decision(row); original = file_canon.atomic_write
    def fail_canon(path, content):
        if path.name == 'canon.json': raise OSError('simulated disk failure')
        return original(path, content)
    monkeypatch.setattr(file_canon, 'atomic_write', fail_canon)
    with pytest.raises(OSError, match='simulated'):
        e.canon_review.review(e.nid, e.pending_id, 'author', request)
    assert e.canon.list(e.nid) == []
    monkeypatch.setattr(file_canon, 'atomic_write', original)
    cancelled = e.canon_review.cancel_recovery(e.nid, e.pending_id, 'author', 1)
    assert cancelled['status'] == 'PENDING' and cancelled['version'] == 2
    assert cancelled['history'][0]['action'] == 'CANCELLED_RECOVERY'
    with pytest.raises(FindingReviewConflict, match='CANON_VERSION_CONFLICT'):
        e.canon_review.review(e.nid, e.pending_id, 'author', request)
    new = preview(e)
    assert e.canon_review.review(e.nid, e.pending_id, 'author', decision(new))['status'] == 'APPROVED'
    assert len(e.canon.list(e.nid)) == 1


def test_original_canon_approve_retry_terminal_edits_reject_and_save_are_idempotent(canon_env):
    e = canon_env
    first = e.canon.approve(e.pending_id)
    assert first['status'] == 'APPROVED' and len(e.canon.list(e.nid)) == 1
    assert e.canon.approve(e.pending_id) == first
    assert len(e.canon.list(e.nid)) == 1
    with pytest.raises(ValueError, match='CANON_TERMINAL_EDIT_FORBIDDEN'):
        e.canon.approve(e.pending_id, [{'fact': 'different'}])
    with pytest.raises(ValueError, match='CANON_ALREADY_REVIEWED'):
        e.canon.reject(e.pending_id)
    assert e.canon.save_pending(e.pending_row)['status'] == 'APPROVED'
    assert e.canon.repository.get_pending(e.pending_id)['status'] == 'APPROVED'
    other = {**e.pending_row, 'id': str(uuid4())}
    e.canon.save_pending(other)
    assert e.canon.reject(other['id'])['status'] == 'REJECTED'
    assert e.canon.reject(other['id'])['status'] == 'REJECTED'
    with pytest.raises(ValueError, match='CANON_ALREADY_REVIEWED'):
        e.canon.approve(other['id'])


def test_canon_terminal_history_remains_listed_and_other_author_can_recover_receipt(canon_env, monkeypatch):
    e = canon_env
    row = preview(e); request = decision(row)
    if e.backend == 'file':
        import app.repositories.file.canon as file_canon
        import json
        original = file_canon.atomic_write
        def fail_final(path, content):
            if path.name == f'{e.pending_id}.json' and json.loads(content).get('status') == 'APPROVED': raise OSError('interrupted receipt')
            return original(path, content)
        monkeypatch.setattr(file_canon, 'atomic_write', fail_final)
        with pytest.raises(OSError): e.canon_review.review(e.nid, e.pending_id, 'author', request)
        monkeypatch.setattr(file_canon, 'atomic_write', original)
        final = e.canon_review.recover(e.nid, e.pending_id, 1)
    else:
        final = e.canon_review.review(e.nid, e.pending_id, 'author', request)
    assert final['status'] == 'APPROVED'
    listed = e.canon_review.list(e.nid)['items'][0]
    assert listed['status'] == 'APPROVED' and listed['history'][0]['action'] == 'APPROVE'
    assert not listed['stale_source']


def test_canon_deleted_or_archived_source_does_not_block_receipt_history_or_other_rows(canon_env, monkeypatch):
    e = canon_env; row = preview(e); request = decision(row)
    if e.backend == 'file':
        import app.repositories.file.canon as file_canon
        import json
        original = file_canon.atomic_write
        def fail_final(path, content):
            if path.name == f'{e.pending_id}.json' and json.loads(content).get('status') == 'APPROVED': raise OSError('interrupted receipt')
            return original(path, content)
        monkeypatch.setattr(file_canon, 'atomic_write', fail_final)
        with pytest.raises(OSError): e.canon_review.review(e.nid, e.pending_id, 'author', request)
        monkeypatch.setattr(file_canon, 'atomic_write', original)
        e.chapters.delete(e.chapter['id'])
        final = e.canon_review.recover(e.nid, e.pending_id, 1)
    else:
        final = e.canon_review.review(e.nid, e.pending_id, 'author', request)
        e.chapters.archive(e.chapter['id'], e.chapter['version'])
        final = e.canon_review.preview(e.nid, e.pending_id, CanonPreviewIn())
    assert final['source_state'] == 'SOURCE_UNAVAILABLE' and final['stale_source']
    assert final['history'][0]['source']['chapter_id'] == e.chapter['id']
    assert len(e.canon.list(e.nid)) == 1
    another = {**e.pending_row, 'id': str(uuid4()), 'chapter_id': e.chapter['id']}
    e.canon.save_pending(another)
    listed = e.canon_review.list(e.nid)['items']
    assert len(listed) == 2 and all(row['source_state'] == 'SOURCE_UNAVAILABLE' for row in listed)


def test_actual_main_canon_withholds_preview_after_late_project_revoke(canon_env, monkeypatch):
    e = canon_env; scoped(e, monkeypatch)
    role = DomainRoleAssignment('canon-late-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    service = e.api.pending_canon_review_service; original = service.preview
    def revoke(*args):
        result = original(*args); e.authorization.revoke_role(role.id, e.lead); return result
    monkeypatch.setattr(service, 'preview', revoke)
    response = e.client.post(e.canon_base + f'/{e.pending_id}/preview', headers=e.headers, json={'chapter_id': e.chapter['id']})
    assert response.status_code == 403 and 'The door is sealed.' not in response.text


def test_canon_exact_preview_evidence_and_archived_source_withheld(canon_env):
    e = canon_env; row = preview(e)
    assert row['source_evidence']['content'] == e.chapter['content']
    assert row['source_evidence']['version'] == row['source']['version']
    final = e.canon_review.review(e.nid, e.pending_id, 'author', decision(row))
    e.chapters.archive(e.chapter['id'], e.chapter['version'])
    unavailable = e.canon_review.preview(e.nid, e.pending_id, CanonPreviewIn())
    assert unavailable['source_evidence'] is None and unavailable['source'] is None
    assert unavailable['source_state'] == 'SOURCE_UNAVAILABLE' and unavailable['stale_source']
    assert unavailable['history'] == final['history']


def test_actual_main_canon_revoke_after_source_load_prevents_commit(canon_env, monkeypatch):
    e = canon_env; scoped(e, monkeypatch)
    role = DomainRoleAssignment('canon-commit-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    row = preview(e); service = e.api.pending_canon_review_service; original = service._preview
    def revoke(*args):
        result = original(*args); e.authorization.revoke_role(role.id, e.lead); return result
    monkeypatch.setattr(service, '_preview', revoke)
    response = e.client.post(e.canon_base + f'/{e.pending_id}/review', headers=e.headers, json=decision(row).model_dump())
    assert response.status_code == 403 and e.canon.list(e.nid) == []
    assert e.canon.repository.get_pending(e.pending_id)['status'] == 'PENDING'


def test_canon_terminal_source_identity_cannot_follow_a_different_active_chapter(canon_env):
    e = canon_env; original = preview(e)
    e.canon_review.review(e.nid, e.pending_id, 'author', decision(original))
    other = e.chapters.create(e.nid, {'title': 'Different active chapter', 'content': 'DIFFERENT_SOURCE_MUST_NOT_REPLACE_RECEIPT'})
    terminal = e.canon_review.preview(e.nid, e.pending_id, CanonPreviewIn(chapter_id=other['id']))
    assert terminal['source'] == original['source']
    assert terminal['source_evidence'] == original['source_evidence']
    assert not terminal['stale_source']


@pytest.mark.parametrize('action,committed', [('recover', True), ('cancel-recovery', False)])
def test_actual_main_canon_recovery_and_cancel_routes(canon_env, monkeypatch, action, committed):
    e = canon_env; row = preview(e)
    if e.backend == 'file':
        import app.repositories.file.canon as file_canon
        import json
        original = file_canon.atomic_write
        def interrupt(path, content):
            if ((committed and path.name == f'{e.pending_id}.json' and json.loads(content).get('status') == 'APPROVED')
                or (not committed and path.name == 'canon.json')): raise OSError('Synthetic interrupted write')
            return original(path, content)
        monkeypatch.setattr(file_canon, 'atomic_write', interrupt)
        with pytest.raises(OSError): e.canon_review.review(e.nid, e.pending_id, 'author', decision(row))
        monkeypatch.setattr(file_canon, 'atomic_write', original)
        response = e.client.post(e.canon_base + f'/{e.pending_id}/{action}', json={'expected_version': 1})
        result = checked(response)
        assert result['version'] == 2 and not result['recovery_required']
        assert result['status'] == ('APPROVED' if committed else 'PENDING')
        assert len(e.canon.list(e.nid)) == int(committed)
    else:
        response = e.client.post(e.canon_base + f'/{e.pending_id}/{action}', json={'expected_version': 1})
        assert response.status_code == 422 and 'CANON_NO_PENDING_RECOVERY' in response.text
