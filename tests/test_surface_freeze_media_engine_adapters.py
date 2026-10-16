"""Surface-freeze contracts: synthetic local media; real File/PG persistence.

PostgreSQL parameters run only in the real PostgreSQL profile. Target engines,
real ASR/alignment models, GPU pipelines and render quality remain NOT_RUN.
"""
import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import json
import subprocess
import threading
from types import SimpleNamespace
import zipfile

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from post_interop_media_fixture_support import rig
from test_r3_media_support import audio_asset, branch_scope
from app.experimental.common import StaleSourceError
from app.experimental.flags import FLAGS, require_flag
from app.experimental.interactive_story import (InteractiveStoryService, GodotExportAdapter, GodotStoryResource,
    StorySpec, validate_condition_tree)
from app.experimental.interactive_story_api import create_interactive_story_router
from app.experimental.planning import PlanningService
from app.experimental.story_graph import StoryGraphService
from app.experimental.store import ExperimentalStore
from app.experimental.subtitle_processing import ProcessingDefinition, ProcessingResult, ProcessingCreateIn
from app.experimental.subtitle_timeline import SubtitleTimelineService
from app.experimental.subtitle_timeline_api import create_subtitle_timeline_router
from app.experimental.voice_direction import DirectedAudiobookService
from app.services.v1_capability_service import CapabilityVersionConflict


class SyntheticAdapter:
    definition = ProcessingDefinition('test.synthetic.captions', '1', ('ASR', 'FORCED_ALIGNMENT', 'BURN_IN'), verification='MOCK_ONLY')
    def __init__(self, callback=None): self.calls = []; self.callback = callback
    def process(self, request):
        self.calls.append(request)
        if self.callback: self.callback(request)
        request.guard()
        if request.operation == 'BURN_IN':
            # Byte-preserving fixture exercises fences and receipt validation,
            # explicitly not an actual subtitle renderer or quality evidence.
            return ProcessingResult(content=request.media, media_type=request.media_type)
        return ProcessingResult(cues=({'id': 'synthetic-1', 'start_tick': 0, 'end_tick': 800,
            'text': request.transcript if request.operation == 'FORCED_ALIGNMENT' else 'Synthetic recognition'},))


