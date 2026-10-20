"""One original File/Job/Asset/Canvas loop; model transport is explicitly synthetic."""
from copy import deepcopy
import base64,hashlib,json,os,shutil,subprocess
from pathlib import Path
import pytest
from app.creative.production_execution_models import MediaJobAction,MediaReview
from test_v2_independent_workspace import rig,import_asset,reopened
from test_creative_canvas_views_additive import owner,create,reference
from test_canvas_view_history import restore_body
from test_v2_image_discovery_capabilities import enabled
from test_v2_discovered_image_production import owner as production_owner
from test_v2_image_provider_recipes import Transport,png

def test_card_task_original_job_review_exact_return_history_restore_and_reopen(rig,tmp_path,monkeypatch):
 if not shutil.which('node') or not (Path(__file__).parents[1]/'frontend/node_modules').is_dir():
  pytest.skip('Cross-owner replay requires Node and the existing frontend dependencies; no installation is performed.')
 e=rig;out=Path(os.environ.get('STUDIO_DUAL_LOOP_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(exist_ok=True)
 source=import_asset(e,data=png(),filename='synthetic-origin.png');graph=owner(e)
 canvas=create(e,graph,{'schema_version':1,'title':'Single-card original work','cards':[{'id':'origin-card','position':{'x':44,'y':66},'asset':reference(source)},{'id':'other-card','position':{'x':400,'y':100},'asset':reference(source)}],
   'groups':[{'id':'original-group','name':'Original group','card_ids':['origin-card'],'collapsed':False}],'viewport':{'x':0,'y':0,'zoom':1}})
 _,registry,adapter,_=enabled(tmp_path,'sdxl-fixture.safetensors','COMFYUI');production=production_owner(registry,monkeypatch,e);wire=Transport();adapter.delegate.transport=wire
 snapshot={'id':source['id'],'kind':'ASSET','version':source['version'],'digest':source['sha256'],'asset_kind':'image'}
 command={'operation_id':'m5.image.i2i','request_id':'synthetic-single-card-task','provider_id':adapter.candidate['provider_id'],'model_id':adapter.candidate['id'],
   'prompt':'Synthetic single-card variation','parameters':{'steps':33,'seed':100,'denoising_strength':0.6},'source_snapshots':[snapshot],'image_source':snapshot,'image_references':[],
   'allow_cloud':False,'license_note':'Synthetic author declaration'}
 preview,_,_=production.preview(e.nid,e.scope,e.actor,command,lambda:None);assert not any(url.endswith('/prompt') for url,_ in wire.calls)
 queued=production.create(e.nid,e.scope,e.actor,{'command':command,'reviewed_preview_digest':preview['preview_digest']},lambda:None)
 assert queued['status']=='QUEUED' and not any(url.endswith('/prompt') for url,_ in wire.calls)
 executed=production.execute(e.nid,e.scope,e.actor,'image',queued['id'],MediaJobAction(expected_version=queued['version'],expected_request_digest=queued['request_digest']),lambda:None)
 assert executed['status']=='AWAITING_REVIEW';candidate=executed['output_candidate']
 with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,candidate['id'])
 posted=[data for url,data in wire.calls if url.endswith('/prompt')];assert len(posted)==1
 sampler=posted[0]['json']['prompt']['3']['inputs'];assert (sampler['steps'],sampler['seed'],sampler['denoise'])==(33,100,0.6)
 assert hashlib.sha256(png()).hexdigest()==candidate['digest']
 approved=production.review(e.nid,e.scope,e.actor,'image',executed['id'],MediaReview(expected_version=executed['version'],expected_request_digest=executed['request_digest'],reviewed_output_digest=candidate['digest']),lambda:None)
 assert approved['status']=='APPROVED';asset=e.service.asset(e.nid,e.scope,candidate['id']);assert asset['provenance']['source_task_id']==approved['id']
 payload={'project':e.nid,'scope':e.scope,'incarnation':e.store.incarnation(e.nid),'source':source,'canvas':canvas,'command':command,'providers':production.providers(e.nid,e.scope,e.actor,lambda:None),
   'preview':preview,'queued':queued,'executed':executed,'approved':approved,'asset':asset,'candidate_png_base64':base64.b64encode(png()).decode(),'model_inference':False}
 input_path=out/'task-owner-input.json';input_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 output_path=out/'task-adoption-output.json';subprocess.run(['node',str(Path(__file__).parent/'fixtures/studio_canvas_image_adoption.cjs'),str(input_path),str(output_path)],check=True,capture_output=True,timeout=30)
 projected=json.loads(output_path.read_text(encoding='utf-8'));definition=projected['definition'];assert definition['cards'][0]['position']==canvas['definition']['cards'][0]['position'] and definition['groups']==canvas['definition']['groups']
 assert definition['cards'][1]==canvas['definition']['cards'][1]
 returned=graph.canvas_views.save(e.nid,e.scope,e.actor,canvas['id'],{'expected_version':canvas['version'],'definition':definition})
 history=graph.canvas_views.history(e.nid,e.scope,e.actor,canvas['id']);restored=graph.canvas_views.restore(e.nid,e.scope,e.actor,canvas['id'],restore_body(history))
 assert returned['version']==2 and restored['version']==3 and restored['definition']==canvas['definition'] and restored['definition_digest']==canvas['definition_digest']
 assert 'incarnation' not in restored and history['incarnation']==e.store.incarnation(e.nid)
 fresh=reopened(e);assert owner(type('Env',(),{'store':fresh.store,'service':fresh})()).canvas_views.get(e.nid,e.scope,e.actor,canvas['id'])==restored
 final_history=graph.canvas_views.history(e.nid,e.scope,e.actor,canvas['id']);assert [r['version'] for r in final_history['items']]==[1,2,3]
 payload.update(returned=returned,history=history,restored=restored,final_history=final_history,prompt_posts=len(posted),frontend_adoption_origin=projected['origin'])
 (out/'dual-loop-fixture.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
