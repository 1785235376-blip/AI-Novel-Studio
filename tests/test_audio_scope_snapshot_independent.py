"""Independent File-scope observation checks, not quota or history acceptance."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from app.experimental.audio_scope_snapshot import (
    AudioScopeObservationUnavailable,
    inspect_existing_audio_scope,
)
from app.experimental.store import ExperimentalStore, LIFECYCLE, canonical
from app.storage import atomic_write
from test_audio_history_status_readonly import snapshot
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only
MIX = 'audio_v2_mix_proposals'


def initialize(rig, count=1):
    project = rig.workspace.store
    identity = project.incarnation(rig.nid)
    store = project.store
    with store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['unrelated_synthetic'] = {'note': {'body': '不要修改雪☃'}}
        rows = {}
        for index in range(count):
            row = candidate()
            row.update(novel_id=rig.nid, scope=copy.deepcopy(rig.scope), id='synthetic-' + str(index))
            rows[row['id']] = row
        doc['collections'][MIX] = rows
    return project, store, identity


@pytest.mark.parametrize('count', [0, 1, 2])
def test_observation_is_read_only_and_never_claims_audio_ownership(rig, count):
    project, store, identity = initialize(rig, count)
    before = snapshot(rig.root)
    guards = []
    result = inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: guards.append(True))
    assert result == {'scope_snapshot': 'UNKNOWN', 'audio_row_binding': 'UNVERIFIED',
                      'project_charge_known': False, 'new_write_admission': 'CLOSED'}
    assert len(guards) == 2
    assert 'content_base64' not in json.dumps(result)
    assert snapshot(rig.root) == before


def test_new_scope_does_not_create_locks_markers_or_document(rig):
    project, store = rig.workspace.store, rig.workspace.store.store
    nid = rig.project()
    scope = {'mode': 'local', 'novel_id': nid}
    before = snapshot(rig.root)
    with pytest.raises(AudioScopeObservationUnavailable):
        inspect_existing_audio_scope(project, nid, scope, lambda: None)
    assert snapshot(rig.root) == before
    assert not store.path(nid, scope).exists()
    assert not (rig.root / 'novels' / nid / 'creative_project_v2.json').exists()


def test_old_scope_without_lifecycle_is_not_invented(rig):
    project, store = rig.workspace.store, rig.workspace.store.store
    # Original legacy transaction occurs before a project marker exists.
    with store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['unrelated_synthetic'] = {'body': {'text': '保留'}}
    path = store.path(rig.nid, rig.scope)
    assert LIFECYCLE not in json.loads(path.read_bytes())
    project.incarnation(rig.nid)
    before = snapshot(rig.root)
    assert inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)['scope_snapshot'] == 'UNKNOWN'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('mode', ['missing_document', 'invalid_document', 'missing_marker'])
def test_missing_or_corrupt_committed_inputs_are_not_repaired(rig, mode):
    project, store, _ = initialize(rig)
    path = store.path(rig.nid, rig.scope)
    if mode == 'missing_document':
        path.unlink()
    elif mode == 'missing_marker':
        (rig.root / 'novels' / rig.nid / 'creative_project_v2.json').unlink()
    elif mode == 'invalid_document':
        path.write_bytes(b'{not-a-valid-json')
    before = snapshot(rig.root)
    if mode == 'missing_marker':
        with pytest.raises(AudioScopeObservationUnavailable):
            inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)
    else:
        assert inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)['scope_snapshot'] == 'UNKNOWN'
    assert snapshot(rig.root) == before


def test_invalid_unbound_audio_does_not_change_unknown_result(rig):
    project, store, _ = initialize(rig)
    path = store.path(rig.nid, rig.scope)
    document = json.loads(path.read_bytes())
    first = next(iter(document['collections'][MIX].values()))
    first['content_sha256'] = '0' * 64
    path.write_text(canonical(document), encoding='utf-8')
    before = snapshot(rig.root)
    assert inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None) == {
        'scope_snapshot': 'UNKNOWN', 'audio_row_binding': 'UNVERIFIED',
        'project_charge_known': False, 'new_write_admission': 'CLOSED'}
    assert snapshot(rig.root) == before


def test_guard_error_before_or_after_snapshot_is_not_suppressed(rig):
    project, store, _ = initialize(rig)
    before = snapshot(rig.root)
    class Revoked(Exception):
        pass
    for fail_on in (1, 2):
        calls = []
        def guard():
            calls.append(True)
            if len(calls) == fail_on:
                raise Revoked('synthetic authority changed')
        with pytest.raises(Revoked):
            inspect_existing_audio_scope(project, rig.nid, rig.scope, guard)
    assert snapshot(rig.root) == before


def test_authority_guard_never_runs_inside_the_project_lease(rig, monkeypatch):
    project, _, _ = initialize(rig)
    before = snapshot(rig.root)
    original = project.owner_lease
    active = []
    @contextmanager
    def lease(nid):
        with original(nid) as identity:
            active.append(True)
            try:
                yield identity
            finally:
                active.pop()
    monkeypatch.setattr(project, 'owner_lease', lease)
    observed = []
    def guard():
        observed.append(bool(active))
    result = inspect_existing_audio_scope(project, rig.nid, rig.scope, guard)
    assert observed == [False, False]
    assert result['audio_row_binding'] == 'UNVERIFIED'
    assert snapshot(rig.root) == before


def test_existing_outer_request_budget_cannot_be_reset_by_observation(rig):
    from app.creative.asset_usage_budget import usage_read_budget
    project, store, _ = initialize(rig)
    raw = store.path(rig.nid, rig.scope).read_bytes()
    before = snapshot(rig.root)
    with usage_read_budget() as budget:
        budget.MAX_SCOPE_BYTES = len(raw) - 1
        assert inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)['scope_snapshot'] == 'UNKNOWN'
        assert budget.MAX_SCOPE_BYTES == len(raw) - 1
    assert snapshot(rig.root) == before


def test_non_file_backend_fails_without_touching_file_owner(rig, monkeypatch):
    project, store, _ = initialize(rig)
    before = snapshot(rig.root)
    monkeypatch.setattr(store, 'backend', 'postgres')
    with pytest.raises(AudioScopeObservationUnavailable):
        inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)
    assert snapshot(rig.root) == before


def test_scope_snapshot_reader_is_not_invoked(rig, monkeypatch):
    project, store, _ = initialize(rig)
    original = store._file_snapshot
    path = store.path(rig.nid, rig.scope)
    calls = []
    def swapped(nid, scope):
        value = original(nid, scope)
        calls.append(True)
        if len(calls) == 1:
            changed = copy.deepcopy(value[1])
            changed['collections']['unrelated_synthetic']['note']['body'] = '外部合成更新'
            atomic_write(path, canonical(changed))
        return value
    monkeypatch.setattr(store, '_file_snapshot', swapped)
    assert inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)['scope_snapshot'] == 'UNKNOWN'
    assert not calls
    assert json.loads(path.read_bytes())['collections']['unrelated_synthetic']['note']['body'] == '不要修改雪☃'


def test_project_delete_and_same_id_recreate_does_not_adopt_old_scope(rig):
    project, store, old_identity = initialize(rig)
    path = store.path(rig.nid, rig.scope)
    original_bytes = path.read_bytes()
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    new_identity = project.incarnation(rig.nid)
    assert new_identity != old_identity
    # The old scope document remains physically present but belongs to the
    # former project incarnation; the read must not adopt or rewrite it.
    assert path.read_bytes() == original_bytes
    before = snapshot(rig.root)
    assert inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)['scope_snapshot'] == 'UNKNOWN'
    assert snapshot(rig.root) == before
