"""Real OTIO 0.18.1 + File/HTTP transfer on public 395ac26, synthetic media only."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest
import opentimelineio as otio
from app.actor_context import SessionContext
from app.audio_production_store import AudioProductionStore
from app.asset_providers import AssetProviderRegistry
from app.creative.production_execution import ProductionExecutionService
from app.experimental import api as experimental_api
from app.experimental.timeline_exchange import parser_status, read_otio
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import NoExternalCalls

pytestmark = pytest.mark.file_backend_only

def checked(r, status=200):
    assert r.status_code == status, r.text
    return r.json()

def files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

@pytest.fixture
def case(rig, monkeypatch, tmp_path):
    p = ProductionExecutionService(rig.workspace, ImageJobService(rig.root/'image'), AssetProviderRegistry(),
        VideoAssemblyService(rig.root/'video', rig.assets), {}, {}, AudioProductionStore(rig.root/'audio'),
        NoExternalCalls(), NoExternalCalls())
    for name, value in p.__dict__.items():
        monkeypatch.setattr(experimental_api.studio_production_service, name, value, raising=False)
    token = 'otio-runtime-host'
    rig.sessions.register(token, SessionContext('otio-session','otio-client','otio-actor','otio-workspace'))
    headers = {'X-Session-Token': token}
    checked(rig.client.post(f'/api/projects/{rig.nid}/studio/activate', headers=headers))
    media = tmp_path/'synthetic.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:r=25:d=2',
        '-an','-c:v','mpeg4','-threads','1','-y',str(media)], check=True, timeout=20)
    with rig.workspace._asset_scope(rig.nid,rig.scope):
        asset = rig.assets.create(rig.nid,'synthetic.mp4',base64.b64encode(media.read_bytes()).decode(),
            'video/mp4','video',required_features=('narrative_production_v2',))
    source = {'kind':'ASSET','asset_kind':'video','id':asset['id'],'version':asset['version'],'digest':asset['sha256']}
    definition = {'schema_version':2,'duration_ms':1000,'width':640,'height':360,'fps':25,
        'tracks':[{'id':'v1','kind':'VIDEO','order':0,'clips':[{'id':'clip1','source_snapshot':source,
        'start_ms':0,'in_ms':400,'out_ms':1400,'include_audio':False}]}],
        'captions':[{'start_ms':0,'end_ms':500,'text':'Synthetic OTIO caption'}]}
    created = checked(rig.client.post(f'/api/projects/{rig.nid}/studio/production/timelines',headers=headers,
        json={'expected_version':0,'title':'Synthetic OTIO transfer','timeline':definition}),201)
    return SimpleNamespace(rig=rig,p=p,headers=headers,row=created,asset=asset)

def base(e,prefix): return f'{prefix}/projects/{e.rig.nid}/studio/production/timelines/{e.row["id"]}'
def body(e,direction='EXPORT',**kw):
    return {'expected_version':e.row['version'],'reviewed_timeline_digest':e.row['timeline_digest'],
        'direction':direction,'format':'OTIO',**kw}
def call(e,url,payload,status=200):return checked(e.rig.client.post(url,headers=e.headers,json=payload),status)
def attachment(e,prefix):
    url=base(e,prefix); request=body(e)
    preview=call(e,url+'/transfer-preview',request)
    r=e.rig.client.post(url+'/transfer-attachment',headers=e.headers,
        json={**request,'reviewed_preview_digest':preview['preview_digest'],'acknowledge_losses':True})
    assert r.status_code==200,r.text
    return preview,r

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_real_native_export_import_replay_history_and_reopen(case,prefix):
    e=case; url=base(e,prefix); before=files(e.rig.root)
    status=parser_status(); assert status['available'] and status['installed_version']=='0.18.1'
    preview,r=attachment(e,prefix)
    assert files(e.rig.root)==before
    assert preview['model_called'] is False and preview['external_media_access'] is False
    assert preview['requires_loss_acknowledgment'] and any(x['code'].startswith('CAPTIONS_REQUIRE') for x in preview['loss_report'])
    assert hashlib.sha256(r.content).hexdigest()==r.headers['x-asset-sha256']==preview['output_sha256']
    assert r.headers['cache-control']=='no-store'
    native=otio.adapters.read_from_string(r.text,'otio_json')
    assert native.tracks[0][0].source_range.start_time.to_seconds()==pytest.approx(.4)
    assert native.duration().to_seconds()==pytest.approx(1)
    request=body(e,'IMPORT',content=r.text,media_bindings=preview['media_bindings'])
    ip=call(e,url+'/transfer-preview',request)
    assert ip['timeline']==e.row['timeline']
    commit={**request,'request_id':'otio-explicit-import','reviewed_preview_digest':ip['preview_digest'],'acknowledge_losses':True}
    applied=call(e,url+'/transfer-import',commit)
    assert applied['version']==2 and applied['timeline']==e.row['timeline']
    after=files(e.rig.root)
    assert call(e,url+'/transfer-import',commit)==applied and files(e.rig.root)==after
    history=checked(e.rig.client.get(url+'/history',headers=e.headers))
    assert history['current_version']==2 and len(history['items'])==1
    # Reopen actual original stores/services, not the same in-memory owner.
    from test_studio_canvas_audio_return import services
    from app.services import ChapterService
    workspace=services(e.rig.root,'file','',e.rig.novels,e.rig.workspace.creative.chapters)
    reopened=ProductionExecutionService(workspace,ImageJobService(e.rig.root/'image'),AssetProviderRegistry(),
        VideoAssemblyService(e.rig.root/'video',workspace.assets),{},{},AudioProductionStore(e.rig.root/'audio'),NoExternalCalls(),NoExternalCalls())
    got=reopened.timeline_get(e.rig.nid,e.rig.scope,'local-author',e.row['id'],lambda:None)
    assert got['version']==2 and got['timeline']==applied['timeline']
    changed={**commit,'request_id':'otio-explicit-import','content':r.text+' '}
    assert call(e,url+'/transfer-import',changed,422)['detail']['code']=='EXPERIMENTAL_INVALID'
    restored=call(e,url+'/restore',{'expected_version':2,'reviewed_timeline_digest':applied['timeline_digest'],
        'restore_version':1,'restore_digest':e.row['timeline_digest']})
    assert restored['version']==3 and restored['timeline']==e.row['timeline']
    assert len(checked(e.rig.client.get(url+'/history',headers=e.headers))['items'])==2

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
@pytest.mark.parametrize('failure',['loss','preview','cas','binding','source'])
def test_transfer_safety_refusals_are_read_only(case,prefix,failure):
    e=case;url=base(e,prefix);preview,r=attachment(e,prefix)
    if failure=='loss':
        request={**body(e),'reviewed_preview_digest':preview['preview_digest'],'acknowledge_losses':False}
        expected=422;endpoint='transfer-attachment'
    elif failure=='preview':
        request={**body(e),'reviewed_preview_digest':'0'*64,'acknowledge_losses':True}
        expected=409;endpoint='transfer-attachment'
    elif failure=='cas':
        request={**body(e),'expected_version':2}; expected=409;endpoint='transfer-preview'
    else:
        bindings=deepcopy(preview['media_bindings'])
        if failure=='binding': bindings[0]['reference']='media/unbound'
        else: bindings[0]['source_snapshot']['version']+=1
        request=body(e,'IMPORT',content=r.text,media_bindings=bindings)
        expected=422;endpoint='transfer-preview'
    before=files(e.rig.root)
    response=e.rig.client.post(url+'/'+endpoint,headers=e.headers,json=request)
    assert response.status_code==expected,response.text
    assert files(e.rig.root)==before
