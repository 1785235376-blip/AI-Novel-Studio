"""M3-A bounded consent contracts. All probes and filesystem data are synthetic."""
from __future__ import annotations

import copy
import json
import os
import struct
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.model_center.discovery import LocalDiscoveryService
from app.model_center.discovery_scope import PREVIEW_LIMIT, PREVIEW_TTL_SECONDS
from app.model_center.discovery_types import DiscoverySettingsInput, LocalRuntimeInput
from test_local_ai_discovery import FixtureClient, gguf, ollama, service


@pytest.fixture(autouse=True)
def synthetic_environment(monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    monkeypatch.setattr('app.model_center.discovery_environment.common_model_roots', lambda: [])


def preview(svc, common=False, principal='host-user', guard=lambda: None):
    return svc.preview_scan_scope(common, principal, guard)


def start(svc, scope, principal='host-user', guard=lambda: None):
    return svc.start_consented_scan(scope['scope_digest'], principal, guard)


def finish(svc, job):
    end = time.monotonic() + 3
    while time.monotonic() < end:
        current = svc.get_scan(job['id'])
        if current['status'] != 'RUNNING': return current
        time.sleep(.005)
    raise AssertionError('synthetic scan did not finish')


def test_preview_is_metadata_only_and_declares_all_effects(tmp_path, monkeypatch):
    svc = service(tmp_path)
    root = tmp_path / 'models'; root.mkdir()
    model = root / 'qwen.gguf'; gguf(model)
    exe_dir = tmp_path / 'bin'; exe_dir.mkdir()
    executable = exe_dir / 'llama-server'; executable.write_bytes(b'NEVER_EXECUTE')
    svc.configure_runtime(LocalRuntimeInput(name='local', type='LLAMA_CPP', endpoint='http://127.0.0.1:9998',
        model_path=str(model), executable=str(executable), health_endpoint='/health'))
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(root)], include_common_model_dirs=True))
    before = svc.path.read_bytes()
    svc.hardware_probe = Mock(side_effect=AssertionError('preview hardware'))
    monkeypatch.setattr('os.scandir', Mock(side_effect=AssertionError('preview enumeration')))
    monkeypatch.setattr(Path, 'open', Mock(side_effect=AssertionError('preview contents')))
    monkeypatch.setattr('threading.Thread.start', Mock(side_effect=AssertionError('preview worker')))
    scope = preview(svc)
    assert scope['schema_version'] == 1 and scope['execution_scope'] == 'BACKEND_HOST'
    assert scope['include_common_model_dirs'] is False and scope['requires_confirmation']
    assert scope['roots'] == [{'path': str(root), 'source': 'CONFIGURED'}]
    paths = {(r['kind'], r['path']) for r in scope['metadata_inspections']}
    assert ('CONFIGURED_GGUF_HEADER', str(model)) in paths
    assert ('EXECUTABLE_DIRECTORY_SIBLINGS', str(exe_dir)) in paths
    assert ('EXECUTABLE_VERSION_RESOURCE', str(executable)) in paths
    assert ('RECURSIVE_MODEL_METADATA', str(root)) in paths
    assert next(r for r in scope['services'] if r['name'] == 'local')['probe_paths'] == ['/health']
    assert scope['side_effects'] == {'launches': False, 'loads_weights': False, 'registers': False,
        'enables': False, 'cloud_calls': False, 'persists_settings': False,
        'may_disable_stale_registrations': True, 'persists_registration_safety_updates': True}
    assert scope['inference_status'] == 'NOT_RUN' and not svc.client.calls
    assert svc.settings['include_common_model_dirs'] is True and svc.scan is None
    svc.hardware_probe.assert_not_called()
    monkeypatch.undo()
    assert svc.path.read_bytes() == before