@pytest.fixture
def env(rig, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    voice = DirectedAudiobookService(rig.store, rig.novels, rig.chapters, assets=rig.assets)
    adapter = SyntheticAdapter()
    service = SubtitleTimelineService(rig.store, rig.novels, rig.chapters, voice, rig.assets, (adapter,))
    asset = audio_asset(rig, 2000)
    caption = service.create_track(rig.nid, rig.scope, rig.actor, {'asset_id': asset['id'], 'cues': []})
    return SimpleNamespace(rig=rig, voice=voice, service=service, adapter=adapter, caption=caption)


def queue(e, operation='ASR', **kw):
    return e.service.queue_processing(e.rig.nid, e.rig.scope, e.rig.actor, {
        'caption_id': e.caption['id'], 'expected_caption_version': e.caption['version'],
        'adapter_id': e.adapter.definition.adapter_id, 'operation': operation, **kw})


def action(e, row, verb, **kw):
    return e.service.processing_action(e.rig.nid, e.rig.scope, e.rig.actor, row['id'], verb, {'expected_version': row['version'], **kw})


def client(e, prefix='/api'):
    authority = {'actor': e.rig.actor, 'allowed': True, 'review': True}
    def authorize(nid, token, branch, permission):
        if not authority['allowed'] or token != 'owner' or nid != e.rig.nid or (permission == 'domain.review' and not authority['review']):
            raise HTTPException(403, 'denied')
        return authority['actor'], branch_scope(e.rig, branch) if branch else e.rig.scope
    app = FastAPI(); app.include_router(create_subtitle_timeline_router(e.service, authorize, require_flag), prefix=prefix)
    return TestClient(app, headers={'X-Session-Token': 'owner'}), authority, prefix + f'/novels/{e.rig.nid}/experimental/subtitle-timeline'


def test_asr_review_updates_original_caption_atomically_and_restart_preserves_owner(env):
    e = env; before = e.rig.chapters.get(e.rig.chapter['id']); task = queue(e)
    output = action(e, task, 'execute')
    assert output['status'] == 'NEEDS_REVIEW' and output['runtime_verification'] == 'NOT_RUN'
    assert output['verification'] == 'MOCK_ONLY' and len(e.adapter.calls) == 1
    assert e.service.records(e.rig.nid, e.rig.scope, e.rig.actor)['items'][0]['cues'] == []
    assert 'content_base64' not in json.dumps(output) and 'transcript' not in output
    approved = action(e, output, 'approve', preview_digest=output['preview_digest'])
    assert approved['status'] == 'APPROVED' and approved['applied_caption_version'] == 2
    restarted = SubtitleTimelineService(ExperimentalStore(e.rig.root, e.rig.backend, e.rig.store.database_url), e.rig.novels,
        e.rig.chapters, e.voice, e.rig.assets)
    caption = restarted.records(e.rig.nid, e.rig.scope, e.rig.actor)['items'][0]
    assert caption['id'] == e.caption['id'] and caption['version'] == 2 and caption['status'] == 'APPROVED'
    assert caption['timing_origin'] == 'SYNTHETIC_FIXTURE' and caption['history'][0]['cues'] == []
    assert len(restarted.processing_tasks(e.rig.nid, e.rig.scope, e.rig.actor)['items']) == 1
    assert b'Synthetic recognition' in restarted.download(e.rig.nid, e.rig.scope, e.rig.actor, caption['id'], 2, 'vtt')
    assert e.rig.chapters.get(e.rig.chapter['id']) == before
    with pytest.raises(CapabilityVersionConflict): action(e, output, 'approve', preview_digest=output['preview_digest'])
    edited = restarted.update(e.rig.nid, e.rig.scope, e.rig.actor, caption['id'], {'expected_version': 2, 'cues': caption['cues']})
    assert edited['status'] == 'DRAFT' and edited['timing_origin'] == 'MANUAL'


def test_alignment_exact_transcript_validation_and_invalid_output_discard(env):
    e = env; task = queue(e, 'FORCED_ALIGNMENT', transcript='Words for alignment')
    output = action(e, task, 'execute'); assert output['result']['cues'][0]['text'] == 'Words for alignment'
    rejected = action(e, output, 'reject', preview_digest=output['preview_digest']); assert rejected['status'] == 'REJECTED'
    class Bad(SyntheticAdapter):
        def process(self, request): return ProcessingResult(cues=({'id':'bad','start_tick':0,'end_tick':800,'text':'different transcript'},))
    e.service._processing_adapters[e.adapter.definition.adapter_id] = Bad()
    task = queue(e, 'FORCED_ALIGNMENT', transcript='Must remain verbatim')
    with pytest.raises(ValueError, match='TRANSCRIPT_CHANGED'): action(e, task, 'execute')
    row = next(r for r in e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)['items'] if r['id'] == task['id'])
    assert row['status'] == 'FAILED' and row['error_code'] == 'PROCESSING_OUTPUT_DISCARDED' and 'result' not in row
    with pytest.raises(ValidationError): ProcessingCreateIn(caption_id='c',expected_caption_version=1,adapter_id='a',operation='FORCED_ALIGNMENT')
    with pytest.raises(ValidationError): ProcessingCreateIn(caption_id='c',expected_caption_version=1,adapter_id='a',operation='ASR',endpoint='https://invalid')


def test_missing_configuration_is_persisted_and_no_silent_mock_fallback(env):
    e=env; e.service._processing_adapters.clear(); task=queue(e)
    assert task['status']=='NOT_CONFIGURED' and e.adapter.calls==[]
    assert {r['status'] for r in e.service.processing_catalog()['operations']}=={'NOT_CONFIGURED'}
    with pytest.raises(ValueError,match='QUEUED'): action(e,task,'execute')
    e.service._processing_adapters[e.adapter.definition.adapter_id]=e.adapter
    task=action(e,task,'resume'); assert task['status']=='QUEUED'
    task=action(e,task,'cancel'); assert task['status']=='CANCELLED' and e.adapter.calls==[]
    with pytest.raises(ValueError): action(e,task,'execute')
    task=action(e,task,'resume'); assert action(e,task,'execute')['status']=='NEEDS_REVIEW'
    with pytest.raises(ValueError,match='TRUSTED_LOCAL'):
        bad=SyntheticAdapter(); bad.definition=replace(bad.definition,local=False)
        SubtitleTimelineService(e.rig.store,e.rig.novels,e.rig.chapters,e.voice,e.rig.assets,(bad,))


def test_cancel_during_adapter_fences_late_output(env):
    e=env; task=queue(e)
    def cancel(request):
        running=e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)['items'][0]
        action(e,running,'cancel')
    e.adapter.callback=cancel
    with pytest.raises(ValueError,match='CANCELLED'): action(e,task,'execute')
    row=e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)['items'][0]
    assert row['status']=='CANCELLED' and 'result' not in row
    assert e.service.records(e.rig.nid,e.rig.scope,e.rig.actor)['items'][0]['cues']==[]


