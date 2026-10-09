"""V2 cloud contract fixtures only. Windows host/device and inference are NOT_RUN."""
from __future__ import annotations

import json
import struct
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.model_center.discovery_api import create_local_discovery_router
from app.model_center.discovery_environment import (
    MAX_METADATA_BYTES, common_model_roots, diffusion_metadata, environment_roots,
    safetensors_metadata, scan_environment_files, windows_acceleration_components,
)
from app.model_center.discovery_types import AIEnvironmentReport, DiscoverySettingsInput, LocalRuntimeInput
from test_local_ai_discovery import FixtureClient, approve_license, gguf, ollama, scan, service


@pytest.fixture(autouse=True)
def v2(monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    # Cloud tests do not enumerate the developer's actual home or local services.
    monkeypatch.setattr('app.model_center.discovery_environment.common_model_roots', lambda: [])


def safetensors(path: Path, header=None, data=b'abcd'):
    header = header or {'tensor': {'dtype':'U8','shape':[4],'data_offsets':[0,4]}}
    raw = json.dumps(header).encode()
    path.write_bytes(struct.pack('<Q', len(raw)) + raw + data)


def files(roots, *, cancel=None, deadline=None):
    reports = environment_roots([str(p) for p in roots], False)
    errors = []
    found = list(scan_environment_files(reports, cancel or threading.Event(), deadline or time.monotonic() + 10, errors))
    return found, reports, errors


def api(svc):
    app = FastAPI()
    app.include_router(create_local_discovery_router(svc, mutation_authorization=lambda token: {'can_mutate':token == 'fixture'}))
    return TestClient(app)


def test_environment_get_is_session_protected_and_never_scans(tmp_path):
    svc = service(tmp_path); client = api(svc)
    svc.hardware_probe = Mock(side_effect=AssertionError('GET must not inspect host'))
    assert client.get('/api/model-center/local-ai/environment').status_code == 401
    result = client.get('/api/model-center/local-ai/environment', headers={'X-Session-Token':'fixture'})
    assert result.status_code == 200
    report = AIEnvironmentReport.model_validate(result.json())
    assert report.status == 'NOT_SCANNED' and report.execution_scope == 'BACKEND_HOST'
    assert report.windows_acceptance == report.inference_status == 'NOT_RUN'
    assert not report.services and not report.model_files
    svc.hardware_probe.assert_not_called(); assert not svc.client.calls


@pytest.mark.parametrize('v1,flags', [('1','narrative_production_v2'), ('','')])
def test_default_off_and_v1_acceptance_preserve_old_scan(tmp_path, monkeypatch, v1, flags):
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1); monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags)
    svc = service(tmp_path); client = api(svc)
    result = client.get('/api/model-center/local-ai/environment', headers={'X-Session-Token':'fixture'})
    assert result.status_code == 404
    job = scan(svc)
    assert 'model_files' not in job and 'roots' not in job
    assert not any(endpoint == 'http://127.0.0.1:1234' for endpoint, _, _ in svc.client.calls)


def test_v2_known_services_report_models_without_inference_or_automatic_enable(tmp_path):
    svc = service(tmp_path); ollama(svc.client)
    svc.client.payloads[('http://127.0.0.1:1234','/v1/models')] = {'data':[{'id':'qwen-local'}]}
    svc.client.payloads[('http://127.0.0.1:8188','/system_stats')] = {'system':{'comfyui_version':'fixture'}}
    svc.client.payloads[('http://127.0.0.1:8188','/object_info')] = {'CheckpointLoaderSimple':{'input':{'required':{'ckpt_name':[['sdxl.safetensors']]}}}}
    scan(svc); report = svc.environment_report()
    lm = next(row for row in report['services'] if row['name'] == 'LM Studio')
    assert lm['status'] == 'RUNNING' and lm['available_models'] == ['qwen-local']
    assert all(row['inference_verified'] is False for row in report['services'])
    assert report['inference_status'] == 'NOT_RUN' and not svc.registrations
    candidate = svc.validate(lm['candidate_ids'][0]); svc.register(candidate['id']); approve_license(svc, candidate['id'])
    with pytest.raises(ValueError, match='ENABLE_BLOCKED'): svc.enable(candidate['id'])
    assert not svc.registrations[candidate['id']]['enabled']
    assert all(body is None for _, _, body in svc.client.calls)
    svc.center.lifecycle.start.assert_not_called()


