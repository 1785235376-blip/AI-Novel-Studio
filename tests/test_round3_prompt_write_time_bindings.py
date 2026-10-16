"""Additive R3 binding verification against original File/PostgreSQL owners.

The imported fixture creates real repository bundles and refuses PostgreSQL fallback.
Existing frozen R3 tests are neither changed nor copied into another owner harness.
"""
from __future__ import annotations

import base64
import copy
import threading
from uuid import uuid4

import pytest

from app.creative import prompt_asset as prompt
from app.creative.prompt_authoring_models import PromptCreateIn
from app.experimental.store import canonical
from test_round3i_prompt_adoption import rig, _storyboard, _body


def _asset(rig, *, actor=None, nid=None, branch=None):
    nid = nid or rig.nid
    scope = {"mode": "local", "novel_id": nid}
    if branch is not None:
        scope["branch_id"] = branch
    with rig.workspace._asset_scope(nid, scope):
        return rig.assets.create(nid, "synthetic.txt", base64.b64encode(b"source bytes").decode(),
                                 kind="text", branch_id=branch, owner_actor_id=actor)


def _prompt(rig, **bindings):
    output_ids = bindings.pop("output_asset_ids", [])
    if output_ids:
        # Imported prompts also have output bindings. Use the original generic asset
        # creation path before its first immutable payload, never bypass an immutable edit.
        with rig.workspace._asset_scope(rig.nid, rig.scope):
            asset = rig.assets.create(rig.nid, "imported.prompt.txt",
                base64.b64encode("绑定正文 🙂".encode()).decode(), kind="prompt",
                owner_actor_id=rig.actor)
            payload = prompt.build_payload(family_id=uuid4().hex, revision=1, purpose="IMAGE", origin="IMPORTED",
                output_asset_ids=output_ids, **bindings)
            asset = rig.assets.update_metadata(asset["id"], {"parameters": {"prompt": payload}},
                                              expected_version=asset["version"], actor_id=rig.actor)
            receipt = {"family_id": payload["family_id"], "asset_id": asset["id"],
                       "asset_version": asset["version"], "revision": 1}
    else:
        receipt = rig.authoring.create(rig.nid, rig.scope, rig.actor,
            PromptCreateIn(text="绑定正文 🙂", request_id=uuid4().hex, **bindings))
    rig.authoring.approve(rig.nid, rig.scope, rig.actor, receipt["family_id"],
                          receipt["asset_id"], receipt["asset_version"])
    body = rig.library.revision_body(rig.nid, rig.scope, receipt["family_id"],
                                     receipt["asset_id"], rig.actor)
    return receipt, body


def _adopt(rig, board, shot_id, receipt, body, **kwargs):
    request = _body(rig, board, receipt, body, shot_id)
    return rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, board["id"],
                                     shot_id, request, **kwargs)


def _unchanged(rig, before):
    assert rig.creative.get(rig.nid, rig.scope, before["id"]) == before


def test_empty_binding_set_is_verified_without_entering_an_aggregate_projection(rig, monkeypatch):
    board, shot_id = _storyboard(rig)
    receipt, body = _prompt(rig)
    monkeypatch.setattr(rig.library, "_bible_indices", lambda *a, **k: pytest.fail("nested aggregate"))
    result = _adopt(rig, board, shot_id, receipt, body)
    proof = result["adoption"]
    assert result["committed"] is True
    assert proof["source_binding_contract"] == "prompt-adoption-bindings/1"
    assert proof["source_bindings_verified"] is True
    assert proof["source_snapshot"] == []


