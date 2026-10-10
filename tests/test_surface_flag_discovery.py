"""Versioned discovery preserves old clients and exposes all explicit opt-ins."""
import pytest
from app.experimental.flags import FLAGS, RUNTIME_FLAGS, SURFACE_FLAGS, enabled_flags, flag_status, require_flag
from fastapi import HTTPException
from test_r3_mounted_contracts import mounted, prefix, checked


def names(values): return {'experimental.' + item for item in values}


def test_legacy_complete_opt_in_does_not_silently_enable_new_surfaces(monkeypatch):
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))
    result = flag_status()
    assert result['schema_version'] == 2
    assert set(result['features']) == names(FLAGS) and all(result['features'].values())
    assert set(result['surface_features']) == names(SURFACE_FLAGS)
    assert not any(result['surface_features'].values())
    assert set(result['runtime_features']) == names(RUNTIME_FLAGS)
    assert set(result['dependencies']) == names(RUNTIME_FLAGS)
    assert enabled_flags() == frozenset(FLAGS)


@pytest.mark.parametrize('configuration', ['', '*', 'all,unknown,arbitrary_plugin'])
def test_discovery_lists_disabled_new_features_without_granting_them(monkeypatch, configuration):
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', configuration)
    result = flag_status()
    assert not any(result['runtime_features'].values())
    assert not any(result['surface_features'].values())
    assert set(result['runtime_features']) == names(RUNTIME_FLAGS)
    assert enabled_flags() == frozenset()


def test_surface_exact_dependencies_and_acceptance_override(monkeypatch):
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_interaction_v1')
    assert enabled_flags() == frozenset()
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2,workspace_interaction_v1')
    assert enabled_flags() == {'workspace_tools_v2', 'workspace_interaction_v1'}
    assert flag_status()['runtime_features']['experimental.workspace_interaction_v1'] is True
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(RUNTIME_FLAGS))
    assert enabled_flags() == frozenset(RUNTIME_FLAGS)
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert not any(flag_status()['runtime_features'].values())
    for flag in RUNTIME_FLAGS:
        with pytest.raises(HTTPException) as error: require_flag(flag)
        assert error.value.status_code == 404


def test_actual_api_discovery_exposes_runtime_inventory_and_does_not_mutate_configuration(mounted, monkeypatch):
    e = mounted
    response = checked(e.client.get(e.prefix + '/experimental/features'))
    assert all(response['features'].values()) and not any(response['surface_features'].values())
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(RUNTIME_FLAGS))
    response = checked(e.client.get(e.prefix + '/experimental/features'))
    assert all(response['runtime_features'].values())
    assert response['surface_features']['experimental.branch_manuscript_v1'] is True
    assert response['dependencies']['experimental.realtime_collaboration_v1'] == ['writer_room_v2', 'branch_manuscript_v1']
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    response = checked(e.client.get(e.prefix + '/experimental/features'))
    assert not any(response['runtime_features'].values())
