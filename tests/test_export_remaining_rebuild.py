"""New verification, not recovered evidence from the unavailable old package."""
import base64
import io
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET
import pytest
from app.export_formats import novel_to_docx, novel_to_epub, _clean_text
from app.services.export_job_service import ExportJobService

@pytest.mark.parametrize('fmt', ['docx', 'epub'])
@pytest.mark.parametrize('bad', ['\ufffe','\uffff','\ufffe\uffff'])
def test_xml_parts_parse_and_preserve_unicode(fmt,bad):
    title='标题😀'+bad
    chapters=[{'title':'章节'+bad,'content':'内容&<> 😀\U0001fffe'+bad}]
    raw=novel_to_docx(title,chapters) if fmt=='docx' else novel_to_epub(title,chapters,'identifier'+bad)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None
        texts=[]
        for name in z.namelist():
            if name.endswith(('.xml','.rels','.opf','.xhtml')):
                texts.append(''.join(ET.fromstring(z.read(name)).itertext()))
        combined=''.join(texts)
        assert '内容&<> 😀\U0001fffe' in combined
        assert '\ufffe' not in combined and '\uffff' not in combined

def test_xml_character_range():
    assert _clean_text('\x00\t\n\r\x1f\ud800\udfff\ufffe\uffff中文😀\U0001fffe') == '\t\n\r中文😀\U0001fffe'

@pytest.mark.parametrize('size',[1,2,3,4,5,6])
@pytest.mark.parametrize('shape',['raw','named','legacy'])
def test_binary_representation_budget(monkeypatch,size,shape):
    monkeypatch.setattr(ExportJobService,'MAX_RESULT_BYTES',size)
    raw=b'x'*size; encoded=base64.b64encode(raw).decode()
    result= {'content':raw} if shape=='raw' else ({'content_base64':encoded} if shape=='named' else {'content':encoded,'content_encoding':'base64'})
    saved=ExportJobService._serialise_result(result)
    assert ExportJobService._result_bytes(saved)==raw

@pytest.mark.parametrize('shape',['raw','named','legacy'])
def test_over_limit_rejected(monkeypatch,shape):
    monkeypatch.setattr(ExportJobService,'MAX_RESULT_BYTES',3)
    raw=b'abcd'; enc=base64.b64encode(raw).decode()
    result={'content':raw} if shape=='raw' else ({'content_base64':enc} if shape=='named' else {'content':enc,'content_encoding':'base64'})
    with pytest.raises(ValueError): ExportJobService._serialise_result(result)

@pytest.mark.parametrize('encoded',['%%%%','é','eA='])
def test_legacy_invalid_base64_rejected(encoded):
    with pytest.raises(ValueError): ExportJobService._serialise_result({'content':encoded,'content_encoding':'base64'})

def service(tmp_path):
    return ExportJobService(tmp_path,lambda n,f:{'format':f,'content':'text'})

def test_idempotency_format_conflict(tmp_path):
    s=service(tmp_path)
    try:
        first=s.create('n','txt','k')
        with pytest.raises(ValueError,match='EXPORT_IDEMPOTENCY_FORMAT_CONFLICT'): s.create('n','json','k')
        assert s.create('n','text','k')['id']==first['id']
        assert len(s._read())==1
    finally:s._pool.shutdown(wait=True)

@pytest.mark.parametrize('alias,canonical',[('text','txt'),('md','markdown'),('word','docx'),('screenplay-standard','screenplay-fountain')])
def test_alias_same_request(tmp_path,alias,canonical):
    s=service(tmp_path)
    try: assert s.create('n',alias,'k')['id']==s.create('n',canonical,'k')['id']
    finally:s._pool.shutdown(wait=True)

def test_concurrent_format_conflict(tmp_path):
    s=service(tmp_path)
    def create(fmt):
        try:return s.create('n',fmt,'k')['format']
        except ValueError as e:return str(e)
    try:
        with ThreadPoolExecutor(2) as pool: result=list(pool.map(create,['txt','json']))
        assert result.count('EXPORT_IDEMPOTENCY_FORMAT_CONFLICT')==1
        assert len(s._read())==1
    finally:s._pool.shutdown(wait=True)

def test_permission_and_novel_scope(tmp_path):
    s=service(tmp_path)
    try:
        a=s.create('n','txt','k',permission_context={'actor_id':'a'})
        b=s.create('n','json','k',permission_context={'actor_id':'b'})
        c=s.create('other','json','k',permission_context={'actor_id':'a'})
        assert len({a['id'],b['id'],c['id']})==3
    finally:s._pool.shutdown(wait=True)