def test_all_binding_kinds_capture_real_owner_snapshots_at_commit(rig):
    board, shot_id = _storyboard(rig)
    novels = rig.workspace.novels
    character = novels.upsert_character(rig.nid, "author-character", {"name": "合成人物"})
    location = novels.upsert_location(rig.nid, "author-location", {"name": "合成地点"})
    reference = _asset(rig, actor=rig.actor)
    receipt, body = _prompt(rig, character_ids=[character["id"]], scene_ids=[location["id"]],
                           shot_ids=[shot_id], reference_asset_ids=[reference["id"]])
    result = _adopt(rig, board, shot_id, receipt, body)
    persisted = rig.creative.get(rig.nid, rig.scope, board["id"])
    proof = persisted["prompt_adoptions"][-1]
    assert proof == result["adoption"]
    snapshots = {row["kind"]: row for row in proof["source_snapshot"]}
    assert set(snapshots) == {"CHARACTER", "SCENE", "SHOT", "ASSET"}
    assert snapshots["CHARACTER"]["digest"] == prompt.digest(canonical(novels.data_set(rig.nid, "characters")[0]))
    assert snapshots["SCENE"]["digest"] == prompt.digest(canonical(novels.data_set(rig.nid, "locations")[0]))
    assert snapshots["SHOT"]["document_id"] == board["id"]
    assert snapshots["SHOT"]["version"] == board["version"]
    assert snapshots["ASSET"]["asset_digest"] == reference["sha256"]
    assert snapshots["ASSET"]["role"] == "reference_asset_ids"
    assert all(row["verification"] == "WRITE_TIME_OWNER_LEASE" for row in snapshots.values())
    assert all(row["project_incarnation"] == rig.workspace.store.incarnation(rig.nid)
               for row in snapshots.values())
    assert "合成人物" not in str(proof) and "合成地点" not in str(proof)
    assert not any("job" in name.lower() for name in rig.store.read(rig.nid, rig.scope)["collections"])


@pytest.mark.parametrize("field", ["character_ids", "scene_ids", "shot_ids", "reference_asset_ids", "output_asset_ids"])
def test_a_missing_declared_binding_refuses_without_a_document_revision(rig, field):
    board, shot_id = _storyboard(rig)
    receipt, body = _prompt(rig, **{field: ["missing-private-identifier"]})
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_UNAVAILABLE$"):
        _adopt(rig, board, shot_id, receipt, body)
    _unchanged(rig, board)


def test_a_shot_id_in_another_document_cannot_satisfy_the_binding(rig):
    board, shot_id = _storyboard(rig)
    other, other_shot = _storyboard(rig, action="另一文档")
    assert other["id"] != board["id"] and other_shot != shot_id
    receipt, body = _prompt(rig, shot_ids=[other_shot])
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_UNAVAILABLE$"):
        _adopt(rig, board, shot_id, receipt, body)
    _unchanged(rig, board)


def test_canonical_shot_number_binding_uses_the_existing_document_scoped_index(rig):
    board, shot_id = _storyboard(rig)
    other, _other_shot = _storyboard(rig, action="另一文档也有镜头一")
    assert board["shots"][0]["number"] == other["shots"][0]["number"] == 1
    key = f"{board['id']}:1"
    receipt, body = _prompt(rig, shot_ids=[key])
    result = _adopt(rig, board, shot_id, receipt, body)
    snapshot = result["adoption"]["source_snapshot"][0]
    assert snapshot["id"] == snapshot["shot_key"] == key
    assert snapshot["shot_id"] == shot_id and snapshot["document_id"] == board["id"]


def test_other_document_same_shot_number_cannot_satisfy_a_canonical_binding(rig):
    board, shot_id = _storyboard(rig)
    other, _other_shot = _storyboard(rig, action="相同镜号的其他文档")
    receipt, body = _prompt(rig, shot_ids=[f"{other['id']}:1"])
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_UNAVAILABLE$"):
        _adopt(rig, board, shot_id, receipt, body)
    _unchanged(rig, board)


