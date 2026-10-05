from types import SimpleNamespace

import pytest

from app.services.v1_capability_service import V1CapabilityService, WorkflowDefinitionIn, WorkflowRunIn
from app.workflow_recipes import RECIPES, recipe_definition


def service(root):
    return V1CapabilityService(root, SimpleNamespace(get=lambda _: {"id":"n"}), SimpleNamespace(), SimpleNamespace())


@pytest.mark.parametrize("recipe", RECIPES)
def test_recipe_output_survives_restart_and_requires_review(tmp_path, recipe):
    first=service(tmp_path)
    definition=first.create_workflow(WorkflowDefinitionIn(**recipe_definition(recipe["id"],"n")))
    run=first.create_workflow_run(definition["id"], WorkflowRunIn(input={"source_text":"人工测试资料一\n人工测试资料二"}),"once")
    assert run["status"]=="WAITING_APPROVAL"
    assert run["node_states"]["prepare"]["output"]["model_called"] is False
    assert run["node_states"]["artifact"]["status"]=="PENDING"
    restarted=service(tmp_path)
    assert restarted.create_workflow_run(definition["id"],WorkflowRunIn(input={"source_text":"人工测试资料一\n人工测试资料二"}),"once")["id"]==run["id"]
    done=restarted.approve_workflow_node(run["id"],"review","author")
    assert done["status"]=="SUCCEEDED"
    assert done["node_states"]["artifact"]["output"]["artifact_type"]==recipe["result"]
    assert done["node_states"]["artifact"]["output"]["applied"] is False
    assert not done["external_ai_calls"]
    with pytest.raises(ValueError):restarted.approve_workflow_node(run["id"],"review","author")


def test_rejection_cancel_and_failed_input_block_downstream(tmp_path):
    engine=service(tmp_path)
    definition=engine.create_workflow(WorkflowDefinitionIn(**recipe_definition("import_knowledge","n")))
    failed=engine.create_workflow_run(definition["id"],WorkflowRunIn(input={}))
    assert failed["status"]=="FAILED" and failed["node_states"]["artifact"]["status"]=="SKIPPED"
    run=engine.create_workflow_run(definition["id"],WorkflowRunIn(input={"source_text":"synthetic"}))
    rejected=engine.reject_workflow_node(run["id"],"review","author")
    assert rejected["status"]=="REJECTED" and rejected["node_states"]["artifact"]["status"]=="SKIPPED"
    with pytest.raises(ValueError):engine.approve_workflow_node(run["id"],"review","author")
    cancelled=engine.create_workflow_run(definition["id"],WorkflowRunIn(input={"source_text":"synthetic"}))
    engine.set_workflow_run_state(cancelled["id"],"cancel")
    with pytest.raises(ValueError):engine.approve_workflow_node(cancelled["id"],"review","author")


def test_agent_trigger_does_not_fake_success_or_advance(tmp_path):
    engine=service(tmp_path)
    definition=engine.create_workflow(WorkflowDefinitionIn(novel_id="n",title="Agent",nodes=[{"id":"agent","type":"agent_task","name":"Writer"},{"id":"after","type":"checkpoint","name":"After"}],edges=[{"source":"agent","target":"after"}]))
    run=engine.create_workflow_run(definition["id"],WorkflowRunIn())
    triggered=engine.trigger_agent_node(run["id"],"agent","author")
    assert triggered["status"]=="RUNNING"
    assert triggered["node_states"]["agent"]["status"]=="QUEUED"
    assert triggered["node_states"]["after"]["status"]=="PENDING"
    engine.claim_agent_task(run["id"],"agent","worker")
    assert engine.list_agent_queue()["items"][0]["status"]=="WORKING"
    engine.set_workflow_run_state(run["id"],"cancel")
    with pytest.raises(ValueError):engine.complete_agent_task(run["id"],"agent","SUCCEEDED",{"text":"late"})
    assert engine.get_workflow_run(run["id"])["node_states"]["after"]["status"]=="PENDING"


