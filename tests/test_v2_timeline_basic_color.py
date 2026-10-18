"""Bounded basic clip color, original owners and real CPU pixel evidence.

Synthetic author-owned source media only; no browser/model/Windows acceptance.
"""
from copy import deepcopy
import hashlib
import json
import shutil
import struct
import subprocess
import types
import zlib

import pytest

from app.experimental.common import StaleSourceError
from app.services.studio_timeline_edit import apply_timeline_edits
from app.services.studio_timeline_export import run_guarded_process
from app.services.studio_timeline_render import normalize_studio_timeline, render_studio_timeline, timeline_digest
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import production, source, edit_body, cpu_video
from test_v2_audio_wav_controls import action

CAP = 25 * 1024 * 1024
NEUTRAL = {'brightness': 0, 'contrast': 1, 'saturation': 1}
ADJUSTED = {'brightness': .2, 'contrast': 1.25, 'saturation': 0}


def pixels_png(reverse=False):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    # Contrasting cool swatches, with independent dark/light center samples.
    colors = [(32, 48, 64), (160, 192, 224)]
    if reverse: colors.reverse()
    scan = b'\0' + b''.join(bytes(color) * 32 for color in colors)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 64, 64, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(scan * 64)) + chunk(b'IEND', b'')


def timeline(pin=None):
    pin = pin or {'id': 'original-image', 'kind': 'ASSET', 'asset_kind': 'image', 'version': 1, 'digest': 'a' * 64}
    return {'schema_version': 2, 'duration_ms': 1000, 'width': 64, 'height': 64, 'fps': 10, 'captions': [],
        'tracks': [{'id': 'picture', 'kind': 'VIDEO', 'order': 0, 'clips': [
            {'id': 'swatch', 'source_snapshot': pin, 'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]}]}


def clip(value): return value['tracks'][0]['clips'][0]


def change(value): return [{'op': 'clip.update', 'clip_id': 'swatch', 'changes': {'color_adjustment': value}}]


def decode(data, path, at_ms=0):
    path.write_bytes(data)
    target = path.with_suffix('.rgb')
    run_guarded_process([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1', '-i', str(path),
        '-ss', str(at_ms / 1000), '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-threads', '1', '-y', str(target)],
        cwd=path.parent, guard=lambda: None, timeout=20)
    values = target.read_bytes(); assert len(values) == 64 * 64 * 3
    samples = [list(values[(32 * 64 + x) * 3:(32 * 64 + x) * 3 + 3]) for x in (16, 48)]
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'rgb_samples': samples}


@pytest.mark.file_backend_only
@pytest.mark.parametrize('bad', [None, {}, [], 'eq=brightness=1', {'brightness': 0, 'contrast': 1},
    {**NEUTRAL, 'filter': 'movie=/etc/passwd'}, {**NEUTRAL, 'lut': '/x.cube'},
    {**NEUTRAL, 'brightness': True}, {**NEUTRAL, 'brightness': '0.2'},
    {**NEUTRAL, 'brightness': float('nan')}, {**NEUTRAL, 'contrast': float('inf')},
    {**NEUTRAL, 'brightness': -1.001}, {**NEUTRAL, 'brightness': 1.001},
    {**NEUTRAL, 'contrast': -.001}, {**NEUTRAL, 'contrast': 2.001},
    {**NEUTRAL, 'saturation': -.001}, {**NEUTRAL, 'saturation': 3.001}])
def test_closed_color_contract_rejects_invalid_numbers_fields_and_expressions(bad):
    value = timeline(); clip(value)['color_adjustment'] = bad
    with pytest.raises(ValueError): normalize_studio_timeline(value)


@pytest.mark.file_backend_only
def test_color_only_explicit_schema_two_video_and_atomic_remove_split_copy():
    original = normalize_studio_timeline(timeline())
    assert 'color_adjustment' not in clip(original)
    changed = apply_timeline_edits(original, change(ADJUSTED))
    assert clip(changed)['color_adjustment'] == ADJUSTED and timeline_digest(changed) != timeline_digest(original)
    assert normalize_studio_timeline(changed) == changed
    assert apply_timeline_edits(changed, change(None)) == original
    for low in (-1, 1):
        accepted = apply_timeline_edits(original, change({'brightness': low, 'contrast': 0 if low < 0 else 2, 'saturation': 0 if low < 0 else 3}))
        assert clip(accepted)['color_adjustment']['brightness'] == low
    legacy = timeline({**clip(original)['source_snapshot'], 'asset_kind': 'video'}); legacy.pop('schema_version')
    with pytest.raises(ValueError, match='SCHEMA_UPGRADE'): apply_timeline_edits(legacy, change(NEUTRAL))
    with pytest.raises(ValueError): normalize_studio_timeline({**legacy, 'tracks': [{**legacy['tracks'][0], 'clips': [{**clip(legacy), 'color_adjustment': NEUTRAL}]}]})
    upgraded = apply_timeline_edits(legacy, [{'op': 'canvas.update', 'changes': {'schema_version': 2}}, *change(NEUTRAL)])
    assert clip(upgraded)['color_adjustment'] == NEUTRAL
    split = apply_timeline_edits(changed, [{'op': 'clip.split', 'clip_id': 'swatch', 'at_ms': 500, 'new_clip_id': 'right'}])
    assert all(c['color_adjustment'] == ADJUSTED for c in split['tracks'][0]['clips'])
    copy = apply_timeline_edits(split, [{'op': 'clip.duplicate', 'clip_id': 'swatch', 'new_clip_id': 'copy', 'track_id': 'picture', 'start_ms': 500}, {'op': 'clip.remove', 'clip_id': 'right', 'ripple': False}])
    assert copy['tracks'][0]['clips'][1]['color_adjustment'] == ADJUSTED
    for version in (2, 3):
        audio = deepcopy(original['tracks'][0]); audio.update(kind='AUDIO', role='DIALOGUE', order=1, id='audio')
        audio['clips'] = [{'id': 'sound', 'source_snapshot': {**clip(original)['source_snapshot'], 'asset_kind': 'audio', 'id': 'audio-source'}, 'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]
        value = {**original, 'tracks': [original['tracks'][0], audio]} if version == 2 else {'schema_version': 3, 'media_kind': 'AUDIO', 'duration_ms': 1000, 'tracks': [audio]}
        for color in (NEUTRAL, None):
            with pytest.raises(ValueError): apply_timeline_edits(value, [{'op': 'clip.update', 'clip_id': 'sound', 'changes': {'color_adjustment': color}}])
        audio['clips'][0]['color_adjustment'] = NEUTRAL
        with pytest.raises(ValueError): normalize_studio_timeline(value)
    locked = deepcopy(changed); locked['tracks'][0]['locked'] = True
    with pytest.raises(ValueError, match='TRACK_LOCKED'): apply_timeline_edits(locked, change(None))
    with pytest.raises(ValueError): apply_timeline_edits(original, [*change(ADJUSTED), *change({**NEUTRAL, 'contrast': 3})])
    assert 'color_adjustment' not in clip(original)


@pytest.fixture
def color_timeline(rig):
    e = rig; e.service.activate(e.nid, e.scope, e.actor)
    e.image = import_asset(e, data=pixels_png(), filename='author-swatches.png', kind='image')
    e.production = production(e)
    e.row = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'Basic clip color', 'timeline': timeline(source(e.image))}, lambda: None)
    return e


def reviewed(row): return {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest']}


def test_color_original_edit_save_reopen_history_playback_cache_review_export(color_timeline, tmp_path):
    e = color_timeline; initial = e.row
    before = e.production.timeline_playback_preview(e.nid, e.scope, e.actor, initial['id'], reviewed(initial), lambda: None)
    assert before['cache_state'] == 'MISSING' and not e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']
    baseline = e.production.timeline_playback_build(e.nid, e.scope, e.actor, initial['id'],
        {**reviewed(initial), 'reviewed_playback_digest': before['playback_digest']}, lambda: None)['job']
    assert baseline['status'] == 'SUCCEEDED', baseline
    _, original_data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', baseline['id'], lambda: None)
    body = edit_body(initial, change(ADJUSTED), 'color-edit')
    edited = e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], body, lambda: None)
    assert e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], body, lambda: None) == edited
    assert clip(edited['timeline'])['color_adjustment'] == ADJUSTED
    with pytest.raises(StaleSourceError): e.production.timeline_playback_build(e.nid, e.scope, e.actor, initial['id'], {**reviewed(initial), 'reviewed_playback_digest': before['playback_digest']}, lambda: None)
    # Whole-document UI Save uses the same original owner and preserves color.
    saved = e.production.timeline_save(e.nid, e.scope, e.actor, edited['id'],
        {'expected_version': edited['version'], 'title': 'Saved basic color', 'timeline': edited['timeline']}, lambda: None)
    fresh = production(e, reopened(e)); assert fresh.timeline_get(e.nid, e.scope, e.actor, saved['id'], lambda: None) == saved
    preview = fresh.timeline_playback_preview(e.nid, e.scope, e.actor, saved['id'], reviewed(saved), lambda: None)
    assert preview['playback_digest'] != before['playback_digest'] and preview['cache_state'] == 'MISSING'
    built = fresh.timeline_playback_build(e.nid, e.scope, e.actor, saved['id'], {**reviewed(saved), 'reviewed_playback_digest': preview['playback_digest']}, lambda: None)
    job = built['job']; assert job['status'] == 'SUCCEEDED', job
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, job['output_candidate']['id'])
    _, data = fresh.candidate(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    old_proof, new_proof = decode(original_data, tmp_path / 'before.mp4'), decode(data, tmp_path / 'after.mp4')
    assert old_proof['sha256'] != new_proof['sha256']
    assert all(max(rgb) - min(rgb) <= 6 for rgb in new_proof['rgb_samples'])
    assert sum(new_proof['rgb_samples'][0]) > sum(old_proof['rgb_samples'][0]) + 60
    attested = fresh.timeline_playback_attest(e.nid, e.scope, e.actor, saved['id'], {**reviewed(saved), 'reviewed_playback_digest': preview['playback_digest'], 'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}, lambda: None)
    assert attested['sha256'] == new_proof['sha256']
    again = fresh.timeline_playback_build(e.nid, e.scope, e.actor, saved['id'], {**reviewed(saved), 'reviewed_playback_digest': preview['playback_digest']}, lambda: None)
    assert again['job']['id'] == job['id']
    approved = fresh.review(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job, True), lambda: None)
    assert approved['status'] == 'APPROVED'
    assert reopened(e).asset(e.nid, e.scope, job['output_candidate']['id'])['sha256'] == new_proof['sha256']
    history = fresh.timeline_history(e.nid, e.scope, e.actor, saved['id'], lambda: None)['items']
    assert next(row for row in history if row['version'] == edited['version'])['timeline'] == edited['timeline']
    restored = fresh.timeline_restore(e.nid, e.scope, e.actor, saved['id'], {**reviewed(saved), 'restore_version': initial['version'], 'restore_digest': initial['timeline_digest']}, lambda: None)
    assert restored['timeline'] == initial['timeline']
    (tmp_path / 'basic-color-proof.json').write_text(json.dumps({'before': old_proof, 'after': new_proof, 'authored': ADJUSTED}, indent=2))


def test_color_cas_track_lock_stale_source_and_invalid_batch_write_nothing(color_timeline):
    e = color_timeline; initial = e.row
    with pytest.raises(ValueError): e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], edit_body(initial, [*change(ADJUSTED), *change({**NEUTRAL, 'lut': '/tmp/x'})]), lambda: None)
    assert e.production.timeline_get(e.nid, e.scope, e.actor, initial['id'], lambda: None) == initial
    assert not e.production.timeline_history(e.nid, e.scope, e.actor, initial['id'], lambda: None)['items']
    edited = e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], edit_body(initial, change(ADJUSTED)), lambda: None)
    with pytest.raises(StaleSourceError): e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], edit_body(initial, change(None), 'stale'), lambda: None)
    locked = e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], edit_body(edited, [{'op': 'track.update', 'track_id': 'picture', 'changes': {'locked': True}}], 'lock'), lambda: None)
    replacement = deepcopy(locked['timeline']); clip(replacement).pop('color_adjustment')
    with pytest.raises(ValueError, match='TRACK_LOCKED'): e.production.timeline_save(e.nid, e.scope, e.actor, initial['id'], {'expected_version': locked['version'], 'title': locked['title'], 'timeline': replacement}, lambda: None)
    with e.service._asset_scope(e.nid, e.scope): e.assets.update_metadata(e.image['id'], {'scene_id': 'changed'}, expected_version=e.image['version'])
    with pytest.raises(StaleSourceError): e.production.timeline_playback_preview(e.nid, e.scope, e.actor, initial['id'], reviewed(locked), lambda: None)
    assert not e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']


