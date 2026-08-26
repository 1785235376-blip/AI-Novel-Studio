from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import agent_job_service
from app.dependencies import trusted_session_resolver
from app.model_runtime import TextGenerationResponse,TextModelNodeOutput
from app.actor_context import SessionContext
from app.collaboration import Branch, Storyline, Workspace
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.identity import User, WorkspaceMembership
from app.dependencies import collaboration_scope_service, identity_service, authorization_service
import time


def setup_novel(client):
    client.headers.update(trusted_agent_headers())
    novel=client.post('/api/novels',json={'title':f'Agent Job {uuid4()}'}).json();client.post(f"/api/novels/{novel['id']}/chapters",json={'title':'第一章','content':'雾港封锁。'});return novel['id']

def trusted_agent_headers():
    token=f'agent-job-test-{uuid4()}'
    trusted_session_resolver.register(token,SessionContext(actor_id='agent-job-test',workspace_id='workspace-a',session_id='session',client_id='test'))
    return {'X-Session-Token':token}

def create_agent_job(client,payload):
    return client.post('/api/agent-jobs',json=payload,headers=trusted_agent_headers())

def test_agent_job_read_endpoints_require_trusted_session():
    client=TestClient(app)
    assert client.get('/api/agent-jobs').status_code==401
    assert client.get('/api/agent-jobs/export.csv').status_code==401
    assert client.get('/api/agent-jobs/audit',params={'novel_id':'n','branch_id':'b'}).status_code==401
    assert client.get('/api/agent-jobs/audit.csv',params={'novel_id':'n','branch_id':'b'}).status_code==401
    assert client.get('/api/agent-jobs',headers={'X-Session-Token':'invalid'}).status_code==401

def test_agent_job_listing_accepts_registered_trusted_session():
    client=TestClient(app)
    assert client.get('/api/agent-jobs',headers=trusted_agent_headers()).status_code==200

def test_agent_job_branch_capability_rejects_unknown_branch():
    client=TestClient(app);nid=setup_novel(client);headers=trusted_agent_headers()
    response=client.post('/api/agent-jobs',headers=headers,json={'agent_id':'planner','novel_id':nid,'chapter':1,'branch_id':'missing-branch'})
    assert response.status_code==403 and response.json()['detail']['code']=='AGENT_JOB_SCOPE_FORBIDDEN'


