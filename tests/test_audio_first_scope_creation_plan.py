"""First File scope creation byte planning, without reservation or authority."""
import copy
import hashlib
from pathlib import Path

import pytest

from app.experimental.audio_shared_document_measurement import (
    plan_file_scope_first_creation,
    plan_file_scope_replacement,
)
from app.experimental.store import ExperimentalStore, LIFECYCLE, canonical
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig

NID = 'synthetic-project'
SCOPE = {'mode': 'local', 'novel_id': NID}
COLLECTION = 'audio_v2_mix_proposals'


def encode(doc):
    return canonical(doc).encode('utf-8')


def doc_with_candidate(nid=NID, scope=SCOPE):
    doc = ExperimentalStore.empty(nid, scope)
    row = candidate()
    row.update(novel_id=nid, scope=copy.deepcopy(scope))
    doc['collections'][COLLECTION] = {row['id']: row}
    return doc


def test_first_creation_plan_requires_separate_absence_and_project_proofs():
    doc = doc_with_candidate()
    raw = encode(doc)
    result = plan_file_scope_first_creation(None, raw, NID, SCOPE)
    field = ('"' + COLLECTION + '":').encode() + encode(doc['collections'][COLLECTION])
    assert result['previous_condition'] == 'ABSENT'
    assert result['first_creation_proof'] == 'REQUIRED'
    assert result['previous_sha256'] is None
    assert result['replacement_sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['previous_candidate_bytes'] == 0
    assert result['replacement_candidate_bytes'] == result['persistent_candidate_delta'] == len(field)
    assert result['requires_write'] is True
    assert result['temporary_reservation_bytes'] == len(raw)


def test_noop_on_initial_empty_document_does_not_reserve():
    empty = encode(ExperimentalStore.empty(NID, SCOPE))
    result = plan_file_scope_first_creation(None, empty, NID, SCOPE)
    assert result['requires_write'] is False
    assert result['persistent_candidate_delta'] == 0
    assert result['temporary_reservation_bytes'] == 0
    assert result['previous_condition'] == 'ABSENT'
    assert result['first_creation_proof'] == 'REQUIRED'


def test_unrelated_first_write_reserves_whole_document_but_no_audio():
    doc = ExperimentalStore.empty(NID, SCOPE)
    doc['collections']['unrelated'] = {'item': {'content': '合成内容雪'}}
    raw = encode(doc)
    result = plan_file_scope_first_creation(None, raw, NID, SCOPE)
    assert result['requires_write'] is True
    assert result['persistent_candidate_delta'] == 0
    assert result['temporary_reservation_bytes'] == len(raw)


@pytest.mark.parametrize('previous', [b'', b'not-json', b'{}'])
def test_existing_or_invalid_source_is_never_reinterpreted_as_absence(previous):
    raw = encode(doc_with_candidate())
    with pytest.raises(ValueError, match='CREATION_REQUIRES_ABSENCE'):
        plan_file_scope_first_creation(previous, raw, NID, SCOPE)


def test_existing_replacement_contract_still_rejects_missing_old_document():
    raw = encode(doc_with_candidate())
    with pytest.raises(ValueError, match='MEASUREMENT_UNAVAILABLE'):
        plan_file_scope_replacement(None, raw, NID, SCOPE)


@pytest.mark.parametrize('fault', ['corrupt', 'wrong_project', 'wrong_scope', 'unsupported_scope'])
def test_bad_first_document_or_scope_is_not_measured(fault):
    doc = doc_with_candidate()
    scope = SCOPE
    if fault == 'wrong_project':
        doc['novel_id'] = 'wrong'
    elif fault == 'wrong_scope':
        doc['scope'] = {'mode': 'local', 'novel_id': 'wrong'}
    elif fault == 'unsupported_scope':
        scope = {'mode': 'unsupported', 'novel_id': NID}
    raw = encode(doc)
    if fault == 'corrupt':
        raw += b'\xff'
    with pytest.raises(ValueError):
        plan_file_scope_first_creation(None, raw, NID, scope)


def test_real_first_commit_measures_final_lifecycle_bytes(rig, monkeypatch):
    import app.experimental.store as store_module

    owner = rig.workspace.store.store
    # Force the real original project identity before the first scope write so
    # its commit adds lifecycle metadata after the user callback completes.
    incarnation = rig.workspace.store.incarnation(rig.nid)
    path = owner.path(rig.nid, rig.scope)
    assert owner._file_snapshot(rig.nid, rig.scope)[0] is None
    assert not path.exists()
    candidate_doc = doc_with_candidate(rig.nid, rig.scope)
    captured = []
    original_atomic_write = store_module.atomic_write

    def observe_final(target, text):
        if Path(target) == path:
            assert owner._file_snapshot(rig.nid, rig.scope)[0] is None
            final_doc = store_module.json.loads(text)
            assert final_doc[LIFECYCLE]['project_identity'] == incarnation
            final = text.encode('utf-8')
            plan = plan_file_scope_first_creation(None, final, rig.nid, rig.scope)
            assert plan['previous_condition'] == 'ABSENT'
            assert plan['first_creation_proof'] == 'REQUIRED'
            assert plan['temporary_reservation_bytes'] == len(final)
            captured.append((final, plan))
        return original_atomic_write(target, text)

    monkeypatch.setattr(store_module, 'atomic_write', observe_final)
    with owner.transaction(rig.nid, rig.scope) as active:
        active['collections'] = copy.deepcopy(candidate_doc['collections'])
        # Lifecycle metadata has not been advanced in the yielded callback.
        assert LIFECYCLE not in active
    assert len(captured) == 1
    assert path.read_bytes() == captured[0][0]
    assert captured[0][1]['replacement_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert owner._file_snapshot(rig.nid, rig.scope)[0] == captured[0][0]


def test_real_first_empty_transaction_does_not_create_scope_document(rig, monkeypatch):
    import app.experimental.store as store_module
    owner = rig.workspace.store.store
    rig.workspace.store.incarnation(rig.nid)
    path = owner.path(rig.nid, rig.scope)
    called = []
    monkeypatch.setattr(store_module, 'atomic_write', lambda *args: called.append(args))
    with owner.transaction(rig.nid, rig.scope) as doc:
        raw = encode(doc)
        plan = plan_file_scope_first_creation(None, raw, rig.nid, rig.scope)
        assert plan['requires_write'] is False
        assert plan['temporary_reservation_bytes'] == 0
    assert not called and not path.exists()
