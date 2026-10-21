"""Ordinary saved image card -> original CPU mask ImageJob -> explicit return.

Short owned PNGs and an authored binary mask only. Pixel expectations are
computed with an independent decoder, never by calling the cutout renderer.
"""
from copy import deepcopy
import base64
import hashlib
import io
import json
import os
from pathlib import Path

import pytest
from PIL import Image, features

from app.creative.production_execution_models import MediaCommand
from app.services.image_job_service import ImageJobService
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, reopened
from test_v2_manual_mask_owner import mask
from test_v2_manual_mask_pixels import source_png, plane
from test_v2_cpu_cutout_owner import cutout, production, snapshot, preview, queue, run, get, review, reconcile, action, revise
from test_creative_canvas_views_additive import owner, create, reference
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_manual_mask_api import mask_client
from test_v2_cpu_cutout_api import cpu_client

REJECTED=(ValueError,FileNotFoundError,StaleSourceError,PermissionError)
PROFILE='WEBP_LOSSLESS_V1'


@pytest.fixture
def card_cutout(cutout):
    e=cutout;e.graph=owner(e);e.graph.configure_media(e.production)
    e.canvas=create(e,e.graph,{'title':'Owned image card with authored mask','cards':[
        {'id':'origin-image','position':{'x':44,'y':66},'asset':reference(e.source)},
        {'id':'other-image','position':{'x':360,'y':120},'asset':reference(e.source)}]})
    e.command['canvas_return']={'contract':'studio-canvas-return/1','project_id':e.nid,'scope':e.scope,
        'incarnation':e.store.incarnation(e.nid),'canvas_id':e.canvas['id'],'canvas_version':e.canvas['version'],
        'canvas_digest':e.canvas['definition_digest'],'card_id':'origin-image','source':snapshot(e.source)}
    return e


def assert_pixels(e,row):
    meta,data=e.production.candidate(e.nid,e.scope,e.actor,'image',row['id'],lambda:None)
    source=e.service.download(e.nid,e.scope,e.source['id'])[1]
    mask_bytes=e.service.download(e.nid,e.scope,e.mask['id'])[1]
    with Image.open(io.BytesIO(source)) as picture,Image.open(io.BytesIO(mask_bytes)) as painted,Image.open(io.BytesIO(data)) as output:
        raw=picture.convert('RGBA').tobytes();bits=painted.convert('L').tobytes()
        assert picture.size==painted.size==output.size==(64,64)
        assert set(bits)=={0,255}
        expected=b''.join(raw[index*4:index*4+4] if keep==255 else bytes(4) for index,keep in enumerate(bits))
        actual=output.convert('RGBA').tobytes()
        assert actual==expected
        assert output.format==('WEBP' if row['command']['parameters'].get('cutout_output')==PROFILE else 'PNG')
    kept=sum(value==255 for value in bits)
    assert kept==512 and len(bits)-kept==3584
    assert all(actual[i*4:i*4+4]==bytes(4) for i,value in enumerate(bits) if value==0)
    assert all(actual[i*4:i*4+4]==raw[i*4:i*4+4] for i,value in enumerate(bits) if value==255)
    proof=row['processing_proof'];sha=hashlib.sha256(data).hexdigest()
    assert sha==meta['sha256']==proof['output_sha256']==row['output_candidate']['digest']
    assert proof['source_sha256']==hashlib.sha256(source).hexdigest()==e.source['sha256']
    assert proof['mask_sha256']==hashlib.sha256(mask_bytes).hexdigest()==e.mask['sha256']
    assert (proof['width'],proof['height'],proof['keep_pixels'],proof['remove_pixels'])==(64,64,512,3584)
    if row['command']['parameters'].get('cutout_output')==PROFILE:
        assert proof['rgba_sha256']==hashlib.sha256(expected).hexdigest()
    return data,{'real_cpu_pixels':True,'model_inference':False,'width':64,'height':64,
        'keep_pixels':kept,'remove_pixels':len(bits)-kept,'rgba_sha256':hashlib.sha256(actual).hexdigest(),
        'output_sha256':sha,'output_bytes':len(data),'bytewise_rgba_equal':actual==expected}


def change_card(e,change):
    definition=deepcopy(e.canvas['definition'])
    if change=='version':definition['title']+=' revised'
    elif change=='deleted-card':definition['cards']=definition['cards'][1:]
    elif change=='replaced-card':definition['cards'][0]['asset']=reference(e.mask)
    else:raise AssertionError(change)
    return e.graph.canvas_views.save(e.nid,e.scope,e.actor,e.canvas['id'],{
        'expected_version':e.canvas['version'],'definition':definition})


