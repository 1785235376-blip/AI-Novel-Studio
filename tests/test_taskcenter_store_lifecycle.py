"""File original-owner lifecycle proofs, with no schema or legacy adoption.

These tests exercise the real scope writer and real CreativeProjectStore marker,
not a query-owned epoch or fixture-only store. Direct physical edits below are
fault injections, not a supported restoration/anti-replay contract.
"""
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from app.creative.project_store import CreativeProjectStore
from app.experimental.store import (
    ExperimentalStore, LIFECYCLE, OBSERVATION_UNSUPPORTED, OBSERVED_COLLECTION, canonical,
)
from app.storage import atomic_write

pytestmark = pytest.mark.file_backend_only
NID = "lifecycle-book"
SCOPE = {"mode": "local", "novel_id": NID}


def row(rid="job", **changes):
    return {"id": rid, "novel_id": NID, "scope": deepcopy(SCOPE), "version": 1,
            "status": "QUEUED", **changes}


@pytest.fixture
def owner(tmp_path):
    store = ExperimentalStore(tmp_path)
    (tmp_path / "novels" / NID).mkdir(parents=True)
    creative = CreativeProjectStore(store)
    identity = creative.incarnation(NID)
    return store, creative, identity


def seed(store, rows=None):
    with store.transaction(NID, SCOPE) as document:
        document["collections"][OBSERVED_COLLECTION] = rows or {"job": row()}
    return store.capture_committed_collection(NID, SCOPE)


def snapshot(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()
            and not any(part.startswith(".") for part in path.relative_to(root).parts)}


def test_missing_reads_noops_and_failed_writes_never_provision_owner_or_scope(tmp_path):
    store = ExperimentalStore(tmp_path)
    assert store.read(NID, SCOPE) == store.empty(NID, SCOPE)
    with store.transaction(NID, SCOPE):
        pass
    with pytest.raises(RuntimeError):
        with store.transaction(NID, SCOPE) as document:
            document["collections"][OBSERVED_COLLECTION] = {"job": row()}
            raise RuntimeError("rollback")
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE)
    assert not store.path(NID, SCOPE).exists()
    assert not (tmp_path / "novels").exists()


def test_first_real_commit_binds_existing_original_owner_in_same_document(owner):
    store, creative, identity = owner
    before = snapshot(store.root)
    with store.transaction(NID, SCOPE):
        pass
    with pytest.raises(RuntimeError):
        with store.transaction(NID, SCOPE) as document:
            document["collections"][OBSERVED_COLLECTION] = {"job": row()}
            raise RuntimeError("rollback")
    assert snapshot(store.root) == before
    captured = seed(store)
    document = store.read(NID, SCOPE)
    assert captured["project_identity"] == identity
    assert document[LIFECYCLE]["project_identity"] == identity
    assert captured["document_incarnation"] == document[LIFECYCLE]["document_incarnation"]
    assert captured["rows"] == [row()]
    assert captured["row_lifecycles"] == document[LIFECYCLE]["rows"]
    assert set(document[LIFECYCLE]) == {"schema_version", "project_identity", "document_incarnation", "rows"}


@pytest.mark.parametrize("populated", [False, True])
def test_existing_legacy_document_is_never_claimed_even_after_business_writes(owner, populated):
    store, _, _ = owner
    old = store.empty(NID, SCOPE)
    if populated:
        old["collections"][OBSERVED_COLLECTION] = {"old": row("old")}
    atomic_write(store.path(NID, SCOPE), canonical(old))
    before = snapshot(store.root)
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE)
    assert snapshot(store.root) == before
    with store.transaction(NID, SCOPE) as document:
        document["collections"].setdefault(OBSERVED_COLLECTION, {})["new"] = row("new")
    assert LIFECYCLE not in store.read(NID, SCOPE)
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE)


