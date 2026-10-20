"""UI-produced original Graph parameters through real File owners and synthetic Comfy wire."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, reopened
from test_v2_graph_image_nodes import graph_owner
from test_v2_image_discovery_capabilities import enabled
from test_v2_discovered_image_production import owner as production_owner
from test_v2_image_provider_recipes import Transport
from test_text_image_output_graph_starter import prepare, dispatch, execution, action, posts

@pytest.mark.parametrize('scenario', ['reviewed-output', 'stale-preview', 'unknown-no-resend'])
def test_ui_sampling_parameters_reach_original_job_recipe_and_wire_without_new_executor(rig,tmp_path,monkeypatch,scenario):
 e=rig
 source=json.loads((Path(__file__).parent/'fixtures/studio_graph_recipe_parameter_edit.json').read_text(encoding='utf-8'))
 assert source['producer']=='applyGraphRecipeParameters'
 _,registry,adapter,_=enabled(tmp_path,'sdxl-fixture.safetensors','COMFYUI')
 production=production_owner(registry,monkeypatch,e);wire=Transport();adapter.delegate.transport=wire
 owner=graph_owner(e,monkeypatch,production)
 def bound(value):
  value=deepcopy(value);node=next(n for n in value['nodes'] if n['id']=='generate')
  node['parameters'].update(provider_id=adapter.candidate['provider_id'],model_id=adapter.candidate['id'])
  return value
 graph=owner.create(e.nid,e.scope,e.actor,{'request_id':'sampling-base','definition':bound(source['base'])})
 output={'generatorNodeId':'generate','reviewNodeId':'review','prompt':source['base']['nodes'][0]['parameters']['prompt']}
 def start(row,request):
  flight=owner.preflight(e.nid,e.scope,e.actor,row['id'],{'expected_version':row['version'],'target_node_ids':[]})
  assert flight['executable'],flight['issues']
  return owner.create_run(e.nid,e.scope,e.actor,row['id'],{'expected_graph_version':row['version'],'reviewed_preflight_digest':flight['preflight_digest'],'target_node_ids':flight['target_node_ids'],'request_id':request})
 if scenario=='stale-preview':
  old=start(graph,'old-sampling-run');old,old_preview=prepare(e,owner,old,output)
 graph=owner.save(e.nid,e.scope,e.actor,graph['id'],{'expected_version':graph['version'],'definition':bound(source['edited'])})
 from app.creative.graph import CreativeGraphService
 fresh=reopened(e);assert CreativeGraphService(fresh.store,fresh).get(e.nid,e.scope,e.actor,graph['id'])==graph
 stored_parameters=graph['definition']['nodes'][1]['parameters']['parameters']
 parameters={key:value for key,value in stored_parameters.items() if value is not None}
 assert parameters=={'width':512,'height':512,'steps':37,'seed':424242,'negative_prompt':'synthetic negative'}
 assert not posts(wire)
 if scenario=='stale-preview':
  with pytest.raises((ValueError,StaleSourceError)):dispatch(e,owner,old,output,old_preview)
  assert not posts(wire) and not owner._owned(e.nid,e.scope,e.actor,owner.RUNS,old['id']).get('media_executions')
  return
 run=start(graph,'edited-sampling-run');run,preview=prepare(e,owner,run,output)
 production_preview=preview['production_preview'];recipe=production_preview['execution_recipe']
 for command in [preview['command'],production_preview['command']]:
  assert {key:value for key,value in command['parameters'].items() if value is not None}==parameters
 assert recipe['adapter']=='COMFYUI_BUILTIN_IMAGE'
 assert recipe['workflow']['3']['inputs']['steps']==37 and recipe['workflow']['3']['inputs']['seed']==424242
 run=dispatch(e,owner,run,output,preview);assert not posts(wire)
 if scenario=='unknown-no-resend':
  original_post=wire.post
  def lost_reply(url,**kwargs):
   response=original_post(url,**kwargs)
   if url.endswith('/prompt'):raise TimeoutError('synthetic accepted sampling request with lost reply')
   return response
  monkeypatch.setattr(wire,'post',lost_reply)
 run=owner.media_runtime.execute_job(e.nid,e.scope,e.actor,run['id'],action(run,output),lambda:None)
 submitted=posts(wire);assert len(submitted)==1
 workflow=submitted[0][1]['json']['prompt']
 assert workflow['3']['inputs']['steps']==37 and workflow['3']['inputs']['seed']==424242
 assert workflow['5']['inputs']['width']==512 and workflow['5']['inputs']['height']==512
 assert workflow['7']['inputs']['text']=='synthetic negative'
 job=execution(run,output)['job']
 if scenario=='unknown-no-resend':
  assert job['status']=='UNKNOWN' and execution(run,output)['send_reserved'] is True
  with pytest.raises(ValueError):owner.media_runtime.execute_job(e.nid,e.scope,e.actor,run['id'],action(run,output),lambda:None)
  owner.get_run(e.nid,e.scope,e.actor,run['id'],reconcile=False);assert len(posts(wire))==1
 else:
  assert job['status']=='AWAITING_REVIEW';candidate=job['output_candidate']
  with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,candidate['id'])
  run=owner.media_runtime.review(e.nid,e.scope,e.actor,run['id'],{**action(run,output),'node_id':'review','reviewed_output_digest':candidate['digest']},lambda:None)
  assert run['status']=='SUCCEEDED' and e.service.asset(e.nid,e.scope,candidate['id'])['kind']=='image'
 assert len(posts(wire))==1
