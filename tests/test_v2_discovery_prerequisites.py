"""Same-scan prerequisite advertisements only; no real model or inference evidence."""
from __future__ import annotations

import copy
import io
import json
import threading
import time
from dataclasses import replace
from unittest.mock import Mock

import pytest

from app.model_center.discovery_probes import LocalProbeClient, ProbeFailure
from app.model_center.discovery_types import AIEnvironmentReport, DiscoverySettingsInput
from test_local_ai_discovery import service, scan


@pytest.fixture(autouse=True)
def v2(monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    monkeypatch.setattr('app.model_center.discovery_environment.common_model_roots', lambda: [])


ENDPOINT = 'http://127.0.0.1:8188'


def object_info(svc, names=None):
    adapter = svc.workflow_adapters[0]
    result = {node: {} for node in adapter['required_nodes']}
    result[adapter['model_loader']] = {'input': {'required': {
        adapter['model_input']: [names if names is not None else ['sdxl.safetensors']]}}}
    return result


def configure_comfy(svc, info):
    svc.client.payloads[(ENDPOINT, '/system_stats')] = {'system': {'comfyui_version': 'synthetic'}}
    svc.client.payloads[(ENDPOINT, '/object_info')] = info


def workflow(job):
    report = job['workflow_prerequisites']
    assert report['schema_version'] == 1 and report['scan_id'] == job['id']
    assert report['scan_status'] == job['status']
    assert len(report['workflows']) == 1
    return report['workflows'][0]


def test_same_scan_complete_nodes_and_loader_are_advertisements_not_readiness(tmp_path):
    svc = service(tmp_path); configure_comfy(svc, object_info(svc))
    original_models = copy.deepcopy(svc.center.models)
    original_policy = copy.deepcopy(svc.center.routing_policy)
    job = scan(svc); row = workflow(job)
    assert job['status'] == 'PARTIAL'  # Other runtime probes unavailable.
    assert row['runtime_id'] == next(r['id'] for r in job['runtimes'] if r['type'] == 'COMFYUI')
    assert row['adapter_id'] == svc.workflow_adapters[0]['id']
    assert row['evidence_status'] == 'COMPLETE'
    assert all(n['observation'] == 'observed' for n in row['nodes'])
    assert row['loader']['observation'] == 'observed' and row['loader']['advertised_count'] == 1
    assert row['loader']['candidate_ids'] == [c['id'] for c in job['candidates'] if c['runtime_type'] == 'COMFYUI']
    assert row['metadata_status'] == 'NOT_VERIFIED' and row['inference_status'] == 'NOT_RUN'
    assert svc.center.models == original_models and svc.center.routing_policy == original_policy
    assert not svc.registrations and all(not c['enabled'] and not c['verified'] for c in job['candidates'])
    svc.center.lifecycle.start.assert_not_called()
    assert svc.client.calls.count((ENDPOINT, '/object_info', None)) == 1
    assert all(body is None for _, _, body in svc.client.calls)


@pytest.mark.parametrize('empty', ['index', 'options', 'missing_node'])
def test_valid_complete_absence_is_scoped_not_observed(tmp_path, empty):
    svc = service(tmp_path); info = object_info(svc, [])
    if empty == 'index': info = {}
    if empty == 'missing_node': del info['SaveImage']
    configure_comfy(svc, info); row = workflow(scan(svc))
    assert row['evidence_status'] == 'COMPLETE'
    if empty == 'index': assert all(n['observation'] == 'not_observed' for n in row['nodes'])
    if empty == 'missing_node': assert next(n for n in row['nodes'] if n['node_class'] == 'SaveImage')['observation'] == 'not_observed'
    assert row['loader']['observation'] == 'not_observed'
    assert row['loader']['advertised_count'] == 0 and not row['loader']['candidate_ids']


@pytest.mark.parametrize('bad', [None, [], 'private malformed payload',
    {'CheckpointLoaderSimple': None}, {'CheckpointLoaderSimple': {'input': []}},
    {'CheckpointLoaderSimple': {'input': {'required': []}}},
    {'CheckpointLoaderSimple': {}},
    {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': 'STRING'}}}},
    {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': ['STRING']}}}},
    {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [[False]]}}}},
    {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [['ok', None]]}}}},
    {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [['x' * 257]]}}}},
    {'Bad': {'input': []}}, {'': {}}, {'x' * 257: {}}])
