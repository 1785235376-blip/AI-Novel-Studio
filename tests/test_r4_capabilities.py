"""F00 registry evidence: registration never implies implementation or opt-in."""
import json
from pathlib import Path
from fastapi import HTTPException
import pytest
from app.experimental.capabilities import CAPABILITIES, capability_status
from app.experimental.flags import FLAGS, FLAG_DEPENDENCIES, enabled_flags, require_flag


def test_all_forty_packages_and_dependency_waves_are_registered():
    expected = {'F00'} | {f'A{i:02}' for i in range(1, 14)} | {f'B{i:02}' for i in range(1, 11)} | {f'U{i:02}' for i in range(1, 17)}
    assert len(CAPABILITIES) == 40
    assert {row['id'] for row in CAPABILITIES} == expected
    assert {row['wave'] for row in CAPABILITIES} == set(range(7))
    assert all(set(row['dependencies']).issubset(expected - {row['id']}) for row in CAPABILITIES)
    matrix = json.loads((Path(__file__).resolve().parents[1] / 'docs/delivery/post-v1-r4-r5-ux/FEATURE_MATRIX.json').read_text())
    assert {row['id'] for row in matrix['packages']} == expected
    assert len(matrix['inherited_r3_gaps']) == 9


def test_planned_capabilities_never_become_runnable_by_allowlist(monkeypatch):
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(str(row['flag']) for row in CAPABILITIES))
    for item in capability_status()['items']:
        if item['implementation'] == 'PENDING':
            assert item['available'] is False
            assert item['disabled_reason'] == 'IMPLEMENTATION_PENDING'
    assert 'b10_v2' not in enabled_flags()


def test_new_flags_exact_allowlist_default_off_and_v1_override(monkeypatch):
    monkeypatch.delenv('EXPERIMENTAL_FEATURES', raising=False)
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    assert not enabled_flags()
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '*,all,writing_recovery_v2,workspace_tools_v2')
    assert enabled_flags() == {'writing_recovery_v2', 'workspace_tools_v2'}
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert not enabled_flags()
    for name in FLAGS:
        with pytest.raises(HTTPException) as error:
            require_flag(name)
        assert error.value.status_code == 404


def test_runtime_dependencies_require_explicit_opt_in(monkeypatch):
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    monkeypatch.setitem(FLAG_DEPENDENCIES, 'workspace_tools_v2', ('writing_recovery_v2',))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    assert not enabled_flags()
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2,writing_recovery_v2')
    assert enabled_flags() == {'workspace_tools_v2', 'writing_recovery_v2'}
    assert set(FLAG_DEPENDENCIES) == set(FLAGS)
