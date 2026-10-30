"""Independent observations of the first-scope planning boundary."""
import copy
import hashlib
from pathlib import Path

import pytest

from app.experimental.audio_shared_document_measurement import plan_file_scope_first_creation
from app.experimental.store import ExperimentalStore, LIFECYCLE, canonical
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig


def _encoded(doc):
    return canonical(doc).encode('utf-8')


def _candidate_doc(nid, scope):
    doc = ExperimentalStore.empty(nid, scope)
    row = candidate()
    row.update(novel_id=nid, scope=copy.deepcopy(scope))
    doc['collections']['audio_v2_mix_proposals'] = {row['id']: row}
    return doc


def test_real_first_commit_and_reopen_include_owner_lifecycle(rig, monkeypatch):
    import app.experimental.store as source
    store = rig.workspace.store.store
    marker = rig.workspace.store.incarnation(rig.nid)
    target = store.path(rig.nid, rig.scope)
    assert not target.exists()
    captured = []
    replace = source.atomic_write

    def check(path, text):
        if Path(path) == target:
            data = text.encode('utf-8')
            plan = plan_file_scope_first_creation(None, data, rig.nid, rig.scope)
            assert plan['previous_condition'] == 'ABSENT'
            assert plan['first_creation_proof'] == 'REQUIRED'
            assert plan['temporary_reservation_bytes'] == len(data)
            assert source.json.loads(text)[LIFECYCLE]['project_identity'] == marker
            captured.append((data, plan))
        return replace(path, text)

    monkeypatch.setattr(source, 'atomic_write', check)
    with store.transaction(rig.nid, rig.scope) as doc:
        doc['collections'] = _candidate_doc(rig.nid, rig.scope)['collections']
    assert len(captured) == 1
    actual = target.read_bytes()
    assert actual == captured[0][0]
    reopened = ExperimentalStore(store.root, 'file', '')
    assert _encoded(reopened.read(rig.nid, rig.scope)) == actual
    assert hashlib.sha256(actual).hexdigest() == captured[0][1]['replacement_sha256']
    with pytest.raises(ValueError, match='CREATION_REQUIRES_ABSENCE'):
        plan_file_scope_first_creation(actual, actual, rig.nid, rig.scope)


def test_absence_is_not_a_first_creation_proof_after_loss(rig):
    store = rig.workspace.store.store
    rig.workspace.store.incarnation(rig.nid)
    with store.transaction(rig.nid, rig.scope) as doc:
        doc['collections'] = _candidate_doc(rig.nid, rig.scope)['collections']
    target = store.path(rig.nid, rig.scope)
    old = target.read_bytes()
    with pytest.raises(ValueError, match='CREATION_REQUIRES_ABSENCE'):
        plan_file_scope_first_creation(old, old, rig.nid, rig.scope)
    # This is an isolated synthetic fixture, not an application cleanup path.
    target.unlink()
    assert store._file_snapshot(rig.nid, rig.scope)[0] is None
    # The calculator cannot distinguish this loss from first creation; it MUST
    # only return an explicit proof requirement, not grant a commit/admission.
    result = plan_file_scope_first_creation(None, old, rig.nid, rig.scope)
    assert result['first_creation_proof'] == 'REQUIRED'
    assert 'authorized' not in result and 'can_commit' not in result
    assert not target.exists()


def test_empty_first_transaction_and_bad_scope_never_write(rig, monkeypatch):
    import app.experimental.store as source
    store = rig.workspace.store.store
    rig.workspace.store.incarnation(rig.nid)
    target = store.path(rig.nid, rig.scope)
    calls = []
    monkeypatch.setattr(source, 'atomic_write', lambda *args: calls.append(args))
    with store.transaction(rig.nid, rig.scope) as doc:
        result = plan_file_scope_first_creation(None, _encoded(doc), rig.nid, rig.scope)
        assert result['first_creation_proof'] == 'REQUIRED'
        assert result['requires_write'] is False and result['temporary_reservation_bytes'] == 0
    assert not calls and not target.exists()
    bad_scope = {'mode': 'collaboration', 'novel_id': rig.nid, 'workspace_id': 'synthetic'}
    with pytest.raises(ValueError):
        plan_file_scope_first_creation(None, _encoded(ExperimentalStore.empty(rig.nid, bad_scope)), rig.nid, bad_scope)
    assert not calls and not target.exists()