@pytest.mark.parametrize("canonical_key", [True, False])
def test_duplicate_shot_numbers_are_not_silently_collapsed_by_the_index(rig, canonical_key):
    board, shot_id = _storyboard(rig)
    # Persisted corruption fixture: two distinct owner identities carrying number 1.
    with rig.creative.store.transaction(rig.nid, rig.scope) as state:
        row = state["collections"][rig.creative.COLLECTION][board["id"]]
        row["shots"].append({**copy.deepcopy(row["shots"][0]), "id": "duplicate-number-identity"})
        board = copy.deepcopy(row)
    # The normal document reader independently refuses this corrupted owner state.
    with pytest.raises(ValueError, match="^CREATIVE_DOCUMENT_CORRUPT$"):
        rig.creative.get(rig.nid, rig.scope, board["id"])
    receipt, body = _prompt(rig, shot_ids=[f"{board['id']}:1" if canonical_key else shot_id])
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_UNAVAILABLE$"):
        _adopt(rig, board, shot_id, receipt, body)
    retained = rig.creative.store.read(rig.nid, rig.scope)["collections"][rig.creative.COLLECTION][board["id"]]
    assert retained == board and not retained.get("prompt_adoptions")


@pytest.mark.parametrize("kind,field", [("character", "character_ids"), ("location", "scene_ids")])
@pytest.mark.parametrize("restriction", [{"branch_id": "other-branch"}, {"is_archived": True}])
def test_story_bindings_respect_original_branch_and_archival_markers(rig, kind, field, restriction):
    board, shot_id = _storyboard(rig)
    owner = getattr(rig.workspace.novels, "upsert_" + kind)
    record = owner(rig.nid, "unavailable-story-record", {"name": "隔离记录", **restriction})
    receipt, body = _prompt(rig, **{field: [record["id"]]})
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_UNAVAILABLE$"):
        _adopt(rig, board, shot_id, receipt, body)
    _unchanged(rig, board)


@pytest.mark.parametrize("case", ["private-other-actor", "foreign-project", "foreign-branch", "deleted", "corrupt-bytes"])
def test_unavailable_asset_bindings_never_leak_or_commit(rig, case):
    board, shot_id = _storyboard(rig)
    if case == "foreign-project":
        other_nid = "other-" + uuid4().hex
        rig.workspace.novels.create({"id": other_nid, "title": "隔离项目"})
        reference = _asset(rig, nid=other_nid)
    else:
        reference = _asset(rig, actor="other-author" if case == "private-other-actor" else None,
                           branch="foreign-branch" if case == "foreign-branch" else None)
    if case == "deleted":
        with rig.workspace._asset_scope(rig.nid, rig.scope):
            rig.assets.delete(reference["id"])
    if case == "corrupt-bytes":
        # Real damaged source bytes; production owner must refuse, not trust its metadata.
        rig.assets._bin_path(reference["id"]).write_bytes(b"damaged")
    receipt, body = _prompt(rig, reference_asset_ids=[reference["id"]])
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_UNAVAILABLE$") as caught:
        _adopt(rig, board, shot_id, receipt, body)
    assert reference["id"] not in str(caught.value)
    _unchanged(rig, board)


def test_imported_output_assets_are_verified_with_their_distinct_role(rig):
    board, shot_id = _storyboard(rig)
    reference = _asset(rig)
    receipt, body = _prompt(rig, reference_asset_ids=[reference["id"]], output_asset_ids=[reference["id"]])
    result = _adopt(rig, board, shot_id, receipt, body)
    snapshots = result["adoption"]["source_snapshot"]
    assert len(snapshots) == 2
    assert {row["role"] for row in snapshots} == {"reference_asset_ids", "output_asset_ids"}
    assert all(row["asset_digest"] == reference["sha256"] for row in snapshots)


def test_a_binding_removed_since_the_read_is_rechecked_at_the_write(rig):
    board, shot_id = _storyboard(rig)
    reference = _asset(rig)
    receipt, body = _prompt(rig, reference_asset_ids=[reference["id"]])
    assert rig.library.detail(rig.nid, rig.scope, receipt["family_id"], rig.actor)["bindings"]["assets"][0]["resolution"] == "KNOWN"
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(reference["id"])
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_UNAVAILABLE$"):
        _adopt(rig, board, shot_id, receipt, body)
    _unchanged(rig, board)


