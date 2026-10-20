"""Real File/ImageJob + original mounted Studio Host invoker, no model runtime.

The small test router submits server-only bindings. Public standalone routes
never accept this internal field. U16's actual facade is tested separately.
"""
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import APIRouter, Header, Request

from app.creative.production_execution_models import MediaCommand, MediaCreate, MediaJobAction, MediaReview
from app.experimental.common import new_row
from app.experimental.planning import digest
from app.experimental.safe_batches import ACTIVE, ACTIVE_LOCK
from app.experimental.safe_batch_studio_image import CONTRACT
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_manual_mask_api import mask_client
from test_v2_cpu_cutout_api import cpu_client, preview, action


@pytest.fixture
def bound(cpu_client, monkeypatch):
    e = cpu_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,safe_batches_v2,reader_preflight_v2')
    e.batches = e.experimental.safe_batches_service
    e.image_batches = e.batches.studio_image
    assert e.image_batches.production is e.production
    captured = checked(preview(e))
    actor, resolved_scope = e.experimental.authorize(e.nid, e.host, None, 'domain.write')
    assert resolved_scope == e.scope
    context = e.production._base(e.nid, e.scope, actor, lambda: None)
    e.claim = uuid4().hex
    frozen = {'steps': [{'input': {'kind': 'STUDIO_IMAGE'},
        'configuration': {'incarnation': context['incarnation'], 'command': captured['command']}}]}
    e.batch = new_row(e.nid, e.scope, actor, {'snapshot': frozen, 'snapshot_digest': digest(frozen),
        'confirmed': True, 'status': 'RUNNING', 'items': [{'status': 'RUNNING', 'claim': e.claim}]})
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections'].setdefault(e.batches.BATCHES, {})[e.batch['id']] = e.batch
    with ACTIVE_LOCK:
        ACTIVE.add(e.claim)
    e.binding = {'contract': CONTRACT, 'batch_id': e.batch['id'], 'item_index': 0,
        **{k: context[k] for k in ('actor', 'scope_key', 'incarnation')},
        'snapshot_digest': e.batch['snapshot_digest'], 'request_id': e.command['request_id']}
    e.create_body = {'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}
    e.harness = '/__u16_binding_' + uuid4().hex
    router = APIRouter()

    @router.post(e.harness + '/{mode}')
    def call(mode: str, request: Request, body: dict,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def operation(actor, scope, guard):
            if mode == 'preview':
                return e.production.preview(e.nid, scope, actor, MediaCommand.model_validate(body), guard, batch_binding=e.binding)[0]
            if mode == 'create':
                return e.production.create(e.nid, scope, actor, MediaCreate.model_validate(body), guard, batch_binding=e.binding)
            jid = body['jid']
            if mode == 'get':
                return e.production.get(e.nid, scope, actor, 'image', jid, guard, batch_binding=e.binding)
            if mode == 'candidate':
                meta, raw = e.production.candidate(e.nid, scope, actor, 'image', jid, guard, batch_binding=e.binding)
                return {'id': meta['id'], 'bytes': len(raw)}
            if mode == 'review':
                return e.production.review(e.nid, scope, actor, 'image', jid,
                    MediaReview.model_validate({k: v for k, v in body.items() if k != 'jid'}), guard, batch_binding=e.binding)
            return e.production.execute(e.nid, scope, actor, 'image', jid,
                MediaJobAction.model_validate({k: v for k, v in body.items() if k != 'jid'}), guard, batch_binding=e.binding)
        return e.image_batches.invoke(request, e.nid, x_session_token, x_branch_id,
            'domain.review' if mode == 'review' else 'domain.write', operation)

    original_routes = list(e.client.app.router.routes)
    e.client.app.include_router(router)
    try:
        yield e
    finally:
        e.client.app.router.routes[:] = original_routes
        with ACTIVE_LOCK:
            ACTIVE.discard(e.claim)


def stage(e, **values):
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections'][e.batches.BATCHES][e.batch['id']]
        row['items'][0].update(values)


def send(e, mode, body, **kwargs):
    return e.client.post(e.harness + '/' + mode, headers=kwargs.pop('headers', e.headers), json=body, **kwargs)


def queue(e):
    e.create_body['reviewed_preview_digest'] = checked(send(e, 'preview', e.command))['preview_digest']
    job = checked(send(e, 'create', e.create_body))
    stage(e, image_job_id=job['id'])
    return job


def test_bound_original_create_execute_separate_review_and_standalone_bypass_denied(bound):
    e = bound
    job = queue(e)
    path = e.base + '/jobs/image/' + job['id']
    for suffix in ['', '/candidate']:
        assert e.client.get(path + suffix, headers=e.headers).status_code == 404
    assert job['id'] not in [j['id'] for j in checked(e.client.get(e.base + '/jobs', headers=e.headers))['items']]
    for suffix in ['/execute', '/cancel', '/reconcile', '/review']:
        body = action(job)
        if suffix == '/review': body['reviewed_output_digest'] = 'a' * 64
        assert e.client.post(path + suffix, headers=e.headers, json=body).status_code == 404
    done = checked(send(e, 'execute', {'jid': job['id'], **action(job)}))
    assert done['status'] == 'AWAITING_REVIEW', done.get('error_code')
    stage(e, status='COMPLETED', claim=None)
    candidate = checked(send(e, 'candidate', {'jid': job['id']}))
    assert candidate['id'] == done['output_candidate']['id'] and candidate['bytes'] > 0
    approved = checked(send(e, 'review', {'jid': job['id'], **action(done),
        'reviewed_output_digest': done['output_candidate']['digest']}))
    assert approved['status'] == 'APPROVED'
    assert checked(send(e, 'get', {'jid': job['id']}))['id'] == job['id']


@pytest.mark.parametrize('change', ['stopped', 'orphan', 'unconfirmed', 'wrong_job', 'snapshot', 'incarnation', 'actor', 'index'])
def test_batch_binding_and_live_claim_fence_execution(bound, change):
    e = bound
    job = queue(e)
    if change in {'actor', 'index', 'incarnation', 'snapshot'}:
        key, value = {'actor': ('actor', 'other'), 'index': ('item_index', 1),
            'incarnation': ('incarnation', 'file:' + str(uuid4())), 'snapshot': ('snapshot_digest', 'f' * 64)}[change]
        e.binding = {**e.binding, key: value}
    elif change == 'wrong_job': stage(e, image_job_id='other')
    elif change == 'orphan':
        with ACTIVE_LOCK: ACTIVE.discard(e.claim)
    else:
        with e.store.transaction(e.nid, e.scope) as state:
            row = state['collections'][e.batches.BATCHES][e.batch['id']]
            row.update(status='CANCELLED' if change == 'stopped' else 'RUNNING', confirmed=change != 'unconfirmed')
    assert send(e, 'execute', {'jid': job['id'], **action(job)}).status_code in {403, 404, 422}
    assert len(list(e.assets.root.glob('*.bin'))) == 2


def test_bound_create_cannot_be_repeated_after_job_is_bound_and_host_is_required(bound):
    e = bound
    queue(e)
    assert send(e, 'create', e.create_body).status_code == 422
    assert send(e, 'get', {'jid': 'unused'}, headers={}).status_code in {401, 403}
    e.sessions.revoke(e.host)
    assert send(e, 'get', {'jid': 'unused'}).status_code in {401, 403}


def test_public_command_cannot_supply_internal_batch_binding(bound):
    e = bound
    response = e.client.post(e.base + '/preview', headers=e.headers, json={**e.command, 'batch_binding': e.binding})
    assert response.status_code == 422