@pytest.mark.parametrize("marker", ["missing", "invalid", "created_during_callback"])
def test_first_commit_without_valid_start_marker_keeps_legacy_behavior(tmp_path, marker):
    store = ExperimentalStore(tmp_path)
    project = tmp_path / "novels" / NID
    project.mkdir(parents=True)
    if marker == "invalid":
        (project / "creative_project_v2.json").write_text('{"schema_version":true}')
    with store.transaction(NID, SCOPE) as document:
        if marker == "created_during_callback":
            CreativeProjectStore(store).incarnation(NID)
        document["collections"][OBSERVED_COLLECTION] = {"job": row()}
    assert LIFECYCLE not in store.read(NID, SCOPE)
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE)
    if marker == "missing":
        assert not (project / "creative_project_v2.json").exists()


def test_new_commit_revalidates_start_project_identity(owner):
    store, creative, original_identity = owner
    marker = store.root / "novels" / NID / "creative_project_v2.json"
    with pytest.raises(ValueError, match="EXPERIMENTAL_PROJECT_OWNER_CHANGED"):
        with store.transaction(NID, SCOPE) as document:
            document["collections"][OBSERVED_COLLECTION] = {"job": row()}
            marker.unlink()
            assert creative.incarnation(NID) != original_identity
    assert not store.path(NID, SCOPE).exists()


def test_protected_scope_cannot_be_adopted_after_same_id_project_recreation(owner):
    store, creative, identity = owner
    original = seed(store)
    marker = store.root / "novels" / NID / "creative_project_v2.json"
    marker.unlink()
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE)
    assert not marker.exists()
    assert creative.incarnation(NID) != identity
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE)
    # Preserve the old raw/offset business contract, without rebinding history.
    with store.transaction(NID, SCOPE) as document:
        document["collections"][OBSERVED_COLLECTION]["new"] = row("new")
    assert store.read(NID, SCOPE)[LIFECYCLE]["project_identity"] == original["project_identity"]
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE)


def test_read_capture_noop_and_original_creative_source_lease_are_read_only(owner):
    store, creative, _ = owner
    expected = seed(store)
    before = snapshot(store.root)
    assert store.read(NID, SCOPE)["collections"][OBSERVED_COLLECTION] == {"job": row()}
    assert store.capture_committed_collection(NID, SCOPE) == expected
    with store.transaction(NID, SCOPE):
        pass
    with creative.existing_owner_only(), creative.source_lease(NID, SCOPE) as view:
        assert view["collections"][OBSERVED_COLLECTION]["job"] == row()
    assert snapshot(store.root) == before


def test_capture_uses_committed_rows_and_proofs_even_inside_other_store_transaction(owner):
    store, _, _ = owner
    committed = seed(store)
    other = ExperimentalStore(store.root)
    with store.transaction(NID, SCOPE) as document:
        document["collections"][OBSERVED_COLLECTION]["job"]["status"] = "RUNNING"
        assert store.read(NID, SCOPE)["collections"][OBSERVED_COLLECTION]["job"]["status"] == "RUNNING"
        assert store.capture_committed_collection(NID, SCOPE) == committed
        assert other.capture_committed_collection(NID, SCOPE) == committed
    current = other.capture_committed_collection(NID, SCOPE)
    assert current["rows"][0]["status"] == "RUNNING"
    assert current["row_lifecycles"] != committed["row_lifecycles"]
    current["rows"][0]["status"] = "COPY_ONLY"
    assert other.capture_committed_collection(NID, SCOPE)["rows"][0]["status"] == "RUNNING"


def test_capture_cannot_see_uncommitted_first_creation(owner):
    store, _, _ = owner
    with store.transaction(NID, SCOPE) as document:
        document["collections"][OBSERVED_COLLECTION] = {"job": row()}
        with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
            store.capture_committed_collection(NID, SCOPE)


