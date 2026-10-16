"""Original asset-owner text archival and read-only source lease contracts.

Run with scripts/run_v2_checks.py. The reused original rig supplies File and
PostgreSQL cases; File runs skip the PostgreSQL parameters without connecting.
No model execution or alternate review owner is involved in these tests.
"""
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from test_v2_creative_foundation import rig


TEXT = "A bounded model proposal.\n原始文本。"
STAMP = "2026-10-10T10:00:00+00:00"


@pytest.fixture
def owner(rig, monkeypatch):
    from app.services.asset_library_service import AssetLibraryService
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(AssetLibraryService.TEXT_RESULT_FEATURES))
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    rig.assets = AssetLibraryService(rig.root)
    return rig


def source(text=TEXT):
    return {"schema_version": 1, "contract": "creative-graph-text-asset/1", "graph_id": "graph-1",
        "graph_version": 2, "graph_digest": "a" * 64, "run_id": "run-1", "source_run_version": 4,
        "model_node_id": "model-1", "job_id": "job-1", "input_digest": "b" * 64,
        "output_digest": hashlib.sha256(text.encode()).hexdigest(), "preview_digest": "c" * 64,
        "produced_at": STAMP}


@contextmanager
def lease(owner, scope=None):
    scope = scope or owner.scope
    with owner.service.store.source_lease(owner.nid, scope) as snapshot:
        with owner.assets.project_scope(owner.nid, scope.get("branch_id"),
                lambda: owner.service.store.owner_lease(owner.nid), scope_key=owner.store.key(owner.nid, scope)):
            yield snapshot


def create(owner, **changes):
    kwargs = {"novel_id": owner.nid, "filename": "result.txt", "text": TEXT, "source_receipt": source(),
        "provider_id": "local.provider", "model_id": "local-model", "source_job_id": "job-1",
        "parameters": {"max_output_tokens": 512}, "idempotency_key": "text-result:run-1",
        "branch_id": None, "owner_actor_id": owner.actor,
        "required_features": tuple(owner.assets.TEXT_RESULT_FEATURES), "guard": lambda: None}
    kwargs.update(changes)
    return owner.assets.create_text_result(**kwargs)


def review(owner, row, **changes):
    receipt = {"run_id": "run-1", "run_version": 7, "review_node_id": "review-1",
        "output_digest": source()["output_digest"], "reviewed_output_digest": "d" * 64,
        "reviewed_by": owner.actor, "reviewed_at": STAMP}
    kwargs = {"actor_id": owner.actor, "branch_id": None, "expected_version": row["version"],
        "output_digest": row["sha256"], "status": "APPROVED", "review_receipt": receipt, "guard": lambda: None}
    kwargs.update(changes)
    return owner.assets.review_text_result(row["id"], **kwargs)


def test_first_metadata_commit_is_complete_and_retry_keeps_original_identity(owner, monkeypatch):
    first_writes = []
    write = owner.assets._write_meta
    def capture(meta):
        first_writes.append(copy.deepcopy(meta))
        write(meta)
    monkeypatch.setattr(owner.assets, "_write_meta", capture)
    before = owner.store.read(owner.nid, owner.scope)
    with lease(owner):
        row = create(owner)
        assert row == create(owner)
        assert owner.assets.content(row["id"], actor_id=owner.actor) == TEXT.encode()
    assert len(first_writes) == 1
    assert row["version"] == 1 and row["kind"] == "text" and row["media_type"] == "text/plain"
    assert row["_text_result_origin"] == source()
    assert row["_text_result_review"] == {"status": "DRAFT", "receipt": None, "history": []}
    assert "approved_at" not in row and row["_owner_actor_id"] == owner.actor
    assert row["parameters"] == {"max_output_tokens": 512}
    assert owner.store.read(owner.nid, owner.scope) == before
    assert "_text_result_origin" not in owner.assets.public(row)
    assert "_text_result_review" not in owner.assets.public(row)