def return_body(e,asset):
    definition=deepcopy(e.canvas['definition']);definition['cards'][0]['asset']=reference(asset)
    return {'expected_version':e.canvas['version'],'definition':definition,
        'expected_incarnation':e.store.incarnation(e.nid),'expected_definition_digest':e.canvas['definition_digest'],
        'expected_card':{'card_id':'origin-image','source':reference(e.source)}}


def no_render(monkeypatch):
    import app.services.studio_image_cutout as pixels
    monkeypatch.setattr(pixels,'render_cutout',lambda *a,**k:pytest.fail('this operation must not render pixels'))


def test_baseline_original_unbound_cpu_cutout_still_has_exact_pixels(cutout):
    e=cutout;row=run(e,queue(e));assert row['status']=='AWAITING_REVIEW'
    assert 'canvas_return' not in row['command'];assert_pixels(e,row)


@pytest.mark.parametrize('profile',[None,PROFILE])
def test_real_pixels_private_candidate_review_exact_card_cas_history_and_file_reopen(card_cutout,monkeypatch,profile):
    e=card_cutout
    if profile:assert features.check('webp'),'existing local WebP required, no install or fallback';e.command['parameters']={'cutout_output':profile}
    original_canvas=deepcopy(e.canvas);captured=preview(e)
    assert captured['provider'] is None and captured['automatic_dispatch'] is False
    assert captured['execution_recipe']['adapter']=='LOCAL_CPU_MASK'
    assert captured['command']['canvas_return']==e.command['canvas_return']
    queued=queue(e);assert queued==queue(e) and queued['status']=='QUEUED'
    with monkeypatch.context() as blocked:
        no_render(blocked)
        e.service=reopened(e);e.store=e.service.store;e.production=production(e);e.graph=owner(e);e.graph.configure_media(e.production)
        assert get(e,queued)==queued and e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==original_canvas
    candidate=run(e,queued);assert candidate['status']=='AWAITING_REVIEW' and candidate['attempt']==1
    data,pixels=assert_pixels(e,candidate)
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2
    with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,candidate['output_candidate']['id'])
    assert e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==original_canvas
    with monkeypatch.context() as blocked:
        no_render(blocked)
        approved=review(e,candidate);assert approved['status']=='APPROVED' and approved['approved_asset_version']==2
        formal=e.service.asset(e.nid,e.scope,approved['output_candidate']['id'])
        assert {item['id'] for item in formal['provenance']['parents']}=={e.source['id'],e.mask['id']}
        returned=e.graph.canvas_views.save(e.nid,e.scope,e.actor,e.canvas['id'],return_body(e,formal))
        assert returned['version']==2 and returned['definition']['cards'][0]=={**original_canvas['definition']['cards'][0],'asset':reference(formal)}
        assert returned['definition']['cards'][1:]==original_canvas['definition']['cards'][1:]
        history=e.graph.canvas_views.history(e.nid,e.scope,e.actor,e.canvas['id'])
        restored=e.graph.canvas_views.restore(e.nid,e.scope,e.actor,e.canvas['id'],{
            'expected_version':returned['version'],'expected_definition_digest':returned['definition_digest'],
            'expected_incarnation':history['incarnation'],'restore_version':original_canvas['version'],
            'restore_definition_digest':original_canvas['definition_digest']})
        assert restored['version']==3 and restored['definition']==original_canvas['definition']
        e.service=reopened(e);e.production=production(e);e.graph=owner(e);e.graph.configure_media(e.production)
        assert get(e,approved)==approved
    folder=os.environ.get('STUDIO_IMAGE_MASK_RETURN_CAPTURE_DIR')
    if folder:
        path=Path(folder);path.mkdir(parents=True,exist_ok=True);label='webp' if profile else 'png'
        (path/('native-card-cutout-'+label+'.json')).write_text(json.dumps({'contract':'owned-cpu-mask-card-return-proof/1',
            'cpu':pixels,'source':e.source,'mask':e.mask,'command':e.command,'preview':captured,'queued':queued,
            'executed':candidate,'approved':approved,'formal':formal,'canvas_before':original_canvas,
            'canvas_after':returned,'history':history,'restored':restored,
            'output_base64':base64.b64encode(data).decode('ascii')},ensure_ascii=False,indent=2),encoding='utf-8')


