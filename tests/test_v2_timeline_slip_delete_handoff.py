"""Slip/delete candidates and explicit Save through original File owners.

No render/provider/browser/HTTP work. Generic Save validates source pins, not
measured media duration; the final test deliberately preserves that limitation.
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


def slip(offset, identity='target'):
    return {'op': 'clip.slip', 'clip_id': identity, 'offset_ms': offset}


def remove(identity='target', ripple=True):
    return {'op': 'clip.remove', 'clip_id': identity, 'ripple': ripple}


def by_id(timeline):
    return {c['id']: c for track in timeline['tracks'] for c in track['clips']}


@pytest.fixture
def edit_env(rig, monkeypatch):
    production = owner(AssetProviderRegistry(), monkeypatch, rig)
    image = import_asset(rig)
    data = io.BytesIO()
    with wave.open(data, 'wb') as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(8000)
        writer.writeframes(b'\x00\x00' * 48000)
    audio = import_asset(rig, data=data.getvalue(), filename='slip.wav', kind='audio')
    visual, sound = reference(image), reference(audio)
    timeline = {'schema_version': 2, 'duration_ms': 10000, 'width': 640, 'height': 360, 'fps': 24,
        'tracks': [
            {'id': 'visual', 'kind': 'VIDEO', 'order': 0, 'clips': [clip('still', visual, 0, 2000)]},
            {'id': 'audio', 'kind': 'AUDIO', 'order': 1, 'clips': [
                clip('target', sound, 1000, 3600, in_ms=600, speed_num=3, speed_den=2),
                clip('before-boundary', sound, 2999, 100),
                clip('at-boundary', sound, 3000, 300),
                clip('after-boundary', sound, 3001, 300),
                clip('gap', sound, 4500, 300)]},
            {'id': 'other', 'kind': 'AUDIO', 'order': 2, 'clips': [clip('untouched', sound, 3000, 300)]}],
        'captions': [{'start_ms': 3000, 'end_ms': 3500, 'text': 'Keep caption 中文🌙'}]}
    def save(value, current=None):
        return production.timeline_save(rig.nid, rig.scope, rig.actor, current['id'] if current else None,
            {'expected_version': current['version'] if current else 0,
             'title': 'Explicit slip/delete Save', 'timeline': value}, lambda: None)
    def get(current, fresh=False):
        service = owner(AssetProviderRegistry(), monkeypatch,
            SimpleNamespace(**{**vars(rig), 'service': reopened(rig)})) if fresh else production
        return service.timeline_get(rig.nid, rig.scope, rig.actor, current['id'], lambda: None)
    return SimpleNamespace(rig=rig, production=production, timeline=timeline, save=save, get=get)


def history(e, row):
    return e.production.timeline_history(e.rig.nid, e.rig.scope, e.rig.actor, row['id'], lambda: None)


def asset_pins(e):
    return sorted((a['id'], a['version'], a['sha256'])
                  for a in e.rig.service.list_assets(e.rig.nid, e.rig.scope)['items'])


def assert_saved_once(e, original, candidate, pins):
    assert e.get(original, fresh=True) == original
    assert history(e, original)['items'] == []
    saved = e.save(candidate, original)
    assert saved['version'] == original['version'] + 1 and saved['timeline'] == candidate
    assert e.get(saved, fresh=True) == saved
    versions = history(e, saved)['items']
    assert [row['version'] for row in versions] == [1]
    assert versions[0]['timeline'] == original['timeline']
    with pytest.raises(CapabilityVersionConflict):
        e.save(candidate, original)
    assert e.get(saved, fresh=True) == saved
    assert history(e, saved)['items'] == versions
    assert asset_pins(e) == pins and len(pins) == 2


@pytest.mark.parametrize('offset', [500, -600, 1])
def test_signed_source_slip_preserves_rational_duration_and_explicit_save(edit_env, offset):
    e = edit_env; original = e.save(e.timeline); pins = asset_pins(e)
    before = deepcopy(original['timeline'])
    candidate = apply_timeline_edits(before, [slip(offset)])
    assert before == original['timeline']
    expected = deepcopy(before); target = by_id(expected)['target']
    target.update(in_ms=600 + offset, out_ms=3600 + offset)
    assert candidate == expected
    assert (target['out_ms'] - target['in_ms']) * target['speed_den'] // target['speed_num'] == 2000
    assert_saved_once(e, original, candidate, pins)


@pytest.mark.parametrize('ripple', [True, False])
def test_delete_exact_same_track_rendered_end_boundary_save_reopen(edit_env, ripple):
    e = edit_env; original = e.save(e.timeline); pins = asset_pins(e)
    before = deepcopy(original['timeline'])
    candidate = apply_timeline_edits(before, [remove(ripple=ripple)])
    expected = deepcopy(before); row = expected['tracks'][1]
    row['clips'] = [c for c in row['clips'] if c['id'] != 'target']
    if ripple:
        for item in row['clips']:
            if item['id'] in ('at-boundary', 'after-boundary', 'gap'):
                item['start_ms'] -= 2000
        row['clips'].sort(key=lambda c: (c['start_ms'], c['id']))
    assert before == original['timeline'] and candidate == expected
    assert by_id(candidate)['before-boundary']['start_ms'] == 2999
    assert_saved_once(e, original, candidate, pins)


def test_zero_slip_returns_detached_equal_candidate_without_implicit_save(edit_env):
    e = edit_env; original = e.save(e.timeline); pins = asset_pins(e)
    candidate = apply_timeline_edits(original['timeline'], [slip(0)])
    assert candidate == original['timeline'] and candidate is not original['timeline']
    by_id(candidate)['target']['in_ms'] = 123
    assert by_id(original['timeline'])['target']['in_ms'] == 600
    assert e.get(original, fresh=True) == original and history(e, original)['items'] == []
    assert asset_pins(e) == pins


@pytest.mark.parametrize('case,error', [
    ('negative-in', 'STUDIO_TIMELINE_INTEGER_INVALID'),
    ('overflow', 'STUDIO_TIMELINE_INTEGER_INVALID'),
    ('fractional', 'STUDIO_TIMELINE_EDIT_INTEGER_INVALID'),
    ('boolean-offset', 'STUDIO_TIMELINE_EDIT_INTEGER_INVALID'),
    ('image', 'STUDIO_TIMELINE_EDIT_STILL_SLIP_INVALID'),
    ('last-clip', 'STUDIO_TIMELINE_CLIP_LIMIT'),
    ('boolean-ripple', 'STUDIO_TIMELINE_EDIT_BOOLEAN_INVALID'),
    ('locked-slip', 'STUDIO_TIMELINE_TRACK_LOCKED'),
    ('locked-delete', 'STUDIO_TIMELINE_TRACK_LOCKED'),
    ('transition', 'STUDIO_TIMELINE_TRANSITION_WINDOW_INVALID'),
    ('overlap', 'STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP'),
])
def test_failed_batch_and_original_edit_leave_file_history_and_pins_unchanged(edit_env, case, error):
    e = edit_env; timeline = deepcopy(e.timeline)
    operations = {'negative-in': slip(-601), 'overflow': slip(36_000_000),
        'fractional': slip(0.5), 'boolean-offset': slip(True), 'image': slip(1, 'still'),
        'last-clip': remove('untouched'), 'boolean-ripple': remove(ripple=1),
        'locked-slip': slip(1), 'locked-delete': remove()}
    op = operations.get(case)
    if case.startswith('locked-'): timeline['tracks'][1]['locked'] = True
    if case in ('transition', 'overlap'):
        row = timeline['tracks'][0]; first = row['clips'][0]
        first['transition_out'] = {'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'second', 'duration_ms': 200}
        row['clips'] += [clip('second', first['source_snapshot'], 1800, 2000),
                         clip('third', first['source_snapshot'], 3800, 2000)]
        op = remove('second' if case == 'transition' else 'still')
    original = e.save(timeline); before = deepcopy(original['timeline']); pins = asset_pins(e)
    # A valid first edit must not survive a later failed operation in the batch.
    batch = [slip(1, 'untouched'), op]
    with pytest.raises(ValueError, match=error):
        apply_timeline_edits(before, batch)
    assert before == original['timeline']
    with pytest.raises(ValueError, match=error):
        e.production.timeline_edit(e.rig.nid, e.rig.scope, e.rig.actor, original['id'],
            {'expected_version': original['version'], 'reviewed_timeline_digest': original['timeline_digest'],
             'request_id': 'reject-' + case, 'operations': batch}, lambda: None)
    assert e.get(original, fresh=True) == original and history(e, original)['items'] == []
    assert asset_pins(e) == pins


@pytest.mark.parametrize('kind', ['slip', 'delete'])
def test_whole_document_save_cannot_bypass_original_track_lock(edit_env, kind):
    e = edit_env; e.timeline['tracks'][1]['locked'] = True; original = e.save(e.timeline)
    candidate = deepcopy(original['timeline']); candidate['tracks'][1]['locked'] = False
    candidate = apply_timeline_edits(candidate, [slip(500) if kind == 'slip' else remove()])
    candidate['tracks'][1]['locked'] = True
    pins = asset_pins(e)
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_TRACK_LOCKED'):
        e.save(candidate, original)
    assert e.get(original, fresh=True) == original and history(e, original)['items'] == []
    assert asset_pins(e) == pins


@pytest.mark.parametrize('kind', ['slip', 'delete'])
def test_save_rejects_changed_source_pin_without_rebinding_or_revision(edit_env, kind):
    e = edit_env; original = e.save(e.timeline); pins = asset_pins(e)
    candidate = apply_timeline_edits(original['timeline'], [slip(500) if kind == 'slip' else remove()])
    for item in by_id(candidate).values():
        if item['source_snapshot']['asset_kind'] == 'audio': item['source_snapshot']['version'] += 1
    with pytest.raises(StaleSourceError, match='STUDIO_TIMELINE_SOURCE_CHANGED'):
        e.save(candidate, original)
    assert e.get(original, fresh=True) == original and history(e, original)['items'] == []
    assert asset_pins(e) == pins


def test_save_checks_pins_without_claiming_measured_source_duration_validation(edit_env):
    e = edit_env; original = e.save(e.timeline); pins = asset_pins(e)
    # Imported WAV is exactly 6000 ms. Slip keeps rendered placement/duration
    # but out_ms=6600 exceeds measured source duration. This proves Save's
    # existing limitation only, and is explicitly NOT a successful render.
    candidate = apply_timeline_edits(original['timeline'], [slip(3000)])
    assert by_id(candidate)['target']['out_ms'] == 6600
    assert_saved_once(e, original, candidate, pins)
