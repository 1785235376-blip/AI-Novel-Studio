"""Original OTIO conversion evidence; no external NLE or rendering claim."""
import copy
import json
from pathlib import Path
from fractions import Fraction
from app.experimental.timeline_exchange import seconds
from app.services.studio_timeline_exchange import studio_timeline_to_exchange, exchange_to_studio_timeline


def test_original_studio_projection_losses_and_exact_pure_roundtrip():
    capture = json.loads((Path(__file__).resolve().parents[1] / 'frontend/src/creative/fixtures/phase6.capture.editing-pipeline.json').read_text())
    timeline = copy.deepcopy(capture['created']['timeline'])
    clip = timeline['tracks'][0]['clips'][0]
    clip.update(opacity=0.5, gain_db=-3, fade_in_ms=10, include_audio=True, speed_num=2, speed_den=1)
    before = copy.deepcopy(timeline)
    result = studio_timeline_to_exchange(timeline, title='Synthetic NLE review')
    report = {(item['path'], item['code']) for item in result['report']}
    assert ('tracks[0].clips[0]', 'VIDEO_GEOMETRY_OPACITY_REQUIRE_STUDIO_METADATA') in report
    assert ('tracks[0].clips[0]', 'CLIP_MIX_FADES_REQUIRE_STUDIO_METADATA') in report
    assert (f"tracks[0].clips.{clip['id']}", 'NLE_LINEAR_TIME_WARP_INTEROPERABILITY_NOT_RUN') in report
    decoded = result['document']
    native = decoded['tracks'][0]['items'][0]
    assert seconds(native['duration']) == Fraction(clip['out_ms'] - clip['in_ms'], 2000)
    restored = exchange_to_studio_timeline(decoded, media_bindings=result['media_bindings'], canvas={})
    assert restored['timeline'] == result['document']['studio']['timeline']
    assert restored['timeline']['tracks'][0]['clips'][0]['source_snapshot'] == clip['source_snapshot']
    assert timeline == before
    assert restored['report'] == []


def test_native_changes_do_not_restore_stale_studio_effects():
    capture = json.loads((Path(__file__).resolve().parents[1] / 'frontend/src/creative/fixtures/phase6.capture.editing-pipeline.json').read_text())
    result = studio_timeline_to_exchange(capture['created']['timeline'], title='Synthetic NLE review')
    changed = copy.deepcopy(result['document'])
    changed['name'] = 'Native title edit'
    # A native clip-name change alters the projection without fabricating timing.
    changed['tracks'][0]['items'][0]['name'] = 'Changed externally'
    restored = exchange_to_studio_timeline(changed, media_bindings=result['media_bindings'], canvas={})
    assert 'STUDIO_METADATA_STALE_AFTER_NATIVE_EDIT_NOT_RESTORED' in {item['code'] for item in restored['report']}
    assert restored['timeline']['tracks'][0]['clips'][0]['id'] != capture['created']['timeline']['tracks'][0]['clips'][0]['id']


def test_original_rational_frame_values_do_not_accumulate_decimal_drift():
    from app.experimental.timeline_exchange import time_value
    frames = [time_value(1, Fraction(30000, 1001)) for _ in range(500)]
    assert sum((seconds(value) for value in frames), Fraction()) == Fraction(500 * 1001, 30000)
    assert frames[0]['rate'] == {'numerator': 30000, 'denominator': 1001}
