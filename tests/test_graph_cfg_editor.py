"""Bounded SD CFG through original Graph/File/Job; all wire responses synthetic."""
from copy import deepcopy
import json,os
from pathlib import Path
import pytest
from app.asset_providers import AssetGenerationRequest,ComfyUIImageProvider
from app.creative.production_execution_models import MediaParameters
from app.experimental.common import StaleSourceError
from app.services.studio_image_provider_recipes import build_workflow,project_comfy_image_recipe,public_capabilities
from test_v2_independent_workspace import rig,reopened
from test_v2_graph_image_nodes import graph_owner
from test_v2_image_discovery_capabilities import enabled
from test_v2_discovered_image_production import owner as production_owner
from test_v2_image_provider_recipes import Transport,object_info
from test_text_image_output_graph_starter import prepare,dispatch,execution,action,posts

@pytest.mark.parametrize('value',[True,'7.25',float('nan'),float('inf'),-1,100.01])
def test_cfg_rejects_non_numeric_or_unbounded_command(value):
 with pytest.raises(ValueError):MediaParameters.model_validate({'cfg':value})

def test_cfg_uses_observed_bounds_and_preserves_family_defaults_and_legacy_registration():
 assert MediaParameters.model_validate(MediaParameters().model_dump()).cfg is None
 info=object_info();info['KSampler']['input']['required']['cfg'][1]={'min':1,'max':12}
 sd=project_comfy_image_recipe(info,'sdxl-fixture.safetensors','STABLE_DIFFUSION')
 assert public_capabilities(sd)['cfg']=={'min':1,'max':12,'default':7}
 assert build_workflow(sd,'p',{'cfg':7.25})['3']['inputs']['cfg']==7.25
 for value in (0,12.01,True,float('nan')):
  with pytest.raises(ValueError):build_workflow(sd,'p',{'cfg':value})
 for model,family,fixed in [('flux1-dev.safetensors','FLUX',1),('qwen_image_fp8_e4m3fn.safetensors','QWEN_IMAGE',4)]:
  recipe=project_comfy_image_recipe(object_info(),model,family)
  assert 'cfg' not in public_capabilities(recipe) and build_workflow(recipe,'p',{})['3']['inputs']['cfg']==fixed
  with pytest.raises(ValueError):build_workflow(recipe,'p',{'cfg':7.25})
 with pytest.raises(ValueError):build_workflow(sd,'p',{'cfg':7.25},operation='i2i')
 wire=Transport();adapter=ComfyUIImageProvider(wire,'http://127.0.0.1:8188')
 old=project_comfy_image_recipe(wire.info,'sdxl-fixture.safetensors','STABLE_DIFFUSION');old.pop('cfg_control');adapter.image_recipe_descriptor=old
 assert 'cfg' not in adapter.image_parameters('t2i')
 adapter.generate(AssetGenerationRequest('synthetic-provider','sdxl-fixture.safetensors','p','legacy-cfg'))
 assert posts(wire)[0][1]['json']['prompt']['3']['inputs']['cfg']==7

