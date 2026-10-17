"""Trim parity and explicit Save/reopen through original File timeline owners.

No render/provider/browser/HTTP work. Save checks source identity and content;
measured source-duration bounds remain the renderer's responsibility.
"""
from copy import deepcopy
import io
from types import SimpleNamespace
import wave

import pytest

from app.asset_providers import AssetProviderRegistry
from app.experimental.common import StaleSourceError
from app.services.studio_timeline_edit import apply_timeline_edits
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_discovered_image_production import owner
from test_v2_independent_workspace import rig, import_asset, reopened

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('rig', ['file'], indirect=True)]


def reference(asset):
    return {'id': asset['id'], 'kind': 'ASSET', 'asset_kind': asset['kind'],
            'version': asset['version'], 'digest': asset['sha256']}


def clip(identity, source, start, end, **extra):
    return {'id': identity, 'source_snapshot': deepcopy(source), 'start_ms': start,
            'in_ms': 0, 'out_ms': end, **extra}


def operation(out_ms=1500, ripple=True, identity='target', in_ms=0):
    return {'op': 'clip.trim', 'clip_id': identity, 'in_ms': in_ms,
            'out_ms': out_ms, 'ripple': ripple}


@pytest.fixture
def trim_env(rig, monkeypatch):
    production = owner(AssetProviderRegistry(), monkeypatch, rig)
    image = import_asset(rig)
    data = io.BytesIO()
    with wave.open(data, 'wb') as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(8000)
        writer.writeframes(b'\x00\x00' * 48000)
    audio = import_asset(rig, data=data.getvalue(), filename='trim.wav', kind='audio')
    visual, sound = reference(image), reference(audio)
    timeline = {'schema_version': 2, 'duration_ms': 10000, 'width': 640, 'height': 360, 'fps': 24,
        'tracks': [
            {'id': 'visual', 'kind': 'VIDEO', 'order': 0, 'clips': [clip('still', visual, 0, 2000)]},
            {'id': 'audio', 'kind': 'AUDIO', 'order': 1, 'clips': [
                clip('target', sound, 1000, 3000, speed_num=3, speed_den=2),
                clip('before-boundary', sound, 2999, 100),
                clip('at-boundary', sound, 3000, 300),
                clip('later', sound, 4500, 300)]},
            {'id': 'other', 'kind': 'AUDIO', 'order': 2, 'clips': [clip('untouched', sound, 3000, 300)]}],
        'captions': [{'start_ms': 3000, 'end_ms': 3500, 'text': 'Keep caption 中文🌙'}]}
    def save(timeline, current=None):
        return production.timeline_save(rig.nid, rig.scope, rig.actor, current['id'] if current else None,
            {'expected_version': current['version'] if current else 0, 'title': 'Explicit trim Save',
             'timeline': timeline}, lambda: None)
    def get(current, fresh=False):
        service = owner(AssetProviderRegistry(), monkeypatch,
            SimpleNamespace(**{**vars(rig), 'service': reopened(rig)})) if fresh else production
        return service.timeline_get(rig.nid, rig.scope, rig.actor, current['id'], lambda: None)
    return SimpleNamespace(rig=rig, production=production, timeline=timeline, save=save, get=get)


def by_id(timeline):
    return {c['id']: c for track in timeline['tracks'] for c in track['clips']}


def history(e, row):
    return e.production.timeline_history(e.rig.nid, e.rig.scope, e.rig.actor, row['id'], lambda: None)


@pytest.mark.parametrize('out_ms,ripple,delta', [(1500, True, -1000), (4500, True, 1000),
                                               (1500, False, 0), (4500, False, 0)])
def test_rational_trim_save_reopen_has_exact_same_track_boundary_and_one_revision(trim_env, out_ms, ripple, delta):
    e = trim_env; original = e.save(e.timeline); before = deepcopy(original['timeline'])
    candidate = apply_timeline_edits(before, [operation(out_ms, ripple)])
    assert before == original['timeline'] and e.get(original) == original
    old, new = by_id(before), by_id(candidate)
    assert new['target'] == {**old['target'], 'out_ms': out_ms}
    assert new['before-boundary'] == old['before-boundary']
    for name in ('at-boundary', 'later'):
        assert new[name] == {**old[name], 'start_ms': old[name]['start_ms'] + delta}
    assert candidate['tracks'][0] == before['tracks'][0]
    assert candidate['tracks'][2] == before['tracks'][2]
    assert candidate['captions'] == before['captions']
    assert candidate['duration_ms'] == before['duration_ms']
    assert {k: c['source_snapshot'] for k, c in new.items()} == {k: c['source_snapshot'] for k, c in old.items()}
    saved = e.save(candidate, original)
    assert saved['version'] == original['version'] + 1 and saved['timeline'] == candidate
    assert e.get(saved, fresh=True) == saved
    assert [row['version'] for row in history(e, saved)['items']] == [1]
    with pytest.raises(CapabilityVersionConflict):
        e.save(candidate, original)
    assert e.get(saved, fresh=True) == saved
    assert len(e.rig.service.list_assets(e.rig.nid, e.rig.scope)['items']) == 2


