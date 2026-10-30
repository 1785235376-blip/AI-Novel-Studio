"""Independent File CAS controls; synthetic source assertions are stubbed."""
import threading

import pytest

from app.experimental.common import change_row
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_u16_capacity_claim import instrumented_batch


def body(batch):
    return {'expected_version': batch['version'], 'snapshot_digest': batch['snapshot_digest'],
            'budget_microusd': 0, 'confirmed': True}


def test_voice_preflight_reauthorizes_before_gate_and_never_snapshots(rig, monkeypatch):
    service, _, ctx = instrumented_batch(rig, monkeypatch, ['VOICE_REDO'], ['PENDING'])
    events = []
    monkeypatch.setattr(service, 'flag_check', lambda name: events.append(name))
    monkeypatch.setattr(service, '_snapshot', lambda *args: pytest.fail('source snapshot reached'))
    before = snapshot(rig.root)
    value = {'items': [{'kind': 'VOICE_REDO', 'voice_job_id': 'synthetic-job',
              'expected_voice_digest': 'a' * 64, 'broker_preview_id': 'synthetic-preview',
              'expected_broker_version': 1}]}
    with pytest.raises(ValueError, match='^AUDIO_CAPACITY_WRITE_UNAVAILABLE$'):
        service.preflight(ctx, value, lambda: events.append('reauthorize'))
    assert events == ['safe_batches_v2', 'reauthorize', 'voice_direction_v2', 'audiobook_v2']
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('bypass_version', [False, True])
def test_confirm_rechecks_voice_kind_under_transaction(rig, monkeypatch, bypass_version):
    # _owned/_assert are intentionally stubbed in instrumented_batch; this
    # proves transaction/CAS ordering only, not real session or source auth.
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['EXPORT'], ['PENDING'],
                                               'PREFLIGHT', confirmed=False)
    seen, done, failures = threading.Event(), threading.Event(), []
    original = service._require_voice_only_confirmation_capacity
    def gate(row):
        original(row)
        if not seen.is_set():
            seen.set()
            assert done.wait(10)
    monkeypatch.setattr(service, '_require_voice_only_confirmation_capacity', gate)
    def contender():
        try:
            assert seen.wait(10)
            with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
                current = doc['collections'][service.BATCHES][batch['id']]
                if bypass_version:
                    # Fault injection, not a claim about legitimate owner code.
                    current['snapshot']['steps'][0]['input']['kind'] = 'VOICE_REDO'
                else:
                    change_row(current, ctx.actor, current['version'],
                               lambda r: r['snapshot']['steps'][0]['input'].update(kind='VOICE_REDO'))
        except BaseException as error:
            failures.append(error)
        finally:
            done.set()
    thread = threading.Thread(target=contender)
    thread.start()
    with pytest.raises(Exception) as denied:
        service.confirm(ctx, batch['id'], body(batch))
    thread.join(10)
    assert not thread.is_alive() and not failures
    if bypass_version:
        assert str(denied.value) == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    else:
        assert type(denied.value).__name__ == 'CapabilityVersionConflict'
    current = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    assert current['status'] == 'PREFLIGHT' and current['confirmed'] is False
    assert not current.get('approvals') and current['items'][0]['attempts'] == 0