def test_row_aba_and_delete_recreate_get_new_random_proofs_without_tombstone_growth(owner):
    store, _, _ = owner
    first = seed(store)
    nonces = [first["row_lifecycles"]["job"]]
    for status in ("RUNNING", "QUEUED"):
        with store.transaction(NID, SCOPE) as document:
            document["collections"][OBSERVED_COLLECTION]["job"]["status"] = status
        captured = store.capture_committed_collection(NID, SCOPE)
        nonces.append(captured["row_lifecycles"]["job"])
    assert captured["rows"] == first["rows"]
    assert len(set(nonces)) == 3
    with store.transaction(NID, SCOPE) as document:
        del document["collections"][OBSERVED_COLLECTION]
    empty = store.capture_committed_collection(NID, SCOPE)
    assert empty["rows"] == [] and empty["row_lifecycles"] == {}
    assert store.read(NID, SCOPE)[LIFECYCLE]["rows"] == {}
    recreated = seed(store)
    assert recreated["rows"] == first["rows"]
    assert recreated["row_lifecycles"]["job"] not in nonces
    assert recreated["document_incarnation"] == first["document_incarnation"]


def test_physical_new_scope_gets_new_document_incarnation(owner):
    store, _, _ = owner
    first = seed(store)
    store.path(NID, SCOPE).unlink()
    second = seed(store)
    assert first["rows"] == second["rows"]
    assert first["document_incarnation"] != second["document_incarnation"]
    assert first["row_lifecycles"] != second["row_lifecycles"]


def test_unselected_collections_and_rows_beyond_window_do_not_change_selected_proofs(owner):
    store, _, _ = owner
    first = seed(store, {f"j{i:03}": row(f"j{i:03}") for i in range(205)})
    with store.transaction(NID, SCOPE) as document:
        document["collections"]["unselected"] = {"secret": {"changed": True}}
    assert store.capture_committed_collection(NID, SCOPE) == first
    with store.transaction(NID, SCOPE) as document:
        document["collections"][OBSERVED_COLLECTION]["j204"]["status"] = "RUNNING"
    second = store.capture_committed_collection(NID, SCOPE)
    assert second["document_incarnation"] == first["document_incarnation"]
    assert second["project_identity"] == first["project_identity"]
    assert second["rows"][:200] == first["rows"][:200]
    assert {k: second["row_lifecycles"][k] for k in list(first["row_lifecycles"])[:200]} == {
        k: first["row_lifecycles"][k] for k in list(first["row_lifecycles"])[:200]}
    assert second["row_lifecycles"]["j204"] != first["row_lifecycles"]["j204"]


def test_original_creative_clear_update_wrapper_preserves_owner_metadata(owner):
    store, creative, _ = owner
    first = seed(store)
    with creative.transaction(NID, SCOPE) as view:
        view["collections"]["another"] = {"x": {"value": 3}}
    assert store.capture_committed_collection(NID, SCOPE) == first
    with creative.transaction(NID, SCOPE) as view:
        view["collections"][OBSERVED_COLLECTION]["job"]["status"] = "RUNNING"
    assert store.capture_committed_collection(NID, SCOPE)["row_lifecycles"] != first["row_lifecycles"]


@pytest.mark.parametrize("change", [
    lambda d: d.pop(LIFECYCLE),
    lambda d: d.update({LIFECYCLE: None}),
    lambda d: d[LIFECYCLE].update(schema_version=True),
    lambda d: d[LIFECYCLE].update(document_incarnation=str(uuid4())),
    lambda d: d[LIFECYCLE].update(project_identity="file:" + str(uuid4())),
    lambda d: d[LIFECYCLE]["rows"].update(job=str(uuid4())),
    lambda d: d[LIFECYCLE]["rows"].clear(),
])
def test_reserved_metadata_mutation_is_rejected_without_any_commit(owner, change):
    store, _, _ = owner
    seed(store)
    before = snapshot(store.root)
    with pytest.raises(ValueError, match="owner-managed"):
        with store.transaction(NID, SCOPE) as document:
            change(document)
    assert snapshot(store.root) == before


def test_forged_metadata_cannot_be_injected_into_new_or_legacy_scope(owner):
    store, _, identity = owner
    forged = {"schema_version": 1, "project_identity": identity,
              "document_incarnation": str(uuid4()), "rows": {}}
    for existing in (False, True):
        if existing:
            atomic_write(store.path(NID, SCOPE), canonical(store.empty(NID, SCOPE)))
        before = snapshot(store.root)
        with pytest.raises(ValueError, match="owner-managed"):
            with store.transaction(NID, SCOPE) as document:
                document[LIFECYCLE] = deepcopy(forged)
        assert snapshot(store.root) == before


