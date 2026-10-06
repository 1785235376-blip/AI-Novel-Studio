"""Wave 4 real persisted domain journeys. Synthetic assets, no model quality claim."""
import base64
import io
import json
import wave
from fractions import Fraction

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.audiobook import AudiobookV2Service, DialogueAttribution
from app.experimental.common import StaleSourceError
from app.experimental.director import CameraGrammar, DirectorService, camera_checks
from app.experimental.media import MediaService
from app.experimental.media_api import create_media_router
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, branch_scope
from test_r4_director import screenplay, plan_body
from test_r4_change_impact import impact, edit, preflight, prepare
from test_r4_registered_local_media import local_media, price


def media(rig, store=None):
    return MediaService(store or rig.store, rig.novels, rig.chapters, rig.assets, rig.screenplays, production_capture_enabled=lambda: True)


def generated(rig, service, brief):
    task = service.queue(rig.nid, rig.scope, rig.actor, {'brief_id': brief['id'], 'expected_brief_version': brief['version'], 'adapter_id': 'mock-image-v1'})
    return service.execute(rig.nid, rig.scope, rig.actor, task['id'], task['version'])


def test_director_additive_grammar_and_transparent_review_checks():
    grammar = CameraGrammar(shot_function='OTS', focus_intent='RACK_FOCUS')
    assert grammar.model_dump()['focus_intent'] == 'RACK_FOCUS'
    one = {'id': 'one', 'scene_id': 'scene', 'shot_size': 'MEDIUM', 'camera_angle': 'EYE_LEVEL', 'camera_motion': 'STATIC', 'duration_seconds': 2,
           'director': {'screen_direction': 'LEFT_TO_RIGHT'}}
    two = {**one, 'id': 'two', 'duration_seconds': 8, 'director': {'screen_direction': 'RIGHT_TO_LEFT'}}
    findings = camera_checks([one, two])
    assert {r['kind'] for r in findings} >= {'AXIS', 'SCREEN_DIRECTION', 'REPEATED_FRAMING', 'SHOT_RHYTHM', 'CONTINUITY'}
    assert next(r for r in findings if r['kind'] == 'AXIS')['state'] == 'INSUFFICIENT_EVIDENCE'
    rhythm = next(r for r in findings if r['kind'] == 'SHOT_RHYTHM')
    assert rhythm['state'] == 'REVIEW_SUGGESTION' and rhythm['evidence']['review_threshold_ratio'] == 3
    two['scene_id'] = 'another'
    assert not any(r['kind'] in {'REPEATED_FRAMING', 'SHOT_RHYTHM', 'CONTINUITY'} for r in camera_checks([one, two]))


def test_director_new_fields_survive_original_apply_history_and_restart(rig):
    service = DirectorService(rig.store, rig.novels, rig.chapters, rig.screenplays)
    original = screenplay(rig)
    plan = service.create_plan(rig.nid, rig.scope, rig.actor, plan_body(original, shot_function='ESTABLISHING', focus_intent='RACK_FOCUS'))
    comparison = service.compare(rig.nid, rig.scope, rig.actor, [plan['id']])
    service.apply(rig.nid, rig.scope, rig.actor, plan['id'], plan['version'], comparison['application_digests'][plan['id']])
    restored = DirectorService(ExperimentalStore(rig.root, rig.backend, rig.store.database_url), rig.novels, rig.chapters, rig.screenplays)
    actual = restored.catalog(rig.nid, rig.scope, rig.actor)['screenplays'][0]
    assert actual['shots'][0]['director']['focus_intent'] == 'RACK_FOCUS'
    assert actual['shot_status'] == 'DRAFT' and actual['edit_version'] == original['edit_version'] + 1
    assert rig.screenplays.history(rig.nid, original['id'])['items']


def test_catalog_reuses_original_ids_and_hides_stale_or_other_branch_sources(rig):
    service = media(rig); original = screenplay(rig)
    catalog = service.catalog(rig.nid, rig.scope)
    assert catalog['screenplays'][0]['id'] == original['id']
    assert catalog['screenplays'][0]['shots'][0]['id'] == original['shots'][0]['id']
    assert catalog['characters'] == [{'id': 'alice', 'name': 'Alice'}]
    assert 'Careful' not in json.dumps(catalog) and not catalog['automatic_generation']
    assert service.catalog(rig.nid, branch_scope(rig))['screenplays'] == []
    rig.chapters.save(rig.chapter['id'], {'version': rig.chapter['version'], 'content': 'Current manuscript revision'})
    assert service.catalog(rig.nid, rig.scope)['screenplays'] == []


