"""Actual complete-chain File/HTTP read costs on small synthetic saved owners."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, create_timeline, snapshot
from studio_asset_usage_resource_meter import four_page_observations, measured_cost

pytestmark = pytest.mark.file_backend_only


def destination_for(e, name):
    # Recorded runs supply an evidence run root. Ordinary regression runs keep
    # optional measurements beside, not inside, the synthetic project fixture.
    return Path(os.environ.get('STUDIO_TEST_RUN_ROOT', str(e.rig.root.parent))) / name


def assert_guarded_cost_contract(record, authority_guarded):
    assert len(record['usage_budgets']) == 1, 'one fresh budget must span the entire HTTP request'
    observed_guarded = sum(row['read_bytes'] for row in record['rows'] if row['physical_input_via_usage_budget'])
    assert observed_guarded == record['usage_budgets'][0]['charged_read_bytes']
    if authority_guarded:
        assert all(row['physical_input_via_usage_budget'] for row in record['rows'] if row['read_calls'])
        assert record['read_bytes'] == record['usage_budgets'][0]['charged_read_bytes']


def test_resource_read_costs_initialized_http_and_cold_process(usage_rig, monkeypatch):
    e = usage_rig
    graph_create(e, 3, 'resource-cost-graph')
    create_timeline(e)
    before = snapshot(e.rig.root)
    records = four_page_observations(e.client, e.rig.root, e.rig.nid, e.asset['id'], e.headers, monkeypatch)
    for record in records:
        # This schema1 sample only reads JSON files: baseline can decode once
        # per read. Chunked guarded input adds reads without adding decodes.
        assert record['read_calls'] >= record['json_decodes'] > 0
        authority_guarded = record['declared_authority_reads_in_budget']
        assert any(row['category'] == 'project_metadata' and row['physical_input_via_usage_budget'] == authority_guarded
                   for row in record['rows'])
        assert any(row['category'] == 'scope_json' and row['physical_input_via_usage_budget']
                   for row in record['rows'])
        assert record['write_calls'] == record['created_directories'] == 0
        assert record['write_opens'] > 0  # Original coordinator remains write-capable.
        assert_guarded_cost_contract(record, authority_guarded)
    assert snapshot(e.rig.root) == before
    destination = destination_for(e, 'resource-costs-initialized-http.json')
    destination.write_text(json.dumps({'scenario': '1 saved Graph with3 direct pins +1 saved Timeline with1 direct pin',
        'phase': 'initialized in-process original main.app HTTP; OS cache not cleared',
        'records': records}, indent=2), encoding='utf-8')
    print('RESOURCE_COSTS_JSON ' + str(destination))

    cold = destination.with_name('resource-costs-fresh-process.json')
    command = [sys.executable, 'scripts/measure_asset_usage_resource_process.py', str(e.rig.root),
               e.rig.nid, e.asset['id'], str(cold)]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True,
        text=True, encoding='utf-8', errors='replace', timeout=180)
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert cold.is_file()
    for record in json.loads(cold.read_text(encoding='utf-8'))['records']:
        assert_guarded_cost_contract(record, record['declared_authority_reads_in_budget'])
    assert snapshot(e.rig.root) == before


def test_resource_schema3_binary_owner_cost_is_measured(usage_rig, monkeypatch):
    e = usage_rig
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',
        'narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    created = e.graph.create(e.rig.nid, e.rig.scope, e.actor, {'request_id': 'resource-binary-owner',
        'definition': {'schema_version': 3, 'title': 'Synthetic original schema3 binary reference',
            'nodes': [{'id': 'binary-pin', 'definition_id': 'asset_reference', 'parameters': {
                'asset_id': e.asset['id'], 'version': e.asset['version'],
                'digest': e.asset['sha256'], 'kind': 'audio'}}]}})
    from app.creative.asset_usage_budget import usage_read_budget
    with usage_read_budget():
        assert e.graph.usage_get(e.rig.nid, e.rig.scope, e.actor, created['id'], lambda: None)['id'] == created['id']
    before = snapshot(e.rig.root)
    response, metrics = measured_cost(e.rig.root, monkeypatch, lambda: e.client.get(
        e.usage_base + '/studio-asset-usages', headers=e.headers, params={'limit': 2, 'sources': 'graph'}))
    assert response.status_code == 200, (response.text, metrics['reader_errors'])
    assert len(response.json()['items']) == 1 and response.json()['total'] == 1
    binaries = [row for row in metrics['rows'] if row['category'] == 'asset_binary']
    assert binaries and sum(row['read_bytes'] for row in binaries) > 0
    authority_guarded = response.json()['budgets'].get('authority_reads_in_budget', False)
    assert all(row['physical_input_via_usage_budget'] == authority_guarded for row in binaries)
    assert_guarded_cost_contract(metrics, authority_guarded)
    assert metrics['write_calls'] == metrics['created_directories'] == 0
    assert snapshot(e.rig.root) == before
    destination = destination_for(e, 'resource-costs-schema3-binary.json')
    destination.write_text(json.dumps({'scenario': 'original saved schema3 Graph direct audio pin; no dispatch',
        'records': [{'request_phase': 'first_page_schema3', 'response_bytes': len(response.content),
            'returned': 1, **metrics}]}, indent=2), encoding='utf-8')
    print('RESOURCE_SCHEMA3_COSTS_JSON ' + str(destination))


def test_resource_real_collaboration_authority_cost_is_measured(usage_rig, monkeypatch):
    from app import main, dependencies
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.packaging.bootstrap_api import PackagedBootstrapRegistry
    from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
    from app.packaging.runtime_identity import RuntimeIdentity
    from test_studio_asset_query import shared_scope
    e = usage_rig
    scope, headers = shared_scope(e.rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', e.rig.nid)
    e.rig.grants.assign_permission(PermissionAssignment('resource-write', 'reader', 'domain.write',
        ModalityDomain.NOVEL, grant_scope, 'synthetic cost fixture'))
    object.__setattr__(e.rig.settings, 'enable_packaged_runtime', True)
    runtime = RuntimeIdentity.create()
    manager = LocalSessionBootstrap(runtime=runtime, sessions=e.rig.sessions,
        trusted_identity=TrustedLocalIdentity('reader', 'query-workspace'),
        expected_origin='http://127.0.0.1:41831')
    token = manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
        runtime_instance_id=runtime.runtime_instance_id, origin=manager.expected_origin,
        remote_host='127.0.0.1').session_token
    registry = PackagedBootstrapRegistry()
    registry.configure(manager)
    monkeypatch.setattr(main, 'packaged_bootstrap_registry', registry)
    monkeypatch.setattr(dependencies, 'packaged_bootstrap_registry', registry)
    headers = {**headers, 'X-Session-Token': token}
    e.headers = headers
    response = e.client.post(e.base + '/activate', headers=headers)
    assert response.status_code == 200, response.text
    e.asset = e.rig.seed('synthetic-authority-cost.wav', 'audio', scope_value=scope)
    e.usage_base = f'/api/novels/{e.rig.nid}/experimental/production/assets/{e.asset["id"]}'
    graph_create(e, 4, 'resource-authority-cost-graph')
    before = snapshot(e.rig.root)
    records = four_page_observations(e.client, e.rig.root, e.rig.nid, e.asset['id'], headers, monkeypatch)
    for record in records:
        authority = [row for row in record['rows'] if row['category'] == 'authority_json']
        assert authority and sum(row['read_bytes'] for row in authority) > 0
        assert all(row['physical_input_via_usage_budget'] == record['declared_authority_reads_in_budget'] for row in authority)
        assert_guarded_cost_contract(record, record['declared_authority_reads_in_budget'])
        assert record['write_calls'] == record['created_directories'] == 0
    assert snapshot(e.rig.root) == before
    destination = destination_for(e, 'resource-costs-real-authority.json')
    destination.write_text(json.dumps({'scenario': 'real File scope/user/membership/permission owners; real in-memory packaged Host bootstrap;4 saved Graph pins',
        'records': records}, indent=2), encoding='utf-8')
    print('RESOURCE_AUTHORITY_COSTS_JSON ' + str(destination))
