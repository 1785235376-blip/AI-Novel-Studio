"""Original mounted Host/File authority and CPU synthetic video, no live model."""
from copy import deepcopy
import pytest
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, action, assert_success_private_headers
from test_v2_storyboard_workspace_api import storyboard_client, get_storyboard, shot_action, approve_board
from test_v2_video_runtime_foundation_api import setup, queue


def test_mounted_video_only_preview_confirm_original_save_and_same_key_reopen(storyboard_client,monkeypatch):
    e=storyboard_client;discovery,adapter,wire,command=setup(e,monkeypatch);board=approve_board(e,get_storyboard(e))
    prepared=checked(e.client.post(e.board_path+'/shots/shot-1/video-request',headers=e.headers,json={
        **shot_action(board),'operation_id':'m7.video.t2v','request_id':'cpu-video-only',
        'provider':{key:command[key] for key in ('operation_id','provider_id','model_id')},'parameters':{'width':64,'height':64,'frame_rate':8}}))
    job=queue(e,prepared['command']);path=e.base+'/jobs/video/'+job['id']
    job=checked(e.client.post(path+'/execute',headers=e.headers,json=action(job)))
    job=checked(e.client.post(path+'/refresh',headers=e.headers,json=action(job)))
    job=checked(e.client.post(path+'/review',headers=e.headers,json={**action(job),'reviewed_output_digest':job['output_candidate']['digest']}))
    bound=checked(e.client.post(e.board_path+'/shots/shot-1/video-binding',headers=e.headers,json={**shot_action(board),
        'asset':{'asset_id':job['output_candidate']['id'],'version':job['approved_asset_version'],'digest':job['output_candidate']['digest'],'kind':'video'},
        'video_job':{key:job[key] for key in ('id','version','request_digest','receipt_digest')}}))
    board=approve_board(e,bound);shot=board['shots'][0];assert shot['image_asset'] is None
    body={'expected_version':board['document_snapshot']['version'],'reviewed_content_digest':board['content_digest'],'title':'CPU video-only',
        'clips':[{key:shot[key] for key in ('shot_id','shot_version','shot_digest')}|{'in_ms':100,'out_ms':400,'include_audio':False}]}
    url=e.board_path+'/storyboard/video-timeline';before=deepcopy(e.store.read(e.nid,e.scope));calls=len(wire.calls)
    response=e.client.post(url+'/preview',headers=e.headers,json=body);assert_success_private_headers(response);shown=checked(response)
    assert shown['clips'][0]['measured']['width']==64 and shown['timeline']['duration_ms']==300
    assert e.store.read(e.nid,e.scope)==before and len(wire.calls)==calls
    intent={**body,'request_id':'mounted-video-only','preview_digest':shown['preview_digest']}
    response=e.client.post(url+'/create',headers=e.headers,json=intent);assert_success_private_headers(response);created=checked(response,201)
    response=e.client.get(url+'/creations/mounted-video-only',headers=e.headers);assert_success_private_headers(response);reopened=checked(response)
    assert reopened['timeline']==created['timeline'] and reopened['replayed']
    assert checked(e.client.post(url+'/create',headers=e.headers,json=intent),201)==reopened
    assert len(checked(e.client.get(e.base+'/timelines',headers=e.headers))['items'])==1 and len(wire.calls)==calls
    assert e.client.post(url+'/create',headers=e.headers,json={**intent,'title':'changed'}).status_code==409


@pytest.mark.parametrize('fault,status',[('missing',401),('forged',401),('origin',403),('forwarded',403)])
def test_new_video_routes_preserve_host_authority_and_no_partial_save(storyboard_client,fault,status):
    e=storyboard_client;board=get_storyboard(e);before=deepcopy(e.store.read(e.nid,e.scope))
    headers={} if fault=='missing' else {'X-Session-Token':'forged'} if fault=='forged' else (
        {**e.headers,'Origin':'https://untrusted.invalid'} if fault=='origin' else {**e.headers,'Forwarded':'for=127.0.0.1'})
    body={'expected_version':board['document_snapshot']['version'],'reviewed_content_digest':board['content_digest'],'title':'not saved',
        'clips':[{key:board['shots'][0][key] for key in ('shot_id','shot_version','shot_digest')}] }
    for method,suffix,value in [('POST','preview',body),('POST','create',{**body,'request_id':'blocked','preview_digest':'0'*64}),('GET','creations/blocked',None)]:
        response=e.client.request(method,e.board_path+'/storyboard/video-timeline/'+suffix,headers=headers,json=value)
        assert response.status_code==status,response.text
    assert e.store.read(e.nid,e.scope)==before


def test_collaboration_novel_read_or_write_role_does_not_replace_storyboard_host(storyboard_client,monkeypatch):
    e=storyboard_client;board=get_storyboard(e);local_scope=deepcopy(e.scope);before=deepcopy(e.store.read(e.nid,local_scope))
    e=scoped(e,monkeypatch);body={'expected_version':board['document_snapshot']['version'],'reviewed_content_digest':board['content_digest'],'title':'no authority',
        'clips':[{key:board['shots'][0][key] for key in ('shot_id','shot_version','shot_digest')}]}
    for headers in [e.headers,e.viewer_headers]:
        for method,suffix,value in [('POST','preview',body),('POST','create',{**body,'request_id':'blocked','preview_digest':'0'*64}),('GET','creations/blocked',None)]:
            response=e.client.request(method,e.board_path+'/storyboard/video-timeline/'+suffix,headers=headers,json=value)
            assert response.status_code==403,response.text
    assert e.store.read(e.nid,local_scope)==before
