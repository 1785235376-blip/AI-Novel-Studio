"""Exact time receipts through the pinned native parser, without NLE acceptance."""
import copy
import json
from fractions import Fraction

import pytest

from app.experimental.timeline_exchange import (
    NS, STUDIO_NS, fraction, rational, read_otio, seconds, semantic_document,
    summary, time_value, write_otio,
)
from app.services.studio_timeline_exchange import (
    exchange_to_studio_timeline, studio_timeline_to_exchange,
)


def document(*, speed=Fraction(2, 3), missing=False):
    rate = Fraction(30000, 1001)
    return {
        'name': 'Synthetic rational source range',
        'global_start_time': None,
        'tracks': [{'name': 'V1', 'kind': 'Video', 'items': [{
            'kind': 'Clip', 'name': 'trimmed',
            'start': time_value(Fraction(1, 3), rate),
            'duration': time_value(Fraction(13, 3), rate),
            'speed': rational(speed),
            'target_url': None if missing else 'media/inert-synthetic.mov',
        }]}],
    }


@pytest.mark.parametrize('speed', [Fraction(1), Fraction(2), Fraction(1, 2), Fraction(2, 3)])
def test_summary_source_out_uses_speed_without_changing_timeline_placement(speed):
    doc = document(speed=speed)
    item = doc['tracks'][0]['items'][0]
    doc['tracks'][0]['items'].append({
        'kind': 'Gap', 'name': 'tail', 'start': time_value(0), 'duration': time_value(1),
    })
    before = copy.deepcopy(doc)
    cuts = summary(doc)['tracks'][0]['cuts']
    assert fraction(cuts[0]['source_in_seconds']) == seconds(item['start'])
    assert fraction(cuts[0]['source_out_seconds']) == seconds(item['start']) + seconds(item['duration']) * speed
    assert fraction(cuts[0]['duration_seconds']) == seconds(item['duration'])
    assert fraction(cuts[1]['start_seconds']) == seconds(item['duration'])
    assert doc == before


@pytest.mark.parametrize('missing', [False, True])
def test_native_file_roundtrip_keeps_exact_declared_media_range(tmp_path, missing):
    pytest.importorskip('opentimelineio')
    doc = document(missing=missing)
    item = doc['tracks'][0]['items'][0]
    item['available_range'] = {
        'start': time_value(Fraction(1, 7), Fraction(30000, 1001)),
        'duration': time_value(Fraction(50, 3), Fraction(30000, 1001)),
    }
    before = copy.deepcopy(doc)
    output = tmp_path / 'exact-media-range.otio'
    output.write_bytes(write_otio(doc))
    restored, losses = read_otio(output.read_text(encoding='utf-8'))
    assert semantic_document(restored) == semantic_document(doc)
    assert not any(row['code'] == 'UNKNOWN_EXCHANGE_METADATA_NOT_REPRESENTED' for row in losses)
    assert write_otio(restored) == output.read_bytes()
    assert doc == before


def test_native_file_roundtrip_keeps_exact_global_start_time(tmp_path):
    pytest.importorskip('opentimelineio')
    doc = document()
    doc['global_start_time'] = time_value(Fraction(1, 3), Fraction(30000, 1001))
    output = tmp_path / 'exact-global-start.otio'
    output.write_bytes(write_otio(doc))
    restored, losses = read_otio(output.read_text(encoding='utf-8'))
    assert semantic_document(restored) == semantic_document(doc)
    assert not any(row['code'] == 'UNKNOWN_EXCHANGE_METADATA_NOT_REPRESENTED' for row in losses)


@pytest.mark.parametrize('target', ['global_start_time', 'available_start', 'available_duration'])
def test_new_exact_time_metadata_must_match_native_values(target):
    pytest.importorskip('opentimelineio')
    doc = document()
    doc['global_start_time'] = time_value(24)
    doc['tracks'][0]['items'][0]['available_range'] = {
        'start': time_value(0), 'duration': time_value(240),
    }
    raw = json.loads(write_otio(doc))
    if target == 'global_start_time':
        exact = raw['metadata'][NS]['global_start_time']
    else:
        ref = raw['tracks']['children'][0]['children'][0]['media_references']['DEFAULT_MEDIA']
        exact = ref['metadata'][NS]['start' if target == 'available_start' else 'duration']
    exact['frames']['numerator'] += 1
    with pytest.raises(ValueError, match='EXACT_TIME_METADATA_MISMATCH'):
        read_otio(json.dumps(raw))


