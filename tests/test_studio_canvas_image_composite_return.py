"""Owned image card + two RGBA PNGs through original CPU Job/Review/CAS.

Expected pixels use rational source-over math, independently of the renderer.
No provider, generic decoder process, model, GPU, or second execution owner.
"""
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
import base64
import hashlib
import io
import json
import os
from pathlib import Path

from PIL import Image
import pytest

from app.experimental.common import StaleSourceError
from app.services.image_job_service import ImageJobService
from app.services.studio_image_execution import _context
from app.creative.production_execution_models import MediaCommand
from test_v2_independent_workspace import rig, reopened
from test_v2_manual_mask_pixels import source_png
from test_v2_cpu_cutout_owner import production, snapshot, preview, queue, run, get, review, reconcile, action, revise
from test_creative_canvas_views_additive import owner, create, reference
from test_v2_image_composite import composite_client, cpu_client, mask_client, client, checked, mounted, prefix

REJECTED=(ValueError,FileNotFoundError,StaleSourceError,PermissionError)
OPERATION='m5.image.composite'


def owned_png(which,width=64):
    colors=(((255,0,30,255),(12,220,34,128),(90,80,70,0),(80,90,100,1)),
            ((0,40,255,128),(210,40,11,64),(41,51,61,0),(1,2,3,0)))[which]
    return source_png(width=width,raw=b''.join(bytes([0])+b''.join(bytes(colors[(x//8+y//8)%4]) for x in range(width)) for y in range(64)))


def upload_owned(e,name,data):
    with e.service._asset_scope(e.nid,e.scope):
        return e.assets.create(e.nid,name,base64.b64encode(data).decode(),'image/png','image',name,
            required_features=('narrative_production_v2',))


@pytest.fixture
def layer_pair(rig,monkeypatch):
    e=rig;e.service.activate(e.nid,e.scope,e.actor)
    e.source=upload_owned(e,'owned-primary.png',owned_png(0));e.secondary=upload_owned(e,'owned-secondary.png',owned_png(1))
    e.production=production(e)
    sources=[snapshot(e.source),snapshot(e.secondary)]
    e.command={'operation_id':OPERATION,'request_id':'card-composite','provider_id':None,'model_id':None,'prompt':'',
        'parameters':{},'allow_cloud':False,'license_note':'Owned synthetic RGBA patterns','source_snapshots':sources,
        'image_layers':[{'source':s,'visible':True,'opacity':255} for s in sources]}
    def denied(*a,**k):raise AssertionError('CPU composite attempted external control or generic inspection')
    import app.creative.production_execution as module
    import app.services.studio_image_execution as image_owner
    import subprocess
    monkeypatch.setattr(module,'inspect_image',denied);monkeypatch.setattr(image_owner,'inspect_image',denied)
    monkeypatch.setattr(subprocess,'run',denied);monkeypatch.setattr(subprocess,'Popen',denied)
    return e


@pytest.fixture
def card_composite(layer_pair):
    e=layer_pair;e.graph=owner(e);e.graph.configure_media(e.production)
    e.canvas=create(e,e.graph,{'title':'Original composite target','cards':[
        {'id':'origin-image','position':{'x':44,'y':66},'asset':reference(e.source)},
        {'id':'other-image','position':{'x':360,'y':120},'asset':reference(e.secondary)}],
        'groups':[{'id':'owned-pair','name':'Keep this arrangement','card_ids':['origin-image','other-image'],'collapsed':False}]})
    e.command['canvas_return']={'contract':'studio-canvas-return/1','project_id':e.nid,'scope':e.scope,
        'incarnation':e.store.incarnation(e.nid),'canvas_id':e.canvas['id'],'canvas_version':e.canvas['version'],
        'canvas_digest':e.canvas['definition_digest'],'card_id':'origin-image','source':snapshot(e.source)}
    return e


def half_up(value):return (value.numerator*2+value.denominator)//(value.denominator*2)


@lru_cache(maxsize=128)
def expected_pixel(bottom,top,bottom_opacity,top_opacity):
    ba=Fraction(bottom[3],255)*Fraction(bottom_opacity,255)
    ta=Fraction(top[3],255)*Fraction(top_opacity,255)
    alpha=ta+ba*(1-ta);encoded_alpha=half_up(alpha*255)
    if encoded_alpha==0:return bytes(4)
    return bytes([half_up((top[c]*ta+bottom[c]*ba*(1-ta))/alpha) for c in range(3)]+[encoded_alpha])


def assert_pixels(e,row):
    originals=[e.service.download(e.nid,e.scope,s['id'])[1] for s in row['command']['source_snapshots']]
    raw=[]
    for data in originals:
        with Image.open(io.BytesIO(data)) as image:assert image.size==(64,64);raw.append(image.convert('RGBA').tobytes())
    layers=row['command']['image_layers'];opacity=[v['opacity'] if v['visible'] else 0 for v in layers]
    expected=b''.join(expected_pixel(tuple(raw[0][p:p+4]),tuple(raw[1][p:p+4]),*opacity) for p in range(0,len(raw[0]),4))
    meta,data=e.production.candidate(e.nid,e.scope,e.actor,'image',row['id'],lambda:None)
    with Image.open(io.BytesIO(data)) as output:
        assert output.format=='PNG' and output.mode=='RGBA' and output.size==(64,64)
        actual=output.tobytes();assert actual==expected
    assert len({actual[p:p+4] for p in range(0,len(actual),4)})>=3
    assert any(actual[p+3]==0 for p in range(0,len(actual),4))
    assert all(actual[p:p+3]==bytes(3) for p in range(0,len(actual),4) if actual[p+3]==0)
    proof=row['processing_proof'];sha=hashlib.sha256(data).hexdigest()
    assert sha==meta['sha256']==row['output_candidate']['digest']==proof['output_sha256']
    assert proof['rgba_sha256']==hashlib.sha256(expected).hexdigest()
    assert proof['source_sha256']==[hashlib.sha256(value).hexdigest() for value in originals]
    assert (proof['width'],proof['height'],proof['output_bytes'])==(64,64,len(data))
    return data,{'real_cpu':True,'model_inference':False,'width':64,'height':64,'rgba_sha256':proof['rgba_sha256'],
        'output_sha256':sha,'output_bytes':len(data),'bytewise_rgba_equal':actual==expected,
        'distinct_rgba':len({actual[p:p+4] for p in range(0,len(actual),4)}),'expectation':'independent rational source-over half-up'}


def no_render(monkeypatch):
    from app.services import studio_image_composite as pixels
    monkeypatch.setattr(pixels,'render',lambda *a,**k:pytest.fail('must not render or replay composite'))


def change_card(e,change):
    definition=deepcopy(e.canvas['definition'])
    if change=='version':definition['title']+=' revised'
    elif change=='deleted-card':
        definition['cards']=definition['cards'][1:];definition['groups'][0]['card_ids']=['other-image']
    elif change=='replaced-card':definition['cards'][0]['asset']=reference(e.secondary)
    else:raise AssertionError(change)
    return e.graph.canvas_views.save(e.nid,e.scope,e.actor,e.canvas['id'],{'expected_version':e.canvas['version'],'definition':definition})


def return_body(e,asset):
    definition=deepcopy(e.canvas['definition']);definition['cards'][0]['asset']=reference(asset)
    return {'expected_version':e.canvas['version'],'definition':definition,
        'expected_incarnation':e.store.incarnation(e.nid),'expected_definition_digest':e.canvas['definition_digest'],
        'expected_card':{'card_id':'origin-image','source':reference(e.source)}}


def test_original_unbound_cpu_composite_still_matches_independent_pixels(layer_pair):
    e=layer_pair;row=run(e,queue(e));assert row['status']=='AWAITING_REVIEW'
    assert 'canvas_return' not in row['command'];assert_pixels(e,row)


@pytest.mark.parametrize('setting',['full','opacity','hidden','swapped'])
def test_real_composite_pixels_private_candidate_exact_return_history_and_reopen(card_composite,monkeypatch,setting):
    e=card_composite
    if setting=='opacity':
        for layer,value in zip(e.command['image_layers'],(73,31)):layer['opacity']=value
    elif setting=='hidden':e.command['image_layers'][1]['visible']=False
    elif setting=='swapped':
        e.command['image_layers'].reverse();e.command['source_snapshots'].reverse()
    captured=preview(e);assert captured['provider'] is None and captured['automatic_dispatch'] is False
    assert captured['execution_recipe']['adapter']=='LOCAL_CPU_COMPOSITE'
    queued=queue(e);assert queue(e)==queued and queued['status']=='QUEUED'
    with monkeypatch.context() as block:
        no_render(block);e.service=reopened(e);e.store=e.service.store;e.production=production(e);e.graph=owner(e);e.graph.configure_media(e.production)
        assert get(e,queued)==queued and e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==e.canvas
    candidate=run(e,queued);assert candidate['status']=='AWAITING_REVIEW' and candidate['attempt']==1
    data,pixels=assert_pixels(e,candidate)
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2
    with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,candidate['output_candidate']['id'])
    assert e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==e.canvas
    with monkeypatch.context() as block:
        no_render(block);approved=review(e,candidate);assert approved['status']=='APPROVED' and approved['approved_asset_version']==2
        formal=e.service.asset(e.nid,e.scope,approved['output_candidate']['id'])
        assert {v['id'] for v in formal['provenance']['parents']}=={e.source['id'],e.secondary['id']}
        returned=e.graph.canvas_views.save(e.nid,e.scope,e.actor,e.canvas['id'],return_body(e,formal))
        assert returned['version']==2
        assert returned['definition']==return_body(e,formal)['definition']
        assert returned['definition']['groups']==e.canvas['definition']['groups']
        history=e.graph.canvas_views.history(e.nid,e.scope,e.actor,e.canvas['id'])
        restored=e.graph.canvas_views.restore(e.nid,e.scope,e.actor,e.canvas['id'],{
            'expected_version':returned['version'],'expected_definition_digest':returned['definition_digest'],
            'expected_incarnation':history['incarnation'],'restore_version':e.canvas['version'],
            'restore_definition_digest':e.canvas['definition_digest']})
        assert restored['version']==3 and restored['definition']==e.canvas['definition']
        e.service=reopened(e);e.production=production(e);assert get(e,approved)==approved
    folder=os.environ.get('STUDIO_CARD_COMPOSITE_CAPTURE_DIR')
    if folder and setting=='full':
        path=Path(folder);path.mkdir(parents=True,exist_ok=True)
        (path/'card-composite.json').write_text(json.dumps({'source':e.source,'secondary':e.secondary,'command':e.command,
            'preview':captured,'queued':queued,'executed':candidate,'approved':approved,'formal':formal,
            'canvas_before':e.canvas,'canvas_after':returned,'history':history,'restored':restored,'pixels':pixels,
            'candidate_png_base64':base64.b64encode(data).decode(),'source_png_base64':base64.b64encode(owned_png(0)).decode(),
            'secondary_png_base64':base64.b64encode(owned_png(1)).decode()},ensure_ascii=False,indent=2),encoding='utf-8')


@pytest.mark.parametrize('mutation',['project','scope','incarnation','version','digest','card','pin'])
def test_exact_canvas_binding_rejects_before_any_job(card_composite,monkeypatch,mutation):
    e=card_composite;value=deepcopy(e.command);origin=value['canvas_return']
    if mutation=='project':origin['project_id']='other-project';origin['scope']={'mode':'local','novel_id':'other-project'}
    elif mutation=='scope':origin['scope']={**e.scope,'workspace_id':'other'}
    elif mutation=='incarnation':origin['incarnation']='file:11111111-1111-4111-8111-111111111111'
    elif mutation=='version':origin['canvas_version']+=1
    elif mutation=='digest':origin['canvas_digest']='f'*64
    elif mutation=='card':origin['card_id']='missing-card'
    else:origin['source']['digest']='f'*64
    no_render(monkeypatch)
    with pytest.raises(REJECTED):preview(e,value)
    assert not list(e.root.rglob('image-jobs/*.json'))


@pytest.mark.parametrize('extra',[{'position':{'x':1,'y':0}},{'transform':{'scale':2}},{'width':128}])
def test_unsupported_spatial_controls_fail_instead_of_ignored(card_composite,extra):
    value=deepcopy(card_composite.command);value['image_layers'][0].update(extra)
    with pytest.raises(ValueError):MediaCommand.model_validate(value)
    assert not list(card_composite.root.rglob('image-jobs/*.json'))


@pytest.mark.parametrize('index',[0,1])
@pytest.mark.parametrize('stage',['queue','execute','review'])
@pytest.mark.parametrize('mutation',['revision','deleted'])
def test_each_layer_even_hidden_rechecks_source_at_all_original_boundaries(card_composite,monkeypatch,index,stage,mutation):
    e=card_composite;e.command['image_layers'][1]['visible']=False
    if stage=='queue':captured=preview(e)
    else:row=queue(e)
    if stage=='review':row=run(e,row);assert row['status']=='AWAITING_REVIEW'
    source=(e.source,e.secondary)[index]
    if mutation=='revision':revise(e,source)
    else:
        with e.service._asset_scope(e.nid,e.scope):e.assets.delete(source['id'])
    no_render(monkeypatch)
    with pytest.raises(REJECTED):
        if stage=='queue':e.production.create(e.nid,e.scope,e.actor,{'command':e.command,'reviewed_preview_digest':captured['preview_digest']},lambda:None)
        elif stage=='execute':run(e,row)
        else:review(e,row)
    if stage=='queue':assert not list(e.root.rglob('image-jobs/*.json'))
    else:
        current=get(e,row);assert current['status']!='APPROVED'
        if stage=='review':
            with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,row['output_candidate']['id'])


@pytest.mark.parametrize('index',[0,1])
def test_sha_pin_is_never_silently_refreshed(card_composite,monkeypatch,index):
    e=card_composite;value=deepcopy(e.command)
    value['source_snapshots'][index]['digest']='f'*64;value['image_layers'][index]['source']['digest']='f'*64
    if index==0:value['canvas_return']['source']['digest']='f'*64
    no_render(monkeypatch)
    with pytest.raises(REJECTED):preview(e,value)
    assert not list(e.root.rglob('image-jobs/*.json'))


def test_different_dimensions_fail_before_render_and_queue(card_composite,monkeypatch):
    e=card_composite;other=upload_owned(e,'wrong-size.png',owned_png(1,72));value=deepcopy(e.command)
    value['source_snapshots'][1]=snapshot(other);value['image_layers'][1]['source']=snapshot(other);no_render(monkeypatch)
    with pytest.raises(ValueError,match='DIMENSIONS_MISMATCH'):preview(e,value)
    assert not list(e.root.rglob('image-jobs/*.json'))


@pytest.mark.parametrize('change',['version','deleted-card','replaced-card'])
@pytest.mark.parametrize('stage',['queue-final','execute','review'])
def test_original_target_checked_at_queue_dispatch_and_review(card_composite,monkeypatch,change,stage):
    e=card_composite
    if stage=='queue-final':captured=preview(e)
    else:row=queue(e)
    if stage=='review':row=run(e,row);assert row['status']=='AWAITING_REVIEW'
    if stage=='queue-final':
        original=ImageJobService.create_studio
        def changed(owner,*a,**k):change_card(e,change);return original(owner,*a,**k)
        monkeypatch.setattr(ImageJobService,'create_studio',changed)
    else:change_card(e,change)
    no_render(monkeypatch)
    with pytest.raises(REJECTED):
        if stage=='queue-final':e.production.create(e.nid,e.scope,e.actor,{'command':e.command,'reviewed_preview_digest':captured['preview_digest']},lambda:None)
        elif stage=='execute':run(e,row)
        else:review(e,row)
    if stage=='queue-final':assert not list(e.root.rglob('image-jobs/*.json'))
    elif stage=='review':
        assert get(e,row)['output_candidate']==row['output_candidate']
        with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,row['output_candidate']['id'])


def test_late_cpu_result_cannot_publish_after_target_changes(card_composite,monkeypatch):
    e=card_composite;row=queue(e)
    from app.services import studio_image_composite as pixels
    original=pixels.render;calls=[]
    def late(*a,**k):
        result=original(*a,**k);calls.append(True);change_card(e,'version');return result
    monkeypatch.setattr(pixels,'render',late);result=run(e,row)
    assert calls==[True] and result['status'] in {'FAILED','UNKNOWN'} and result['output_candidate'] is None
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2
    with pytest.raises(REJECTED):run(e,result)


def test_approved_candidate_is_retained_when_card_cas_conflicts(card_composite):
    e=card_composite;approved=review(e,run(e,queue(e)));formal=e.service.asset(e.nid,e.scope,approved['output_candidate']['id'])
    current=change_card(e,'version')
    with pytest.raises(REJECTED):e.graph.canvas_views.save(e.nid,e.scope,e.actor,e.canvas['id'],return_body(e,formal))
    assert e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==current
    assert get(e,approved)==approved and e.service.asset(e.nid,e.scope,formal['id'])==formal


def test_canvas_origin_remains_digest_bound_in_original_job_context(card_composite):
    e=card_composite;queued=queue(e)
    row=next(row for path in e.root.rglob('image-jobs/*.json') for row in json.loads(path.read_text('utf-8')) if row['id']==queued['id'])
    assert 'canvas_return' not in row['body'] and row['context']['command']['canvas_return']==e.command['canvas_return']
    changed=deepcopy(row['context']);changed['command']['canvas_return']['card_id']='other-image'
    with pytest.raises(ValueError):_context(changed,row['body'],row['owner_actor_id'])


def test_unknown_reconciles_without_render_replay_or_automatic_return(card_composite,monkeypatch):
    e=card_composite;row=queue(e);original=e.assets.create
    def lost(*a,**k):original(*a,**k);raise OSError('synthetic lost private publication response')
    with monkeypatch.context() as patch:patch.setattr(e.assets,'create',lost);unknown=run(e,row)
    assert unknown['status']=='UNKNOWN' and unknown['processing_proof'] and unknown['output_candidate'] is None
    no_render(monkeypatch);assert get(e,unknown)==unknown and queue(e)==unknown
    with pytest.raises(ValueError):run(e,unknown)
    recovered=reconcile(e,unknown)
    assert recovered['status']=='AWAITING_REVIEW' and recovered['attempt']==1
    assert recovered['processing_proof']==unknown['processing_proof']
    assert e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==e.canvas
    assert review(e,recovered)['status']=='APPROVED'


@pytest.mark.parametrize('stage',['queue','execute','review'])
def test_original_permission_revocation_blocks_dispatch_and_adoption(card_composite,monkeypatch,stage):
    e=card_composite
    if stage!='queue':row=queue(e)
    if stage=='review':row=run(e,row)
    no_render(monkeypatch)
    def denied():raise PermissionError('synthetic current author revoked')
    with pytest.raises(PermissionError):
        if stage=='queue':queue(e,guard=denied)
        elif stage=='execute':run(e,row,guard=denied)
        else:review(e,row,guard=denied)
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2


@pytest.mark.parametrize('change',['project','incarnation','actor'])
def test_original_job_does_not_cross_owner_or_recreated_project(card_composite,monkeypatch,change):
    e=card_composite;row=queue(e);nid,scope,actor=e.nid,e.scope,e.actor
    if change=='project':nid=e.create_project('Other composite owner');scope={'mode':'local','novel_id':nid}
    elif change=='incarnation':e.novels.delete(e.nid);e.create_project('Recreated composite owner',e.nid)
    else:actor='other-author'
    e.service.activate(nid,scope,actor);no_render(monkeypatch)
    with pytest.raises(REJECTED):e.production.execute(nid,scope,actor,'image',row['id'],action(row),lambda:None)


def test_original_graph_composite_entry_stays_unsupported(card_composite,monkeypatch):
    e=card_composite;no_render(monkeypatch)
    from app.creative.graph_models import MediaNodeParameters
    from app.creative.graph_media_binding import make_graph_binding_digest
    with pytest.raises(ValueError):MediaNodeParameters.model_validate({'operation_id':OPERATION})
    _,context,_=e.production.preview(e.nid,e.scope,e.actor,e.command,lambda:None)
    binding={'contract':'creative-graph-media-binding/1','run_id':'run','node_id':'composite','graph_id':'graph',
        'graph_version':1,'graph_digest':'a'*64,'run_request_digest':'b'*64,'input_digest':'c'*64,
        'preview_run_version':1,'command_digest':'d'*64}
    binding['attempt_digest']=make_graph_binding_digest(binding,context)
    with pytest.raises(ValueError,match='STUDIO_IMAGE_CUTOUT_STANDALONE_ONLY'):
        e.production.preview(e.nid,e.scope,e.actor,e.command,lambda:None,graph_binding=binding)
    assert not list(e.root.rglob('image-jobs/*.json'))


def test_mounted_composite_card_original_api_both_prefixes(composite_client,monkeypatch):
    e=composite_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    from app.creative.canvas_views import CreativeCanvasViews
    from app.creative.graph_asset_inputs import GraphAssetInputs
    graph=e.experimental.creative_graph_service
    monkeypatch.setattr(graph,'store',e.studio.store);monkeypatch.setattr(graph,'workspace',e.studio)
    monkeypatch.setattr(graph,'asset_inputs',GraphAssetInputs(graph));monkeypatch.setattr(graph,'canvas_views',CreativeCanvasViews(graph));graph.configure_media(e.production)
    canvas=checked(e.client.post(e.studio_base+'/canvas-views',headers=e.headers,json={'request_id':'api-composite-card',
        'definition':{'title':'API original composite card','cards':[{'id':'origin-image','position':{'x':44,'y':66},'asset':reference(e.source)}]}}),201)
    e.command['canvas_return']={'contract':'studio-canvas-return/1','project_id':e.nid,'scope':e.scope,
        'incarnation':e.studio.store.incarnation(e.nid),'canvas_id':canvas['id'],'canvas_version':canvas['version'],
        'canvas_digest':canvas['definition_digest'],'card_id':'origin-image','source':snapshot(e.source)}
    captured=checked(e.client.post(e.base+'/preview',headers=e.headers,json=e.command))
    queued=checked(e.client.post(e.base+'/jobs',headers=e.headers,json={'command':e.command,'reviewed_preview_digest':captured['preview_digest']}),201)
    assert checked(e.client.get(e.base+'/jobs/image/'+queued['id'],headers=e.headers))==queued
    candidate=checked(e.client.post(e.base+'/jobs/image/'+queued['id']+'/execute',headers=e.headers,json={
        'expected_version':queued['version'],'expected_request_digest':queued['request_digest']}))
    assert candidate['status']=='AWAITING_REVIEW' and captured['provider'] is None
    assert e.client.get(e.studio_base+'/assets/'+candidate['output_candidate']['id'],headers=e.headers).status_code==404
    data=e.client.get(e.base+'/jobs/image/'+queued['id']+'/candidate',headers=e.headers)
    assert data.status_code==200 and hashlib.sha256(data.content).hexdigest()==candidate['processing_proof']['output_sha256']
    approved=checked(e.client.post(e.base+'/jobs/image/'+queued['id']+'/review',headers=e.headers,json={
        'expected_version':candidate['version'],'expected_request_digest':candidate['request_digest'],
        'reviewed_output_digest':candidate['output_candidate']['digest']}))
    formal=checked(e.client.get(e.studio_base+'/assets/'+approved['output_candidate']['id'],headers=e.headers))
    definition=deepcopy(canvas['definition']);definition['cards'][0]['asset']=reference(formal)
    returned=checked(e.client.put(e.studio_base+'/canvas-views/'+canvas['id'],headers=e.headers,json={
        'expected_version':canvas['version'],'expected_definition_digest':canvas['definition_digest'],
        'expected_incarnation':e.studio.store.incarnation(e.nid),'expected_card':{'card_id':'origin-image','source':reference(e.source)},'definition':definition}))
    assert returned['version']==2 and returned['definition']['cards'][0]['asset']==reference(formal)