def test_concurrent_retry_creates_only_one_original_asset(owner):
    def submit(_):
        with lease(owner):
            return create(owner)["id"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        ids = list(pool.map(submit, range(3)))
    assert len(set(ids)) == 1
    with lease(owner):
        assert len(owner.assets.list(owner.nid, actor_id=owner.actor)) == 1


@pytest.mark.parametrize("changed", ["text", "source", "model", "parameters"])
def test_idempotency_binds_exact_bytes_source_and_model(owner, changed):
    from app.services.asset_library_service import AssetIdempotencyConflict
    with lease(owner):
        original = create(owner)
        changes = {"text": {"text": "Changed", "source_receipt": source("Changed")},
            "source": {"source_receipt": {**source(), "source_run_version": 5}},
            "model": {"model_id": "other-model"}, "parameters": {"parameters": {"max_output_tokens": 1024}}}[changed]
        with pytest.raises(AssetIdempotencyConflict):
            create(owner, **changes)
        assert owner.assets.get(original["id"], actor_id=owner.actor) == original


@pytest.mark.parametrize("after_commit", [False, True])
def test_metadata_write_failure_is_retryable_without_partial_index(owner, monkeypatch, after_commit):
    write = owner.assets._write_meta
    def fail(meta):
        if after_commit:
            write(meta)
        raise OSError("synthetic metadata interruption")
    monkeypatch.setattr(owner.assets, "_write_meta", fail)
    with lease(owner):
        with pytest.raises(OSError):
            create(owner)
        retained = owner.assets.list(owner.nid, actor_id=owner.actor)
        assert len(retained) == int(after_commit)
        assert len(list(owner.assets.root.glob("*.bin"))) == int(after_commit)
        monkeypatch.setattr(owner.assets, "_write_meta", write)
        result = create(owner)
        assert result["version"] == 1 and result["_text_result_origin"] == source()
        if after_commit:
            assert result == retained[0]
        assert not list(owner.assets.root.glob("*.tmp"))


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED"])
def test_review_is_idempotent_cas_projection_and_stays_actor_private(owner, status):
    from app.services.v1_capability_service import CapabilityVersionConflict
    with lease(owner):
        original = create(owner)
        result = review(owner, original, status=status)
        assert result["version"] == 2 and result["_owner_actor_id"] == owner.actor
        assert result["_text_result_origin"] == original["_text_result_origin"]
        assert result["_text_result_review"]["status"] == status
        assert result["_text_result_review"]["history"] == [{"status": "DRAFT", "asset_version": 1}]
        assert ("approved_at" in result) == (status == "APPROVED")
        assert review(owner, original, status=status) == result
        assert create(owner) == result
        assert owner.assets.content(result["id"], actor_id=owner.actor) == TEXT.encode()
        with pytest.raises(FileNotFoundError):
            owner.assets.get(result["id"])
        with pytest.raises(FileNotFoundError):
            owner.assets.get(result["id"], actor_id="other-actor")
        with pytest.raises(CapabilityVersionConflict):
            review(owner, original, status="REJECTED" if status == "APPROVED" else "APPROVED")
        with pytest.raises(ValueError, match="ALREADY_FINAL"):
            review(owner, result, status="REJECTED" if status == "APPROVED" else "APPROVED")


@pytest.mark.parametrize("field,value", [("source_job_id", "forged-job"), ("provider_id", "forged-provider"),
    ("model_id", "forged-model"), ("parameters", {"max_output_tokens": 1}), ("approved_at", STAMP),
    ("source_asset_ids", [])])
def test_generic_metadata_cannot_rewrite_text_provenance(owner, field, value):
    with lease(owner):
        row = create(owner)
        with pytest.raises(ValueError, match="PROVENANCE_IMMUTABLE"):
            owner.assets.update_metadata(row["id"], {field: value}, actor_id=owner.actor, expected_version=1)
        assert owner.assets.get(row["id"], actor_id=owner.actor) == row
        with pytest.raises(ValueError, match="PRIVATE_OWNER_REQUIRED"):
            owner.assets.promote_owned(row["id"], actor_id=owner.actor, branch_id=None,
                expected_version=1, provenance={})


def test_authority_guards_abort_create_review_and_retry(owner):
    def denied():
        raise PermissionError("synthetic revocation")
    with lease(owner):
        with pytest.raises(PermissionError):
            create(owner, guard=denied)
        assert not owner.assets.list(owner.nid, actor_id=owner.actor)
        row = create(owner)
        with pytest.raises(PermissionError):
            create(owner, guard=denied)
        with pytest.raises(PermissionError):
            review(owner, row, guard=denied)
        assert owner.assets.get(row["id"], actor_id=owner.actor) == row


@pytest.mark.parametrize("changes", [{"source_receipt": {**source(), "extra": "untrusted"}},
    {"source_receipt": {**source(), "source_run_version": True}},
    {"source_receipt": {**source(), "produced_at": "2026-10-10T10:00:00"}},
    {"source_receipt": {**source(), "output_digest": "f" * 64}}, {"source_job_id": "other-job"},
    {"text": " "}, {"text": "x\x00y"}, {"text": "文" * 10_667},
    {"parameters": {"number": float("nan")}}, {"parameters": {"asset_lineage_v2": {}}},
    {"owner_actor_id": None}, {"guard": None}, {"idempotency_key": ""}])
def test_closed_source_receipt_and_bounded_text(owner, changes):
    with lease(owner):
        with pytest.raises(ValueError):
            create(owner, **changes)
        assert not owner.assets.list(owner.nid, actor_id=owner.actor)


def test_review_distinguishes_bytes_digest_and_review_digest(owner):
    with lease(owner):
        row = create(owner)
        with pytest.raises(ValueError, match="BINDING_INVALID"):
            review(owner, row, output_digest="d" * 64)
        result = review(owner, row)
        receipt = result["_text_result_review"]["receipt"]
        assert receipt["output_digest"] == row["sha256"]
        assert receipt["reviewed_output_digest"] == "d" * 64
        assert receipt["reviewed_output_digest"] != receipt["output_digest"]


def test_text_results_require_scope_and_do_not_leak_to_other_scopes(owner, monkeypatch):
    with pytest.raises(ValueError, match="BINDING_REQUIRED"):
        create(owner)
    with lease(owner):
        row = create(owner)
    with pytest.raises(FileNotFoundError):
        owner.assets.get(row["id"], actor_id=owner.actor)
    other_scope = {"mode": "collaboration", "novel_id": owner.nid, "workspace_id": "workspace",
        "storyline_id": "storyline", "branch_id": "branch"}
    with lease(owner, other_scope):
        with pytest.raises(FileNotFoundError):
            owner.assets.get(row["id"], branch_id="branch", actor_id=owner.actor)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    with lease(owner):
        with pytest.raises(FileNotFoundError):
            owner.assets.get(row["id"], actor_id=owner.actor)


@pytest.mark.parametrize("target", ["view", "raw"])
def test_source_lease_rejects_scope_mutation_and_preserves_original(owner, target):
    with owner.store.transaction(owner.nid, owner.scope) as original:
        original["collections"]["existing-domain"] = {"retained": {"nested": [1, 2]}}
    before = owner.store.read(owner.nid, owner.scope)
    with pytest.raises(ValueError, match="SOURCE_LEASE_MUTATION_DENIED"):
        with owner.service.store.source_lease(owner.nid, owner.scope) as view:
            selected = view if target == "view" else owner.store._local.active[owner.store.key(owner.nid, owner.scope)]
            selected["collections"]["existing-domain"]["retained"]["nested"].append(3)
    assert owner.store.read(owner.nid, owner.scope) == before


def test_source_lease_allows_snapshot_reads_but_rejects_nested_and_inverted_order(owner):
    with lease(owner) as view:
        assert owner.store.read(owner.nid, owner.scope) == view
        with pytest.raises(ValueError, match="NESTED_OR_ORDER"):
            with owner.service.store.source_lease(owner.nid, owner.scope):
                pass
        with pytest.raises(ValueError, match="nested experimental"):
            with owner.service.store.transaction(owner.nid, owner.scope):
                pass
    with owner.service.store.transaction(owner.nid, owner.scope):
        with pytest.raises(ValueError, match="NESTED_OR_ORDER"):
            with owner.service.store.source_lease(owner.nid, owner.scope):
                pass
    with owner.service.store.owner_lease(owner.nid):
        with pytest.raises(ValueError, match="NESTED_OR_ORDER"):
            with owner.service.store.source_lease(owner.nid, owner.scope):
                pass


def test_recreated_owner_cannot_adopt_old_text_result(owner):
    with lease(owner):
        original = create(owner)
    owner.novels.delete(owner.nid)
    owner.novels.create({"id": owner.nid, "title": "Replacement synthetic owner"})
    with lease(owner):
        with pytest.raises(FileNotFoundError):
            owner.assets.get(original["id"], actor_id=owner.actor)
        replacement = create(owner)
        assert replacement["id"] != original["id"]
        assert replacement["_project_binding"] != original["_project_binding"]
        assert owner.assets.project_usage(owner.nid) == {"count": 1, "bytes": len(TEXT.encode())}
    assert json.loads(owner.assets._meta_path(original["id"]).read_text()) == original


def test_project_usage_includes_other_actors_deleted_and_disabled_features(owner, monkeypatch):
    with pytest.raises(ValueError, match="BINDING_REQUIRED"):
        owner.assets.project_usage(owner.nid)
    with lease(owner):
        create(owner)
        hidden = create(owner, owner_actor_id="other-author")
        assert len(owner.assets.list(owner.nid, actor_id=owner.actor)) == 1
        hidden.update(deleted_at=STAMP, version=2)
        owner.assets._write_meta(hidden)
        assert owner.assets.project_usage(owner.nid) == {"count": 2, "bytes": 2 * len(TEXT.encode())}
    branch = {"mode": "collaboration", "novel_id": owner.nid, "workspace_id": "workspace",
        "storyline_id": "storyline", "branch_id": "branch"}
    with lease(owner, branch):
        create(owner, branch_id="branch")
        assert owner.assets.project_usage(owner.nid, branch_id="branch")["count"] == 1
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    with lease(owner):
        assert owner.assets.list(owner.nid, actor_id=owner.actor) == []
        assert owner.assets.project_usage(owner.nid) == {"count": 2, "bytes": 2 * len(TEXT.encode())}