def test_a_guard_failure_after_bindings_does_not_publish_the_proof(rig, monkeypatch):
    board, shot_id = _storyboard(rig)
    reference = _asset(rig)
    receipt, body = _prompt(rig, reference_asset_ids=[reference["id"]])
    original = rig.adoption._write_time_bindings
    verified = False

    def bindings(*args, **kwargs):
        nonlocal verified
        value = original(*args, **kwargs)
        verified = True
        return value

    monkeypatch.setattr(rig.adoption, "_write_time_bindings", bindings)

    def guard():
        if verified:
            raise PermissionError("AUTHORITY_REVOKED")

    with pytest.raises(PermissionError, match="AUTHORITY_REVOKED"):
        _adopt(rig, board, shot_id, receipt, body, guard=guard)
    _unchanged(rig, board)


def test_original_story_record_writer_waits_until_the_adoption_commit(rig, monkeypatch):
    board, shot_id = _storyboard(rig)
    novels = rig.workspace.novels
    character = novels.upsert_character(rig.nid, "leased-character", {"name": "写入前"})
    original_record = copy.deepcopy(novels.data_set(rig.nid, "characters")[0])
    receipt, body = _prompt(rig, character_ids=[character["id"]])
    read_done, release, writer_started, writer_done = (threading.Event() for _ in range(4))
    original = rig.adoption._write_time_bindings
    outcomes = {}

    def bindings(*args, **kwargs):
        result = original(*args, **kwargs)
        read_done.set()  # Only signals AFTER original owners were read inside the phase.
        assert release.wait(20), "test failed to release the phase"
        return result

    monkeypatch.setattr(rig.adoption, "_write_time_bindings", bindings)

    def adoption():
        try:
            outcomes["adoption"] = _adopt(rig, board, shot_id, receipt, body)
        except Exception as exc:
            outcomes["adoption_error"] = exc

    def writer():
        writer_started.set()
        try:
            outcomes["writer"] = novels.upsert_character(rig.nid, character["id"], {"name": "写入后"})
        except Exception as exc:
            outcomes["writer_error"] = exc
        finally:
            writer_done.set()

    workers = [threading.Thread(target=adoption, daemon=True), threading.Thread(target=writer, daemon=True)]
    try:
        workers[0].start()
        assert read_done.wait(20), "adoption did not reach binding verification"
        workers[1].start()
        assert writer_started.wait(10)
        assert not writer_done.wait(0.3), "original writer crossed the owner lease"
    finally:
        release.set()
        for worker in workers:
            if worker.ident is not None:
                worker.join(25)
    assert not any(worker.is_alive() for worker in workers), "owner lock order deadlocked"
    assert "adoption_error" not in outcomes, outcomes
    assert "writer_error" not in outcomes, outcomes
    assert outcomes["adoption"]["committed"] is True
    snapshot = outcomes["adoption"]["adoption"]["source_snapshot"][0]
    assert snapshot["digest"] == prompt.digest(canonical(original_record))
    assert snapshot["digest"] != prompt.digest(canonical(novels.data_set(rig.nid, "characters")[0]))
    assert novels.data_set(rig.nid, "characters")[0]["name"] == "写入后"


def test_production_adoption_switch_stays_closed():
    from app.creative.prompt_adoption_api import PROMPT_ADOPTION_WRITE_ENABLED
    assert PROMPT_ADOPTION_WRITE_ENABLED is False


def test_binding_resolution_cannot_escape_the_shared_phase(rig):
    board, _shot_id = _storyboard(rig)
    payload = prompt.build_payload(family_id=uuid4().hex, revision=1, purpose="IMAGE", origin="MANUAL")
    with pytest.raises(ValueError, match="^PROMPT_ADOPTION_BINDING_PHASE_REQUIRED$"):
        rig.adoption._write_time_bindings(rig.nid, rig.scope, rig.actor, board, payload, lambda: None)
