from __future__ import annotations
from types import SimpleNamespace
import copy
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.common import DomainService
from app.experimental.inbox import ReviewBinding, ReviewContext, UnifiedReviewInbox
from app.experimental.inbox_api import create_inbox_router, BatchItem
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'unified_review_inbox,advanced_planning_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    scope = {'mode': 'local', 'novel_id': 'n'}
    ctx = ReviewContext('n', scope, 'author')
    service = DomainService(ExperimentalStore(tmp_path), SimpleNamespace(get=lambda n: {}), None)
    calls = []
    def listing(context):
        return [{**r, 'preview': r['title'], 'allowed_actions': ['approve', 'reject'] if r['status'] == 'REVIEW' else []} for r in service.list(context.novel_id, context.scope, 'proposals')]
    def review(context, rid, action, version):
        calls.append((rid, action, version))
        return service.mutate(context.novel_id, context.scope, context.actor, 'proposals', rid, version,
                              lambda r: r.update(status='APPROVED' if action == 'approve' else 'REJECTED'))
    inbox = UnifiedReviewInbox()
    inbox.register(ReviewBinding('planning', listing, review, 'advanced_planning_v2', frozenset({'reject'})))
    a = service.create('n', scope, 'author', 'proposals', {'title': 'Moon voyage', 'status': 'REVIEW'})
    b = service.create('n', scope, 'author', 'proposals', {'title': 'River voyage', 'status': 'REVIEW'})
    return inbox, service, ctx, calls, a, b


def test_inbox_filter_projection_and_delegate(inbox):
    box, service, ctx, calls, a, b = inbox
    rows = box.list(ctx, search='moon', status='REVIEW')['items']
    assert len(rows) == 1 and rows[0]['id'] == a['id']
    assert rows[0]['scope'] == ctx.scope and rows[0]['privacy_state'] == 'LOCAL_ONLY'
    assert rows[0]['batch_actions'] == ['reject']
    result = box.review(ctx, 'planning', a['id'], 'approve', 1)
    assert result['status'] == 'APPROVED' and calls == [(a['id'], 'approve', 1)]
    with pytest.raises(CapabilityVersionConflict):
        box.review(ctx, 'planning', a['id'], 'approve', 1)
    assert len(calls) == 1
    foreign = ReviewContext('other', {'mode': 'local', 'novel_id': 'other'}, 'author')
    assert box.list(foreign)['items'] == []
    with pytest.raises(FileNotFoundError):
        box.review(foreign, 'planning', a['id'], 'approve', 1)


def test_batch_preflight_blocks_unsafe_types_and_duplicate_targets(inbox):
    box, service, ctx, calls, a, b = inbox
    items = [BatchItem(domain='planning', id=a['id'], action='reject', expected_version=1),
             BatchItem(domain='planning', id=b['id'], action='approve', expected_version=1)]
    with pytest.raises(ValueError, match='does not permit'):
        box.batch(ctx, items, lambda: None)
    assert calls == []
    with pytest.raises(ValueError, match='duplicate'):
        box.batch(ctx, [items[0], items[0]], lambda: None)
    assert calls == []


def test_batch_partial_receipt_preserves_success_and_stops_on_revoke(inbox):
    box, service, ctx, calls, a, b = inbox
    items = [BatchItem(domain='planning', id=r['id'], action='reject', expected_version=1) for r in (a,b)]
    checks = []
    def authorize():
        checks.append(True)
        if len(checks) == 2:
            raise HTTPException(403, 'revoked')
    result = box.batch(ctx, items, authorize)
    assert result['status'] == 'PARTIAL'
    assert [r['status'] for r in result['results']] == ['SUCCEEDED', 'FAILED']
    assert service.get('n', ctx.scope, 'proposals', a['id'])['status'] == 'REJECTED'
    assert service.get('n', ctx.scope, 'proposals', b['id'])['status'] == 'REVIEW'
    assert len(calls) == 1


def test_flags_hide_domains_and_fail_closed(inbox, monkeypatch):
    box, _, ctx, _, a, _ = inbox
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'unified_review_inbox')
    assert box.list(ctx)['items'] == []
    with pytest.raises(FileNotFoundError):
        box.review(ctx, 'planning', a['id'], 'approve', 1)


def test_api_authorization_and_review_permission_are_not_write_bypass(inbox):
    box, service, ctx, calls, a, b = inbox
    from app.experimental.flags import require_flag
    def authorize(nid, token, branch, permission):
        if token != 'reader': raise HTTPException(401, 'required')
        if permission != 'domain.read': raise HTTPException(403, 'review denied')
        return ctx.actor, ctx.scope
    app = FastAPI()
    app.include_router(create_inbox_router(box, authorize, require_flag))
    client = TestClient(app)
    prefix = '/novels/n/experimental/review-inbox'
    assert client.get(prefix).status_code == 401
    assert client.get(prefix, headers={'X-Session-Token': 'reader'}).status_code == 200
    assert client.post(prefix + '/planning/' + a['id'] + '/approve', headers={'X-Session-Token': 'reader'}, json={'expected_version':1}).status_code == 403
    assert calls == []


def test_projection_cannot_leak_cross_scope(inbox):
    box, _, ctx, _, a, _ = inbox
    box.register(ReviewBinding('broken', lambda _: [{'id': 'secret', 'novel_id': 'other', 'preview': 'private'}]))
    with pytest.raises(ValueError, match='escaped'):
        box.list(ctx)