def test_storyboard_revision_history_restart_and_old_result_fence(rig):
    service = media(rig); original = screenplay(rig)
    body = {'screenplay_id': original['id'], 'shot_id': original['shots'][0]['id'], 'expected_screenplay_version': original['edit_version'], 'prompt': 'Original brief'}
    brief = service.create_storyboard(rig.nid, rig.scope, rig.actor, body)
    first = generated(rig, service, brief)
    revised = service.update_storyboard(rig.nid, rig.scope, rig.actor, brief['id'], 1, {**body, 'prompt': 'Revised intention'})
    assert revised['id'] == brief['id'] and revised['version'] == 2 and revised['history'][0]['prompt'] == 'Original brief'
    with pytest.raises(CapabilityVersionConflict):
        service.update_storyboard(rig.nid, rig.scope, rig.actor, brief['id'], 1, body)
    with pytest.raises(ValueError, match='IDENTITY_IMMUTABLE'):
        service.update_storyboard(rig.nid, rig.scope, rig.actor, brief['id'], 2, {**body, 'shot_id': 'not-the-original'})
    with pytest.raises(StaleSourceError):
        service.review(rig.nid, rig.scope, rig.actor, first['proposal_ids'][0], 'approve', 1)
    assert rig.assets.list(rig.nid) == []
    second = generated(rig, service, revised)
    comparison = service.compare(rig.nid, rig.scope, [first['proposal_ids'][0], second['proposal_ids'][0]])
    assert not comparison['same_source_version'] and [r['stale'] for r in comparison['items']] == [True, False]
    restarted = media(rig, ExperimentalStore(rig.root, rig.backend, rig.store.database_url))
    saved = restarted.briefs(rig.nid, rig.scope, 'STORYBOARD')[0]
    assert saved['version'] == 2 and saved['history'][0]['version'] == 1
    approved = restarted.review(rig.nid, rig.scope, rig.actor, second['proposal_ids'][0], 'approve', 1)
    assert rig.assets.get(approved['asset_id'])['parameters']['experimental_media_lineage']['shot_id'] == body['shot_id']


def test_cover_typography_survives_manifest_lineage_without_raw_prompt_export(rig):
    service = media(rig)
    brief = service.create_cover(rig.nid, rig.scope, rig.actor, {'title': 'Title', 'typography_intent': 'Keep top quarter clear for title', 'prompt': 'private-scene-text'})
    task = generated(rig, service, brief)
    assert task['brief_snapshot']['typography_intent'] == brief['typography_intent']
    approved = service.review(rig.nid, rig.scope, rig.actor, task['proposal_ids'][0], 'approve', 1)
    production = ProductionLineageService(rig.store, rig.novels, rig.chapters, rig.assets, service)
    manifest = production.capture(rig.nid, rig.scope, rig.actor, {'task_id': task['id'], 'expected_task_version': task['version']})
    assert manifest['assurance']['replayable'] == 'NOT_CHECKED'
    assert manifest['assurance']['approximately_reproducible'] == 'NOT_EVALUATED'
    assert manifest['assurance']['deterministically_reproducible'] == 'SYNTHETIC_PROTOCOL_ONLY'
    assert not manifest['assurance']['seed_guarantees_identical_bytes']
    preflight = production.preflight(rig.nid, rig.scope, rig.actor, manifest['id'], 1)
    assert preflight['assurance']['replayable'] == 'CURRENT_PREFLIGHT_PASSED'
    generation = production.asset(rig.nid, rig.scope, approved['asset_id'])['generation']
    assert generation['produced_at'] and generation['adapter_version'] and generation['prompt_digest']
    assert generation['model_quality'] == 'NOT_RUN'
    assert 'private-scene-text' not in json.dumps(production.export(rig.nid, rig.scope, manifest['id']))
    assert 'private-scene-text' not in json.dumps(generation)
    assert ProductionLineageService.assurance({'environment': {'deterministic': False}, 'seed': {'value': 1}})['deterministically_reproducible'] == 'NOT_VERIFIED'


