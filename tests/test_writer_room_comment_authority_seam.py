"""Backward-compatible original-comment precommit callback; no parallel authority."""
import copy
import pytest
from fastapi import HTTPException
from app.identity import IdentityStatus
from app.services.creation_workbench_service import CommentIn
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


def test_original_comment_default_contract_unchanged_and_denied_callback_rolls_back(mounted):
    e = mounted
    body = CommentIn(chapter_id=e.chapter['id'], chapter_version=e.chapter['version'], text='Original default behavior')
    row = e.creation.create_comment(e.nid, e.scope, 'local-author', body)
    before = copy.deepcopy(e.creation.list_comments(e.nid, e.scope))
    def deny(): raise PermissionError('revoked before commit')
    with pytest.raises(PermissionError):
        e.creation.update_comment(e.nid, e.scope, 'local-author', row['id'], 'reply', 1, 'Denied candidate', reauthorize=deny)
    assert e.creation.list_comments(e.nid, e.scope) == before
    with pytest.raises(PermissionError):
        e.creation.create_comment(e.nid, e.scope, 'local-author', body, reauthorize=deny)
    assert e.creation.list_comments(e.nid, e.scope) == before
    updated = e.creation.update_comment(e.nid, e.scope, 'local-author', row['id'], 'reply', 1, 'Default still supported')
    assert updated['version'] == 2 and len(updated['messages']) == 2


def test_original_comment_callback_rechecks_real_membership_after_source_read_before_commit(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    anchor = e.creation._anchor
    def revoked(*args):
        result = anchor(*args)
        e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
        return result
    monkeypatch.setattr(e.creation, '_anchor', revoked)
    check = lambda: e.api._workbench_authorize(e.nid, e.lead, e.branch, 'domain.write')
    body = CommentIn(chapter_id=e.chapter['id'], chapter_version=e.chapter['version'], text='Must not persist')
    with pytest.raises(HTTPException) as exc:
        e.creation.create_comment(e.nid, e.scope, e.lead, body, reauthorize=check)
    assert exc.value.status_code == 403
    assert e.creation.list_comments(e.nid, e.scope)['items'] == []