def test_malformed_or_incomplete_evidence_never_reports_absence(tmp_path, bad):
    svc = service(tmp_path); configure_comfy(svc, bad)
    row = workflow(scan(svc))
    assert row['evidence_status'] == 'MALFORMED'
    assert all(n['observation'] == 'unknown' for n in row['nodes'])
    assert row['loader']['observation'] == 'unknown' and row['loader']['advertised_count'] is None
    assert not row['loader']['candidate_ids']
    assert 'private malformed payload' not in json.dumps(row)


@pytest.mark.parametrize('kind', ['nodes', 'options', 'fields', 'groups'])
def test_bounded_object_info_does_not_claim_negative_evidence(tmp_path, kind):
    svc = service(tmp_path); info = object_info(svc)
    if kind == 'nodes': info.update({f'FixtureNode{i}': {} for i in range(4097)})
    if kind == 'options': info['CheckpointLoaderSimple']['input']['required']['ckpt_name'] = [[f'sd{i}' for i in range(513)]]
    if kind == 'fields': info['Other'] = {'input': {'required': {f'field{i}': ['STRING'] for i in range(129)}}}
    if kind == 'groups': info['Other'] = {'input': {f'group{i}': {} for i in range(4)}}
    configure_comfy(svc, info); row = workflow(scan(svc))
    assert row['evidence_status'] == 'BOUNDED'
    assert all(n['observation'] == 'unknown' for n in row['nodes'])
    assert row['loader']['observation'] == 'unknown' and row['loader']['advertised_count'] is None


def test_unavailable_evidence_differs_from_valid_empty_index(tmp_path):
    svc = service(tmp_path); row = workflow(scan(svc))
    assert row['evidence_status'] == 'UNAVAILABLE'
    assert all(n['observation'] == 'unknown' for n in row['nodes'])
    assert row['loader']['advertised_count'] is None


def test_exact_loader_binding_excludes_other_nodes_fields_and_old_scans(tmp_path):
    svc = service(tmp_path); configure_comfy(svc, object_info(svc, ['sd-old']))
    first = scan(svc); old_id = workflow(first)['loader']['candidate_ids'][0]
    info = object_info(svc, ['sd-new'])
    info['AnotherLoader'] = {'input': {'required': {'ckpt_name': [['other']]}}}
    info['CheckpointLoaderSimple']['input']['required']['model_name'] = [['wrong-field']]
    configure_comfy(svc, info); second = scan(svc); row = workflow(second)
    candidates = {c['model_name']: c['id'] for c in second['candidates']}
    assert row['loader']['candidate_ids'] == [candidates['sd-new']]
    assert old_id not in row['loader']['candidate_ids'] and second['id'] != first['id']


def test_catalog_components_never_infer_installed_status_from_names_or_indexes(tmp_path):
    svc = service(tmp_path)
    missing = svc.center.models['flux2-dev']
    svc.center.models[missing.id] = replace(missing, components=(*missing.components, 'unknown-component'))
    names = list(svc.center.components)
    configure_comfy(svc, object_info(svc, names))
    root = tmp_path / 'indexes'; root.mkdir()
    (root / 'model_index.json').write_text(json.dumps({'_class_name': 'FluxPipeline',
        **{name: ['library', 'Component'] for name in names}}))
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(root)], include_common_model_dirs=False))
    job = scan(svc); components = job['workflow_prerequisites']['components']
    expected = {(m.id, c) for m in svc.center.models.values() for c in m.components}
    assert {(r['model_id'], r['component_id']) for r in components} == expected
    assert all(r['observation'] == 'unknown' and r['metadata_status'] == 'NOT_VERIFIED' and r['inference_status'] == 'NOT_RUN' for r in components)
    unknown = next(r for r in components if r['component_id'] == 'unknown-component')
    assert unknown['reason'] == 'COMPONENT_DEFINITION_UNAVAILABLE' and unknown['component_type'] is None
    known = next(r for r in components if r['component_id'] in names)
    assert known['reason'] == 'NO_COMPONENT_IDENTITY_EVIDENCE'
    assert known['component_type'] == svc.center.components[known['component_id']].component_type
    assert known['model_display_name'] == svc.center.models[known['model_id']].display_name
    assert job['model_files'][0]['format'] == 'DIFFUSERS'


