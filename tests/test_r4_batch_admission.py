"""Original U16 admission/receipt/template closure; File + real PG parameters.

No real provider is called. Registered adapter tests use explicit synthetic data
through original media decoding and the original broker reservation ledger.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from app.experimental.common import StaleSourceError
from app.experimental.model_broker import ModelBrokerService
from app.experimental.safe_batches import SafeBatchesService
from app.experimental.template_library import TemplateLibraryService, parse_package
from app.experimental.flags import enabled_flags
from app.experimental.media import MockImageWorkflowAdapter
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from test_r4_portable_batches import work, rig, confirm, version, FLAGS


@pytest.fixture
def admitted(work, monkeypatch):
    r = work
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS + ',model_broker_v2,model_benchmark_v2,template_library_v2,source_provenance')
    # Tests use the real broker; authority switches use the injected check so
    # media tests are independent of unrelated Model Center dependency setup.
    r.broker = ModelBrokerService(r.store, r.novels, r.chapters, runtime=Runtime(StableIdentityStore(r.root / 'identities.json')), media_registry=r.media.registry)
    r.templates = TemplateLibraryService(r.store, r.novels, r.chapters, enabled_features=lambda: {'safe_batches_v2'})
    r.batches = SafeBatchesService(r.store, r.novels, r.chapters, sources=r.sources, reader=r.reader, media=r.media, broker=r.broker, templates=r.templates, flag_check=lambda _: None)
    return r


def media_item(r, adapter_id='mock-image-v1'):
    brief = r.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Synthetic admitted brief', 'chapter_ids': [r.chapter['id']]})
    route = next(x for x in r.broker.candidates() if x.get('adapter_id') == adapter_id)
    if not route['synthetic']:
        stamp = datetime.now(timezone.utc)
        r.broker.configure_price(r.nid, r.scope, r.actor, {'route_id': route['route_id'], 'route_fingerprint': route['fingerprint'], 'reserve_microusd': 0, 'source': 'Synthetic no-fee contract test estimate', 'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0})
    preview = r.broker.preview(r.nid, r.scope, r.actor, {'capability': 'IMAGE', 'chapter_ids': [r.chapter['id']], 'policy': 'CUSTOM', 'preferred_route': route['route_id'], 'allow_synthetic': True, 'profile': 'LOCAL_ONLY', 'max_cost_microusd': 0})
    assert preview['chosen']
    return {'kind': 'REGISTERED_MEDIA', 'brief_id': brief['id'], 'expected_brief_version': brief['version'], 'adapter_id': adapter_id, 'broker_preview_id': preview['id'], 'expected_broker_version': preview['version']}


def run(r, item):
    row = r.batches.preflight(r.ctx, {'items': [item]})
    assert not r.store.read(r.nid, r.scope)['collections'].get(r.broker.LEDGER)
    row = r.batches.confirm(r.ctx, row['id'], confirm(row))
    return r.batches.dispatch(r.ctx, row['id'], version(row))


def test_registered_synthetic_uses_original_ledger_and_satisfied_asset_not_regenerated(admitted):
    r = admitted; item = media_item(r); done = run(r, item)
    receipt = done['items'][0]['receipts'][0]
    assert done['status'] == 'COMPLETED' and receipt['cost_state'] == 'KNOWN_SYNTHETIC_ZERO'
    assert receipt['approval_version'] == 1 and len(done['approvals']) == 1
    ledger = r.broker.ledger(r.nid, r.scope, r.actor)[0]
    assert ledger['status'] == 'SETTLED' and ledger['actual_microusd'] == 0 and ledger['authorization_digest'] == done['snapshot_digest']
    proposal = done['items'][0]['proposals'][0]
    accepted = r.batches.approve_media(r.ctx, done['id'], {**confirm(done), 'proposal_id': proposal['id'], 'proposal_version': proposal['version']})
    again = r.batches.preflight(r.ctx, {'items': [item]})
    assert again['items'][0]['status'] == 'SKIPPED'
    assert again['items'][0]['satisfied_asset_ids'] == [accepted['items'][0]['proposals'][0]['asset_id']]
    assert len(r.broker.ledger(r.nid, r.scope, r.actor)) == 1
    assert r.batches.confirm(r.ctx, again['id'], confirm(again))['status'] == 'COMPLETED'


def test_real_registered_contract_zero_estimate_still_retains_unknown_invoice(admitted):
    r = admitted
    class RegisteredSyntheticContract(MockImageWorkflowAdapter):
        """Same fixed PNG, intentionally not trusted built-in known-zero type."""
    adapter = RegisteredSyntheticContract()
    adapter.definition = adapter.definition.model_copy(update={'adapter_id': 'synthetic-registered-contract'})
    r.media.registry.register(adapter)
    item = media_item(r, adapter.definition.adapter_id)
    done = run(r, item)
    assert done['status'] == 'UNKNOWN' and done['items'][0]['proposals']
    receipt = done['items'][0]['receipts'][0]
    assert receipt['cost_state'] == 'UNKNOWN_UPSTREAM'
    with pytest.raises(ValueError, match='ONLY_FAILED'): r.batches.retry_failed(r.ctx, done['id'], version(done))
    with pytest.raises(ValueError, match='NO_TERMINAL'): r.batches.reconcile(r.ctx, done['id'], version(done))
    ledger = r.broker.ledger(r.nid, r.scope, r.actor)[0]
    r.broker.reconcile(r.nid, r.scope, r.actor, ledger['id'], {'expected_version': ledger['version'], 'actual_microusd': 0, 'upstream_terminal_confirmed': True, 'evidence_note': 'Synthetic fixture has no upstream billing'})
    recovered = r.batches.reconcile(r.ctx, done['id'], version(done))
    assert recovered['status'] == 'COMPLETED' and recovered['items'][0]['proposals'] == done['items'][0]['proposals']
    assert recovered['items'][0]['receipts'][0]['reconciliation'] == 'ORIGINAL_EXECUTOR_RECEIPT'


def test_failed_retry_retains_attempt_and_original_approval(admitted, monkeypatch):
    r = admitted; item = {'kind': 'PROOF', 'chapter_ids': [r.chapter['id']]}
    row = r.batches.preflight(r.ctx, {'items': [item]}); row = r.batches.confirm(r.ctx, row['id'], confirm(row))
    original = r.reader.proof
    monkeypatch.setattr(r.reader, 'proof', lambda *_: (_ for _ in ()).throw(ValueError('Synthetic rule failure')))
    with pytest.raises(ValueError): r.batches.dispatch(r.ctx, row['id'], version(row))
    failed = r.batches.list_batches(r.ctx)['items'][0]
    retried = r.batches.retry_failed(r.ctx, failed['id'], version(failed))
    assert retried['items'][0]['receipts'][0]['status'] == 'FAILED'
    assert retried['approvals'] == failed['approvals']
    retried = r.batches.confirm(r.ctx, retried['id'], confirm(retried)); monkeypatch.setattr(r.reader, 'proof', original)
    done = r.batches.dispatch(r.ctx, retried['id'], version(retried))
    assert len(done['approvals']) == 2
    assert [x['status'] for x in done['items'][0]['receipts']] == ['FAILED', 'COMPLETED']
    assert done['items'][0]['receipts'][0]['approval_version'] != done['items'][0]['receipts'][1]['approval_version']


def test_b01_preset_snapshot_changes_cannot_reuse_batch_approval(admitted):
    r = admitted
    entry = next(e for e in r.templates.catalog(r.ctx)['items'] if e['package']['manifest']['type'] == 'safe_batch')
    instance = r.templates.copy(r.ctx, {'package_id': entry['id'], 'package_digest': entry['digest'], 'request_id': 'synthetic-batch-copy'})
    body = {'items': [{'kind': 'PROOF', 'chapter_ids': [r.chapter['id']]}, {'kind': 'EXPORT', 'chapter_ids': [r.chapter['id']], 'format': 'txt'}], 'preset_id': instance['id'], 'expected_preset_version': instance['version']}
    row = r.batches.preflight(r.ctx, body)
    assert row['preset']['id'] == instance['id']
    r.templates.edit(r.ctx, instance['id'], {'expected_version': instance['version'], 'content': {'proof': True, 'export_format': 'docx', 'skip_satisfied': True}})
    from app.services.v1_capability_service import CapabilityVersionConflict
    with pytest.raises(CapabilityVersionConflict) as error: r.batches.confirm(r.ctx, row['id'], confirm(row))
    assert 'version' in str(error.value).lower() or 'VERSION' in str(error.value)
    package = deepcopy(entry['package']); package['content']['budget_microusd'] = 99
    with pytest.raises(ValueError): parse_package(package)


def test_broker_route_source_actor_and_price_fences(admitted):
    r = admitted; item = media_item(r)
    row = r.batches.preflight(r.ctx, {'items': [item]})
    with r.store.transaction(r.nid, r.scope) as state:
        state['collections'][r.broker.DECISIONS][item['broker_preview_id']]['created_by'] = 'another-actor'
    with pytest.raises(FileNotFoundError): r.batches.confirm(r.ctx, row['id'], confirm(row))
    assert not r.broker.ledger(r.nid, r.scope, r.actor)


@pytest.fixture
def voice_admitted(admitted, monkeypatch):
    import httpx
    from app.audio_production_store import AudioProductionStore
    from app.audio_providers import HttpAudioProvider
    from app.services.audiobook_service import AudiobookService
    from app.experimental.voice_direction import DirectedAudiobookService
    from app.experimental.safe_batch_voice import BatchVoiceAuthority
    from test_r5_voice_subtitles import edit
    from test_r3_media_support import wav_bytes
    r = admitted
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS + ',audiobook_v2,voice_direction_v2')
    r.voice = DirectedAudiobookService(r.store, r.novels, r.chapters, assets=r.assets)
    profile = r.voice.create_profile(r.nid, r.scope, r.actor, {'display_name': 'Synthetic TTS', 'provider_id': 'dasheng-local', 'model_id': 'dasheng-audiogen', 'voice_id': 'fixture', 'license_note': 'Synthetic fixture'})
    for cid in ['alice', '__narrator__']: r.voice.map_voice(r.nid, r.scope, r.actor, {'character_id': cid, 'profile_id': profile['id']})
    plan = r.voice.create_plan(r.nid, r.scope, r.actor, {'chapter_id': r.chapter['id']})
    for segment in plan['segments']: plan = r.voice.edit_direction(r.nid, r.scope, r.actor, plan['id'], segment['id'], edit(plan, segment, profile, speech_rate=1))
    plan = r.voice.as_actor(r.actor, r.voice.review, r.nid, r.scope, r.actor, plan['id'], 'approve', plan['version'])
    r.audio_calls = []; r.audio_endpoint = 'http://127.0.0.1:8001/v1'
    class Transport:
        def post(self, url, **kwargs):
            r.audio_calls.append((url, kwargs))
            return httpx.Response(200, content=wav_bytes(500), headers={'content-type': 'audio/wav'}, request=httpx.Request('POST', url))
    transport = Transport()
    def resolver(pid):
        if pid != 'dasheng-local': raise ValueError('not configured')
        return pid, 'dasheng-audiogen', HttpAudioProvider(transport, r.audio_endpoint, local=True)
    def factory(scope, actor): return AudiobookService(AudioProductionStore(r.root / 'audio').for_branch(scope.get('branch_id')).for_actor(actor), r.assets, scope.get('branch_id'))
    r.audio_factory = factory; r.audio_resolver = resolver
    r.broker.audio_resolver = resolver
    r.batches.voice = BatchVoiceAuthority(r.voice, factory, resolver)
    job = r.voice.as_actor(r.actor, r.voice.queue_selected, r.nid, r.scope, r.actor, plan['id'], {'expected_version': plan['version'], 'segment_ids': [plan['segments'][0]['id']], 'approve_selected': True}, factory(r.scope, r.actor), lambda: None, 'synthetic-selected-voice')['items'][0]
    r.voice_job = job
    return r


def voice_item(r, price=True):
    route = next(x for x in r.broker.candidates() if x.get('audio_provider_id') == 'dasheng-local')
    if price:
        stamp = datetime.now(timezone.utc)
        r.broker.configure_price(r.nid, r.scope, r.actor, {'route_id': route['route_id'], 'route_fingerprint': route['fingerprint'], 'reserve_microusd': 0, 'source': 'Synthetic transport explicit fee estimate', 'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0})
    preview = r.broker.preview(r.nid, r.scope, r.actor, {'capability': 'AUDIO', 'chapter_ids': [r.chapter['id']], 'policy': 'CUSTOM', 'preferred_route': route['route_id'], 'profile': 'LOCAL_ONLY', 'max_cost_microusd': 0})
    return {'kind': 'VOICE_REDO', 'voice_job_id': r.voice_job['id'], 'expected_voice_digest': r.voice_job['request_sha256'], 'broker_preview_id': preview['id'], 'expected_broker_version': preview['version']}, preview


def test_audio_original_broker_price_not_locality_required(voice_admitted):
    r = voice_admitted; item, preview = voice_item(r, price=False)
    assert preview['chosen'] is None and not r.audio_calls
    with pytest.raises(ValueError, match='LEGAL_PREVIEW'): r.batches.preflight(r.ctx, {'items': [item]})
    assert not r.broker.ledger(r.nid, r.scope, r.actor)


def test_audio_original_executor_original_review_and_unknown_cost_receipt(voice_admitted):
    from app.experimental.safe_batch_voice import voice_context
    r = voice_admitted; item, _ = voice_item(r); row = run(r, item)
    assert row['status'] == 'UNKNOWN' and len(r.audio_calls) == 1
    assert row['items'][0]['voice_result']['duration_ms'] == 500
    assert not r.assets.list(r.nid)  # candidate stays private until explicit review
    assert not r.audio_factory(r.scope, r.actor).store.load(r.nid)['jobs']  # no generic bypass
    with pytest.raises(ValueError): r.audio_factory(r.scope, r.actor).transition(r.nid, r.voice_job['id'], 'QUEUED')
    ledger = r.broker.ledger(r.nid, r.scope, r.actor)[0]
    r.broker.reconcile(r.nid, r.scope, r.actor, ledger['id'], {'expected_version': ledger['version'], 'actual_microusd': 0, 'upstream_terminal_confirmed': True, 'evidence_note': 'Synthetic transport, verified no external bill'})
    row = r.batches.reconcile(r.ctx, row['id'], version(row))
    raw, mime = r.batches.preview_voice(r.ctx, row['id'], 0); assert raw.startswith(b'RIFF') and mime == 'audio/wav'
    row = r.batches.approve_voice(r.ctx, row['id'], {**confirm(row), 'item_index': 0, 'expected_asset_version': row['items'][0]['voice_result']['asset_version']})
    assert row['items'][0]['voice_result']['approval_status'] == 'APPROVED' and len(r.assets.list(r.nid)) == 1
    assert len(r.audio_calls) == 1
    with voice_context(r.ctx, row['id']):
        assert r.audio_factory(r.scope, r.actor).store.load(r.nid)['jobs'][0]['approval_status'] == 'APPROVED'


def test_audio_config_drift_and_source_revocation_before_send(voice_admitted):
    r = voice_admitted; item, _ = voice_item(r)
    row = r.batches.preflight(r.ctx, {'items': [item]}); row = r.batches.confirm(r.ctx, row['id'], confirm(row))
    r.audio_endpoint = 'http://127.0.0.1:8003/v1'
    with pytest.raises(StaleSourceError): r.batches.dispatch(r.ctx, row['id'], version(row))
    assert r.audio_calls == [] and not r.broker.ledger(r.nid, r.scope, r.actor)


def test_registered_media_interruption_adopts_original_success_without_regeneration(admitted, monkeypatch):
    r = admitted; item = media_item(r)
    row = r.batches.preflight(r.ctx, {'items': [item]}); row = r.batches.confirm(r.ctx, row['id'], confirm(row))
    original = r.batches._media_result
    monkeypatch.setattr(r.batches, '_media_result', lambda *_: (_ for _ in ()).throw(ValueError('synthetic interruption after original success')))
    with pytest.raises(ValueError): r.batches.dispatch(r.ctx, row['id'], version(row))
    state = r.store.read(r.nid, r.scope)['collections']; failed = state[r.batches.BATCHES][row['id']]
    assert failed['status'] == 'UNKNOWN' and state[r.media.TASKS][failed['items'][0]['task_id']]['status'] == 'SUCCEEDED'
    monkeypatch.setattr(r.batches, '_media_result', original)
    recovered = r.batches.reconcile(r.ctx, row['id'], {'expected_version': failed['version']})
    assert recovered['status'] == 'COMPLETED' and recovered['items'][0]['attempts'] == 1
    assert len(r.store.read(r.nid, r.scope)['collections'][r.media.TASKS]) == 1


def test_unknown_reconciled_positive_cost_never_extends_zero_budget(admitted):
    r = admitted
    class Contract(MockImageWorkflowAdapter): pass
    adapter = Contract(); adapter.definition = adapter.definition.model_copy(update={'adapter_id': 'positive-invoice-fixture'})
    r.media.registry.register(adapter); item = media_item(r, adapter.definition.adapter_id); row = run(r, item)
    ledger = r.broker.ledger(r.nid, r.scope, r.actor)[0]
    r.broker.reconcile(r.nid, r.scope, r.actor, ledger['id'], {'expected_version': ledger['version'], 'actual_microusd': 1, 'upstream_terminal_confirmed': True, 'evidence_note': 'Synthetic overrun marker'})
    with pytest.raises(ValueError, match='OVERRUN'): r.batches.reconcile(r.ctx, row['id'], version(row))
    with pytest.raises(ValueError): r.batches.dispatch(r.ctx, row['id'], version(row))
    stopped = r.batches.stop(r.ctx, row['id'], version(row))
    assert stopped['status'] == 'CANCELLED' and stopped['items'][0]['receipts'][0]['reservation_id'] == ledger['id']


def test_voice_private_dependency_and_budget_cost_are_not_bypassed(voice_admitted, monkeypatch):
    r = voice_admitted; item, _ = voice_item(r)
    # A hidden dependency cannot leak its task or frozen source via catalog.
    original = r.chapters.get(r.chapter['id'])
    monkeypatch.setattr(r.sources, 'chapter_reader', lambda _: [{**original, 'hidden': True}])
    assert r.batches.catalog(r.ctx)['voice_jobs'] == []
    with pytest.raises(FileNotFoundError): r.batches.preflight(r.ctx, {'items': [item]})
    assert not r.audio_calls


def test_stop_during_original_audio_send_discards_result_and_preserves_hold(voice_admitted):
    r = voice_admitted; item, _ = voice_item(r)
    row = r.batches.preflight(r.ctx, {'items': [item]}); row = r.batches.confirm(r.ctx, row['id'], confirm(row))
    original = r.audio_resolver
    fired = []
    def resolver(pid):
        resolved_id, model, provider = original(pid)
        transport = provider.transport
        class StopTransport:
            def post(self, *args, **kwargs):
                result = transport.post(*args, **kwargs)
                current = r.store.read(r.nid, r.scope)['collections'][r.batches.BATCHES][row['id']]
                r.batches.stop(r.ctx, row['id'], {'expected_version': current['version']}); fired.append(True)
                return result
        provider.transport = StopTransport()
        return resolved_id, model, provider
    r.broker.audio_resolver = resolver; r.batches.voice.resolver = resolver
    with pytest.raises(ValueError): r.batches.dispatch(r.ctx, row['id'], version(row))
    current = r.batches.list_batches(r.ctx)['items'][0]
    assert fired and current['status'] == 'CANCELLED'
    assert r.assets.list(r.nid, actor_id=r.actor) == []
    assert r.broker.ledger(r.nid, r.scope, r.actor)[0]['status'] == 'UNKNOWN_UPSTREAM'


def test_changed_visible_voice_source_retains_sanitized_original_receipts(voice_admitted):
    r = voice_admitted; item, _ = voice_item(r); row = run(r, item)
    chapter = r.chapters.get(r.chapter['id'])
    r.chapters.save(chapter['id'], {'version': chapter['version'], 'content': 'Synthetic revised chapter after execution.'})
    visible = r.batches.list_batches(r.ctx)['items'][0]
    assert visible['stale'] and visible['approvals'] == row['approvals']
    assert visible['retained_receipts'][0]['receipts'][0]['reservation_id'] == row['items'][0]['receipts'][0]['reservation_id']
    assert 'voice_result' not in str(visible) and 'source_text' not in str(visible)
    assert r.broker.ledger(r.nid, r.scope, r.actor)[0]['status'] == 'UNKNOWN_UPSTREAM'


def test_voice_restart_reopens_original_receipts_and_never_repeats_send(voice_admitted):
    from app.experimental.safe_batch_voice import BatchVoiceAuthority
    r = voice_admitted; item, _ = voice_item(r); row = run(r, item)
    broker = ModelBrokerService(r.store, r.novels, r.chapters, runtime=Runtime(StableIdentityStore(r.root / 'identities.json')), media_registry=r.media.registry, audio_resolver=r.audio_resolver)
    restarted = SafeBatchesService(r.store, r.novels, r.chapters, sources=r.sources, reader=r.reader, media=r.media, broker=broker, voice=BatchVoiceAuthority(r.voice, r.audio_factory, r.audio_resolver), flag_check=lambda _: None)
    reopened = restarted.list_batches(r.ctx)['items'][0]
    assert reopened['status'] == 'UNKNOWN' and not reopened['stale']
    ledger = broker.ledger(r.nid, r.scope, r.actor)[0]
    broker.reconcile(r.nid, r.scope, r.actor, ledger['id'], {'expected_version': ledger['version'], 'actual_microusd': 0, 'upstream_terminal_confirmed': True, 'evidence_note': 'Original synthetic terminal receipt after restart'})
    recovered = restarted.reconcile(r.ctx, row['id'], version(reopened))
    assert recovered['status'] == 'COMPLETED' and len(r.audio_calls) == 1


def test_duplicate_domain_target_cannot_hide_behind_unrelated_parameters(admitted):
    r = admitted; item = media_item(r)
    with pytest.raises(ValueError, match='DUPLICATE_ITEM'):
        r.batches.preflight(r.ctx, {'items': [item, {**item, 'format': 'docx'}]})
    assert not r.broker.ledger(r.nid, r.scope, r.actor)


def test_original_unsent_orphan_confirmation_permits_failed_only_retry(voice_admitted, monkeypatch):
    r = voice_admitted; item, _ = voice_item(r)
    row = r.batches.preflight(r.ctx, {'items': [item]}); row = r.batches.confirm(r.ctx, row['id'], confirm(row))
    original = r.batches.voice.dispatch
    class SyntheticCrash(BaseException): pass
    monkeypatch.setattr(r.batches.voice, 'dispatch', lambda *args: (_ for _ in ()).throw(SyntheticCrash()))
    with pytest.raises(SyntheticCrash): r.batches.dispatch(r.ctx, row['id'], version(row))
    reopened = r.batches.list_batches(r.ctx)['items'][0]; assert reopened['status'] == 'UNKNOWN' and r.audio_calls == []
    ledger = r.broker.ledger(r.nid, r.scope, r.actor)[0]; assert ledger['status'] == 'RESERVED' and not ledger['dispatched']
    with pytest.raises(ValueError, match='NO_TERMINAL'): r.batches.reconcile(r.ctx, row['id'], version(reopened))
    r.broker.reconcile(r.nid, r.scope, r.actor, ledger['id'], {'expected_version': ledger['version'], 'actual_microusd': 0, 'upstream_terminal_confirmed': True, 'original_executor_stopped_confirmed': True, 'evidence_note': 'Synthetic process terminated before original send'}, allow_orphan=True)
    failed = r.batches.reconcile(r.ctx, row['id'], version(reopened)); assert failed['status'] == 'PARTIAL' and failed['items'][0]['status'] == 'FAILED'
    retried = r.batches.retry_failed(r.ctx, row['id'], version(failed)); assert retried['status'] == 'PREFLIGHT'
    retried = r.batches.confirm(r.ctx, row['id'], confirm(retried)); monkeypatch.setattr(r.batches.voice, 'dispatch', original)
    done = r.batches.dispatch(r.ctx, row['id'], version(retried))
    assert len(r.audio_calls) == 1 and len(done['items'][0]['receipts']) == 2
    assert done['items'][0]['receipts'][0]['reservation_id'] == ledger['id']


def test_stopped_batch_keeps_satisfied_completed_stages_reusable(admitted):
    r = admitted; items = [{'kind': 'PROOF', 'chapter_ids': [r.chapter['id']]}, {'kind': 'EXPORT', 'chapter_ids': [r.chapter['id']]}]
    row = r.batches.preflight(r.ctx, {'items': items}); row = r.batches.confirm(r.ctx, row['id'], confirm(row))
    row = r.batches.dispatch(r.ctx, row['id'], version(row)); r.batches.stop(r.ctx, row['id'], version(row))
    again = r.batches.preflight(r.ctx, {'items': items})
    assert [item['status'] for item in again['items']] == ['SKIPPED', 'PENDING']
