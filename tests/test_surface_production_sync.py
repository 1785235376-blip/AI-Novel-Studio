"""Production-sync contracts over original File/real PostgreSQL outbox/inbox.

No production cloud, synthetic database, external network or cryptography claim.
"""
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.experimental.common import StaleSourceError
from app.experimental.flags import RUNTIME_FLAGS as FLAGS
from app.experimental.offline_sync_production import (
    ProductionSync, SyntheticSyncTransport, SyntheticPlaintextEncryption, build_delta, apply_delta,
)
from app.experimental.planning import digest
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r5_offline_sync import pair, channel, edit, queue, doc, review, apply
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_r5_offline_sync_mounted import sync, create


@pytest.fixture(autouse=True)
def explicit_surface_opt_in(request, monkeypatch):
    # Historical mounted fixtures deliberately enable only their frozen flags.
    if 'mounted' in request.fixturenames: request.getfixturevalue('mounted')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))


def device(e):
    return e.service.production.register_device(e.ctx, {'device_id': 'device-' + uuid4().hex, 'label': 'Synthetic local device'})

def manifest(e, registered, **extra):
    return e.service.production.manifest(e.ctx, {'channel_id': e.channel['id'], 'channel_version': channel(e)['version'],
        'device_id': registered['device_id'], 'request_id': uuid4().hex, **extra})

def transfer(e, manifest, out):
    return e.service.production.prepare_transfer(e.ctx, {'manifest_id': manifest['id'], 'message_ids': [out['id']],
        'request_id': uuid4().hex, 'acknowledge_copy_boundary': True})

def action(e, row, action='dispatch', **extra):
    return e.service.production.action(e.ctx, row['id'], {'expected_version': row['version'], 'action': action}, **extra)

def route(a, b, *, transport=None, guard=lambda: None):
    transport = transport or SyntheticSyncTransport()
    def receive(envelope):
        return b.service.receive(b.ctx, b.channel['id'], {'expected_version': channel(b)['version'],
            'envelope': envelope, 'target_chapter_id': b.cid}, guard)
    transport.bind(channel(b)['endpoint_id'], receive, guard)
    a.service.production.transport = transport
    return transport


def test_production_manifest_exact_delta_metadata_original_review_and_receipt_checkpoint(pair):
    a, b = pair; registered = device(a); baseline = manifest(a, registered)
    edit(a, 'Offline revised rich content'); out = queue(a)
    changed = manifest(a, registered, base_manifest_id=baseline['id'])
    assert changed['manifest_version'] == 2 and changed['objects'][0]['version'] == a.chapters.get(a.cid)['version']
    assert changed['change_set'][0]['delta']['kind'] == 'BLOCK_SPLICE'
    original = a.service.production._row(a.ctx, ProductionSync.MANIFESTS, baseline['id'])
    delta = changed['change_set'][0]['delta']
    rebuilt = apply_delta(original['snapshots'][a.cid], delta)
    assert rebuilt['document'] == doc('Offline revised rich content') and digest(rebuilt) == changed['objects'][0]['digest']
    job = transfer(a, changed, out); route(a, b)
    done = action(a, job)
    assert done['status'] == 'COMPLETED' and done['checkpoint']['completed_ids'] == [out['id']]
    assert done['checkpoint']['receipts'][out['id']]['status'] == 'RECEIVED'
    assert b.chapters.get(b.cid)['document'] == doc()  # Delivery is never manuscript replication.
    inbox = b.service.records(b.ctx)['inbox'][0]
    assert inbox['status'] == 'PENDING_REVIEW'
    apply(b, inbox, review(b, inbox))
    assert b.chapters.get(b.cid)['document'] == doc('Offline revised rich content')
    fresh_store = ExperimentalStore(a.store.root, a.store.backend, a.store.database_url)
    saved = fresh_store.read(a.nid, a.ctx.scope)['collections'][ProductionSync.TRANSFERS][job['id']]
    assert saved['checkpoint'] == done['checkpoint']