@pytest.mark.parametrize('scenario',['reviewed-output','stale-preview','unknown-no-resend','metadata-revoked'])
def test_ui_cfg_reaches_original_file_job_wire_and_review(rig,tmp_path,monkeypatch,scenario):
 e=rig;source=json.loads((Path(__file__).parent/'fixtures/studio_graph_cfg_parameter_edit.json').read_text(encoding='utf-8'))
 assert source['producer']=='applyGraphRecipeParameters-cfg'
 _,registry,adapter,_=enabled(tmp_path,'sdxl-fixture.safetensors','COMFYUI');production=production_owner(registry,monkeypatch,e)
 wire=Transport();adapter.delegate.transport=wire;owner=graph_owner(e,monkeypatch,production)
 def bound(value):
  value=deepcopy(value);value['nodes'][1]['parameters'].update(provider_id=adapter.candidate['provider_id'],model_id=adapter.candidate['id']);return value
 graph=owner.create(e.nid,e.scope,e.actor,{'request_id':'cfg-base','definition':bound(source['base'])})
 output={'generatorNodeId':'generate','reviewNodeId':'review','prompt':source['base']['nodes'][0]['parameters']['prompt']}
 def start(row,key):
  f=owner.preflight(e.nid,e.scope,e.actor,row['id'],{'expected_version':row['version'],'target_node_ids':[]});assert f['executable'],f['issues']
  return owner.create_run(e.nid,e.scope,e.actor,row['id'],{'expected_graph_version':row['version'],'reviewed_preflight_digest':f['preflight_digest'],'target_node_ids':f['target_node_ids'],'request_id':key})
 old=start(graph,'cfg-old');old,old_preview=prepare(e,owner,old,output)
 edited=source['zero'] if scenario=='reviewed-output' else source['decimal'];cfg=edited['nodes'][1]['parameters']['parameters']['cfg']
 graph=owner.save(e.nid,e.scope,e.actor,graph['id'],{'expected_version':graph['version'],'definition':bound(edited)})
 from app.creative.graph import CreativeGraphService
 fresh=reopened(e);assert CreativeGraphService(fresh.store,fresh).get(e.nid,e.scope,e.actor,graph['id'])==graph
 with pytest.raises((ValueError,StaleSourceError)):dispatch(e,owner,old,output,old_preview)
 assert not posts(wire)
 if scenario=='stale-preview':return
 run=start(graph,'cfg-new');run,preview=prepare(e,owner,run,output);p=preview['production_preview']
 assert p['command']['parameters']['cfg']==cfg and p['execution_recipe']['workflow']['3']['inputs']['cfg']==cfg
 run=dispatch(e,owner,run,output,preview);assert not posts(wire)
 if scenario=='metadata-revoked':wire.info['KSampler']['input']['required']['cfg'][1]['max']=7
 if scenario=='unknown-no-resend':
  original=wire.post
  def lost(url,**kwargs):
   response=original(url,**kwargs)
   if url.endswith('/prompt'):raise TimeoutError('synthetic accepted CFG request, reply lost')
   return response
  monkeypatch.setattr(wire,'post',lost)
 run=owner.media_runtime.execute_job(e.nid,e.scope,e.actor,run['id'],action(run,output),lambda:None);job=execution(run,output)['job']
 if scenario=='metadata-revoked':
  assert not posts(wire) and job['status']=='UNKNOWN'
  with pytest.raises(ValueError):owner.media_runtime.execute_job(e.nid,e.scope,e.actor,run['id'],action(run,output),lambda:None)
  assert not posts(wire);return
 sent=posts(wire);assert len(sent)==1;assert sent[0][1]['json']['prompt']==p['execution_recipe']['workflow']
 assert sent[0][1]['json']['prompt']['3']['inputs']['cfg']==cfg
 if scenario=='unknown-no-resend':
  assert job['status']=='UNKNOWN'
  with pytest.raises(ValueError):owner.media_runtime.execute_job(e.nid,e.scope,e.actor,run['id'],action(run,output),lambda:None)
  assert len(posts(wire))==1;return
 assert job['status']=='AWAITING_REVIEW';candidate=job['output_candidate']
 # The Graph response intentionally exposes a compact Job snapshot. Exercise
 # the original full decoder with the owner's exact, Graph-bound projection.
 full_job=owner.media_runtime._job(e.nid,e.scope,e.actor,owner._owned(e.nid,e.scope,e.actor,owner.RUNS,run['id']),'generate',lambda:None)
 receipt={'project':e.nid,'providers':production.providers(e.nid,e.scope,e.actor,lambda:None),'preview':p,'job':full_job,'cfg':cfg,'models_or_GPU':0}
 if os.environ.get('STUDIO_CFG_RECEIPT_OUT'):Path(os.environ['STUDIO_CFG_RECEIPT_OUT']).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,candidate['id'])
 run=owner.media_runtime.review(e.nid,e.scope,e.actor,run['id'],{**action(run,output),'node_id':'review','reviewed_output_digest':candidate['digest']},lambda:None)
 assert run['status']=='SUCCEEDED' and e.service.asset(e.nid,e.scope,candidate['id'])['kind']=='image'
