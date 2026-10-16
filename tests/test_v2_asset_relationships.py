"""M1 descriptive links on real asset/manuscript/screenplay owners.

Use the owned V2 runner for File and genuine PostgreSQL. Media helpers decode
real local PNGs, and all persistence/authority owners are the production ones.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from threading import Barrier
from uuid import uuid4

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace import (
    rig, decoders, import_asset, upload, declaration, png_bytes, reopened,
    stored_asset, asset_files, branch_scope, assert_public,
)
from test_v2_independent_workspace_api import client, upload_body


KINDS = ("SOURCE_OF", "DERIVED_FROM", "REFERENCES", "USED_IN", "ALTERNATE_VERSION", "APPROVED_FOR", "LINKED_CONTEXT")
KEY = "asset_relationships_v2"


def target_for(service, nid, scope, kind, rid):
    candidates = service.relationships.references(nid, scope, kind)
    row = next(row for row in candidates["items"] if row["id"] == rid)
    return {key: row[key] for key in ("kind", "id", "version", "digest")}


def body(row, target, kind="REFERENCES", reason="Explicit author reference"):
    return {"expected_version": row["version"], "type": kind, "target": copy.deepcopy(target), "reason": reason}


def add(rig, row, target, kind="REFERENCES", *, service=None, scope=None, guard=lambda: None):
    return (service or rig.service).relationships.add(
        rig.nid, scope or rig.scope, rig.actor, row["id"], body(row, target, kind), guard)


@pytest.fixture
def originals(rig):
    from app.services.screenplay_service import ScreenplayService
    screenplays = ScreenplayService(rig.bundle.novels, rig.bundle.chapters)
    rig.service.lineage.media.screenplays = screenplays
    chapter = rig.chapters.create(rig.nid, {"title": "Manuscript source", "content": "PRIVATE_MANUSCRIPT_BODY_65ad"})
    chapter = rig.chapters.get(chapter["id"])
    screenplay = screenplays.create(rig.nid, "Original legacy screenplay")
    screenplay["scenes"][0]["action"] = "PRIVATE_SCREENPLAY_ACTION_73ce"
    screenplay = screenplays._save_screenplay(rig.nid, screenplay)
    return chapter, screenplay, screenplays


@pytest.mark.parametrize("kind", KINDS)
def test_all_seven_relationship_kinds_are_versioned_declarations_on_original_assets(rig, decoders, kind):
    source, target = import_asset(rig), import_asset(rig)
    if kind == "SOURCE_OF":
        target = rig.service.annotate(rig.nid, rig.scope, rig.actor, target["id"], declaration(1, [source["id"]]))
    elif kind == "DERIVED_FROM":
        source = rig.service.annotate(rig.nid, rig.scope, rig.actor, source["id"], declaration(1, [target["id"]]))
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    before_scope = rig.raw_store.read(rig.nid, rig.scope)
    before_target = stored_asset(rig, target["id"])
    result = add(rig, source, reference, kind)
    assert result["version"] == source["version"] + 1
    assert len(result["relationships"]) == 1
    relation = result["relationships"][0]
    assert relation["type"] == kind and relation["state"] == "CURRENT"
    assert relation["expected"] == reference
    assert relation["created_by"] == rig.actor
    assert relation["semantics"] == "DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION"
    stored = stored_asset(rig, source["id"])
    assert stored["parameters"][KEY]["schema_version"] == 1
    assert stored["parameters"][KEY]["items"][0]["target"] == reference
    assert stored["parameters"][KEY]["items"][0]["removed_at"] is None
    assert KEY not in result.get("parameters", {})
    assert_public(result)
    assert stored_asset(rig, target["id"]) == before_target
    assert rig.raw_store.read(rig.nid, rig.scope) == before_scope
    assert rig.service.download(rig.nid, rig.scope, source["id"])[1] == png_bytes()
    assert len(rig.service.list_assets(rig.nid, rig.scope)["items"]) == 2
    assert reopened(rig).asset(rig.nid, rig.scope, source["id"]) == result


@pytest.mark.parametrize("target_kind", ["ASSET", "CHAPTER", "SCREENPLAY"])
def test_references_capture_exact_owner_version_digest_without_copying_or_editing_text(rig, decoders, originals, target_kind):
    from app.experimental.store import canonical
    from app.source_privacy import content_digest
    chapter, screenplay, screenplays = originals
    source, target_asset = import_asset(rig), import_asset(rig)
    before_chapter = rig.chapters.get(chapter["id"])
    before_screenplay = copy.deepcopy(screenplays.list(rig.nid))
    owner = {"ASSET": target_asset, "CHAPTER": chapter, "SCREENPLAY": screenplay}[target_kind]
    reference = target_for(rig.service, rig.nid, rig.scope, target_kind, owner["id"])
    if target_kind == "ASSET":
        assert reference["version"] == owner["version"] and reference["digest"] == owner["sha256"]
    elif target_kind == "CHAPTER":
        assert reference["version"] == owner["version"] and reference["digest"] == content_digest(owner)
    else:
        assert reference["version"] == owner["edit_version"]
        assert reference["digest"] == hashlib.sha256(canonical({key: value for key, value in owner.items()
                                                               if key != "version_history"}).encode()).hexdigest()
    candidates = rig.service.relationships.references(rig.nid, rig.scope, target_kind)
    assert candidates["read_only"] is True and candidates["content_copied"] is False
    linked = add(rig, source, reference, "LINKED_CONTEXT")
    graph = rig.service.relationships.graph(rig.nid, rig.scope)
    exported = json.dumps([candidates, linked, graph, stored_asset(rig, source["id"])])
    assert "PRIVATE_MANUSCRIPT_BODY_65ad" not in exported
    assert "PRIVATE_SCREENPLAY_ACTION_73ce" not in exported
    assert rig.chapters.get(chapter["id"]) == before_chapter
    assert screenplays.list(rig.nid) == before_screenplay
    assert graph["graph_kind"] == "ASSET_RELATIONSHIPS"
    assert graph["executable"] is graph["knowledge_graph"] is graph["automatic_regeneration"] is False
    assert graph["edges"][0]["target"]["kind"] == target_kind


@pytest.mark.parametrize("kind", ["SOURCE_OF", "DERIVED_FROM"])
def test_derivation_links_require_existing_lineage_and_never_invent_results(rig, decoders, originals, kind):
    chapter, screenplay, _ = originals
    source, target = import_asset(rig), import_asset(rig)
    before_assets = asset_files(rig)
    before_scope = rig.raw_store.read(rig.nid, rig.scope)
    for target_kind, rid in (("ASSET", target["id"]), ("CHAPTER", chapter["id"]), ("SCREENPLAY", screenplay["id"])):
        reference = target_for(rig.service, rig.nid, rig.scope, target_kind, rid)
        with pytest.raises(ValueError, match="REQUIRES_ASSET_LINEAGE"):
            add(rig, source, reference, kind)
        assert asset_files(rig) == before_assets
        assert rig.raw_store.read(rig.nid, rig.scope) == before_scope
    assert len(rig.service.list_assets(rig.nid, rig.scope)["items"]) == 2


def test_graph_projects_original_lineage_and_declared_links_with_distinct_semantics(rig, decoders):
    parent, child = import_asset(rig), import_asset(rig)
    child = rig.service.annotate(rig.nid, rig.scope, rig.actor, child["id"], declaration(1, [parent["id"]]))
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", parent["id"])
    child = add(rig, child, reference, "REFERENCES")
    graph = rig.service.relationships.graph(rig.nid, rig.scope)
    assert {node["id"] for node in graph["nodes"]} == {parent["id"], child["id"]}
    inherited = next(edge for edge in graph["edges"] if edge.get("owner") == "ASSET_LINEAGE")
    declared = next(edge for edge in graph["edges"] if edge.get("semantics"))
    assert inherited["type"] == "DERIVED_FROM" and inherited["state"] == "CURRENT"
    assert inherited["from"] == declared["from"] == child["id"]
    assert declared["type"] == "REFERENCES"
    assert declared["semantics"] == "DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION"
    assert not any(rig.raw_store.read(rig.nid, rig.scope)["collections"].get(name)
                   for name in ("media_tasks", "media_proposals", "production_manifests_v2"))


def test_duplicate_self_reference_and_unknown_targets_fail_without_any_write(rig, decoders):
    source, target = import_asset(rig), import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    current = add(rig, source, reference)
    before = asset_files(rig)
    with pytest.raises(ValueError, match="ALREADY_EXISTS"):
        add(rig, current, reference)
    with pytest.raises(ValueError, match="SELF_REFERENCE"):
        add(rig, current, target_for(rig.service, rig.nid, rig.scope, "ASSET", current["id"]))
    with pytest.raises(FileNotFoundError):
        add(rig, current, {**reference, "id": str(uuid4())})
    assert asset_files(rig) == before


@pytest.mark.parametrize("mutation", [
    {"type": "EXECUTE"}, {"expected_version": True}, {"expected_version": "1"},
    {"expected_version": 0}, {"reason": "x" * 1001}, {"created_by": "forged"},
    {"target": {"kind": "KNOWLEDGE", "id": "x", "version": 1, "digest": "0" * 64}},
    {"target": {"kind": "ASSET", "id": "x", "version": True, "digest": "0" * 64}},
    {"target": {"kind": "ASSET", "id": "x", "version": "1", "digest": "0" * 64}},
    {"target": {"kind": "ASSET", "id": "x", "version": 1, "digest": "no"}},
])
def test_relationship_input_is_closed_strict_and_bounded(rig, decoders, mutation):
    source, target = import_asset(rig), import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    before = asset_files(rig)
    with pytest.raises(ValueError):
        rig.service.relationships.add(rig.nid, rig.scope, rig.actor, source["id"], {**body(source, reference), **mutation})
    assert asset_files(rig) == before


@pytest.mark.parametrize("changed", ["version", "digest"])
def test_target_version_and_digest_each_bind_independently_before_commit(rig, decoders, changed):
    from app.experimental.common import StaleSourceError
    source, target = import_asset(rig), import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    reference[changed] = 99 if changed == "version" else "0" * 64
    before = asset_files(rig)
    with pytest.raises(StaleSourceError, match="TARGET_CHANGED"):
        add(rig, source, reference)
    assert asset_files(rig) == before


def test_cross_project_branch_workspace_storyline_targets_are_unavailable(rig, decoders, originals):
    source = import_asset(rig)
    other = rig.create_project("Foreign original project")
    foreign_scope = {"mode": "local", "novel_id": other}
    foreign = rig.service.import_asset(other, foreign_scope, rig.actor, upload())
    foreign_chapter = rig.chapters.create(other, {"title": "Private chapter", "content": "Private text"})
    foreign_script = originals[2].create(other, "Private script")
    for kind, rid in (("ASSET", foreign["id"]), ("CHAPTER", foreign_chapter["id"]), ("SCREENPLAY", foreign_script["id"])):
        reference = target_for(rig.service, other, foreign_scope, kind, rid)
        before = asset_files(rig)
        with pytest.raises(FileNotFoundError):
            add(rig, source, reference)
        assert asset_files(rig) == before
    scope = branch_scope(rig)
    private = import_asset(rig, scope=scope)
    reference = target_for(rig.service, rig.nid, scope, "ASSET", private["id"])
    for wrong_scope in (rig.scope, {**scope, "branch_id": "elsewhere"},
                        {**scope, "workspace_id": "elsewhere"}, {**scope, "storyline_id": "elsewhere"}):
        local = import_asset(rig, scope=wrong_scope)
        with pytest.raises(FileNotFoundError):
            add(rig, local, reference, scope=wrong_scope)
        assert private["id"] not in json.dumps(rig.service.relationships.references(rig.nid, wrong_scope, "ASSET"))


@pytest.mark.parametrize("privacy_field", ["hidden", "secret"])
def test_hidden_screenplay_disappears_without_stored_identifier_or_text_leaks(rig, decoders, originals, privacy_field):
    _, screenplay, owner = originals
    source = import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "SCREENPLAY", screenplay["id"])
    linked = add(rig, source, reference)
    hidden = owner._save_screenplay(rig.nid, {**screenplay, privacy_field: True})
    assert hidden[privacy_field] is True
    assert rig.service.relationships.references(rig.nid, rig.scope, "SCREENPLAY")["items"] == []
    current = rig.service.asset(rig.nid, rig.scope, source["id"])
    assert current["relationships"][0]["state"] == "UNAVAILABLE"
    serialized = json.dumps([current, rig.service.relationships.graph(rig.nid, rig.scope)])
    assert screenplay["id"] not in serialized and screenplay["title"] not in serialized
    assert "PRIVATE_SCREENPLAY_ACTION_73ce" not in serialized
    with pytest.raises(FileNotFoundError):
        add(rig, linked, reference, "USED_IN")
    # Internal evidence remains intact for later explicit visibility/review.
    assert stored_asset(rig, source["id"])["parameters"][KEY]["items"][0]["target"] == reference


@pytest.mark.parametrize("kind", ["ASSET", "CHAPTER", "SCREENPLAY"])
def test_target_edits_mark_exact_record_stale_and_deletion_is_explicit(rig, decoders, originals, kind):
    chapter, screenplay, owner = originals
    source, target_asset = import_asset(rig), import_asset(rig)
    target = {"ASSET": target_asset, "CHAPTER": chapter, "SCREENPLAY": screenplay}[kind]
    reference = target_for(rig.service, rig.nid, rig.scope, kind, target["id"])
    linked = add(rig, source, reference)
    if kind == "ASSET":
        revised = rig.service.annotate(rig.nid, rig.scope, rig.actor, target["id"], declaration(1))
    elif kind == "CHAPTER":
        revised = rig.chapters.save(chapter["id"], {"version": chapter["version"], "content": "A real manuscript revision"})
    else:
        revised = owner._save_screenplay(rig.nid, {**screenplay, "title": "Revised legacy screenplay"})
    current = rig.service.asset(rig.nid, rig.scope, linked["id"])
    assert current["relationships"][0]["state"] == "STALE"
    assert current["relationships"][0]["expected"] == reference
    if kind == "ASSET":
        # Simulate the established original owner's deletion, bypassing the
        # new incoming-link policy only to inspect its honest tombstone view.
        with rig.service._asset_scope(rig.nid, rig.scope):
            rig.assets.delete(target["id"])
        expected_state = "DELETED"
    elif kind == "CHAPTER":
        rig.chapters.delete(chapter["id"])
        expected_state = "UNAVAILABLE"
    else:
        owner._save_screenplay(rig.nid, {**revised, "status": "ARCHIVED"})
        expected_state = "DELETED"
    current = rig.service.asset(rig.nid, rig.scope, linked["id"])
    assert current["relationships"][0]["state"] == expected_state
    assert target["id"] not in {row["id"] for row in rig.service.relationships.references(rig.nid, rig.scope, kind)["items"]}


def test_generic_metadata_cannot_create_replace_or_erase_reserved_relationships(rig, decoders):
    source, target = import_asset(rig), import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    with rig.service._asset_scope(rig.nid, rig.scope):
        with pytest.raises(ValueError, match="scoped versioned annotation"):
            rig.assets.update_metadata(source["id"], {"parameters": {KEY: {"schema_version": 1, "items": []}}})
    linked = add(rig, source, reference)
    reserved = copy.deepcopy(stored_asset(rig, source["id"])["parameters"][KEY])
    with rig.service._asset_scope(rig.nid, rig.scope):
        with pytest.raises(ValueError, match="scoped versioned annotation"):
            rig.assets.update_metadata(source["id"], {"parameters": {KEY: {"schema_version": 1, "items": []}}})
        saved = rig.assets.update_metadata(source["id"], {"parameters": {"ordinary_note": "preserved"}},
                                           expected_version=linked["version"])
    assert saved["parameters"][KEY] == reserved
    assert saved["parameters"]["ordinary_note"] == "preserved"
    public = rig.assets.public({"items": [saved]})
    assert KEY not in public["items"][0]["parameters"]
    assert len(rig.service.asset(rig.nid, rig.scope, source["id"])["relationships"]) == 1


def test_incoming_active_relations_block_deletion_and_removal_keeps_tombstone(rig, decoders):
    from app.services.v1_capability_service import CapabilityVersionConflict
    source, target = import_asset(rig), import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    linked = add(rig, source, reference, "USED_IN")
    relation = linked["relationships"][0]
    before = asset_files(rig)
    with pytest.raises(ValueError, match="ASSET_IN_USE"):
        rig.service.lifecycle(rig.nid, rig.scope, target["id"], 1)
    with pytest.raises(CapabilityVersionConflict):
        rig.service.relationships.remove(rig.nid, rig.scope, rig.actor, source["id"], relation["id"], 1)
    assert asset_files(rig) == before
    removed = rig.service.relationships.remove(rig.nid, rig.scope, "link-editor", source["id"], relation["id"], linked["version"])
    assert removed["version"] == linked["version"] + 1 and removed["relationships"] == []
    tombstone = stored_asset(rig, source["id"])["parameters"][KEY]["items"][0]
    assert tombstone["id"] == relation["id"] and tombstone["removed_at"] and tombstone["removed_by"] == "link-editor"
    assert tombstone["target"] == reference
    assert rig.service.relationships.graph(rig.nid, rig.scope)["edges"] == []
    with pytest.raises(FileNotFoundError):
        rig.service.relationships.remove(rig.nid, rig.scope, rig.actor, source["id"], relation["id"], removed["version"])
    deleted = rig.service.lifecycle(rig.nid, rig.scope, target["id"], 1)
    assert deleted["deleted_at"]
    assert (rig.assets.root / f"{target['id']}.bin").read_bytes() == png_bytes()


def test_relationship_bounds_count_tombstones_and_reference_indexes(rig, decoders, monkeypatch):
    import app.creative.workspace_relationships as module
    source, target = import_asset(rig), import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    monkeypatch.setattr(module, "MAX_RELATIONSHIPS", 1)
    linked = add(rig, source, reference)
    relation = linked["relationships"][0]
    removed = rig.service.relationships.remove(rig.nid, rig.scope, rig.actor, source["id"], relation["id"], linked["version"])
    before = asset_files(rig)
    with pytest.raises(ValueError, match="RELATIONSHIP_LIMIT"):
        add(rig, removed, reference, "USED_IN")
    assert asset_files(rig) == before
    monkeypatch.setattr(rig.service, "MAX_ASSETS", 1)
    for operation in (lambda: rig.service.relationships.references(rig.nid, rig.scope, "ASSET"),
                      lambda: rig.service.relationships.graph(rig.nid, rig.scope)):
        with pytest.raises(ValueError, match="REFERENCE_INDEX_LIMIT"):
            operation()


@pytest.mark.parametrize("corruption", ["boolean-schema", "float-schema", "duplicate-id", "invalid-digest",
                                        "missing-removal", "boolean-removal", "invalid-remover", "unknown-kind", "extra-field"])
def test_corrupt_persisted_relationships_fail_closed_without_leaking_or_rewriting(rig, decoders, corruption):
    source, target = import_asset(rig), import_asset(rig)
    linked = add(rig, source, target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"]))
    raw = stored_asset(rig, source["id"])
    envelope, record = raw["parameters"][KEY], raw["parameters"][KEY]["items"][0]
    if corruption == "boolean-schema": envelope["schema_version"] = True
    elif corruption == "float-schema": envelope["schema_version"] = 1.0
    elif corruption == "duplicate-id": envelope["items"].append(copy.deepcopy(record))
    elif corruption == "invalid-digest": record["target"]["digest"] = "not-a-digest"
    elif corruption == "missing-removal": record.pop("removed_at")
    elif corruption == "boolean-removal": record["removed_at"] = True
    elif corruption == "invalid-remover": record.update(removed_at="2026-10-09T00:00:00+00:00", removed_by=42)
    elif corruption == "unknown-kind": record["type"] = "EXECUTE"
    else: record["private_unvalidated"] = "PRIVATE_CORRUPT_SENTINEL"
    rig.assets._write_meta(raw)
    before = asset_files(rig)
    for operation in (lambda: rig.service.asset(rig.nid, rig.scope, linked["id"]),
                      lambda: rig.service.relationships.graph(rig.nid, rig.scope)):
        with pytest.raises(ValueError, match="RELATIONSHIPS_CORRUPT"):
            operation()
    assert asset_files(rig) == before


def test_independent_services_relationship_cas_allows_only_one_writer(rig, decoders):
    from app.services.v1_capability_service import CapabilityVersionConflict
    source, target = import_asset(rig), import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"])
    barrier = Barrier(2)
    def write(kind):
        service = reopened(rig)
        barrier.wait(timeout=10)
        try:
            return add(rig, source, reference, kind, service=service)
        except CapabilityVersionConflict:
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("REFERENCES", "USED_IN")))
    assert results.count("CONFLICT") == 1
    winner = next(row for row in results if row != "CONFLICT")
    assert winner["version"] == 2 and len(winner["relationships"]) == 1
    assert reopened(rig).asset(rig.nid, rig.scope, source["id"]) == winner


def test_precommit_revocation_and_target_recheck_leave_source_unchanged(rig, decoders, originals):
    from app.experimental.common import StaleSourceError
    chapter, _, _ = originals
    source = import_asset(rig)
    reference = target_for(rig.service, rig.nid, rig.scope, "CHAPTER", chapter["id"])
    before = stored_asset(rig, source["id"])
    def revoked():
        raise PermissionError("relationship permission revoked")
    with pytest.raises(PermissionError):
        add(rig, source, reference, guard=revoked)
    assert stored_asset(rig, source["id"]) == before
    def changed_target():
        assert rig.assets._scope.binding["novel_id"] == rig.nid
        assert rig.assets._scope.binding["incarnation"] == rig.store.incarnation(rig.nid)
        rig.chapters.save(chapter["id"], {"version": chapter["version"], "content": "Changed immediately before asset commit"})
    with pytest.raises(StaleSourceError, match="TARGET_CHANGED"):
        add(rig, source, reference, guard=changed_target)
    assert stored_asset(rig, source["id"]) == before
    assert rig.chapters.get(chapter["id"])["version"] == chapter["version"] + 1
    assert getattr(rig.assets._scope, "binding", None) is None


def test_relationship_removal_revocation_preserves_active_dependency(rig, decoders):
    source, target = import_asset(rig), import_asset(rig)
    linked = add(rig, source, target_for(rig.service, rig.nid, rig.scope, "ASSET", target["id"]))
    relation = linked["relationships"][0]
    before = asset_files(rig)
    def revoked():
        raise PermissionError("link removal permission revoked")
    with pytest.raises(PermissionError):
        rig.service.relationships.remove(rig.nid, rig.scope, rig.actor, source["id"], relation["id"], linked["version"], revoked)
    assert asset_files(rig) == before
    assert getattr(rig.assets._scope, "binding", None) is None
    with pytest.raises(ValueError, match="ASSET_IN_USE"):
        rig.service.lifecycle(rig.nid, rig.scope, target["id"], target["version"])
    assert rig.service.asset(rig.nid, rig.scope, source["id"]) == linked


def test_relationship_reads_and_writes_never_enter_scope_document_storage_under_asset_lease(rig, decoders, originals, monkeypatch):
    source, target = import_asset(rig), import_asset(rig)
    chapter, screenplay, _ = originals
    original_read, original_transaction = rig.raw_store.read, rig.raw_store.transaction
    def checked_read(*args, **kwargs):
        assert getattr(rig.assets._scope, "binding", None) is None, "scope read under asset-owner lease"
        return original_read(*args, **kwargs)
    def checked_transaction(*args, **kwargs):
        assert getattr(rig.assets._scope, "binding", None) is None, "scope transaction under asset-owner lease"
        return original_transaction(*args, **kwargs)
    monkeypatch.setattr(rig.raw_store, "read", checked_read)
    monkeypatch.setattr(rig.raw_store, "transaction", checked_transaction)
    for kind, rid in (("ASSET", target["id"]), ("CHAPTER", chapter["id"]), ("SCREENPLAY", screenplay["id"])):
        source = add(rig, source, target_for(rig.service, rig.nid, rig.scope, kind, rid))
    assert len(rig.service.relationships.graph(rig.nid, rig.scope)["edges"]) == 3
    first = source["relationships"][0]
    removed = rig.service.relationships.remove(rig.nid, rig.scope, rig.actor, source["id"], first["id"], source["version"])
    assert len(removed["relationships"]) == 2


@pytest.fixture
def relation_client(client, monkeypatch):
    from app.creative.workspace_relationships import AssetRelationshipAdapter
    e = client
    monkeypatch.setattr(e.studio, "relationships", AssetRelationshipAdapter(e.studio))
    monkeypatch.setattr(e.studio.lineage.media, "screenplays", e.screenplays)
    return e


def api_assets(e, headers=None):
    return [checked(e.client.post(e.studio_base + "/assets", headers=headers or {}, json=upload_body(uuid4().hex)), 201)
            for _ in range(2)]


def api_reference(e, row, headers=None):
    result = checked(e.client.get(e.studio_base + "/references?kind=ASSET", headers=headers or {}))
    target = next(item for item in result["items"] if item["id"] == row["id"])
    return {key: target[key] for key in ("kind", "id", "version", "digest")}


def test_mounted_relationship_routes_roundtrip_readonly_bridge_cas_tombstone_and_download(relation_client):
    e = relation_client
    source, target = api_assets(e)
    reference = api_reference(e, target)
    path = e.studio_base + f"/assets/{source['id']}/relationships"
    created = checked(e.client.post(path, json=body(source, reference)), 201)
    relation = created["relationships"][0]
    assert relation["expected"] == reference and relation["state"] == "CURRENT"
    stale = e.client.post(path, json=body(source, reference, "USED_IN"))
    assert stale.status_code == 409 and stale.json()["detail"]["current"] == {"version": 2}
    assert stale.headers["cache-control"] == "no-store"
    graph = checked(e.client.get(e.studio_base + "/relationships"))
    assert graph["executable"] is graph["knowledge_graph"] is False
    chapters = checked(e.client.get(e.studio_base + "/references?kind=CHAPTER"))
    assert chapters["read_only"] and not chapters["content_copied"]
    assert e.chapters.get(e.chapter["id"]) == e.chapter
    assert e.client.get(e.studio_base + f"/assets/{source['id']}/download").content == png_bytes()
    removed = checked(e.client.delete(path + f"/{relation['id']}?expected_version=2"))
    assert removed["version"] == 3 and removed["relationships"] == []
    assert checked(e.client.get(e.studio_base + "/relationships"))["edges"] == []


def test_mounted_approved_for_requires_real_review_permission_not_intent_or_write(relation_client, monkeypatch):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    e = scoped(relation_client, monkeypatch)
    auth_scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    write_id = "relation-write-" + uuid4().hex
    review_id = "relation-review-" + uuid4().hex
    e.authorization.assign_permission(PermissionAssignment(write_id, e.viewer, "domain.write", ModalityDomain.NOVEL, auth_scope, e.lead))
    source, target = api_assets(e, e.headers)
    reference = api_reference(e, target, e.viewer_headers)
    path = e.studio_base + f"/assets/{source['id']}/relationships"
    ordinary = checked(e.client.post(path, headers=e.viewer_headers, json=body(source, reference)), 201)
    checked(e.client.put(e.studio_base + "/preferences", headers=e.viewer_headers,
                         json={"expected_version": 0, "intents": ["COMMERCIAL_CG", "CUSTOM"], "preset": "MIXED", "custom_intent": "Review approval"}))
    denied = e.client.post(path, headers=e.viewer_headers, json=body(ordinary, reference, "APPROVED_FOR"))
    assert denied.status_code == 403
    assert len(checked(e.client.get(e.studio_base + f"/assets/{source['id']}", headers=e.headers))["relationships"]) == 1
    e.authorization.assign_permission(PermissionAssignment(review_id, e.viewer, "domain.review", ModalityDomain.NOVEL, auth_scope, e.lead))
    approved = checked(e.client.post(path, headers=e.viewer_headers, json=body(ordinary, reference, "APPROVED_FOR")), 201)
    assert approved["relationships"][-1]["created_by"] == e.viewer
    assert approved["relationships"][-1]["semantics"] == "DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION"
    e.authorization.revoke_permission(review_id, e.lead)
    another = checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json=upload_body(uuid4().hex)), 201)
    denied = e.client.post(e.studio_base + f"/assets/{another['id']}/relationships", headers=e.viewer_headers,
                           json=body(another, reference, "APPROVED_FOR"))
    assert denied.status_code == 403


def test_mounted_relationships_respect_real_branch_authority_and_default_off(relation_client, monkeypatch):
    e = relation_client
    source, target = api_assets(e)
    reference = api_reference(e, target)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    for method, suffix, payload in (
        ("GET", "/references?kind=ASSET", None), ("GET", "/relationships", None),
        ("POST", f"/assets/{source['id']}/relationships", body(source, reference)),
        ("DELETE", f"/assets/{source['id']}/relationships/missing?expected_version=1", None),
    ):
        response = e.client.request(method, e.studio_base + suffix, json=payload)
        assert response.status_code == 404, response.text
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    e = scoped(e, monkeypatch)
    source, target = api_assets(e, e.headers)
    reference = api_reference(e, target, e.headers)
    path = e.studio_base + f"/assets/{source['id']}/relationships"
    assert e.client.post(path, headers=e.viewer_headers, json=body(source, reference)).status_code == 403
    denied = e.client.get(e.studio_base + "/relationships", headers={**e.headers, "X-Branch-ID": e.other_branch})
    assert denied.status_code == 403 and source["id"] not in denied.text
    assert e.client.get(e.studio_base + "/references?kind=CHAPTER", headers=e.headers).json()["items"] == []


def test_mounted_relationship_late_revoke_suppresses_private_graph(relation_client, monkeypatch):
    e = scoped(relation_client, monkeypatch)
    source, target = api_assets(e, e.headers)
    reference = api_reference(e, target, e.headers)
    checked(e.client.post(e.studio_base + f"/assets/{source['id']}/relationships", headers=e.headers,
                          json=body(source, reference)), 201)
    original = e.studio.relationships.graph
    def revoke_after_projection(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.lead)
        return result
    monkeypatch.setattr(e.studio.relationships, "graph", revoke_after_projection)
    response = e.client.get(e.studio_base + "/relationships", headers=e.headers)
    assert response.status_code == 401
    assert source["id"] not in response.text and target["id"] not in response.text
    assert response.headers["cache-control"] == "no-store"