@pytest.mark.parametrize("change", [
    lambda m: m.update(schema_version=True),
    lambda m: m.update(schema_version=-1),
    lambda m: m.update(schema_version=2**100),
    lambda m: m.update(schema_version=1.0),
    lambda m: m.update(extra="unknown"),
    lambda m: m.update(project_identity="file:not-a-uuid"),
    lambda m: m.update(document_incarnation="not-a-uuid"),
    lambda m: m.update(document_incarnation=True),
    lambda m: m.update(rows=[]),
    lambda m: m["rows"].update(job="bad-nonce"),
    lambda m: m["rows"].update(unknown=str(uuid4())),
    lambda m: m["rows"].clear(),
])
def test_persisted_metadata_is_strictly_validated_and_never_repaired(owner, change):
    store, _, _ = owner
    seed(store)
    document = store.read(NID, SCOPE)
    change(document[LIFECYCLE])
    atomic_write(store.path(NID, SCOPE), canonical(document))
    before = snapshot(store.root)
    with pytest.raises(ValueError, match="metadata is invalid"):
        store.read(NID, SCOPE)
    with pytest.raises(ValueError, match="metadata is invalid"):
        store.capture_committed_collection(NID, SCOPE)
    with pytest.raises(ValueError, match="metadata is invalid"):
        with store.transaction(NID, SCOPE):
            pass
    assert snapshot(store.root) == before


def test_duplicate_json_keys_are_not_silently_accepted(owner):
    store, _, _ = owner
    seed(store)
    raw = store.path(NID, SCOPE).read_text()
    raw = raw.replace('"schema_version":1', '"schema_version":1,"schema_version":1', 1)
    atomic_write(store.path(NID, SCOPE), raw)
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        store.capture_committed_collection(NID, SCOPE)


@pytest.mark.parametrize("outer_changes", [False, True])
def test_cross_instance_reentrant_commit_cannot_be_overwritten_even_by_noop(owner, outer_changes):
    store, _, _ = owner
    seed(store)
    inner = ExperimentalStore(store.root)
    with pytest.raises(ValueError, match="EXPERIMENTAL_SCOPE_CONCURRENT_WRITE"):
        with store.transaction(NID, SCOPE) as document:
            if outer_changes:
                document["collections"][OBSERVED_COLLECTION]["job"]["status"] = "OUTER"
            with inner.transaction(NID, SCOPE) as other:
                other["collections"][OBSERVED_COLLECTION]["job"]["status"] = "INNER"
    assert store.capture_committed_collection(NID, SCOPE)["rows"][0]["status"] == "INNER"
    with store.transaction(NID, SCOPE):
        pass  # No leaked active state or broken lock after failed CAS.


def test_original_source_lease_detects_other_store_write(owner):
    store, creative, _ = owner
    seed(store)
    other = ExperimentalStore(store.root)
    with pytest.raises(ValueError, match="EXPERIMENTAL_SCOPE_CONCURRENT_WRITE"):
        with creative.source_lease(NID, SCOPE):
            with other.transaction(NID, SCOPE) as document:
                document["collections"][OBSERVED_COLLECTION]["job"]["status"] = "INNER"
    assert store.capture_committed_collection(NID, SCOPE)["rows"][0]["status"] == "INNER"


def test_original_same_instance_nested_write_stays_rejected(owner):
    store, _, _ = owner
    seed(store)
    before = snapshot(store.root)
    with pytest.raises(ValueError, match="nested experimental transaction"):
        with store.transaction(NID, SCOPE):
            with store.transaction(NID, SCOPE):
                pass
    assert snapshot(store.root) == before


