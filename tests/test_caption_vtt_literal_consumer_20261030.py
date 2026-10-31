"""B04 authored literal text survives its own VTT export/import-preview parser."""
import pytest
from app.experimental.subtitle_timeline import render_captions, read_captions
from app.services.studio_timeline_subtitles import parse_subtitle_cues


def caption(text, speaker=None):
    return {'timebase':{'numerator':1000,'denominator':1},
            'cues':[{'id':'c','segment_id':'s','start_tick':0,'end_tick':900,'text':text}],
            'speakers':{'s':{'name':speaker}} if speaker else {}}

@pytest.mark.parametrize('text', ['&#65;', '&copy;', '&amp;', '&amp;lt;', 'R&D 中文', 'caf&eacute;'])
@pytest.mark.parametrize('format', ['srt','vtt'])
def test_authored_reference_spelling_roundtrips_through_shared_import(text, format):
    raw = render_captions(caption(text),format).decode()
    assert parse_subtitle_cues(raw,format.upper())[0]['text']==text
    assert read_captions(raw,format)[0]['text']==text

@pytest.mark.parametrize('speaker',['R&amp;D','&#65; &copy;'])
def test_entire_composed_speaker_label_is_literal(speaker):
    raw = render_captions(caption('Hello &amp;',speaker),'vtt').decode()
    assert parse_subtitle_cues(raw,'VTT')[0]['text']==f'[{speaker}] Hello &amp;'


def test_empty_readback_contract_is_unchanged():
    assert read_captions('WEBVTT\n\n\n','vtt')==[]

@pytest.mark.parametrize('text', ['Literal &amp; &#65; &copy;', 'Show &lt;tag&gt;'])
def test_external_ffmpeg_preserves_authored_caption_spelling(tmp_path, text):
    import subprocess
    source = tmp_path/'caption.vtt'
    source.write_bytes(render_captions(caption(text),'vtt'))
    result = subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-f','srt','-'],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=10)
    assert result.stdout.decode().splitlines()[2]==text
