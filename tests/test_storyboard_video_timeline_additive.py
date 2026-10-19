"""Original reviewed job/asset owners and decoded CPU WEBM; no real model."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.creative.production_execution_models import MediaReview
from app.creative.production_execution import TIMELINES
from app.creative.storyboard_video_timeline import VideoTimelineInput, validate_video_creation_receipt
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig, reopened
from test_v2_storyboard_workspace import board_value, approve, content
from test_v2_video_runtime_foundation import configured, queued, action


@pytest.fixture
def videos(rig, tmp_path, monkeypatch, request):
    e = rig; discovery, production, adapter, wire, command = configured(e, tmp_path, monkeypatch)
    creative = e.service.creative; value = board_value()
    for number in range(3, getattr(request, 'param', 2) + 1):
        value['shots'].append({**deepcopy(value['shots'][1]), 'id':f'shot-{number}', 'number':number, 'continuity':{}})
    row = creative.create(e.nid, e.scope, e.actor, value)
    receipt = approve(creative, e, row['id'])
    for shot_id in [shot['id'] for shot in value['shots']]:
        shot = next(shot for shot in receipt['shots'] if shot['shot_id'] == shot_id)
        prepared = creative.storyboards.video_request(e.nid, e.scope, e.actor, row['id'], shot_id,
            {'expected_version': receipt['document_snapshot']['version'], 'shot_version': shot['shot_version'], 'shot_digest': shot['shot_digest'],
             'operation_id': 'm7.video.t2v', 'request_id': 'cpu-' + shot_id,
             'provider': {key: command[key] for key in ('operation_id','provider_id','model_id')}, 'parameters': {'width':64,'height':64,'frame_rate':8}})
        _, job = queued(e, production, prepared['command']); job = production.execute(e.nid,e.scope,e.actor,'video',job['id'],action(job),lambda:None)
        job = production.refresh_video(e.nid,e.scope,e.actor,job['id'],action(job),lambda:None)
        job = production.review(e.nid,e.scope,e.actor,'video',job['id'],MediaReview(**action(job).model_dump(),reviewed_output_digest=job['output_candidate']['digest']),lambda:None)
        creative.storyboards.bind_video(e.nid,e.scope,e.actor,row['id'],shot_id,{'expected_version':receipt['document_snapshot']['version'],
            'shot_version':shot['shot_version'],'shot_digest':shot['shot_digest'],
            'asset':{'asset_id':job['output_candidate']['id'],'version':job['approved_asset_version'],'digest':job['output_candidate']['digest'],'kind':'video'},
            'video_job':{key:job[key]for key in ('id','version','request_digest','receipt_digest')}})
        receipt = approve(creative,e,row['id'])
    body={'expected_version':receipt['document_snapshot']['version'],'reviewed_content_digest':receipt['content_digest'],
          'title':'CPU reviewed video-only draft','width':1280,'height':720,'fps':24,
          'clips':[{key:shot[key]for key in ('shot_id','shot_version','shot_digest')}|{'in_ms':0,'out_ms':None,'include_audio':False}for shot in reversed(receipt['shots'])]}
    assert all(shot['image_asset'] is None for shot in receipt['shots'])
    return SimpleNamespace(e=e,owner=creative.storyboards,creative=creative,production=production,receipt=receipt,rid=row['id'],body=body,wire=wire)


def request(p, key='once'):
    shown=p.owner.video_timeline_preview(p.e.nid,p.e.scope,p.e.actor,p.rid,p.body,lambda:None)
    return shown,{**deepcopy(p.body),'request_id':key,'preview_digest':shown['preview_digest']}


def test_real_cpu_video_only_preview_order_trim_atomic_create_reopen_and_same_key(videos):
    p=videos;e=p.e;p.body['clips'][0].update(in_ms=100,out_ms=400)
    before=deepcopy(e.store.read(e.nid,e.scope));calls=len(p.wire.calls);shown,body=request(p)
    assert e.store.read(e.nid,e.scope)==before and len(p.wire.calls)==calls
    assert [item['shot_id']for item in shown['clips']]==['shot-2','shot-1']
    assert all(item['measured']['validation']=='DECODED' and item['measured']['width']==64 and item['measured']['height']==64 and item['measured']['extension']=='webm' for item in shown['clips'])
    assert shown['timeline']['duration_ms']==800
    created=p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,body,lambda:None)
    import os, json
    from pathlib import Path
    if os.getenv('STORYBOARD_VIDEO_WIRE_CAPTURE'):
        root=Path(__file__).resolve().parents[1];target=(root/'.runtime/video-wire.json');target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps({'receipt':p.receipt,'body':p.body,'shown':shown,'request':body,'created':created},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert created['timeline']['version']==1 and all(clip['source_snapshot']['asset_kind']=='video'for clip in created['timeline']['timeline']['tracks'][0]['clips'])
    assert len(e.store.read(e.nid,e.scope)['collections'][TIMELINES])==1
    assert p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,body,lambda:None)['replayed']
    from app.creative.production_execution import ProductionExecutionService
    fresh=reopened(e);new=ProductionExecutionService(fresh,None,None,None,None,None,None,None,None)
    recovered=fresh.creative.storyboards.video_timeline_creation(e.nid,e.scope,e.actor,p.rid,body['request_id'],lambda:None)
    assert recovered['timeline']==created['timeline'] and recovered['replayed']
    after=deepcopy(e.store.read(e.nid,e.scope));after['collections'].pop(TIMELINES)
    assert after==before and len(p.wire.calls)==calls
    bad={**body,'title':'different payload'}
    with pytest.raises(StaleSourceError):p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,bad,lambda:None)
    assert len(e.store.read(e.nid,e.scope)['collections'][TIMELINES])==1


@pytest.mark.parametrize('fault',['trim','digest','source','approval','guard','late_guard'])
def test_rejects_changed_or_invalid_preview_without_leaving_partial_timeline(videos,fault):
    p=videos;e=p.e;shown,body=request(p)
    if fault=='trim':body['clips'][0]['out_ms']=501
    elif fault=='digest':body['preview_digest']='0'*64
    elif fault in {'source','approval'}:
        row=p.creative.get(e.nid,e.scope,p.rid);value=content(row);value['title']='After preview'
        p.creative.update(e.nid,e.scope,e.actor,p.rid,row['version'],value)
        if fault=='source':approve(p.creative,e,p.rid)
    before=deepcopy(e.store.read(e.nid,e.scope))
    def guard():
        if fault=='guard' or fault=='late_guard' and e.store.read(e.nid,e.scope)['collections'].get(TIMELINES):
            raise PermissionError('revoked')
    with pytest.raises((ValueError,PermissionError,CapabilityVersionConflict)) as error:p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,body,guard)
    assert error.value and e.store.read(e.nid,e.scope)==before


def test_bounds_no_client_asset_injection_receipt_corruption_and_old_image_gate(videos):
    p=videos;e=p.e
    for clips in [[],p.body['clips']*3,p.body['clips'][:1]*2]:
        with pytest.raises(ValidationError):VideoTimelineInput.model_validate({**p.body,'clips':clips})
    with pytest.raises(ValidationError):VideoTimelineInput.model_validate({**p.body,'clips':[{**p.body['clips'][0],'asset':{'id':'forged'}}]})
    with pytest.raises(ValueError,match='IMAGE_REQUIRED'):p.owner.timeline_draft(e.nid,e.scope,e.actor,p.rid,
        {'expected_version':p.body['expected_version'],'reviewed_content_digest':p.body['reviewed_content_digest'],'title':'old image contract','shot_ids':['shot-1']})
    _,body=request(p);made=p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,body,lambda:None)
    raw=deepcopy(e.store.read(e.nid,e.scope)['collections'][TIMELINES][made['timeline']['id']]);raw['storyboard_video_create_receipt']['preview']['clips'][0]['measured']['width']=999
    with pytest.raises(StaleSourceError):validate_video_creation_receipt(raw)


@pytest.mark.parametrize('videos',[4],indirect=True)
def test_four_reviewed_clips_and_single_subset_use_original_save_and_later_history(videos):
    p=videos;e=p.e;shown,body=request(p,'four')
    assert [clip['shot_id'] for clip in shown['clips']]==['shot-4','shot-3','shot-2','shot-1']
    assert shown['timeline']['duration_ms']==2000
    created=p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,body,lambda:None)
    row=created['timeline'];changed=deepcopy(row['timeline'])
    changed['tracks'][0]['muted']=True
    saved=p.production.timeline_save(e.nid,e.scope,e.actor,row['id'],{'expected_version':1,'title':row['title'],'timeline':changed},lambda:None)
    assert saved['version']==2
    recovered=p.owner.video_timeline_creation(e.nid,e.scope,e.actor,p.rid,'four',lambda:None)
    assert recovered['timeline']['version']==2 and recovered['creation_receipt']==created['creation_receipt']
    p.body['clips']=p.body['clips'][1:2];one,body=request(p,'one')
    assert len(one['clips'])==1 and one['clips'][0]['shot_id']=='shot-3'
    assert p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,body,lambda:None)['timeline']['version']==1
    assert len(e.store.read(e.nid,e.scope)['collections'][TIMELINES])==2


@pytest.mark.parametrize('fault',['capacity','bytes','during_decode','audio'])
def test_original_capacity_decode_and_source_guards_roll_back_without_artifacts(videos,monkeypatch,fault):
    p=videos;e=p.e;shown,body=request(p);before=deepcopy(e.store.read(e.nid,e.scope));calls=len(p.wire.calls)
    if fault=='capacity':
        def reject(state):raise ValueError('original capacity reached')
        monkeypatch.setattr(p.production,'_capacity',reject)
    elif fault=='bytes':
        monkeypatch.setattr('app.services.studio_timeline_render.MAX_SOURCE_BYTES',1)
    elif fault=='audio':body['clips'][0]['include_audio']=True
    else:
        original=p.production.source;changed=False
        def source(*args,**kwargs):
            nonlocal changed,before
            result=original(*args,**kwargs)
            if not changed:
                changed=True;row=p.creative.get(e.nid,e.scope,p.rid);value=content(row);value['title']='Edited during native decode'
                p.creative.update(e.nid,e.scope,e.actor,p.rid,row['version'],value);before=deepcopy(e.store.read(e.nid,e.scope))
            return result
        monkeypatch.setattr(p.production,'source',source)
    with pytest.raises((ValueError,PermissionError,CapabilityVersionConflict)):
        p.owner.video_timeline_create(e.nid,e.scope,e.actor,p.rid,body,lambda:None)
    assert e.store.read(e.nid,e.scope)==before and len(p.wire.calls)==calls
