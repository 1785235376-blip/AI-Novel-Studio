"""Mounted original broker/template/media admission, real File and PG matrix."""
import pytest
from test_r4_portable_batches_mounted import tools, mounted, prefix, checked, scoped
from test_r4_portable_batches import confirm, version


def prepare(e):
    base = e.base + '/safe-batches'
    status = checked(e.client.get(e.base + '/model-broker/status'))
    route = next(r for r in status['candidates'] if r.get('adapter_id') == 'mock-image-v1')
    broker = checked(e.client.post(e.base + '/model-broker/preview', json={'capability': 'IMAGE', 'chapter_ids': [e.chapter['id']], 'policy': 'CUSTOM', 'preferred_route': route['route_id'], 'profile': 'LOCAL_ONLY', 'max_cost_microusd': 0, 'allow_synthetic': True}))
    brief = checked(e.client.post(e.base + '/media/cover-briefs', json={'title': 'SYNTHETIC_BATCH_ADMISSION', 'chapter_ids': [e.chapter['id']]}), 201)
    item = {'kind': 'REGISTERED_MEDIA', 'brief_id': brief['id'], 'expected_brief_version': brief['version'], 'adapter_id': 'mock-image-v1', 'broker_preview_id': broker['id'], 'expected_broker_version': broker['version']}
    return base, item


def test_mounted_original_registered_media_receipt_review_and_skip(tools):
    e = tools; base, item = prepare(e)
    row = checked(e.client.post(base + '/preflight', json={'items': [item]}))
    assert row['status'] == 'PREFLIGHT'
    assert checked(e.client.get(e.base + '/model-broker/history'))['ledger'] == []
    row = checked(e.client.post(base + f"/{row['id']}/confirm", json=confirm(row)))
    row = checked(e.client.post(base + f"/{row['id']}/dispatch-next", json=version(row)))
    assert row['status'] == 'COMPLETED' and len(row['items'][0]['receipts']) == 1
    ledger = checked(e.client.get(e.base + '/model-broker/history'))['ledger'][0]
    assert ledger['status'] == 'SETTLED' and ledger['actual_microusd'] == 0
    proposal = row['items'][0]['proposals'][0]
    row = checked(e.client.post(base + f"/{row['id']}/approve-media", json={**confirm(row), 'proposal_id': proposal['id'], 'proposal_version': proposal['version']}))
    skipped = checked(e.client.post(base + '/preflight', json={'items': [item]}))
    assert skipped['items'][0]['status'] == 'SKIPPED' and skipped['items'][0]['satisfied_asset_ids']
    assert checked(e.client.get(e.base + '/media/tasks'))['items'] == []


def test_mounted_template_original_copy_is_bound_to_preview(tools, monkeypatch):
    e = tools; base = e.base + '/safe-batches'
    # The production object is injected at composition; test asserts that seam,
    # rather than replacing any route or authorization implementation.
    assert e.batches.templates is e.experimental.template_library_service
    entry = next(x for x in checked(e.client.get(e.base + '/template-library'))['items'] if x['package']['manifest']['type'] == 'safe_batch')
    copy = checked(e.client.post(e.base + '/template-library/instances', json={'package_id': entry['id'], 'package_digest': entry['digest'], 'request_id': 'mounted-synthetic-batch'}), 201)
    row = checked(e.client.post(base + '/preflight', json={'items': [{'kind': 'PROOF', 'chapter_ids': [e.chapter['id']]}, {'kind': 'EXPORT', 'chapter_ids': [e.chapter['id']]}], 'preset_id': copy['id'], 'expected_preset_version': copy['version']}))
    checked(e.client.put(e.base + '/template-library/instances/' + copy['id'], json={'expected_version': copy['version'], 'content': {'proof': True, 'export_format': 'docx', 'skip_satisfied': True}}))
    changed = e.client.post(base + f"/{row['id']}/confirm", json=confirm(row))
    assert changed.status_code == 409 and 'current' not in changed.json()['detail']
    assert not e.store.read(e.nid, e.scope)['collections'].get(e.batches.media.TASKS)


def test_mounted_broker_revocation_blocks_before_media_dispatch(tools, monkeypatch):
    from app.experimental.flags import FLAGS
    e = tools; base, item = prepare(e)
    row = checked(e.client.post(base + '/preflight', json={'items': [item]}))
    row = checked(e.client.post(base + f"/{row['id']}/confirm", json=confirm(row)))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(f for f in FLAGS if f != 'model_broker_v2'))
    assert e.client.post(base + f"/{row['id']}/dispatch-next", json=version(row)).status_code == 404
    assert not e.store.read(e.nid, e.scope)['collections'].get(e.batches.media.TASKS)