def test_production_disconnect_restart_resume_reuses_original_outbox_and_no_duplicate_inbox(pair):
    a, b = pair; registered = device(a); edit(a, 'Interrupted saved content'); out = queue(a); snap = manifest(a, registered); job = transfer(a, snap, out)
    transport = route(a, b); original_send = transport.send; calls = []
    def lost(*args):
        result = original_send(*args); calls.append(result); raise ConnectionError('lost after delivery')
    transport.send = lost
    with pytest.raises(ConnectionError): action(a, job)
    paused = a.service.production.records(a.ctx)['transfers'][0]
    assert paused['status'] == 'PAUSED' and paused['checkpoint']['completed_ids'] == []
    assert len(b.service.records(b.ctx)['inbox']) == 1
    a.service._production = ProductionSync(a.service)
    resumed_transport = route(a, b)
    done = action(a, paused, 'resume')
    assert done['status'] == 'COMPLETED' and len(b.service.records(b.ctx)['inbox']) == 1
    assert b.chapters.get(b.cid)['document'] == doc()
    assert len(calls) == 1 and not done['error_code']


def test_production_durable_ack_recovered_without_reexport(pair, monkeypatch):
    a, b = pair; registered = device(a); out = queue(a); snap = manifest(a, registered); job = transfer(a, snap, out)
    route(a, b)
    original = a.service.production._bounded
    def interrupted(state):
        if any(r.get('checkpoint', {}).get('completed_ids') for r in state['collections'].get(ProductionSync.TRANSFERS, {}).values()):
            raise RuntimeError('checkpoint persistence failed')
        return original(state)
    monkeypatch.setattr(a.service.production, '_bounded', interrupted)
    with pytest.raises(RuntimeError, match='checkpoint persistence'): action(a, job)
    assert a.service._owned(a.ctx, a.service.OUTBOX, out['id'])['status'] == 'ACKNOWLEDGED'
    paused = a.service.production.records(a.ctx)['transfers'][0]
    monkeypatch.setattr(a.service.production, '_bounded', original)
    monkeypatch.setattr(a.service.production.transport, 'send', lambda *args: pytest.fail('ACK must not redeliver'))
    assert action(a, paused, 'resume')['status'] == 'COMPLETED'


def test_production_cancel_device_revocation_scope_and_stale_manifest(pair):
    a, b = pair; registered = device(a); out = queue(a); snap = manifest(a, registered); job = transfer(a, snap, out)
    cancelled = action(a, job, 'cancel')
    assert cancelled['status'] == 'CANCELLED'
    with pytest.raises(ValueError, match='TERMINAL'): action(a, cancelled, 'resume')
    job = transfer(a, snap, out)
    revoked = a.service.production.revoke_device(a.ctx, registered['id'], {'expected_version': registered['version']})
    assert revoked['status'] == 'REVOKED'
    revoked_job = next(r for r in a.service.production.records(a.ctx)['transfers'] if r['id'] == job['id'])
    assert revoked_job['status'] == 'REVOKED'
    with pytest.raises(ValueError, match='REVOKED'): manifest(a, registered)
    with pytest.raises(FileNotFoundError):
        a.service.production.revoke_device(replace(a.ctx, actor='other'), registered['id'], {'expected_version': revoked['version']})
    with pytest.raises(FileNotFoundError): b.service.production._row(b.ctx, ProductionSync.MANIFESTS, snap['id'])
    new_device = device(a); current = manifest(a, new_device); edit(a, 'Version changed')
    with pytest.raises(StaleSourceError, match='SOURCE_CHANGED'): transfer(a, current, out)
    assert not b.service.records(b.ctx)['inbox']


def test_production_revoke_during_transport_stops_future_work_and_retains_copy_boundary(pair):
    a, b = pair; registered = device(a); out = queue(a); snap = manifest(a, registered); job = transfer(a, snap, out)
    transport = route(a, b); send = transport.send
    def revoking(*args):
        receipt = send(*args)
        a.service.production.revoke_device(a.ctx, registered['id'], {'expected_version': registered['version']})
        return receipt
    transport.send = revoking
    with pytest.raises(ValueError, match='NOT_RUNNING'): action(a, job)
    assert a.service.production.records(a.ctx)['transfers'][0]['status'] == 'REVOKED'
    assert len(b.service.records(b.ctx)['inbox']) == 1 and b.chapters.get(b.cid)['document'] == doc()


