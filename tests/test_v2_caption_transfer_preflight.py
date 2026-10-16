"""Original caption renderer to original Timeline parser; no model or HTTP runtime."""
import copy
import pytest
from app.experimental.subtitle_timeline import render_captions
from app.services.studio_timeline_subtitles import import_subtitles


def target():
    return {'duration_ms': 2000, 'tracks': [{'id': 'video', 'kind': 'VIDEO', 'order': 0, 'clips': [{'id': 'synthetic-clip', 'start_ms': 0, 'in_ms': 0, 'out_ms': 2000, 'source_snapshot': {'id': 'synthetic-video', 'kind': 'ASSET', 'asset_kind': 'video', 'version': 1, 'digest': 'a'*64}}]}],
            'captions': [{'start_ms': 0, 'end_ms': 100, 'text': 'Original target'}]}


@pytest.mark.parametrize('format', ['srt', 'vtt'])
def test_original_file_handoff_quantizes_unicode_speaker_and_replaces_only_captions(format, tmp_path):
    row = {'timebase': {'numerator': 30000, 'denominator': 1001},
           'speakers': {'seg': {'name': '月🌙'}},
           'cues': [{'start_tick': 0, 'end_tick': 30, 'text': '你好🌙\nHello', 'segment_id': 'seg'},
                    {'start_tick': 15, 'end_tick': 45, 'text': '合唱', 'overlap_reason': '同时发言'}]}
    before = copy.deepcopy(row)
    path = tmp_path / f'captions.{format}'
    path.write_bytes(render_captions(row, format))
    timeline = target()
    converted = import_subtitles(timeline, path.read_text(encoding='utf-8'), format.upper())
    assert converted['captions'] == [
        {'start_ms': 0, 'end_ms': 1001, 'text': '[月🌙] 你好🌙\nHello'},
        {'start_ms': 500, 'end_ms': 1501, 'text': '合唱'}]
    assert timeline == target() and row == before
    assert converted['tracks'][0]['id'] == 'video'
    assert all(set(cue) == {'start_ms', 'end_ms', 'text'} for cue in converted['captions'])


@pytest.mark.parametrize('text', ['literal {style}', 'a\\b', 'a --> b', 'a'*1001])
def test_caption_owner_output_can_be_incompatible_with_timeline(text):
    output = render_captions({'timebase': {'numerator': 1000, 'denominator': 1},
                             'cues': [{'start_tick': 0, 'end_tick': 1000, 'text': text}]}, 'srt')
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_CAPTION'):
        import_subtitles(target(), output.decode('utf-8'), 'SRT')


def test_target_duration_is_independently_validated():
    content = render_captions({'timebase': {'numerator': 1000, 'denominator': 1},
                              'cues': [{'start_tick': 0, 'end_tick': 2001, 'text': 'Longer source'}]}, 'srt')
    with pytest.raises(ValueError):
        import_subtitles(target(), content.decode('utf-8'), 'SRT')


@pytest.mark.parametrize('text', ['a\r\nb', 'a\u0085b', 'a\u2028b', 'a\u2029b', 'a '])
def test_original_export_rejects_readback_text_loss(text):
    with pytest.raises(ValueError, match='CAPTION_ROUND_TRIP_FAILED'):
        render_captions({'timebase': {'numerator': 1000, 'denominator': 1},
                         'cues': [{'start_tick': 0, 'end_tick': 1000, 'text': text}]}, 'srt')
