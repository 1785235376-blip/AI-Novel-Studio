"""Synthetic ordering counterexample, not full broker/authorization proof."""
from types import SimpleNamespace
from copy import deepcopy
import threading
import pytest

from app.experimental.common import new_row, change_row
from app.experimental.safe_batches import SafeBatchesService
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig


def test_voice_stage_must_refuse_before_any_batch_claim(rig, monkeypatch):
    class StopBroker:
        LEDGER = 'synthetic_ledger'
        def reserve(self, *args, **kwargs):
            raise ValueError('SYNTHETIC_BROKER_INTERCEPTION')
    media = SimpleNamespace(TASKS='synthetic_tasks')
    service = SafeBatchesService(rig.workspace.store.store, rig.novels, rig.workspace.creative.chapters,
                                sources=None, reader=None, media=media, broker=StopBroker())
    item = {'kind': 'VOICE_REDO', 'voice_job_id': 'synthetic-job', 'expected_voice_digest': 'a' * 64,
            'broker_preview_id': 'synthetic-preview', 'expected_broker_version': 1}
    batch = new_row(rig.nid, rig.scope, 'synthetic-actor', {'status': 'READY', 'confirmed': True,
        'snapshot_digest': 'b' * 64, 'snapshot': {'steps': [{'input': item}]},
        'items': [{'index': 0, 'status': 'PENDING', 'attempts': 0, 'receipts': []}]})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    # Isolate dispatch order after a hypothetical already successful authority
    # and input check; this is not proof those checks were actually satisfied.
    monkeypatch.setattr(service, '_owned', lambda ctx, rid: service.get(ctx.novel_id, ctx.scope, service.BATCHES, rid))
    monkeypatch.setattr(service, '_assert', lambda ctx, row, check: check())
    ctx = SimpleNamespace(novel_id=rig.nid, scope=rig.scope, actor='synthetic-actor')
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.dispatch(ctx, batch['id'], {'expected_version': batch['version']})
    assert snapshot(rig.root) == before


def instrumented_batch(rig, monkeypatch, kinds, states, batch_status='READY', actor='synthetic-actor', confirmed=True):
    """File owner with stubbed source/authority checks; not an auth proof."""
    class NoBroker:
        LEDGER = 'synthetic_ledger'
        def reserve(self, *args, **kwargs): pytest.fail('broker reservation reached')
    class NoVoice:
        def retry(self, *args, **kwargs): pytest.fail('voice retry reached')
        def approve(self, *args, **kwargs): pytest.fail('voice approval reached')
    media = SimpleNamespace(TASKS='synthetic_tasks')
    service = SafeBatchesService(rig.workspace.store.store, rig.novels, rig.workspace.creative.chapters,
        sources=None, reader=None, media=media, broker=NoBroker(), voice=NoVoice())
    steps = [{'input': {'kind': kind, 'voice_job_id': 'synthetic-job',
                        'expected_voice_digest': 'a' * 64, 'broker_preview_id': 'synthetic-preview',
                        'expected_broker_version': 1}} for kind in kinds]
    items = [{'index': i, 'status': status, 'attempts': 0, 'receipts': [], 'claim': None}
             for i, status in enumerate(states)]
    batch = new_row(rig.nid, rig.scope, actor, {'status': batch_status, 'confirmed': confirmed,
        'snapshot_digest': 'b' * 64, 'snapshot': {'steps': steps}, 'items': items})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    monkeypatch.setattr(service, '_owned', lambda ctx, rid: service.get(ctx.novel_id, ctx.scope, service.BATCHES, rid))
    monkeypatch.setattr(service, '_assert', lambda ctx, row, check: check())
    monkeypatch.setattr(service, '_public', lambda row: deepcopy(row))
    return service, batch, SimpleNamespace(novel_id=rig.nid, scope=rig.scope, actor=actor)