def test_interrupted_restart_requires_recover_then_resume_and_no_replay(env):
    e=env; task=queue(e)
    def interrupt(request): raise KeyboardInterrupt('synthetic process interruption')
    e.adapter.callback=interrupt
    with pytest.raises(KeyboardInterrupt): action(e,task,'execute')
    e.service=SubtitleTimelineService(ExperimentalStore(e.rig.root,e.rig.backend,e.rig.store.database_url),e.rig.novels,e.rig.chapters,e.voice,e.rig.assets,(e.adapter,))
    row=e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)['items'][0]
    assert row['status']=='RUNNING' and row['recovery_required'] and len(e.adapter.calls)==1
    with pytest.raises(ValueError,match='RESUME_INVALID'):action(e,row,'resume')
    row=action(e,row,'recover');assert row['status']=='INTERRUPTED'
    row=action(e,row,'resume');e.adapter.callback=None
    assert action(e,row,'execute')['status']=='NEEDS_REVIEW' and len(e.adapter.calls)==2


def test_source_drift_and_other_actor_branch_withhold_results(env):
    e=env; task=queue(e); output=action(e,task,'execute')
    assert e.service.processing_tasks(e.rig.nid,e.rig.scope,'other')['items']==[]
    for actor,scope in [('other',e.rig.scope),(e.rig.actor,branch_scope(e.rig))]:
        with pytest.raises(FileNotFoundError):e.service.processing_action(e.rig.nid,scope,actor,task['id'],'cancel',{'expected_version':output['version']})
    e.rig.assets.update_metadata(e.caption['asset_id'],{'model_id':'new-source-version'})
    rows=e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)['items']
    assert rows[0]['stale'] and rows[0]['content_withheld'] and 'result' not in rows[0]
    with pytest.raises(StaleSourceError):action(e,output,'approve',preview_digest=output['preview_digest'])
    assert action(e,output,'cancel')['status']=='CANCELLED'


def test_queue_and_review_reauthorization_rollback(env):
    e=env; before=e.rig.store.read(e.rig.nid,e.rig.scope); calls=[]
    def revoke():
        calls.append(1)
        if len(calls)==2:raise HTTPException(403,'revoked')
    with pytest.raises(HTTPException):e.service.queue_processing(e.rig.nid,e.rig.scope,e.rig.actor,{'caption_id':e.caption['id'],'expected_caption_version':1,'adapter_id':e.adapter.definition.adapter_id,'operation':'ASR'},revoke)
    assert e.rig.store.read(e.rig.nid,e.rig.scope)==before
    task=queue(e); output=action(e,task,'execute');before=e.rig.store.read(e.rig.nid,e.rig.scope);calls.clear()
    with pytest.raises(HTTPException):e.service.processing_action(e.rig.nid,e.rig.scope,e.rig.actor,output['id'],'approve',{'expected_version':output['version'],'preview_digest':output['preview_digest']},revoke)
    assert e.rig.store.read(e.rig.nid,e.rig.scope)==before


@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_mounted_api_permissions_conflict_flags_schema_and_states(env,monkeypatch,prefix):
    e=env;c,auth,base=client(e,prefix)
    catalog=c.get(base+'/processing/catalog');assert catalog.status_code==200 and catalog.headers['cache-control']=='no-store'
    assert set(catalog.json()['surface']['states'])>={'LOADING','EMPTY','ERROR','UNAUTHORIZED','NOT_CONFIGURED','DISABLED','CONFLICT','REVIEW','RECOVERY'}
    body={'caption_id':e.caption['id'],'expected_caption_version':1,'adapter_id':e.adapter.definition.adapter_id,'operation':'ASR'}
    queued=c.post(base+'/processing/tasks',json=body);assert queued.status_code==201,queued.text
    task=queued.json();path=base+'/processing/tasks/'+task['id']
    conflict=c.post(path+'/execute',json={'expected_version':99});assert conflict.status_code==409
    assert 'asset_snapshot' not in conflict.text and 'caption_id' not in conflict.text
    output=c.post(path+'/execute',json={'expected_version':task['version']}).json()
    auth['review']=False
    review={'expected_version':output['version'],'preview_digest':output['preview_digest']}
    assert c.post(path+'/approve',json=review).status_code==403
    auth['review']=True;assert c.post(path+'/approve',json=review).status_code==200
    auth['actor']='other';assert c.get(base+'/processing/tasks').json()['items']==[]
    auth['allowed']=False;assert c.get(base+'/processing/catalog').status_code==403
    auth['allowed']=True
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2');assert c.get(base+'/processing/tasks').status_code==404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(FLAGS));monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert c.get(base+'/processing/catalog').status_code==404