def test_retimed_original_timeline_file_then_native_edit_retains_source_bounds(tmp_path):
    otio = pytest.importorskip('opentimelineio')
    from pathlib import Path
    capture = json.loads((Path(__file__).resolve().parents[1] /
        'frontend/src/creative/fixtures/phase6.capture.editing-pipeline.json').read_text(encoding='utf-8'))
    timeline = copy.deepcopy(capture['created']['timeline'])
    timeline['duration_ms'] = 4000
    clip = timeline['tracks'][0]['clips'][0]
    clip.update(in_ms=120, out_ms=2400, speed_num=2, speed_den=3)
    converted = studio_timeline_to_exchange(timeline, title='Synthetic retime edit')
    path = tmp_path / 'original-retimed.otio'
    path.write_bytes(write_otio(converted['document']))
    native = otio.core.deserialize_json_from_string(path.read_text(encoding='utf-8'))
    native.metadata.pop(STUDIO_NS)
    native.tracks[0][0].name = 'Externally renamed cut'
    path.write_text(otio.core.serialize_json_to_string(native), encoding='utf-8')
    decoded, _ = read_otio(path.read_text(encoding='utf-8'))
    restored = exchange_to_studio_timeline(decoded, media_bindings=converted['media_bindings'], canvas={})
    actual = restored['timeline']['tracks'][0]['clips'][0]
    cut = summary(decoded)['tracks'][0]['cuts'][0]
    assert (actual['in_ms'], actual['out_ms'], actual['speed_num'], actual['speed_den']) == (120, 2400, 2, 3)
    assert fraction(cut['source_in_seconds']) * 1000 == actual['in_ms']
    assert fraction(cut['source_out_seconds']) * 1000 == actual['out_ms']
    assert 'RESOLVE_PREMIERE_INTEROPERABILITY_NOT_RUN' in {row['code'] for row in converted['report']}


@pytest.mark.parametrize('target', ['global_start_time', 'available_range'])
def test_exact_metadata_cannot_restore_a_removed_native_time(target):
    pytest.importorskip('opentimelineio')
    doc = document()
    doc['global_start_time'] = time_value(24)
    doc['tracks'][0]['items'][0]['available_range'] = {
        'start': time_value(0), 'duration': time_value(240),
    }
    raw = json.loads(write_otio(doc))
    if target == 'global_start_time':
        raw['global_start_time'] = None
    else:
        raw['tracks']['children'][0]['children'][0]['media_references']['DEFAULT_MEDIA']['available_range'] = None
    with pytest.raises(ValueError, match='EXACT_TIME_METADATA_MISMATCH'):
        read_otio(json.dumps(raw))


@pytest.mark.parametrize('target', ['global_start_time', 'available_start', 'available_duration'])
@pytest.mark.parametrize('bad_rational', [
    {'numerator': 1, 'denominator': 0},
    {'numerator': 10**15 + 1, 'denominator': 1},
])
def test_new_exact_metadata_retains_existing_rational_limits(target, bad_rational):
    pytest.importorskip('opentimelineio')
    doc = document()
    doc['global_start_time'] = time_value(24)
    doc['tracks'][0]['items'][0]['available_range'] = {
        'start': time_value(0), 'duration': time_value(240),
    }
    raw = json.loads(write_otio(doc))
    if target == 'global_start_time':
        exact = raw['metadata'][NS]['global_start_time']
    else:
        ref = raw['tracks']['children'][0]['children'][0]['media_references']['DEFAULT_MEDIA']
        exact = ref['metadata'][NS]['start' if target == 'available_start' else 'duration']
    exact['frames'] = bad_rational
    with pytest.raises(ValueError, match='RATIONAL_LIMIT'):
        read_otio(json.dumps(raw))


