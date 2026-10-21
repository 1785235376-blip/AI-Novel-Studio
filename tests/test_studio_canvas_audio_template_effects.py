"""Saved original Graph envelopes -> local card overrides -> real AudioJob CPU.

Only owned, short synthetic WAVs. No provider/model, alternate template store,
queue, processor, automatic approval, or reusable execution authorization.
"""
from copy import deepcopy
import base64
import hashlib
import json
import io
import struct
import wave
import os
from pathlib import Path

import pytest

from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution import digest
from app.creative.production_execution_models import CanvasAudioTemplateParameters
from app.experimental.common import StaleSourceError
from app.services.audiobook_service import AudiobookError
from test_creative_canvas_views_additive import reference
from test_studio_canvas_audio_envelope import envelope_canvas, decode, return_body, RATE, AMPLITUDE
from test_studio_canvas_audio_return import change_origin
from test_v2_audio_wav_controls import production, preview, queue, run, get, review
from test_v2_independent_workspace import rig, reopened
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_audio_wav_controls_api import audio_client


EFFECTS = ('gain_db', 'fade_in_ms', 'fade_out_ms')
FIELDS = ('in_ms', 'out_ms', *EFFECTS)
TEMPLATE = {'in_ms': 200, 'out_ms': 1200, 'gain_db': -6,
            'fade_in_ms': 200, 'fade_out_ms': 300}
LOCAL = {'in_ms': 200, 'out_ms': 1200, 'gain_db': -6.020599913279624,
         'fade_in_ms': 100, 'fade_out_ms': 200}
REJECTED = (ValueError, StaleSourceError, FileNotFoundError, AudiobookError)


def definition(e, parameters, *, runnable=False):
    nodes = [
        {'id': 'source', 'definition_id': 'asset_reference', 'parameters': {
            'asset_id': e.source['id'], 'version': e.source['version'],
            'digest': e.source['sha256'], 'kind': 'audio'}},
        {'id': 'trim', 'definition_id': 'media_generate', 'parameters': {
            'operation_id': 'm8.audio.trim', 'parameters': deepcopy(parameters)}}]
    edges = [{'id': 'source_trim', 'source_node_id': 'source', 'source_port': 'asset',
              'target_node_id': 'trim', 'target_port': 'source'}]
    if runnable:
        nodes.append({'id': 'review', 'definition_id': 'media_review', 'parameters': {}})
        edges.append({'id': 'trim_review', 'source_node_id': 'trim', 'source_port': 'candidate',
                      'target_node_id': 'review', 'target_port': 'candidate'})
    return {'schema_version': 3, 'title': 'Owned envelope workflow', 'nodes': nodes, 'edges': edges}


def pin(row):
    node = next(node for node in row['definition']['nodes'] if node['id'] == 'trim')
    parameters = node['parameters']['parameters']
    return {'contract': 'studio-canvas-audio-template/1', 'graph_id': row['id'],
        'graph_version': row['version'], 'definition_digest': row['definition_digest'],
        'execution_digest': row['execution_digest'], 'node_id': node['id'],
        'parameters': {key: parameters[key] for key in FIELDS if parameters.get(key) is not None}}


@pytest.fixture
def effect_template(envelope_canvas):
    e = envelope_canvas
    e.template = e.graph.create(e.nid, e.scope, e.actor, {
        'request_id': 'owned-audio-effects-template', 'definition': definition(e, TEMPLATE)})
    e.command['template_ref'] = pin(e.template)
    e.command['parameters'] = deepcopy(TEMPLATE)
    return e


def save_template(e, **changes):
    value = deepcopy(e.template['definition'])
    value['nodes'][1]['parameters']['parameters'].update(changes)
    return e.graph.save(e.nid, e.scope, e.actor, e.template['id'], {
        'expected_version': e.template['version'], 'definition': value})


def no_jobs(e):
    audio = e.production._audio(e.scope, e.actor)
    assert audio.list(e.nid, e.production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None) == []


def no_native(monkeypatch):
    from app.services import studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process',
                        lambda *a, **k: pytest.fail('this action must not execute FFmpeg'))