def test_image_trim_preserves_zero_in_and_exact_pin_on_save_reopen(trim_env):
    e = trim_env; original = e.save(e.timeline)
    candidate = apply_timeline_edits(original['timeline'], [operation(1000, True, 'still')])
    saved = e.save(candidate, original)
    assert e.get(saved, fresh=True) == saved
    assert by_id(saved['timeline'])['still'] == {**by_id(original['timeline'])['still'], 'out_ms': 1000}


@pytest.mark.parametrize('case,error', [
    ('fractional', 'STUDIO_TIMELINE_EDIT_FRACTIONAL_MS'),
    ('still-in', 'STUDIO_TIMELINE_STILL_RANGE_INVALID'),
    ('fades', 'STUDIO_TIMELINE_FADE_RANGE_INVALID'),
    ('locked', 'STUDIO_TIMELINE_TRACK_LOCKED'),
    ('overlap', 'STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP'),
    ('transition', 'STUDIO_TIMELINE_TRANSITION_WINDOW_INVALID'),
    ('canvas', 'STUDIO_TIMELINE_CLIP_RANGE_INVALID'),
    ('boolean', 'STUDIO_TIMELINE_EDIT_BOOLEAN_INVALID'),
])
def test_rejected_original_trim_is_atomic_and_reopens_unchanged(trim_env, case, error):
    e = trim_env; timeline = deepcopy(e.timeline); op = operation()
    if case == 'fractional': op['out_ms'] = 1501
    if case == 'still-in': op = operation(1000, True, 'still', 1)
    if case == 'fades': timeline['tracks'][1]['clips'][0].update(fade_in_ms=600, fade_out_ms=600)
    if case == 'locked': timeline['tracks'][1]['locked'] = True
    if case in ('overlap', 'transition'):
        visual = timeline['tracks'][0]
        visual['clips'].append(clip('next-still', visual['clips'][0]['source_snapshot'],
                                    1800 if case == 'transition' else 2000, 2000))
        if case == 'transition':
            visual['clips'][0]['transition_out'] = {'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'next-still', 'duration_ms': 200}
        op = operation(1000 if case == 'transition' else 2500, case == 'transition', 'still')
    if case == 'canvas': op['out_ms'] = 15000
    if case == 'boolean': op['ripple'] = 1
    original = e.save(timeline); prior_history = history(e, original)
    with pytest.raises(ValueError, match=error):
        e.production.timeline_edit(e.rig.nid, e.rig.scope, e.rig.actor, original['id'],
            {'expected_version': original['version'], 'reviewed_timeline_digest': original['timeline_digest'],
             'request_id': 'reject-' + case, 'operations': [op]}, lambda: None)
    assert e.get(original, fresh=True) == original
    assert history(e, original) == prior_history


def test_save_rejects_changed_source_pin_without_rebinding_or_revision(trim_env):
    e = trim_env; original = e.save(e.timeline)
    candidate = apply_timeline_edits(original['timeline'], [operation()])
    # Change every occurrence coherently: reject at original asset ownership,
    # rather than the earlier same-document conflicting-snapshot schema check.
    for track in candidate['tracks']:
        for item in track['clips']:
            if item['source_snapshot']['asset_kind'] == 'audio':
                item['source_snapshot']['version'] += 1
    with pytest.raises(StaleSourceError, match='STUDIO_TIMELINE_SOURCE_CHANGED'):
        e.save(candidate, original)
    assert e.get(original, fresh=True) == original
    assert history(e, original)['items'] == []


def test_whole_document_save_cannot_bypass_original_track_lock(trim_env):
    e = trim_env; e.timeline['tracks'][1]['locked'] = True; original = e.save(e.timeline)
    candidate = deepcopy(original['timeline']); by_id(candidate)['target']['out_ms'] = 1500
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_TRACK_LOCKED'):
        e.save(candidate, original)
    assert e.get(original, fresh=True) == original
    assert history(e, original)['items'] == []


def test_save_checks_pins_but_does_not_claim_measured_source_duration_validation(trim_env):
    e = trim_env; original = e.save(e.timeline)
    # Imported WAV is exactly 6000 ms. At 3/2 speed, a 9000 ms source span
    # occupies 6000 ms and fits this canvas. Generic Save intentionally has
    # no decoded-duration check; this is NOT evidence that rendering succeeds.
    candidate = apply_timeline_edits(original['timeline'], [operation(9000, False)])
    saved = e.save(candidate, original)
    assert by_id(saved['timeline'])['target']['out_ms'] == 9000
    assert e.get(saved, fresh=True) == saved
