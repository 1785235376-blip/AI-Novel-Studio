"""Real composed /api and /api/v1 B01/B02 routes, File and hosted PostgreSQL."""
import copy
import json
import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from app.experimental.declarative_agents import default_definition
from app.experimental.flags import FLAGS


def test_mounted_template_to_original_planning_and_workflow_then_real_execution(mounted):
    e = mounted; base = e.base; original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    catalog = checked(e.client.get(base + '/template-library'))
    planning = next(r for r in catalog['items'] if r['package']['manifest']['type'] == 'planning')
    copied = checked(e.client.post(base + '/template-library/instances', json={'package_id': planning['id'], 'package_digest': planning['digest'], 'request_id': 'mounted-planning'}), 201)
    actual = checked(e.client.get(base + '/planning/templates'))
    assert copied['linked_target']['id'] in {r['id'] for r in actual['items']}
    workflow = next(r for r in catalog['items'] if r['package']['manifest']['type'] == 'workflow')
    raw = json.dumps(workflow['package'])
    preview = checked(e.client.post(base + '/template-library/preview', json={'package': raw}))
    installed = checked(e.client.post(base + '/template-library/install', json={'package': raw, 'expected_version': preview['expected_version'], 'preview_digest': preview['preview_digest']}))
    copied = checked(e.client.post(base + '/template-library/instances', json={'package_id': workflow['id'], 'package_digest': workflow['digest'], 'request_id': 'mounted-workflow'}), 201)
    authored = checked(e.client.get(base + '/declarative-agents/definitions'))['items'][0]
    assert authored['id'] == copied['linked_target']['id']
    checked(e.client.post(base + '/template-library/packages/' + workflow['id'] + '/uninstall', json={'expected_version': installed['version']}))
    assert checked(e.client.get(base + '/declarative-agents/definitions'))['items'][0]['id'] == authored['id']
    run = checked(e.client.post(base + f'/declarative-agents/definitions/{authored["id"]}/runs', json={'expected_version': authored['version'], 'reviewed_definition_digest': authored['definition_digest'], 'input': {'source_text': '原创合成林舟寻找潮汐地图。'}, 'request_id': 'mounted-run'}), 201)
    assert run['status'] == 'QUEUED'
    waiting = checked(e.client.post(base + f'/declarative-agents/runs/{run["id"]}/execute', json={'expected_version': run['version']}))
    assert waiting['status'] == 'WAITING_APPROVAL' and waiting['node_states']['prepare']['output']['provenance']['method'] == 'LOCAL_RULES'
    result = checked(e.client.post(base + f'/declarative-agents/runs/{run["id"]}/approve', json={'expected_version': waiting['version'], 'note': 'Synthetic explicit review'}))
    assert result['status'] == 'SUCCEEDED' and result['agent_output']['draft'] == run['input']['source_text']
    assert [n['node_id'] for n in result['dispatch_trace']] == ['prepare', 'review', 'artifact']
    assert not result['applied'] and not result['model_called']
    assert e.chapters.get(e.chapter['id']) == original
    assert e.client.get(base + '/declarative-agents/runs').headers['cache-control'] == 'no-store'


def test_mounted_off_v1_dependencies_and_scripts_deny_without_side_effects(mounted, monkeypatch):
    e = mounted
    malicious = default_definition(); malicious['nodes'][0]['type'] = 'python'
    assert e.client.post(e.base + '/declarative-agents/preflight', json=malicious).status_code == 422
    for configured, v1 in [('', 'false'), ('*', 'false'), (','.join(FLAGS), 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', configured); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        assert e.client.get(e.base + '/template-library').status_code == 404
        assert e.client.get(e.base + '/declarative-agents/runs').status_code == 404
        assert e.client.post(e.base + '/declarative-agents/definitions', json={'definition': default_definition()}).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false'); monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'template_library_v2,declarative_agents_v2')
    assert e.client.get(e.base + '/template-library').status_code == 200
    assert e.client.get(e.base + '/declarative-agents/catalog').status_code == 404


def test_mounted_current_collaboration_actor_scope_and_permission_fences(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    authored = checked(e.client.post(e.base + '/declarative-agents/definitions', headers=e.headers, json={'definition': default_definition()}), 201)
    body = {'expected_version': 1, 'reviewed_definition_digest': authored['definition_digest'], 'input': {'source_text': '合成协作测试'}, 'request_id': 'scope-run'}
    run = checked(e.client.post(e.base + f'/declarative-agents/definitions/{authored["id"]}/runs', headers=e.headers, json=body), 201)
    assert checked(e.client.get(e.base + '/declarative-agents/definitions', headers=e.viewer_headers))['items'] == []
    assert e.client.get(e.base + f'/declarative-agents/runs/{run["id"]}', headers=e.viewer_headers).status_code == 404
    assert e.client.post(e.base + f'/declarative-agents/runs/{run["id"]}/execute', headers=e.viewer_headers, json={'expected_version': 1}).status_code == 403
    wrong = {**e.headers, 'X-Branch-ID': e.other_branch}
    assert e.client.post(e.base + f'/declarative-agents/runs/{run["id"]}/execute', headers=wrong, json={'expected_version': 1}).status_code in {403, 404}
    assert e.client.get(e.base + '/template-library').status_code in {401, 403}
    waiting = checked(e.client.post(e.base + f'/declarative-agents/runs/{run["id"]}/execute', headers=e.headers, json={'expected_version': 1}))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    blocked = e.client.post(e.base + f'/declarative-agents/runs/{run["id"]}/approve', headers=e.headers, json={'expected_version': waiting['version']})
    assert blocked.status_code == 501 and blocked.json()['detail']['code'] == 'COLLABORATION_ROUTE_NOT_ENABLED'
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    current = checked(e.client.get(e.base + f'/declarative-agents/runs/{run["id"]}', headers=e.headers))
    assert current['status'] == 'WAITING_APPROVAL' and current['node_states']['artifact']['output'] is None


def test_mounted_real_role_revocation_blocks_pending_run(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    authored = checked(e.client.post(e.base + '/declarative-agents/definitions', headers=e.headers, json={'definition': default_definition()}), 201)
    run = checked(e.client.post(e.base + f'/declarative-agents/definitions/{authored["id"]}/runs', headers=e.headers, json={'expected_version': 1, 'reviewed_definition_digest': authored['definition_digest'], 'input': {'source_text': 'Synthetic'}, 'request_id': 'revoke'}), 201)
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(e.base + f'/declarative-agents/runs/{run["id"]}/execute', headers=e.headers, json={'expected_version': 1}).status_code == 403
    stored = e.store.read(e.nid, e.scope)['collections'][e.experimental.declarative_agents_service.RUNS][run['id']]
    assert stored['status'] == 'QUEUED' and not stored['dispatch_trace']