def test_permission_revocation_during_processing_discards_result(env):
    e=env;c,auth,base=client(e);task=queue(e)
    e.adapter.callback=lambda request:auth.update(allowed=False)
    response=c.post(base+'/processing/tasks/'+task['id']+'/execute',json={'expected_version':task['version']})
    assert response.status_code==403 and len(e.adapter.calls)==1
    row=e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)['items'][0]
    assert row['status']=='FAILED' and 'result' not in row


def test_concurrent_execution_has_one_claim_and_one_adapter_call(env):
    e=env;task=queue(e);barrier=threading.Barrier(3);outcomes=[]
    def execute():
        barrier.wait()
        try:action(e,task,'execute');outcomes.append('executed')
        except CapabilityVersionConflict:outcomes.append('conflict')
    threads=[threading.Thread(target=execute) for _ in range(2)]
    for thread in threads:thread.start()
    barrier.wait()
    for thread in threads:thread.join(20);assert not thread.is_alive()
    assert sorted(outcomes)==['conflict','executed'] and len(e.adapter.calls)==1


def test_burn_in_synthetic_fixture_requires_review_before_download(env,tmp_path):
    e=env; path=tmp_path/'synthetic.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=blue:s=32x32:r=10:d=1','-c:v','mpeg4','-y',str(path)],check=True,timeout=20)
    content=path.read_bytes(); asset=e.rig.assets.create(e.rig.nid,'synthetic.mp4',base64.b64encode(content).decode(),'video/mp4','video')
    e.caption=e.service.create_track(e.rig.nid,e.rig.scope,e.rig.actor,{'asset_id':asset['id'],'cues':[{'id':'one','start_tick':0,'end_tick':800,'text':'Synthetic subtitle'}]})
    task=queue(e,'BURN_IN');output=action(e,task,'execute')
    assert output['result']['render_verification']=='MOCK_ONLY' and output['result']['sha256']==hashlib.sha256(content).hexdigest()
    with pytest.raises(ValueError,match='APPROVED_RENDER'):e.service.processing_download(e.rig.nid,e.rig.scope,e.rig.actor,task['id'],output['version'])
    approved=action(e,output,'approve',preview_digest=output['preview_digest'])
    actual,mime=e.service.processing_download(e.rig.nid,e.rig.scope,e.rig.actor,task['id'],approved['version'])
    assert actual==content and mime=='video/mp4'
    persisted=e.rig.store.read(e.rig.nid,e.rig.scope)['collections'][e.service.PROCESSING][task['id']]
    assert all('result' not in old and 'transcript' not in old for old in persisted['history'])
    assert persisted['history'][-1]['result_digest']
    assert 'content_base64' not in json.dumps(e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor))


@pytest.fixture
def story(env):
    e=env.rig;planning=PlanningService(e.store,e.novels,e.chapters);graph=StoryGraphService(e.store,e.novels,e.chapters)
    service=InteractiveStoryService(e.store,e.novels,e.chapters,planning,graph,e.assets)
    plan=planning.create_graph(e.nid,e.scope,e.actor,{'title':'Synthetic engine fixture','links':{'chapter_ids':[e.chapter['id']]}})
    last=planning.create_node(e.nid,e.scope,e.actor,{'graph_id':plan['id'],'parent_id':plan['root_node_id'],'level':'VOLUME','title':'End'})
    spec=StorySpec.model_validate({'title':'Safe [literal] {markup}','graph_id':plan['id'],'graph_version':1,'entry_node_id':plan['root_node_id'],
        'variables':[{'name':'ready','type':'bool','initial':True}], 'nodes':[
            {'node_id':plan['root_node_id'],'node_version':1,'title':'Start','dialogue':'Literal content','choices':[{'id':'next','label':'Next','target':last['id'],'condition':'ready','assignments':{'ready':False}}]},
            {'node_id':last['id'],'node_version':1,'title':'End','ending':'Done'}]}).model_dump()
    row=service.create_story(e.nid,e.scope,e.actor,{'spec':spec})
    row=service.review(e.nid,e.scope,e.actor,row['id'],{'expected_version':1,'action':'submit'})
    preview=service.review_preview(e.nid,e.scope,e.actor,row['id'],{'expected_version':row['version']})
    row=service.review(e.nid,e.scope,e.actor,row['id'],{'expected_version':row['version'],'action':'approve','preview_digest':preview['preview_digest']})
    return SimpleNamespace(rig=e,service=service,row=row,spec=spec)