@pytest.mark.parametrize('mutation',['project','scope','incarnation','version','digest','card','pin'])
def test_original_card_binding_is_exact_before_any_job(card_cutout,monkeypatch,mutation):
    e=card_cutout;value=deepcopy(e.command);origin=value['canvas_return']
    if mutation=='project':origin['project_id']='other-project';origin['scope']={'mode':'local','novel_id':'other-project'}
    elif mutation=='scope':origin['scope']={**e.scope,'workspace_id':'another'}
    elif mutation=='incarnation':origin['incarnation']='file:11111111-1111-4111-8111-111111111111'
    elif mutation=='version':origin['canvas_version']+=1
    elif mutation=='digest':origin['canvas_digest']='f'*64
    elif mutation=='card':origin['card_id']='missing-card'
    else:origin['source']['digest']='f'*64
    no_render(monkeypatch)
    with pytest.raises(REJECTED):preview(e,value)
    assert not list(e.root.rglob('image-jobs/*.json'))


@pytest.mark.parametrize('index',[0,1])
@pytest.mark.parametrize('field',['id','version','digest'])
def test_original_source_and_mask_snapshots_cannot_be_changed(card_cutout,monkeypatch,index,field):
    e=card_cutout;value=deepcopy(e.command);source=value['source_snapshots'][index]
    if field=='id':source['id']='missing-image-source'
    elif field=='version':source['version']+=1
    else:source['digest']='f'*64
    no_render(monkeypatch)
    with pytest.raises(REJECTED):preview(e,value)
    assert not list(e.root.rglob('image-jobs/*.json'))


@pytest.mark.parametrize('width',[64,72])
def test_authored_mask_for_other_source_or_dimensions_is_never_repaired_implicitly(card_cutout,monkeypatch,width):
    e=card_cutout
    with e.service._asset_scope(e.nid,e.scope):
        other=e.assets.create(e.nid,'other-owned.png',base64.b64encode(source_png(width=width)).decode(),
            'image/png','image','another-source-'+str(width),required_features=('narrative_production_v2',))
    painted=e.service.author_mask(e.nid,e.scope,e.actor,other['id'],{'contract':'manual-binary-mask/1',
        'source_version':other['version'],'source_sha256':other['sha256'],'width':width,'height':64,
        'bitplane_base64':plane(width=width),'idempotency_key':'other-owned-mask'},lambda:None)['asset']
    value=deepcopy(e.command);value['source_snapshots'][1]=snapshot(painted);no_render(monkeypatch)
    with pytest.raises(ValueError):preview(e,value)
    assert not list(e.root.rglob('image-jobs/*.json'))


def test_png_lookalike_is_not_an_authored_mask(card_cutout,monkeypatch):
    e=card_cutout;mask_bytes=e.service.download(e.nid,e.scope,e.mask['id'])[1]
    with e.service._asset_scope(e.nid,e.scope):
        lookalike=e.assets.create(e.nid,'mask-lookalike.png',base64.b64encode(mask_bytes).decode(),'image/png','image',
            'lookalike',required_features=('narrative_production_v2',))
    value=deepcopy(e.command);value['source_snapshots'][1]=snapshot(lookalike);no_render(monkeypatch)
    with pytest.raises(ValueError,match='IMAGE_MASK_ORIGIN_INVALID'):preview(e,value)
    assert not list(e.root.rglob('image-jobs/*.json'))


@pytest.mark.parametrize('stage',['queue','execute','review'])
@pytest.mark.parametrize('index',[0,1])
def test_source_and_mask_revision_after_preview_never_refresh_implicitly(card_cutout,monkeypatch,stage,index):
    e=card_cutout
    if stage=='queue':captured=preview(e)
    else:row=queue(e)
    if stage=='review':row=run(e,row);assert row['status']=='AWAITING_REVIEW'
    revise(e,e.source if index==0 else e.mask);no_render(monkeypatch)
    with pytest.raises(REJECTED):
        if stage=='queue':e.production.create(e.nid,e.scope,e.actor,{'command':e.command,'reviewed_preview_digest':captured['preview_digest']},lambda:None)
        elif stage=='execute':run(e,row)
        else:review(e,row)
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2


@pytest.mark.parametrize('change',['version','deleted-card','replaced-card'])
def test_original_queue_atomic_phase_rechecks_card_after_preview(card_cutout,monkeypatch,change):
    e=card_cutout;captured=preview(e);original=ImageJobService.create_studio
    def changed(owner,*args,**kwargs):
        change_card(e,change)
        return original(owner,*args,**kwargs)
    monkeypatch.setattr(ImageJobService,'create_studio',changed);no_render(monkeypatch)
    with pytest.raises(REJECTED):
        e.production.create(e.nid,e.scope,e.actor,{'command':e.command,
            'reviewed_preview_digest':captured['preview_digest']},lambda:None)
    assert not list(e.root.rglob('image-jobs/*.json'))


