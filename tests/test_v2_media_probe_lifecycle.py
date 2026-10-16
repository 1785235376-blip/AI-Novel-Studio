"""Original import/source/audio owners observe non-WAV inspection fences.

Fixtures use real CPU FFmpeg FLAC bytes. Long-running native children are
controlled test processes; no provider/model/network or paid work is performed.
"""
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from app.services import studio_timeline_export as native
from app.services.studio_audio_execution import StudioAudioExecution
from test_r3_mounted_contracts import mounted, prefix, scoped
from test_v2_audio_wav_controls_api import audio_client, client, checked, command, snapshot, upload, wav_bytes, queue, run


@pytest.fixture
def flac(tmp_path):
    source, target = tmp_path / 'fixture.wav', tmp_path / 'fixture.flac'
    source.write_bytes(wav_bytes())
    assert shutil.which('ffmpeg')
    subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-i', str(source), '-c:a', 'flac', '-y', str(target)], check=True, timeout=20,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return target.read_bytes()


@pytest.fixture
def non_wav_client(audio_client, flac):
    e = audio_client
    e.source = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(flac, kind='audio', filename='owned-fixture.flac')), 201)
    e.command = command(snapshot(e.source))
    return e


@pytest.fixture
def stall(monkeypatch):
    original = native.subprocess.Popen
    processes, directories = [], []
    def install(phase, changed):
        def launch(command, *args, **kwargs):
            selected = '-show_streams' in command if phase == 'probe' else '-map' in command and '-f' in command and 'null' in command
            if not selected:
                return original(command, *args, **kwargs)
            process = original([sys.executable, '-c', 'import time; time.sleep(60)'], *args, **kwargs)
            processes.append(process); directories.append(Path(kwargs['cwd']))
            changed()
            return process
        monkeypatch.setattr(native.subprocess, 'Popen', launch)
        return processes, directories
    yield install
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)


def assert_reaped(processes, directories):
    assert len(processes) == 1
    for process in processes:
        assert process.poll() is not None
        assert process.stderr.closed
        assert process.stdout is None or process.stdout.closed
    assert not any(path.exists() for path in directories)


@pytest.mark.parametrize('phase', ['probe', 'decode'])
def test_mounted_import_feature_revocation_interrupts_native_and_never_persists(audio_client, flac, stall, monkeypatch, phase):
    e = audio_client
    before = set(e.assets.root.glob('*.bin'))
    # Imports retain their original project/feature authority; production has
    # the additional captured Host-session fence tested separately below.
    processes, directories = stall(phase, lambda: monkeypatch.setenv('EXPERIMENTAL_FEATURES', ''))
    started = time.monotonic()
    response = e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(flac, kind='audio', filename='revoked.flac'))
    assert response.status_code in {401, 403, 404}, response.text
    assert time.monotonic() - started < 5
    assert_reaped(processes, directories)
    assert set(e.assets.root.glob('*.bin')) == before


@pytest.mark.parametrize('phase', ['probe', 'decode'])
def test_first_source_inspection_observes_cancel_outside_asset_lease(non_wav_client, stall, monkeypatch, phase):
    e = non_wav_client; _, queued = queue(e)
    before = set(e.assets.root.glob('*.bin'))
    lease_depth, attempt_checks = 0, []
    original_scope, original_attempt = e.studio._asset_scope, StudioAudioExecution._attempt
    @contextmanager
    def asset_scope(*args, **kwargs):
        nonlocal lease_depth
        with original_scope(*args, **kwargs):
            lease_depth += 1
            try:
                yield
            finally:
                lease_depth -= 1
    def attempt(*args, **kwargs):
        assert lease_depth == 0, 'job store must not be read while an asset lease is held'
        attempt_checks.append(1)
        return original_attempt(*args, **kwargs)
    monkeypatch.setattr(e.studio, '_asset_scope', asset_scope)
    monkeypatch.setattr(StudioAudioExecution, '_attempt', attempt)
    def cancel():
        assert lease_depth == 0
        current = checked(e.client.get(e.base + '/jobs/audio/' + queued['id'], headers=e.headers))
        assert current['status'] == 'RUNNING'
        cancelled = checked(e.client.post(e.base + '/jobs/audio/' + queued['id'] + '/cancel', headers=e.headers,
            json={'expected_version': current['version'], 'expected_request_digest': current['request_digest']}))
        assert cancelled['status'] == 'CANCELLED'
    processes, directories = stall(phase, cancel)
    started = time.monotonic(); result = checked(run(e, queued))
    assert time.monotonic() - started < 5
    assert result['status'] == 'CANCELLED' and result['output_candidate'] is None
    assert result['automatic_replay'] is False
    stored = e.audio.for_actor('local-author').load(e.nid, include_studio=True)
    assert next(row for row in stored['jobs'] if row['id'] == queued['id'])['receipt_state'] == 'NOT_SENT'
    assert attempt_checks
    assert_reaped(processes, directories)
    assert set(e.assets.root.glob('*.bin')) == before
    # The unchanged original cancelled receipt cannot execute/replay.
    retried = e.client.post(e.base + '/jobs/audio/' + queued['id'] + '/execute', headers=e.headers,
        json={'expected_version': result['version'], 'expected_request_digest': result['request_digest']})
    assert retried.status_code == 409
    assert len(processes) == 1


