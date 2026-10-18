"""Saved Storyboard CSV through the original Creative owner and mounted router."""
import copy,csv,hashlib,io,json
import pytest
from test_v2_creative_foundation import rig,client,public
from app.creative.service import CreativeService


def document(e):
    return e.service.create(e.nid,e.scope,e.actor,{'mode':'STORYBOARD','title':'分镜计划 🎬','source_independent':True,
        'scenes':[{'id':'scene','sequence':1,'heading':'港口','action':'等待'}],
        'shots':[{'id':'late','scene_id':'scene','number':2,'action':'后一个镜头','duration_seconds':8},
                 {'id':'first','scene_id':'scene','number':1,'frame_prompt':' =HYPERLINK("synthetic")',
                  'action':'逗号,与换行\n第二行','sound':'海风','dialogue':[{'speaker':'角色','text':'你好'}]}]})


def test_original_saved_owner_exports_ordered_shots_and_preserves_source(rig):
    e=rig;row=document(e);before=copy.deepcopy(e.store.read(e.nid,e.scope));owner=CreativeService(e.store,e.novels,e.chapters)
    result=owner.export_storyboard_sheet(e.nid,e.scope,row['id'],1)
    rows=list(csv.DictReader(io.StringIO(result['content'].decode('utf-8-sig'))))
    assert [r['shot_id'] for r in rows]==['first','late']
    assert rows[0]['frame_prompt']=="' =HYPERLINK(\"synthetic\")"
    assert rows[0]['action']=='逗号,与换行\n第二行' and rows[0]['sound']=='海风'
    assert json.loads(rows[0]['dialogue'])[0]['text']=='你好'
    assert all(r['document_id']==row['id'] and r['document_status']=='DRAFT' and r['document_digest']==result['document_digest'] for r in rows)
    assert rows[1]['duration_seconds']=='8'
    assert hashlib.sha256(result['content']).hexdigest()==result['sha256']
    assert e.store.read(e.nid,e.scope)==before and owner.get(e.nid,e.scope,row['id'])==row


@pytest.mark.parametrize('change',['version','permission','capacity'])
def test_original_post_render_guards_refuse_changed_source_or_authority(rig,monkeypatch,change):
    from app.creative import director_sheet_export as encoder
    e=rig;row=document(e);original=encoder.render_storyboard;revoked=False
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
    else:monkeypatch.setattr(encoder,'render_storyboard',render)
    with pytest.raises((ValueError,PermissionError)):
        e.service.export_storyboard_sheet(e.nid,e.scope,row['id'],1,reauthorize=guard)


def test_mounted_csv_requires_original_read_access_and_exact_version(rig,client):
    e=rig;row=document(e);url=f'/api/novels/{e.nid}/experimental/creative/documents/{row["id"]}/storyboard-sheet-export'
    response=client.get(url,params={'expected_version':1},headers={'X-Session-Token':'reader'})
    assert response.status_code==200,response.text
    assert response.headers['content-type'].startswith('text/csv')
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-creative-document-version']=='1'
    assert hashlib.sha256(response.content).hexdigest()==response.headers['x-content-sha256']
    assert client.get(url,params={'expected_version':1}).status_code==401
    assert client.get(url,params={'expected_version':2},headers={'X-Session-Token':'owner'}).status_code==409


def test_director_is_not_mislabeled_as_storyboard(rig):
    from test_director_sheet_export_additive import document as director
    e=rig;row=director(e)
    with pytest.raises(ValueError,match='STORYBOARD_SHEET_MODE_REQUIRED'):
        e.service.export_storyboard_sheet(e.nid,e.scope,row['id'],1)
