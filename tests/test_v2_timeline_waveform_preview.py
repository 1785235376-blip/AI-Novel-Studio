"""Additive File-owner waveform contracts using genuine, locally generated WAV.

Fixtures use the original Asset owner directly, not a native media importer or
fabricated inspection result. No PostgreSQL, provider, model, or browser work.
"""
import base64
from copy import deepcopy
import io
import hashlib
import json
import struct
from types import SimpleNamespace
import wave

import pytest

from app.asset_providers import AssetProviderRegistry
from app.experimental.common import StaleSourceError
from test_v2_discovered_image_production import owner
from test_v2_independent_workspace import rig, png_bytes

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('rig', ['file'], indirect=True)]


def wav(samples, rate=8000, channels=1, width=2):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(rate)
        writer.writeframes(struct.pack('<' + 'h' * len(samples), *samples) if width == 2 else bytes(samples))
    return buffer.getvalue()


def reference(asset):
    return {'id': asset['id'], 'kind': 'ASSET', 'asset_kind': 'audio',
            'version': asset['version'], 'digest': asset['sha256']}


def persist_audio(workspace, nid, scope, data, *, key='waveform-source'):
    with workspace._asset_scope(nid, scope):
        return workspace.assets.create(nid, key + '.wav', base64.b64encode(data).decode(),
            'audio/wav', 'audio', key, branch_id=scope.get('branch_id'),
            required_features=('narrative_production_v2',))


def persist_visual(workspace, nid, scope):
    with workspace._asset_scope(nid, scope):
        return workspace.assets.create(nid, 'fixture.png', base64.b64encode(png_bytes()).decode(),
            'image/png', 'image', 'waveform-visual', branch_id=scope.get('branch_id'),
            required_features=('narrative_production_v2',))