def test_branch_scoped_agent_job_lifecycle_and_export_audit():
    """A valid branch job must remain scoped across reads, retry, and export."""
    client = TestClient(app)
    novel = client.post('/api/novels', json={'title': f'Agent Branch {uuid4()}'}).json()
    nid = novel['id']
    client.post(f"/api/novels/{nid}/chapters", json={'title': '第一章', 'content': '雾港封锁。'})

    workspace_id = f"agent-workspace-{uuid4()}"
    actor_id = f"agent-actor-{uuid4()}"
    storyline_id = f"agent-storyline-{uuid4()}"
    branch_id = f"agent-branch-{uuid4()}"
    collaboration_scope_service.create_workspace(Workspace(workspace_id, 'Agent Jobs'))
    collaboration_scope_service.link_project(workspace_id, nid)
    collaboration_scope_service.create_storyline(Storyline(storyline_id, workspace_id, nid, 'Main'))
    collaboration_scope_service.create_branch(Branch(branch_id, workspace_id, nid, storyline_id, 'main'))
    identity_service.create_user(User(actor_id, 'Agent Actor'))
    identity_service.add_membership(WorkspaceMembership(f"membership-{uuid4()}", actor_id, workspace_id))
    scope = AuthorizationScope(ScopeKind.BRANCH, workspace_id, nid, storyline_id, branch_id)
    authorization_service.assign_role(
        DomainRoleAssignment(
            f"role-{uuid4()}", actor_id, DomainRole.DOMAIN_LEAD,
            ModalityDomain.NOVEL, scope, actor_id,
        )
    )
    token = f"branch-agent-{uuid4()}"
    trusted_session_resolver.register(token, SessionContext(actor_id, 'test-client', actor_id, workspace_id))
    headers = {'X-Session-Token': token}

    created = client.post(
        '/api/agent-jobs', headers=headers,
        json={'agent_id': 'planner', 'novel_id': nid, 'chapter': 1, 'branch_id': branch_id},
    )
    assert created.status_code == 202
    job = created.json()
    assert job['branch_id'] == branch_id
    assert client.get(f"/api/agent-jobs/{job['id']}", headers=headers).status_code == 200

    cancelled = client.post(f"/api/agent-jobs/{job['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()['status'] == 'CANCELLED'
    retried = client.post(f"/api/agent-jobs/{job['id']}/retry", headers=headers)
    assert retried.status_code == 202 and retried.json()['branch_id'] == branch_id

    exported = client.get('/api/agent-jobs/export.csv', headers=headers, params={'branch_id': branch_id})
    assert exported.status_code == 200 and 'id,agent_id' in exported.text
    audit = client.get('/api/agent-jobs/audit', headers=headers, params={'novel_id': nid, 'branch_id': branch_id})
    assert audit.status_code == 200 and audit.json()['total'] >= 1

def test_agent_job_audit_rejects_unknown_branch():
    client=TestClient(app);nid=setup_novel(client)
    response=client.get('/api/agent-jobs/audit',params={'novel_id':nid,'branch_id':'missing-branch'},headers=trusted_agent_headers())
    assert response.status_code==403 and response.json()['detail']['code']=='AGENT_JOB_SCOPE_FORBIDDEN'

def test_agent_job_audit_csv_rejects_unknown_branch():
    client=TestClient(app);nid=setup_novel(client)
    response=client.get('/api/agent-jobs/audit.csv',params={'novel_id':nid,'branch_id':'missing-branch'},headers=trusted_agent_headers())
    assert response.status_code==403 and response.json()['detail']['code']=='AGENT_JOB_SCOPE_FORBIDDEN'

def test_legacy_export_does_not_claim_audit_without_branch():
    client=TestClient(app)
    response=client.get('/api/agent-jobs/export.csv',headers=trusted_agent_headers())
    assert response.status_code==200 and 'id,agent_id' in response.text


def test_agent_job_lifecycle_records_context_and_structured_output():
    client=TestClient(app);nid=setup_novel(client);created=create_agent_job(client,{'agent_id':'planner','novel_id':nid,'chapter':1,'instruction':'规划第二幕'}).json()
    assert created['status']=='QUEUED' and len(created['context_hash'])==64 and created['chapter_version']==1
    completed=client.post(f"/api/agent-jobs/{created['id']}/execute").json();stored=client.get(f"/api/agent-jobs/{created['id']}",headers=trusted_agent_headers()).json()
    assert completed['status']=='COMPLETED' and stored['provider']=='deterministic-local'
    output=stored['result']['structured_output'];assert output['schema']=='story_plan_proposal' and output['context_hash']==created['context_hash']


def test_agent_job_preserves_requested_model_metadata():
    client=TestClient(app);nid=setup_novel(client);created=create_agent_job(client,{'agent_id':'writer','novel_id':nid,'chapter':1,'provider_id':'deepseek','model_id':'deepseek-chat'}).json();completed=client.post(f"/api/agent-jobs/{created['id']}/execute").json()
    assert completed['provider']=='deepseek' and completed['model']=='deepseek-chat'


def test_completed_agent_job_cannot_execute_twice():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'continuity','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{created['id']}/execute")
    assert client.post(f"/api/agent-jobs/{created['id']}/execute").status_code==400


def test_agent_job_review_accepts_without_applying_output():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{created['id']}/execute")
    accepted=client.post(f"/api/agent-jobs/{created['id']}/review",json={'decision':'ACCEPTED','reviewed_by':'author-1','note':'方向可用'}).json()
    assert accepted['status']=='ACCEPTED' and accepted['review']['applied'] is False
    assert accepted['review']['reviewed_by']=='author-1' and len(accepted['review']['output_hash'])==64


def test_agent_job_review_rejects_and_prevents_second_decision():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'editor','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{created['id']}/execute")
    rejected=client.post(f"/api/agent-jobs/{created['id']}/review",json={'decision':'REJECTED','reviewed_by':'author-1'}).json();assert rejected['status']=='REJECTED'
    assert client.post(f"/api/agent-jobs/{created['id']}/review",json={'decision':'ACCEPTED','reviewed_by':'author-1'}).status_code==400


def test_agent_job_cannot_be_reviewed_before_completion():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'director','novel_id':nid,'chapter':1}).json()
    assert client.post(f"/api/agent-jobs/{created['id']}/review",json={'decision':'ACCEPTED','reviewed_by':'author-1'}).status_code==400


