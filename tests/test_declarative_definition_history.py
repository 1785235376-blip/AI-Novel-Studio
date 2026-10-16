"""Original B02 authored-definition history, real File/API, no provider calls."""
import copy
from dataclasses import replace

import pytest

from app.experimental.common import StaleSourceError
from app.experimental.declarative_agents import DeclarativeAgentsService
from app.experimental.planning import digest
from app.experimental.store import ExperimentalStore, canonical
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r5_declarative_templates import env, storage_env, definition, run, transition


def edit(e, saved, title):
    value = copy.deepcopy(saved['definition'])
    value['agent']['title'] = title
    return e.agents.save(e.ctx, saved['id'], {'expected_version': saved['version'], 'definition': value})


def test_history_reopens_and_existing_put_restores_as_new_version_without_reviving_run(env):
    e = env
    first = definition(e, title='Original authored definition')
    waiting = transition(e, run(e, first), 'execute')
    second = edit(e, first, 'Edited authored definition')
    reopened = DeclarativeAgentsService(ExperimentalStore(e.store.root, e.store.backend, e.store.database_url), e.novels, e.chapters, sources=e.sources)
    before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    page = reopened.definition_history(e.ctx, first['id'])
    assert page['current_version'] == 2 and page['current_definition_digest'] == second['definition_digest']
    assert page['next_before_version'] is None
    assert page['items'] == [{'version': 1, 'title': first['definition']['agent']['title'], 'definition_digest': first['definition_digest'], 'updated_at': first['updated_at']}]
    historical = reopened.definition_history_version(e.ctx, first['id'], 1)
    assert set(historical) == {'definition_id', 'current_version', 'current_definition_digest', 'version', 'definition_digest', 'definition'}
    assert historical['definition'] == first['definition']
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    third = reopened.save(e.ctx, first['id'], {'expected_version': second['version'], 'definition': historical['definition']})
    assert third['version'] == 3 and third['definition_digest'] == first['definition_digest']
    assert [item['version'] for item in reopened.definition_history(e.ctx, first['id'])['items']] == [2, 1]
    with pytest.raises(CapabilityVersionConflict):
        reopened.save(e.ctx, first['id'], {'expected_version': 2, 'definition': historical['definition']})
    assert reopened.get_run(e.ctx, waiting['id'])['stale']
    assert reopened.get_run(e.ctx, waiting['id'])['node_states']['prepare']['output'] is None
    with pytest.raises(StaleSourceError):
        reopened.transition(e.ctx, waiting['id'], 'approve', {'expected_version': waiting['version']})


def test_metadata_pages_are_bounded_exclusive_and_not_shifted_by_new_versions(env):
    e = env; saved = definition(e)
    for number in range(2, 24): saved = edit(e, saved, f'Authored version {number}')
    page = e.agents.definition_history(e.ctx, saved['id'])
    assert len(page['items']) == 20
    assert [item['version'] for item in page['items']] == list(range(22, 2, -1))
    assert page['next_before_version'] == 3 and len(canonical(page).encode()) <= 65536
    assert all(set(item) == {'version', 'title', 'definition_digest', 'updated_at'} for item in page['items'])
    saved = edit(e, saved, 'Concurrent later version')
    older = e.agents.definition_history(e.ctx, saved['id'], before_version=page['next_before_version'])
    assert [item['version'] for item in older['items']] == [2, 1] and older['next_before_version'] is None
    assert e.agents.definition_history(e.ctx, saved['id'], before_version=1)['items'] == []
    for changes in ({'limit': 0}, {'limit': 21}, {'before_version': 0}, {'limit': True}):
        with pytest.raises(ValueError): e.agents.definition_history(e.ctx, saved['id'], **changes)
    for version in (0, -1, True):
        with pytest.raises(ValueError): e.agents.definition_history_version(e.ctx, saved['id'], version)
    for version in (saved['version'], saved['version'] + 1):
        with pytest.raises(FileNotFoundError): e.agents.definition_history_version(e.ctx, saved['id'], version)


