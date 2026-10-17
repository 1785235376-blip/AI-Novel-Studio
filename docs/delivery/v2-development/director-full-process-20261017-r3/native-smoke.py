"""Owned Linux app process, original one-shot bootstrap, manual Director/Graph only."""
from contextlib import closing
import json, os, secrets, socket, subprocess, sys, time
from pathlib import Path
from uuid import uuid4
import httpx

root=Path.cwd();packet=root/'docs/delivery/v2-development/director-full-process-20261017-r3'
runtime=root/'.runtime/director-full-process-20261017-r3';runtime.mkdir(exist_ok=False)
origin='http://127.0.0.1:5198';process=None;streams=[];private=[];calls=[]
result={'status':'RUNNING','response_mocks':False,'development_sessions':False,'lifespan':'original','model_requests':'NOT_REQUESTED','browser':'NOT_RUN','platform':'Linux cloud, not Windows','processes':[]}
def stop():
 global process
 if process is not None:
  process.terminate()
  try:process.wait(timeout=20)
  except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
  result['processes'][-1]['stopped']=process.poll() is not None
  process=None
 for stream in streams:stream.close()
 streams.clear()
def start(phase):
 global process
 with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
  probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
 secret=secrets.token_urlsafe(48);instance=str(uuid4());private.append(secret)
 env=dict(os.environ,PROJECT_ROOT=str(root),NOVEL_DATA_PATH=str(runtime/'novel-data'),
  STORAGE_BACKEND='file',ENABLE_PACKAGED_RUNTIME='true',ENABLE_COLLABORATION_RUNTIME='true',
  COLLABORATION_DEV_SESSIONS_JSON='',PACKAGED_RUNTIME_INSTANCE_ID=instance,PACKAGED_BOOTSTRAP_SECRET=secret,
  FRONTEND_ORIGIN=origin,PACKAGED_FRONTEND_DIST=str(root/'frontend/dist'),PYTHONUTF8='1',
  EXPERIMENTAL_FEATURES='branch_manuscript_v1,narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2',
  ENABLE_CLOUD='false',ENABLE_PROVIDER_FALLBACK='false',CREDENTIAL_VAULT_BACKEND='memory')
 for key in ('HOME','USERPROFILE','LOCALAPPDATA','APPDATA','XDG_DATA_HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME'):
  folder=runtime/key.lower();folder.mkdir(exist_ok=True);env[key]=str(folder)
 stdout=(packet/(phase+'.stdout.log')).open('w');stderr=(packet/(phase+'.stderr.log')).open('w');streams.extend([stdout,stderr])
 process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=stdout,stderr=stderr)
 result['processes'].append({'pid':process.pid,'phase':phase,'port':port,'stopped':False})
 client=httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=15,headers={'Origin':origin})
 deadline=time.monotonic()+45
 while True:
  if process.poll() is not None:raise RuntimeError('Owned app exited before readiness: '+phase)
  try:
   response=client.get('/api/health')
   if response.status_code==200 and response.json().get('storage')=='file':break
  except httpx.HTTPError:pass
  if time.monotonic()>deadline:raise RuntimeError('Owned app readiness timeout: '+phase)
  time.sleep(.2)
 response=client.post('/api/packaged/bootstrap',json={'bootstrap_secret':secret,'runtime_instance_id':instance})
 assert response.status_code==200,'Original bootstrap failed'
 token=response.json()['session_token'];private.append(token)
 return client,token

def call(client,method,path,token=None,branch=None,body=None,status=200):
 headers={}
 if token:headers['X-Session-Token']=token
 if branch:headers['X-Branch-Id']=branch
 response=client.request(method,path,headers=headers,json=body)
 calls.append({'method':method,'path':path,'status':response.status_code})
 assert response.status_code==status, f'{method} {path}: {response.status_code}, expected {status}'
 return response.json() if response.content else None
try:
 client,token=start('first')
 with closing(client):
  call(client,'GET','/api/workspaces',status=401)
  workspace=call(client,'POST','/api/packaged/initial-workspace',token,body={});assert workspace['id']=='workspace-a'
  admin='/api/collaboration/admin/workspaces/workspace-a'
  project=call(client,'POST',admin+'/projects',token,body={'title':'SYNTHETIC native process Director','genre':''},status=201)
  nid=project['id'];navigation=call(client,'GET',admin+'/navigation',token)
  branch=next(p['branch_id'] for p in navigation['eligible_paths'] if p['project_id']==nid)
  base=f'/api/projects/{nid}/studio';docs=f'/api/novels/{nid}/experimental/creative/documents'
  call(client,'POST',base+'/activate',token,branch)
  capabilities=call(client,'GET',f'/api/novels/{nid}/experimental/creative/director-proposals/model-capabilities',token,branch)
  assert capabilities.get('independent_director_contract')=='CREATIVE_DIRECTOR_MODEL_V1'
  result['actual_application_director_advertisement']=True
  content={'mode':'DIRECTOR','title':'SYNTHETIC manually authored Director','source_independent':True,'source_chapter_ids':[], 'scenes':[], 'director_notes':[], 'shots':[], 'video_plan':None,'visual_target':{'style':'ink','atmosphere':'quiet','color':'blue','rhythm':'slow','reference_works':[]}}
  document=call(client,'POST',docs,token,branch,content,201)
  catalog=call(client,'GET',base+'/graphs/planning-documents',token,branch)
  source=next(d for d in catalog['documents'] if d['id']==document['id'])
  pin={k:source[k] for k in ('id','version','digest')}
  definition={'schema_version':4,'title':'SYNTHETIC persisted Director graph','nodes':[{'id':'director','definition_id':'director_plan','parameters':{'document_snapshot':pin}}],'edges':[]}
  graph=call(client,'POST',base+'/graphs',token,branch,{'request_id':'native-process-graph','definition':definition},201)
  path=base+'/graphs/'+graph['id'];assert call(client,'GET',path,token,branch)==graph
  result['saved']={'project_id':nid,'branch_id':branch,'document_pin':pin,'graph':graph}
 old_token=token;stop();client,token=start('restart')
 with closing(client):
  call(client,'GET',path,old_token,branch,status=401)
  call(client,'POST','/api/packaged/initial-workspace',token,body={})
  assert call(client,'GET',path,token,branch)==graph
  assert call(client,'GET',path.replace('/api/','/api/v1/',1),token,branch)==graph
  assert call(client,'GET',docs+'/'+document['id'],token,branch)==document
  changed={**content,'title':'SYNTHETIC explicit later source edit','expected_version':document['version']}
  updated=call(client,'PUT',docs+'/'+document['id'],token,branch,changed)
  assert updated['version']==document['version']+1
  stale=call(client,'GET',path,token,branch)
  assert stale['reference_states'][0]['state']=='STALE'
  assert stale['definition']['nodes'][0]['parameters']['document_snapshot']==pin
  assert stale['version']==graph['version']
  result['restart_readback_equal']=True;result['stale_source_preserved_pin']=True
 result['status']='PASS_FULL_PROCESS_FILE_MANUAL_DIRECTOR_GRAPH'
except BaseException as exc:
 result['status']='FAIL';result['failure_type']=type(exc).__name__;result['failure']=str(exc)
 raise
finally:
 stop();result['calls']=calls
 for log in packet.glob('*.log'):
  value=log.read_text()
  for secret in private:assert secret not in value,'Synthetic credential leaked into process logs'
 (packet/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