def test_physical_cas_checks_existence_and_exact_bytes_even_for_noop(owner):
    store, _, _ = owner
    with pytest.raises(ValueError, match="EXPERIMENTAL_SCOPE_CONCURRENT_WRITE"):
        with store.transaction(NID, SCOPE):
            atomic_write(store.path(NID, SCOPE), canonical(store.empty(NID, SCOPE)))
    with pytest.raises(ValueError, match="EXPERIMENTAL_SCOPE_CONCURRENT_WRITE"):
        with store.transaction(NID, SCOPE):
            path = store.path(NID, SCOPE)
            atomic_write(path, json.dumps(json.loads(path.read_text()), indent=2))
    with pytest.raises(ValueError, match="EXPERIMENTAL_SCOPE_CONCURRENT_WRITE"):
        with store.transaction(NID, SCOPE):
            store.path(NID, SCOPE).unlink()


def test_only_file_local_semantic_import_observation_is_supported(owner):
    store, _, _ = owner
    seed(store)
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, SCOPE, "unselected")
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        ExperimentalStore(store.root, "postgres").capture_committed_collection(NID, SCOPE)
    shared = {"mode": "collaboration", "novel_id": NID,
              "workspace_id": "w", "storyline_id": "s", "branch_id": "b"}
    with store.transaction(NID, shared) as document:
        document["collections"][OBSERVED_COLLECTION] = {"job": row(scope=shared)}
    assert LIFECYCLE not in store.read(NID, shared)
    with pytest.raises(ValueError, match=OBSERVATION_UNSUPPORTED):
        store.capture_committed_collection(NID, shared)


def test_uncommitted_aba_and_failed_protected_mutations_leave_original_proofs(owner, monkeypatch):
    store, _, _ = owner
    first = seed(store)
    before = snapshot(store.root)
    with store.transaction(NID, SCOPE) as document:
        document["collections"][OBSERVED_COLLECTION]["job"]["status"] = "RUNNING"
        document["collections"][OBSERVED_COLLECTION]["job"]["status"] = "QUEUED"
    assert snapshot(store.root) == before
    assert store.capture_committed_collection(NID, SCOPE) == first
    with pytest.raises(ValueError, match="corrupt or scope mismatch"):
        with store.transaction(NID, SCOPE) as document:
            document["collections"][OBSERVED_COLLECTION] = []
    with pytest.raises(RuntimeError, match="business rollback"):
        with store.transaction(NID, SCOPE) as document:
            document["collections"][OBSERVED_COLLECTION]["job"]["status"] = "RUNNING"
            raise RuntimeError("business rollback")
    from app.experimental import store as module
    with monkeypatch.context() as fault:
        def failed_replace(*args, **kwargs):
            raise OSError("injected before atomic commit")
        fault.setattr(module, "atomic_write", failed_replace)
        with pytest.raises(OSError, match="injected before atomic commit"):
            with store.transaction(NID, SCOPE) as document:
                document["collections"][OBSERVED_COLLECTION]["job"]["status"] = "RUNNING"
    assert snapshot(store.root) == before
    assert store.capture_committed_collection(NID, SCOPE) == first


def test_live_nonce_storage_is_bounded_by_live_row_count(owner):
    store, _, _ = owner
    seed(store)
    for index in range(12):
        rid = f"replacement-{index}"
        with store.transaction(NID, SCOPE) as document:
            document["collections"][OBSERVED_COLLECTION] = {rid: row(rid)}
        metadata = store.read(NID, SCOPE)[LIFECYCLE]
        assert set(metadata["rows"]) == {rid}


def test_nonsemantic_first_business_commit_still_has_stable_later_row_identity(owner):
    store, _, identity = owner
    with store.transaction(NID, SCOPE) as document:
        document["collections"]["another_owner"] = {"other": {"value": 1}}
    empty = store.capture_committed_collection(NID, SCOPE)
    assert empty["rows"] == [] and empty["row_lifecycles"] == {}
    assert empty["project_identity"] == identity
    first = seed(store)
    assert first["document_incarnation"] == empty["document_incarnation"]
    assert set(first["row_lifecycles"]) == {"job"}