def test_history_projection_never_reads_or_returns_run_or_reference_data(env, monkeypatch):
    e = env; first = definition(e, role_prompt='An authored chapter-like label is only text.')
    saved = edit(e, first, 'Current')
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        historical = state['collections'][e.agents.DEFINITIONS][saved['id']]['history'][0]
        historical.update(input={'source_text': 'CAPTURED_RUN_SECRET'}, agent_output='CAPTURED_OUTPUT_SECRET',
                          sources={'private-chapter': 'PRIVATE_RESOURCE'}, node_states={'output': 'NODE_SECRET'})
    def forbidden(*args, **kwargs): raise AssertionError('History must not resolve chapter/model resources')
    monkeypatch.setattr(e.sources, '_source', forbidden)
    monkeypatch.setattr(e.agents, '_model_routes', forbidden)
    listing = e.agents.definition_history(e.ctx, saved['id'])
    detail = e.agents.definition_history_version(e.ctx, saved['id'], 1)
    serialized = canonical([listing, detail])
    assert all(value not in serialized for value in ('CAPTURED_RUN_SECRET', 'CAPTURED_OUTPUT_SECRET', 'PRIVATE_RESOURCE', 'NODE_SECRET'))
    assert detail['definition'] == first['definition']


def test_detail_preserves_legacy_authored_shape_and_does_not_reenable_retired_route(env):
    e = env; first = definition(e); saved = edit(e, first, 'Current')
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        historical = state['collections'][e.agents.DEFINITIONS][saved['id']]['history'][0]
        raw = historical['definition']; raw['agent'].pop('capability_requirements'); raw['agent'].pop('runtime_requirement')
        raw['agent']['model_route'] = 'retired-local-route'; raw['nodes'][0]['type'] = 'agent_task'
        historical['definition_digest'] = digest(raw)
    detail = e.agents.definition_history_version(e.ctx, saved['id'], 1)
    assert 'runtime_requirement' not in detail['definition']['agent']
    assert detail['definition_digest'] == digest(detail['definition'])
    with pytest.raises(ValueError, match='registry'):
        e.agents.save(e.ctx, saved['id'], {'expected_version': 2, 'definition': detail['definition']})


@pytest.mark.parametrize('damage', ['extra_authored_field', 'missing_editor_field', 'missing_schema_field', 'digest', 'oversized', 'snapshot_owner', 'snapshot_scope'])
def test_history_detail_fails_closed_without_trimming_or_mutation(env, damage):
    e = env; first = definition(e); saved = edit(e, first, 'Current')
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        historical = state['collections'][e.agents.DEFINITIONS][saved['id']]['history'][0]
        if damage == 'extra_authored_field': historical['definition']['captured_input'] = 'not authored'
        if damage == 'missing_editor_field':
            historical['definition']['agent'].pop('allowed_tools')
            historical['definition_digest'] = digest(historical['definition'])
        if damage == 'missing_schema_field':
            historical['definition']['agent']['input_schema']['fields'][0].pop('max_length')
            historical['definition_digest'] = digest(historical['definition'])
        if damage == 'digest': historical['definition_digest'] = '0' * 64
        if damage == 'oversized': historical['definition']['agent']['role_prompt'] = '字' * 128000
        if damage == 'snapshot_owner': historical['created_by'] = 'another-owner'
        if damage == 'snapshot_scope': historical['scope'] = {'mode': 'local', 'novel_id': 'another-project'}
    before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    with pytest.raises(ValueError, match='DECLARATIVE_HISTORY_'):
        e.agents.definition_history_version(e.ctx, saved['id'], 1)
    if damage in {'extra_authored_field', 'missing_editor_field', 'missing_schema_field'}:
        assert e.agents.definition_history(e.ctx, saved['id'])['items'][0]['version'] == 1
        assert e.agents.definitions(e.ctx)['items'][0]['definition'] == saved['definition']
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before