def test_hardware_failure_preserves_other_service_results(tmp_path):
    svc = service(tmp_path); ollama(svc.client)
    svc.hardware_probe = Mock(side_effect=OSError('private host failure'))
    job = scan(svc); report = svc.environment_report()
    assert job['status'] == 'PARTIAL' and job['candidates']
    assert report['hardware']['status'] == 'NOT_VERIFIED'
    assert any(row['code'] == 'LOCAL_AI_HARDWARE_UNAVAILABLE' for row in report['errors'])
    assert 'private host failure' not in json.dumps(report)


def test_one_unexpected_service_failure_does_not_abort_later_services(tmp_path):
    svc = service(tmp_path)
    svc.client.payloads[('http://127.0.0.1:11434','/api/tags')] = RuntimeError('private detail')
    svc.client.payloads[('http://127.0.0.1:1234','/v1/models')] = {'data':[{'id':'qwen-local'}]}
    assert any(c['model_name'] == 'qwen-local' for c in scan(svc)['candidates'])
    assert 'private detail' not in json.dumps(svc.environment_report())


def test_common_roots_are_fixed_scoped_windows_locations(tmp_path):
    roots = common_model_roots(home=tmp_path, environ={'HF_HOME':str(tmp_path/'hf'), 'OLLAMA_MODELS':'//server/models'}, system='Windows')
    assert str(tmp_path/'.lmstudio'/'models') in roots
    assert str(tmp_path/'hf'/'hub') in roots
    assert str(tmp_path) not in roots and not any(r.startswith('//') for r in roots)
    assert common_model_roots(home=tmp_path, environ={}, system='Linux') == []


def test_common_roots_opt_out_persists_and_omitted_setting_does_not_reset(tmp_path, monkeypatch):
    common = tmp_path/'common'; common.mkdir(); safetensors(common/'sdxl.safetensors')
    monkeypatch.setattr('app.model_center.discovery_environment.common_model_roots', lambda: [str(common)])
    svc = service(tmp_path)
    svc.configure_roots(DiscoverySettingsInput(include_common_model_dirs=False))
    assert not scan(svc)['model_files']
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[]))
    assert not svc.settings['include_common_model_dirs']
    from app.model_center.discovery import LocalDiscoveryService
    restored = LocalDiscoveryService(svc.center, svc.path, client=FixtureClient())
    assert restored.settings['include_common_model_dirs'] is False
    svc.configure_roots(DiscoverySettingsInput(include_common_model_dirs=True))
    assert scan(svc)['model_files'][0]['source'] == 'COMMON'


def test_files_include_gguf_safetensors_diffusion_but_never_execute_or_read_private_files(tmp_path, monkeypatch):
    root = tmp_path/'models'; root.mkdir(); gguf(root/'qwen.gguf'); safetensors(root/'sdxl.safetensors')
    bundle = root/'flux'; bundle.mkdir(); (bundle/'model_index.json').write_text(json.dumps({'_class_name':'FluxPipeline','custom':'ignore'}))
    (root/'private.txt').write_text('NEVER_READ_PRIVATE_CONTENT'); (root/'unsafe.pt').write_bytes(b'PICKLE_MUST_NOT_LOAD')
    monkeypatch.setattr('subprocess.run', Mock(side_effect=AssertionError('never execute')))
    found, reports, errors = files([root])
    assert {row['format'] for row in found} == {'GGUF','SAFETENSORS','DIFFUSERS'}
    assert all(row['header_valid'] for row in found)
    assert all(row['inference_verified'] is False and 'RUNTIME_BINDING_REQUIRED' in row['notes'] for row in found)
    assert not errors and reports[0]['status'] == 'SCANNED'
    assert 'NEVER_READ_PRIVATE_CONTENT' not in json.dumps(found)


def test_v2_scan_reuses_configured_gguf_identity_without_duplicate_binding(tmp_path):
    svc = service(tmp_path); path = tmp_path/'qwen.gguf'; gguf(path)
    svc.configure_runtime(LocalRuntimeInput(name='My llama', type='LLAMA_CPP', endpoint='http://127.0.0.1:9998', model_path=str(path)))
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(tmp_path)], include_common_model_dirs=False))
    job = scan(svc); matches = [c for c in job['candidates'] if c['local_path'] == str(path)]
    assert len(matches) == 1
    assert job['model_files'][0]['candidate_ids'] == [matches[0]['id']]
    assert matches[0]['runtime_config']['endpoint'] == 'http://127.0.0.1:9998'