def test_native_mixed_track_retime_receipts_keep_independent_placement_and_dissolve(tmp_path):
    pytest.importorskip('opentimelineio')
    doc = document(speed=Fraction(2, 3))
    first = doc['tracks'][0]['items'][0]
    dissolve = {'kind': 'Transition', 'name': 'dissolve', 'transition_type': 'SMPTE_Dissolve',
        'in_offset': time_value(1, 100), 'out_offset': time_value(1, 100)}
    second = copy.deepcopy(first)
    second['speed'] = rational(Fraction(1, 2))
    doc['tracks'][0]['items'].extend([dissolve, second])
    audio = copy.deepcopy(first)
    audio.update(name='dialogue', target_url='media/inert-synthetic.wav',
        start=time_value(12000, 48000), duration=time_value(96000, 48000), speed=rational(2))
    doc['tracks'].append({'name': 'A1', 'kind': 'Audio', 'items': [audio]})
    path = tmp_path / 'mixed-rate-retimed.otio'
    path.write_bytes(write_otio(doc))
    decoded, _ = read_otio(path.read_text(encoding='utf-8'))
    tracks = summary(decoded)['tracks']
    assert fraction(tracks[0]['duration_seconds']) == 2 * seconds(first['duration'])
    assert fraction(tracks[0]['cuts'][1]['start_seconds']) == seconds(first['duration'])
    assert fraction(tracks[0]['cuts'][1]['source_out_seconds']) == seconds(second['start']) + seconds(second['duration']) / 2
    assert fraction(tracks[1]['cuts'][0]['source_in_seconds']) == Fraction(1, 4)
    assert fraction(tracks[1]['cuts'][0]['source_out_seconds']) == Fraction(17, 4)
    assert fraction(tracks[1]['duration_seconds']) == 2


EXACT_METADATA_TARGETS = [
    'global_start_time', 'external_start', 'external_duration',
    'missing_start', 'missing_duration',
]


def exact_metadata_fixture(target):
    doc = document(missing=target.startswith('missing_'))
    doc['global_start_time'] = time_value(24)
    doc['tracks'][0]['items'][0]['available_range'] = {
        'start': time_value(0), 'duration': time_value(240),
    }
    raw = json.loads(write_otio(doc))
    if target == 'global_start_time':
        owner, key, path = raw, target, 'timeline'
    else:
        owner = raw['tracks']['children'][0]['children'][0]['media_references']['DEFAULT_MEDIA']
        key, path = target.split('_', 1)[1], 'tracks[0].items[0].media_reference'
    return doc, raw, owner['metadata'][NS][key], path


@pytest.mark.parametrize('target', EXACT_METADATA_TARGETS)
def test_unknown_exact_time_fields_have_explicit_losses(target):
    pytest.importorskip('opentimelineio')
    doc, raw, exact, path = exact_metadata_fixture(target)
    exact['vendor_payload'] = {'nested': {'comment': 'unrepresented exact-time field'}}
    restored, losses = read_otio(json.dumps(raw))
    assert {'path': path, 'code': 'UNKNOWN_EXCHANGE_METADATA_NOT_REPRESENTED',
            'severity': 'LOSS'} in losses
    assert semantic_document(restored) == semantic_document(doc)
    output = write_otio(restored)
    assert b'unrepresented exact-time field' not in output
    again, output_losses = read_otio(output.decode('utf-8'))
    assert semantic_document(again) == semantic_document(doc)
    assert not any(row['code'] == 'UNKNOWN_EXCHANGE_METADATA_NOT_REPRESENTED'
                   for row in output_losses)


@pytest.mark.parametrize('target', EXACT_METADATA_TARGETS)
@pytest.mark.parametrize('field', ['frames', 'rate'])
def test_unknown_fields_nested_inside_exact_rationals_remain_rejected(target, field):
    pytest.importorskip('opentimelineio')
    _, raw, exact, _ = exact_metadata_fixture(target)
    exact[field]['vendor_payload'] = {'nested': {'comment': 'invalid rational field'}}
    with pytest.raises(ValueError, match='OTIO_INVALID_RATIONAL'):
        read_otio(json.dumps(raw))


@pytest.mark.parametrize('missing', [False, True])
def test_legacy_integer_global_and_available_times_need_no_exact_metadata(missing):
    pytest.importorskip('opentimelineio')
    doc = document(missing=missing)
    doc['global_start_time'] = time_value(24)
    item = doc['tracks'][0]['items'][0]
    item.update(start=time_value(24), duration=time_value(24),
                available_range={'start': time_value(0), 'duration': time_value(240)})
    raw = json.loads(write_otio(doc))
    raw['metadata'].pop(NS)
    ref = raw['tracks']['children'][0]['children'][0]['media_references']['DEFAULT_MEDIA']
    ref['metadata'].pop(NS)
    restored, losses = read_otio(json.dumps(raw))
    assert semantic_document(restored) == semantic_document(doc)
    assert not any(row['code'] == 'UNKNOWN_EXCHANGE_METADATA_NOT_REPRESENTED'
                   for row in losses)
