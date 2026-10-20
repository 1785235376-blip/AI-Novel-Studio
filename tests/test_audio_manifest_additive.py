"""Real File Audio review -> manual manifest, without model/provider execution."""
import copy
import json
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.audio_manifest import AudioManifestService, AudioManifestInput, COLLECTION
from app.experimental.audio_manifest_api import create_audio_manifest_router
from app.creative.production_execution_api import create_production_invoker
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import audible_wav, production, trimmed, source
from test_v2_audio_wav_controls import command

@pytest.fixture
def approved(rig):
    e=rig;e.service.activate(e.nid,e.scope,e.actor)
    e.audio_source=import_asset(e,data=audible_wav(),kind='audio',filename='owned-synthetic.wav')
    e.production=production(e);e.formal,e.job=trimmed(e)
    e.manifests=AudioManifestService(e.production)
    return e

def body(e,key='manual-one'):
    preview=e.manifests.preview(e.nid,e.scope,e.actor,e.job['id'],lambda:None)
    return {'job_id':e.job['id'],'expected_job_version':e.job['version'],
            'reviewed_capture_digest':preview['capture_digest'],'request_id':key,'confirmed':True}

def files(e):return {str(p.relative_to(e.root)):p.read_bytes() for p in e.root.rglob('*.json')}

def test_file_record_replay_reopen_and_exportable_projection_preserve_original_owners(approved):
    e=approved;before=files(e);request=body(e)
    result=e.manifests.record(e.nid,e.scope,e.actor,request,lambda:None)
    assert result['capture']['asset']=={'id':e.formal['id'],'version':e.formal['version'],'digest':e.formal['sha256'],'kind':'audio'}
    assert result['capture']['job']['version']==e.job['version'] and result['capture']['result']['output_digest']==e.formal['sha256']
    assert result['replayable'] is False and result['capture']['environment']['state']=='UNKNOWN'
    encoded=json.dumps(result);assert not any(secret in encoded for secret in ('_studio_body','_actor','owner_actor','session_token','prompt','credential'))
    saved=files(e);assert e.manifests.record(e.nid,e.scope,e.actor,request,lambda:None)==result and files(e)==saved
    fresh=AudioManifestService(production(e,reopened(e)))
    assert fresh.get(e.nid,e.scope,e.actor,result['id'],lambda:None)==result
    assert fresh.list(e.nid,e.scope,e.actor,lambda:None)['items']==[result]
    assert e.production.get(e.nid,e.scope,e.actor,'audio',e.job['id'],lambda:None)==e.job
    # Only the existing scope document is changed; job/asset files stay byte-identical.
    changed=[path for path in saved if saved[path]!=before.get(path)]
    assert len(changed)==1 and 'experimental' in changed[0]

def test_file_rejects_unreviewed_job_wrong_preview_and_nonexplicit_confirmation(approved):
    e=approved;value=command(source(e.audio_source));value['request_id']='unreviewed-local-trim'
    preview=e.production.preview(e.nid,e.scope,e.actor,value,lambda:None)[0]
    pending=e.production.create(e.nid,e.scope,e.actor,{'command':value,'reviewed_preview_digest':preview['preview_digest']},lambda:None)
    before=files(e)
    with pytest.raises(ValueError):e.manifests.preview(e.nid,e.scope,e.actor,pending['id'],lambda:None)
    request=body(e)
    for changes in ({'reviewed_capture_digest':'b'*64},{'expected_job_version':request['expected_job_version']-1},{'confirmed':False},{'confirmed':1},{'extra':'no'}):
        with pytest.raises(ValueError):e.manifests.record(e.nid,e.scope,e.actor,{**request,**changes},lambda:None)
        assert files(e)==before

def test_file_deleted_formal_asset_refuses_saved_manifest(approved):
    e=approved;result=e.manifests.record(e.nid,e.scope,e.actor,body(e),lambda:None)
    e.service.lifecycle(e.nid,e.scope,e.formal['id'],e.formal['version'],actor_id=e.actor)
    before=files(e)
    with pytest.raises((FileNotFoundError,ValueError)):e.manifests.get(e.nid,e.scope,e.actor,result['id'],lambda:None)
    assert files(e)==before

def test_file_changed_source_refuses_manifest_without_reclassifying_review(approved):
    e=approved;result=e.manifests.record(e.nid,e.scope,e.actor,body(e),lambda:None)
    with e.service._asset_scope(e.nid,e.scope):
        e.service.assets.annotate_lineage(e.audio_source['id'],{'schema':'asset-lineage-v2','origin':'EXTERNAL_IMPORT',
            'license':{'label':'Synthetic owned source','source':'local fixture','note':''},'sources':{},'operation':'fixture declaration'},
            [],branch_id=e.scope.get('branch_id'),expected_version=e.audio_source['version'])
    before=files(e)
    with pytest.raises((FileNotFoundError,ValueError)):e.manifests.get(e.nid,e.scope,e.actor,result['id'],lambda:None)
    assert files(e)==before

