"""Original-owner File snapshot observations; these do not establish quota."""
import copy

import pytest

from app.experimental.audio_scope_snapshot import AudioScopeObservationUnavailable, inspect_existing_audio_scope
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig


def committed(rig):
    project = rig.workspace.store
    project.incarnation(rig.nid)
    raw = project.store
    row = candidate()
    row.update(novel_id=rig.nid, scope=copy.deepcopy(rig.scope))
    with raw.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['audio_v2_mix_proposals'] = {row['id']: row}
    return project, raw.path(rig.nid, rig.scope)


def test_existing_file_observation_is_not_a_project_charge(rig):
    project, path = committed(rig)
    previous = path.read_bytes()
    calls = []
    result = inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: calls.append('guard'))
    assert calls == ['guard', 'guard']
    assert result == {'scope_snapshot': 'UNKNOWN', 'audio_row_binding': 'UNVERIFIED',
                      'project_charge_known': False, 'new_write_admission': 'CLOSED'}
    assert path.read_bytes() == previous


def test_missing_scope_is_unavailable_and_never_created(rig):
    project = rig.workspace.store
    project.incarnation(rig.nid)
    with project.store.transaction(rig.nid, rig.scope):
        pass
    path = project.store.path(rig.nid, rig.scope)
    assert not path.exists()
    with pytest.raises(AudioScopeObservationUnavailable):
        inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)
    assert not path.exists()


def test_guard_failure_is_not_wrapped_or_ignored(rig):
    project, path = committed(rig)
    previous = path.read_bytes()
    calls = []
    def guard():
        calls.append(True)
        if len(calls) == 2:
            raise PermissionError('synthetic revoked authority')
    with pytest.raises(PermissionError):
        inspect_existing_audio_scope(project, rig.nid, rig.scope, guard)
    assert path.read_bytes() == previous


def test_changed_second_snapshot_fails_closed(rig, monkeypatch):
    project, path = committed(rig)
    original = project.store._file_snapshot
    seen = []
    def changed(nid, scope):
        raw, row = original(nid, scope)
        seen.append(True)
        if len(seen) == 2:
            return raw + b' ', row
        return raw, row
    monkeypatch.setattr(project.store, '_file_snapshot', changed)
    with pytest.raises(AudioScopeObservationUnavailable):
        inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)
    assert len(seen) == 2 and path.read_bytes()


def test_old_unbound_document_is_not_adopted(rig):
    project = rig.workspace.store
    raw = project.store
    row = candidate()
    row.update(novel_id=rig.nid, scope=copy.deepcopy(rig.scope))
    # The original owner may write a legacy scope without an existing project
    # marker. Creating the marker later must not claim those historical rows.
    with raw.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['audio_v2_mix_proposals'] = {row['id']: row}
    path = raw.path(rig.nid, rig.scope)
    previous = path.read_bytes()
    project.incarnation(rig.nid)
    with pytest.raises(AudioScopeObservationUnavailable):
        inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)
    assert path.read_bytes() == previous


def test_corrupt_committed_scope_is_rejected(rig):
    project, path = committed(rig)
    path.write_bytes(b'{"schema_version":1,')
    with pytest.raises(AudioScopeObservationUnavailable):
        inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None)
    assert path.read_bytes() == b'{"schema_version":1,'
