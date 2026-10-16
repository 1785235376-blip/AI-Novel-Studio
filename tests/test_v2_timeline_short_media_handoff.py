"""Actual mounted frontend handoff -> original File Timeline -> native CPU bytes.

The Node subprocess uses only installed frontend test dependencies. Real media,
source receipts and persisted results come from the existing owner fixtures.
"""
import json
import os
from pathlib import Path
import subprocess
from copy import deepcopy
import shutil

import pytest

from test_v2_independent_workspace import rig, reopened, import_asset
from test_v2_audio_editing_pipeline import editing, trimmed, production, measured_output, audio_insert, source
from test_v2_audio_wav_controls import action, command


def mounted_handoff(tmp_path, asset, receipt, timeline, manual_range=None):
    root = Path(__file__).resolve().parents[1]
    source, output = tmp_path / 'handoff-input.json', tmp_path / 'handoff-output.json'
    source.write_text(json.dumps({'asset': asset, 'receipt': receipt,
        'draft': {'title': 'Actual short media handoff', 'timeline': timeline}, 'output': str(output), 'manual_range': manual_range}))
    command = ['node', 'node_modules/vitest/vitest.mjs', 'run',
        'src/creative/StudioTimelineShortMedia.bridge.test.tsx', '--no-cache', '--maxWorkers=1', '--minWorkers=1']
    result = subprocess.run(command, cwd=root / 'frontend', env={**os.environ, 'STUDIO_SHORT_MEDIA_HANDOFF_CASE': str(source)},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    (tmp_path / 'mounted-handoff.log').write_text(result.stdout)
    assert result.returncode == 0, result.stdout
    return json.loads(output.read_text())


def test_actual_short_flac_handoff_renders_reviews_and_reopens(editing, tmp_path):
    e = editing; asset, receipt = trimmed(e)
    assert receipt['media_measurement']['duration_ms'] == 800
    draft = mounted_handoff(tmp_path, asset, receipt, e.timeline['timeline'])
    assert draft['timeline']['tracks'][-1]['clips'][0]['out_ms'] == 800
    render_and_reopen(e, draft, tmp_path)


def render_and_reopen(e, draft, tmp_path):
    row = e.production.timeline_save(e.nid, e.scope, e.actor, None, {'expected_version': 0, **draft}, lambda: None)
    job = e.production.timeline_render(e.nid, e.scope, e.actor, row['id'], {'expected_version': row['version'],
        'reviewed_timeline_digest': row['timeline_digest'], 'request_id': 'actual-short-handoff'}, lambda: None)
    # RED before the fix: the real renderer measures the 800 ms source and
    # rejects the mounted handoff's fabricated 1000 ms out-point.
    assert job['status'] == 'SUCCEEDED', {'job': job, 'handed_clip': draft['timeline']['tracks'][-1]['clips'][0]}
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    proof = measured_output(data, tmp_path / 'actual-composed.mp4')
    assert proof['output_sha256'] == job['output_candidate']['digest']
    approved = e.production.review(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job, True), lambda: None)
    fresh = reopened(e); restored = production(e, fresh)
    assert restored.timeline_get(e.nid, e.scope, e.actor, row['id'], lambda: None) == row
    assert restored.get(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)['status'] == 'APPROVED'
    assert fresh.asset(e.nid, e.scope, approved['output_candidate']['id'])['version'] == 2


def test_actual_short_mp3_handoff_renders_reviews_and_reopens(editing, tmp_path):
    e = editing
    value = command(source(e.audio_source), in_ms=100, out_ms=800, output_format='MP3', sample_rate=22050, channels=1)
    value['audio_profile'] = 'studio-audio-mp3/1'
    preview = e.production.preview(e.nid, e.scope, e.actor, value, lambda: None)[0]
    queued = e.production.create(e.nid, e.scope, e.actor, {'command': value, 'reviewed_preview_digest': preview['preview_digest']}, lambda: None)
    ready = e.production.execute(e.nid, e.scope, e.actor, 'audio', queued['id'], action(queued), lambda: None)
    receipt = e.production.review(e.nid, e.scope, e.actor, 'audio', ready['id'], action(ready, True), lambda: None)
    asset = e.service.asset(e.nid, e.scope, receipt['output_candidate']['id'])
    assert receipt['media_measurement']['duration_ms'] == 700 and asset['media_type'] == 'audio/mpeg'
    draft = mounted_handoff(tmp_path, asset, receipt, e.timeline['timeline'])
    assert draft['timeline']['tracks'][-1]['clips'][0]['out_ms'] == 700
    render_and_reopen(e, draft, tmp_path)


@pytest.mark.parametrize('known_output', [True, False])
def test_actual_short_video_handoff_uses_exact_receipt_or_explicit_unknown_range(editing, tmp_path, known_output):
    e = editing; audio, _ = trimmed(e)
    baseline = deepcopy(e.timeline['timeline'])
    baseline['tracks'].append(audio_insert(audio)[0]['track'])
    baseline['tracks'][-1]['clips'].append(audio_insert(audio)[1]['clip'])
    if known_output:
        short = deepcopy(baseline); short['duration_ms'] = 400
        for track in short['tracks']:
            for clip in track['clips']: clip['out_ms'] = 400
        row = e.production.timeline_save(e.nid, e.scope, e.actor, None,
            {'expected_version': 0, 'title': 'Short approved video', 'timeline': short}, lambda: None)
        rendered = e.production.timeline_render(e.nid, e.scope, e.actor, row['id'], {'expected_version': row['version'],
            'reviewed_timeline_digest': row['timeline_digest'], 'request_id': 'short-video-source'}, lambda: None)
        assert rendered['status'] == 'SUCCEEDED', rendered
        receipt = e.production.review(e.nid, e.scope, e.actor, 'timeline', rendered['id'], action(rendered, True), lambda: None)
        asset = e.service.asset(e.nid, e.scope, receipt['output_candidate']['id'])
        assert receipt['media_measurement']['duration_ms'] == 400
    else:
        from app.services.studio_timeline_export import run_guarded_process
        path = tmp_path / 'short-import.mp4'
        run_guarded_process([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1', '-f', 'lavfi',
            '-i', 'color=c=blue:s=64x64:r=10:d=0.4', '-an', '-c:v', 'mpeg4', '-threads', '1', '-y', str(path)],
            cwd=tmp_path, guard=lambda: None, timeout=20)
        asset = import_asset(e, data=path.read_bytes(), filename='short-import.mp4', kind='video'); receipt = None
    draft = mounted_handoff(tmp_path, asset, receipt, baseline, None if known_output else {'in_ms': 0, 'out_ms': 400})
    assert draft['timeline']['tracks'][-1]['clips'][0]['out_ms'] == 400
    render_and_reopen(e, draft, tmp_path)
