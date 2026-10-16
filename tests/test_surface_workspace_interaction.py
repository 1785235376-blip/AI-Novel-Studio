"""Functional freeze: original workspace owner, real File/PostgreSQL profiles."""
from copy import deepcopy
from dataclasses import replace
import threading

import pytest
from fastapi import HTTPException

from app.experimental.store import ExperimentalStore
from app.experimental.ux import WorkspaceToolsService
from app.experimental.workspace_interaction import COMMANDS, InteractionPreferences
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r4_workspace_tools import ux_env
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_r4_mounted_workspaces import workspace as legacy_workspace


@pytest.fixture
def workspace(legacy_workspace, monkeypatch):
    from app.experimental.flags import RUNTIME_FLAGS
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(RUNTIME_FLAGS))
    return legacy_workspace


def save(e, version=0, **preferences):
    return e.service.save_interaction(e.ctx, {'expected_version': version, 'preferences': preferences})


def test_interaction_initial_empty_no_model_or_manuscript_copy(ux_env):
    e = ux_env
    before = deepcopy(e.rows)
    value = e.service.interaction(e.ctx)
    assert value['version'] == 0 and value['state'] == 'EMPTY'
    assert value['preferences']['keyboard_enabled'] is False
    assert value['preferences']['confirm_navigation_with_unsaved_input'] is True
    commands = e.service.workspace_commands(e.ctx)
    assert len(commands['items']) == 5 and commands['dispatches_tasks'] is False
    assert all(row['shortcut'] is None and row['requires_dirty_guard'] for row in commands['items'])
    assert e.rows == before and e.store.read(e.ctx.novel_id, e.ctx.scope)['collections'] == {}


