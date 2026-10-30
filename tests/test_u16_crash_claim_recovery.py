"""U16 claim/order/crash evidence for the closed capacity write gates.

These tests only prove synthetic ordering and recovery semantics on the File
store; they are not a broker, authorization or real-model proof. They cover the
ledger's open question: a batch must refuse at the closed capacity gate before
any RUNNING claim/attempt/reservation, and an interrupted RUNNING claim from a
dead process must surface UNKNOWN without replay, remaining recoverable only by
the original executor/stop path.
"""
from __future__ import annotations

import pytest

from app.experimental.common import change_row
from test_u16_capacity_claim import instrumented_batch, rig
from test_audio_history_status_readonly import snapshot

pytestmark = pytest.mark.file_backend_only


def _interrupted(rig, monkeypatch):
    # PROOF keeps the public projection small; the synthetic row carries only
    # what _public reads, it is not a broker/authorization proof.
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['PROOF'], ['RUNNING'], 'RUNNING')

    def prepare(row):
        row['snapshot']['budget'] = {}
        row['snapshot']['preset'] = None
        step = row['snapshot']['steps'][0]
        step['sources'] = {}
        step['source_versions'] = {}
        step['configuration'] = {'version': 1}
        step['resource_requirements'] = []
        step['permission'] = 'domain.write'
        step['input'].update(start=None, end=None)
        row['items'][0].update(claim='dead-process-claim', attempts=1)

    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        current = doc['collections'][service.BATCHES][batch['id']]
        change_row(current, ctx.actor, current['version'], prepare)
    return service, batch, ctx


def test_interrupted_running_claim_surfaces_unknown_without_replay(rig, monkeypatch):
    service, batch, ctx = _interrupted(rig, monkeypatch)
    current = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    # instrumented_batch stubs _public for concise stubs; call the real
    # projection explicitly to verify the interrupted-claim mapping.
    from app.experimental.safe_batches import SafeBatchesService
    public = SafeBatchesService._public(service, current)
    assert public['status'] == 'UNKNOWN'
    assert public['items'][0]['status'] == 'UNKNOWN'
    assert public['items'][0]['error_code'] == 'BATCH_INTERRUPTED_RECONCILIATION_REQUIRED_NO_REPLAY'
    assert public['items'][0]['attempts'] == 1
    assert 'UNKNOWN_RESULT_MUST_RECONCILE_IN_ORIGINAL_EXECUTOR' in public['limitations']


def test_interrupted_claim_stop_cancels_without_executor_replay(rig, monkeypatch):
    service, batch, ctx = _interrupted(rig, monkeypatch)
    current = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    stopped = service.stop(ctx, batch['id'], {'expected_version': current['version']})
    assert stopped['status'] == 'CANCELLED'
    assert stopped['items'][0]['status'] == 'CANCELLED'
    stored = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    assert stored['items'][0]['claim'] is None and stored['items'][0]['attempts'] == 1


def test_closed_gate_refuses_before_running_claim_or_attempt(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'])
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='^AUDIO_CAPACITY_WRITE_UNAVAILABLE$'):
        service.dispatch(ctx, batch['id'], {'expected_version': batch['version']})
    stored = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    item = stored['items'][0]
    assert item['status'] == 'PENDING' and item['attempts'] == 0
    assert item.get('claim') is None and item['receipts'] == []
    assert 'task_id' not in item and 'reservation_id' not in item
    assert snapshot(rig.root) == before


def test_confirm_gate_refusal_leaves_no_claim_or_attempt(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'],
                                                'PREFLIGHT', confirmed=False)
    body = {'expected_version': batch['version'], 'snapshot_digest': batch['snapshot_digest'],
            'budget_microusd': 0, 'confirmed': True}
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='^AUDIO_CAPACITY_WRITE_UNAVAILABLE$'):
        service.confirm(ctx, batch['id'], body)
    stored = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    assert stored['status'] == 'PREFLIGHT' and stored['confirmed'] is False
    assert stored['items'][0]['status'] == 'PENDING' and stored['items'][0]['attempts'] == 0
    assert stored['items'][0].get('claim') is None
    assert snapshot(rig.root) == before


