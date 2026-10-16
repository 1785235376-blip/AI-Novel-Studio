"""Synthetic provider barrier; unchanged JobManager/API; no real model or network."""
import os,sys,tempfile,json,socket,threading,time
from pathlib import Path
import argparse
_args_parser = argparse.ArgumentParser(description="AI-Novel-Studio synthetic read-only-source reproduction")
_args_parser.add_argument("--repo", required=True, type=Path)
_args_parser.add_argument("--output-dir", type=Path)
_args = _args_parser.parse_args()
_repo = _args.repo.expanduser().resolve()
if not (_repo / "app" / "main.py").is_file():
    _args_parser.error("--repo must point to the fixed checkout root containing app/main.py")
_out_parent = None
if _args.output_dir:
    _out_parent = _args.output_dir.expanduser().resolve()
    _out_parent.mkdir(parents=True, exist_ok=True)
root=Path(tempfile.mkdtemp(prefix='novel-audit-reject-',dir=_out_parent))
os.environ.update(PROJECT_ROOT=str(_repo),NOVEL_DATA_PATH=str(root/'data'),
 HOME=str(root/'home'),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'xdg'),
 ENABLE_CLOUD='false',MOCK_PROVIDER='true',CREDENTIAL_VAULT_BACKEND='memory',STORAGE_BACKEND='file',
 ENABLE_PACKAGED_RUNTIME='false',ENABLE_COLLABORATION_RUNTIME='false',EXPERIMENTAL_FEATURES='',V1_ACCEPTANCE_MODE='true')
sys.path.insert(0,str(_repo));sys.dont_write_bytecode=True
socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('AUDIT_NETWORK_DISABLED'))
from app.main import app
from app import api
from app.runtime import runtime
from fastapi.testclient import TestClient
c=TestClient(app,raise_server_exceptions=False)
novel=api.novel_service.create({'id':'audit-reject','title':'Synthetic reject'})
chapter=api.chapter_service.create(novel['id'],{'title':'Original','content':'Synthetic original only.'})
results=[]
for prefix in ['/api','/api/v1']:
 entered=threading.Event();release=threading.Event();returned=threading.Event()
 def controlled_stream(prompt,model,**kwargs):
  yield 'SYNTHETIC_FIRST_CHUNK'
  entered.set()
  if not release.wait(5):raise RuntimeError('AUDIT_BARRIER_TIMEOUT')
  yield '_LATE_CHUNK'
  returned.set()
 runtime.providers['mock'].stream=controlled_stream
 job=api.jobs.prepare_job('rewrite',{'novel_id':novel['id'],'chapter_id':chapter['id'],'instruction':'Synthetic test',
  'profile':'LOCAL_ONLY','provider_id':'mock','model_id':'mock-writer'})
 from app.router import Route
 api.jobs.prepare_author_request(job,Route('mock','mock-writer'))
 api.jobs.start_prepared(job)
 if not entered.wait(5):
  raise RuntimeError('Provider not entered: '+json.dumps(job.public(),ensure_ascii=False))
 before={'status':job.status,'output':job.output}
 reject=c.post(f'{prefix}/generation/{job.id}/reject')
 rejected={'http':reject.status_code,'state':reject.json()['status'],'cancelled':job.cancelled.is_set()}
 release.set();returned.wait(5)
 for _ in range(200):
  if job.status=='COMPLETED':break
  time.sleep(.01)
 persisted=api.jobs.persistence.get(job.id)
 final=c.get(f'{prefix}/generation/{job.id}')
 results.append({'prefix':prefix,'before':before,'reject':rejected,
 'final_http':final.status_code,'final_status':final.json().get('status'),'final_output':final.json().get('output'),
 'persisted_status':persisted.get('status')})
print(json.dumps({'source':'c6f2126115b52e17839d48efea091dc21ec08c61','python':sys.version.split()[0],
 'scope':'Synthetic provider + real File JobManager/HTTP API; no Windows/model test','results':results},indent=2,ensure_ascii=False))