def test_probe_paths_are_complete_and_credentials_never_probed(tmp_path):
    svc = service(tmp_path)
    svc.configure_runtime(LocalRuntimeInput(name='api-v1', type='OPENAI_COMPATIBLE_LOCAL', endpoint='http://127.0.0.1:9997/v1'))
    svc.configure_runtime(LocalRuntimeInput(name='health', type='CUSTOM_HTTP', endpoint='http://127.0.0.1:9996', health_endpoint='/status'))
    svc.configure_runtime(LocalRuntimeInput(name='secret', type='OLLAMA', endpoint='http://127.0.0.1:9995', credential_required=True))
    scope = preview(svc)
    assert next(row for row in scope['services'] if row['name'] == 'secret')['probe_paths'] == []
    finish(svc, start(svc, scope))
    declared = {(row['endpoint'], path) for row in scope['services'] for path in row['probe_paths']}
    assert all((endpoint, path) in declared and body is None for endpoint, path, body in svc.client.calls)
    assert not any(endpoint.endswith(':9995') for endpoint, _, _ in svc.client.calls)
    assert next(row for row in scope['services'] if row['type'] == 'OLLAMA')['probe_paths'] == ['/api/tags', '/api/version']
    assert not any('manifest' in row['kind'].lower() for row in scope['metadata_inspections'])


def test_explicit_common_override_freezes_roots_without_persisting(tmp_path, monkeypatch):
    common = tmp_path / 'common'; common.mkdir(); gguf(common / 'qwen.gguf')
    monkeypatch.setattr('app.model_center.discovery_environment.common_model_roots', lambda: [str(common)])
    svc = service(tmp_path)
    svc.configure_roots(DiscoverySettingsInput(include_common_model_dirs=False))
    before = svc.path.read_bytes()
    no = preview(svc)
    yes = preview(svc, True)
    assert no['roots'] == [] and yes['roots'] == [{'path': str(common), 'source': 'COMMON'}]
    assert finish(svc, start(svc, yes))['model_files'][0]['root'] == str(common)
    assert svc.path.read_bytes() == before and not svc.settings['include_common_model_dirs']


@pytest.mark.parametrize('change', ['roots', 'settings', 'runtime', 'center', 'sources', 'client', 'hardware'])
def test_all_effective_configuration_drift_is_rejected_before_probe(tmp_path, change):
    svc = service(tmp_path); scope = preview(svc)
    if change == 'roots': svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(tmp_path / 'new')]))
    if change == 'settings': svc.configure_roots(DiscoverySettingsInput(include_common_model_dirs=False))
    if change == 'runtime': svc.configure_runtime(LocalRuntimeInput(name='custom', type='CUSTOM_HTTP', endpoint='http://127.0.0.1:9091', health_endpoint='/health'))
    if change == 'center':
        identifier = next(iter(svc.center.runtimes))
        with svc.center._config_lock:
            svc.center.runtimes[identifier] = replace(svc.center.runtimes[identifier], base_url='http://127.0.0.1:9999')
    if change == 'sources': svc.configured_runtime_sources = [{'id': 'source', **LocalRuntimeInput(name='source', type='CUSTOM_HTTP', endpoint='http://127.0.0.1:9092', health_endpoint='/health').model_dump()}]
    if change == 'client': svc.client = FixtureClient()
    if change == 'hardware': svc.hardware_probe = Mock()
    with pytest.raises(ValueError, match='LOCAL_AI_SCOPE_STALE'): start(svc, scope)
    assert svc.scan is None and not svc.client.calls


@pytest.mark.parametrize('change', ['new', 'replace', 'link', 'metadata'])
def test_path_identity_changes_reject_before_probe(tmp_path, change):
    svc = service(tmp_path); root = tmp_path / 'models'
    if change != 'new': root.mkdir()
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(root)]))
    scope = preview(svc)
    if change == 'new': root.mkdir()
    if change == 'replace': root.rename(tmp_path / 'old'); root.mkdir()
    if change == 'link':
        other = tmp_path / 'other'; other.mkdir()
        root.rmdir(); root.symlink_to(other, target_is_directory=True)
    if change == 'metadata': gguf(root / 'qwen.gguf')
    with pytest.raises(ValueError, match='LOCAL_AI_SCOPE_STALE'): start(svc, scope)
    assert not svc.client.calls


def test_missing_expired_foreign_and_restart_digests_fail_closed(tmp_path, monkeypatch):
    svc = service(tmp_path); scope = preview(svc)
    with pytest.raises(ValueError, match='SCOPE_REQUIRED'): svc.start_consented_scan('', 'host-user', lambda: None)
    with pytest.raises(ValueError, match='SCOPE_INVALID'): svc.start_consented_scan('invented', 'host-user', lambda: None)
    with pytest.raises(ValueError, match='SCOPE_PRINCIPAL_MISMATCH'): start(svc, scope, principal='other')
    restored = LocalDiscoveryService(svc.center, svc.path, client=FixtureClient(), hardware_probe=Mock())
    with pytest.raises(ValueError, match='SCOPE_INVALID'): start(restored, scope)
    svc._scope_previews[scope['scope_digest']]['expires'] = time.monotonic() - 1
    with pytest.raises(ValueError, match='SCOPE_EXPIRED'): start(svc, scope)
    assert not svc.client.calls and not restored.client.calls