@pytest.mark.parametrize('change', ['adapter', 'component', 'requirement'])
def test_definition_drift_invalidates_existing_consent_without_starting_probe(tmp_path, change):
    svc = service(tmp_path)
    preview = svc.preview_scan_scope(False, 'host', lambda: None)
    if change == 'adapter': svc.workflow_adapters[0]['required_nodes'].append('AdditionalNode')
    if change == 'component':
        key = next(iter(svc.center.components)); svc.center.components[key] = replace(svc.center.components[key], architecture='CHANGED')
    if change == 'requirement':
        key = 'flux2-dev'; svc.center.models[key] = replace(svc.center.models[key], components=('new-requirement',))
    with pytest.raises(ValueError, match='LOCAL_AI_SCOPE_STALE'):
        svc.start_consented_scan(preview['scope_digest'], 'host', lambda: None)
    assert not svc.client.calls and svc.scan is None


def test_running_cancelled_and_unstarted_workflows_stay_unknown(tmp_path):
    svc = service(tmp_path); entered, release = threading.Event(), threading.Event()
    def hardware(): entered.set(); release.wait(2); return {'gpus': []}
    svc.hardware_probe = hardware
    job = svc.start_scan(); assert entered.wait(1)
    pending = workflow(svc.get_scan(job['id']))
    assert pending['evidence_status'] == 'NOT_SCANNED'
    svc.cancel_scan(job['id']); release.set()
    deadline = time.monotonic() + 3
    while svc.get_scan(job['id'])['status'] == 'RUNNING' and time.monotonic() < deadline: time.sleep(.005)
    row = workflow(svc.get_scan(job['id']))
    assert row['evidence_status'] == 'CANCELLED'
    assert all(n['observation'] == 'unknown' for n in row['nodes'])


def test_projection_never_recomputes_from_live_catalog_and_returns_copies(tmp_path, monkeypatch):
    svc = service(tmp_path); configure_comfy(svc, object_info(svc)); job = scan(svc)
    before = copy.deepcopy(job['workflow_prerequisites'])
    svc.center.components.clear(); svc.workflow_adapters.clear()
    guard = Mock(side_effect=AssertionError('cached observation only'))
    monkeypatch.setattr(svc.client, 'json', guard)
    for projected in (svc.snapshot()['scan'], svc.get_scan(job['id']), svc.environment_report()):
        assert projected['workflow_prerequisites'] == before
        projected['workflow_prerequisites']['workflows'][0]['loader']['candidate_ids'].clear()
    assert svc.get_scan(job['id'])['workflow_prerequisites'] == before
    guard.assert_not_called()


@pytest.mark.parametrize('acceptance', [True, False])
def test_default_off_acceptance_and_older_scans_do_not_gain_prerequisites(tmp_path, monkeypatch, acceptance):
    if acceptance: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    svc = service(tmp_path); configure_comfy(svc, object_info(svc)); job = scan(svc)
    assert 'workflow_prerequisites' not in job
    assert svc.environment_report().get('workflow_prerequisites') is None
    assert AIEnvironmentReport().model_dump().get('workflow_prerequisites') is None


@pytest.mark.parametrize('path', ['/object_info', '/api/tags', '/v1/models'])
def test_duplicate_json_keys_are_rejected_by_original_probe_client(path):
    class Response(io.BytesIO):
        status = 200
    client = LocalProbeClient(); client.open = lambda *args, **kwargs: Response(b'{"node":{},"node":null}')
    with pytest.raises(ProbeFailure): client.json('http://127.0.0.1:8188', path)


@pytest.mark.parametrize('bad', [None, object(), {'id': 'invalid'}, 'invalid'])
def test_malformed_catalog_model_does_not_abort_original_scan(tmp_path, bad):
    svc = service(tmp_path); svc.center.models['malformed-fixture'] = bad
    configure_comfy(svc, object_info(svc))
    job = scan(svc)
    assert job['workflow_prerequisites']['definition_status'] == 'MALFORMED'
    assert workflow(job)['evidence_status'] == 'COMPLETE'


@pytest.mark.parametrize('bad', [True, 'component-id', {'component-id': True}])
def test_malformed_component_collection_stays_unknown(tmp_path, bad):
    svc = service(tmp_path); model = svc.center.models['flux2-dev']
    svc.center.models[model.id] = replace(model, components=bad)
    job = scan(svc)
    assert job['workflow_prerequisites']['definition_status'] == 'MALFORMED'
    assert all(r['model_id'] != model.id for r in job['workflow_prerequisites']['components'])


