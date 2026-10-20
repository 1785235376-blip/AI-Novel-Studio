"""Descriptive asset relations on the original asset metadata owner.

These are not executable graph edges or knowledge facts. Proven derivation
continues to use the original lineage DAG; SOURCE_OF/DERIVED_FROM records may
only describe a relationship already captured there. Other links are explicit
author declarations and never establish copyright, model output or review.
"""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime
from uuid import UUID, uuid4
from typing import get_args

from ..experimental.common import now, StaleSourceError
from ..experimental.store import canonical
from ..services.v1_capability_service import CapabilityVersionConflict
from ..source_privacy import content_digest
from .workspace_models import AssetRelationshipIn, RelationshipKind, RelationshipTarget

KEY = "asset_relationships_v2"
MAX_RELATIONSHIPS = 100


class AssetRelationshipAdapter:
    def __init__(self, workspace):
        self.workspace = workspace

    def records(self, row):
        value = row.get("parameters", {}).get(KEY, {"schema_version": 1, "items": []})
        if (not isinstance(value, dict) or set(value) != {"schema_version", "items"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or not isinstance(value["items"], list)
                or len(value["items"]) > MAX_RELATIONSHIPS
                or any(not isinstance(item, dict) for item in value["items"])):
            raise ValueError("CREATIVE_RELATIONSHIPS_CORRUPT")
        seen = set()
        for item in value["items"]:
            try:
                if (set(item) - {"id", "type", "target", "reason", "created_by", "created_at", "removed_at", "removed_by"}
                        or str(UUID(item["id"])) != item["id"] or item["type"] not in get_args(RelationshipKind)
                        or not all(isinstance(item.get(key), str) for key in ("reason", "created_by", "created_at"))
                        or not 1 <= len(item["created_by"]) <= 240 or len(item["created_at"]) > 64
                        or "removed_at" not in item or len(item["reason"]) > 1000 or item["id"] in seen):
                    raise ValueError("invalid record")
                seen.add(item["id"])
                if datetime.fromisoformat(item["created_at"]).tzinfo is None:
                    raise ValueError("invalid timestamp")
                if item["removed_at"] is not None:
                    if (not isinstance(item["removed_at"], str) or len(item["removed_at"]) > 64
                            or datetime.fromisoformat(item["removed_at"]).tzinfo is None
                            or not isinstance(item.get("removed_by"), str) or not 1 <= len(item["removed_by"]) <= 240):
                        raise ValueError("invalid removal")
                elif "removed_by" in item:
                    raise ValueError("invalid removal")
                RelationshipTarget.model_validate(item["target"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("CREATIVE_RELATIONSHIPS_CORRUPT") from None
        return copy.deepcopy(value["items"])

    def target(self, nid, scope, kind, rid):
        service = self.workspace
        if kind == "ASSET":
            row = service._row(nid, scope, rid, deleted=True)
            return {"kind": kind, "id": rid, "version": row["version"], "digest": row["sha256"],
                    "label": row["filename"], "deleted": bool(row.get("deleted_at"))}
        if kind == "CHAPTER":
            row = service.creative.chapters_for(scope).get(rid)
            if (row.get("novel_id") != nid or row.get("branch_id") != scope.get("branch_id")
                    or row.get("hidden") or row.get("secret")):
                raise FileNotFoundError(rid)
            return {"kind": kind, "id": rid, "version": row["version"], "digest": content_digest(row),
                    "label": row.get("title", ""), "deleted": bool(row.get("is_archived"))}
        if kind == "SCREENPLAY":
            owner = service.lineage.media.screenplays
            if owner is None:
                raise ValueError("CREATIVE_SCREENPLAY_REFERENCE_NOT_CONFIGURED")
            row = next((item for item in owner.list(nid, branch_id=scope.get("branch_id"))
                        if item.get("id") == rid and item.get("novel_id") == nid
                        and item.get("branch_id") == scope.get("branch_id")), None)
            if row is None or row.get("hidden") or row.get("secret"):
                raise FileNotFoundError(rid)
            digest = hashlib.sha256(canonical({key: value for key, value in row.items() if key != "version_history"}).encode()).hexdigest()
            return {"kind": kind, "id": rid, "version": row.get("edit_version", 0), "digest": digest,
                    "label": row.get("title", ""), "deleted": row.get("status") == "ARCHIVED"}
        raise ValueError("CREATIVE_REFERENCE_KIND_INVALID")

    def references(self, nid, scope, kind):
        service = self.workspace
        with service._asset_scope(nid, scope):
            if kind == "ASSET":
                ids = [row["id"] for row in service.assets.list(nid, branch_id=scope.get("branch_id"))]
            elif kind == "CHAPTER":
                ids = [row["id"] for row in service.creative.chapters_for(scope).list(nid)]
            elif kind == "SCREENPLAY":
                owner = service.lineage.media.screenplays
                if owner is None:
                    raise ValueError("CREATIVE_SCREENPLAY_REFERENCE_NOT_CONFIGURED")
                ids = [row["id"] for row in owner.list(nid, branch_id=scope.get("branch_id"))]
            else:
                raise ValueError("CREATIVE_REFERENCE_KIND_INVALID")
            if len(ids) > service.MAX_ASSETS:
                raise ValueError("CREATIVE_REFERENCE_INDEX_LIMIT")
            result = []
            for rid in ids:
                try:
                    target = self.target(nid, scope, kind, rid)
                    if not target["deleted"]:
                        result.append(target)
                except FileNotFoundError:
                    # Hidden/foreign-branch rows are not reference candidates.
                    continue
            return {"items": result, "read_only": True, "content_copied": False}

    def project(self, nid, scope, row):
        result = []
        for record in self.records(row):
            if record.get("removed_at"):
                continue
            try:
                expected = RelationshipTarget.model_validate(record["target"])
                target = self.target(nid, scope, expected.kind, expected.id)
            except (FileNotFoundError, ValueError, KeyError):
                result.append({"id": record.get("id"), "type": record.get("type"), "state": "UNAVAILABLE",
                               "target": {"label": "关联内容不可用或无权访问"}})
                continue
            current = {key: target[key] for key in ("kind", "id", "version", "digest")}
            state = "DELETED" if target["deleted"] else "CURRENT" if current == expected.model_dump() else "STALE"
            result.append({"id": record["id"], "type": record["type"], "target": target,
                           "expected": expected.model_dump(), "state": state, "reason": record["reason"],
                           "created_by": record["created_by"], "created_at": record["created_at"],
                           "semantics": "DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION"})
        return result

    def add(self, nid, scope, actor, aid, value, guard=lambda: None):
        body = AssetRelationshipIn.model_validate(value)
        service = self.workspace
        with service._asset_scope(nid, scope):
            row = service._row(nid, scope, aid)
            if row["version"] != body.expected_version:
                raise CapabilityVersionConflict({"version": row["version"]})
            if body.target.kind == "ASSET" and body.target.id == aid:
                raise ValueError("CREATIVE_RELATIONSHIP_SELF_REFERENCE")
            target = self.target(nid, scope, body.target.kind, body.target.id)
            if target["deleted"] or any(target[key] != getattr(body.target, key) for key in ("kind", "id", "version", "digest")):
                raise StaleSourceError("CREATIVE_RELATIONSHIP_TARGET_CHANGED")
            if body.type in {"SOURCE_OF", "DERIVED_FROM"}:
                if body.target.kind != "ASSET":
                    raise ValueError("CREATIVE_DERIVATION_REQUIRES_ASSET_LINEAGE")
                child = row if body.type == "DERIVED_FROM" else service._row(nid, scope, body.target.id)
                parent_id = body.target.id if body.type == "DERIVED_FROM" else aid
                if parent_id not in child.get("source_asset_ids", []):
                    raise ValueError("CREATIVE_DERIVATION_REQUIRES_ASSET_LINEAGE")
            records = self.records(row)
            if len(records) >= MAX_RELATIONSHIPS:
                raise ValueError("CREATIVE_RELATIONSHIP_LIMIT")
            if any(not item.get("removed_at") and item["type"] == body.type
                   and item["target"]["kind"] == body.target.kind and item["target"]["id"] == body.target.id for item in records):
                raise ValueError("CREATIVE_RELATIONSHIP_ALREADY_EXISTS")
            records.append({"id": str(uuid4()), "type": body.type, "target": body.target.model_dump(),
                            "reason": body.reason, "created_by": actor, "created_at": now(), "removed_at": None})
            parameters = {**row.get("parameters", {}), KEY: {"schema_version": 1, "items": records}}
            def before_commit():
                guard()
                current = self.target(nid, scope, body.target.kind, body.target.id)
                if current["deleted"] or any(current[key] != getattr(body.target, key) for key in ("kind", "id", "version", "digest")):
                    raise StaleSourceError("CREATIVE_RELATIONSHIP_TARGET_CHANGED")
            service.assets.update_metadata(aid, {"parameters": parameters}, branch_id=scope.get("branch_id"),
                expected_version=body.expected_version, _relationships_write=True, guard=before_commit)
            guard()
            return service._view(nid, scope, service._row(nid, scope, aid))

    def graph(self, nid, scope):
        service = self.workspace
        with service._asset_scope(nid, scope):
            rows = service.assets.list(nid, branch_id=scope.get("branch_id"))
            if len(rows) > service.MAX_ASSETS:
                raise ValueError("CREATIVE_REFERENCE_INDEX_LIMIT")
            nodes, edges = [], []
            for row in rows:
                service._row(nid, scope, row["id"])
                nodes.append({"id": row["id"], "kind": "ASSET", "asset_kind": row["kind"],
                              "label": row["filename"], "version": row["version"], "digest": row["sha256"]})
                edges.extend({"from": row["id"], **record} for record in self.project(nid, scope, row))
                lineage = row.get("parameters", {}).get("asset_lineage_v2", {})
                for parent_id in row.get("source_asset_ids", []):
                    edge = {"id": "lineage-" + hashlib.sha256(canonical([row["id"], parent_id]).encode()).hexdigest(),
                            "from": row["id"], "type": "DERIVED_FROM", "owner": "ASSET_LINEAGE"}
                    try:
                        target = self.target(nid, scope, "ASSET", parent_id)
                        expected = lineage.get("parents", {}).get(parent_id)
                        state = "DELETED" if target["deleted"] else "CURRENT" if expected == {
                            "version": target["version"], "digest": target["digest"]} else "STALE"
                        edges.append({**edge, "target": target, "state": state})
                    except FileNotFoundError:
                        edges.append({**edge, "target": {"label": "来源不可用或无权访问"}, "state": "UNAVAILABLE"})
            return {"graph_kind": "ASSET_RELATIONSHIPS", "nodes": nodes, "edges": edges,
                    "executable": False, "knowledge_graph": False, "automatic_regeneration": False}

    def remove(self, nid, scope, actor, aid, relationship_id, expected_version, guard=lambda: None):
        service = self.workspace
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("CREATIVE_EXPECTED_VERSION_INVALID")
        with service._asset_scope(nid, scope):
            row = service._row(nid, scope, aid)
            if row["version"] != expected_version:
                raise CapabilityVersionConflict({"version": row["version"]})
            records = self.records(row)
            record = next((item for item in records if item.get("id") == relationship_id and not item.get("removed_at")), None)
            if record is None:
                raise FileNotFoundError(relationship_id)
            record.update(removed_at=now(), removed_by=actor)
            service.assets.update_metadata(aid, {"parameters": {**row.get("parameters", {}), KEY: {"schema_version": 1, "items": records}}},
                branch_id=scope.get("branch_id"), expected_version=expected_version, _relationships_write=True, guard=guard)
            guard()
            return service._view(nid, scope, service._row(nid, scope, aid))