def test_previews_are_nonce_bound_bounded_and_fixed_ttl(tmp_path):
    svc = service(tmp_path)
    rows = [preview(svc) for _ in range(PREVIEW_LIMIT + 2)]
    assert len({row['scope_digest'] for row in rows}) == len(rows)
    assert len(svc._scope_previews) == PREVIEW_LIMIT
    assert rows[0]['scope_digest'] not in svc._scope_previews
    record = svc._scope_previews[rows[-1]['scope_digest']]
    assert 0 < record['expires'] - time.monotonic() <= PREVIEW_TTL_SECONDS
    expiry = record['expires']
    job = start(svc, rows[-1]); finish(svc, job)
    assert start(svc, rows[-1])['id'] == job['id'] and record['expires'] == expiry


def test_identical_confirmation_is_idempotent_even_after_fast_completion(tmp_path):
    svc = service(tmp_path); scope = preview(svc)
    first = finish(svc, start(svc, scope)); calls = list(svc.client.calls)
    assert start(svc, scope) == first and svc.client.calls == calls
    assert first['consent'] == {'scope_digest': scope['scope_digest'], 'confirmed_at': first['consent']['confirmed_at'], 'execution_scope': 'BACKEND_HOST'}
    assert 'principal' not in json.dumps(first) and 'host-user' not in json.dumps(first)
    next_scope = preview(svc); next_job = finish(svc, start(svc, next_scope))
    assert next_job['id'] != first['id']
    with pytest.raises(ValueError, match='SCOPE_CONSUMED'): start(svc, scope)


def test_running_other_preview_conflicts_and_same_confirmation_reuses_scan(tmp_path):
    svc = service(tmp_path); began, release = threading.Event(), threading.Event()
    def hardware(): began.set(); release.wait(2); return {'gpus': [], 'status': 'DETECTED'}
    svc.hardware_probe = hardware
    a = preview(svc); b = preview(svc)
    job = start(svc, a); assert began.wait(1)
    try:
        assert start(svc, a)['id'] == job['id']
        with pytest.raises(ValueError, match='SCOPE_CONFLICT'): start(svc, b)
    finally: release.set()
    finish(svc, job)


def test_execution_uses_frozen_runtime_and_roots_after_admission(tmp_path):
    svc = service(tmp_path); root = tmp_path / 'approved'; root.mkdir(); gguf(root / 'qwen.gguf')
    unapproved = tmp_path / 'unapproved'; unapproved.mkdir(); gguf(unapproved / 'private.gguf')
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(root)]))
    began, release = threading.Event(), threading.Event()
    def hardware(): began.set(); release.wait(2); return {'gpus': []}
    svc.hardware_probe = hardware
    scope = preview(svc); job = start(svc, scope); assert began.wait(1)
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(unapproved)]))
    svc.configure_runtime(LocalRuntimeInput(name='unapproved', type='CUSTOM_HTTP', endpoint='http://127.0.0.1:9999', health_endpoint='/extra'))
    release.set(); result = finish(svc, job)
    assert [row['root'] for row in result['model_files']] == [str(root)]
    assert not any(endpoint.endswith(':9999') for endpoint, _, _ in svc.client.calls)


@pytest.mark.parametrize('phase', ['before', 'after_plan', 'admission'])
def test_guard_rechecked_before_after_plan_and_admission(tmp_path, monkeypatch, phase):
    svc = service(tmp_path); scope = preview(svc)
    revoked = False
    def guard():
        if revoked: raise RuntimeError('private token must never be exposed')
    if phase == 'before': revoked = True
    if phase == 'after_plan':
        original = svc._scope_plan
        def plan(*args):
            nonlocal revoked
            value = original(*args); revoked = True; return value
        monkeypatch.setattr(svc, '_scope_plan', plan)
    if phase == 'admission':
        original = svc._issued_scope; calls = 0
        def issued(*args):
            nonlocal calls, revoked
            calls += 1
            result = original(*args)
            if calls == 2: revoked = True
            return result
        monkeypatch.setattr(svc, '_issued_scope', issued)
    with pytest.raises(ValueError, match='SCOPE_REVOKED'): start(svc, scope, guard=guard)
    assert svc.scan is None and not svc.client.calls