def test_legacy_range_dump_and_digest_do_not_acquire_effect_defaults():
    old = {key: None for key in ('width', 'height', 'steps', 'seed', 'cfg', 'negative_prompt',
        'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate')}
    old.update(in_ms=200, out_ms=1200)
    checked = MediaNodeParameters.model_validate({'operation_id': 'm8.audio.trim',
        'parameters': {'in_ms': 200, 'out_ms': 1200}})
    dumped = checked.parameters.model_dump(mode='json')
    assert dumped == old
    assert digest(dumped) == digest(old)
    template = CanvasAudioTemplateParameters.model_validate({'in_ms': 200, 'out_ms': 1200})
    assert template.model_dump(mode='json') == {'in_ms': 200, 'out_ms': 1200}


@pytest.mark.parametrize('effects', [
    {'gain_db': -60}, {'gain_db': 12}, {'gain_db': 0},
    {'fade_in_ms': 0}, {'fade_out_ms': 1000},
    {'gain_db': -6, 'fade_in_ms': 400, 'fade_out_ms': 600}])
def test_graph_and_template_preserve_exact_optional_effect_intent(effects):
    params = {'in_ms': 200, 'out_ms': 1200, **effects}
    node = MediaNodeParameters.model_validate({'operation_id': 'm8.audio.trim', 'parameters': params})
    graph = node.parameters.model_dump(mode='json')
    for field in EFFECTS:
        assert (field in graph) == (field in effects)
        if field in effects:
            assert graph[field] == effects[field]
    assert CanvasAudioTemplateParameters.model_validate(params).model_dump(mode='json') == params


@pytest.mark.parametrize('extra', [
    {'gain_db': None}, {'gain_db': True}, {'gain_db': '-6'},
    {'gain_db': float('nan')}, {'gain_db': float('inf')},
    {'gain_db': -60.01}, {'gain_db': 12.01},
    {'fade_in_ms': None}, {'fade_in_ms': True}, {'fade_in_ms': '10'}, {'fade_in_ms': 0.5},
    {'fade_out_ms': None}, {'fade_out_ms': False}, {'fade_out_ms': float('nan')},
    {'fade_in_ms': -1}, {'fade_out_ms': 120001},
    {'fade_in_ms': 501, 'fade_out_ms': 500},
    {'sample_rate': 48000}, {'channels': 2}, {'output_format': 'FLAC'}, {'normalize': True}])
def test_graph_and_template_reject_invalid_or_unsupported_effects(extra):
    params = {'in_ms': 200, 'out_ms': 1200, **extra}
    with pytest.raises(ValueError):
        MediaNodeParameters.model_validate({'operation_id': 'm8.audio.trim', 'parameters': params})
    with pytest.raises(ValueError):
        CanvasAudioTemplateParameters.model_validate(params)


def test_non_trim_graph_operation_cannot_acquire_envelope_controls():
    with pytest.raises(ValueError):
        MediaNodeParameters.model_validate({'operation_id': 'm8.audio.music',
            'parameters': {'gain_db': -6, 'fade_in_ms': 100}})