def test_file_other_actor_scope_and_incarnation_cannot_adopt_manifest(approved):
    e=approved;result=e.manifests.record(e.nid,e.scope,e.actor,body(e),lambda:None)
    before=files(e)
    with pytest.raises(FileNotFoundError):e.manifests.get(e.nid,e.scope,'other-synthetic-actor',result['id'],lambda:None)
    assert files(e)==before
    # Replace only this synthetic File identity; original store must exclude it.
    marker=e.root/'novels'/e.nid/'creative_project_v2.json'
    from uuid import uuid4
    marker.write_text(json.dumps({'schema_version':1,'project_incarnation':str(uuid4())}),encoding='utf8')
    before=files(e)
    with pytest.raises((FileNotFoundError,ValueError)):e.manifests.get(e.nid,e.scope,e.actor,result['id'],lambda:None)
    assert files(e)==before
    marker.unlink();before=files(e)
    with pytest.raises((FileNotFoundError,ValueError)):e.manifests.get(e.nid,e.scope,e.actor,result['id'],lambda:None)
    assert files(e)==before and not marker.exists()

def test_file_final_authority_withdrawal_rolls_back_manifest_without_changing_audio(approved):
    e=approved;request=body(e);before=files(e)
    def revoked():
        active=getattr(e.production.store.store._local,'active',{})
        if any(document['collections'].get(COLLECTION) for document in active.values()):
            raise PermissionError('Synthetic read authority withdrawn before commit')
    with pytest.raises(PermissionError):e.manifests.record(e.nid,e.scope,e.actor,request,revoked)
    assert files(e)==before

def api(e,permissions=None,principal=True,host=True):
    state={'permissions':set(permissions or ['domain.read','domain.write']), 'actor':e.actor,'host':host}
    def invoke(nid,token,branch,permission,callback):
        actor,scope=state['actor'],e.scope
        def guard():
            if permission not in state['permissions']:raise HTTPException(403,{'code':'SYNTHETIC_DENIED'})
        guard();result=callback(actor,scope,guard);guard();return result
    def host_session(token):
        if not state['host']:raise HTTPException(403,{'code':'SYNTHETIC_HOST_DENIED'})
    call=create_production_invoker(invoke,require_host_session=host_session,
        model_host_authority=lambda request,token:SimpleNamespace(principal=principal,guard=lambda:None))
    app=FastAPI();app.include_router(create_audio_manifest_router(e.production,call))
    return TestClient(app),state,f'/novels/{e.nid}/experimental/production/audio-manifests'

def test_file_dedicated_api_original_host_invoker_read_write_and_export(approved):
    e=approved;client,state,root=api(e)
    assert client.get(root+'/results').json()['items'][0]['id']==e.job['id']
    preview=client.get(root+'/results/'+e.job['id']);assert preview.status_code==200
    request={**body(e),'reviewed_capture_digest':preview.json()['capture_digest']}
    response=client.post(root,json=request);assert response.status_code==201,response.text
    result=response.json();download=client.get(root+'/'+result['id']+'/export')
    assert download.status_code==200 and download.json()==result and download.headers['cache-control']=='no-store'
    assert client.get(root+'/'+result['id']).json()==result
    for permissions in ({'domain.write'}, {'domain.read'}):
        state['permissions']=permissions;before=files(e)
        assert client.post(root,json=request).status_code==403 and files(e)==before
    state['permissions']={'domain.write'}
    assert client.get(root+'/'+result['id']+'/export').status_code==403
    state['permissions']={'domain.read','domain.write'};state['host']=False
    assert client.get(root).status_code==403

def test_file_dedicated_api_no_host_principal_or_adapter_fails_closed(approved):
    e=approved;client,_,root=api(e,principal=False);before=files(e)
    assert client.get(root+'/results').status_code==403 and files(e)==before
    app=FastAPI();app.include_router(create_audio_manifest_router(e.production,None));client=TestClient(app)
    assert client.get(root).status_code==403 and files(e)==before

def test_validation_error_422_keeps_private_body_and_security_headers():
    def forbidden(*args,**kwargs):
        raise AssertionError('Invalid request must not reach Host or owner')
    app=FastAPI()
    app.include_router(create_audio_manifest_router(SimpleNamespace(store=None,workspace=None),forbidden))
    response=TestClient(app).post('/novels/synthetic-project/experimental/production/audio-manifests',json={
        'job_id':'synthetic-job','expected_job_version':1,'reviewed_capture_digest':'a'*64,
        'request_id':'header-regression','confirmed':True,'prompt':'synthetic-private-do-not-echo'})
    assert response.status_code==422
    assert response.json()=={'detail':{'code':'AUDIO_MANIFEST_REQUEST_INVALID'}}
    assert response.headers['content-type'].startswith('application/json')
    assert response.headers['cache-control']=='no-store'
    assert response.headers.get('x-content-type-options')=='nosniff'
    assert 'synthetic-private-do-not-echo' not in response.text