@pytest.mark.parametrize('cancelled', [False, True])
def test_late_hardware_revoke_or_cancel_discards_results_and_stops_access(tmp_path, cancelled):
    svc = service(tmp_path); began, release = threading.Event(), threading.Event(); revoked = False
    def hardware(): began.set(); release.wait(2); return {'private_hardware': True, 'gpus': []}
    def guard(): return not revoked
    svc.hardware_probe = hardware
    scope = preview(svc, guard=guard); job = start(svc, scope, guard=guard); assert began.wait(1)
    if cancelled: svc.cancel_scan(job['id'])
    else: revoked = True
    release.set(); result = finish(svc, job)
    assert result['status'] == 'CANCELLED' and not result['runtimes'] and not svc.client.calls
    assert 'private_hardware' not in svc.hardware
    if not cancelled: assert {'code': 'LOCAL_AI_SCOPE_REVOKED'} in result['errors']


def test_probe_revocation_discards_late_data_and_never_reconciles(tmp_path):
    svc = service(tmp_path); revoked = False
    def tags(_):
        nonlocal revoked
        revoked = True
        return {'models': [{'name': 'private-late-model'}]}
    svc.client.payloads[('http://127.0.0.1:11434', '/api/tags')] = tags
    svc._reconcile_detected_runtime = Mock()
    guard = lambda: not revoked
    result = finish(svc, start(svc, preview(svc, guard=guard), guard=guard))
    assert result['status'] == 'CANCELLED' and not result['candidates'] and not result['runtimes']
    assert len(svc.client.calls) == 1
    svc._reconcile_detected_runtime.assert_not_called()


def test_legacy_http_rejects_v2_but_argument_free_start_remains(tmp_path, monkeypatch):
    svc = service(tmp_path)
    with pytest.raises(ValueError, match='SCOPE_CONFIRMATION_REQUIRED'): svc.start_legacy_http_scan(lambda: None)
    assert finish(svc, svc.start_scan())['environment_schema_version'] == 2
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    job = finish(svc, svc.start_legacy_http_scan(lambda: None))
    assert 'environment_schema_version' not in job


def test_legacy_http_flag_flip_stops_before_late_hardware_adoption(tmp_path, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    svc = service(tmp_path); began, release = threading.Event(), threading.Event()
    def hardware(): began.set(); release.wait(2); return {'late_hardware': True}
    svc.hardware_probe = hardware
    job = svc.start_legacy_http_scan(lambda: None); assert began.wait(1)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    release.set(); result = finish(svc, job)
    assert result['status'] == 'CANCELLED' and not svc.client.calls and 'late_hardware' not in svc.hardware


def registered_llama(svc, path):
    runtime = next(row for row in svc._runtimes() if row['type'] == 'LLAMA_CPP')
    candidate = svc._candidate(runtime, path.name, local_path=str(path))
    candidate.update(enabled=True, validated_at='fixture')
    svc.registrations[candidate['id']] = candidate
    return candidate


def test_registered_file_outside_roots_is_explicitly_planned(tmp_path):
    svc = service(tmp_path); path = tmp_path / 'registered.gguf'; gguf(path)
    record = registered_llama(svc, path)
    scope = preview(svc)
    assert scope['roots'] == []
    assert {'kind': 'REGISTERED_GGUF_HEADER', 'path': str(path), 'max_entries': 1, 'max_bytes': 256 * 1024} in scope['metadata_inspections']
    result = finish(svc, start(svc, scope))
    assert result['status'] == 'PARTIAL' and not svc.registrations[record['id']]['enabled']
    assert svc.path.exists()  # Existing fail-closed registration safety persists.


def test_registration_path_changed_after_preview_is_stale(tmp_path):
    svc = service(tmp_path); a = tmp_path / 'a.gguf'; gguf(a)
    b = tmp_path / 'b.gguf'; gguf(b)
    record = registered_llama(svc, a); scope = preview(svc)
    svc.registrations[record['id']]['local_path'] = str(b)
    with pytest.raises(ValueError, match='SCOPE_STALE'): start(svc, scope)
    assert not svc.client.calls


def test_new_unplanned_registered_file_is_never_read_during_worker(tmp_path, monkeypatch):
    svc = service(tmp_path); path = tmp_path / 'unapproved.gguf'; gguf(path)
    began, release = threading.Event(), threading.Event()
    def hardware(): began.set(); release.wait(2); return {'gpus': []}
    svc.hardware_probe = hardware
    scope = preview(svc); job = start(svc, scope); assert began.wait(1)
    registered_llama(svc, path)
    read = Mock(side_effect=AssertionError('unapproved registration metadata'))
    monkeypatch.setattr('app.model_center.discovery.gguf_metadata', read)
    release.set(); result = finish(svc, job)
    assert result['status'] == 'CANCELLED' and {'code': 'LOCAL_AI_SCOPE_STALE'} in result['errors']
    read.assert_not_called()


def test_file_and_network_limits_are_actual_and_frozen_at_admission(tmp_path, monkeypatch):
    svc = service(tmp_path); root = tmp_path / 'models'; root.mkdir()
    gguf(root / 'one.gguf'); gguf(root / 'two.gguf')
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(root)]))
    svc.client.timeout = 1.25; svc.client.max_response_bytes = 1024
    monkeypatch.setattr('app.model_center.discovery_environment.MAX_FILES', 1)
    began, release = threading.Event(), threading.Event()
    def hardware(): began.set(); release.wait(2); return {'gpus': []}
    svc.hardware_probe = hardware
    scope = preview(svc)
    assert scope['limits']['max_files'] == 1
    assert scope['limits']['request_timeout_seconds'] == 1.25 and scope['limits']['max_response_bytes'] == 1024
    job = start(svc, scope); assert began.wait(1)
    monkeypatch.setattr('app.model_center.discovery_environment.MAX_FILES', 100)
    svc.client.timeout = 99; svc.client.max_response_bytes = 999999
    assert svc.cancel_event.client.timeout == 1.25 and svc.cancel_event.client.max_response_bytes == 1024
    release.set(); result = finish(svc, job)
    assert len(result['model_files']) == 1
    assert {'code': 'LOCAL_AI_FILESYSTEM_BUDGET_REACHED'} in result['errors']