def test_accepted_agent_actions_apply_with_before_after_snapshots():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{created['id']}/execute")
    actions=[{'type':'outline.update','payload':{'theme':'信任','premise':'追查雾港','structure':'THREE_ACT','beginning':'抵达','middle':'背叛','ending':'公开真相','main_conflict':'真相与安全','climax':'灯塔','status':'ACTIVE'}},{'type':'volume.upsert','id':'fog','payload':{'title':'迷雾卷','sequence':1,'goal':'建立悬念','summary':'进入雾港','start_chapter':1,'end_chapter':8,'status':'WRITING'}},{'type':'scene.upsert','id':'arrival','payload':{'title':'抵达雾港','sequence':1,'volume_id':'fog','chapter_id':f'{nid}:1','location_id':'','characters':[],'purpose':'展示封锁','conflict':'证件失效','outcome':'潜入码头','status':'PLANNED'}}]
    client.post(f"/api/agent-jobs/{created['id']}/review",json={'decision':'ACCEPTED','reviewed_by':'author-1','actions':actions});applied=client.post(f"/api/agent-jobs/{created['id']}/apply",json={'applied_by':'author-1'}).json()
    assert applied['review']['applied'] is True and len(applied['application']['actions'])==3
    assert applied['application']['actions'][0]['before']=={} and applied['application']['actions'][0]['after']['theme']=='信任'
    assert client.get(f'/api/novels/{nid}/volumes').json()[0]['id']=='fog' and client.get(f'/api/novels/{nid}/scenes').json()[0]['id']=='arrival'


def test_agent_application_rejects_unknown_action_and_repeat_apply():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{created['id']}/execute");client.post(f"/api/agent-jobs/{created['id']}/review",json={'decision':'ACCEPTED','reviewed_by':'author','actions':[{'type':'chapter.overwrite','payload':{}}]})
    assert client.post(f"/api/agent-jobs/{created['id']}/apply",json={'applied_by':'author'}).status_code==400
    second=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{second['id']}/execute");client.post(f"/api/agent-jobs/{second['id']}/review",json={'decision':'ACCEPTED','reviewed_by':'author','actions':[]});assert client.post(f"/api/agent-jobs/{second['id']}/apply",json={'applied_by':'author'}).status_code==200;assert client.post(f"/api/agent-jobs/{second['id']}/apply",json={'applied_by':'author'}).status_code==400


def test_model_execution_uses_requested_route_and_validates_structure(monkeypatch):
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1,'provider_id':'deepseek','model_id':'deepseek-chat','execution_mode':'model'}).json()
    class Node:
        def execute(self,_):
            text='{"schema":"story_plan_proposal","agent_id":"planner","summary":"第二幕方案","proposals":[],"findings":[],"context_hash":"'+created['context_hash']+'"}'
            response=TextGenerationResponse(text,'completed','deepseek','deepseek-chat');return TextModelNodeOutput(text,response,created['id'])
    monkeypatch.setattr(agent_job_service.runtime,'prepare_text_route',lambda *_:Node());completed=client.post(f"/api/agent-jobs/{created['id']}/execute").json()
    assert completed['status']=='COMPLETED' and completed['provider']=='deepseek' and completed['model']=='deepseek-chat' and completed['fallback_used'] is False