def test_mixed_image_then_voice_does_not_create_voice_claim(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'], ['PENDING', 'PENDING'])
    calls = []
    service.studio_image = SimpleNamespace(dispatch=lambda *args: calls.append('image') or {'synthetic': True})
    result = service.dispatch(ctx, batch['id'], {'expected_version': batch['version']})
    assert calls == ['image'] and result['items'][0]['status'] == 'COMPLETED'
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.dispatch(ctx, batch['id'], {'expected_version': result['version']})
    assert snapshot(rig.root) == before
    after = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    assert after['items'][1]['status'] == 'PENDING' and after['items'][1]['attempts'] == 0
    assert calls == ['image']


def test_voice_retry_refuses_before_original_voice_transition(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['FAILED'], 'PARTIAL')
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.retry_failed(ctx, batch['id'], {'expected_version': batch['version']})
    assert snapshot(rig.root) == before


def test_voice_approval_refuses_before_original_promotion(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['COMPLETED'], 'COMPLETED')
    before = snapshot(rig.root)
    body = {'expected_version': batch['version'], 'snapshot_digest': batch['snapshot_digest'],
            'budget_microusd': 0, 'confirmed': True, 'item_index': 0, 'expected_asset_version': 1}
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.approve_voice(ctx, batch['id'], body)
    assert snapshot(rig.root) == before


def test_concurrent_stage_change_rejected_by_original_version_cas(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE'], ['PENDING'])
    observed, committed = threading.Event(), threading.Event()
    errors = []
    original_gate = service._require_stage_write_capacity
    def stage_check(row, index):
        original_gate(row, index)
        if not observed.is_set():
            observed.set()
            assert committed.wait(10), 'contending writer did not commit'
    monkeypatch.setattr(service, '_require_stage_write_capacity', stage_check)
    def contender():
        try:
            assert observed.wait(10)
            with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
                current = doc['collections'][service.BATCHES][batch['id']]
                change_row(current, ctx.actor, current['version'],
                    lambda r: r['snapshot']['steps'][0]['input'].update(kind='VOICE_REDO'))
        except BaseException as exc:
            errors.append(exc)
        finally:
            committed.set()
    thread = threading.Thread(target=contender)
    thread.start()
    with pytest.raises(Exception) as exc:
        service.dispatch(ctx, batch['id'], {'expected_version': batch['version']})
    thread.join(10)
    assert not thread.is_alive() and not errors
    assert type(exc.value).__name__ == 'CapabilityVersionConflict'
    current = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    assert current['version'] == batch['version'] + 1
    assert current['items'][0]['status'] == 'PENDING' and current['items'][0]['attempts'] == 0


def test_transaction_rechecks_voice_even_if_corrupt_writer_keeps_version(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE'], ['PENDING'])
    observed, committed = threading.Event(), threading.Event()
    errors = []
    original_gate = service._require_stage_write_capacity
    def stage_check(row, index):
        original_gate(row, index)
        if not observed.is_set():
            observed.set()
            assert committed.wait(10)
    monkeypatch.setattr(service, '_require_stage_write_capacity', stage_check)
    def corrupt_contender():
        try:
            assert observed.wait(10)
            with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
                # Deliberately bypass change_row/version; this is a fault
                # injection, not a claim that a legitimate writer does so.
                doc['collections'][service.BATCHES][batch['id']]['snapshot']['steps'][0]['input']['kind'] = 'VOICE_REDO'
        except BaseException as exc:
            errors.append(exc)
        finally:
            committed.set()
    thread = threading.Thread(target=corrupt_contender)
    thread.start()
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.dispatch(ctx, batch['id'], {'expected_version': batch['version']})
    thread.join(10)
    assert not thread.is_alive() and not errors
    current = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    assert current['items'][0]['status'] == 'PENDING' and current['items'][0]['attempts'] == 0


def test_membership_revoked_before_gate_denies_with_real_authorizer(rig, monkeypatch):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.experimental import api as experimental_api
    from app.identity import IdentityStatus
    from fastapi import HTTPException
    from test_studio_asset_query import shared_scope
    scope, _ = shared_scope(rig)
    rig.scope = scope
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('u16-write', 'reader', 'domain.write',
        ModalityDomain.NOVEL, grant_scope, 'synthetic'))
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'], actor='reader')
    original_owned = service._owned
    def revoke_after_row(ctx, rid):
        row = original_owned(ctx, rid)
        thread = threading.Thread(target=lambda: rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.INACTIVE))
        thread.start(); thread.join(10)
        assert not thread.is_alive()
        return row
    monkeypatch.setattr(service, '_owned', revoke_after_row)
    def real_authorize():
        actor, scope = experimental_api.authorize(rig.nid, 'token-reader', 'query-branch-a', 'domain.write')
        assert (actor, scope) == ('reader', rig.scope)
    real_authorize()
    before = rig.workspace.store.store._file_bytes(rig.nid, rig.scope)
    with pytest.raises(HTTPException) as exc:
        service.dispatch(ctx, batch['id'], {'expected_version': batch['version']}, real_authorize)
    assert exc.value.status_code in (401, 403)
    assert rig.workspace.store.store._file_bytes(rig.nid, rig.scope) == before


def test_recreated_project_old_voice_batch_cannot_claim(rig, monkeypatch):
    previous_identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'])
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    assert rig.workspace.store.incarnation(rig.nid) != previous_identity
    before = rig.workspace.store.store._file_bytes(rig.nid, rig.scope)
    # The source/row assertions are stubbed: this establishes only that the
    # old VOICE_REDO cannot acquire a claim, not U16 incarnation binding.
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.dispatch(ctx, batch['id'], {'expected_version': batch['version']})
    assert rig.workspace.store.store._file_bytes(rig.nid, rig.scope) == before


@pytest.mark.parametrize('alias', [False, True])
def test_voice_preflight_http_requires_original_host_session_and_stays_read_only(rig, monkeypatch, alias):
    from app.actor_context import SessionContext
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', rig.workspace.store.store)
    body = {'items': [{'kind': 'VOICE_REDO', 'voice_job_id': 'synthetic-job', 'expected_voice_digest': 'a' * 64,
                      'broker_preview_id': 'synthetic-preview', 'expected_broker_version': 1}]}
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/preflight'
    before = snapshot(rig.root)
    denied = rig.client.post(path, json=body)
    assert denied.status_code == 401, denied.text
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2')
    disabled = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'}, json=body)
    assert disabled.status_code == 404, disabled.text
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'}, json=body)
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_voice_dispatch_http_uses_original_auth_before_closed_claim(rig, monkeypatch, alias):
    from app.actor_context import SessionContext
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'], actor='local-author')
    mounted = experimental_api.safe_batches_service
    # Keep mounted HTTP authentication and File storage; isolate the source
    # assertion because no provider, broker approval or model is involved.
    monkeypatch.setattr(mounted, 'store', service.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, 'broker', service.broker)
    monkeypatch.setattr(mounted, 'media', service.media)
    monkeypatch.setattr(mounted, 'voice', service.voice)
    monkeypatch.setattr(mounted, '_owned', service._owned)
    monkeypatch.setattr(mounted, '_assert', service._assert)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/dispatch-next'
    before = snapshot(rig.root)
    denied = rig.client.post(path, json={'expected_version': batch['version']})
    assert denied.status_code == 401, denied.text
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'},
                               json={'expected_version': batch['version']})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before