def timeline(source, visual, *, in_ms=0, out_ms=100, speed_num=1, speed_den=1):
    return {'schema_version': 2, 'duration_ms': 10000, 'width': 640, 'height': 360, 'fps': 24,
        'tracks': [{'id': 'sound', 'kind': 'AUDIO', 'order': 0, 'gain_db': -6,
            'clips': [{'id': 'measured', 'source_snapshot': reference(source), 'start_ms': 500,
                'in_ms': in_ms, 'out_ms': out_ms, 'speed_num': speed_num, 'speed_den': speed_den,
                'gain_db': -12, 'muted': True}]},
            {'id': 'visual', 'kind': 'VIDEO', 'order': 1, 'clips': [
                {'id': 'still', 'source_snapshot': {**reference(visual), 'asset_kind': 'image'},
                 'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]}], 'captions': []}


def request_body(row):
    return {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'],
        'clip_id': 'measured', 'source_snapshot': deepcopy(row['timeline']['tracks'][0]['clips'][0]['source_snapshot'])}


def durable_files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def forbid_effects(monkeypatch, production):
    import subprocess
    import app.media_files as media
    import app.creative.workspace as workspace
    import app.creative.production_execution as execution
    import app.experimental.store as storage
    def forbidden(*args, **kwargs):
        raise AssertionError('waveform preview attempted native/provider/job/product-write work')
    for module in (media, workspace, execution):
        monkeypatch.setattr(module, 'inspect_media', forbidden)
    for name in ('run', 'Popen'):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(storage, 'atomic_write', forbidden)
    for name in ('create', 'execute', 'timeline_save', 'timeline_render', '_image', '_audio'):
        monkeypatch.setattr(production, name, forbidden)
    monkeypatch.setattr(production.workspace.assets, 'create', forbidden)
    monkeypatch.setattr(production.image_registry, 'get', forbidden)


@pytest.fixture
def waveform(rig, monkeypatch):
    production = owner(AssetProviderRegistry(), monkeypatch, rig)
    def prepare(samples=None, *, data=None, rate=8000, channels=1, **clip):
        raw = data if data is not None else wav(samples if samples is not None else [0] * 800, rate, channels)
        source = persist_audio(rig.service, rig.nid, rig.scope, raw)
        visual = persist_visual(rig.service, rig.nid, rig.scope)
        saved = production.timeline_save(rig.nid, rig.scope, rig.actor, None,
            {'expected_version': 0, 'title': 'Synthetic source envelope', 'timeline': timeline(source, visual, **clip)}, lambda: None)
        def preview(body=None, guard=lambda: None, *, scope=None, actor=None):
            return production.timeline_waveform_preview(rig.nid, scope or rig.scope, actor or rig.actor,
                saved['id'], body or request_body(saved), guard)
        return SimpleNamespace(rig=rig, production=production, source=source, visual=visual, saved=saved,
            raw=raw, preview=preview)
    return prepare


@pytest.mark.parametrize('channels', [1, 2])
def test_exact_source_peaks_silence_full_scale_and_last_bucket_are_read_only(waveform, monkeypatch, channels):
    frames = 800
    samples = [0] * (frames * channels)
    samples[0] = -32768
    samples[10 * channels + channels - 1] = 16384
    samples[-1] = 8192
    e = waveform(samples, channels=channels)
    before = durable_files(e.rig.root)
    forbid_effects(monkeypatch, e.production)
    result = e.preview()
    assert result['contract'] == 'studio-timeline-waveform-preview/1'
    assert result['status'] == 'MEASURED_PCM16_PEAKS' and result['scope'] == 'CLIP_SOURCE_ENVELOPE'
    assert result['timeline_id'] == e.saved['id'] and result['timeline_version'] == 1
    assert result['timeline_digest'] == e.saved['timeline_digest']
    assert result['source_snapshot'] == reference(e.source)
    assert result['byte_count'] == len(e.raw)
    assert (result['frame_count'], result['sample_rate'], result['channels']) == (frames, 8000, channels)
    assert result['duration_seconds'] == {'num': frames, 'den': 8000}
    assert (result['start_frame'], result['end_frame'], result['samples_per_bucket']) == (0, frames, 2)
    assert result['peaks'] == [1.0] + [0.0] * 4 + [0.5] + [0.0] * 393 + [0.25]
    assert result['clip'] == {'in_ms': 0, 'out_ms': 100, 'start_ms': 500, 'speed_num': 1, 'speed_den': 1}
    assert durable_files(e.rig.root) == before
    assert e.production.timeline_get(e.rig.nid, e.rig.scope, e.rig.actor, e.saved['id'], lambda: None) == e.saved
    assert e.production.timeline_history(e.rig.nid, e.rig.scope, e.rig.actor, e.saved['id'], lambda: None)['items'] == []


def test_ceil_half_open_trim_excludes_adjacent_impulses_before_binning(waveform):
    # 11025 Hz: [1, 3) ms is exactly frames [12, 34), not rounded [11, 33).
    samples = [0] * 100
    samples[11] = -32768; samples[12] = 4096; samples[33] = 16384; samples[34] = -32768
    e = waveform(samples, rate=11025, in_ms=1, out_ms=3, speed_num=2, speed_den=1)
    result = e.preview()
    assert (result['start_frame'], result['end_frame'], result['samples_per_bucket']) == (12, 34, 1)
    assert result['peaks'] == [0.125] + [0.0] * 20 + [0.5]
    assert result['frame_count'] == 100 and result['duration_seconds'] == {'num': 100, 'den': 11025}
    assert result['clip']['speed_num'] == 2


def test_partial_last_bucket_and_repeat_do_not_cache_or_persist(waveform, monkeypatch):
    samples = [0] * 1025; samples[-1] = -32768
    e = waveform(samples, rate=1000, out_ms=1025)
    before = durable_files(e.rig.root)
    forbid_effects(monkeypatch, e.production)
    first = e.preview(); second = e.preview()
    assert first == second
    assert first['samples_per_bucket'] == 3 and first['peaks'] == [0.0] * 341 + [1.0]
    assert len(first['peaks']) <= 512 and durable_files(e.rig.root) == before


@pytest.mark.parametrize('field', ['expected_version', 'reviewed_timeline_digest', 'source_version', 'source_digest', 'source_id', 'clip_id'])
def test_exact_reviewed_identity_cannot_be_rebound(waveform, field):
    e = waveform(); body = request_body(e.saved); before = durable_files(e.rig.root)
    if field == 'expected_version': body[field] += 1
    elif field == 'reviewed_timeline_digest': body[field] = '0' * 64
    elif field == 'source_version': body['source_snapshot']['version'] += 1
    elif field == 'source_digest': body['source_snapshot']['digest'] = '0' * 64
    elif field == 'source_id': body['source_snapshot']['id'] = 'other-source'
    else: body['clip_id'] = 'missing-clip'
    with pytest.raises((ValueError, FileNotFoundError, StaleSourceError)):
        e.preview(body)
    assert durable_files(e.rig.root) == before


@pytest.mark.parametrize('change', ['actor', 'scope', 'private', 'pin', 'tamper', 'recreate'])
def test_original_live_authorities_and_content_fail_closed(waveform, change):
    e = waveform(); options = {}
    if change == 'actor': options['actor'] = 'different-author'
    elif change == 'scope': options['scope'] = {**e.rig.scope, 'branch_id': 'wrong-branch'}
    elif change in {'private', 'pin'}:
        path = e.rig.assets._meta_path(e.source['id']); row = json.loads(path.read_text())
        if change == 'private': row['_owner_actor_id'] = e.rig.actor
        else: row['version'] += 1
        path.write_text(json.dumps(row))
    elif change == 'tamper':
        path = e.rig.assets._bin_path(e.source['id']); data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
    else:
        e.rig.novels.delete(e.rig.nid); e.rig.create_project(nid=e.rig.nid)
    before = durable_files(e.rig.root)
    with pytest.raises((ValueError, FileNotFoundError, StaleSourceError)):
        e.preview(**options)
    after = durable_files(e.rig.root)
    if change == 'scope':
        # Original File scope reads create one empty POSIX advisory lock. This
        # exact housekeeping artifact is not a product document or cache.
        key = e.rig.raw_store.key(e.rig.nid, options['scope'])
        name = '.workspace-mutation-locks/' + hashlib.sha256(('experimental:' + key).encode()).hexdigest() + '.lock'
        assert name not in before
        assert after.pop(name) == b''
    assert after == before


@pytest.mark.parametrize('kind', ['truncated-tail', 'truncated-data', 'not-wave', 'pcm8', 'too-fast', 'range'])
def test_malformed_or_unsupported_full_source_never_returns_early_trim(waveform, kind):
    data = wav([0] * 800)
    if kind == 'truncated-tail': data = data[:-2]
    elif kind == 'truncated-data':
        data = bytearray(data[:-2]); struct.pack_into('<I', data, 4, len(data) - 8); data = bytes(data)
    elif kind == 'not-wave': data = b'PRIVATE malformed source path /private/sentinel.wav'
    elif kind == 'pcm8': data = wav([128] * 800, width=1)
    elif kind == 'too-fast': data = wav([0] * 800, rate=192001)
    e = waveform(data=data, in_ms=0, out_ms=200 if kind == 'range' else 1)
    before = durable_files(e.rig.root)
    with pytest.raises(ValueError, match='STUDIO_WAVEFORM_'):
        e.preview()
    assert durable_files(e.rig.root) == before


@pytest.mark.parametrize('change', ['content', 'timeline', 'recreate'])
def test_injected_change_after_original_content_read_suppresses_result(waveform, monkeypatch, change):
    e = waveform(); original = e.rig.assets.content; triggered = []
    def changed(*args, **kwargs):
        data = original(*args, **kwargs)
        if not triggered:
            triggered.append(True)
            if change == 'content':
                path = e.rig.assets._bin_path(e.source['id']); mutated = bytearray(data); mutated[-1] ^= 1; path.write_bytes(mutated)
            elif change == 'timeline':
                from app.creative.production_execution import TIMELINES
                key = e.rig.service.store.key(e.rig.nid, e.rig.scope)
                e.rig.service.store._local.active[key]['collections'][TIMELINES][e.saved['id']]['version'] += 1
            else:
                e.rig.novels.delete(e.rig.nid); e.rig.create_project(nid=e.rig.nid)
        return data
    monkeypatch.setattr(e.rig.assets, 'content', changed)
    with pytest.raises((ValueError, FileNotFoundError, StaleSourceError)):
        e.preview()
    assert triggered


def test_oversized_metadata_rejects_before_any_binary_owner_read(waveform, monkeypatch):
    e = waveform(); path = e.rig.assets._meta_path(e.source['id'])
    metadata = json.loads(path.read_text()); metadata['size'] = 8 * 1024 * 1024 + 1
    path.write_text(json.dumps(metadata))
    def forbidden(*args, **kwargs):
        raise AssertionError('oversized source reached binary content reader')
    monkeypatch.setattr(e.rig.assets, 'content', forbidden)
    before = durable_files(e.rig.root)
    with pytest.raises(ValueError, match='STUDIO_WAVEFORM_LIMIT'):
        e.preview()
    assert durable_files(e.rig.root) == before


@pytest.mark.parametrize('change', ['source-pin', 'content', 'timeline'])
def test_change_at_pcm_checkpoint_suppresses_result(waveform, monkeypatch, change):
    import app.creative.timeline_waveform as module
    e = waveform(); original = module.pcm16_envelope; calls = []
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        if change == 'source-pin':
            path = e.rig.assets._meta_path(e.source['id']); row = json.loads(path.read_text()); row['version'] += 1
            path.write_text(json.dumps(row))
        elif change == 'content':
            path = e.rig.assets._bin_path(e.source['id']); raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
        else:
            from app.creative.production_execution import TIMELINES
            key = e.rig.service.store.key(e.rig.nid, e.rig.scope)
            e.rig.service.store._local.active[key]['collections'][TIMELINES][e.saved['id']]['version'] += 1
        return result
    monkeypatch.setattr(module, 'pcm16_envelope', changed)
    with pytest.raises((ValueError, FileNotFoundError, StaleSourceError)):
        e.preview()
    assert calls == [True]


def test_unrelated_missing_visual_does_not_trigger_whole_timeline_content_read(waveform, monkeypatch):
    e = waveform(); e.rig.assets._bin_path(e.visual['id']).unlink()
    original = e.rig.assets.content; observed = []
    def selected_only(asset_id, **kwargs):
        assert asset_id == e.source['id'], 'preview attempted unrelated visual content'
        observed.append(asset_id)
        return original(asset_id, **kwargs)
    monkeypatch.setattr(e.rig.assets, 'content', selected_only)
    before = durable_files(e.rig.root)
    assert e.preview()['peaks'] == [0.0] * 400
    assert observed and durable_files(e.rig.root) == before