def test_interaction_restart_history_restore_and_scope_actor_isolation(ux_env):
    e = ux_env
    first = save(e, keyboard_enabled=True, announcements='off')
    second = save(e, 1, reduced_motion='reduce')
    assert (first['version'], second['version']) == (1, 2)
    restart = WorkspaceToolsService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters)
    assert restart.interaction(e.ctx)['preferences']['reduced_motion'] == 'reduce'
    assert restart.interaction(replace(e.ctx, actor='bob'))['version'] == 0
    branch = replace(e.ctx, scope={'mode': 'collaboration', 'novel_id': e.ctx.novel_id,
                                  'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}, branch='b')
    assert restart.interaction(branch)['version'] == 0
    restored = restart.restore_interaction(e.ctx, {'expected_version': 2, 'source_version': 1})
    assert restored['version'] == 3 and restored['preferences']['keyboard_enabled'] is True
    assert restored['preferences']['announcements'] == 'off'
    assert [r['version'] for r in restart.interaction_history(e.ctx)['items']] == [1, 2]


def test_interaction_two_writers_only_one_cas_wins(ux_env):
    e = ux_env
    save(e)
    barrier = threading.Barrier(2)
    outcomes = []
    def write():
        barrier.wait()
        try:
            save(e, 1, keyboard_enabled=True)
            outcomes.append('SAVED')
        except CapabilityVersionConflict:
            outcomes.append('CONFLICT')
    threads = [threading.Thread(target=write) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert sorted(outcomes) == ['CONFLICT', 'SAVED']
    assert e.service.interaction(e.ctx)['version'] == 2


@pytest.mark.parametrize('body', [
    {'shortcuts': {'open_search': 'Mod+Shift+J', 'open_tasks': 'Mod+Shift+J'}},
    {'shortcuts': {'delete_project': 'Mod+Shift+R'}},
    {'shortcuts': {'open_tasks': 'javascript:execute()'}},
    {'confirm_navigation_with_unsaved_input': False},
    {'announcements': '<script>unsafe</script>'},
    {'unknown_access': True},
])
def test_interaction_rejects_collisions_unknown_or_unsafe_preferences(ux_env, body):
    e = ux_env
    with pytest.raises(ValueError):
        save(e, **body)
    assert e.service.interaction(e.ctx)['version'] == 0


def test_interaction_revocation_rolls_back_at_final_commit_fence(ux_env):
    e = ux_env
    calls = []
    def revoked():
        calls.append(True)
        if len(calls) == 3:
            raise HTTPException(403, 'REVOKED')
    with pytest.raises(HTTPException):
        e.service.save_interaction(e.ctx, {'expected_version': 0, 'preferences': {}}, revoked)
    assert len(calls) == 3
    assert e.service.interaction(e.ctx)['version'] == 0


def test_interaction_corruption_isolated_and_explicit_cas_reset(ux_env):
    e = ux_env
    save(e, keyboard_enabled=True)
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as doc:
        row = doc['collections'][e.service.INTERACTION][e.service._owner(e.ctx.actor)]
        row['preferences'] = {'secret': 'PRIVATE_BAD_PREFS'}
    result = e.service.interaction(e.ctx)
    assert result['recovery_required'] and result['preferences']['keyboard_enabled'] is False
    assert 'PRIVATE_BAD_PREFS' not in str(result)
    with pytest.raises(CapabilityVersionConflict):
        e.service.reset_interaction(e.ctx, 0)
    reset = e.service.reset_interaction(e.ctx, 1)
    assert reset['version'] == 2 and not reset['recovery_required']
    assert e.service.interaction_history(e.ctx)['items'] == [{'version': 1, 'state': 'UNAVAILABLE'}]
    with pytest.raises(ValueError):
        e.service.restore_interaction(e.ctx, {'expected_version': 2, 'source_version': 1})


def test_command_resolve_is_actor_scope_revision_bound_and_never_executes(ux_env):
    e = ux_env
    before = deepcopy(e.rows)
    commands = e.service.workspace_commands(e.ctx)
    target = e.service.resolve_workspace_command(e.ctx, {'command_id': 'open_search', 'expected_revision': commands['revision']})
    assert target['section'] == 'search' and target['dispatched'] is False
    with pytest.raises(HTTPException) as error:
        e.service.resolve_workspace_command(replace(e.ctx, actor='bob'), {'command_id': 'open_search', 'expected_revision': commands['revision']})
    assert error.value.status_code == 409
    save(e, keyboard_enabled=True)
    with pytest.raises(HTTPException):
        e.service.resolve_workspace_command(e.ctx, {'command_id': 'open_search', 'expected_revision': commands['revision']})
    assert e.rows == before


def test_interaction_history_bounded_and_no_missing_restore_overwrite(ux_env):
    e = ux_env
    for version in range(24):
        save(e, version, keyboard_enabled=bool(version % 2))
    history = e.service.interaction_history(e.ctx)['items']
    assert len(history) == 20 and history[0]['version'] == 4
    with pytest.raises(FileNotFoundError):
        e.service.restore_interaction(e.ctx, {'expected_version': 24, 'source_version': 1})
    assert e.service.interaction(e.ctx)['version'] == 24


def test_mounted_interaction_api_flag_version_command_and_recovery(workspace, monkeypatch):
    e = workspace
    base = e.base + '/workspace'
    initial = e.client.get(base + '/interaction')
    assert initial.headers['cache-control'] == 'no-store'
    assert checked(initial)['state'] == 'EMPTY'
    saved = checked(e.client.put(base + '/interaction', json={'expected_version': 0, 'preferences': {'keyboard_enabled': True}}))
    assert saved['version'] == 1
    assert e.client.put(base + '/interaction', json={'expected_version': 0, 'preferences': {}}).status_code == 409
    commands = checked(e.client.get(base + '/commands'))
    assert all(r['shortcut'] for r in commands['items'])
    result = checked(e.client.post(base + '/commands/resolve', json={'command_id': 'open_tasks', 'expected_revision': commands['revision']}))
    assert result['section'] == 'tasks' and result['dispatched'] is False
    reset = checked(e.client.post(base + '/interaction/reset', json={'expected_version': 1}))
    assert reset['version'] == 2
    assert checked(e.client.get(base + '/interaction/history'))['items'][0]['version'] == 1
    assert checked(e.client.post(base + '/interaction/restore', json={'expected_version': 2, 'source_version': 1}))['preferences']['keyboard_enabled'] is True
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    assert e.client.get(base + '/interaction').status_code == 404
    assert e.client.get(base + '/commands').status_code == 404


def test_mounted_interaction_viewer_write_denied_actor_separation_revoke(workspace, monkeypatch):
    e = scoped(workspace, monkeypatch)
    base = e.base + '/workspace'
    assert checked(e.client.put(base + '/interaction', headers=e.headers, json={'expected_version': 0, 'preferences': {'keyboard_enabled': True}}))['version'] == 1
    assert checked(e.client.get(base + '/interaction', headers=e.viewer_headers))['version'] == 0
    assert e.client.put(base + '/interaction', headers=e.viewer_headers, json={'expected_version': 0, 'preferences': {}}).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(base + '/interaction', headers=e.headers).status_code == 403
    assert e.client.get(base + '/commands', headers=e.headers).status_code == 403


def test_mounted_interaction_v1_and_dependency_gate(workspace, monkeypatch):
    e = workspace
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_interaction_v1')
    assert e.client.get(e.base + '/workspace/interaction').status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2,workspace_interaction_v1')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert e.client.get(e.base + '/workspace/interaction').status_code == 404
