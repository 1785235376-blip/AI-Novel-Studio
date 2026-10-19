"""Schema7 original mounted File authority; no default capability enablement."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_creative_graph_api import graph_client, scoped_graph_client
from test_v2_independent_workspace_api import client
from test_v2_graph_local_conditions import definition
from test_v2_local_subgraph import child_definition


def enable(monkeypatch):
    monkeypatch.setenv('CREATIVE_GRAPH_CONDITIONS_V1', '1')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)


def create(e, value, headers=None):
    return checked(e.client.post(e.graph_base, headers=headers,
        json={'request_id': uuid4().hex, 'definition': value}), 201)


def admit(e, graph, headers=None):
    base = e.graph_base + '/' + graph['id']
    preview = checked(e.client.post(base + '/preflight', headers=headers,
        json={'expected_version': graph['version']}))
    assert preview['executable'] and preview['graph_schema_version'] == 7
    run = checked(e.client.post(base + '/runs', headers=headers, json={
        'expected_graph_version': graph['version'], 'reviewed_preflight_digest': preview['preflight_digest'],
        'request_id': uuid4().hex}), 201)
    return preview, run


def grant(e, permissions):
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    for name in permissions:
        e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, name,
            ModalityDomain.NOVEL, scope, e.lead))


def test_schema7_create_save_preflight_and_admission_require_source_read_but_schema1_write_stays(scoped_graph_client, monkeypatch):
    enable(monkeypatch); e = scoped_graph_client
    graph = create(e, definition(), e.headers)
    preview, _ = admit(e, graph, e.headers)
    legacy = create(e, child_definition(), e.headers)
    path = e.graph_base + '/' + graph['id']
    grant(e, ('domain.write',))
    before = deepcopy(e.graphs.store.read(e.nid, graph['scope']))
    responses = [
        e.client.post(e.graph_base, headers=e.headers, json={'request_id': uuid4().hex, 'definition': graph['definition']}),
        e.client.put(path, headers=e.headers, json={'expected_version': graph['version'], 'definition': graph['definition']}),
        e.client.post(path + '/preflight', headers=e.headers, json={'expected_version': graph['version']}),
        e.client.post(path + '/runs', headers=e.headers, json={'expected_graph_version': graph['version'],
            'reviewed_preflight_digest': preview['preflight_digest'], 'request_id': uuid4().hex}),
    ]
    assert all(response.status_code == 403 and 'Pinned authored source' not in response.text for response in responses)
    assert e.graphs.store.read(e.nid, graph['scope']) == before
    saved = checked(e.client.put(e.graph_base + '/' + legacy['id'], headers=e.headers,
        json={'expected_version': legacy['version'], 'definition': legacy['definition']}))
    assert saved['version'] == legacy['version'] + 1 and saved['definition'] == legacy['definition']


@pytest.mark.parametrize('waiting', [False, True])
def test_schema7_saved_run_actions_keep_read_guard_and_original_cancel_reject(scoped_graph_client, monkeypatch, waiting):
    enable(monkeypatch); e = scoped_graph_client
    graph = create(e, definition(), e.headers); _, run = admit(e, graph, e.headers)
    path = e.studio_base + '/graph-runs/' + run['id']
    if waiting:
        run = checked(e.client.post(path + '/execute', headers=e.headers, json={'expected_version': run['version']}))
    grant(e, ('domain.write', 'domain.review'))
    before = deepcopy(e.graphs.store.read(e.nid, graph['scope']))
    body = {'expected_version': run['version']}
    if waiting: body.update(node_id=run['review']['node_id'], reviewed_output_digest=run['review']['output_digest'])
    denied = e.client.post(path + ('/approve' if waiting else '/execute'), headers=e.headers, json=body)
    assert denied.status_code == 403 and 'Selected A' not in denied.text
    assert e.client.get(path, headers=e.headers).status_code == 403
    assert e.graphs.store.read(e.nid, graph['scope']) == before
    cleaned = checked(e.client.post(path + ('/reject' if waiting else '/cancel'), headers=e.headers, json=body))
    assert cleaned['status'] == ('REJECTED' if waiting else 'CANCELLED') and cleaned['review'] is None
    assert all(item['output'] is None for item in cleaned['node_states'].values())


def test_opted_in_schema7_uses_real_guarded_local_run_and_exact_original_human_review(scoped_graph_client, monkeypatch):
    enable(monkeypatch); e = scoped_graph_client
    graph = create(e, definition(), e.headers); _, run = admit(e, graph, e.headers)
    path = e.studio_base + '/graph-runs/' + run['id']
    run = checked(e.client.post(path + '/execute', headers=e.headers, json={'expected_version': run['version']}))
    assert run['status'] == 'WAITING_APPROVAL' and not run['model_called'] and not run['external_calls']
    assert run['node_states']['no']['status'] == run['node_states']['no_review']['status'] == 'SKIPPED'
    review = run['review']; assert review['draft'] == {'origin': 'MANUAL', 'text': 'Selected A'}
    accepted = checked(e.client.post(path + '/approve', headers=e.headers,
        json={'expected_version': run['version'], 'node_id': review['node_id'], 'reviewed_output_digest': review['output_digest']}))
    assert accepted['status'] == 'SUCCEEDED' and accepted['reviewed'] and not accepted['applied']
    assert checked(e.client.get(path, headers=e.headers)) == accepted


def test_default_schema7_opt_in_remains_closed_without_any_global_enablement(graph_client, monkeypatch):
    e = graph_client
    monkeypatch.delenv('CREATIVE_GRAPH_CONDITIONS_V1', raising=False)
    before = deepcopy(e.graphs.store.read(e.nid, e.scope))
    response = e.client.post(e.graph_base, json={'request_id': uuid4().hex, 'definition': definition()})
    assert response.status_code == 422
    assert e.graphs.store.read(e.nid, e.scope) == before
    catalog = checked(e.client.get(e.graph_base + '/catalog'))
    assert all(item['id'] != 'local_condition' for item in catalog['definitions'])