def test_godot_and_renpy_export_share_existing_review_source_receipt_and_checksums(story):
    e=story;value={'expected_version':e.row['version']};p=e.service.export_preview(e.rig.nid,e.rig.scope,e.rig.actor,e.row['id'],value)
    output=e.service.export(e.rig.nid,e.rig.scope,e.rig.actor,e.row['id'],{**value,'preview_digest':p['preview_digest']})
    assert output['target_runtime']=='NOT_RUN'
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(output['content_base64']))) as archive:
        prefix='interactive-story-'+e.row['id']+'/'
        godot=GodotStoryResource.model_validate_json(archive.read(prefix+'godot/story.json'))
        assert godot.entry_index==0 and godot.nodes[0].choices[0].target_index==1
        assert godot.nodes[0].choices[0].condition_tree.model_dump()=={'op':'var','name':'ready'}
        assert godot.runtime_verification=='NOT_RUN' and godot.importer_status=='TARGET_INTEGRATION_REQUIRED'
        assert archive.read(prefix+'game/story.rpy').startswith(b'# AI-Novel-Studio')
        schema=json.loads(archive.read(prefix+'godot/story.schema.json'));assert not schema['additionalProperties']
        for name,sha in json.loads(archive.read(prefix+'checksums.json')).items():assert hashlib.sha256(archive.read(prefix+name)).hexdigest()==sha
    contract=e.service.engine_contract();assert 'GODOT_4_DATA_ADAPTER' in contract['supported_targets']
    assert contract['third_party_execution']=='DENY_ALL'
    e.rig.chapters.save(e.rig.chapter['id'],{'version':e.rig.chapter['version'],'content':'Changed source'})
    with pytest.raises(StaleSourceError):e.service.export(e.rig.nid,e.rig.scope,e.rig.actor,e.row['id'],{**value,'preview_digest':p['preview_digest']})


def test_godot_data_validator_rejects_code_foreign_targets_and_invalid_assignments(story):
    data=GodotExportAdapter().resource(story.spec,{})
    for change in ['target','expression','assignment','extra']:
        value=deepcopy(data);choice=value['nodes'][0]['choices'][0]
        if change=='target':choice['target_index']=99
        elif change=='expression':choice['condition_tree']={'op':'call','function':'load','path':'secret'}
        elif change=='assignment':choice['assignments']={'ready':1}
        else:value['script']='load("https://invalid")'
        with pytest.raises((ValidationError,ValueError)):GodotStoryResource.model_validate(value)
    for value in [{'op':'var','name':'x.y'},{'op':'literal','value':10001},{'op':'and','args':[]}]:
        with pytest.raises(ValueError):validate_condition_tree(value)


def test_original_media_operation_schema_has_post_and_sound_design_boundaries():
    from app.experimental.media import MediaOperationInput, MediaAdapterRegistry
    values=[{'operation':'upscale','source_asset_id':'video','upscale_factor':2},
        {'operation':'frame_interpolation','source_asset_id':'video','target_fps':48},
        *[{'operation':op,'prompt':'Synthetic intention','duration_seconds':2} for op in ['background_music','ambience','sound_effect']]]
    for value in values:
        assert MediaOperationInput.model_validate(value).operation==value['operation']
        with pytest.raises(ValidationError):MediaOperationInput.model_validate({'operation':value['operation']})
    with pytest.raises(ValidationError):MediaOperationInput.model_validate({'operation':'upscale','source_asset_id':'video','upscale_factor':True})
    definitions=MediaAdapterRegistry(include_mock=False).definitions()
    assert definitions['real_model_verification']=='NOT_RUN'
    assert definitions['execution_boundary']['third_party_execution']=='DENY_ALL'
    assert {'qwen-image','flux','minimax-h3','wan','ltx','seedvr2','rife'}<={r['adapter_id'] for r in definitions['items']}
    assert all(not row['runnable'] and row['state']=='ADAPTER_REQUIRED' for row in definitions['items'])
    assert next(row for row in definitions['items'] if row['adapter_id']=='seedvr2')['operations']==['upscale']
    assert next(row for row in definitions['items'] if row['adapter_id']=='rife')['operations']==['frame_interpolation']


# Actual production composition uses the real trusted-session and membership
# authority. The adapter injection is synthetic; authorization is not mocked.
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r3_media_support import wav_bytes