def test_production_unconfigured_transport_encryption_and_permission_no_dispatch(pair):
    a, b = pair; registered = device(a); out = queue(a); snap = manifest(a, registered); job = transfer(a, snap, out)
    contract = a.service.production.contract(a.ctx)
    assert contract['state'] == 'PARTIAL' and contract['cloud'] == contract['transport'] == contract['encryption'] == 'NOT_CONFIGURED'
    assert not contract['network_enabled'] and not contract['automatic_apply']
    with pytest.raises(ValueError, match='TRANSPORT_NOT_CONFIGURED'): action(a, job)
    route(a, b)
    def denied(): raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): action(a, job, check=denied)
    assert not b.service.records(b.ctx)['inbox']


def test_delta_tamper_tombstone_and_synthetic_encryption_associated_data_revocation(pair):
    a, b = pair
    base = {'title': 'Shared', 'document': doc()}; target = {'title': 'Shared', 'document': doc('Changed')}
    delta = build_delta(base, target); assert apply_delta(base, delta) == target
    bad = deepcopy(delta); bad['blocks'][0]['content'][0]['text'] = 'Tampered'
    with pytest.raises(ValueError, match='TARGET_MISMATCH'): apply_delta(base, bad)
    with pytest.raises(StaleSourceError): apply_delta(target, delta)
    assert apply_delta(base, build_delta(base, None)) is None
    assert apply_delta(None, build_delta(None, target)) == target
    cipher = SyntheticPlaintextEncryption(); payload = b'synthetic-content'; aad = b'scope-device-peer-sequence'
    sealed = cipher.seal(payload, associated_data=aad, key_reference='public-test-key')
    assert not cipher.production_verified and cipher.open(sealed, associated_data=aad, key_reference='public-test-key') == payload
    with pytest.raises(ValueError, match='ASSOCIATED_DATA'): cipher.open(sealed, associated_data=b'other-scope', key_reference='public-test-key')
    cipher.revoke('public-test-key')
    with pytest.raises(ValueError, match='REVOKED'): cipher.open(sealed, associated_data=aad, key_reference='public-test-key')


def test_production_mounted_original_host_session_flags_strict_input_and_states(sync, monkeypatch):
    e = sync; base = e.sbase + '/production'; contract = checked(e.client.get(base))
    assert contract['cloud'] == 'NOT_CONFIGURED' and contract['state'] == 'PARTIAL'
    registered = checked(e.client.post(base + '/devices', json={'device_id': 'synthetic-device', 'label': 'Local laptop'}), 201)
    ch = create(e)
    snap = checked(e.client.post(base + '/manifests', json={'channel_id': ch['id'], 'channel_version': ch['version'],
        'device_id': registered['device_id'], 'request_id': uuid4().hex}), 201)
    assert snap['objects'][0]['object_id'] == e.chapter['id'] and snap['objects'][0]['version'] == e.chapter['version']
    assert checked(e.client.get(base + '/manifests/' + snap['id'])) == snap
    assert e.client.get(base + '/records').headers['cache-control'] == 'no-store'
    assert e.client.post(base + '/devices', json={'device_id': 'another', 'label': 'Laptop', 'cloud_url': 'https://invalid.example'}).status_code == 422
    assert e.client.post(base + '/devices', content='x' * 540000).status_code == 413
    e.client.headers.pop('X-Session-Token')
    assert e.client.get(base).status_code == 401
    e.client.headers['X-Session-Token'] = 'sync-host'
    for flags, v1 in [('', 'false'), ('production_sync_v1', 'false'), ('*', 'false')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags)
        assert e.client.get(base).status_code == 404
        assert e.client.post(base + '/devices', json={}).status_code == 404