def test_safetensors_header_is_strict_and_does_not_read_tensor_payload(tmp_path, monkeypatch):
    path = tmp_path/'model.safetensors'; safetensors(path)
    original = __import__('os').fdopen; reads = []
    class Tracked:
        def __init__(self, file): self.file = file
        def __enter__(self): return self
        def __exit__(self, *args): return self.file.__exit__(*args)
        def fileno(self): return self.file.fileno()
        def read(self, n): reads.append(n); return self.file.read(n)
    monkeypatch.setattr('app.model_center.discovery_environment.os.fdopen', lambda fd, mode: Tracked(original(fd, mode)))
    assert safetensors_metadata(path)['header_valid']
    assert reads == [8, len(json.dumps({'tensor': {'dtype':'U8','shape':[4],'data_offsets':[0,4]}}).encode())]


@pytest.mark.parametrize('header', [
    {'tensor':{'dtype':'U8','shape':[4],'data_offsets':[0,999]}},
    {'tensor':{'dtype':'U8','shape':[True],'data_offsets':[0,4]}},
    {'tensor':{'dtype':'PICKLE','shape':[4],'data_offsets':[0,4]}},
    {'tensor':{'dtype':'U8','shape':[4],'data_offsets':[True,4]}},
    {'__metadata__':{'x':'y'}},
])
def test_malformed_safetensors_never_promotes_header(tmp_path, header):
    path = tmp_path/'model.safetensors'; safetensors(path, header)
    assert not safetensors_metadata(path)['header_valid']


def test_oversized_metadata_and_diffusion_custom_imports_are_not_executed(tmp_path):
    path = tmp_path/'model.safetensors'; path.write_bytes(struct.pack('<Q', MAX_METADATA_BYTES + 1))
    assert not safetensors_metadata(path)['header_valid']
    index = tmp_path/'model_index.json'; index.write_text('{"_class_name":"os.system(unsafe)"}')
    assert not diffusion_metadata(index)['header_valid']
    index.write_text('x'*(MAX_METADATA_BYTES + 1))
    assert not diffusion_metadata(index)['header_valid']


def test_duplicate_json_keys_in_safetensors_rejected(tmp_path):
    path = tmp_path/'model.safetensors'; header = b'{"x":{},"x":{}}'
    path.write_bytes(struct.pack('<Q',len(header)) + header)
    assert not safetensors_metadata(path)['header_valid']


def test_symlink_roots_and_entries_skipped_and_nested_roots_deduplicated(tmp_path):
    root = tmp_path/'models'; root.mkdir(); child = root/'sub'; child.mkdir(); safetensors(child/'model.safetensors')
    private = tmp_path/'private'; private.mkdir(); safetensors(private/'secret.safetensors')
    (root/'linked').symlink_to(private, target_is_directory=True)
    found, _, _ = files([root, child])
    assert len(found) == 1 and found[0]['name'] == 'model.safetensors'
    found, reports, errors = files([root/'linked'])
    assert not found and reports[0]['status'] == 'REJECTED' and errors


def test_depth_and_file_budgets_report_partial_explicitly(tmp_path, monkeypatch):
    root = tmp_path/'models'; root.mkdir(); safetensors(root/'one.safetensors'); safetensors(root/'two.safetensors')
    monkeypatch.setattr('app.model_center.discovery_environment.MAX_FILES', 1)
    found, roots, errors = files([root])
    assert len(found) == 1 and roots[0]['status'] == 'BOUNDED'
    assert errors[-1]['code'] == 'LOCAL_AI_FILESYSTEM_BUDGET_REACHED'


def test_cancel_and_deadline_terminate_with_honest_root_status(tmp_path):
    event = threading.Event(); event.set()
    found, roots, _ = files([tmp_path], cancel=event)
    assert not found and roots[0]['status'] == 'CANCELLED'
    found, roots, errors = files([tmp_path], deadline=time.monotonic() - 1)
    assert not found and roots[0]['status'] == 'BOUNDED' and errors


def test_nonwindows_acceleration_probe_has_no_positive_claim(monkeypatch):
    monkeypatch.setattr('app.model_center.discovery_environment.platform.system', lambda:'Linux')
    assert all(row['status'] == 'NOT_RUN' and row['inference_verified'] is False for row in windows_acceleration_components().values())