def test_production_mounted_processing_real_membership_and_origin_flags(mounted, monkeypatch):
    e=scoped(mounted,monkeypatch); service=e.experimental.subtitle_timeline_service;adapter=SyntheticAdapter()
    monkeypatch.setattr(service,'_processing_adapters',{adapter.definition.adapter_id:adapter})
    asset=e.assets.create(e.nid,'branch.wav',base64.b64encode(wav_bytes(2000)).decode(),'audio/wav','audio',branch_id=e.branch)
    base=e.base+'/subtitle-timeline'
    caption=checked(e.client.post(base+'/records',headers=e.headers,json={'asset_id':asset['id'],'cues':[]}),201)
    body={'caption_id':caption['id'],'expected_caption_version':1,'adapter_id':adapter.definition.adapter_id,'operation':'ASR'}
    assert e.client.post(base+'/processing/tasks',headers=e.viewer_headers,json=body).status_code==403
    task=checked(e.client.post(base+'/processing/tasks',headers=e.headers,json=body),201)
    path=base+'/processing/tasks/'+task['id']
    output=checked(e.client.post(path+'/execute',headers=e.headers,json={'expected_version':task['version']}))
    assert output['status']=='NEEDS_REVIEW' and len(adapter.calls)==1
    assert checked(e.client.get(base+'/processing/tasks',headers=e.viewer_headers))['items']==[]
    body={'expected_version':output['version'],'preview_digest':output['preview_digest']}
    assert e.client.post(path+'/approve',headers=e.viewer_headers,json=body).status_code==403
    assert e.client.get(base+'/processing/tasks',headers={**e.headers,'X-Branch-ID':e.other_branch}).status_code==403
    approved=checked(e.client.post(path+'/approve',headers=e.headers,json=body));assert approved['status']=='APPROVED'
    e.authorization.revoke_role(e.role,e.lead)
    assert e.client.get(base+'/processing/tasks',headers=e.headers).status_code==403
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2')
    assert e.client.get(base+'/processing/catalog',headers=e.headers).status_code==404


def test_production_mounted_engine_contract_and_archive_source_fences(mounted):
    from test_r5_interactive_story_mounted import create,approve
    e=mounted; row,_=create(e); row=approve(e,row);base=e.base+'/interactive-stories'
    contract=checked(e.client.get(base+'/engine-contract'));assert 'GODOT_4_DATA_ADAPTER' in contract['supported_targets']
    body={'expected_version':row['version']}
    preview=checked(e.client.post(base+'/'+row['id']+'/export-preview',json=body))
    output=checked(e.client.post(base+'/'+row['id']+'/export',json={**body,'preview_digest':preview['preview_digest']}))
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(output['content_base64']))) as archive:
        assert any(name.endswith('/godot/story.json') for name in archive.namelist())
    archived=checked(e.client.post(base+'/'+row['id']+'/review',json={**body,'action':'archive'}))
    assert archived['status']=='ARCHIVED'
    assert not checked(e.client.post(base+'/'+row['id']+'/export-preview',json={'expected_version':archived['version']}))['can_export']


def test_real_model_adapter_requires_original_runtime_admission(env):
    e=env; e.adapter.definition=replace(e.adapter.definition,verification='CONTRACT_VERIFIED')
    task=queue(e)
    assert task['status']=='NOT_CONFIGURED' and e.adapter.calls==[]
    with pytest.raises(ValueError):action(e,task,'execute')
    with pytest.raises(ValueError,match='NOT_CONFIGURED'):action(e,task,'resume')
    catalog=e.service.processing_catalog()
    assert next(row for row in catalog['operations'] if row['operation']=='ASR')['status']=='NOT_CONFIGURED'
    assert catalog['model_runtime_admission']=='NOT_CONFIGURED_ORIGINAL_MEDIA_RUNTIME_REQUIRED'