def test_history_cannot_read_another_owner_or_scope(env):
    e = env; first = definition(e); saved = edit(e, first, 'Current')
    for ctx in (replace(e.ctx, actor='someone-else'), replace(e.ctx, scope={**e.ctx.scope, 'mode': 'collaboration', 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'})):
        with pytest.raises(FileNotFoundError): e.agents.definition_history(ctx, saved['id'])
        with pytest.raises(FileNotFoundError): e.agents.definition_history_version(ctx, saved['id'], 1)


def test_history_metadata_and_detail_limits_are_explicit_errors_not_partial_payloads(env, monkeypatch):
    import app.experimental.declarative_agents as module
    e = env; first = definition(e); saved = edit(e, first, 'Current')
    monkeypatch.setattr(module, 'MAX_HISTORY_METADATA_BYTES', 10)
    with pytest.raises(ValueError, match='DECLARATIVE_HISTORY_METADATA_LIMIT'):
        e.agents.definition_history(e.ctx, saved['id'])
    monkeypatch.setattr(module, 'MAX_PACKAGE_BYTES', 10)
    with pytest.raises(ValueError, match='DECLARATIVE_HISTORY_DETAIL_LIMIT'):
        e.agents.definition_history_version(e.ctx, saved['id'], 1)


def test_mounted_history_gets_and_existing_put_use_original_owner(mounted):
    e = mounted; base = e.base + '/declarative-agents/definitions'
    from app.experimental.declarative_agents import default_definition
    first = checked(e.client.post(base, json={'definition': default_definition()}), 201)
    changed = copy.deepcopy(first['definition']); changed['agent']['title'] = 'Mounted second'
    second = checked(e.client.put(base + '/' + first['id'], json={'expected_version': 1, 'definition': changed}))
    history_path = base + '/' + first['id'] + '/history'
    response = e.client.get(history_path); page = checked(response)
    assert response.headers['cache-control'] == 'no-store' and page['current_version'] == 2
    response = e.client.get(history_path + '/1'); detail = checked(response)
    assert response.headers['cache-control'] == 'no-store' and detail['definition'] == first['definition']
    assert 'history' not in detail and 'scope' not in detail and 'created_by' not in detail
    third = checked(e.client.put(base + '/' + first['id'], json={'expected_version': second['version'], 'definition': detail['definition']}))
    assert third['version'] == 3
    assert e.client.get(history_path + '/3').status_code == 404
    for query in ('?limit=21', '?limit=0', '?before_version=0'):
        assert e.client.get(history_path + query).status_code == 422


def test_mounted_history_uses_current_scope_and_existing_feature_gates(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    from app.experimental.declarative_agents import default_definition
    base = e.base + '/declarative-agents/definitions'
    first = checked(e.client.post(base, headers=e.headers, json={'definition': default_definition()}), 201)
    checked(e.client.put(base + '/' + first['id'], headers=e.headers, json={'expected_version': 1, 'definition': first['definition']}))
    paths = [base + '/' + first['id'] + '/history', base + '/' + first['id'] + '/history/1']
    for path in paths:
        assert e.client.get(path, headers=e.headers).status_code == 200
        assert e.client.get(path, headers=e.viewer_headers).status_code == 404
        assert e.client.get(path, headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code in {403, 404}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    for path in paths: assert e.client.get(path, headers=e.headers).status_code in {404, 501}


@pytest.mark.parametrize('method,suffix', [('definition_history', ''), ('definition_history_version', '/1')])
def test_mounted_history_rechecks_original_authority_after_read(mounted, monkeypatch, method, suffix):
    e = scoped(mounted, monkeypatch)
    from app.experimental.declarative_agents import default_definition
    base = e.base + '/declarative-agents/definitions'
    first = checked(e.client.post(base, headers=e.headers, json={'definition': default_definition()}), 201)
    checked(e.client.put(base + '/' + first['id'], headers=e.headers, json={'expected_version': 1, 'definition': first['definition']}))
    service = e.experimental.declarative_agents_service
    original = getattr(service, method)
    def revoked_after_read(*args):
        result = original(*args)
        e.authorization.revoke_role(e.role, e.lead)
        return result
    monkeypatch.setattr(service, method, revoked_after_read)
    response = e.client.get(base + '/' + first['id'] + '/history' + suffix, headers=e.headers)
    assert response.status_code == 403
    assert 'definition_digest' not in response.text