def test_color_native_source_change_blocks_publication(color_timeline, monkeypatch):
    from app.services import studio_timeline_export as native
    e = color_timeline; e.row = e.production.timeline_edit(e.nid, e.scope, e.actor, e.row['id'], edit_body(e.row, change(ADJUSTED)), lambda: None)
    original = native.run_guarded_process; observed = []
    def changed(args, **kwargs):
        result = original(args, **kwargs)
        if '-filter_complex' in args and str(args[-1]).endswith('timeline.mp4'):
            observed.append(args[args.index('-filter_complex') + 1])
            with e.service._asset_scope(e.nid, e.scope): e.assets.update_metadata(e.image['id'], {'scene_id': 'changed'}, expected_version=e.image['version'])
        return result
    monkeypatch.setattr(native, 'run_guarded_process', changed)
    job = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], {**reviewed(e.row), 'request_id': 'color-source-change'}, lambda: None)
    assert observed and 'eq=brightness=0.20000000' in observed[0]
    assert job['status'] == 'FAILED' and job['output_candidate'] is None
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1


def test_color_unknown_recovers_original_output_without_second_render(color_timeline, monkeypatch):
    e = color_timeline; e.row = e.production.timeline_edit(e.nid, e.scope, e.actor, e.row['id'], edit_body(e.row, change(ADJUSTED)), lambda: None)
    original = e.assets.create; published = []
    def interrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        if str(args[1]).startswith('studio-timeline-'):
            published.append(result); raise OSError('owned post-publication interruption')
        return result
    monkeypatch.setattr(e.assets, 'create', interrupted)
    body = {**reviewed(e.row), 'request_id': 'color-unknown'}
    job = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], body, lambda: None)
    assert job['status'] == 'UNKNOWN' and len(published) == 1
    assert e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], body, lambda: None)['id'] == job['id']
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job), lambda: None)
    assert recovered['status'] == 'SUCCEEDED' and len(published) == 1
    assert e.production.review(e.nid, e.scope, e.actor, 'timeline', recovered['id'], action(recovered, True), lambda: None)['status'] == 'APPROVED'


