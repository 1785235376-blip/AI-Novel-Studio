"""External plain-text WebVTT references, per WebVTT/HTML data-state rules."""
import pytest
from app.services.studio_timeline_subtitles import import_subtitles, parse_subtitle_cues, export_subtitles
from tests.test_studio_vtt_literal_rebuild_20261029 import timeline, vtt


@pytest.mark.parametrize('encoded,expected', [
    ('caf&eacute; &copy; &#65; &#x1f600;', 'café © A 😀'),
    ('&NotEqualTilde; &AMP; &amp', '\u2242\u0338 & &'),
    ('&notit; &notin; &unknown; &amp=1', '¬it; ∉ &unknown; &=1'),
    ('&#128; &#x80; &#0; &#xD800; &#1114112;', '€ € � � �'),
    ('&amp;#65; &amp;eacute;', '&#65; &eacute;'),
    ('&#65 &#x41 &#x; &#;', 'A A &#x; &#;'),
])
def test_external_references_follow_html_data_state(encoded, expected):
    assert import_subtitles(timeline('old'), vtt(encoded), 'VTT')['captions'][0]['text'] == expected


@pytest.mark.parametrize('encoded', ['&#60;b&#62;', '&#123;', '&#92;', '&#1;', '&#127;'])
def test_reference_decoding_keeps_original_literal_owner_boundary(encoded):
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_CAPTION_LITERAL_TEXT_REQUIRED'):
        import_subtitles(timeline('old'), vtt(encoded), 'VTT')


def test_numeric_reference_longer_than_python_integer_limit_is_bounded():
    assert parse_subtitle_cues(vtt('&#' + '9' * 10000 + ';'), 'VTT')[0]['text'] == '�'


def test_numeric_noncharacter_is_not_silently_deleted():
    assert parse_subtitle_cues(vtt('a&#xFDD0;b'), 'VTT')[0]['text'] == 'a\ufdd0b'


def test_authored_reference_spellings_remain_literal_and_srt_is_unchanged():
    text = '&eacute; &#65; &notit; &AMP;'
    for format in ('VTT', 'SRT'):
        encoded = export_subtitles(timeline(text), format)
        assert import_subtitles(timeline('old'), encoded.decode(), format)['captions'][0]['text'] == text