def test_original_nonvoice_export_preflight_still_persists(rig, monkeypatch):
    created = rig.workspace.creative.chapters.create(rig.nid, {'title': 'Synthetic', 'content': 'Synthetic prose.'})
    chapter = rig.workspace.creative.chapters.get(created['id'])
    service = SafeBatchesService(rig.workspace.store.store, rig.novels, rig.workspace.creative.chapters,
        sources=None, reader=None, media=SimpleNamespace(TASKS='synthetic_tasks'), flag_check=lambda _: None)
    # Source projection is isolated; real preflight and File batch persistence
    # execute, but this does not establish external/branch authorization.
    monkeypatch.setattr(service, '_rows', lambda ctx: [deepcopy(chapter)])
    ctx = SimpleNamespace(novel_id=rig.nid, scope=rig.scope, actor='synthetic-actor')
    result = service.preflight(ctx, {'items': [{'kind': 'EXPORT', 'chapter_ids': [chapter['id']],
                                               'format': 'txt'}], 'skip_satisfied': False})
    assert result['status'] == 'PREFLIGHT' and result['items'][0]['kind'] == 'EXPORT'
    saved = service.get(rig.nid, rig.scope, service.BATCHES, result['id'])
    assert saved['snapshot']['steps'][0]['input']['kind'] == 'EXPORT'


def test_voice_only_confirmation_refuses_before_file_update(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'],
                                               'PREFLIGHT', confirmed=False)
    before = snapshot(rig.root)
    body = {'expected_version': batch['version'], 'snapshot_digest': batch['snapshot_digest'],
            'budget_microusd': 0, 'confirmed': True}
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.confirm(ctx, batch['id'], body)
    assert snapshot(rig.root) == before


def test_mixed_batch_confirmation_preserves_original_image_path(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'], 'PREFLIGHT', confirmed=False)
    body = {'expected_version': batch['version'], 'snapshot_digest': batch['snapshot_digest'],
            'budget_microusd': 0, 'confirmed': True}
    result = service.confirm(ctx, batch['id'], body)
    assert result['status'] == 'READY' and result['confirmed'] is True
    assert result['items'][0]['status'] == 'PENDING' and result['items'][1]['status'] == 'PENDING'


@pytest.mark.parametrize('alias', [False, True])
def test_voice_only_confirmation_http_reauth_and_no_file_update(rig, monkeypatch, alias):
    from app.actor_context import SessionContext
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'],
                                               'PREFLIGHT', actor='local-author', confirmed=False)
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', service.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, '_owned', service._owned)
    monkeypatch.setattr(mounted, '_assert', service._assert)
    monkeypatch.setattr(mounted, '_public', lambda row: deepcopy(row))
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/confirm'
    body = {'expected_version': batch['version'], 'snapshot_digest': batch['snapshot_digest'],
            'budget_microusd': 0, 'confirmed': True}
    before = snapshot(rig.root)
    denied = rig.client.post(path, json=body)
    assert denied.status_code == 401, denied.text
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'}, json=body)
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before