def test_workflow_cycle_and_input_limit_are_rejected(tmp_path):
    engine=service(tmp_path)
    with pytest.raises(ValueError):
        engine.create_workflow(WorkflowDefinitionIn(novel_id="n",title="Cycle",nodes=[{"id":"a","type":"checkpoint","name":"A"},{"id":"b","type":"checkpoint","name":"B"}],edges=[{"source":"a","target":"b"},{"source":"b","target":"a"}]))
    definition=engine.create_workflow(WorkflowDefinitionIn(**recipe_definition("planning_draft","n")))
    failed=engine.create_workflow_run(definition["id"],WorkflowRunIn(input={"source_text":"x"*20001}))
    assert failed["status"]=="FAILED"


def test_workflow_api_requires_session_and_hides_other_owner():
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import trusted_session_resolver
    from app.actor_context import SessionContext
    client=TestClient(app)
    assert client.get('/api/workflows').status_code==401
    token='workflow-'+str(uuid4());other='workflow-'+str(uuid4())
    trusted_session_resolver.register(token,SessionContext('session','client','writer-'+token,'workspace'))
    trusted_session_resolver.register(other,SessionContext('other-session','client','reader-'+other,'workspace'))
    novel=client.post('/api/novels',json={'title':'Synthetic workflow owner'}).json()
    response=client.post('/api/workflows/recipes/import_knowledge',json={'novel_id':novel['id']},headers={'X-Session-Token':token})
    assert response.status_code==201,response.text
    workflow=response.json()
    assert client.get('/api/workflows/'+workflow['id'],headers={'X-Session-Token':other}).status_code==403
    listing=client.get('/api/workflows',headers={'X-Session-Token':other}).json()
    assert workflow['id'] not in {row['id'] for row in listing['items']}
    created=client.post('/api/workflows/'+workflow['id']+'/runs',json={'input':{'source_text':'synthetic'}},headers={'X-Session-Token':token}).json()
    assert client.post('/api/workflow-runs/'+created['id']+'/nodes/review/approve',headers={'X-Session-Token':other}).status_code==403
    approved=client.post('/api/workflow-runs/'+created['id']+'/nodes/review/approve?approved_by=forged',headers={'X-Session-Token':token}).json()
    assert approved['node_states']['review']['output']['approved_by']=='writer-'+token


def test_direct_agent_jobs_do_not_bypass_workflow_owner_isolation():
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import trusted_session_resolver
    from app.actor_context import SessionContext
    client=TestClient(app)
    tokens=['agent-owner-'+str(uuid4()),'agent-outsider-'+str(uuid4())]
    for token in tokens:trusted_session_resolver.register(token,SessionContext(token,'client',token,'workspace'))
    novel=client.post('/api/novels',json={'title':'Synthetic agent isolation'}).json()
    client.post('/api/novels/'+novel['id']+'/chapters',json={'title':'Synthetic','content':'Synthetic'})
    headers={'X-Session-Token':tokens[0]};outsider={'X-Session-Token':tokens[1]}
    created=client.post('/api/agent-jobs',json={'agent_id':'planner','novel_id':novel['id'],'chapter':1},headers=headers).json()
    assert client.get('/api/agent-jobs/'+created['id'],headers=outsider).status_code==403
    assert client.get('/api/agent-jobs',headers=outsider).json()['items']==[]
    assert created['id'] not in client.get('/api/agent-jobs/export.csv',headers=outsider).text
    client.post('/api/agent-jobs/'+created['id']+'/cancel',headers=headers)
    retried=client.post('/api/agent-jobs/'+created['id']+'/retry',headers=headers).json()
    assert retried['owner']==created['owner']
    assert client.get('/api/agent-jobs/'+retried['id'],headers=outsider).status_code==403


def test_workflow_deadline_survives_restart_and_prevents_late_approval(tmp_path):
    engine=service(tmp_path)
    definition=engine.create_workflow(WorkflowDefinitionIn(**recipe_definition("import_knowledge","n")))
    run=engine.create_workflow_run(definition["id"],WorkflowRunIn(input={"source_text":"Synthetic"},timeout_seconds=1))
    engine._update("workflow_runs",run["id"],{"started_at":"2000-01-01T00:00:00+00:00"},novel_id="n",expected_version=run["version"],action="TEST_TIME",target_type="WorkflowRun")
    restarted=service(tmp_path)
    assert restarted.get_workflow_run(run["id"])["error"]["code"]=="WORKFLOW_TIMEOUT"
    with pytest.raises(ValueError):restarted.approve_workflow_node(run["id"],"review","author")