def test_malformed_dtype_retains_other_model_files(tmp_path):
    root = tmp_path/'models'; root.mkdir()
    safetensors(root/'bad.safetensors', {'x':{'dtype':[], 'shape':[4], 'data_offsets':[0,4]}})
    safetensors(root/'good.safetensors')
    found, _, _ = files([root])
    assert len(found) == 2
    assert not next(row for row in found if row['name'] == 'bad.safetensors')['header_valid']
    assert next(row for row in found if row['name'] == 'good.safetensors')['header_valid']


def test_scan_cancel_preserves_partial_service_results_and_never_probes_later_services(tmp_path):
    svc = service(tmp_path); ollama(svc.client)
    def cancel_after_tags(_):
        svc.cancel_event.set()
        return {'models':[{'name':'qwen-fixture'}]}
    svc.client.payloads[('http://127.0.0.1:11434', '/api/tags')] = cancel_after_tags
    result = scan(svc)
    assert result['status'] == 'CANCELLED' and result['candidates']
    assert all(endpoint == 'http://127.0.0.1:11434' for endpoint, _, _ in svc.client.calls)
    assert svc.environment_report()['status'] == 'CANCELLED'


def test_scan_has_no_implicit_process_launch_and_partial_status_keeps_valid_file(tmp_path, monkeypatch):
    root = tmp_path/'models'; root.mkdir(); safetensors(root/'one.safetensors'); safetensors(root/'two.safetensors')
    monkeypatch.setattr('app.model_center.discovery_environment.MAX_FILES', 1)
    svc = service(tmp_path); svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(root)], include_common_model_dirs=False))
    job = scan(svc)
    assert job['status'] == 'PARTIAL' and len(job['model_files']) == 1
    assert any(item['code'] == 'LOCAL_AI_FILESYSTEM_BUDGET_REACHED' for item in job['errors'])
    assert not svc.registrations; svc.center.lifecycle.start.assert_not_called()


def test_system_component_presence_is_not_a_driver_or_inference_claim(tmp_path, monkeypatch):
    import ctypes
    (tmp_path/'nvcuda.dll').write_bytes(b'NOT_A_REAL_DLL')
    class Query:
        def __call__(self, target, length): target.value = str(tmp_path); return len(str(tmp_path))
    class Kernel: GetSystemDirectoryW = Query()
    dll = Mock(return_value=Kernel())
    monkeypatch.setattr(ctypes, 'WinDLL', dll, raising=False)
    monkeypatch.setattr('app.model_center.discovery_environment.platform.system', lambda:'Windows')
    result = windows_acceleration_components()
    assert result['cuda']['status'] == 'COMPONENT_FOUND_NOT_VERIFIED'
    assert result['directml']['status'] == 'NOT_FOUND'
    assert all(not item['inference_verified'] for item in result.values())
    dll.assert_called_once_with('kernel32', use_last_error=True)


def test_directory_permission_error_does_not_hide_other_roots(tmp_path, monkeypatch):
    import os
    blocked = tmp_path/'blocked'; blocked.mkdir(); good = tmp_path/'good'; good.mkdir(); safetensors(good/'model.safetensors')
    original = os.scandir
    def scoped(path):
        if Path(path) == blocked: raise PermissionError('private denial')
        return original(path)
    monkeypatch.setattr('app.model_center.discovery_environment.os.scandir', scoped)
    found, roots, errors = files([blocked, good])
    assert len(found) == 1 and roots[0]['status'] == 'UNREADABLE' and roots[1]['status'] == 'SCANNED'
    assert errors[0]['code'] == 'LOCAL_AI_ROOT_UNREADABLE'
    assert 'private denial' not in json.dumps(errors)


def test_new_scan_does_not_relabel_previous_hardware_as_current(tmp_path):
    svc = service(tmp_path); scan(svc)
    entered, release = threading.Event(), threading.Event()
    def wait_hardware():
        entered.set(); release.wait(2)
        return {'status':'NOT_VERIFIED','gpus':[]}
    svc.hardware_probe = wait_hardware
    job = svc.start_scan(); assert entered.wait(1)
    assert svc.environment_report()['hardware']['status'] == 'NOT_VERIFIED'
    assert svc.environment_report()['hardware']['notes'] == ['SCAN_PENDING']
    svc.cancel_scan(job['id']); release.set()
    deadline = time.monotonic() + 3
    while svc.get_scan(job['id'])['status'] == 'RUNNING' and time.monotonic() < deadline: time.sleep(.005)
    assert svc.get_scan(job['id'])['status'] == 'CANCELLED'