def test_duplicate_component_requirements_are_reported_once_with_malformed_status(tmp_path):
    svc = service(tmp_path); model = svc.center.models['flux2-dev']
    svc.center.models[model.id] = replace(model, components=model.components * 2)
    report = scan(svc)['workflow_prerequisites']
    assert report['definition_status'] == 'MALFORMED'
    keys = [(r['model_id'], r['component_id']) for r in report['components']]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize('dimension', ['models', 'requirements', 'adapters', 'required_nodes'])
def test_definition_limits_are_disclosed_without_unbounded_materialization(tmp_path, dimension):
    svc = service(tmp_path); model = svc.center.models['flux2-dev']
    if dimension == 'models':
        svc.center.models = {f'model{i}': replace(model, id=f'model{i}') for i in range(257)}
    if dimension == 'requirements':
        svc.center.models = {model.id: replace(model, components=tuple(f'component{i}' for i in range(513)))}
    if dimension == 'adapters':
        svc.workflow_adapters = [{**svc.workflow_adapters[0], 'id': f'workflow{i}'} for i in range(17)]
    if dimension == 'required_nodes':
        svc.workflow_adapters[0]['required_nodes'] += [f'Node{i}' for i in range(65)]
    report = scan(svc)['workflow_prerequisites']
    assert report['definition_status'] == 'BOUNDED'
    assert len(report['components']) <= 512 and len(report['workflows']) <= 320
    assert all(len(row['nodes']) <= 64 for row in report['workflows'])


@pytest.mark.parametrize('bad', [None, object(), {'component_type': 'CHECKPOINT'}])
def test_malformed_component_definition_does_not_become_installed_or_abort(tmp_path, bad):
    svc = service(tmp_path); svc.center.components['flux2-dev-mistral-encoder'] = bad
    report = scan(svc)['workflow_prerequisites']
    row = next(r for r in report['components'] if r['component_id'] == 'flux2-dev-mistral-encoder')
    assert row['observation'] == 'unknown' and row['reason'] == 'COMPONENT_DEFINITION_UNAVAILABLE'
    assert row['component_type'] is None


def test_invalid_system_stats_cannot_certify_complete_workflow_evidence(tmp_path):
    svc = service(tmp_path); configure_comfy(svc, object_info(svc))
    svc.client.payloads[(ENDPOINT, '/system_stats')] = []
    row = workflow(scan(svc))
    assert row['evidence_status'] == 'MALFORMED'
    assert all(n['observation'] == 'unknown' for n in row['nodes'])


@pytest.mark.parametrize('payload', [b'{', b'{"x":NaN}', b'{"a":{},"a":{}}', b'\xff'])
def test_invalid_json_transport_is_explicit_malformed_evidence(payload):
    class Response(io.BytesIO):
        status = 200
    client = LocalProbeClient(); client.open = lambda *args, **kwargs: Response(payload)
    with pytest.raises(ProbeFailure, match='LOCAL_AI_INVALID_RESPONSE'):
        client.json(ENDPOINT, '/object_info')


def test_deadline_after_object_info_returns_does_not_certify_absence(tmp_path, monkeypatch):
    import app.model_center.discovery as discovery
    svc = service(tmp_path); now = [0.0]
    monkeypatch.setattr(discovery.time, 'monotonic', lambda: now[0])
    svc.client.payloads[(ENDPOINT, '/system_stats')] = {}
    def late(_body): now[0] = 46.0; return {}
    svc.client.payloads[(ENDPOINT, '/object_info')] = late
    job = {'id': 'direct-fixture', 'status': 'RUNNING', 'errors': [], 'runtimes': [], 'candidates': [],
           'environment_schema_version': 2, 'roots': [], 'model_files': []}
    from app.model_center.discovery_prerequisites import prerequisite_template
    runtimes = [r for r in svc._runtimes() if r['type'] == 'COMFYUI']
    job['workflow_prerequisites'] = {'schema_version': 1, 'scan_id': job['id'], 'scan_status': 'RUNNING',
        **prerequisite_template(runtimes, svc.workflow_adapters, [], 'COMPLETE')}
    svc._scan(job, runtimes, [], threading.Event())
    assert job['status'] == 'PARTIAL' and workflow(job)['evidence_status'] == 'BOUNDED'
    assert all(n['observation'] == 'unknown' for n in workflow(job)['nodes'])