def test_mounted_audio_original_resolver_executor_invoice_reconciliation_and_review(tools, monkeypatch):
    import httpx
    from datetime import datetime, timedelta, timezone
    from test_r3_media_support import wav_bytes
    e = tools; base = e.base + '/safe-batches'; calls = []
    def synthetic_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, content=wav_bytes(400), headers={'content-type': 'audio/wav'}, request=httpx.Request('POST', url))
    # Only HTTP transport is synthetic. Keep the shipped resolver, adapter,
    # production composition, authorization, cost ledger, decoder and writers.
    monkeypatch.setattr(httpx, 'post', synthetic_post)
    profile = checked(e.client.post(e.base + '/audiobook/profiles', json={'display_name': 'Synthetic route voice', 'provider_id': 'dasheng-local', 'model_id': 'dasheng-audiogen', 'voice_id': 'fixture', 'license_note': 'Synthetic test only'}), 201)
    checked(e.client.post(e.base + '/audiobook/mappings', json={'character_id': '__narrator__', 'profile_id': profile['id']}))
    plan = checked(e.client.post(e.base + '/audiobook/plans', json={'chapter_id': e.chapter['id']}), 201)
    for segment in plan['segments']:
        plan = checked(e.client.put(e.base + f"/voice-direction/plans/{plan['id']}/segments/{segment['id']}", json={'expected_version': plan['version'], 'kind': 'NARRATION', 'profile_id': profile['id'], 'reviewed_text': segment['text'], 'text_reviewed': True, 'attribution_reviewed': True, 'voice_authorized': True}))
    plan = checked(e.client.post(e.base + f"/audiobook/plans/{plan['id']}/approve", json={'expected_version': plan['version']}))
    job = checked(e.client.post(e.base + f"/voice-direction/plans/{plan['id']}/queue", json={'expected_version': plan['version'], 'segment_ids': [plan['segments'][0]['id']], 'approve_selected': True}), 202)['items'][0]
    status = checked(e.client.get(e.base + '/model-broker/status')); route = next(r for r in status['candidates'] if r.get('audio_provider_id') == 'dasheng-local')
    stamp = datetime.now(timezone.utc)
    checked(e.client.put(e.base + '/model-broker/price', json={'route_id': route['route_id'], 'route_fingerprint': route['fingerprint'], 'reserve_microusd': 0, 'source': 'Synthetic transport fee estimate', 'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0}))
    preview = checked(e.client.post(e.base + '/model-broker/preview', json={'capability': 'AUDIO', 'chapter_ids': [e.chapter['id']], 'policy': 'CUSTOM', 'preferred_route': route['route_id'], 'profile': 'LOCAL_ONLY', 'max_cost_microusd': 0}))
    assert preview['chosen'] and calls == []
    row = checked(e.client.post(base + '/preflight', json={'items': [{'kind': 'VOICE_REDO', 'voice_job_id': job['id'], 'expected_voice_digest': job['request_sha256'], 'broker_preview_id': preview['id'], 'expected_broker_version': preview['version']}]}))
    row = checked(e.client.post(base + f"/{row['id']}/confirm", json=confirm(row)))
    row = checked(e.client.post(base + f"/{row['id']}/dispatch-next", json=version(row)))
    assert row['status'] == 'UNKNOWN' and len(calls) == 1 and row['items'][0]['voice_result']['duration_ms'] == 400
    assert checked(e.client.get(e.base + '/voice-direction/jobs'))['items'] == []
    assert e.client.post(e.base + f"/voice-direction/jobs/{job['id']}/retry").status_code == 404
    ledger = checked(e.client.get(e.base + '/model-broker/history'))['ledger'][0]
    checked(e.client.post(e.base + f"/model-broker/ledger/{ledger['id']}/reconcile", json={'expected_version': ledger['version'], 'actual_microusd': 0, 'upstream_terminal_confirmed': True, 'evidence_note': 'Synthetic transport verified without a provider bill'}))
    row = checked(e.client.post(base + f"/{row['id']}/reconcile", json=version(row)))
    audio = e.client.get(base + f"/{row['id']}/items/0/audio"); assert audio.status_code == 200 and audio.content.startswith(b'RIFF')
    row = checked(e.client.post(base + f"/{row['id']}/approve-voice", json={**confirm(row), 'item_index': 0, 'expected_asset_version': row['items'][0]['voice_result']['asset_version']}))
    assert row['items'][0]['voice_result']['approval_status'] == 'APPROVED' and len(calls) == 1
