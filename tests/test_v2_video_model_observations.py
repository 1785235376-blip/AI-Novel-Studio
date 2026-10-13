"""Tiny synthetic metadata and original protected APIs; no weights or model run."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.asset_providers import AssetProviderRegistry
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_environment import video_file_associations
from app.model_center.discovery_types import DiscoverySettingsInput
from app.model_runtime import ModelRegistry, ProviderRegistry
from test_local_ai_discovery import service, approve_license
from test_local_ai_environment_v2 import safetensors, v2  # noqa: F401
from test_v2_discovery_scope import preview, start, finish
from test_v2_discovery_onboarding_api import HEADERS, onboard  # noqa: F401
from test_v2_video_runtime_foundation import MODELS, object_info


def populate(svc, root):
    svc.client.payloads[('http://127.0.0.1:8188', '/system_stats')] = {'system': {}}
    svc.client.payloads[('http://127.0.0.1:8188', '/object_info')] = object_info()
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(root)], include_common_model_dirs=False))
    return finish(svc, start(svc, preview(svc)))


def wan(report):
    return next(row for row in report['models'] if row['model_name'] == MODELS['WAN'])


def forbid_projection_io(svc, monkeypatch):
    forbidden = Mock(side_effect=AssertionError('Projection may not probe, enumerate, inspect or start'))
    monkeypatch.setattr(svc.client, 'json', forbidden)
    monkeypatch.setattr(svc, 'hardware_probe', forbidden)
    monkeypatch.setattr('app.model_center.discovery_environment._metadata_bytes', forbidden)
    monkeypatch.setattr('app.model_center.discovery_environment._scoped_scandir', forbidden)
    return forbidden


@pytest.mark.parametrize('directory', ['', 'diffusion_models', 'unet'])
def test_exact_loader_observation_has_no_enable_or_loaded_path_authority(tmp_path, monkeypatch, directory):
    svc = service(tmp_path); root = tmp_path / 'synthetic-models'; target = root / directory
    target.mkdir(parents=True); path = target / MODELS['WAN']; safetensors(path)
    job = populate(svc, root); before = deepcopy(job)
    expected_bytes = path.stat().st_size
    forbidden = forbid_projection_io(svc, monkeypatch)
    report = svc.environment_report()['video_observations']
    value = wan(report)
    assert value['file_association'] == {'status': 'MATCHED', 'reason': 'CONFIGURED_ROOT_OBSERVATION_NOT_RUNTIME_BINDING',
        'file_id': next(row['id'] for row in job['model_files'] if row['path'] == str(path)),
        'path': str(path), 'root': str(root), 'observed_file_bytes': expected_bytes, 'size_semantics': 'WEIGHT_FILE',
        'runtime_path_verified': False, 'eligibility_derived': False}
    assert value['registered'] is value['enabled'] is value['enable_eligible'] is value['inference_verified'] is False
    assert value['model_total_bytes'] is value['required_vram_bytes'] is None
    assert report['health_probed'] is report['credentials_read'] is report['automatic_runtime_start'] is False
    assert svc.snapshot()['video_observations'] == report and svc.get_scan(job['id']) == before
    assert not svc.registrations and all(candidate['local_path'] == '' for candidate in job['candidates'])
    forbidden.assert_not_called(); svc.center.lifecycle.start.assert_not_called()


def test_nested_same_basename_is_not_an_exact_loader_filename_match(tmp_path):
    svc = service(tmp_path); root = tmp_path / 'synthetic-models'
    for directory in ('one', 'two'):
        target = root / directory; target.mkdir(parents=True); safetensors(target / MODELS['WAN'])
    populate(svc, root)
    association = wan(svc.environment_report()['video_observations'])['file_association']
    assert association['status'] == 'NOT_OBSERVED' and association['path'] is None
    assert not svc.registrations


def test_multiple_exact_configured_roots_are_ambiguous_without_path_or_qualification(tmp_path):
    svc = service(tmp_path); first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir(); second.mkdir(); safetensors(first / MODELS['WAN']); safetensors(second / MODELS['WAN'])
    populate(svc, first)
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(first), str(second)], include_common_model_dirs=False))
    finish(svc, start(svc, preview(svc)))
    row = wan(svc.environment_report()['video_observations'])
    assert row['file_association']['status'] == 'AMBIGUOUS'
    assert row['file_association']['path'] is row['file_association']['observed_file_bytes'] is None
    assert row['enable_eligible'] is False and not svc.registrations


@pytest.mark.parametrize('fault', ['bounded', 'cancelled', 'removed-root', 'common-only', 'bad-header'])
def test_incomplete_or_unapproved_observation_stays_unknown(tmp_path, fault):
    svc = service(tmp_path); root = tmp_path / 'synthetic-models'; root.mkdir(); safetensors(root / MODELS['WAN'])
    populate(svc, root)
    if fault == 'bounded': svc.scan['roots'][0]['status'] = 'BOUNDED'
    elif fault == 'cancelled': svc.scan['status'] = 'CANCELLED'
    elif fault == 'removed-root': svc.configure_roots(DiscoverySettingsInput(scan_roots=[], include_common_model_dirs=False))
    elif fault == 'common-only': svc.scan['model_files'][0]['source'] = 'COMMON'
    else: svc.scan['model_files'][0]['header_valid'] = False
    row = wan(svc.environment_report()['video_observations'])
    assert row['file_association']['status'] in {'UNKNOWN', 'NOT_OBSERVED'}
    assert row['file_association']['path'] is row['required_vram_bytes'] is None
    assert row['registered'] is row['enabled'] is False


@pytest.mark.parametrize('filename', ['../wan.safetensors', '/wan.safetensors', 'C:/wan.safetensors', 'folder//wan.safetensors'])
def test_absolute_or_traversing_loader_names_never_project_private_files(tmp_path, filename):
    svc = service(tmp_path); root = tmp_path / 'synthetic-models'; root.mkdir(); safetensors(root / MODELS['WAN'])
    job = populate(svc, root)
    candidate = next(row for row in job['candidates'] if row['model_name'] == MODELS['WAN'])
    candidate['model_name'] = filename
    association = video_file_associations(job, [str(root)])(candidate)
    assert association['status'] == 'UNKNOWN' and association['path'] is None


def test_diffusers_index_bytes_are_only_metadata_and_never_total_or_vram(tmp_path):
    svc = service(tmp_path); root = tmp_path / 'synthetic-models'; bundle = root / 'wan-bundle'; bundle.mkdir(parents=True)
    index = bundle / 'model_index.json'; index.write_text(json.dumps({'_class_name': 'WanPipeline'}), encoding='utf-8')
    job = populate(svc, root)
    raw = next(row for row in job['model_files'] if row['format'] == 'DIFFUSERS')
    row = next(row for row in svc.environment_report()['video_observations']['files'] if row['format'] == 'DIFFUSERS')
    assert raw['size_bytes'] == row['observed_file_bytes'] == index.stat().st_size
    assert row['size_semantics'] == 'INDEX_METADATA'
    assert row['model_total_bytes'] is row['required_vram_bytes'] is None and row['inference_verified'] is False


def test_original_live_registration_and_bridge_state_project_without_probe(tmp_path, monkeypatch):
    svc = service(tmp_path); root = tmp_path / 'synthetic-models'; root.mkdir(); populate(svc, root)
    videos = {}; svc.route_bridge = LocalDiscoveryBridge(svc,
        SimpleNamespace(provider_registry=ProviderRegistry(), model_registry=ModelRegistry()), AssetProviderRegistry(), videos)
    identifier = wan(svc.snapshot()['video_observations'])['candidate_id']
    svc.validate(identifier); svc.register(identifier); approve_license(svc, identifier); svc.enable(identifier)
    adapter = videos[svc.registrations[identifier]['provider_id']]
    forbidden = forbid_projection_io(svc, monkeypatch)
    monkeypatch.setattr(adapter, 'studio_configuration', forbidden); monkeypatch.setattr(adapter, 'health_check', forbidden)
    before = deepcopy(svc.registrations)
    row = wan(svc.environment_report()['video_observations'])
    assert row['registered'] is row['enabled'] is row['enable_eligible'] is row['structure_validated'] is True
    assert row['route_state'] == 'REGISTERED' and row['structural_only'] is True and row['inference_verified'] is False
    assert svc.registrations == before
    svc.disable(identifier)
    row = wan(svc.environment_report()['video_observations'])
    assert row['registered'] is True and row['enabled'] is False and row['route_state'] == 'NOT_REGISTERED'
    forbidden.assert_not_called()


def test_historical_registration_cannot_lend_loader_evidence_to_a_new_file_scan(tmp_path, monkeypatch):
    svc = service(tmp_path); root = tmp_path / 'synthetic-models'; root.mkdir(); safetensors(root / MODELS['WAN'])
    populate(svc, root)
    identifier = wan(svc.snapshot()['video_observations'])['candidate_id']
    svc.validate(identifier); svc.register(identifier)
    before = deepcopy(svc.registrations)
    # The last scan can no longer advertise that model or its exact loader.
    svc.scan['candidates'] = [row for row in svc.scan['candidates'] if row['id'] != identifier]
    forbidden = forbid_projection_io(svc, monkeypatch)
    row = wan(svc.environment_report()['video_observations'])
    assert row['registered'] is True and row['enabled'] is False
    assert row['file_association']['status'] == 'UNKNOWN' and row['file_association']['path'] is None
    assert row['file_association']['reason'] == 'RUNTIME_MODEL_NOT_OBSERVED_IN_LAST_SCAN'
    assert svc.registrations == before
    forbidden.assert_not_called()


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_mounted_optional_report_is_host_private_passive_and_copies_original_evidence(onboard, tmp_path, monkeypatch, prefix):
    client, svc, sessions = onboard; root = tmp_path / 'synthetic-models'; root.mkdir(); safetensors(root / MODELS['WAN'])
    original = populate(svc, root)
    forbidden = forbid_projection_io(svc, monkeypatch)
    base = prefix + '/model-center/local-ai'
    snapshot = client.get(base, headers=HEADERS); environment = client.get(base + '/environment', headers=HEADERS)
    assert snapshot.status_code == environment.status_code == 200
    assert snapshot.headers['Cache-Control'] == environment.headers['Cache-Control'] == 'no-store'
    report = snapshot.json()['video_observations']
    assert report == environment.json()['video_observations'] and wan(report)['file_association']['status'] == 'MATCHED'
    assert snapshot.json()['scan'] == original and svc.get_scan(original['id']) == original
    if prefix == '/api' and os.environ.get('POEMSEED_VIDEO_OBSERVATION_CAPTURE'):
        # Optional local handoff capture of actual mounted synthetic evidence.
        # Replace only this fixture's generated root, never user scan contents.
        capture = Path(os.environ['POEMSEED_VIDEO_OBSERVATION_CAPTURE'])
        capture.parent.mkdir(parents=True, exist_ok=True)
        data = environment.json()
        def sanitized(value):
            if isinstance(value, dict): return {key: sanitized(item) for key, item in value.items()}
            if isinstance(value, list): return [sanitized(item) for item in value]
            if isinstance(value, str) and value.startswith(str(root)):
                return '/SYNTHETIC_MODEL_ROOT' + value[len(str(root)):].replace('\\', '/')
            return value
        capture.write_text(json.dumps(sanitized(data), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    report['models'][0]['enabled'] = True; report['files'][0]['path'] = 'response-only-change'
    assert svc.environment_report()['video_observations'] == environment.json()['video_observations']
    assert 'synthetic-scope-host' not in snapshot.text + environment.text
    assert client.get(base + '/environment').status_code == 401
    sessions.revoke('synthetic-scope-host')
    assert client.get(base, headers=HEADERS).status_code == 401
    assert client.get(base + '/environment', headers=HEADERS).status_code == 401
    forbidden.assert_not_called(); svc.center.lifecycle.start.assert_not_called()


@pytest.mark.parametrize('v1,flags', [('1', 'narrative_production_v2'), ('', '')])
def test_additive_projection_does_not_change_default_or_v1_snapshot(tmp_path, monkeypatch, v1, flags):
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1); monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags)
    svc = service(tmp_path)
    assert 'video_observations' not in svc.snapshot()
    assert 'video_observations' not in svc.environment_report()
    assert svc.scan is None and svc.client.calls == []
