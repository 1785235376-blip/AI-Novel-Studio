import copy,csv,hashlib,io,json
from pathlib import Path
import pytest
from test_v2_creative_foundation import rig,client,public
from app.creative.service import CreativeService


def document(e):
    return e.service.create(e.nid,e.scope,e.actor,{'mode':'DIRECTOR','title':'中文导演计划','source_independent':True,
        'scenes':[{'id':'scene','sequence':1,'heading':'港口','action':'等待'}],
        'director_notes':[{'id':'note','scene_id':'scene','number':1,'note':'  =HYPERLINK("synthetic")','blocking':'第一行,第二列\n第二行','duration_seconds':7,
                           'performances':[{'character':'角色','action':'等待','expression':'平静','state':'站立'}]}]})


def test_saved_director_csv_reopens_quotes_unicode_and_formula_cells_without_writes(rig):
    e=rig;row=document(e);before=copy.deepcopy(e.store.read(e.nid,e.scope));service=CreativeService(e.store,e.novels,e.chapters)
    result=service.export_director_sheet(e.nid,e.scope,row['id'],1)
    rows=list(csv.DictReader(io.StringIO(result['content'].decode('utf-8-sig'))))
    assert len(rows)==1 and rows[0]['title']=='中文导演计划'
    assert rows[0]['direction']=="'  =HYPERLINK(\"synthetic\")" and rows[0]['blocking']=='第一行,第二列\n第二行'
    assert json.loads(rows[0]['performances'])[0]['action']=='等待'
    assert rows[0]['document_id']==row['id'] and rows[0]['document_status']=='DRAFT'
    assert rows[0]['document_digest']==result['document_digest']
    assert hashlib.sha256(result['content']).hexdigest()==result['sha256']
    assert e.store.read(e.nid,e.scope)==before and service.get(e.nid,e.scope,row['id'])==row


@pytest.mark.parametrize('change',['version','permission','capacity'])
def test_csv_final_boundary_refuses_changed_source_or_authority(rig,monkeypatch,change):
    from app.creative import director_sheet_export as encoder
    e=rig;row=document(e);original=encoder.render;revoked=False
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    def guard():
        if revoked:raise PermissionError('revoked')
    def render(*args):
        nonlocal revoked
        value=original(*args)
        if change=='permission':revoked=True
        elif change=='version':
            body=public(row);body['title']='Changed';e.service.update(e.nid,e.scope,e.actor,row['id'],1,body)
        return value
    if change=='capacity':monkeypatch.setattr(encoder,'MAX_BYTES',32)
    else:monkeypatch.setattr(encoder,'render',render)
    with pytest.raises((ValueError,PermissionError)):
        e.service.export_director_sheet(e.nid,e.scope,row['id'],1,reauthorize=guard)
    if change!='version':assert e.store.read(e.nid,e.scope)==before


def test_original_mounted_csv_read_permission_and_hash_headers(rig,client):
    e=rig;row=document(e);url=f'/api/novels/{e.nid}/experimental/creative/documents/{row["id"]}/director-sheet-export'
    response=client.get(url,params={'expected_version':1},headers={'X-Session-Token':'reader'})
    assert response.status_code==200,response.text
    assert response.headers['content-type'].startswith('text/csv') and response.headers['x-creative-document-version']=='1'
    assert hashlib.sha256(response.content).hexdigest()==response.headers['x-content-sha256']
    assert client.get(url,params={'expected_version':1}).status_code==401
    assert client.get(url,params={'expected_version':2},headers={'X-Session-Token':'owner'}).status_code==409


@pytest.mark.parametrize('text',['=1+1',' +SUM(A1)','-1','@cmd','\tvalue','\rvalue','\nvalue','＝1+1','＋SUM(A1)','－1','＠cmd',' \ufeff \u200b=1'])
def test_formula_like_cells_are_literal(text):
    from app.creative.director_sheet_export import cell
    assert cell(text)=="'"+text


def test_sheet_encoder_declared_in_original_public_manifest():
    manifest=json.loads(Path('packaging/public-build.json').read_text())
    assert 'app/creative/director_sheet_export.py' in manifest['files']