def test_model_execution_fails_closed_on_invalid_structure(monkeypatch):
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1,'provider_id':'deepseek','model_id':'deepseek-chat','execution_mode':'model'}).json()
    class Node:
        def execute(self,_):
            response=TextGenerationResponse('{"summary":"missing contract"}','completed','deepseek','deepseek-chat');return TextModelNodeOutput(response.text,response,created['id'])
    monkeypatch.setattr(agent_job_service.runtime,'prepare_text_route',lambda *_:Node());failed=client.post(f"/api/agent-jobs/{created['id']}/execute").json()
    assert failed['status']=='FAILED' and failed['error_code']=='INVALID_STRUCTURED_OUTPUT' and failed['fallback_used'] is False


def test_model_mode_requires_explicit_provider_and_model():
    client=TestClient(app);nid=setup_novel(client);response=client.post('/api/agent-jobs',json={'agent_id':'writer','novel_id':nid,'chapter':1,'execution_mode':'model'})
    assert response.status_code==400


def test_async_agent_job_completes_and_can_be_polled():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{created['id']}/start")
    for _ in range(50):
        stored=client.get(f"/api/agent-jobs/{created['id']}",headers=trusted_agent_headers()).json()
        if stored['status']=='COMPLETED':break
        time.sleep(.01)
    assert stored['status']=='COMPLETED'


def test_agent_job_cancel_is_terminal_against_late_model_result(monkeypatch):
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1,'provider_id':'deepseek','model_id':'deepseek-chat','execution_mode':'model'}).json()
    class Node:
        def execute(self,_):
            time.sleep(.15);text='{"schema":"story_plan_proposal","agent_id":"planner","summary":"late","proposals":[],"findings":[],"context_hash":"'+created['context_hash']+'"}';response=TextGenerationResponse(text,'completed','deepseek','deepseek-chat');return TextModelNodeOutput(text,response,created['id'])
    monkeypatch.setattr(agent_job_service.runtime,'prepare_text_route',lambda *_:Node());client.post(f"/api/agent-jobs/{created['id']}/start");time.sleep(.03);cancelled=client.post(f"/api/agent-jobs/{created['id']}/cancel").json();time.sleep(.2);stored=client.get(f"/api/agent-jobs/{created['id']}",headers=trusted_agent_headers()).json()
    assert cancelled['status']=='CANCELLED' and stored['status']=='CANCELLED'


def test_agent_job_timeout_is_terminal_and_retry_creates_new_job(monkeypatch):
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1,'provider_id':'deepseek','model_id':'deepseek-chat','execution_mode':'model','timeout_seconds':1}).json()
    class Node:
        def execute(self,_):
            time.sleep(1.2);text='{"schema":"story_plan_proposal","agent_id":"planner","summary":"late","proposals":[],"findings":[],"context_hash":"'+created['context_hash']+'"}';response=TextGenerationResponse(text,'completed','deepseek','deepseek-chat');return TextModelNodeOutput(text,response,created['id'])
    monkeypatch.setattr(agent_job_service.runtime,'prepare_text_route',lambda *_:Node());client.post(f"/api/agent-jobs/{created['id']}/start");time.sleep(1.1);stored=client.get(f"/api/agent-jobs/{created['id']}",headers=trusted_agent_headers()).json();retried=client.post(f"/api/agent-jobs/{created['id']}/retry").json()
    assert stored['status']=='FAILED' and stored['error_code']=='TIMEOUT';assert retried['id']!=created['id'] and retried['retry_of']==created['id'] and retried['status']=='QUEUED'


def test_completed_agent_job_is_not_retryable_or_cancellable():
    client=TestClient(app);nid=setup_novel(client);created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':nid,'chapter':1}).json();client.post(f"/api/agent-jobs/{created['id']}/execute")
    assert client.post(f"/api/agent-jobs/{created['id']}/retry").status_code==400 and client.post(f"/api/agent-jobs/{created['id']}/cancel").status_code==400
