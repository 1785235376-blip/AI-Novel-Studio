"""Additive original Job origin and original Canvas CAS fences. No model inference."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.creative.production_execution_models import MediaCommand
from app.creative.canvas_view_models import CanvasViewSave
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig,import_asset
from test_creative_canvas_views_additive import owner,create,reference
from test_v2_image_discovery_capabilities import enabled
from test_v2_discovered_image_production import owner as production_owner
from test_v2_image_provider_recipes import Transport,png

def setup(e,tmp_path,monkeypatch):
 source=import_asset(e,data=png(),filename='synthetic-origin.png');graph=owner(e)
 canvas=create(e,graph,{'schema_version':1,'title':'Bound return','cards':[{'id':'origin-card','position':{'x':44,'y':66},'asset':reference(source)}],'viewport':{'x':0,'y':0,'zoom':1}})
 _,registry,adapter,_=enabled(tmp_path,'sdxl-fixture.safetensors','COMFYUI');production=production_owner(registry,monkeypatch,e);graph.configure_media(production)
 wire=Transport();adapter.delegate.transport=wire
 pin={'id':source['id'],'kind':'ASSET','version':source['version'],'digest':source['sha256'],'asset_kind':'image'}
 command={'operation_id':'m5.image.i2i','request_id':'synthetic-persistent-return','provider_id':adapter.candidate['provider_id'],'model_id':adapter.candidate['id'],'prompt':'Synthetic persistent return','parameters':{'steps':33,'seed':100,'denoising_strength':0.6},'source_snapshots':[pin],'image_source':pin,'allow_cloud':False,'license_note':'Synthetic author declaration',
   'canvas_return':{'contract':'studio-canvas-return/1','project_id':e.nid,'scope':e.scope,'incarnation':e.store.incarnation(e.nid),'canvas_id':canvas['id'],'canvas_version':canvas['version'],'canvas_digest':canvas['definition_digest'],'card_id':'origin-card','source':pin}}
 return graph,production,wire,canvas,command

def test_legacy_command_and_canvas_save_dump_identity_stays_unchanged():
 fixture=json.loads((Path(__file__).parent/'fixtures/studio_dual_canvas_loop.json').read_text(encoding='utf-8'))
 legacy=deepcopy(fixture['preview']['command']);legacy.pop('canvas_return',None)
 assert MediaCommand.model_validate(legacy).model_dump()==legacy
 value={'expected_version':1,'definition':fixture['canvas']['definition']}
 assert CanvasViewSave.model_validate(value).model_dump()==value

@pytest.mark.parametrize('change',['null','contract','project','scope','incarnation','card','version','bool-version','digest','source','cloud','operation'])
def test_invalid_or_stale_return_origin_never_dispatches(rig,tmp_path,monkeypatch,change):
 graph,production,wire,canvas,command=setup(rig,tmp_path,monkeypatch);origin=command['canvas_return']
 if change=='null':command['canvas_return']=None
 elif change=='contract':origin['contract']='unknown/1'
 elif change=='project':origin['project_id']='another-project';origin['scope']={'mode':'local','novel_id':'another-project'}
 elif change=='scope':origin['scope']={**origin['scope'],'branch_id':'other-branch'}
 elif change=='incarnation':origin['incarnation']='file:00000000-0000-0000-0000-000000000000'
 elif change=='card':origin['card_id']='deleted-card'
 elif change=='version':origin['canvas_version']+=1
 elif change=='bool-version':origin['canvas_version']=True
 elif change=='digest':origin['canvas_digest']='f'*64
 elif change=='source':origin['source']={**origin['source'],'digest':'f'*64}
 elif change=='cloud':command['allow_cloud']=True
 elif change=='operation':command['operation_id']='m5.image.t2i'
 with pytest.raises((ValueError,StaleSourceError,FileNotFoundError)):production.preview(rig.nid,rig.scope,rig.actor,command,lambda:None)
 assert not any(url.endswith('/prompt') for url,_ in wire.calls)
 assert graph.canvas_views.get(rig.nid,rig.scope,rig.actor,canvas['id'])['version']==1

@pytest.mark.parametrize('field',['expected_incarnation','expected_definition_digest'])
def test_original_canvas_cas_refuses_stale_origin_and_keeps_version(rig,tmp_path,monkeypatch,field):
 graph,_,_,canvas,_=setup(rig,tmp_path,monkeypatch)
 body={'expected_version':1,'definition':canvas['definition'],'expected_incarnation':rig.store.incarnation(rig.nid),'expected_definition_digest':canvas['definition_digest']}
 body[field]='file:00000000-0000-0000-0000-000000000000' if field=='expected_incarnation' else 'f'*64
 with pytest.raises(StaleSourceError):graph.canvas_views.save(rig.nid,rig.scope,rig.actor,canvas['id'],body)
 assert graph.canvas_views.get(rig.nid,rig.scope,rig.actor,canvas['id'])['version']==1

def test_partial_or_null_canvas_origin_fence_is_not_silently_dropped():
 definition={'schema_version':1,'title':'Legacy','cards':[],'viewport':{'x':0,'y':0,'zoom':1}}
 for values in [{'expected_incarnation':'file:any'},{'expected_definition_digest':'f'*64},{'expected_incarnation':None,'expected_definition_digest':None}]:
  with pytest.raises(ValueError):CanvasViewSave.model_validate({'expected_version':1,'definition':definition,**values})

@pytest.mark.parametrize('mutation',['metadata','deleted'])
def test_source_pin_is_checked_inside_original_asset_lease_even_when_replacement_removes_it(rig,tmp_path,monkeypatch,mutation):
 graph,_,_,canvas,command=setup(rig,tmp_path,monkeypatch)
 replacement=import_asset(rig,data=png(),filename='synthetic-reviewed-result.png')
 definition=deepcopy(canvas['definition']);definition['cards'][0]['asset']=reference(replacement)
 body={'expected_version':1,'definition':definition,'expected_incarnation':rig.store.incarnation(rig.nid),'expected_definition_digest':canvas['definition_digest'],'expected_card':{'card_id':'origin-card','source':canvas['definition']['cards'][0]['asset']}}
 with rig.service._asset_scope(rig.nid,rig.scope):
  if mutation=='metadata':rig.assets.update_metadata(command['image_source']['id'],{'provider_id':'synthetic-version-change'},expected_version=command['image_source']['version'])
  else:rig.assets.delete(command['image_source']['id'])
 with pytest.raises(StaleSourceError,match='CREATIVE_CANVAS_RETURN_SOURCE_CHANGED'):graph.canvas_views.save(rig.nid,rig.scope,rig.actor,canvas['id'],body)
 assert graph.canvas_views.get(rig.nid,rig.scope,rig.actor,canvas['id'])['version']==1
 assert rig.service.asset(rig.nid,rig.scope,replacement['id'])['id']==replacement['id']