@pytest.mark.parametrize('stage',['execute','review'])
@pytest.mark.parametrize('change',['version','deleted-card','replaced-card'])
def test_changed_target_stops_dispatch_or_review_and_keeps_candidate_private(card_cutout,monkeypatch,stage,change):
    e=card_cutout;row=queue(e)
    if stage=='review':row=run(e,row);assert row['status']=='AWAITING_REVIEW'
    change_card(e,change);no_render(monkeypatch)
    with pytest.raises(REJECTED):
        if stage=='execute':run(e,row)
        else:review(e,row)
    current=get(e,row)
    if stage=='review':
        assert current['output_candidate']==row['output_candidate']
        with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,row['output_candidate']['id'])
    else:assert current['output_candidate'] is None
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2


@pytest.mark.parametrize('change',['version','deleted-card','replaced-card'])
def test_return_cas_refuses_target_change_and_keeps_approved_asset(card_cutout,change):
    e=card_cutout;approved=review(e,run(e,queue(e)));formal=e.service.asset(e.nid,e.scope,approved['output_candidate']['id'])
    change_card(e,change)
    with pytest.raises(REJECTED):e.graph.canvas_views.save(e.nid,e.scope,e.actor,e.canvas['id'],return_body(e,formal))
    assert get(e,approved)==approved and e.service.asset(e.nid,e.scope,formal['id'])==formal


def test_late_cpu_bytes_cannot_publish_to_changed_card(card_cutout,monkeypatch):
    e=card_cutout;queued=queue(e)
    import app.services.studio_image_cutout as pixels
    original=pixels.render_cutout;calls=[]
    def late(*a,**k):
        result=original(*a,**k);calls.append(True);change_card(e,'version');return result
    monkeypatch.setattr(pixels,'render_cutout',late)
    result=run(e,queued)
    assert calls==[True] and result['status'] in {'FAILED','UNKNOWN'} and result['output_candidate'] is None
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2
    with pytest.raises(REJECTED):run(e,result)


def test_unknown_only_reconciles_exact_private_candidate_without_render_or_new_dispatch(card_cutout,monkeypatch):
    e=card_cutout;queued=queue(e);original=e.assets.create
    def lost(*a,**k):original(*a,**k);raise OSError('synthetic lost private publication response')
    with monkeypatch.context() as patch:
        patch.setattr(e.assets,'create',lost);unknown=run(e,queued)
    assert unknown['status']=='UNKNOWN' and unknown['processing_proof'] and unknown['output_candidate'] is None
    no_render(monkeypatch)
    assert get(e,unknown)==unknown and queue(e)==unknown
    with pytest.raises(ValueError):run(e,unknown)
    recovered=reconcile(e,unknown)
    assert recovered['status']=='AWAITING_REVIEW' and recovered['attempt']==1
    assert recovered['processing_proof']==unknown['processing_proof']
    assert e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==e.canvas
    assert review(e,recovered)['status']=='APPROVED'


@pytest.mark.parametrize('stage',['queue','execute','review'])
def test_denied_original_authority_never_dispatches_or_adopts(card_cutout,monkeypatch,stage):
    e=card_cutout
    if stage!='queue':row=queue(e)
    if stage=='review':row=run(e,row)
    no_render(monkeypatch)
    def denied():raise PermissionError('synthetic current domain authority revoked')
    with pytest.raises(PermissionError):
        if stage=='queue':queue(e,guard=denied)
        elif stage=='execute':run(e,row,guard=denied)
        else:review(e,row,guard=denied)
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2


@pytest.mark.parametrize('change',['other-project','recreated-project'])
def test_original_job_never_rebinds_to_new_project_or_incarnation(card_cutout,monkeypatch,change):
    e=card_cutout;row=queue(e)
    if change=='other-project':nid=e.create_project('Other cutout owner');scope={'mode':'local','novel_id':nid}
    else:e.novels.delete(e.nid);e.create_project('Recreated cutout owner',e.nid);nid,scope=e.nid,e.scope
    e.service.activate(nid,scope,e.actor);no_render(monkeypatch)
    with pytest.raises(REJECTED):e.production.execute(nid,scope,e.actor,'image',row['id'],action(row),lambda:None)


