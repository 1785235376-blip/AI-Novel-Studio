"""Optional B02 trusted-host hook; original Workflow behavior is unchanged."""
from types import SimpleNamespace
import pytest
from app.services.v1_capability_service import V1CapabilityService, WorkflowDefinitionIn, WorkflowRunIn
from app.workflow_recipes import recipe_definition


def test_original_workflow_without_hook_and_opt_in_per_node_dispatch(tmp_path):
    service = V1CapabilityService(tmp_path, SimpleNamespace(get=lambda _: {'id': 'synthetic'}), SimpleNamespace(), SimpleNamespace())
    definition = service.create_workflow(WorkflowDefinitionIn(**recipe_definition('planning_draft', 'synthetic')))
    body = WorkflowRunIn(input={'source_text': 'Synthetic local source'})
    original = service.create_workflow_run(definition['id'], body)
    assert original['status'] == 'WAITING_APPROVAL'
    approved = service.approve_workflow_node(original['id'], 'review', 'author')
    assert approved['status'] == 'SUCCEEDED' and approved['node_states']['artifact']['output']['applied'] is False
    dispatches = []
    service.workflow_dispatch_guard = lambda run, node: dispatches.append((node['id'], run['status']))
    second = service.create_workflow_run(definition['id'], body)
    assert [row[0] for row in dispatches] == ['prepare', 'review']
    service.approve_workflow_node(second['id'], 'review', 'author')
    assert [row[0] for row in dispatches] == ['prepare', 'review', 'artifact']


def test_hook_revocation_is_not_swallowed_as_a_successful_node(tmp_path):
    service = V1CapabilityService(tmp_path, SimpleNamespace(get=lambda _: {'id': 'synthetic'}), SimpleNamespace(), SimpleNamespace())
    definition = service.create_workflow(WorkflowDefinitionIn(**recipe_definition('planning_draft', 'synthetic')))
    def denied(run, node): raise PermissionError('trusted host revoked dispatch')
    service.workflow_dispatch_guard = denied
    with pytest.raises(PermissionError): service.create_workflow_run(definition['id'], WorkflowRunIn(input={'source_text': 'Synthetic'}))
    row = service.list_workflow_runs(definition['id'])['items'][0]
    assert row['status'] == 'QUEUED' and all(s['status'] == 'PENDING' for s in row['node_states'].values())