@pytest.mark.parametrize('phase', ['probe', 'decode'])
def test_mounted_source_revocation_interrupts_before_candidate(non_wav_client, stall, phase):
    e = non_wav_client; _, queued = queue(e)
    before = set(e.assets.root.glob('*.bin'))
    processes, directories = stall(phase, lambda: e.sessions.revoke(e.host))
    started = time.monotonic(); response = run(e, queued)
    assert response.status_code in {401, 403, 404}, response.text
    assert time.monotonic() - started < 5
    assert_reaped(processes, directories)
    assert set(e.assets.root.glob('*.bin')) == before


def test_real_flac_source_keeps_original_private_wav_review_flow(non_wav_client):
    e = non_wav_client; preview, queued = queue(e)
    assert preview['sources'][0]['measured'] == {'media_type': 'audio/flac', 'extension': 'flac',
        'duration_ms': 1000, 'validation': 'DECODED', 'codec': 'flac'}
    candidate = checked(run(e, queued))
    assert candidate['status'] == 'AWAITING_REVIEW', candidate
    assert candidate['media_measurement']['container'] == 'wav'
    assert candidate['media_measurement']['duration_ms'] == 700
    asset = candidate['output_candidate']
    assert e.client.get(e.studio_base + '/assets/' + asset['id'], headers=e.headers).status_code == 404
    approved = checked(e.client.post(e.base + '/jobs/audio/' + queued['id'] + '/review', headers=e.headers,
        json={'expected_version': candidate['version'], 'expected_request_digest': candidate['request_digest'],
              'reviewed_output_digest': asset['digest']}))
    assert approved['status'] == 'APPROVED'
    assert checked(e.client.get(e.studio_base + '/assets/' + asset['id'], headers=e.headers))['media_type'] == 'audio/wav'


@pytest.fixture
def timeline_client(audio_client, tmp_path, monkeypatch):
    from app.services.video_assembly_service import VideoAssemblyService
    e = audio_client
    monkeypatch.setattr(e.production, 'video_owner', VideoAssemblyService(e.root, e.assets))
    from app.creative.graph_asset_inputs import GraphAssetInputs
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    clip = tmp_path / 'fixture.mp4'
    subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-f', 'lavfi', '-i', 'color=c=blue:s=32x32:r=10:d=0.3', '-c:v', 'mpeg4',
        '-threads', '1', '-y', str(clip)], check=True, timeout=20,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    source = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(clip.read_bytes(), kind='video', filename='fixture.mp4')), 201)
    video = {**snapshot(source), 'asset_kind': 'video'}
    definition = {'duration_ms': 300, 'width': 32, 'height': 32, 'fps': 10,
        'tracks': [{'id': 'picture', 'kind': 'VIDEO', 'order': 0, 'clips': [
            {'id': 'blue', 'source_snapshot': video, 'start_ms': 0, 'in_ms': 0, 'out_ms': 300}]}]}
    e.timeline = checked(e.client.post(e.base + '/timelines', headers=e.headers,
        json={'title': 'Synthetic timeline', 'timeline': definition, 'expected_version': 0}), 201)
    return e


def render_timeline(e, mode):
    value = {'expected_version': e.timeline['version'], 'reviewed_timeline_digest': e.timeline['timeline_digest']}
    if mode == 'export':
        value['export_profile'] = {'preset': 'REVIEW_MP4'}
        preview = checked(e.client.post(e.base + '/timelines/' + e.timeline['id'] + '/export-preview',
            headers=e.headers, json=value))
        value['reviewed_export_digest'] = preview['preview_digest']
    value['request_id'] = 'one-render'
    return e.client.post(e.base + '/timelines/' + e.timeline['id'] + '/' + mode, headers=e.headers, json=value)


@pytest.mark.parametrize('mode', ['render', 'export'])
@pytest.mark.parametrize('phase', ['probe', 'decode'])
def test_timeline_initial_source_probe_observes_cancellation(timeline_client, stall, monkeypatch, mode, phase):
    e = timeline_client
    before = set(e.assets.root.glob('*.bin'))
    lease_depth = 0
    original_scope, original_read = e.studio._asset_scope, e.production.video_owner._studio_read
    @contextmanager
    def asset_scope(*args, **kwargs):
        nonlocal lease_depth
        with original_scope(*args, **kwargs):
            lease_depth += 1
            try:
                yield
            finally:
                lease_depth -= 1
    def read(*args, **kwargs):
        assert lease_depth == 0, 'timeline job read cannot run under source asset lease'
        return original_read(*args, **kwargs)
    monkeypatch.setattr(e.studio, '_asset_scope', asset_scope)
    monkeypatch.setattr(e.production.video_owner, '_studio_read', read)
    def cancel():
        assert lease_depth == 0
        jobs = checked(e.client.get(e.base + '/jobs', headers=e.headers))['items']
        current = next(row for row in jobs if row['owner'] == 'timeline')
        assert current['status'] == 'RUNNING'
        cancelled = checked(e.client.post(e.base + '/jobs/timeline/' + current['id'] + '/cancel', headers=e.headers,
            json={'expected_version': current['version'], 'expected_request_digest': current['request_digest']}))
        assert cancelled['status'] == 'CANCELLED'
    processes, directories = stall(phase, cancel)
    started = time.monotonic(); response = checked(render_timeline(e, mode))
    assert time.monotonic() - started < 5
    assert response['status'] == 'CANCELLED' and response['output_candidate'] is None
    assert response['automatic_replay'] is False
    assert_reaped(processes, directories)
    assert set(e.assets.root.glob('*.bin')) == before