def test_timeout_limit_change_requires_new_preview(tmp_path):
    svc = service(tmp_path); svc.client.timeout = 1
    scope = preview(svc); svc.client.timeout = 2
    with pytest.raises(ValueError, match='SCOPE_STALE'): start(svc, scope)
    svc.client.timeout = 3
    with pytest.raises(ValueError, match='SCOPE_INVALID'): preview(svc)


def test_preview_rejects_unsafe_filesystem_object_without_opening(tmp_path, monkeypatch):
    if not hasattr(os, 'mkfifo'): pytest.skip('POSIX FIFO fixture')
    svc = service(tmp_path); root = tmp_path / 'pipe'; os.mkfifo(root)
    svc.settings['scan_roots'] = [str(root)]
    with pytest.raises(ValueError, match='SCOPE_INVALID'): preview(svc)
    assert not svc.client.calls


@pytest.mark.parametrize('ancestor', [False, True])
def test_nofollow_metadata_read_rejects_link_swap_after_path_check(tmp_path, monkeypatch, ancestor):
    from app.model_center import discovery_environment as environment
    from app.model_center.discovery_probes import gguf_metadata
    model_dir = tmp_path / 'models'; model_dir.mkdir(); path = model_dir / 'qwen.gguf'; gguf(path)
    other = tmp_path / 'private'; other.mkdir(); gguf(other / 'qwen.gguf')
    original = environment.safe_local_path; swapped = False
    def check(value):
        nonlocal swapped
        checked = original(value)
        if value == str(path) and not swapped:
            swapped = True
            if ancestor:
                model_dir.rename(tmp_path / 'original-models'); model_dir.symlink_to(other, target_is_directory=True)
            else:
                path.unlink(); path.symlink_to(other / 'qwen.gguf')
        return checked
    monkeypatch.setattr(environment, 'safe_local_path', check)
    result = gguf_metadata(path)
    assert swapped and not result['file_exists'] and not result['header_valid']