def test_catalog_registry_key_mismatch_cannot_duplicate_requirement_identity(tmp_path):
    svc = service(tmp_path); svc.center.models['alias'] = svc.center.models['flux2-dev']
    report = scan(svc)['workflow_prerequisites']
    assert report['definition_status'] == 'MALFORMED'
    keys = [(r['model_id'], r['component_id']) for r in report['components']]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize('field', ['family', 'capability'])
def test_adapter_declaration_dimensions_also_bind_existing_scope_digest(tmp_path, field):
    svc = service(tmp_path); preview = svc.preview_scan_scope(False, 'host', lambda: None)
    svc.workflow_adapters[0][field] = 'DIFFERENT'
    with pytest.raises(ValueError, match='LOCAL_AI_SCOPE_STALE'):
        svc.start_consented_scan(preview['scope_digest'], 'host', lambda: None)
    assert svc.scan is None and not svc.client.calls


def test_ambiguous_runtime_ids_do_not_create_duplicate_or_cross_bound_rows(tmp_path):
    from app.model_center.discovery_prerequisites import prerequisite_template
    svc = service(tmp_path)
    duplicate = [{'id': 'ambiguous', 'type': 'COMFYUI'}, {'id': 'ambiguous', 'type': 'COMFYUI'}]
    report = prerequisite_template(duplicate, svc.workflow_adapters, [], 'COMPLETE')
    assert report['definition_status'] == 'MALFORMED'
    assert report['workflows'] == []


def test_admission_captures_original_definitions_and_never_reads_new_owner_values(tmp_path):
    svc = service(tmp_path); configure_comfy(svc, object_info(svc))
    entered, release = threading.Event(), threading.Event()
    def hardware(): entered.set(); release.wait(2); return {'gpus': []}
    svc.hardware_probe = hardware
    preview = svc.preview_scan_scope(False, 'host', lambda: None)
    job = svc.start_consented_scan(preview['scope_digest'], 'host', lambda: None)
    assert entered.wait(1)
    initial = copy.deepcopy(job['workflow_prerequisites'])
    svc.workflow_adapters[0]['required_nodes'].append('LaterRequirement')
    svc.center.components.clear()
    release.set()
    deadline = time.monotonic() + 3
    while svc.get_scan(job['id'])['status'] == 'RUNNING' and time.monotonic() < deadline: time.sleep(.005)
    result = svc.get_scan(job['id'])
    assert workflow(result)['evidence_status'] == 'COMPLETE'
    assert result['workflow_prerequisites']['components'] == initial['components']
    assert not any(n['node_class'] == 'LaterRequirement' for n in workflow(result)['nodes'])


def test_cancellation_after_valid_comfy_evidence_clears_all_positive_observations(tmp_path):
    svc = service(tmp_path); configure_comfy(svc, object_info(svc))
    def stop(_body): svc.cancel_event.set(); return []
    svc.client.payloads[('http://127.0.0.1:7860', '/sdapi/v1/sd-models')] = stop
    job = scan(svc); row = workflow(job)
    assert job['status'] == 'CANCELLED' and row['evidence_status'] == 'CANCELLED'
    assert all(n['observation'] == 'unknown' for n in row['nodes'])
    assert row['loader']['observation'] == 'unknown' and row['loader']['candidate_ids'] == []


@pytest.mark.parametrize('bad', [None, {}, [None], [{'id': 'invalid'}]])
def test_malformed_adapter_declarations_remain_unknown(tmp_path, bad):
    svc = service(tmp_path); svc.workflow_adapters = bad
    report = scan(svc)['workflow_prerequisites']
    assert report['definition_status'] == 'MALFORMED' and report['workflows'] == []


def test_catalog_iteration_stops_at_bound_without_copying_large_registry(tmp_path):
    from app.model_center.discovery_prerequisites import catalog_requirements, MAX_CATALOG_MODELS
    svc = service(tmp_path); model = svc.center.models['flux2-dev']
    class BoundedRegistry(dict):
        def items(self):
            for i in range(MAX_CATALOG_MODELS): yield f'm{i}', replace(model, id=f'm{i}')
            raise AssertionError('must not traverse beyond the catalogue bound')
        def values(self):
            raise AssertionError('must verify registry key/id and iterate bounded items')
        def __len__(self): return 1000000
    rows, _, status = catalog_requirements(BoundedRegistry(), svc.center.components)
    assert status == 'BOUNDED' and len(rows) == MAX_CATALOG_MODELS