def test_media_audio_use_true_branch_manuscript_and_ignore_mainline_changes(env,monkeypatch):
    from app.services.branch_manuscript_service import BranchManuscriptService
    from app.experimental.ux import ReadContext
    from app.experimental.media import MediaService
    from app.document import markdown_to_document
    e=env;r=e.rig;scope=branch_scope(r,'synthetic-media-branch')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join([*FLAGS,'branch_manuscript_v1']))
    owner=BranchManuscriptService(r.store,r.novels,r.chapters)
    monkeypatch.setattr(r.chapters,'branch_authority',owner.for_scope,raising=False)
    ctx=ReadContext(r.nid,scope,r.actor,None,scope['branch_id'])
    preview=owner.preview_fork(ctx,r.scope,[r.chapter['id']])
    fork=owner.apply_fork(ctx,preview['id'],preview['version'],preview['preview_digest'],True)
    cid=fork['id_map'][r.chapter['id']]
    owner.save(ctx,cid,markdown_to_document('Branch-specific spoken prose.'),1)
    plan=e.voice.create_plan(r.nid,scope,r.actor,{'chapter_id':cid})
    assert plan['sources'][cid]['scope']==scope and plan['sources'][cid]['version']==2
    assert ''.join(segment['text'] for segment in plan['segments'])=='Branch-specific spoken prose.'
    media=MediaService(r.store,r.novels,r.chapters,r.assets,r.screenplays)
    brief=media.create_cover(r.nid,scope,r.actor,{'title':'Branch cover','chapter_ids':[cid]})
    assert brief['sources'][cid]['scope']==scope
    r.chapters.save(r.chapter['id'],{'version':r.chapter['version'],'content':'Independent mainline replacement'})
    def forbidden_mainline_read(cid):raise AssertionError('branch media must never read mainline')
    monkeypatch.setattr(r.chapters,'get',forbidden_mainline_read)
    legacy_plan=deepcopy(plan);legacy_plan['sources'][cid].pop('scope')
    e.voice._assert_plan(r.nid,scope,legacy_plan)
    e.voice._assert_plan(r.nid,scope,plan)
    assert not media.briefs(r.nid,scope,'COVER')[0]['stale']
    with pytest.raises(StaleSourceError,match='BRANCH_SOURCE_ADAPTER_REQUIRED'):e.voice.create_plan(r.nid,scope,r.actor,{'chapter_id':r.chapter['id']})
    owner.save(ctx,cid,markdown_to_document('Changed branch prose.'),2)
    with pytest.raises(StaleSourceError):e.voice._assert_plan(r.nid,scope,plan)
    assert media.briefs(r.nid,scope,'COVER')[0]['stale']


@pytest.mark.parametrize('exception',[ValueError,RuntimeError,StaleSourceError,lambda text:HTTPException(403,text)])
def test_adapter_exception_never_leaks_provider_text_to_http_or_task(env,exception):
    e=env;task=queue(e);c,_,base=client(e)
    def failure(request):raise exception('PRIVATE_PROVIDER_SENTINEL /private/provider/path secret-prompt')
    e.adapter.callback=failure
    response=c.post(base+'/processing/tasks/'+task['id']+'/execute',json={'expected_version':task['version']})
    assert response.status_code==422 and 'PROCESSING_OUTPUT_DISCARDED' in response.text
    assert 'PRIVATE_PROVIDER_SENTINEL' not in response.text and '/private/provider/path' not in response.text
    rows=e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)
    assert 'PRIVATE_PROVIDER_SENTINEL' not in json.dumps(rows)
    assert rows['items'][0]['status']=='FAILED'


def test_godot_retains_exact_reviewed_dialogue_and_ending_whitespace(story):
    spec=deepcopy(story.spec)
    spec['nodes'][0]['dialogue']='  Leading line\nTrailing line  \n'
    spec['nodes'][1]['ending']='  Exact ending\n'
    result=GodotExportAdapter().resource(spec,{})
    assert result['nodes'][0]['text']==spec['nodes'][0]['dialogue']
    assert result['nodes'][1]['ending']==spec['nodes'][1]['ending']
    files=GodotExportAdapter().files(spec,{})
    decoded=json.loads(files['godot/story.json'])
    assert decoded['nodes'][0]['text']==spec['nodes'][0]['dialogue']


def test_unified_task_center_projects_original_processing_owner_and_cancels_with_receipt(mounted,monkeypatch):
    e=mounted;service=e.experimental.subtitle_timeline_service
    monkeypatch.setattr(service,'_processing_adapters',{})
    asset=e.assets.create(e.nid,'local.wav',base64.b64encode(wav_bytes(2000)).decode(),'audio/wav','audio')
    base=e.base+'/subtitle-timeline'
    caption=checked(e.client.post(base+'/records',json={'asset_id':asset['id'],'cues':[]}),201)
    task=checked(e.client.post(base+'/processing/tasks',json={'caption_id':caption['id'],'expected_caption_version':1,'adapter_id':'not-configured','operation':'ASR'}),201)
    assert task['status']=='NOT_CONFIGURED'
    tasks=checked(e.client.get(e.base+'/workspace/tasks'))
    row=next(r for r in tasks['items'] if r['authority']=='subtitle_processing' and r['id']==task['id'])
    assert row['source']=={'kind':'feature','id':task['id'],'feature':'subtitle_timeline_v2','task_authority':'subtitle_processing'}
    assert 'cancel' in row['actions'] and 'transcript' not in json.dumps(row) and 'asset_snapshot' not in row
    url=e.base+'/workspace/tasks/subtitle_processing/'+task['id']+'/cancel'
    assert e.client.post(url,json={'expected_revision':'0'*64}).status_code==409
    cancelled=checked(e.client.post(url,json={'expected_revision':row['revision']}))
    assert cancelled['cancellation_requested'] and cancelled['executor'] is False and cancelled['item']['status']=='CANCELLED'
    original=checked(e.client.get(base+'/processing/tasks'))['items'][0]
    assert original['id']==task['id'] and original['status']=='CANCELLED' and original['version']==2
    assert checked(e.client.get(base+'/records'))['items'][0]['version']==1
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2,workspace_tools_v2')
    assert not any(r['authority']=='subtitle_processing' for r in checked(e.client.get(e.base+'/workspace/tasks'))['items'])