def test_saved_template_local_override_frozen_queue_real_cpu_review_return_and_reopen(effect_template, monkeypatch):
    e = effect_template
    before = deepcopy(e.template)
    assert pin(before)['parameters'] == TEMPLATE
    assert e.graph.get(e.nid, e.scope, e.actor, before['id']) == before
    e.command['parameters'] = deepcopy(LOCAL)
    captured = preview(e)
    assert captured['provider'] is None
    assert captured['execution_recipe']['adapter'] == 'LOCAL_FFMPEG'
    assert captured['execution_recipe']['parameters'] == LOCAL
    assert captured['command']['template_ref'] == pin(before)
    queued = queue(e)
    assert queued['status'] == 'QUEUED' and queued['media_measurement'] is None
    assert queued['command']['parameters'] == LOCAL
    assert queue(e) == queued
    assert e.graph.get(e.nid, e.scope, e.actor, before['id']) == before
    changed = save_template(e, gain_db=6, fade_in_ms=10, fade_out_ms=20)
    assert changed['version'] == before['version'] + 1
    assert pin(changed)['parameters'] != pin(before)['parameters']
    rechecked = preview(e)['command']
    rechecked['parameters'] = {k: v for k, v in rechecked['parameters'].items() if v is not None}
    assert rechecked == queued['command']
    assert queue(e) == queued and get(e, queued) == queued
    fresh = deepcopy(e.command)
    fresh['request_id'] = 'new-request-obsolete-effects-pin'
    with pytest.raises(REJECTED):
        preview(e, fresh)
    replacement = deepcopy(e.command)
    replacement['template_ref'] = pin(changed)
    with pytest.raises(REJECTED):
        queue(e, replacement)
    candidate = run(e, queued)
    assert candidate['status'] == 'AWAITING_REVIEW', candidate
    assert candidate['command'] == queued['command']
    assert candidate['execution_recipe']['parameters'] == LOCAL
    channels, pcm, data, measured = decode(e, candidate)
    plateau = AMPLITUDE * 10 ** (LOCAL['gain_db'] / 20)
    errors = []
    for samples in channels:
        errors.append(max(abs(sample - plateau * min(1, (index * 1000 / RATE) / 100)
            * min(1, (1000 - index * 1000 / RATE) / 200)) for index, sample in enumerate(samples)))
    assert max(errors) <= 1.1, errors  # PCM16 quantization, fixed before executing.
    assert channels[0] == channels[1]
    assert e.service.download(e.nid, e.scope, e.source['id'])[1] == e.original_bytes
    with pytest.raises(FileNotFoundError):
        e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas
    no_native(monkeypatch)
    approved = review(e, candidate)
    assert approved['status'] == 'APPROVED' and review(e, approved) == approved
    formal = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    assert formal['version'] == 2
    returned = e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas['id'], return_body(e, formal))
    assert returned['version'] == e.canvas['version'] + 1
    assert returned['definition']['cards'][0] == {**e.canvas['definition']['cards'][0], 'asset': reference(formal)}
    assert returned['definition']['cards'][1:] == e.canvas['definition']['cards'][1:]
    for key in set(e.canvas['definition']) - {'cards'}:
        assert returned['definition'][key] == e.canvas['definition'][key]
    e.production = production(e, reopened(e))
    e.graph.configure_media(e.production)
    assert get(e, approved) == approved
    assert e.graph.get(e.nid, e.scope, e.actor, before['id']) == changed
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == returned
    assert not e.raw_store.read(e.nid, e.scope)['collections'].get(e.graph.RUNS)
    folder = os.environ.get('STUDIO_AUDIO_TEMPLATE_CAPTURE_DIR')
    if folder:
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        evidence = {'contract': 'owned-audio-template-effects-proof/1', 'model_inference': False,
            'graph': before, 'updated_graph': changed, 'template_ref': pin(before), 'command': e.command,
            'preview': captured, 'queued': queued, 'executed': candidate, 'approved': approved,
            'formal': formal, 'canvas_before': e.canvas, 'canvas_after': returned,
            'cpu': {**measured, 'maximum_absolute_lsb_error': errors,
                    'pcm_bytes': len(pcm), 'independent_pcm_sha256': hashlib.sha256(pcm).hexdigest()},
            'source_wav_base64': base64.b64encode(e.original_bytes).decode(),
            'candidate_wav_base64': base64.b64encode(data).decode()}
        (path / 'native-template-effects.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')


@pytest.mark.parametrize('change', ['gain', 'fade-in', 'fade-out', 'missing-effect', 'scope', 'source-pin'])
def test_tampered_template_or_source_binding_is_rejected_before_admission(effect_template, monkeypatch, change):
    e = effect_template
    value = deepcopy(e.command)
    if change == 'gain':
        value['template_ref']['parameters']['gain_db'] = -5
    elif change == 'fade-in':
        value['template_ref']['parameters']['fade_in_ms'] = 199
    elif change == 'fade-out':
        value['template_ref']['parameters']['fade_out_ms'] = 299
    elif change == 'missing-effect':
        value['template_ref']['parameters'].pop('gain_db')
    elif change == 'scope':
        value['canvas_return']['scope'] = {**e.scope, 'branch_id': 'other'}
    else:
        value['source_snapshots'][0]['digest'] = 'f' * 64
    no_native(monkeypatch)
    with pytest.raises(REJECTED):
        preview(e, value)
    no_jobs(e)


