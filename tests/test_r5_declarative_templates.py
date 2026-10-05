"""B01/B02 actual deterministic nodes, durable File/real-PG metadata and APIs."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_r4_reader_sessions import env as storage_env
from app.experimental.ux import ReadContext
from app.experimental.planning import PlanningService, digest
from app.experimental.common import StaleSourceError
from app.experimental.template_library import TemplateLibraryService, builtin_packages, parse_package
from app.experimental.template_library_api import create_template_library_router
from app.experimental.declarative_agents import DeclarativeAgentsService, WorkflowAuthoring, default_definition
from app.experimental.declarative_agents_api import create_declarative_agents_router
from app.experimental.declarative_adapter_sdk import AdapterCapabilities, AdapterRequest, LocalRecipeAdapter, TransientAdapterError, AdapterCancelled, run_trusted_local
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture
def env(storage_env):
    e = storage_env
    e.enabled = {'template_library_v2', 'declarative_agents_v2', 'advanced_planning_v2'}
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.library = TemplateLibraryService(e.store, e.novels, e.chapters, planning=e.planning, enabled_features=lambda: e.enabled)
    e.agents = DeclarativeAgentsService(e.store, e.novels, e.chapters, sources=e.sources)
    return e


def package(kind='planning'):
    return next(p for p in builtin_packages() if p['manifest']['type'] == kind)


def install(e, p=None):
    raw = json.dumps(p or package(), ensure_ascii=False)
    preview = e.library.preview(e.ctx, {'package': raw})
    return e.library.install(e.ctx, {'package': raw, 'expected_version': preview['expected_version'], 'preview_digest': preview['preview_digest']})


def instance(e, p=None, request_id='copy-one'):
    p = p or package()
    return e.library.copy(e.ctx, {'package_id': p['manifest']['id'], 'package_digest': digest(p), 'request_id': request_id})


def definition(e, **agent_changes):
    value = default_definition(); value['agent'].update(agent_changes)
    return e.agents.save(e.ctx, None, {'definition': value})


def run(e, d=None, **changes):
    d = d or definition(e)
    return e.agents.create_run(e.ctx, d['id'], {'expected_version': d['version'], 'input': {'source_text': '林舟等潮落。\n同伴举起合成地图。'}, 'request_id': 'run-one', 'reviewed_definition_digest': d['definition_digest'], 'source_version': e.chapters.get(e.cid)['version'] if changes.get('chapter_ids') else None, **changes})


def transition(e, r, action, **body):
    return e.agents.transition(e.ctx, r['id'], action, {'expected_version': r['version'], **body})


def test_builtin_manifest_reuses_planning_and_all_six_types_are_offline(env):
    e = env; original = e.store.read(e.ctx.novel_id, e.ctx.scope)
    catalog = e.library.catalog(e.ctx)
    assert len(catalog['items']) == 8 and set(catalog['types']) == {'planning', 'character', 'screenplay', 'storyboard', 'review', 'workflow'}
    assert all(p['package']['manifest']['license'] == 'CC0-1.0' for p in catalog['items'])
    assert catalog['remote_sync'] == 'DISABLED' and catalog['executable_extensions'] == 'DENY_ALL'
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == original
    e.enabled.clear()
    assert next(p for p in e.library.catalog(e.ctx)['items'] if p['package']['manifest']['type'] == 'planning')['missing_dependencies'] == ['advanced_planning_v2']
    with pytest.raises(ValueError, match='DEPENDENCY'): instance(e)


def test_install_preview_cas_version_rules_owner_and_dependency_not_enabled(env):
    e = env; p = package(); original = copy.deepcopy(e.enabled)
    installed = install(e, p)
    assert installed['version'] == 1 and e.enabled == original
    p['content']['beats']['setup'] = 'New proposed setup'
    with pytest.raises(ValueError, match='manifest version'): install(e, p)
    p['manifest']['version'] = '1.1.0'; updated = install(e, p)
    assert updated['version'] == 2 and updated['package']['content']['beats']['setup'] == 'New proposed setup'
    with pytest.raises(CapabilityVersionConflict): e.library.uninstall(e.ctx, p['manifest']['id'], {'expected_version': 1})
    other = replace(e.ctx, actor='other')
    assert next(x for x in e.library.catalog(other)['items'] if x['id'] == p['manifest']['id'])['version'] == 0


@pytest.mark.parametrize('malicious', [
    lambda p: {**p, 'script': 'python evil.py'},
    lambda p: {**p, 'manifest': {**p['manifest'], 'id': '../../escape'}},
    lambda p: {**p, 'manifest': {**p['manifest'], 'install': 'shell'}},
    lambda p: {**p, 'content': {**p['content'], 'import': 'os'}},
    lambda p: {**p, 'content': {**p['content'], 'credentials': 'synthetic-secret'}},
    lambda p: 'PK' + 'compressed fake archive',
    lambda p: '{' + ' ' * 128001,
    lambda p: {**p, 'manifest': {**p['manifest'], 'screenshot_path': '/private/file'}},
])
def test_malicious_catalog_inputs_denied_without_store_mutation(env, malicious):
    e = env; before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    p = malicious(package()); raw = p if isinstance(p, str) else json.dumps(p)
    with pytest.raises(ValueError): e.library.preview(e.ctx, {'package': raw})
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before


def test_copy_fresh_project_ids_original_planning_and_workflow_targets_survive_uninstall(env):
    e = env; before = copy.deepcopy(e.chapters.get(e.cid))
    installed = install(e)
    copy_one = instance(e); assert instance(e)['id'] == copy_one['id']
    copy_two = instance(e, request_id='copy-two')
    assert copy_one['id'] != copy_two['id'] and copy_one['linked_target']['id'] != copy_two['linked_target']['id']
    template = e.planning._template(e.ctx.novel_id, e.ctx.scope, copy_one['linked_target']['id'])
    assert template.title == package()['content']['title']
    w = instance(e, package('workflow'), 'copy-workflow')
    assert e.agents.definitions(e.ctx)['items'][0]['id'] == w['linked_target']['id']
    e.library.uninstall(e.ctx, package()['manifest']['id'], {'expected_version': installed['version']})
    assert len(e.library.instances(e.ctx)['items']) == 3
    assert e.planning._template(e.ctx.novel_id, e.ctx.scope, copy_one['linked_target']['id']) == template
    assert e.chapters.get(e.cid) == before


def test_favorite_update_compare_preserves_edited_copies_and_target_then_revert(env):
    e = env; p = package(); pid = p['manifest']['id']
    e.library.favorite(e.ctx, pid, {'expected_version': 0, 'favorite': True})
    assert next(x for x in e.library.catalog(e.ctx)['items'] if x['id'] == pid)['favorite']
    copied = instance(e)
    content = copy.deepcopy(copied['content']); content['beats']['setup'] = 'My independent edit'
    edited = e.library.edit(e.ctx, copied['id'], {'expected_version': 1, 'content': content})
    p['manifest']['version'] = '2.0.0'; p['content']['beats']['setup'] = 'Publisher update'; install(e, p)
    assert e.library.instances(e.ctx)['items'][0]['content']['beats']['setup'] == 'My independent edit'
    compared = e.library.compare(e.ctx, copied['id'], {'expected_version': 2, 'package_id': pid})
    assert compared['edited'] and compared['diff']['lines'] and not compared['linked_target_will_change']
    payload = {'expected_version': 2, 'package_id': pid, 'preview_digest': compared['preview_digest']}
    with pytest.raises(ValueError, match='overwrite'): e.library.apply_update(e.ctx, copied['id'], payload)
    result = e.library.apply_update(e.ctx, copied['id'], {**payload, 'overwrite_edited_copy': True})
    assert result['content']['beats']['setup'] == 'Publisher update'
    original_target = e.planning._template(e.ctx.novel_id, e.ctx.scope, copied['linked_target']['id'])
    assert original_target.beats['setup'] != 'Publisher update'
    restored = e.library.revert(e.ctx, copied['id'], {'expected_version': 3, 'restore_version': 2})
    assert restored['version'] == 4 and restored['content']['beats']['setup'] == 'My independent edit'
    assert len(e.library.history(e.ctx, copied['id'])['items']) == 3


def test_template_preview_stale_and_final_revocation_are_atomic(env):
    e = env; p = package(); raw = json.dumps(p); preview = e.library.preview(e.ctx, {'package': raw})
    def denied(): raise HTTPException(403)
    with pytest.raises(HTTPException): e.library.install(e.ctx, {**{'package': raw}, 'expected_version': 0, 'preview_digest': preview['preview_digest']}, denied)
    assert all(not x['installed'] for x in e.library.catalog(e.ctx)['items'])
    with pytest.raises(HTTPException): e.library.copy(e.ctx, {'package_id': p['manifest']['id'], 'package_digest': digest(p), 'request_id': 'rollback'}, denied)
    assert e.library.instances(e.ctx)['items'] == [] and len(e.planning.templates(e.ctx.novel_id, e.ctx.scope)) == 3


def test_actual_original_executor_waits_for_review_emits_trace_and_no_manuscript_write(env):
    e = env; original = copy.deepcopy(e.chapters.get(e.cid)); d = definition(e)
    r = run(e, d)
    assert r['status'] == 'QUEUED' and not r['dispatch_trace']
    assert run(e, d)['id'] == r['id']
    waiting = transition(e, r, 'execute')
    assert waiting['status'] == 'WAITING_APPROVAL'
    assert waiting['node_states']['prepare']['output']['draft'] == r['input']['source_text']
    assert [x['node_id'] for x in waiting['dispatch_trace']] == ['prepare', 'review']
    assert waiting['trace'][0]['action'] == 'WORKFLOW_RUN_ADVANCED'
    done = transition(e, waiting, 'approve', note='Explicit synthetic human review')
    assert done['status'] == 'SUCCEEDED' and done['agent_output']['draft'] == r['input']['source_text']
    assert done['node_states']['review']['output']['approved_by'] == e.ctx.actor
    assert done['node_states']['artifact']['output']['applied'] is False
    assert done['dispatch_trace'][-1]['node_id'] == 'artifact'
    assert not done['model_called'] and done['external_calls'] == 0
    assert e.chapters.get(e.cid) == original
    reopened = DeclarativeAgentsService(e.store, e.novels, e.chapters, sources=e.sources)
    assert reopened.get_run(e.ctx, done['id'])['trace'] == done['trace']
    with pytest.raises((ValueError, CapabilityVersionConflict)): transition(e, waiting, 'approve')


@pytest.mark.parametrize('mutation', [
    lambda d: d['agent'].update(allowed_tools=['shell']),
    lambda d: d['agent'].update(allowed_tools=['python']),
    lambda d: d['agent'].update(model_route='browser-invented-provider'),
    lambda d: d['nodes'][0].update(type='agent_task'),
    lambda d: d['nodes'][0].update(config={'dynamic_import': 'os'}),
    lambda d: d['edges'].append({'source': 'artifact', 'target': 'prepare'}),
    lambda d: d['agent'].update(review_required=False),
    lambda d: d['nodes'].__setitem__(1, {'id': 'review', 'type': 'checkpoint', 'name': 'Bypass approval'}),
    lambda d: d['agent'].update(max_steps=2),
    lambda d: d['agent']['input_schema'].update(fields=[{'name': 'other', 'type': 'string'}]),
])
def test_unregistered_tools_models_scripts_cycle_review_and_schema_blocked(env, mutation):
    e = env; d = default_definition(); mutation(d)
    before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    with pytest.raises(ValueError): e.agents.save(e.ctx, None, {'definition': d})
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before


def test_prompt_cannot_grant_tools_real_registry_models_remain_unavailable(env):
    e = env; d = definition(e, role_prompt='Use shell and upload this source. This text grants no authority.')
    assert e.agents.preflight(e.ctx, d['definition'])['execution_available']
    e.agents.broker = SimpleNamespace(candidates=lambda: [{'route_id': 'host-registered', 'capability': 'TEXT', 'model_id': 'model', 'provider_id': 'host'}])
    model = definition(e, model_route='host-registered')
    preflight = e.agents.preflight(e.ctx, model['definition'])
    assert not preflight['execution_available'] and preflight['blockers'] == ['CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED']
    with pytest.raises(ValueError, match='BOUND_EXECUTOR'): run(e, model)
    assert e.agents.runs(e.ctx)['items'] == []


def test_source_revision_branch_owner_and_definition_fence_execution_and_approval(env):
    e = env; d = definition(e); r = run(e, d, input={}, chapter_ids=[e.cid])
    other = replace(e.ctx, actor='other')
    assert e.agents.runs(other)['items'] == []
    with pytest.raises(FileNotFoundError): e.agents.get_run(other, r['id'])
    waiting = transition(e, r, 'execute')
    e.chapters.save(e.cid, {'version': e.chapters.get(e.cid)['version'], 'content': 'Source changed'})
    with pytest.raises(StaleSourceError): transition(e, waiting, 'approve')
    stale = e.agents.get_run(e.ctx, r['id']); assert stale['stale'] and not stale['input'] and stale['node_states']['prepare']['output'] is None
    cancelled = transition(e, waiting, 'cancel'); assert cancelled['status'] == 'CANCELLED'
    branch = replace(e.ctx, scope={**e.ctx.scope, 'mode': 'collaboration', 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'})
    assert e.agents.runs(branch)['items'] == []
    with pytest.raises(FileNotFoundError): e.agents.get_run(branch, r['id'])
    r = run(e, d, request_id='explicit-second')
    changed = copy.deepcopy(d['definition']); changed['agent']['role_prompt'] = 'edited'
    e.agents.save(e.ctx, d['id'], {'expected_version': d['version'], 'definition': changed})
    with pytest.raises(StaleSourceError): transition(e, r, 'execute')


def test_output_bound_and_cancel_retry_are_real_persisted_states(env):
    e = env; d = definition(e, max_output_bytes=256)
    r = run(e, d, input={'source_text': '合成' * 500})
    failed = transition(e, r, 'execute')
    assert failed['status'] == 'FAILED' and failed['error']['code'] == 'WORKFLOW_OUTPUT_LIMIT'
    assert failed['agent_output'] is None and all(not n['output'] for n in failed['node_states'].values())
    d = definition(e); queued = run(e, d, request_id='second')
    cancelled = transition(e, queued, 'cancel'); assert cancelled['status'] == 'CANCELLED'
    with pytest.raises(ValueError): transition(e, cancelled, 'execute')
    retried = transition(e, cancelled, 'retry'); assert retried['status'] == 'QUEUED' and retried['attempt'] == 2
    waiting = transition(e, retried, 'execute')
    paused = transition(e, waiting, 'pause'); assert paused['status'] == 'PAUSED'
    resumed = transition(e, paused, 'resume'); assert resumed['status'] == 'WAITING_APPROVAL'
    rejected = transition(e, resumed, 'reject'); assert rejected['status'] == 'REJECTED'


def test_dispatch_reauthorization_before_each_real_node_and_atomic_rollback(env, monkeypatch):
    e = env; r = run(e); calls = []
    import app.workflow_recipes as recipes
    original = recipes.execute_local_recipe_node
    revoked = [False]
    def execute(*args):
        result = original(*args); calls.append(args[0]); revoked[0] = True; return result
    monkeypatch.setattr(recipes, 'execute_local_recipe_node', execute)
    def guard():
        if revoked[0]: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): e.agents.transition(e.ctx, r['id'], 'execute', {'expected_version': r['version']}, guard)
    assert calls == ['draft_prepare']
    untouched = e.agents.get_run(e.ctx, r['id'])
    assert untouched['version'] == 1 and untouched['status'] == 'QUEUED' and not untouched['trace']


def test_concurrent_compare_and_set_allows_one_executor(env):
    e = env; r = run(e)
    def attempt(_):
        try: return transition(e, r, 'execute')['status']
        except CapabilityVersionConflict: return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(attempt, range(2)))
    assert sorted(results) == ['CONFLICT', 'WAITING_APPROVAL']


def test_mounted_router_permissions_scope_drift_and_off_are_current(env):
    e = env; auth = {'actor': e.ctx.actor, 'deny': False, 'drift': False, 'calls': 0}; permissions = []
    def authorize(nid, token, branch, permission):
        permissions.append(permission); auth['calls'] += 1
        if auth['deny']: raise HTTPException(403)
        return ('drift' if auth['drift'] and auth['calls'] % 2 == 0 else auth['actor']), e.ctx.scope
    def flag(name):
        if name not in e.enabled: raise HTTPException(404)
    app = FastAPI(); app.include_router(create_template_library_router(e.library, authorize, flag)); app.include_router(create_declarative_agents_router(e.agents, authorize, flag))
    client = TestClient(app); base = f'/novels/{e.ctx.novel_id}/experimental'
    assert client.get(base + '/template-library').headers['cache-control'] == 'no-store'
    d = client.post(base + '/declarative-agents/definitions', json={'definition': default_definition()}).json()
    r = client.post(base + f'/declarative-agents/definitions/{d["id"]}/runs', json={'expected_version': 1, 'input': {'source_text': '合成'}, 'request_id': 'router', 'reviewed_definition_digest': d['definition_digest']}).json()
    waiting = client.post(base + f'/declarative-agents/runs/{r["id"]}/execute', json={'expected_version': 1}).json()
    approved = client.post(base + f'/declarative-agents/runs/{r["id"]}/approve', json={'expected_version': waiting['version']})
    assert approved.status_code == 200 and 'domain.review' in permissions
    auth.update(drift=True, calls=0)
    assert client.get(base + '/declarative-agents/catalog').status_code == 409
    auth.update(drift=False, deny=True)
    assert client.get(base + '/template-library').status_code == 403
    auth.update(deny=False); e.enabled.clear()
    assert client.get(base + '/template-library').status_code == 404
    assert client.get(base + '/declarative-agents/runs').status_code == 404
    assert client.post(base + f'/declarative-agents/runs/{r["id"]}/approve', json={'expected_version': 3}).status_code == 404


def test_sdk_actual_local_adapter_contract_and_minimal_example():
    request = AdapterRequest('draft_prepare', {'source_text': 'Synthetic'}, 'request', 'scope')
    result = run_trusted_local(LocalRecipeAdapter(), request, authorize=lambda: None)
    assert result.output['draft'] == 'Synthetic' and result.attempts == 1 and not result.applied
    from examples.declarative_agents.trusted_local_host import example
    assert example().output['draft'].startswith('林舟')


def test_sdk_cancel_timeout_output_and_explicit_one_retry_contracts():
    request = AdapterRequest('draft_prepare', {'source_text': 'Synthetic'}, 'request', 'scope', retry_limit=1)
    class Flaky(LocalRecipeAdapter):
        attempts = 0
        def execute(self, request):
            self.attempts += 1
            if self.attempts == 1: raise TransientAdapterError()
            return super().execute(request)
    assert run_trusted_local(Flaky(), request, authorize=lambda: None).attempts == 2
    with pytest.raises(AdapterCancelled): run_trusted_local(LocalRecipeAdapter(), request, authorize=lambda: None, cancelled=lambda: True)
    times = iter([0, 0, 20])
    with pytest.raises(TimeoutError): run_trusted_local(LocalRecipeAdapter(), request, authorize=lambda: None, monotonic=lambda: next(times))
    class Oversized(LocalRecipeAdapter):
        capabilities = replace(LocalRecipeAdapter.capabilities, max_output_bytes=1)
    with pytest.raises(ValueError, match='OUTPUT'): run_trusted_local(Oversized(), request, authorize=lambda: None)
    class Remote(LocalRecipeAdapter):
        capabilities = replace(LocalRecipeAdapter.capabilities, network=True)
    with pytest.raises(ValueError, match='EGRESS'): run_trusted_local(Remote(), request, authorize=lambda: None)
    with pytest.raises(ValueError): run_trusted_local(LocalRecipeAdapter(), replace(request, node_type='shell'), authorize=lambda: None)


def test_source_selection_requires_reviewed_version_and_graph_digest(env):
    e = env; d = definition(e)
    with pytest.raises(StaleSourceError): run(e, d, input={}, chapter_ids=[e.cid], source_version=999)
    with pytest.raises(StaleSourceError): run(e, d, reviewed_definition_digest='a' * 64)
    assert e.agents.runs(e.ctx)['items'] == []


def test_original_timeout_survives_restart_and_is_persisted_on_next_action(env):
    e = env; queued = run(e); waiting = transition(e, queued, 'execute')
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        state['collections'][e.agents.RUNS][waiting['id']]['started_at'] = '2000-01-01T00:00:00+00:00'
    e.agents = DeclarativeAgentsService(e.store, e.novels, e.chapters, sources=e.sources)
    failed = transition(e, waiting, 'approve')
    assert failed['status'] == 'FAILED' and failed['error']['code'] == 'WORKFLOW_TIMEOUT'
    assert failed['node_states']['artifact']['output'] is None
    assert failed['trace'][-1]['action'] == 'WORKFLOW_TIMED_OUT'


def test_output_schema_limits_fail_without_a_false_success(env):
    e = env; authored = default_definition(); authored['agent']['output_schema']['fields'][0]['max_length'] = 1
    d = e.agents.save(e.ctx, None, {'definition': authored}); queued = run(e, d)
    waiting = transition(e, queued, 'execute'); failed = transition(e, waiting, 'approve')
    assert failed['status'] == 'FAILED' and failed['error']['code'] == 'AGENT_OUTPUT_SCHEMA_LIMIT' and failed['agent_output'] is None