def test_unified_review_inbox_keeps_exact_result_approval_with_original_subtitle_owner(mounted,monkeypatch):
    e=mounted;service=e.experimental.subtitle_timeline_service;adapter=SyntheticAdapter()
    monkeypatch.setattr(service,'_processing_adapters',{adapter.definition.adapter_id:adapter})
    asset=e.assets.create(e.nid,'local.wav',base64.b64encode(wav_bytes(2000)).decode(),'audio/wav','audio')
    base=e.base+'/subtitle-timeline'
    caption=checked(e.client.post(base+'/records',json={'asset_id':asset['id'],'cues':[]}),201)
    task=checked(e.client.post(base+'/processing/tasks',json={'caption_id':caption['id'],'expected_caption_version':1,'adapter_id':adapter.definition.adapter_id,'operation':'ASR'}),201)
    output=checked(e.client.post(base+'/processing/tasks/'+task['id']+'/execute',json={'expected_version':task['version']}))
    inbox=checked(e.client.get(e.base+'/review-inbox',params={'domain':'subtitle_processing'}))
    assert inbox['approval_authority']=='DOMAIN_SERVICE' and inbox['total']==1
    row=inbox['items'][0]
    assert row['id']==task['id'] and row['version']==output['version'] and row['domain']=='subtitle_processing'
    assert row['target']=={'domain':'subtitle_timeline_v2','id':task['id']} and row['allowed_actions']==[] and not row['batch_safe']
    assert 'result' not in row and 'content_base64' not in json.dumps(row)
    assert e.client.post(e.base+'/review-inbox/subtitle_processing/'+task['id']+'/approve',json={'expected_version':row['version']}).status_code==422
    assert checked(e.client.get(base+'/records'))['items'][0]['cues']==[]
    approved=checked(e.client.post(base+'/processing/tasks/'+task['id']+'/approve',json={'expected_version':output['version'],'preview_digest':output['preview_digest']}))
    assert approved['status']=='APPROVED'
    assert checked(e.client.get(e.base+'/review-inbox',params={'domain':'subtitle_processing'}))['total']==0


@pytest.mark.parametrize('ticks',[{'start_tick':False,'end_tick':800},{'start_tick':0,'end_tick':800.0}])
def test_adapter_output_requires_exact_integer_cue_ticks(env,ticks):
    e=env
    class Invalid(SyntheticAdapter):
        def process(self,request):return ProcessingResult(cues=({'id':'invalid','text':'No coerced timing',**ticks},))
    e.service._processing_adapters[e.adapter.definition.adapter_id]=Invalid()
    task=queue(e)
    with pytest.raises(ValueError,match='INTEGER_TICKS'):action(e,task,'execute')
    assert e.service.processing_tasks(e.rig.nid,e.rig.scope,e.rig.actor)['items'][0]['status']=='FAILED'


def test_task_limit_and_attempt_limit_do_not_block_cancellation(env,monkeypatch):
    import app.experimental.subtitle_processing as processing
    e=env;monkeypatch.setattr(processing,'MAX_TASKS',1);task=queue(e)
    with pytest.raises(ValueError,match='TASK_LIMIT'):queue(e)
    task=action(e,task,'cancel')
    assert task['status']=='CANCELLED'
    with e.rig.store.transaction(e.rig.nid,e.rig.scope) as state:
        state['collections'][e.service.PROCESSING][task['id']]['attempt']=processing.MAX_ATTEMPTS
    with pytest.raises(ValueError,match='ATTEMPT_LIMIT'):action(e,task,'resume')
    assert len(e.adapter.calls)==0


def test_godot_exported_json_schema_rejects_executable_condition_shape(story):
    import jsonschema
    resource=GodotExportAdapter().resource(story.spec,{})
    schema=GodotStoryResource.model_json_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(resource,schema)
    resource['nodes'][0]['choices'][0]['condition_tree']={'op':'call','function':'load'}
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(resource,schema)