@pytest.mark.file_backend_only
@pytest.mark.parametrize('kind', ['image', 'video'])
def test_each_basic_control_changes_real_pixels_and_neutral_is_identity(kind, tmp_path):
    data = pixels_png()
    if kind == 'video':
        path = tmp_path / 'swatches.png'; path.write_bytes(data); target = tmp_path / 'swatches.mp4'
        run_guarded_process([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1', '-loop', '1', '-i', str(path), '-t', '1', '-r', '10', '-c:v', 'mpeg4', '-threads', '1', '-y', str(target)], cwd=tmp_path, guard=lambda: None, timeout=20)
        data = target.read_bytes()
    pin = {'id': kind, 'kind': 'ASSET', 'asset_kind': kind, 'version': 1, 'digest': hashlib.sha256(data).hexdigest()}
    def guard(snapshot): return {'snapshot': deepcopy(pin), 'data': data, 'row': {'id': kind, 'kind': kind, 'version': 1, 'sha256': pin['digest']}}
    value = timeline(pin); original, _ = render_studio_timeline(value, source_guard=guard, guard=lambda: None, max_bytes=CAP)
    baseline = decode(original, tmp_path / 'baseline.mp4')
    neutral = apply_timeline_edits(value, change(NEUTRAL)); neutral_data, _ = render_studio_timeline(neutral, source_guard=guard, guard=lambda: None, max_bytes=CAP)
    assert original == neutral_data
    proofs = {'baseline': baseline}
    for control, setting in [('brightness', .2), ('contrast', .5), ('saturation', 0)]:
        adjusted = apply_timeline_edits(value, change({**NEUTRAL, control: setting}))
        output, _ = render_studio_timeline(adjusted, source_guard=guard, guard=lambda: None, max_bytes=CAP)
        result = decode(output, tmp_path / f'{control}.mp4'); proofs[control] = result
        assert result['sha256'] != baseline['sha256'] and result['rgb_samples'] != baseline['rgb_samples']
        if control == 'brightness': assert sum(result['rgb_samples'][0]) > sum(baseline['rgb_samples'][0]) + 90
        if control == 'contrast': assert sum(result['rgb_samples'][1]) - sum(result['rgb_samples'][0]) < .65 * (sum(baseline['rgb_samples'][1]) - sum(baseline['rgb_samples'][0]))
        if control == 'saturation': assert all(max(rgb) - min(rgb) <= 6 for rgb in result['rgb_samples'])
    (tmp_path / f'{kind}-controls-proof.json').write_text(json.dumps(proofs, indent=2))


@pytest.mark.file_backend_only
def test_absent_color_matches_frozen_schema_and_actual_legacy_render_bytes(tmp_path):
    ref = '3fe05b171e05f777dba6553c3fad185592b72774'
    def frozen(name):
        text = subprocess.check_output(['git', 'show', f'{ref}:app/services/{name}.py'], text=True)
        module = types.ModuleType('app.services.frozen_' + name); module.__package__ = 'app.services'
        exec(compile(text, 'frozen-' + name, 'exec'), module.__dict__); return module
    old = frozen('studio_timeline_render'); schema = frozen('studio_timeline_schema')
    data = cpu_video(tmp_path / 'original.mp4'); pin = {'id': 'video', 'kind': 'ASSET', 'asset_kind': 'video', 'version': 1, 'digest': hashlib.sha256(data).hexdigest()}
    def guard(snapshot): return {'snapshot': deepcopy(pin), 'data': data, 'row': {'id': 'video', 'kind': 'video', 'version': 1, 'sha256': pin['digest']}}
    proofs = []
    for version in (1, 2):
        value = timeline(pin)
        if version == 1: value.pop('schema_version')
        old_normal = schema.normalize_timeline_v2(value) if version == 2 else old.normalize_studio_timeline(value)
        normal = normalize_studio_timeline(value)
        assert old_normal == normal and old.timeline_digest(old_normal) == timeline_digest(normal)
        before, m1 = old.render_studio_timeline(value, source_guard=guard, guard=lambda: None, max_bytes=CAP)
        after, m2 = render_studio_timeline(value, source_guard=guard, guard=lambda: None, max_bytes=CAP)
        assert before == after and m1 == m2
        proofs.append({'schema': version, 'bytes': len(after), 'sha256': hashlib.sha256(after).hexdigest(), 'timeline_digest': timeline_digest(normal)})
    (tmp_path / 'legacy-byte-proof.json').write_text(json.dumps({'baseline_commit': ref, 'outputs': proofs}, indent=2))


@pytest.mark.file_backend_only
def test_color_preserves_transparent_source_alpha_before_composite(tmp_path):
    def rgba_png():
        def chunk(kind, data): return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        scan = b'\0' + bytes((240, 32, 32, 0)) * 32 + bytes((240, 32, 32, 255)) * 32
        return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 64, 64, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(scan * 64)) + chunk(b'IEND', b'')
    assets = {}
    for identity, kind, data in [('blue', 'video', cpu_video(tmp_path / 'blue.mp4')), ('alpha', 'image', rgba_png())]:
        pin = {'id': identity, 'kind': 'ASSET', 'asset_kind': kind, 'version': 1, 'digest': hashlib.sha256(data).hexdigest()}
        assets[identity] = {'snapshot': pin, 'data': data, 'row': {'id': identity, 'kind': kind, 'version': 1, 'sha256': pin['digest']}}
    value = timeline(assets['blue']['snapshot'])
    upper = deepcopy(value['tracks'][0]); upper.update(id='upper', order=1)
    upper['clips'][0].update(id='overlay', source_snapshot=assets['alpha']['snapshot'], opacity=.5,
        color_adjustment={**NEUTRAL, 'saturation': 0})
    value['tracks'].append(upper)
    data, _ = render_studio_timeline(value, source_guard=lambda pin: deepcopy(assets[pin['id']]), guard=lambda: None, max_bytes=CAP)
    proof = decode(data, tmp_path / 'alpha-composite.mp4')
    transparent, opaque = proof['rgb_samples']
    assert transparent[2] > 240 and transparent[0] < 10 and transparent[1] < 10
    assert opaque[0] > 25 and abs(opaque[0] - opaque[1]) <= 6 and opaque[2] > opaque[0] + 80


@pytest.mark.file_backend_only
@pytest.mark.parametrize('colored', [False, True])
def test_real_cross_dissolve_restores_cfr_and_blends_actual_frames(colored, tmp_path):
    assets = {}
    for identity, data in [('left', pixels_png()), ('right', pixels_png(reverse=True))]:
        pin = {'id': identity, 'kind': 'ASSET', 'asset_kind': 'image', 'version': 1, 'digest': hashlib.sha256(data).hexdigest()}
        assets[identity] = {'snapshot': pin, 'data': data, 'row': {'id': identity, 'kind': 'image', 'version': 1, 'sha256': pin['digest']}}
    value = timeline(assets['left']['snapshot']); value['duration_ms'] = 1400
    left = clip(value); left.update(out_ms=800, transition_out={'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'right', 'duration_ms': 200})
    right = deepcopy(left); right.pop('transition_out'); right.update(id='right', start_ms=600, source_snapshot=assets['right']['snapshot'])
    if colored:
        left['color_adjustment'] = {**NEUTRAL, 'brightness': .2}
        right['color_adjustment'] = {**NEUTRAL, 'saturation': 0}
    value['tracks'][0]['clips'].append(right)
    output, measured = render_studio_timeline(value, source_guard=lambda pin: deepcopy(assets[pin['id']]), guard=lambda: None, max_bytes=CAP)
    assert measured['transition_windows'][0]['start_ms'] == 600
    assert measured['video_transition_policy'] == 'PREMULTIPLIED_ALPHA_LINEAR_CROSS_DISSOLVE'
    samples = [decode(output, tmp_path / f'dissolve-{time}.mp4', time)['rgb_samples'][0] for time in (0, 700, 1000)]
    assert samples[0] != samples[2]
    for channel in range(3): assert samples[1][channel] == pytest.approx((samples[0][channel] + samples[2][channel]) / 2, abs=8)
    (tmp_path / 'dissolve-proof.json').write_text(json.dumps({'colored': colored, 'rgb_start_mid_end': samples, 'sha256': hashlib.sha256(output).hexdigest()}, indent=2))


@pytest.mark.file_backend_only
def test_color_otio_exact_studio_metadata_roundtrip_and_explicit_native_loss():
    from app.services.studio_timeline_exchange import studio_timeline_to_exchange, exchange_to_studio_timeline
    value = apply_timeline_edits(timeline(), change(ADJUSTED))
    exported = studio_timeline_to_exchange(value, title='Basic color transfer')
    assert {'path': 'tracks[0].clips[0]', 'code': 'BASIC_COLOR_NOT_NATIVE_NLE_PRESERVED_IN_STUDIO_METADATA', 'severity': 'LOSS'} in exported['report']
    restored = exchange_to_studio_timeline(exported['document'], media_bindings=exported['media_bindings'], canvas={})
    assert restored['timeline'] == value
    changed = deepcopy(exported['document']); changed['tracks'][0]['name'] = 'Native edit'
    native = exchange_to_studio_timeline(changed, media_bindings=exported['media_bindings'], canvas={})
    assert 'color_adjustment' not in clip(native['timeline'])
    assert any(row['code'] == 'STUDIO_METADATA_STALE_AFTER_NATIVE_EDIT_NOT_RESTORED' for row in native['report'])
