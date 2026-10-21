"""Standalone trim controls over original owners; actual CPU FFmpeg on fixture WAV.

The waveform is synthetic. Encoding and PCM decoding, original File/PostgreSQL
project admission, private Asset persistence and review are real. No model runs.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
import shutil
import struct
import wave

import pytest

from app.audio_production_store import AudioProductionStore
from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaCommand, MediaJobAction, MediaReview, MediaParameters
from app.services.audiobook_service import AudiobookError
from app.services.image_job_service import ImageJobService
from app.services.studio_audio_execution import _body, _digest, StudioAudioExecution
from test_v2_independent_workspace import rig, reopened, import_asset


class NoControl:
    def __getattr__(self, name):
        raise AssertionError('local trim attempted provider or external control: ' + name)


def wav_bytes(rate=16000, channels=1, milliseconds=1000, amplitude=2000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setnchannels(channels); writer.setsampwidth(2); writer.setframerate(rate)
        writer.writeframes(struct.pack('<h', amplitude) * (rate * milliseconds // 1000) * channels)
    return output.getvalue()


def snapshot(row):
    return {'kind': 'ASSET', 'asset_kind': 'audio', 'id': row['id'], 'version': row['version'], 'digest': row['sha256']}


def command(source=None, **parameters):
    return {'operation_id': 'm8.audio.trim', 'request_id': 'trim-one', 'provider_id': None, 'model_id': None,
        'prompt': '', 'parameters': {'in_ms': 100, 'out_ms': 800, **parameters}, 'allow_cloud': False,
        'source_snapshots': [source or {'kind': 'ASSET', 'asset_kind': 'audio', 'id': 'source-a', 'version': 1, 'digest': 'b' * 64}],
        'license_note': ''}


def production(e, workspace=None):
    return ProductionExecutionService(workspace or e.service, ImageJobService(e.root), NoControl(),
        NoControl(), {}, {}, AudioProductionStore(e.root / 'audio-production'), NoControl(), NoControl())


@pytest.fixture
def audio(rig):
    e = rig; assert shutil.which('ffmpeg'), 'real PCM controls require installed FFmpeg'
    e.service.activate(e.nid, e.scope, e.actor)
    e.source = import_asset(e, data=wav_bytes(), filename='owned-fixture.wav', kind='audio')
    e.production = production(e)
    e.command = command(snapshot(e.source), gain_db=-6.020599913279624, sample_rate=22050, channels=1)
    return e


def preview(e, value=None, **kwargs):
    return e.production.preview(e.nid, e.scope, e.actor, value or e.command, lambda: None, **kwargs)[0]


def queue(e, value=None):
    value = value or e.command
    p = preview(e, value)
    return e.production.create(e.nid, e.scope, e.actor, {'command': value, 'reviewed_preview_digest': p['preview_digest']}, lambda: None)


def action(row, review=False):
    values = {'expected_version': row['version'], 'expected_request_digest': row['request_digest']}
    return MediaReview(**values, reviewed_output_digest=row['output_candidate']['digest']) if review else MediaJobAction(**values)


def run(e, row):
    return e.production.execute(e.nid, e.scope, e.actor, 'audio', row['id'], action(row), lambda: None)


def get(e, row):
    return e.production.get(e.nid, e.scope, e.actor, 'audio', row['id'], lambda: None)


def review(e, row):
    return e.production.review(e.nid, e.scope, e.actor, 'audio', row['id'], action(row, True), lambda: None)


def test_actual_wav_gain_resampling_mono_private_review_and_reopen(audio):
    e = audio; p = preview(e)
    assert p['execution_recipe']['output_profile'] == 'PCM_S16LE_WAV_22050_MONO'
    assert p['execution_recipe']['parameters'] == e.command['parameters'] and p['provider'] is None
    queued = queue(e); assert queue(e) == queued and queued['media_measurement'] is None
    candidate = run(e, queued); assert candidate['status'] == 'AWAITING_REVIEW', candidate
    measured = candidate['media_measurement']; asset = candidate['output_candidate']
    assert measured == {'duration_ms': 700, 'byte_count': measured['byte_count'], 'sample_rate': 22050,
        'channels': 1, 'sample_width': 2, 'container': 'wav', 'audio_codec': 'pcm_s16le',
        'profile_validation': 'PCM_DECODED', 'output_sha256': asset['digest']}
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, asset['id'])
    meta, data = e.production.candidate(e.nid, e.scope, e.actor, 'audio', candidate['id'], lambda: None)
    assert len(data) == measured['byte_count'] and hashlib.sha256(data).hexdigest() == asset['digest'] == meta['sha256']
    with wave.open(io.BytesIO(data), 'rb') as result:
        assert (result.getframerate(), result.getnchannels(), result.getsampwidth()) == (22050, 1, 2)
        samples = struct.unpack('<' + 'h' * result.getnframes(), result.readframes(result.getnframes()))
    # Actual samples, not requested gain repeated as a claimed measurement.
    assert max(abs(sample - 1000) for sample in samples[100:-100]) <= 1
    e.production = production(e, reopened(e)); assert get(e, queued) == candidate
    approved = review(e, candidate); assert approved['status'] == 'APPROVED'
    assert approved['media_measurement'] == measured and approved['approved_asset_version'] == 2
    assert e.service.asset(e.nid, e.scope, asset['id'])['provenance']['origin'] == 'DERIVED_PROCESSING'
    assert review(e, approved) == approved
    with pytest.raises(AudiobookError, match='版本'): review(e, candidate)
    assert e.chapters.list(e.nid) == []


def test_omitted_controls_still_execute_original_48000_stereo(audio):
    e = audio; e.command = command(snapshot(e.source))
    p = preview(e)
    assert p['execution_recipe']['output_profile'] == 'PCM_S16LE_WAV_48000_STEREO'
    assert not {'gain_db', 'sample_rate', 'channels'}.intersection(p['command']['parameters'])
    result = run(e, queue(e)); assert result['status'] == 'AWAITING_REVIEW', result
    assert result['media_measurement']['sample_rate'] == 48000 and result['media_measurement']['channels'] == 2


@pytest.mark.parametrize('parameters', [
    {'gain_db': -60.1}, {'gain_db': 12.1}, {'gain_db': math.nan}, {'gain_db': math.inf}, {'gain_db': True}, {'gain_db': 'volume=1'},
    {'sample_rate': 7999}, {'sample_rate': 96001}, {'sample_rate': 22050.0}, {'sample_rate': True}, {'sample_rate': '48000'},
    {'channels': 0}, {'channels': 3}, {'channels': 1.0}, {'channels': True}, {'codec': 'mp3'}, {'speed': 1.2}, {'normalize': True},
])
def test_controls_are_closed_strict_and_finite_in_both_owners(parameters):
    value = command(**parameters)
    with pytest.raises(ValueError): MediaCommand.model_validate(value)
    payload = {key: item for key, item in value.items() if key not in {'request_id', 'allow_cloud', 'license_note'}}
    with pytest.raises(AudiobookError): _body(payload)


@pytest.mark.parametrize('key,value', [('output_format', 'FLAC'), ('sample_rate', 48000), ('channels', 2)])
def test_graph_and_non_trim_operations_do_not_gain_new_controls(key, value):
    with pytest.raises(ValueError):
        MediaNodeParameters.model_validate({'operation_id': 'm8.audio.trim', 'parameters': {'in_ms': 0, 'out_ms': 10, key: value}})
    with pytest.raises(ValueError, match='STUDIO_OPERATION_PARAMETER_UNSUPPORTED'):
        MediaCommand.model_validate({**command(**{key: value}), 'operation_id': 'm8.audio.music'})
    service = object.__new__(ProductionExecutionService)
    with pytest.raises(ValueError, match='STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'):
        service.preview('project', {}, 'actor', command(**{key: value}), lambda: None, graph_binding={})


def test_capacity_rejected_before_native_execution_and_parameter_change_invalidates_preview(audio, monkeypatch):
    e = audio
    from app.services import studio_timeline_export
    monkeypatch.setattr(studio_timeline_export, 'run_guarded_process', lambda *a, **k: pytest.fail('preview must not execute'))
    value = command(snapshot(e.source), in_ms=0, out_ms=120000, sample_rate=96000, channels=2)
    with pytest.raises(AudiobookError, match='PCM WAV') as failure: preview(e, value)
    assert failure.value.code == 'STUDIO_AUDIO_TRIM_BYTES_BUDGET_EXCEEDED'
    captured = preview(e)
    for key, replacement in [('gain_db', 0.0), ('sample_rate', 44100), ('channels', 2)]:
        changed = deepcopy(e.command); changed['parameters'][key] = replacement
        assert preview(e, changed)['preview_digest'] != captured['preview_digest']
        with pytest.raises(ValueError):
            e.production.create(e.nid, e.scope, e.actor, {'command': changed, 'reviewed_preview_digest': captured['preview_digest']}, lambda: None)


def legacy_preview_service():
    service = object.__new__(ProductionExecutionService)
    service._base = lambda *args: {'actor': 'author', 'scope_key': 'a' * 64, 'incarnation': 'file:legacy-fixture'}
    service._binding = lambda c: None
    service._sources_current = lambda nid, scope, context, guard: [{'snapshot': s, 'measured': {
        'duration_ms': 1000, 'sample_rate': 8000, 'channels': 1}} for s in context['sources']]
    service._egress = lambda *args: None
    return service


def test_exact_legacy_command_preview_recipe_request_and_owner_hashes_are_stable():
    # Values captured from unchanged 005893ef before this implementation.
    service = legacy_preview_service(); value = command(); value['request_id'] = 'legacy-trim'
    p, context, parsed = service.preview('project', {}, 'author', value, lambda: None)
    assert digest(parsed.model_dump()) == '12113d9776ca251b2ffc03a22345193e58b140da7c8dc0a2a4085fc7f9dacf27'
    assert p['request_digest'] == '2f90a075e3dd51ee00549d77fe46e952ad71992ba989dc477168b3fedda86a6f'
    assert p['preview_digest'] == 'f7ece5c37a5a892e09e83df4fb6874301bd218361a6270ac1f4f63e8da267aef'
    assert p['execution_recipe']['recipe_digest'] == 'bd7b3525f584ffcb10c5376c4822d02958233bd127ce5bae2ce7e2640dec8a3c'
    context['command'] = parsed.model_dump()
    payload = parsed.model_dump(exclude={'source_snapshots', 'allow_cloud', 'license_note', 'request_id'})
    payload['parameters'] = parsed.parameters.model_dump(exclude_none=True); payload['source_snapshots'] = context['sources']
    assert _digest({'body': _body(payload), 'context': context}) == '71f21f6bcc0a54198648a3978989decc59f0126071ac1b2067fdaee2f5e13c61'
    assert json.loads(parsed.model_dump_json()) == parsed.model_dump()
    explicit_nulls = deepcopy(value); explicit_nulls['parameters'].update(gain_db=None, sample_rate=None, channels=None)
    assert service.preview('project', {}, 'author', explicit_nulls, lambda: None)[0] == p
    assert set(MediaParameters().model_dump()) == {'width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality',
        'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms'}


def test_original_legacy_receipt_hash_is_not_widened():
    row = {'id': 'audio-one', 'version': 1, 'request_digest': 'a' * 64, 'status': 'QUEUED', 'attempt': 0,
        'dispatch_state': 'NOT_SENT', 'publication_state': 'NOT_STARTED', 'review_state': 'NOT_READY'}
    fields = ('id', 'version', 'request_digest', 'status', 'attempt', 'dispatch_state', 'publication_state',
        'review_state', 'remote_task_id', 'provider_status', 'output_asset_id', 'candidate_asset_version',
        'output_digest', 'duration_ms', 'media_validation', 'cancellation_mode', 'error_code')
    expected = _digest({key: row.get(key) for key in fields}); StudioAudioExecution._receipt(row)
    assert row['receipt_digest'] == expected


@pytest.mark.parametrize('mutation', ['source', 'cas', 'cancel', 'measurement', 'measurement_missing', 'recipe'])
def test_authoritative_source_cas_cancel_and_receipt_fences(audio, mutation):
    e = audio; queued = queue(e)
    owner = e.production._audio(e.scope, e.actor)
    if mutation == 'source':
        with e.service._asset_scope(e.nid, e.scope):
            e.assets.update_metadata(e.source['id'], {'scene_id': 'changed'}, expected_version=e.source['version'])
        result = run(e, queued); assert result['status'] == 'FAILED'
    elif mutation == 'cas':
        with pytest.raises(Exception):
            e.production.execute(e.nid, e.scope, e.actor, 'audio', queued['id'],
                MediaJobAction(expected_version=queued['version'] + 1, expected_request_digest=queued['request_digest']), lambda: None)
        assert get(e, queued)['status'] == 'QUEUED'
    elif mutation == 'cancel':
        cancelled = e.production.cancel(e.nid, e.scope, e.actor, 'audio', queued['id'], action(queued), lambda: None)
        assert cancelled['status'] == 'CANCELLED'
        with pytest.raises(AudiobookError): run(e, cancelled)
    else:
        result = run(e, queued); assert result['status'] == 'AWAITING_REVIEW'
        state = owner.store.load(e.nid, include_studio=True); saved = state['jobs'][0]
        if mutation == 'measurement': saved['measured']['sample_rate'] = 48000
        elif mutation == 'measurement_missing': saved.pop('measured')
        else: saved['context']['execution_recipe']['parameters']['gain_db'] = 1
        owner.store.save(e.nid, state, include_studio=True)
        with pytest.raises(AudiobookError): get(e, queued)
        with pytest.raises(AudiobookError): review(e, result)
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1


def test_old_preview_can_still_create_and_replay_exact_original_job(tmp_path, monkeypatch):
    from test_v2_studio_audio_listing import make_owner
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    service = legacy_preview_service(); value = command(); value['request_id'] = 'legacy-trim'
    owner = make_owner(tmp_path, actor='author', branch=None)
    service._audio = lambda *args: owner
    service._source_guard = lambda *args: lambda snapshot: snapshot
    create = {'command': value, 'reviewed_preview_digest': 'f7ece5c37a5a892e09e83df4fb6874301bd218361a6270ac1f4f63e8da267aef'}
    result = service.create('project', {}, 'author', create, lambda: None)
    stored = owner.store.load('project', include_studio=True)['jobs'][0]
    assert stored['request_sha256'] == '71f21f6bcc0a54198648a3978989decc59f0126071ac1b2067fdaee2f5e13c61'
    assert digest(stored['context']['command']) == '12113d9776ca251b2ffc03a22345193e58b140da7c8dc0a2a4085fc7f9dacf27'
    assert 'measured' not in stored
    assert service.create('project', {}, 'author', create, lambda: None) == result


def test_explicit_default_controls_are_reviewed_and_not_dropped():
    service = legacy_preview_service(); old = command()
    p = service.preview('project', {}, 'author', old, lambda: None)[0]
    for key, value in [('gain_db', 0.0), ('sample_rate', 48000), ('channels', 2)]:
        new = command(**{key: value}); result = service.preview('project', {}, 'author', new, lambda: None)[0]
        assert result['command']['parameters'][key] == value
        assert result['execution_recipe']['parameters'][key] == value
        assert result['request_digest'] != p['request_digest'] and result['preview_digest'] != p['preview_digest']


def test_lost_publication_recovers_exact_measured_private_wav_without_reencoding(audio, monkeypatch):
    e = audio; queued = queue(e); create = e.assets.create
    def lost(*args, **kwargs):
        create(*args, **kwargs)
        raise OSError('synthetic lost publication response')
    monkeypatch.setattr(e.assets, 'create', lost)
    interrupted = run(e, queued)
    assert interrupted['status'] == 'UNKNOWN' and interrupted['media_measurement']
    monkeypatch.setattr(e.assets, 'create', create)
    import app.services.studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('recovery must not reencode'))
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, 'audio', queued['id'], action(interrupted), lambda: None)
    assert recovered['status'] == 'AWAITING_REVIEW' and recovered['attempt'] == 1
    assert recovered['media_measurement'] == interrupted['media_measurement']
    assert recovered['output_candidate']['digest'] == recovered['media_measurement']['output_sha256']
    assert review(e, recovered)['status'] == 'APPROVED'


def test_cancel_during_real_native_work_prevents_private_publication(audio, monkeypatch):
    e = audio; queued = queue(e)
    import app.services.studio_timeline_export as native
    original = native.run_guarded_process
    def cancel_after_native(*args, **kwargs):
        result = original(*args, **kwargs)
        running = get(e, queued)
        cancelled = e.production.cancel(e.nid, e.scope, e.actor, 'audio', queued['id'], action(running), lambda: None)
        assert cancelled['status'] == 'CANCELLED'
        return result
    monkeypatch.setattr(native, 'run_guarded_process', cancel_after_native)
    result = run(e, queued)
    assert result['status'] == 'CANCELLED' and result['output_candidate'] is None and result['media_measurement'] is None
    assert len(list(e.assets.root.glob('*.bin'))) == 1


@pytest.mark.parametrize('change', ['sample_rate', 'channels', 'sample_width', 'duration'])
def test_wrong_actual_wav_profile_is_rejected_even_if_tool_reports_success(audio, monkeypatch, change):
    # Synthetic malicious tool output, decoded for real. This is failure-path
    # evidence, distinct from the native success fixtures above.
    from pathlib import Path
    e = audio; queued = queue(e)
    import app.services.studio_timeline_export as native
    def wrong_output(argv, **kwargs):
        kwargs['guard']()
        values = {'rate': 22050, 'channels': 1, 'milliseconds': 700}
        if change == 'sample_rate': values['rate'] = 48000
        elif change == 'channels': values['channels'] = 2
        elif change == 'duration': values['milliseconds'] = 600
        content = wav_bytes(**values)
        if change == 'sample_width':
            output = io.BytesIO()
            with wave.open(output, 'wb') as writer:
                writer.setnchannels(1); writer.setsampwidth(1); writer.setframerate(22050)
                writer.writeframes(bytes([128]) * 15435)
            content = output.getvalue()
        Path(argv[-1]).write_bytes(content)
    monkeypatch.setattr(native, 'run_guarded_process', wrong_output)
    result = run(e, queued)
    assert result['status'] == 'FAILED' and result['output_candidate'] is None and result['media_measurement'] is None
    assert len(list(e.assets.root.glob('*.bin'))) == 1


def test_fixed_native_arguments_never_accept_arbitrary_filters(audio, monkeypatch):
    e = audio; observed = []
    import app.services.studio_timeline_export as native
    original = native.run_guarded_process
    def capture(argv, **kwargs):
        observed.append((argv, kwargs))
        return original(argv, **kwargs)
    monkeypatch.setattr(native, 'run_guarded_process', capture)
    assert run(e, queue(e))['status'] == 'AWAITING_REVIEW'
    argv, kwargs = observed[0]
    assert len(observed) == 1 and argv[argv.index('-c:a') + 1] == 'pcm_s16le'
    assert argv[argv.index('-af') + 1].startswith('volume=-6.020599913279624')
    assert argv[argv.index('-ar') + 1] == '22050' and argv[argv.index('-ac') + 1] == '1'
    assert argv[argv.index('-protocol_whitelist') + 1] == 'file,pipe'
    assert '-nostdin' in argv and kwargs['timeout'] == 50 and callable(kwargs['guard'])


def test_graph_media_parameter_schema_is_not_expanded():
    schema = MediaNodeParameters.model_json_schema()
    fields = schema['$defs']['MediaParameters']['properties']
    assert not {'gain_db', 'sample_rate', 'channels'}.intersection(fields)
    assert set(fields) == set(MediaParameters().model_dump())


def test_original_audio_binding_rejects_new_graph_controls_even_on_internal_entry():
    from app.creative.graph_media_binding import make_graph_binding_digest
    from app.services.studio_audio_execution import _binding
    service = legacy_preview_service()
    value = command(gain_db=0.0)
    _, context, parsed = service.preview('project', {}, 'author', value, lambda: None)
    graph = {'contract': 'creative-graph-media-binding/1', 'run_id': 'run', 'node_id': 'trim', 'graph_id': 'graph',
        'graph_version': 1, 'graph_digest': 'a' * 64, 'run_request_digest': 'b' * 64, 'input_digest': 'c' * 64,
        'preview_run_version': 1, 'command_digest': 'd' * 64}
    graph['attempt_digest'] = make_graph_binding_digest(graph, context)
    context['graph_binding'] = graph
    payload = parsed.model_dump(exclude={'source_snapshots', 'allow_cloud', 'license_note', 'request_id'})
    payload['parameters'] = parsed.parameters.model_dump(exclude_none=True); payload['source_snapshots'] = context['sources']
    with pytest.raises(AudiobookError) as failure: _binding(context, _body(payload))
    assert failure.value.code == 'STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'


@pytest.mark.parametrize('rate,channels,gain,amplitude,expected', [
    (8000, 1, -60.0, 2000, 2),
    (96000, 2, 12.0, 10000, 32767),
    (96000, 2, 12.0, -10000, -32768),
    (48000, 1, 12.0, 2000, 7962),
])
def test_real_boundary_profiles_and_pcm_saturation_keep_reviewed_duration(audio, rate, channels, gain, amplitude, expected):
    e = audio
    source = import_asset(e, data=wav_bytes(amplitude=amplitude, channels=channels), filename='boundary-fixture.wav', kind='audio')
    e.command = command(snapshot(source), gain_db=gain, sample_rate=rate, channels=channels)
    result = run(e, queue(e)); assert result['status'] == 'AWAITING_REVIEW', result
    measured = result['media_measurement']
    assert (measured['sample_rate'], measured['channels'], measured['sample_width'], measured['duration_ms']) == (rate, channels, 2, 700)
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'audio', result['id'], lambda: None)
    with wave.open(io.BytesIO(data), 'rb') as decoded:
        assert decoded.getnframes() == rate * 700 // 1000  # resampling must not change speed/duration
        samples = struct.unpack('<' + 'h' * decoded.getnframes() * channels, decoded.readframes(decoded.getnframes()))
    assert max(abs(sample - expected) for sample in samples[100:-100]) <= 1
    if expected in {32767, -32768}:
        assert set(samples[100:-100]) == {expected}  # PCM saturation, not an unrequested limiter/normalizer


def test_exact_pcm_capacity_edge_is_accepted_then_rejected_without_native_work():
    from app.services.studio_audio_execution import trim_output_profile
    rate, channels = 96000, 2
    maximum_ms = (25 * 1024 * 1024 - 4096) * 1000 // (rate * channels * 2)
    parameters = {'in_ms': 0, 'out_ms': maximum_ms, 'sample_rate': rate, 'channels': channels}
    assert trim_output_profile(parameters) == 'PCM_S16LE_WAV_96000_STEREO'
    accepted = command(**parameters)
    assert legacy_preview_service().preview('project', {}, 'author', accepted, lambda: None)[0]['execution_recipe']['parameters'] == parameters
    parameters['out_ms'] += 1
    with pytest.raises(AudiobookError) as failure: trim_output_profile(parameters)
    assert failure.value.code == 'STUDIO_AUDIO_TRIM_BYTES_BUDGET_EXCEEDED'
