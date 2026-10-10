"""Original SSE response iterator, original session/membership authority, synthetic job.
No TCP server, model, paid API or Windows interactive test.
"""
import os,sys,tempfile,json,socket,asyncio
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
root=Path(tempfile.mkdtemp(prefix='novel-audit-stream-',dir=_out_parent))
os.environ.update(PROJECT_ROOT=str(_repo),NOVEL_DATA_PATH=str(root/'data'),
 HOME=str(root/'home'),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'xdg'),
 ENABLE_CLOUD='false',MOCK_PROVIDER='true',CREDENTIAL_VAULT_BACKEND='memory',STORAGE_BACKEND='file',
 ENABLE_PACKAGED_RUNTIME='false',ENABLE_COLLABORATION_RUNTIME='false',EXPERIMENTAL_FEATURES='',V1_ACCEPTANCE_MODE='true')
sys.path.insert(0,str(_repo));sys.dont_write_bytecode=True
socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('AUDIT_NETWORK_DISABLED'))
from app.main import app
from app import api
from app.config import settings
from app.jobs import Job
from app.actor_context import SessionContext
from app.collaboration import Storyline,Branch
from fastapi import HTTPException
from fastapi.testclient import TestClient
actor='audit-user';workspace='audit-workspace';nid='audit-stream';token='synthetic-test-session-not-a-real-secret'
r=api.collaboration_scope_service.repository
r.provision_initial_workspace(actor,workspace,'Synthetic Workspace','Audit User')
api.novel_service.create({'id':nid,'title':'Synthetic SSE'})
api.collaboration_scope_service.link_project(workspace,nid)
api.collaboration_scope_service.create_storyline(Storyline('audit-storyline',workspace,nid,'Synthetic Story'))
api.collaboration_scope_service.create_branch(Branch('audit-branch',workspace,nid,'audit-storyline','main'))
ch=api.chapter_service.create(nid,{'title':'Synthetic Chapter','content':'Synthetic original'})
session=SessionContext('audit-session','audit-client',actor,workspace)
api.trusted_session_resolver.register(token,session)
object.__setattr__(settings,'enable_collaboration_runtime',True)
job=Job(id='audit-stream-job',operation='rewrite',novel_id=nid,chapter_id=ch['id'],instruction='synthetic',profile='LOCAL_ONLY',
 status='GENERATING',output='BEFORE_REVOCATION',actor_id=actor,session_id=session.session_id,client_id=session.client_id,
 workspace_id=workspace,scope={'kind':'BRANCH','workspace_id':workspace,'project_id':nid,'storyline_id':'audit-storyline','branch_id':'audit-branch'})
api.jobs.jobs[job.id]=job;api.jobs._persist(job)
response=api.events(job.id,x_session_token=token)
async def check():
 first=await response.body_iterator.__anext__()
 api.trusted_session_resolver.revoke(token)
 try:api.generation(job.id,x_session_token=token);revoked_read='UNEXPECTED_ALLOWED'
 except HTTPException as exc:revoked_read=exc.status_code
 # Simulate the next output from an already-running request, after token revocation.
 api.jobs._emit(job,'_AFTER_REVOCATION')
 job.status='COMPLETED';api.jobs._emit(job)
 try:second=await response.body_iterator.__anext__()
 except StopAsyncIteration:second='STOPPED'
 return {'initial_stream_chunk':first,'new_read_after_revocation':revoked_read,
 'existing_stream_after_revocation':second,'post_revocation_output_disclosed':'_AFTER_REVOCATION' in second}
print(json.dumps({'source':'c6f2126115b52e17839d48efea091dc21ec08c61','python':sys.version.split()[0],
 'scope':'Original API StreamingResponse iterator and membership/session services, synthetic File job',
 'result':asyncio.run(check())},ensure_ascii=False,indent=2))

