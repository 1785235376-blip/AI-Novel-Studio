import subprocess
from copy import deepcopy
import pytest
from app.services.studio_timeline_subtitles import export_subtitles, import_subtitles, parse_subtitle_cues
from test_studio_otio_runtime_20261029 import case, rig, base, body, call, checked, files

def timeline(text):
    return {'duration_ms':1000,'tracks':[{'id':'v','kind':'VIDEO','order':0,'clips':[{'id':'c','source_snapshot':{'id':'a','kind':'ASSET','asset_kind':'video','version':1,'digest':'a'*64},'start_ms':0,'in_ms':0,'out_ms':1000}]}], 'captions':[{'start_ms':0,'end_ms':500,'text':text}]}

def vtt(text):return 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:00.500\n'+text+'\n'

def external_text(data):
    r=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','webvtt','-i','pipe:0','-f','srt','pipe:1'],input=data,capture_output=True,check=True,timeout=15)
    lines=r.stdout.decode().strip().splitlines()
    assert '-->' in lines[1]
    return '\n'.join(lines[2:])

@pytest.mark.parametrize('text',['R&amp;D','Show &lt;tag&gt;','Nested &amp;amp; &unknown;','普通中文🙂 & raw'])
def test_actual_external_display_matches_literal(text):
    encoded=export_subtitles(timeline(text),'VTT')
    assert external_text(encoded)==text
    assert parse_subtitle_cues(encoded.decode(),'VTT')[0]['text']==text

@pytest.mark.parametrize('text,expected',[('&amp;lt;','&lt;'),('&amp;amp;','&amp;'),('&amp;&nbsp;&lrm;&rlm;','&\u00a0\u200e\u200f')])
def test_exact_references_decode_only_once(text,expected):
    assert parse_subtitle_cues(vtt(text),'VTT')[0]['text']==expected

@pytest.mark.parametrize('text',['&lt;b&gt;unsafe&lt;/b&gt;','<b>unsafe</b>'])
def test_markup_still_rejected_by_owner(text):
    with pytest.raises(ValueError,match='LITERAL_TEXT_REQUIRED'):
        import_subtitles(timeline('safe'),vtt(text),'VTT')

def test_unrecognized_numeric_and_html_references_remain_literal():
    text='&#60;b&#62; &quot; &apos; &AMP; &bogus;'
    assert parse_subtitle_cues(vtt(text),'VTT')[0]['text']==text

def test_srt_stays_byte_equivalent():
    text='R&amp;D &lt;tag&gt;'
    encoded=export_subtitles(timeline(text),'SRT')
    assert encoded==b'1\n00:00:00,000 --> 00:00:00,500\nR&amp;D &lt;tag&gt;\n'
    assert parse_subtitle_cues(encoded.decode(),'SRT')[0]['text']==text

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_entity_literal_http_import_export_replay_restore(case,prefix):
    e=case; url=base(e,prefix)
    literal='Show &lt;tag&gt; and R&amp;D'
    request=body(e,'IMPORT',content=vtt('Show &amp;lt;tag&amp;gt; and R&amp;amp;D'))
    request['format']='VTT'
    before=files(e.rig.root)
    preview=call(e,url+'/transfer-preview',request)
    assert files(e.rig.root)==before
    assert preview['timeline']['captions'][0]['text']==literal
    commit={**request,'request_id':'vtt-independent-import','reviewed_preview_digest':preview['preview_digest'],'acknowledge_losses':True}
    applied=call(e,url+'/transfer-import',commit)
    after=files(e.rig.root)
    assert call(e,url+'/transfer-import',commit)==applied and files(e.rig.root)==after
    e.row=applied
    export=body(e);export['format']='VTT'
    ep=call(e,url+'/transfer-preview',export)
    out=e.rig.client.post(url+'/transfer-attachment',headers=e.headers,json={**export,'reviewed_preview_digest':ep['preview_digest'],'acknowledge_losses':True})
    assert out.status_code==200,out.text
    assert external_text(out.content)==literal
    history=checked(e.rig.client.get(url+'/history',headers=e.headers))
    original=history['items'][0]
    # The restore request uses immutable original identity, not a new import.
    restored=call(e,url+'/restore',{'expected_version':applied['version'],'reviewed_timeline_digest':applied['timeline_digest'], 'restore_version':original['version'],'restore_digest':original['timeline_digest']})
    assert restored['version']==applied['version']+1
    assert restored['timeline']['captions'][0]['text']=='Synthetic OTIO caption'
