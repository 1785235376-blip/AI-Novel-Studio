"""NEW literal WebVTT evidence, independent of missing historical artifacts."""
import subprocess
import pytest
from app.services.studio_timeline_subtitles import export_subtitles, import_subtitles, parse_subtitle_cues


def timeline(text):
    return {'duration_ms':1000,'width':640,'height':360,'fps':25,
        'tracks':[{'id':'v','kind':'VIDEO','order':0,'clips':[{'id':'c','source_snapshot':{
        'id':'a','kind':'ASSET','asset_kind':'video','version':1,'digest':'a'*64},
        'start_ms':0,'in_ms':0,'out_ms':1000}]}],
        'captions':[{'start_ms':0,'end_ms':900,'text':text}]}


def vtt(text):
    return 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:00.900\n'+text+'\n'


@pytest.mark.parametrize('text',['R&amp;D','Show &lt;tag&gt;','&amp;amp; and &nbsp;', '中文 &amp; 😀', 'R&D', '&#65; and &copy;'])
def test_external_ffmpeg_preserves_authored_literal(tmp_path,text):
    source=tmp_path/'caption.vtt';source.write_bytes(export_subtitles(timeline(text),'VTT'))
    result=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-f','srt','-'],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=10)
    assert result.stdout.decode().splitlines()[2]==text
    imported=import_subtitles(timeline('old'),source.read_text(),'VTT')
    assert imported['captions'][0]['text']==text
    assert export_subtitles(imported,'VTT')==source.read_bytes()


@pytest.mark.parametrize('encoded,expected',[
    ('R&amp;D','R&D'),('&amp;lt;tag&amp;gt;','&lt;tag&gt;'),
    ('a&nbsp;b&lrm;c&rlm;d','a\u00a0b\u200ec\u200fd'),
    ('&#38; &#x26; &copy; &AMP; &amp','& & © & &'),
])
def test_import_decodes_character_references_once(encoded,expected):
    assert import_subtitles(timeline('old'),vtt(encoded),'VTT')['captions'][0]['text']==expected


@pytest.mark.parametrize('encoded',['&lt;b&gt;','&gt;'])
def test_decoded_markup_still_rejected(encoded):
    with pytest.raises(ValueError,match='STUDIO_TIMELINE_CAPTION_LITERAL_TEXT_REQUIRED'):
        import_subtitles(timeline('old'),vtt(encoded),'VTT')


def test_srt_literal_contract_unchanged():
    text='Show &lt;tag&gt; and R&amp;D'
    raw=export_subtitles(timeline(text),'SRT')
    assert raw.decode().splitlines()[2]==text
    assert import_subtitles(timeline('old'),raw.decode(),'SRT')['captions'][0]['text']==text


def test_lexical_parser_decodes_legacy_references():
    assert parse_subtitle_cues(vtt('&lt;&gt;&amp;&nbsp;&lrm;&rlm;'),'VTT')[0]['text']=='<>&\u00a0\u200e\u200f'