def test_cancel_between_safetensors_prefix_and_header_stops_second_read(tmp_path, monkeypatch):
    from app.model_center.discovery_environment import safetensors_metadata
    path = tmp_path / 'model.safetensors'; body = b'{"x":{}}'; path.write_bytes(struct.pack('<Q', len(body)) + body)
    cancel = threading.Event(); reads = []; original = os.fdopen
    class File:
        def __init__(self, wrapped): self.wrapped = wrapped
        def __enter__(self): return self
        def __exit__(self, *args): return self.wrapped.__exit__(*args)
        def fileno(self): return self.wrapped.fileno()
        def read(self, count):
            reads.append(count); value = self.wrapped.read(count); cancel.set(); return value
    monkeypatch.setattr(os, 'fdopen', lambda *args: File(original(*args)))
    assert not safetensors_metadata(path, cancel=cancel)['header_valid']
    assert reads == [8]


def test_executable_sibling_inspection_stays_bounded_and_cancelable(tmp_path, monkeypatch):
    from app.model_center import discovery_environment as environment
    from app.model_center.discovery_probes import executable_metadata
    executable = tmp_path / 'server'; executable.write_bytes(b'NEVER_EXECUTE')
    reads = 0; cancel = threading.Event()
    class Entries:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def __iter__(self): return self
        def __next__(self):
            nonlocal reads
            reads += 1
            return type('Entry', (), {'name': 'unrelated'})()
    monkeypatch.setattr(environment, '_scoped_scandir', lambda *_: Entries())
    assert executable_metadata(str(executable))['executable_exists'] and reads == 256
    reads = 0; cancel.set()
    executable_metadata(str(executable), cancel=cancel)
    assert reads == 0


def test_passive_hardware_never_calls_platform_processor(tmp_path, monkeypatch):
    from app.model_center.discovery_probes import host_hardware
    monkeypatch.setattr('platform.system', lambda: 'Linux')
    monkeypatch.setattr('platform.machine', lambda: 'Synthetic')
    monkeypatch.setattr('platform.processor', Mock(side_effect=AssertionError('may launch uname')))
    monkeypatch.setattr('os.sysconf', lambda _: 1)
    monkeypatch.setattr('os.cpu_count', lambda: 4)
    assert host_hardware()['cpu'] == 'Synthetic'


def test_mutation_late_guard_blocks_atomic_replace_and_keeps_saved_memory(tmp_path, monkeypatch):
    svc = service(tmp_path); svc.configure_roots(DiscoverySettingsInput(include_common_model_dirs=False))
    before = svc.path.read_bytes(); settings = copy.deepcopy(svc.settings); revoked = False
    original = os.fsync
    def revoke(descriptor):
        nonlocal revoked
        original(descriptor); revoked = True
    monkeypatch.setattr(os, 'fsync', revoke)
    with pytest.raises(ValueError, match='SCOPE_REVOKED'):
        svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(tmp_path / 'new')]), guard=lambda: not revoked)
    assert svc.path.read_bytes() == before and svc.settings == settings
    assert not list(tmp_path.glob('.discovery-*.tmp'))


@pytest.mark.parametrize('method,args', [
    ('configure_roots', (DiscoverySettingsInput(),)),
    ('configure_runtime', (LocalRuntimeInput(name='x', type='CUSTOM_HTTP', endpoint='http://127.0.0.1:9090', health_endpoint='/health'),)),
    ('validate', ('missing',)), ('register', ('missing',)),
    ('configure_registration', ('missing', None)), ('enable', ('missing',)),
    ('disable', ('missing',)), ('remove', ('missing',)),
])
def test_all_mutations_guard_before_state_or_probe(tmp_path, method, args):
    svc = service(tmp_path)
    with pytest.raises(ValueError, match='SCOPE_REVOKED'): getattr(svc, method)(*args, guard=lambda: False)
    assert not svc.client.calls and not svc.path.exists()


def test_validate_revoke_during_probe_never_adopts_or_persists_result(tmp_path):
    svc = service(tmp_path); ollama(svc.client)
    result = finish(svc, start(svc, preview(svc))); identifier = result['candidates'][0]['id']
    before = copy.deepcopy(svc.scan); revoked = False
    def tags(_):
        nonlocal revoked
        revoked = True
        return {'models': [{'name': 'qwen3.6:8b'}]}
    svc.client.payloads[('http://127.0.0.1:11434', '/api/tags')] = tags
    svc.client.calls.clear()
    with pytest.raises(ValueError, match='SCOPE_REVOKED'): svc.validate(identifier, guard=lambda: not revoked)
    assert svc.scan == before and not svc.registrations and not svc.path.exists()
    assert len(svc.client.calls) == 1