@pytest.mark.parametrize('mode', ['render', 'export'])
def test_real_timeline_with_non_wav_sources_remains_private(timeline_client, mode):
    e = timeline_client
    result = checked(render_timeline(e, mode))
    assert result['status'] == 'SUCCEEDED', result
    assert result['media_measurement']['container'] == 'mp4'
    asset = result['output_candidate']
    assert e.client.get(e.studio_base + '/assets/' + asset['id'], headers=e.headers).status_code == 404
    response = e.client.get(e.base + '/jobs/timeline/' + result['id'] + '/candidate', headers=e.headers)
    assert response.status_code == 200 and response.headers['content-type'].startswith('video/mp4')


@pytest.mark.parametrize('phase', ['probe', 'decode'])
def test_provider_receipt_inspection_observes_original_attempt_cancel(tmp_path, flac, stall, monkeypatch, phase):
    import base64
    from types import SimpleNamespace
    from test_v2_studio_audio_listing import make_owner, binding, queued
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    owner = make_owner(tmp_path, assets=SimpleNamespace(MAX_BYTES=25 * 1024 * 1024))
    context = binding(); row = queued(owner, context)
    calls = []
    class FixtureProvider:
        endpoint = context['provider_binding']['endpoint']
        local = True
        supports_dispatch_guard = True
        def generate(self, request):
            request.dispatch_guard()
            calls.append('fixture-receipt')
            return SimpleNamespace(provider_id='fixture', model_id='fixture-tts', status='SUCCEEDED',
                remote_task_id='fixture-task', audio_uri='data:audio/flac;base64,' + base64.b64encode(flac).decode())
    provider = FixtureProvider()
    def cancel():
        current = owner.get('project', row['id'], context, lambda: None)
        owner.cancel('project', row['id'], current['version'], context, lambda: None)
    processes, directories = stall(phase, cancel)
    started = time.monotonic()
    result = owner.execute('project', row['id'], row['version'], context, lambda: None, lambda value: value,
        lambda *args: ('fixture', 'fixture-tts', provider),
        lambda *args: pytest.fail('cancelled receipt must never publish'), lambda *args: None)
    assert time.monotonic() - started < 5
    assert result['status'] == 'CANCELLED' and result.get('output_asset_id') is None
    assert result['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert calls == ['fixture-receipt']
    assert_reaped(processes, directories)


@pytest.mark.parametrize('phase', ['probe', 'decode'])
def test_queued_timeline_first_source_inspection_has_original_attempt_fence(timeline_client, stall, phase):
    from app.services.studio_timeline_render import studio_sources
    from app.creative.production_execution import digest
    e = timeline_client
    scope, actor = {'mode': 'local', 'novel_id': e.nid}, 'local-author'
    context = e.production._base(e.nid, scope, actor, lambda: None)
    context.update(request_id='queued-render', operation_id='m9.timeline.multitrack',
        sources=studio_sources(e.timeline['timeline']), rights={},
        timeline_snapshot={'id': e.timeline['id'], 'version': e.timeline['version'], 'digest': e.timeline['timeline_digest']})
    context['request_digest'] = digest(context)
    owner = e.production.video_owner
    queued = owner.queue_studio(e.nid, None, actor, e.timeline['timeline'], context=context, guard=lambda: None)
    source = e.production._source_guard(e.nid, scope, lambda: None)
    def cancel():
        current = owner.get_studio(e.nid, None, actor, queued['id'], context=context, guard=lambda: None)
        owner.cancel_studio(e.nid, None, actor, queued['id'], current['version'], current['request_digest'],
            context=context, guard=lambda: None)
    processes, directories = stall(phase, cancel)
    started = time.monotonic()
    result = owner.execute_studio(e.nid, None, actor, queued['id'], queued['version'], queued['request_digest'],
        context=context, guard=lambda: None, source_guard=source, inspect_source=source,
        publish=lambda *args: pytest.fail('cancelled timeline must never publish'))
    assert time.monotonic() - started < 5
    assert result['status'] == 'CANCELLED' and result.get('output_candidate') is None
    assert_reaped(processes, directories)