@pytest.mark.parametrize('field', EFFECTS)
def test_effect_edit_invalidates_the_exact_reviewed_preview(effect_template, monkeypatch, field):
    e = effect_template
    captured = preview(e)
    changed = deepcopy(e.command)
    changed['parameters'][field] += 1
    no_native(monkeypatch)
    assert preview(e, changed)['preview_digest'] != captured['preview_digest']
    with pytest.raises(REJECTED):
        e.production.create(e.nid, e.scope, e.actor, {
            'command': changed, 'reviewed_preview_digest': captured['preview_digest']}, lambda: None)
    no_jobs(e)


@pytest.mark.parametrize('change', ['source-pin', 'deleted-card', 'version'])
def test_queued_envelope_template_does_not_bypass_source_or_target_pins(effect_template, monkeypatch, change):
    e = effect_template
    queued = queue(e)
    change_origin(e, change)
    no_native(monkeypatch)
    with pytest.raises(REJECTED):
        run(e, queued)
    assert get(e, queued)['output_candidate'] is None


def test_late_cpu_result_becomes_unknown_and_is_never_replayed(effect_template, monkeypatch):
    e = effect_template
    queued = queue(e)
    from app.services import studio_timeline_export as native
    original = native.run_guarded_process
    renders = []
    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        if args and '-af' in args[0]:
            renders.append(list(args[0]))
            change_origin(e, 'version')
        return result
    monkeypatch.setattr(native, 'run_guarded_process', late)
    current = run(e, queued)
    assert len(renders) == 1
    assert current['status'] == 'UNKNOWN' and current['output_candidate'] is None
    no_native(monkeypatch)
    with pytest.raises(REJECTED):
        run(e, current)
    assert get(e, current) == current
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1


def queued_original_graph(e):
    from test_v2_graph_image_nodes import create_run
    graph, row = create_run(e, e.graph, definition(e, TEMPLATE, runnable=True))
    runtime = e.graph.media_runtime
    row = runtime.preview(e.nid, e.scope, e.actor, row['id'], {
        'expected_version': row['version'], 'node_id': 'trim'}, lambda: None)
    captured = row['media_runtime']['nodes'][0]['preview']
    actual_preview = captured['production_preview']
    assert actual_preview['execution_recipe']['adapter'] == 'LOCAL_FFMPEG'
    assert actual_preview['execution_recipe']['parameters'] == TEMPLATE
    for value in (captured['command'], actual_preview['command']):
        assert {k: v for k, v in value['parameters'].items() if v is not None} == TEMPLATE
    row = runtime.dispatch(e.nid, e.scope, e.actor, row['id'], {
        'expected_version': row['version'], 'node_id': 'trim',
        'reviewed_preview_digest': captured['preview_digest']}, lambda: None)
    queued = row['media_runtime']['nodes'][0]['execution']['job']
    assert queued['status'] == 'QUEUED'
    assert queued['request_digest'] == actual_preview['request_digest']
    return graph, row, captured, queued


def test_original_audiojob_graph_guard_keeps_other_controls_standalone(envelope_canvas, monkeypatch):
    e = envelope_canvas
    no_native(monkeypatch)
    _, row, _, queued = queued_original_graph(e)
    stored = e.graph._owned(e.nid, e.scope, e.actor, e.graph.RUNS, row['id'])
    binding = stored['media_executions']['trim']['graph_binding']
    original, context = e.production._row(e.nid, e.scope, e.actor, 'audio', queued['id'],
                                         lambda: None, graph_binding=binding)
    from app.services.studio_audio_execution import _body, _binding
    body = _body(original['_studio_body'])
    assert context['graph_binding'] == binding
    assert _binding(context, body) == context  # This is a real admitted original binding.
    for extra in ({'sample_rate': 44100}, {'channels': 1}, {'output_format': 'FLAC'}):
        changed = deepcopy(body)
        changed['parameters'].update(extra)
        # Each is valid for a standalone original AudioJob. The same actual
        # Graph binding must still reject these capabilities at its own guard.
        with pytest.raises(AudiobookError) as failure:
            _binding(context, _body(changed))
        assert failure.value.code == 'STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'
    assert get_graph_job(e, row, queued)['status'] == 'QUEUED'


def get_graph_job(e, row, receipt):
    stored = e.graph._owned(e.nid, e.scope, e.actor, e.graph.RUNS, row['id'])
    return e.production.get(e.nid, e.scope, e.actor, 'audio', receipt['id'], lambda: None,
                            graph_binding=stored['media_executions']['trim']['graph_binding'])


