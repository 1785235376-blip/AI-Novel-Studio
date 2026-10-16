"""Phase5 explicit Shot provenance without changing published Graph5 identities.

The baseline fixture was captured from actual Phase4 code with synthetic inputs.
It is a byte/request compatibility proof, not a provider or native Host receipt.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json

import pytest
from pydantic import ValidationError

from app.creative.graph_models import VideoNodeParameters, ShotCard
from app.creative.graph_video_nodes import video_command_fields, preflight_video
from app.creative.production_execution_models import MediaCommand
from app.experimental.store import canonical
from test_v2_independent_workspace import rig


def legacy():
    return json.loads((Path(__file__).parent/'fixtures/v2_phase5_legacy_video_command.json').read_text(encoding='utf-8'))


def test_published_graph5_body_prompt_and_original_request_digest_are_exactly_preserved():
    old=legacy()
    assert old['baseline_sha']=='8e4f028680f885d7bc9e040609c5c1b5d2a48e13' and old['synthetic_only']
    for addition in ({},{'bind_shot':None}):
        cfg={**old['parameters'],**addition}
        assert VideoNodeParameters.model_validate(cfg).model_dump()==old['normalized_parameters']
        assert ShotCard.model_validate(old['ports']['shot']['shot']).model_dump()==old['ports']['shot']['shot']
        fields=video_command_fields({'parameters':cfg},old['ports'])
        assert fields==old['command_fields'] and 'storyboard_shot' not in fields
        body=MediaCommand.model_validate({**fields,'request_id':'phase5-legacy-identity'}).model_dump()
        assert body==old['command']
        assert hashlib.sha256(canonical(body).encode()).hexdigest()==old['command_digest']


@pytest.mark.parametrize('invalid',[False,1,0,'true',{},[]])
def test_new_binding_is_explicit_true_or_omitted_not_coerced(invalid):
    with pytest.raises(ValidationError,match='SHOT_BINDING_INVALID'):
        VideoNodeParameters.model_validate({**legacy()['parameters'],'bind_shot':invalid})


def test_explicit_binding_carries_only_exact_shot_source_and_changes_identity():
    old=legacy()
    cfg={**old['parameters'],'bind_shot':True}
    fields=video_command_fields({'parameters':cfg},old['ports'])
    shot=old['ports']['shot']
    assert fields['storyboard_shot']=={key:shot[key] for key in ('document_snapshot','shot_id','shot_version','shot_digest')}
    assert 'approved' not in fields['storyboard_shot'] and 'bind_shot' not in fields
    assert fields['source_snapshots']==old['command_fields']['source_snapshots']
    assert fields['prompt']==old['command_fields']['prompt']
    body=MediaCommand.model_validate({**fields,'request_id':'phase5-legacy-identity'}).model_dump()
    assert hashlib.sha256(canonical(body).encode()).hexdigest()!=old['command_digest']
    mismatched=deepcopy(fields)
    mismatched['storyboard_shot']['document_snapshot']['version']+=1
    with pytest.raises(ValidationError):
        MediaCommand.model_validate({**mismatched,'request_id':'phase5-legacy-identity'})


def test_missing_shot_binding_rejects_before_original_provider_admission():
    cfg=VideoNodeParameters.model_validate({**legacy()['parameters'],'bind_shot':True}).model_dump()
    with pytest.raises(ValueError,match='SHOT_BINDING_INPUT_REQUIRED'):
        video_command_fields({'parameters':cfg},{})
    issues=preflight_video({'video':{'definition_id':'video_generate','parameters':cfg}},
        {'video':[]},['video'],lambda _edge:pytest.fail('No Asset probe allowed'))
    assert issues==[{'code':'CREATIVE_GRAPH_VIDEO_SHOT_BINDING_INPUT_REQUIRED','node_id':'video'}]


def test_unapproved_shot_never_receives_binding_authority():
    old=legacy()
    ports=deepcopy(old['ports']); ports['shot']['approved']=False
    with pytest.raises(ValueError,match='STORYBOARD_APPROVAL_REQUIRED'):
        video_command_fields({'parameters':{**old['parameters'],'bind_shot':True}},ports)


def test_authored_video_hint_is_consumed_with_exact_original_shot_pin():
    old=legacy(); ports=deepcopy(old['ports'])
    ports['shot']['shot']['video_generation_hint']='SYNTHETIC slow dolly, retain final pose'
    ports['shot']['shot_digest']=hashlib.sha256(canonical(ports['shot']['shot']).encode()).hexdigest()
    fields=video_command_fields({'parameters':{**old['parameters'],'bind_shot':True}},ports)
    assert fields['prompt'].endswith('\nvideo_generation_hint: SYNTHETIC slow dolly, retain final pose')
    assert fields['storyboard_shot']['shot_digest']==ports['shot']['shot_digest']
    assert fields['parameters']['duration_seconds']==ports['shot']['shot']['duration_seconds']


@pytest.mark.parametrize('invalid',['x'*4001,12,False])
def test_hint_is_closed_and_bounded(invalid):
    shot={**legacy()['ports']['shot']['shot'],'video_generation_hint':invalid}
    with pytest.raises(ValidationError): ShotCard.model_validate(shot)


def test_hint_and_frame_prompt_overflow_rejects_without_truncation():
    old=legacy(); ports=deepcopy(old['ports'])
    ports['shot']['shot'].update(frame_prompt='x'*15900,video_generation_hint='y'*4000)
    ports['shot']['shot_digest']=hashlib.sha256(canonical(ports['shot']['shot']).encode()).hexdigest()
    fields=video_command_fields({'parameters':{**old['parameters'],'bind_shot':True}},ports)
    assert 'x'*15900 in fields['prompt'] and 'y'*4000 in fields['prompt']
    with pytest.raises(ValidationError):
        MediaCommand.model_validate({**fields,'request_id':'bounded-hint'})


@pytest.mark.parametrize('operation,duration_ms',[
    ('m7.video.t2v',1250),('m7.video.i2v',1250),('m7.video.t2v',500)])
def test_graph_reviewed_video_binds_historical_shot_and_adopts_original_clip(
        rig,tmp_path,monkeypatch,operation,duration_ms):
    """Real isolated owners + synthetic transport + actual CPU media, no model."""
    import shutil
    from app.creative.models import CreativeProductionDocumentIn
    from app.creative.storyboard import storyboard_receipt
    from app.services.studio_timeline_export import run_guarded_process
    from test_v2_independent_workspace import import_asset,png_bytes,reopened
    from test_v2_graph_image_nodes import graph_owner,create_run
    from test_v2_graph_production_planning import documents
    from test_v2_graph_video_foundation import video_graph
    from test_v2_video_runtime_foundation import configured
    e=rig
    discovery,production,adapter,wire,command=configured(e,tmp_path,monkeypatch)
    path=tmp_path/'timeline-duration.webm'
    assert shutil.which('ffmpeg'), 'real CPU media prerequisite required'
    run_guarded_process([shutil.which('ffmpeg'),'-nostdin','-v','error','-f','lavfi','-i',
        f'color=c=blue:s=64x64:r=8:d={duration_ms/1000}','-c:v','libvpx-vp9','-threads','1','-y',str(path)],
        cwd=tmp_path,guard=lambda:None,timeout=20)
    wire.data=path.read_bytes()
    graph=graph_owner(e,monkeypatch,production)
    _,board=documents(e)
    authored={key:deepcopy(board[key]) for key in CreativeProductionDocumentIn.model_fields if key in board}
    authored['shots'][0].update(duration_seconds=1,video_generation_hint='SYNTHETIC maintain final pose')
    board=e.service.creative.update(e.nid,e.scope,e.actor,board['id'],board['version'],authored)
    image=import_asset(e,data=png_bytes(),filename='synthetic-storyboard.png')
    item=storyboard_receipt(board)['shots'][0]
    e.service.creative.storyboards.bind_image(e.nid,e.scope,e.actor,board['id'],item['shot_id'],{
        'expected_version':board['version'],'shot_version':item['shot_version'],'shot_digest':item['shot_digest'],
        'asset':{'asset_id':image['id'],'version':image['version'],'digest':image['sha256'],'kind':'image'}})
    board=e.service.creative.get(e.nid,e.scope,board['id'])
    receipt=e.service.creative.storyboards.approve(e.nid,e.scope,e.actor,board['id'],{
        'expected_version':board['version'],'reviewed_content_digest':storyboard_receipt(board)['content_digest']})
    board=e.service.creative.get(e.nid,e.scope,board['id'])
    original_pin=deepcopy(receipt['document_snapshot']); item=receipt['shots'][0]
    create_body={'expected_version':board['version'],'reviewed_content_digest':receipt['content_digest'],
        'request_id':'graph-timeline-create','title':'SYNTHETIC approved timeline','shot_ids':[item['shot_id']],
        'width':64,'height':64,'fps':8}
    created=e.service.creative.storyboards.timeline_create(e.nid,e.scope,e.actor,board['id'],create_body)
    timeline=created['timeline']; origin=deepcopy(created['storyboard_origin'])
    assert timeline['version']==1 and not created['automatic_dispatch']
    assert not any(url.endswith('/prompt') for url,_ in wire.calls)
    value=video_graph(board,receipt)
    value['nodes'][2]['parameters'].update(operation_id=operation,provider_id=command['provider_id'],
        model_id=command['model_id'],bind_shot=True,parameters={'width':64,'height':64,'frame_rate':8,'seed':7})
    _,run=create_run(e,graph,value); runtime=graph.media_runtime
    run=runtime.preview(e.nid,e.scope,e.actor,run['id'],{'expected_version':run['version'],'node_id':'video'},lambda:None)
    preview=run['media_runtime']['nodes'][0]['preview']
    assert preview['command']['storyboard_shot']['document_snapshot']==original_pin
    run=runtime.dispatch(e.nid,e.scope,e.actor,run['id'],{'expected_version':run['version'],'node_id':'video',
        'reviewed_preview_digest':preview['preview_digest']},lambda:None)
    def action(row):
        job=row['media_runtime']['nodes'][0]['execution']['job']
        return {'expected_version':row['version'],'node_id':'video','expected_job_version':job['version'],
                'expected_request_digest':job['request_digest']}
    run=runtime.execute_job(e.nid,e.scope,e.actor,run['id'],action(run),lambda:None)
    run=runtime.refresh(e.nid,e.scope,e.actor,run['id'],action(run),lambda:None)
    job=run['media_runtime']['nodes'][0]['execution']['job']
    assert job['status']=='AWAITING_REVIEW'
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid,e.scope,job['output_candidate']['id'])
    run=runtime.review(e.nid,e.scope,e.actor,run['id'],{**action(run),'node_id':'review',
        'reviewed_output_digest':job['output_candidate']['digest']},lambda:None)
    assert run['status']=='SUCCEEDED'
    job=run['media_runtime']['nodes'][0]['execution']['job']
    descriptor={key:job[key] for key in ('id','version','request_digest','receipt_digest')}
    asset=run['node_states']['review']['output']['asset']
    bound=e.service.creative.storyboards.bind_video(e.nid,e.scope,e.actor,board['id'],item['shot_id'],{
        'expected_version':board['version'],'shot_version':item['shot_version'],'shot_digest':item['shot_digest'],
        'asset':asset,'video_job':descriptor})
    assert not bound['approved'] and bound['shots'][0]['shot_version']==item['shot_version']
    assert bound['shots'][0]['video_result']['source_shot']['document_snapshot']==original_pin
    board=e.service.creative.get(e.nid,e.scope,board['id'])
    approved=e.service.creative.storyboards.approve(e.nid,e.scope,e.actor,board['id'],{
        'expected_version':board['version'],'reviewed_content_digest':bound['content_digest']})
    adopted_body={'expected_version':approved['document_snapshot']['version'],
        'shot_version':item['shot_version'],'shot_digest':item['shot_digest'],
        'expected_timeline_version':timeline['version'],'reviewed_timeline_digest':timeline['timeline_digest'],
        'request_id':'graph-reviewed-video-adoption','clip_id':origin['shots'][0]['clip_id'],
        'video_asset':asset,'video_job':descriptor,'in_ms':0,'out_ms':1000,'include_audio':False}
    if duration_ms<1000:
        with pytest.raises(ValueError,match='VIDEO_RANGE_INVALID'):
            e.service.creative.storyboards.adopt_video(e.nid,e.scope,e.actor,board['id'],item['shot_id'],timeline['id'],adopted_body)
        assert production.timeline_get(e.nid,e.scope,e.actor,timeline['id'],lambda:None)['version']==1
    else:
        adopted=e.service.creative.storyboards.adopt_video(e.nid,e.scope,e.actor,board['id'],item['shot_id'],timeline['id'],adopted_body)
        assert adopted['timeline']['version']==2 and adopted['timeline']['storyboard_origin']==origin
        assert adopted['timeline']['timeline']['tracks'][0]['clips'][0]['source_snapshot']['id']==asset['asset_id']
        replay=e.service.creative.storyboards.adopt_video(e.nid,e.scope,e.actor,board['id'],item['shot_id'],timeline['id'],adopted_body)
        assert replay['timeline']['version']==2
        lookup=e.service.creative.storyboards.timeline_creation(e.nid,e.scope,e.actor,board['id'],create_body['request_id'])
        assert lookup['creation_receipt']['creation_snapshot']['version']==1 and lookup['timeline']['version']==2
        workspace=reopened(e); production.workspace=workspace
        assert production.timeline_get(e.nid,e.scope,e.actor,timeline['id'],lambda:None)['version']==2
    assert sum(url.endswith('/prompt') for url,_ in wire.calls)==1
    assert discovery.center.lifecycle.start.call_count==0