def test_original_graph_cutout_entry_stays_unsupported(card_cutout,monkeypatch):
    e=card_cutout;no_render(monkeypatch)
    from app.creative.graph_models import MediaNodeParameters
    with pytest.raises(ValueError):MediaNodeParameters.model_validate({'operation_id':'m5.image.cutout'})
    from app.creative.graph_media_binding import make_graph_binding_digest
    _,context,_=e.production.preview(e.nid,e.scope,e.actor,e.command,lambda:None)
    binding={'contract':'creative-graph-media-binding/1','run_id':'run','node_id':'cutout','graph_id':'graph',
        'graph_version':1,'graph_digest':'a'*64,'run_request_digest':'b'*64,'input_digest':'c'*64,
        'preview_run_version':1,'command_digest':'d'*64}
    binding['attempt_digest']=make_graph_binding_digest(binding,context)
    with pytest.raises(ValueError,match='STUDIO_IMAGE_CUTOUT_STANDALONE_ONLY'):
        e.production.preview(e.nid,e.scope,e.actor,e.command,lambda:None,graph_binding=binding)
    assert not list(e.root.rglob('image-jobs/*.json'))


def test_mounted_original_cutout_card_preview_execute_review_and_return(cpu_client,monkeypatch):
    e=cpu_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    from app.creative.canvas_views import CreativeCanvasViews
    from app.creative.graph_asset_inputs import GraphAssetInputs
    graph=e.experimental.creative_graph_service
    monkeypatch.setattr(graph,'store',e.studio.store);monkeypatch.setattr(graph,'workspace',e.studio)
    monkeypatch.setattr(graph,'asset_inputs',GraphAssetInputs(graph));monkeypatch.setattr(graph,'canvas_views',CreativeCanvasViews(graph));graph.configure_media(e.production)
    canvas=checked(e.client.post(e.studio_base+'/canvas-views',headers=e.headers,json={'request_id':'api-cutout-return-card',
        'definition':{'title':'API original cutout card','cards':[{'id':'origin-image','position':{'x':44,'y':66},'asset':reference(e.source)}]}}),201)
    e.command['canvas_return']={'contract':'studio-canvas-return/1','project_id':e.nid,'scope':e.scope,
        'incarnation':e.studio.store.incarnation(e.nid),'canvas_id':canvas['id'],'canvas_version':canvas['version'],
        'canvas_digest':canvas['definition_digest'],'card_id':'origin-image','source':snapshot(e.source)}
    captured=checked(e.client.post(e.base+'/preview',headers=e.headers,json=e.command))
    assert captured['command']['canvas_return']==e.command['canvas_return'] and captured['provider'] is None
    queued=checked(e.client.post(e.base+'/jobs',headers=e.headers,json={'command':e.command,'reviewed_preview_digest':captured['preview_digest']}),201)
    assert checked(e.client.get(e.base+'/jobs/image/'+queued['id'],headers=e.headers))==queued
    result=checked(e.client.post(e.base+'/jobs/image/'+queued['id']+'/execute',headers=e.headers,json={
        'expected_version':queued['version'],'expected_request_digest':queued['request_digest']}))
    assert result['status']=='AWAITING_REVIEW'
    data=e.client.get(e.base+'/jobs/image/'+queued['id']+'/candidate',headers=e.headers)
    assert data.status_code==200 and hashlib.sha256(data.content).hexdigest()==result['processing_proof']['output_sha256']
    assert e.client.get(e.studio_base+'/assets/'+result['output_candidate']['id'],headers=e.headers).status_code==404
    approved=checked(e.client.post(e.base+'/jobs/image/'+queued['id']+'/review',headers=e.headers,json={
        'expected_version':result['version'],'expected_request_digest':result['request_digest'],
        'reviewed_output_digest':result['output_candidate']['digest']}))
    assert approved['status']=='APPROVED'
    asset=checked(e.client.get(e.studio_base+'/assets/'+approved['output_candidate']['id'],headers=e.headers))
    definition=deepcopy(canvas['definition']);definition['cards'][0]['asset']=reference(asset)
    returned=checked(e.client.put(e.studio_base+'/canvas-views/'+canvas['id'],headers=e.headers,json={
        'expected_version':canvas['version'],'expected_definition_digest':canvas['definition_digest'],
        'expected_incarnation':e.studio.store.incarnation(e.nid),'expected_card':{'card_id':'origin-image','source':reference(e.source)},
        'definition':definition}))
    assert returned['version']==2 and returned['definition']['cards'][0]['asset']==reference(asset)