def test_production_manifest_integrity_version_and_worker_lease_prevent_ambiguous_resume(pair):
    a, b = pair; registered = device(a); out = queue(a); snap = manifest(a, registered); job = transfer(a, snap, out)
    route(a, b)
    with pytest.raises(CapabilityVersionConflict):
        a.service.production.action(a.ctx, job['id'], {'expected_version': 99, 'action': 'dispatch'})
    with a.store.transaction(a.nid, a.ctx.scope) as state:
        stored = state['collections'][ProductionSync.TRANSFERS][job['id']]
        stored.update(status='RUNNING', worker_token='synthetic-old-process', lease_until=a.service.production.clock() + 30)
    with pytest.raises(ValueError, match='LEASE_ACTIVE'): action(a, job, 'resume')
    with a.store.transaction(a.nid, a.ctx.scope) as state:
        state['collections'][ProductionSync.TRANSFERS][job['id']]['lease_until'] = 0
    assert action(a, job, 'resume')['status'] == 'COMPLETED'
    with a.store.transaction(a.nid, a.ctx.scope) as state:
        state['collections'][ProductionSync.MANIFESTS][snap['id']]['objects'][0]['digest'] = '0' * 64
    with pytest.raises(ValueError, match='INTEGRITY_MISMATCH'): transfer(a, snap, out)


def test_production_receiver_authority_revoked_prevents_delivery(pair):
    a, b = pair; registered = device(a); out = queue(a); snap = manifest(a, registered); job = transfer(a, snap, out)
    allowed = [True]
    def guard():
        if not allowed[0]: raise HTTPException(403, 'receiver no longer authorized')
    route(a, b, guard=guard); allowed[0] = False
    with pytest.raises(HTTPException): action(a, job)
    assert not b.service.records(b.ctx)['inbox']
    assert a.service.production.records(a.ctx)['transfers'][0]['status'] == 'PAUSED'


def test_production_lists_do_not_replay_manuscript_deltas_and_detail_marks_stale(pair):
    a, b = pair; registered = device(a); edit(a, 'Private historical change'); sealed = manifest(a, registered)
    assert sealed['change_set'] and sealed['source_state'] == 'CURRENT'
    assert 'change_set' not in a.service.production.records(a.ctx)['manifests'][0]
    edit(a, 'New current source')
    inspected = a.service.production.manifest_detail(a.ctx, sealed['id'])
    assert inspected['source_state'] == 'STALE' and inspected['change_set'] == sealed['change_set']


def test_surface_contract_request_schemas_match_strict_models(pair):
    import json
    from pathlib import Path
    from app.experimental.writer_room_realtime import JoinIn, ParticipantActionIn, CursorIn, EditIn, OperationIn
    from app.experimental.offline_sync_production import DeviceIn, ManifestIn, TransferIn, TransferActionIn, VersionIn
    import jsonschema
    schemas = json.loads(Path('contracts/functional-surfaces/realtime-sync-models.v1.json').read_text())['models']
    for model in [JoinIn, ParticipantActionIn, CursorIn, EditIn, OperationIn, DeviceIn, ManifestIn, TransferIn, TransferActionIn, VersionIn]:
        expected = model.model_json_schema(); saved = deepcopy(schemas[model.__name__]); saved.pop('$id')
        assert saved == expected
        jsonschema.Draft202012Validator.check_schema(schemas[model.__name__])


def test_production_new_surface_rejects_branch_fallback_and_v1_override(sync, monkeypatch):
    e = scoped(sync, monkeypatch); base = e.sbase + '/production'
    rejected = e.client.get(base, headers=e.headers)
    assert rejected.status_code == 422 and 'BRANCH_WRITER_UNAVAILABLE' in rejected.text
    assert 'city gate opened' not in rejected.text
    assert e.client.post(base + '/devices', headers=e.headers, json={'device_id': 'device', 'label': 'Device'}).status_code == 422
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    disabled = e.client.get(base, headers=e.headers)
    assert disabled.status_code == 501 and disabled.json()['detail']['code'] == 'COLLABORATION_ROUTE_NOT_ENABLED'


def test_delta_preserves_empty_root_shape_rich_marks_and_unicode_exactly(pair):
    base = {'title': 'Empty', 'document': {'type': 'doc', 'content': []}}
    target = {'title': 'Empty renamed', 'document': {'type': 'doc'}}
    assert apply_delta(base, build_delta(base, target)) == target
    rich = {'title': 'Unicode', 'document': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [
        {'type': 'text', 'text': '星✨🪐', 'marks': [{'type': 'bold'}]}]}]}}
    assert apply_delta(target, build_delta(target, rich)) == rich
    assert apply_delta(rich, build_delta(rich, base)) == base
