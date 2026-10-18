"""Closed global caption styling on original Timeline; real CPU pixel evidence."""
from copy import deepcopy
import hashlib
import json
import shutil
import subprocess
import types

import pytest

from app.experimental.common import StaleSourceError
from app.services.studio_timeline_caption_style import normalize_caption_style, compile_caption_style
from app.services.studio_timeline_edit import apply_timeline_edits
from app.services.studio_timeline_render import normalize_studio_timeline, render_studio_timeline, timeline_digest
from app.services.studio_timeline_export import run_guarded_process
from app.services.studio_timeline_subtitles import export_subtitles, import_subtitles
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import production, source, edit_body, cpu_video
from test_v2_audio_wav_controls import action

STYLE = {'font_size': 24, 'primary_color': '#FF0000', 'alignment': 'BOTTOM_CENTER', 'outline_width': 1}
CAP = 25 * 1024 * 1024


def timeline(pin=None):
    pin = pin or {'id': 'source', 'kind': 'ASSET', 'asset_kind': 'video', 'version': 1, 'digest': 'a' * 64}
    return {'schema_version': 2, 'duration_ms': 1000, 'width': 320, 'height': 180, 'fps': 10,
            'tracks': [{'id': 'picture', 'kind': 'VIDEO', 'order': 0, 'clips': [
                {'id': 'blue', 'source_snapshot': pin, 'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]}],
            'captions': [{'start_ms': 200, 'end_ms': 800, 'text': 'STUDIO'}]}


def change(style): return [{'op': 'canvas.update', 'changes': {'caption_style': style}}]
def reviewed(row): return {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest']}


@pytest.mark.parametrize('bad', [None, {}, [], '', {**STYLE, 'font': '/etc/passwd'},
    {**STYLE, 'font_size': True}, {**STYLE, 'font_size': 7}, {**STYLE, 'font_size': 73},
    {**STYLE, 'font_size': 24.0}, {**STYLE, 'font_size': float('nan')},
    {**STYLE, 'outline_width': -1}, {**STYLE, 'outline_width': 5}, {**STYLE, 'outline_width': False},
    {**STYLE, 'primary_color': '#FFFFFF,FontName=evil'}, {**STYLE, 'primary_color': '#FFFFFF\n'},
    {**STYLE, 'primary_color': '&HFFFFFF'}, {**STYLE, 'alignment': 8},
    {**STYLE, 'alignment': "TOP_CENTER';movie=/etc/passwd"}])
def test_closed_caption_style_rejects_malformed_saved_values(bad):
    with pytest.raises(ValueError): normalize_studio_timeline({**timeline(), 'caption_style': bad})


def test_style_edit_reset_schema_boundaries_text_safety_and_atomic_batch():
    original = normalize_studio_timeline(timeline())
    changed = apply_timeline_edits(original, change({**STYLE, 'primary_color': '#ff0000'}))
    assert changed['caption_style'] == STYLE and 'caption_style' not in original
    assert apply_timeline_edits(changed, change(None)) == original
    assert compile_caption_style(STYLE) == 'FontSize=24,PrimaryColour=&H000000FF,Alignment=2,Outline=1'
    assert 'Alignment=6' in compile_caption_style({**STYLE, 'alignment': 'TOP_CENTER'})
    for size in (8, 72): assert normalize_caption_style({**STYLE, 'font_size': size})['font_size'] == size
    legacy = timeline(); legacy.pop('schema_version')
    for style in (STYLE, None):
        with pytest.raises(ValueError): apply_timeline_edits(legacy, change(style))
        with pytest.raises(ValueError): normalize_studio_timeline({**legacy, 'caption_style': style})
    upgraded = apply_timeline_edits(legacy, [{'op': 'canvas.update', 'changes': {'schema_version': 2}}, *change(STYLE)])
    assert upgraded['caption_style'] == STYLE
    audio = {'schema_version': 3, 'media_kind': 'AUDIO', 'duration_ms': 1000,
             'tracks': [{'id': 'audio', 'kind': 'AUDIO', 'order': 0, 'clips': [
                 {'id': 'audio', 'source_snapshot': {**original['tracks'][0]['clips'][0]['source_snapshot'], 'asset_kind': 'audio'},
                  'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]}]}
    for style in (STYLE, None):
        with pytest.raises(ValueError): apply_timeline_edits(audio, change(style))
        with pytest.raises(ValueError): normalize_studio_timeline({**audio, 'caption_style': style})
    for text in ('{\\an8}STUDIO', '<b>STUDIO</b>', 'STUDIO\\Nnext', 'STUDIO\n\nnext', '00 --> 01', '\x00'):
        with pytest.raises(ValueError): normalize_studio_timeline({**changed, 'captions': [{'start_ms': 0, 'end_ms': 500, 'text': text}]})
    with pytest.raises(ValueError): apply_timeline_edits(original, [*change(STYLE), *change({**STYLE, 'filter': 'movie=x'})])
    assert 'caption_style' not in original
    locked = deepcopy(original); locked['tracks'][0]['locked'] = True
    assert apply_timeline_edits(locked, change(STYLE))['caption_style'] == STYLE  # Captions are independent of media-track locks.


def decode(data, path):
    path.write_bytes(data); target = path.with_suffix('.rgb')
    run_guarded_process([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:v:0', '-frames:v', '10',
        '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-threads', '1', '-y', str(target)],
        cwd=path.parent, guard=lambda: None, timeout=20)
    raw = target.read_bytes(); assert len(raw) == 320 * 180 * 3 * 10
    def proof(frame):
        pixels = raw[frame * 320 * 180 * 3:(frame + 1) * 320 * 180 * 3]
        red, black = [], []
        for i in range(0, len(pixels), 3):
            r, g, b = pixels[i:i + 3]; point = ((i // 3) % 320, (i // 3) // 320)
            if r > 100 and r > 2 * g and r > 2 * b: red.append(point)
            if 70 <= point[0] < 250 and max(r, g, b) < 45: black.append(point)  # Exclude aspect-fit pillarboxes.
        return {'red_pixels': len(red), 'black_pixels': len(black),
                'red_bounds': [min(p[0] for p in red), min(p[1] for p in red), max(p[0] for p in red), max(p[1] for p in red)] if red else None}
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'frames': {str(frame): proof(frame) for frame in (0, 5, 9)}}


@pytest.mark.file_backend_only
def test_real_cpu_style_controls_timing_and_frozen_legacy_render(tmp_path):
    data = cpu_video(tmp_path / 'blue.mp4'); pin = {'id': 'source', 'kind': 'ASSET', 'asset_kind': 'video', 'version': 1, 'digest': hashlib.sha256(data).hexdigest()}
    def guard(snapshot): return {'snapshot': pin, 'data': data, 'row': {'id': 'source', 'kind': 'video', 'version': 1, 'sha256': pin['digest']}}
    def render(style, name):
        value = timeline(pin)
        if style is not None: value['caption_style'] = style
        output, _ = render_studio_timeline(value, source_guard=guard, guard=lambda: None, max_bytes=CAP)
        return decode(output, tmp_path / (name + '.mp4'))
    proofs = {'bottom': render(STYLE, 'bottom'), 'top': render({**STYLE, 'alignment': 'TOP_CENTER'}, 'top'),
              'large': render({**STYLE, 'font_size': 48}, 'large'), 'outlined': render({**STYLE, 'outline_width': 4}, 'outlined'),
              'white': render({**STYLE, 'primary_color': '#FFFFFF'}, 'white')}
    for name in ('bottom', 'top', 'large', 'outlined'):
        frames = proofs[name]['frames']; assert frames['5']['red_pixels'] > 10
        assert frames['0']['red_pixels'] == frames['9']['red_pixels'] == 0
        assert frames['0']['black_pixels'] == frames['9']['black_pixels'] == 0
    bottom, top, large, outlined = [proofs[key]['frames']['5'] for key in ('bottom', 'top', 'large', 'outlined')]
    assert top['red_bounds'][3] < 90 < bottom['red_bounds'][1]
    assert large['red_pixels'] > bottom['red_pixels'] * 2
    assert outlined['black_pixels'] > bottom['black_pixels'] * 2
    assert proofs['white']['frames']['5']['red_pixels'] == 0
    ref = '501ff11b'
    def frozen(name):
        code = subprocess.check_output(['git', 'show', f'{ref}:app/services/{name}.py'], text=True)
        module = types.ModuleType('app.services.frozen_' + name); module.__package__ = 'app.services'
        exec(compile(code, 'frozen-' + name, 'exec'), module.__dict__); return module
    old, schema = frozen('studio_timeline_render'), frozen('studio_timeline_schema')
    proofs['legacy'] = []
    for version in (1, 2):
        value = timeline(pin)
        if version == 1: value.pop('schema_version')
        normal = normalize_studio_timeline(value)
        before_normal = old.normalize_studio_timeline(value) if version == 1 else schema.normalize_timeline_v2(value)
        assert normal == before_normal and timeline_digest(normal) == old.timeline_digest(before_normal)
        before, m1 = old.render_studio_timeline(value, source_guard=guard, guard=lambda: None, max_bytes=CAP)
        after, m2 = render_studio_timeline(value, source_guard=guard, guard=lambda: None, max_bytes=CAP)
        assert before == after and m1 == m2
        proofs['legacy'].append({'schema': version, 'sha256': hashlib.sha256(after).hexdigest(), 'timeline_digest': timeline_digest(normal)})
    (tmp_path / 'caption-style-proof.json').write_text(json.dumps(proofs, indent=2))


@pytest.fixture
def caption_timeline(rig, tmp_path):
    e = rig; e.service.activate(e.nid, e.scope, e.actor)
    e.video = import_asset(e, data=cpu_video(tmp_path / 'blue.mp4'), filename='caption-blue.mp4', kind='video')
    e.production = production(e)
    e.row = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'Caption style', 'timeline': timeline(source(e.video))}, lambda: None)
    return e


def test_style_original_lifecycle_review_cache_and_sidecar_loss(caption_timeline, tmp_path):
    e = caption_timeline; initial = e.row
    before = e.production.timeline_playback_preview(e.nid, e.scope, e.actor, initial['id'], reviewed(initial), lambda: None)
    body = edit_body(initial, change(STYLE), 'caption-style-edit')
    edited = e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], body, lambda: None)
    assert e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], body, lambda: None) == edited
    with pytest.raises(StaleSourceError): e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], edit_body(initial, change(None), 'stale'), lambda: None)
    with pytest.raises(StaleSourceError): e.production.timeline_playback_build(e.nid, e.scope, e.actor, initial['id'], {**reviewed(initial), 'reviewed_playback_digest': before['playback_digest']}, lambda: None)
    saved = e.production.timeline_save(e.nid, e.scope, e.actor, initial['id'],
        {'expected_version': edited['version'], 'title': edited['title'], 'timeline': edited['timeline']}, lambda: None)
    fresh = production(e, reopened(e)); assert fresh.timeline_get(e.nid, e.scope, e.actor, saved['id'], lambda: None) == saved
    preview = fresh.timeline_playback_preview(e.nid, e.scope, e.actor, saved['id'], reviewed(saved), lambda: None)
    assert preview['playback_digest'] != before['playback_digest'] and preview['cache_state'] == 'MISSING'
    build = {**reviewed(saved), 'reviewed_playback_digest': preview['playback_digest']}
    job = fresh.timeline_playback_build(e.nid, e.scope, e.actor, saved['id'], build, lambda: None)['job']
    assert job['status'] == 'SUCCEEDED', job
    assert fresh.timeline_playback_build(e.nid, e.scope, e.actor, saved['id'], build, lambda: None)['job']['id'] == job['id']
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, job['output_candidate']['id'])
    _, data = fresh.candidate(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    proof = decode(data, tmp_path / 'saved-style.mp4'); assert proof['frames']['5']['red_pixels'] > 10
    attested = fresh.timeline_playback_attest(e.nid, e.scope, e.actor, saved['id'], {**build, 'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}, lambda: None)
    assert attested['sha256'] == proof['sha256']
    assert fresh.review(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job, True), lambda: None)['status'] == 'APPROVED'
    assert reopened(e).asset(e.nid, e.scope, job['output_candidate']['id'])['sha256'] == proof['sha256']
    for format in ('SRT', 'VTT'):
        request = {**reviewed(saved), 'direction': 'EXPORT', 'format': format}
        transfer = fresh.timeline_transfer_preview(e.nid, e.scope, e.actor, saved['id'], request, lambda: None)
        assert transfer['requires_loss_acknowledgment'] and transfer['loss_report'] == [
            {'path': 'caption_style', 'code': 'CAPTION_STYLE_NOT_PRESERVED_IN_PLAIN_SIDECAR', 'severity': 'LOSS'}]
        download = {**request, 'reviewed_preview_digest': transfer['preview_digest']}
        with pytest.raises(ValueError, match='LOSS_REPORT'): fresh.timeline_transfer_attachment(e.nid, e.scope, e.actor, saved['id'], download, lambda: None)
        sidecar, _, _ = fresh.timeline_transfer_attachment(e.nid, e.scope, e.actor, saved['id'], {**download, 'acknowledge_losses': True}, lambda: None)
        assert sidecar == export_subtitles(initial['timeline'], format)
        assert import_subtitles(saved['timeline'], sidecar.decode(), format)['caption_style'] == STYLE
    history = fresh.timeline_history(e.nid, e.scope, e.actor, saved['id'], lambda: None)['items']
    assert next(row for row in history if row['version'] == edited['version'])['timeline']['caption_style'] == STYLE
    restored = fresh.timeline_restore(e.nid, e.scope, e.actor, saved['id'], {**reviewed(saved), 'restore_version': initial['version'], 'restore_digest': initial['timeline_digest']}, lambda: None)
    assert restored['timeline'] == initial['timeline'] and 'caption_style' not in restored['timeline']
    (tmp_path / 'saved-caption-proof.json').write_text(json.dumps(proof, indent=2))


@pytest.mark.file_backend_only
def test_style_otio_metadata_exact_and_native_edit_loss():
    from app.services.studio_timeline_exchange import studio_timeline_to_exchange, exchange_to_studio_timeline
    value = apply_timeline_edits(timeline(), change(STYLE))
    exported = studio_timeline_to_exchange(value, title='Caption style')
    assert {'path': 'caption_style', 'code': 'CAPTION_STYLE_NOT_NATIVE_NLE_PRESERVED_IN_STUDIO_METADATA', 'severity': 'LOSS'} in exported['report']
    assert exchange_to_studio_timeline(exported['document'], media_bindings=exported['media_bindings'], canvas={})['timeline'] == value
    native = deepcopy(exported['document']); native['tracks'][0]['name'] = 'Changed'
    restored = exchange_to_studio_timeline(native, media_bindings=exported['media_bindings'], canvas={})
    assert 'caption_style' not in restored['timeline'] and any(row['code'] == 'STUDIO_METADATA_STALE_AFTER_NATIVE_EDIT_NOT_RESTORED' for row in restored['report'])


def test_style_invalid_batch_and_native_source_change_publish_nothing(caption_timeline, monkeypatch):
    from app.services import studio_timeline_export as native
    e = caption_timeline; initial = e.row
    with pytest.raises(ValueError): e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'],
        edit_body(initial, [*change(STYLE), *change({**STYLE, 'font_name': '/host/font'})]), lambda: None)
    assert e.production.timeline_get(e.nid, e.scope, e.actor, initial['id'], lambda: None) == initial
    assert not e.production.timeline_history(e.nid, e.scope, e.actor, initial['id'], lambda: None)['items']
    e.row = e.production.timeline_edit(e.nid, e.scope, e.actor, initial['id'], edit_body(initial, change(STYLE)), lambda: None)
    original = native.run_guarded_process; observed = []
    def changed(args, **kwargs):
        result = original(args, **kwargs)
        if '-filter_complex' in args and str(args[-1]).endswith('timeline.mp4'):
            observed.append(args[args.index('-filter_complex') + 1])
            with e.service._asset_scope(e.nid, e.scope): e.assets.update_metadata(e.video['id'], {'scene_id': 'changed'}, expected_version=e.video['version'])
        return result
    monkeypatch.setattr(native, 'run_guarded_process', changed)
    job = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], {**reviewed(e.row), 'request_id': 'style-source-change'}, lambda: None)
    assert observed and ":force_style='FontSize=24,PrimaryColour=&H000000FF,Alignment=2,Outline=1'" in observed[0]
    assert job['status'] == 'FAILED' and job['output_candidate'] is None
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1


def test_style_unknown_recovers_original_output_without_render_replay(caption_timeline, monkeypatch):
    e = caption_timeline; e.row = e.production.timeline_edit(e.nid, e.scope, e.actor, e.row['id'], edit_body(e.row, change(STYLE)), lambda: None)
    original = e.assets.create; published = []
    def interrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        if str(args[1]).startswith('studio-timeline-'):
            published.append(result); raise OSError('owned post-publication interruption')
        return result
    monkeypatch.setattr(e.assets, 'create', interrupted)
    body = {**reviewed(e.row), 'request_id': 'caption-style-unknown'}
    job = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], body, lambda: None)
    assert job['status'] == 'UNKNOWN' and len(published) == 1
    assert e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], body, lambda: None)['id'] == job['id']
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job), lambda: None)
    assert recovered['status'] == 'SUCCEEDED' and len(published) == 1
    assert e.production.review(e.nid, e.scope, e.actor, 'timeline', recovered['id'], action(recovered, True), lambda: None)['status'] == 'APPROVED'