@pytest.mark.parametrize('outcome', ['approved', 'missing-measured'])
def test_original_graph_runtime_executes_supported_envelope_and_keeps_review_explicit(envelope_canvas, outcome):
    e = envelope_canvas
    graph, row, captured, queued = queued_original_graph(e)
    runtime = e.graph.media_runtime
    row = runtime.execute_job(e.nid, e.scope, e.actor, row['id'], {
        'expected_version': row['version'], 'node_id': 'trim',
        'expected_job_version': queued['version'], 'expected_request_digest': queued['request_digest']}, lambda: None)
    candidate = row['media_runtime']['nodes'][0]['execution']['job']
    assert row['current_node_id'] == 'review' and candidate['status'] == 'AWAITING_REVIEW'
    # Public Graph receipts intentionally omit command/recipe/measurement. Read
    # the original job using the original run binding, never widen that DTO.
    original = get_graph_job(e, row, candidate)
    assert original['execution_recipe']['parameters'] == TEMPLATE
    assert original['media_measurement'] is None  # Original Graph public projection stays unchanged.
    stored = e.graph._owned(e.nid, e.scope, e.actor, e.graph.RUNS, row['id'])
    raw, _ = e.production._row(e.nid, e.scope, e.actor, 'audio', candidate['id'], lambda: None,
                              graph_binding=stored['media_executions']['trim']['graph_binding'])
    measured = raw['measured']
    assert measured['duration_ms'] == 1000 and measured['profile_validation'] == 'PCM_DECODED'
    assert measured['sample_rate'] == RATE and measured['channels'] == 2
    meta, data = runtime.candidate(e.nid, e.scope, e.actor, row['id'], 'trim', lambda: None)
    with wave.open(io.BytesIO(data), 'rb') as stream:
        assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getnframes()) == (RATE, 2, 2, RATE)
        pcm = stream.readframes(stream.getnframes())
    samples = struct.unpack('<' + 'h' * (len(pcm) // 2), pcm)
    assert samples[0::2] == samples[1::2]
    plateau = AMPLITUDE * 10 ** (TEMPLATE['gain_db'] / 20)
    maximum_error = max(abs(sample - plateau * min(1, (index * 1000 / RATE) / 200)
        * min(1, (1000 - index * 1000 / RATE) / 300)) for index, sample in enumerate(samples[0::2]))
    assert maximum_error <= 1.1
    assert hashlib.sha256(data).hexdigest() == meta['sha256'] == candidate['output_candidate']['digest']
    with pytest.raises(FileNotFoundError):
        e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    review_body = {'expected_version': row['version'], 'node_id': 'review',
        'expected_job_version': candidate['version'], 'expected_request_digest': candidate['request_digest'],
        'reviewed_output_digest': candidate['output_candidate']['digest']}
    if outcome == 'missing-measured':
        audio = e.production._audio(e.scope, e.actor)
        state = audio.store.load(e.nid, include_studio=True)
        persisted = next(job for job in state['jobs'] if job['id'] == candidate['id'])
        persisted.pop('measured')
        audio.store.save(e.nid, state, include_studio=True)
        with pytest.raises(AudiobookError) as failure:
            get_graph_job(e, row, candidate)
        assert failure.value.code == 'STUDIO_AUDIO_MEASUREMENT_INVALID'
        with pytest.raises(AudiobookError) as failure:
            runtime.review(e.nid, e.scope, e.actor, row['id'], review_body, lambda: None)
        assert failure.value.code == 'STUDIO_AUDIO_MEASUREMENT_INVALID'
        with pytest.raises(FileNotFoundError):
            e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
        return
    row = runtime.review(e.nid, e.scope, e.actor, row['id'], review_body, lambda: None)
    assert row['status'] == 'SUCCEEDED' and row['reviewed']
    formal = e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    assert formal['version'] == 2
    assert e.graph.get(e.nid, e.scope, e.actor, graph['id']) == graph
    folder = os.environ.get('STUDIO_AUDIO_TEMPLATE_CAPTURE_DIR')
    if folder:
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        evidence = {'contract': 'owned-original-graph-audio-effects-proof/1',
            'real_cpu_ffmpeg': True, 'model_inference': False, 'graph': graph,
            'preview': captured, 'queued_receipt': queued, 'executed_original_job': original,
            'succeeded_run': row, 'formal': formal, 'original_audio_measurement': measured,
            'independent_frames': len(samples) // 2,
            'maximum_absolute_lsb_error': maximum_error,
            'candidate_sha256': hashlib.sha256(data).hexdigest(),
            'independent_pcm_sha256': hashlib.sha256(pcm).hexdigest()}
        (path / 'native-original-graph-effects.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')



def test_mounted_original_preview_and_jobs_echo_template_effects_and_reject_tampering(audio_client, monkeypatch):
    e = audio_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    from app.creative.canvas_views import CreativeCanvasViews
    from app.creative.graph_asset_inputs import GraphAssetInputs
    graphs = e.experimental.creative_graph_service
    monkeypatch.setattr(graphs, 'store', e.studio.store)
    monkeypatch.setattr(graphs, 'workspace', e.studio)
    monkeypatch.setattr(graphs, 'asset_inputs', GraphAssetInputs(graphs))
    monkeypatch.setattr(graphs, 'canvas_views', CreativeCanvasViews(graphs))
    graphs.configure_media(e.production)
    params = {**TEMPLATE, 'in_ms': 100, 'out_ms': 800}
    graph = checked(e.client.post(e.studio_base + '/graphs', headers=e.headers, json={
        'request_id': 'api-owned-envelope-template', 'expected_version': 0,
        'definition': definition(e, params)}), 201)
    canvas = checked(e.client.post(e.studio_base + '/canvas-views', headers=e.headers, json={
        'request_id': 'api-owned-envelope-card', 'definition': {'title': 'Owned API audio task',
            'cards': [{'id': 'origin-audio', 'position': {'x': 40, 'y': 60}, 'asset': reference(e.source)}]}}), 201)
    e.command['parameters'] = {**params, 'gain_db': -3, 'fade_in_ms': 50, 'fade_out_ms': 100}
    e.command['template_ref'] = pin(graph)
    source = e.command['source_snapshots'][0]
    e.command['canvas_return'] = {'contract': 'studio-canvas-return/1', 'project_id': e.nid,
        'scope': e.scope, 'incarnation': e.studio.store.incarnation(e.nid), 'canvas_id': canvas['id'],
        'canvas_version': canvas['version'], 'canvas_digest': canvas['definition_digest'],
        'card_id': 'origin-audio', 'source': source}
    no_native(monkeypatch)
    response = e.client.post(e.base + '/preview', headers=e.headers, json=e.command)
    captured = checked(response)
    assert captured['command']['template_ref'] == pin(graph)
    assert captured['execution_recipe']['parameters'] == e.command['parameters']
    assert response.headers['cache-control'] == 'no-store'
    queued = checked(e.client.post(e.base + '/jobs', headers=e.headers, json={
        'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}), 201)
    expected = deepcopy(e.command)
    # The mounted typed source contract has always added this literal marker.
    expected['source_snapshots'] = [{**source, 'reference_only': True} for source in expected['source_snapshots']]
    assert queued['status'] == 'QUEUED' and queued['command'] == expected
    assert queued['execution_recipe']['parameters'] == e.command['parameters']
    assert checked(e.client.get(e.base + '/jobs/audio/' + queued['id'], headers=e.headers)) == queued
    bad = deepcopy(e.command)
    bad['request_id'] = 'api-tampered-template-effects'
    bad['template_ref']['parameters']['gain_db'] = -5
    rejected = e.client.post(e.base + '/preview', headers=e.headers, json=bad)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()['detail'] == {'code': 'EXPERIMENTAL_INVALID',
                                         'message': 'STUDIO_CANVAS_AUDIO_TEMPLATE_CHANGED'}
    rejected_create = e.client.post(e.base + '/jobs', headers=e.headers, json={
        'command': bad, 'reviewed_preview_digest': captured['preview_digest']})
    assert rejected_create.status_code == 422, rejected_create.text
    assert rejected_create.json()['detail']['message'] == 'STUDIO_CANVAS_AUDIO_TEMPLATE_CHANGED'
    current = checked(e.client.get(e.base + '/jobs', headers=e.headers))
    assert [row['id'] for row in current['items']] == [queued['id']]
    assert checked(e.client.get(e.base + '/jobs/audio/' + queued['id'], headers=e.headers)) == queued