def test_media_new_api_permission_flag_and_version_conflict(rig, monkeypatch):
    from app.experimental.flags import require_flag
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'cover_storyboard_generation')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    service = media(rig); original = screenplay(rig)
    def authorize(nid, token, branch, permission):
        if token != 'owner' or nid != rig.nid: raise HTTPException(403, 'denied')
        return rig.actor, rig.scope if branch is None else branch_scope(rig, branch)
    app = FastAPI(); app.include_router(create_media_router(service, authorize, require_flag), prefix='/api')
    client = TestClient(app); base = f'/api/novels/{rig.nid}/experimental/media'; headers = {'X-Session-Token': 'owner'}
    assert client.get(base + '/catalog').status_code == 403
    assert client.get(base + '/catalog', headers=headers).json()['screenplays'][0]['id'] == original['id']
    body = {'screenplay_id': original['id'], 'shot_id': original['shots'][0]['id'], 'expected_screenplay_version': original['edit_version']}
    brief = client.post(base + '/storyboard-briefs', headers=headers, json=body).json()
    path = base + f'/storyboard-briefs/{brief["id"]}?expected_version=1'
    assert client.put(path, headers=headers, json={**body, 'prompt': 'Revised via API'}).status_code == 200
    assert client.put(path, headers=headers, json=body).status_code == 409
    assert client.get(base + '/catalog', headers={**headers, 'X-Branch-ID': 'other'}).json()['screenplays'] == []
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.get(base + '/catalog', headers=headers).status_code == 404
    assert client.put(path, headers=headers, json=body).status_code == 404


def test_unknown_attribution_cannot_claim_confirmed_without_speaker(rig):
    class Uncertain:
        def attribute(self, *args): return DialogueAttribution(None, 'RULE_CONFIRMED', 'adapter omitted identity')
    service = AudiobookV2Service(rig.store, rig.novels, rig.chapters, rig.assets, attribution=Uncertain())
    plan = service.create_plan(rig.nid, rig.scope, rig.actor, {'chapter_id': rig.chapter['id']})
    assert all(r['attribution_status'] == 'NEEDS_REVIEW' for r in plan['segments'] if r['kind'] == 'DIALOGUE')
    assert service.duration_manifest(rig.nid, rig.scope, plan['id'])['precision'] == 'UNMEASURED'
    with pytest.raises(ValueError, match='ATTRIBUTION_NEEDS_REVIEW'):
        service.review(rig.nid, rig.scope, rig.actor, plan['id'], 'approve', plan['version'])


def test_measured_frame_timeline_does_not_accumulate_rounded_millisecond_drift():
    plan = {'segments': [{'duration_ms': 23, 'frame_timing': {'frames': 1001, 'sample_rate': 44100}} for _ in range(100)]}
    AudiobookV2Service._timeline(plan)
    assert plan['duration_ms'] == float(Fraction(100100 * 1000, 44100))
    assert plan['segments'][-1]['start_ms'] == float(Fraction(99099 * 1000, 44100))
    assert plan['duration_ms'] != 2300 and plan['timing_status'] == 'MEASURED'
    plan['segments'][1]['duration_ms'] = None
    AudiobookV2Service._timeline(plan)
    assert plan['duration_ms'] is None and plan['segments'][2]['start_ms'] is None and plan['timing_status'] == 'PARTIAL'


def test_audio_edit_invalidates_previous_frame_evidence(rig):
    service = AudiobookV2Service(rig.store, rig.novels, rig.chapters, rig.assets)
    plan = service.create_plan(rig.nid, rig.scope, rig.actor, {'chapter_id': rig.chapter['id']})
    segment = plan['segments'][0]
    out = io.BytesIO()
    with wave.open(out, 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(44100); stream.writeframes(b'\0\0' * 1001)
    asset = rig.assets.create(rig.nid, 'measured.wav', base64.b64encode(out.getvalue()).decode(), 'audio/wav', 'audio')
    plan = service.bind_audio(rig.nid, rig.scope, rig.actor, plan['id'], segment['id'], {'expected_version': 1, 'asset_id': asset['id']})
    assert plan['segments'][0]['frame_timing']['frames'] == 1001
    plan = service.update_segment(rig.nid, rig.scope, rig.actor, plan['id'], segment['id'], {'expected_version': plan['version'], 'emotion': 'quiet'})
    assert plan['segments'][0]['frame_timing'] is None and plan['segments'][0]['duration_ms'] is None
    manifest = service.duration_manifest(rig.nid, rig.scope, plan['id'])
    assert manifest['alignment_model'] is None and manifest['word_alignment'] == 'NOT_CONFIGURED'


def test_otio_drops_no_unknown_extension_without_loss_warning():
    otio = pytest.importorskip('opentimelineio', reason='NOT_RUN: pinned official parser required')
    from app.experimental.timeline_exchange import read_otio, NS
    clip = otio.schema.Clip(name='Fixture', source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(0, 24), otio.opentime.RationalTime(48, 24)))
    clip.metadata[NS] = {'linked_audio_group': 'not-supported'}
    timeline = otio.schema.Timeline(tracks=[otio.schema.Track(children=[clip])])
    _, report = read_otio(otio.core.serialize_json_to_string(timeline))
    assert any(r['code'] == 'UNKNOWN_EXCHANGE_METADATA_NOT_REPRESENTED' for r in report)


