"""Read-only-source audit: all mutations are to disposable synthetic File data.
Uses actual packaged session issuance and API middleware, not a mocked auth verdict.
No network/model execution or Windows runtime is used.
"""
import os,sys,tempfile,json,socket
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
root=Path(tempfile.mkdtemp(prefix='novel-audit-auth-',dir=_out_parent))
os.environ.update(PROJECT_ROOT=str(_repo), NOVEL_DATA_PATH=str(root/'data'),
 HOME=str(root/'home'), XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'xdg'),
 ENABLE_CLOUD='false',MOCK_PROVIDER='true',CREDENTIAL_VAULT_BACKEND='memory',STORAGE_BACKEND='file',
 ENABLE_PACKAGED_RUNTIME='false',ENABLE_COLLABORATION_RUNTIME='false',FRONTEND_ORIGIN='http://127.0.0.1:5173',
 EXPERIMENTAL_FEATURES='',V1_ACCEPTANCE_MODE='true')
sys.path.insert(0,str(_repo));sys.dont_write_bytecode=True
socket.create_connection=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('AUDIT_NETWORK_DISABLED'))
from app.main import app
from app.config import settings
from app import api
from app.dependencies import packaged_bootstrap_registry
from app.packaging.local_session_bootstrap import LocalSessionBootstrap,TrustedLocalIdentity
from app.packaging.runtime_identity import RuntimeIdentity
from fastapi import HTTPException
from fastapi.testclient import TestClient
# Actual real File repositories create two distinct workspaces. Only workspace B owns the target.
r=api.collaboration_scope_service.repository
r.create_workspace('audit-workspace-a','Audit A','audit-user-a')
r.create_workspace('audit-workspace-b','Audit B','audit-user-b')
novel=api.novel_service.create({'id':'audit-private-b','title':'Synthetic private B'})
r.link_project(novel['id'],'audit-workspace-b')
api.chapter_service.create(novel['id'],{'title':'Synthetic chapter','content':'ONLY_SYNTHETIC_B_CONTENT'})
manager=LocalSessionBootstrap(runtime=RuntimeIdentity.create(),sessions=api.trusted_session_resolver,
 trusted_identity=TrustedLocalIdentity('audit-user-a','audit-workspace-a'),expected_origin=settings.frontend_origin)
packaged_bootstrap_registry.configure(manager)
token=manager.exchange(bootstrap_secret=manager.take_launcher_secret(),runtime_instance_id=manager.runtime.runtime_instance_id,
 origin=settings.frontend_origin,remote_host='127.0.0.1').session_token
object.__setattr__(settings,'enable_packaged_runtime',True)
object.__setattr__(settings,'enable_collaboration_runtime',True)
try:api._authorize_novel_project(novel['id'],token,'domain.write');control='UNEXPECTED_ALLOWED'
except HTTPException as exc:control={'status':exc.status_code,'detail':exc.detail}
# Ordinary in-process HTTP client, with the unmodified router/middleware.
c=TestClient(app,raise_server_exceptions=False)
results={'source':'c6f2126115b52e17839d48efea091dc21ec08c61','environment':'Linux Python '+sys.version.split()[0]+' File TestClient; actual LocalSessionBootstrap issuance', 'real_model_calls':0,
 'control_project_write_authorization':control,'aliases':{}}
for prefix in ['/api','/api/v1']:
 base=f'{prefix}/novels/{novel["id"]}'
 no_token=c.get(base+'/writing-goal')
 headers={'X-Session-Token':token}
 protected=c.get(base+'/export',params={'format':'txt'},headers=headers)
 goal_get=c.get(base+'/writing-goal',headers=headers)
 goal_put=c.put(base+'/writing-goal',headers=headers,json={'target_words':4321,'target_chapters':7,'deadline':'audit-only'})
 raw=c.get(base,headers=headers)
 rows=c.get(base+'/chapters',headers=headers)
 overview=c.get(base+'/overview',headers=headers)
 results['aliases'][prefix]={'no_token':no_token.status_code,'protected_export':protected.status_code,
 'goal_get':goal_get.status_code,'goal_put':goal_put.status_code,
 'goal_persisted':api.novel_service.get(novel['id']).get('writing_goal'),
 'raw_novel_get':raw.status_code,'chapters_get':rows.status_code,
 'chapter_content_disclosed':'ONLY_SYNTHETIC_B_CONTENT' in rows.text,'overview':overview.status_code}
print(json.dumps(results,ensure_ascii=False,indent=2))
(root/'RESULT.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))