def test_validate_revoke_during_ollama_show_stops_after_current_request(tmp_path):
    svc = service(tmp_path); ollama(svc.client)
    result = finish(svc, start(svc, preview(svc))); identifier = result['candidates'][0]['id']
    before = copy.deepcopy(svc.scan); revoked = False
    def show(_):
        nonlocal revoked
        revoked = True
        return {'capabilities': ['completion']}
    svc.client.payloads[('http://127.0.0.1:11434', '/api/show')] = show
    svc.client.calls.clear()
    with pytest.raises(ValueError, match='SCOPE_REVOKED'): svc.validate(identifier, guard=lambda: not revoked)
    assert svc.scan == before and svc.client.calls[-1][1] == '/api/show'


def test_preview_holds_no_model_center_lock_during_discovery_planning(tmp_path, monkeypatch):
    svc = service(tmp_path)
    original = svc._runtimes
    def runtimes(**kwargs):
        assert not svc.center._config_lock._is_owned()
        return original(**kwargs)
    monkeypatch.setattr(svc, '_runtimes', runtimes)
    assert preview(svc)['services']


def test_simultaneous_confirmations_admit_only_one_worker(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    svc = service(tmp_path); count = 0
    def hardware():
        nonlocal count
        count += 1
        return {'gpus': []}
    svc.hardware_probe = hardware
    scope = preview(svc)
    with ThreadPoolExecutor(max_workers=8) as executor:
        jobs = list(executor.map(lambda _: start(svc, scope), range(16)))
    assert len({job['id'] for job in jobs}) == 1
    finish(svc, jobs[0]); assert count == 1


def test_issuing_other_previews_does_not_evict_current_confirmation(tmp_path):
    svc = service(tmp_path); scope = preview(svc)
    completed = finish(svc, start(svc, scope))
    for _ in range(PREVIEW_LIMIT * 2): preview(svc)
    assert len(svc._scope_previews) == PREVIEW_LIMIT
    assert start(svc, scope)['id'] == completed['id']


def test_public_preview_mutation_cannot_expand_private_frozen_scope(tmp_path):
    svc = service(tmp_path); scope = preview(svc)
    scope['services'][0]['endpoint'] = 'http://127.0.0.1:29999'
    scope['roots'].append({'path': str(tmp_path), 'source': 'COMMON'})
    scope['limits']['max_files'] = 999999
    result = finish(svc, start(svc, scope))
    assert result['roots'] == [] and not any(endpoint.endswith(':29999') for endpoint, _, _ in svc.client.calls)


def test_hidden_runtime_options_change_invalidates_consent(tmp_path):
    svc = service(tmp_path)
    runtime = svc.configure_runtime(LocalRuntimeInput(name='llama-options', type='LLAMA_CPP', endpoint='http://127.0.0.1:29998'))
    scope = preview(svc)
    svc.configure_runtime(LocalRuntimeInput(name='llama-options', type='LLAMA_CPP', endpoint='http://127.0.0.1:29998', context_size=16384), runtime['id'])
    with pytest.raises(ValueError, match='SCOPE_STALE'): start(svc, scope)


def test_common_root_resolution_change_invalidates_consent(tmp_path, monkeypatch):
    svc = service(tmp_path)
    first = tmp_path / 'first'; first.mkdir()
    second = tmp_path / 'second'; second.mkdir()
    monkeypatch.setattr('app.model_center.discovery_environment.common_model_roots', lambda: [str(first)])
    scope = preview(svc, True)
    monkeypatch.setattr('app.model_center.discovery_environment.common_model_roots', lambda: [str(second)])
    with pytest.raises(ValueError, match='SCOPE_STALE'): start(svc, scope)
    assert not svc.client.calls


def test_consented_scan_flag_revocation_stops_late_result_adoption(tmp_path, monkeypatch):
    svc = service(tmp_path); began, release = threading.Event(), threading.Event()
    def hardware(): began.set(); release.wait(2); return {'late': True}
    svc.hardware_probe = hardware
    job = start(svc, preview(svc)); assert began.wait(1)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    release.set(); result = finish(svc, job)
    assert result['status'] == 'CANCELLED' and not svc.client.calls and 'late' not in svc.hardware


def test_registration_metadata_reconciliation_respects_shared_scan_deadline(tmp_path):
    svc = service(tmp_path); path = tmp_path / 'registered.gguf'; gguf(path)
    record = registered_llama(svc, path)
    svc._observed_registration = Mock(side_effect=AssertionError('no metadata after deadline'))
    svc._reconcile_detected_runtime(record['runtime_config'], {}, [], deadline=time.monotonic() - 1)
    svc._observed_registration.assert_not_called()


@pytest.mark.parametrize('mode', ['revoke', 'deadline'])
@pytest.mark.parametrize('operation', ['preview', 'confirm'])
def test_planning_stops_between_registered_metadata_entries(tmp_path, monkeypatch, mode, operation):
    from app.model_center import discovery_scope as scope_module
    svc = service(tmp_path)
    paths = [tmp_path / f'registered-{index}.gguf' for index in range(3)]
    for path in paths: gguf(path); registered_llama(svc, path)
    issued = preview(svc) if operation == 'confirm' else None
    original = scope_module.path_identity; seen = []; revoked = False
    current_time = time.monotonic()
    clock = [current_time]
    monkeypatch.setattr(scope_module.time, 'monotonic', lambda: clock[0])
    def identity(path, **kwargs):
        nonlocal revoked
        result = original(path, **kwargs)
        seen.append(path)
        if path == str(paths[0]):
            if mode == 'revoke': revoked = True
            else: clock[0] += scope_module.PLANNING_BUDGET_SECONDS + 1
        return result
    monkeypatch.setattr(scope_module, 'path_identity', identity)
    code = 'LOCAL_AI_SCOPE_REVOKED' if mode == 'revoke' else 'LOCAL_AI_SCOPE_BUDGET_REACHED'
    with pytest.raises(ValueError, match=code):
        if operation == 'confirm': start(svc, issued, guard=lambda: not revoked)
        else: preview(svc, guard=lambda: not revoked)
    assert seen == [str(paths[0])]
    assert svc.scan is None and not svc.client.calls
    if operation == 'preview': assert not svc._scope_previews
    else:
        row = svc._scope_previews[issued['scope_digest']]
        assert row['scan_id'] is None and not row.get('stale')


def test_planning_deadline_after_final_metadata_read_does_not_issue_preview(tmp_path, monkeypatch):
    from app.model_center import discovery_scope as scope_module
    svc = service(tmp_path); path = tmp_path / 'only.gguf'; gguf(path); registered_llama(svc, path)
    original = scope_module.path_identity
    clock = [time.monotonic()]
    monkeypatch.setattr(scope_module.time, 'monotonic', lambda: clock[0])
    def identity(value, **kwargs):
        result = original(value, **kwargs)
        clock[0] += scope_module.PLANNING_BUDGET_SECONDS + 1
        return result
    monkeypatch.setattr(scope_module, 'path_identity', identity)
    with pytest.raises(ValueError, match='LOCAL_AI_SCOPE_BUDGET_REACHED'): preview(svc)
    assert not svc._scope_previews and svc.scan is None and not svc.client.calls


def test_planning_owner_lock_wait_uses_finite_budget(tmp_path, monkeypatch):
    svc = service(tmp_path); held, release = threading.Event(), threading.Event()
    def block():
        with svc.center._config_lock:
            held.set(); release.wait(2)
    thread = threading.Thread(target=block); thread.start(); assert held.wait(1)
    monkeypatch.setattr('app.model_center.discovery.PLANNING_BUDGET_SECONDS', .05)
    started = time.monotonic()
    try:
        with pytest.raises(ValueError, match='LOCAL_AI_SCOPE_BUDGET_REACHED'): preview(svc)
        assert time.monotonic() - started < .5
        assert not svc._scope_previews and not svc.client.calls
    finally:
        release.set(); thread.join(1)


def test_planning_owner_lock_wait_rechecks_revocation(tmp_path):
    svc = service(tmp_path); held, release = threading.Event(), threading.Event(); checks = 0
    def block():
        with svc.center._config_lock:
            held.set(); release.wait(2)
    def guard():
        nonlocal checks
        checks += 1
        return checks < 5
    thread = threading.Thread(target=block); thread.start(); assert held.wait(1)
    try:
        with pytest.raises(ValueError, match='LOCAL_AI_SCOPE_REVOKED'): preview(svc, guard=guard)
        assert not svc._scope_previews and not svc.client.calls
    finally:
        release.set(); thread.join(1)


def test_preview_discloses_separate_fixed_planning_and_scan_budgets(tmp_path):
    scope = preview(service(tmp_path))
    assert scope['limits']['planning_budget_seconds'] == 5
    assert scope['limits']['scan_budget_seconds'] == 45