def test_otio_screenplay_camera_sound_and_dialogue_have_explicit_losses(rig):
    pytest.importorskip('opentimelineio', reason='NOT_RUN: pinned official parser required')
    from app.experimental.timeline_exchange import TimelineExchangeService
    original = screenplay(rig)
    shot = {**original['shots'][0], 'dialogue': [{'speaker': 'Alice', 'text': 'Hello'}]}
    original = rig.screenplays.update_shot(rig.nid, original['id'], shot['id'], {**shot, 'expected_version': original['edit_version']})
    service = TimelineExchangeService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    receipt = service.from_screenplay(rig.nid, rig.scope, rig.actor, {'screenplay_id': original['id'], 'expected_screenplay_version': original['edit_version'], 'shots': [{'shot_id': shot['id']}]})
    assert {'CAMERA_GRAMMAR_NOT_REPRESENTED', 'DIALOGUE_SUBTITLES_NOT_REPRESENTED', 'SOUND_DESIGN_NOT_RENDERED_OR_LINKED'} <= {r['code'] for r in receipt['loss_report']}
    assert receipt['summary']['audio_video_relation'] == 'INDEPENDENT_TRACK_TIMING_ONLY_NO_LINKED_CLIP_CONTRACT'
    with pytest.raises(ValueError, match='REVIEW_LOSS_REPORT_REQUIRED'):
        service.download(rig.nid, rig.scope, rig.actor, receipt['id'], receipt['version'], False)


def test_u06_selective_refresh_preserves_cover_typography_in_original_new_task(rig, impact):
    r, service = rig, impact
    brief = service.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Cover', 'typography_intent': 'Reserve left title column', 'chapter_ids': [r.chapter['id']]})
    task = generated(r, service.media, brief)
    edit(r)
    plan = preflight(r, service, task)
    refreshed = prepare(r, service, plan)
    current = service.media.get(r.nid, r.scope, service.media.TASKS, refreshed['task_id'])
    assert current['brief_snapshot']['typography_intent'] == 'Reserve left title column'
    assert current['sources'] != task['sources'] and current['status'] == 'QUEUED'
    assert service.media.get(r.nid, r.scope, service.media.TASKS, task['id'])['status'] == 'SUCCEEDED'
    assert rig.assets.list(rig.nid) == []


def test_registered_original_adapter_receives_typography_and_does_not_claim_determinism(local_media):
    e = local_media; r = e.r; price(e)
    brief = e.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Cover', 'typography_intent': 'No image detail behind title'})
    task = e.media.queue(r.nid, r.scope, r.actor, {'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': e.route['adapter_id'], 'candidate_count': 1, 'parameters': {'seed': 77}})
    quote = e.media.preflight_registered(r.nid, r.scope, r.actor, task['id'], 1)
    task = e.media.execute_registered(r.nid, r.scope, r.actor, task['id'], 1, quote['broker_decision_id'], quote['broker_decision_version'])
    assert len(e.calls) == 1 and 'No image detail behind title' in e.calls[0]['json']['prompt']
    manifest = e.production.capture(r.nid, r.scope, r.actor, {'task_id': task['id'], 'expected_task_version': task['version']})
    assert manifest['seed']['value'] == 77
    assert manifest['assurance']['deterministically_reproducible'] == 'NOT_VERIFIED'
    assert manifest['assurance']['approximately_reproducible'] == 'NOT_EVALUATED'


def test_otio_summary_exposes_distinct_source_in_out_and_timeline_position():
    from app.experimental.timeline_exchange import summary, time_value
    result = summary({'name': 'Trimmed', 'tracks': [{'name': 'V1', 'kind': 'Video', 'items': [
        {'kind': 'Clip', 'name': 'trim', 'start': time_value(48), 'duration': time_value(72)}]}]})
    cut = result['tracks'][0]['cuts'][0]
    assert cut['start_seconds'] == {'numerator': 0, 'denominator': 1}
    assert cut['source_in_seconds'] == {'numerator': 2, 'denominator': 1}
    assert cut['source_out_seconds'] == {'numerator': 5, 'denominator': 1}
