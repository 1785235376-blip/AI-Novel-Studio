"""Versioned, scope-bound author plans and review threads.

Uses the existing durable capability store in both repository profiles. These
records are authoring inputs, never direct edits to manuscript or Canon.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .v1_capability_service import CapabilityVersionConflict
from ..source_privacy import content_digest
from ..repositories.file.mutation_coordinator import workspace_mutation


class PlanningWorldRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    statement: str = Field(min_length=1, max_length=2000)
    forbidden_terms: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def bounded_terms(self):
        if any(not term or len(term) > 200 for term in self.forbidden_terms):
            raise ValueError("forbidden terms must contain 1–200 characters")
        return self


class PlanningLocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    rules: str = Field(default="", max_length=4000)
    atmosphere: str = Field(default="", max_length=2000)


class PlanningCharacterIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="", max_length=2000)
    personality: str = Field(default="", max_length=2000)
    goal: str = Field(default="", max_length=2000)
    age: int | None = Field(default=None, ge=0, le=999)
    status: Literal["ALIVE", "DEAD", "MISSING"] = "ALIVE"


class PlanningOutlineIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    theme: str = Field(min_length=1, max_length=2000)
    premise: str = Field(min_length=1, max_length=4000)
    structure: Literal["THREE_ACT"] = "THREE_ACT"
    beginning: str = Field(min_length=1, max_length=4000)
    middle: str = Field(min_length=1, max_length=4000)
    ending: str = Field(min_length=1, max_length=4000)
    main_conflict: str = Field(min_length=1, max_length=4000)
    climax: str = Field(min_length=1, max_length=4000)


class WorkbenchRecordIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["STYLE", "PLOT", "HISTORY", "GEOGRAPHY", "CIVILIZATION", "ABILITY", "PSYCHOLOGY", "WORLD", "CHARACTERS", "OUTLINE"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=12000)
    instructions: str = Field(default="", max_length=120)
    acts: list[str] = Field(default_factory=list, max_length=3)
    conflict: str = Field(default="", max_length=4000)
    climax: str = Field(default="", max_length=4000)
    ending: str = Field(default="", max_length=4000)
    rules: list[str] = Field(default_factory=list, max_length=50)
    character_ids: list[str] = Field(default_factory=list, max_length=50)
    location_ids: list[str] = Field(default_factory=list, max_length=50)
    chapter_ids: list[str] = Field(default_factory=list, max_length=200)
    related_record_ids: list[str] = Field(default_factory=list, max_length=50)
    story_route_id: str | None = Field(default=None, max_length=240)
    privacy_level: Literal["LOCAL_ONLY", "REDACT_BEFORE_CLOUD", "CLOUD_ALLOWED"] = "LOCAL_ONLY"
    world_summary: str = Field(default="", max_length=12000)
    world_rules: list[PlanningWorldRuleIn] = Field(default_factory=list, max_length=20)
    locations: list[PlanningLocationIn] = Field(default_factory=list, max_length=20)
    characters: list[PlanningCharacterIn] = Field(default_factory=list, max_length=20)
    outline: PlanningOutlineIn | None = None

    @model_validator(mode="after")
    def structure(self):
        if self.kind == "STYLE" and not self.instructions:
            raise ValueError("style instructions are required")
        if self.kind == "PLOT" and (len(self.acts) != 3 or not all(x.strip() for x in self.acts) or not self.conflict or not self.climax or not self.ending):
            raise ValueError("plot requires three acts, conflict, climax and ending")
        if self.kind not in {"STYLE", "PLOT"} and not self.description:
            raise ValueError("world and psychology records require a description")
        if any(not x.strip() or len(x) > 4000 for x in self.rules + self.acts):
            raise ValueError("rules and acts must be 1–4000 characters")
        if self.kind == "WORLD" and (not self.world_summary or not self.world_rules or not self.locations):
            raise ValueError("world requires summary, explicit rules and locations")
        if self.kind == "CHARACTERS" and not self.characters:
            raise ValueError("characters requires at least one character")
        if self.kind == "OUTLINE" and self.outline is None:
            raise ValueError("outline requires a complete three-act outline")
        if self.kind != "WORLD" and (self.world_summary or self.world_rules or self.locations):
            raise ValueError("world payload is only allowed for WORLD")
        if self.kind != "CHARACTERS" and self.characters:
            raise ValueError("character payload is only allowed for CHARACTERS")
        if self.kind != "OUTLINE" and self.outline is not None:
            raise ValueError("outline payload is only allowed for OUTLINE")
        for rows in (self.characters, self.locations):
            if len({row.name.casefold() for row in rows}) != len(rows):
                raise ValueError("proposed entity names must be unique")
        return self


class CommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    quote: str = Field(default="", max_length=2000)
    text: str = Field(min_length=1, max_length=8000)


class CreationWorkbenchService:
    def __init__(self, capabilities, chapters, novels):
        self.store, self.chapters, self.novels = capabilities, chapters, novels

    def chapters_for(self, scope):
        from ..manuscript_sources import scoped_chapters
        return scoped_chapters(self.chapters, scope)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def local_scope(nid):
        return {"mode": "local", "novel_id": nid}

    def _rows(self, collection):
        # Fail closed on corruption rather than silently overwriting saved work.
        path = self.store._path(collection)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
            raise ValueError("workbench store is corrupt; restore a verified backup")
        return copy.deepcopy(raw["items"])

    @staticmethod
    def _match(row, nid, scope):
        return row.get("novel_id") == nid and row.get("scope") == scope

    def _find(self, rows, nid, scope, rid):
        item = next((r for r in rows if r.get("id") == rid and self._match(r, nid, scope)), None)
        if item is None:
            raise FileNotFoundError(rid)
        return item

    def reference_data(self, nid):
        self.novels.get(nid)
        return {"characters": [{"id": r["id"], "name": r.get("name", r["id"])} for r in self.novels.data_set(nid, "characters")],
                "locations": [{"id": r["id"], "name": r.get("name", r["id"])} for r in self.novels.data_set(nid, "locations")],
                "story_routes": [{"id": r["id"], "name": r.get("title", r["id"])} for r in self.novels.data_set(nid, "story_routes")]}

    def list_records(self, nid, scope, kind=None):
        self.novels.get(nid)
        with self.store._lock, workspace_mutation(self.store.root, "creation-workbench"):
            rows = [r for r in self._rows("creation_records") if self._match(r, nid, scope) and (not kind or r["kind"] == kind)]
        return {"items": sorted(rows, key=lambda r: r["updated_at"], reverse=True), "storage": self.store.storage_mode, "inference_performed": False}

    def get_record(self, nid, scope, rid):
        self.novels.get(nid)
        with self.store._lock, workspace_mutation(self.store.root, "creation-workbench"):
            return self._find(self._rows("creation_records"), nid, scope, rid)

    def _references(self, nid, scope, body):
        for field, dataset in (("character_ids", "characters"), ("location_ids", "locations")):
            available = {str(r.get("id")) for r in self.novels.data_set(nid, dataset)}
            if not set(getattr(body, field)) <= available:
                raise ValueError(f"{field} contain an unknown project entity")
        versions = {}
        for cid in body.chapter_ids:
            chapter = self.chapters_for(scope).get(cid)
            if chapter.get("novel_id") != nid:
                raise ValueError("chapter belongs to another project")
            versions[cid] = chapter["version"]
        if body.story_route_id and body.story_route_id not in {str(r.get("id")) for r in self.novels.data_set(nid, "story_routes")}:
            raise ValueError("unknown story route")
        for rid in body.related_record_ids:
            self.get_record(nid, scope, rid)
        return versions

    @staticmethod
    def _snapshot(row):
        return copy.deepcopy({k: v for k, v in row.items() if k != "history"})

    def save_record(self, nid, scope, actor, body: WorkbenchRecordIn, rid=None, expected_version=None):
        self.novels.get(nid)
        with self.store._lock, workspace_mutation(self.store.root, "creation-workbench"):
            refs = self._references(nid, scope, body)
            rows = self._rows("creation_records")
            now = self._now()
            if rid:
                row = self._find(rows, nid, scope, rid)
                if expected_version != row["version"]:
                    raise CapabilityVersionConflict(row)
                if row["kind"] != body.kind:
                    raise ValueError("record kind cannot change")
                history = row.get("history", []) + [self._snapshot(row)]
                version, created = row["version"] + 1, row["created_at"]
            else:
                rid, history, version, created = str(uuid.uuid4()), [], 1, now
                row = {}
                rows.append(row)
            row.update(body.model_dump(mode="json"))
            row.update(id=rid, novel_id=nid, scope=copy.deepcopy(scope), status="DRAFT", version=version,
                       created_at=created, updated_at=now, actor_id=actor, source="USER", source_versions=refs,
                       history=history, source_digests={cid: content_digest(self.chapters_for(scope).get(cid)) for cid in refs})
            self.store._write("creation_records", rows)
            return copy.deepcopy(row)

    def save_generated_record(self, nid, scope, actor, body: WorkbenchRecordIn, provenance):
        """Idempotent Draft-only promotion; a failed run checkpoint cannot duplicate writes."""
        self.novels.get(nid)
        with self.store._lock:
            rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"planning-record:{nid}:{provenance['run_id']}:{provenance['candidate_id']}"))
            rows = self._rows("creation_records")
            existing = next((row for row in rows if row.get("id") == rid), None)
            if existing is not None:
                if not self._match(existing, nid, scope) or existing.get("source_provenance") != provenance:
                    raise ValueError("candidate record provenance conflict")
                return copy.deepcopy(existing)
            versions = self._references(nid, scope, body)
            digests = {}
            for source in provenance["sources"]:
                chapter = self.chapters_for(scope).get(source["chapter_id"])
                if chapter.get("novel_id") != nid or chapter.get("version") != source["chapter_version"] or content_digest(chapter) != source["content_sha256"]:
                    raise ValueError("source chapter changed; generate and review a new candidate")
                digests[chapter["id"]] = source["content_sha256"]
            if set(versions) != set(digests):
                raise ValueError("candidate references do not match its source snapshot")
            now = self._now()
            row = body.model_dump(mode="json")
            row.update(id=rid, novel_id=nid, scope=copy.deepcopy(scope), actor_id=actor,
                       status="DRAFT", privacy_level="LOCAL_ONLY", version=1, created_at=now,
                       updated_at=now, source=provenance["analysis_source"], source_versions=versions,
                       source_digests=digests, source_provenance=copy.deepcopy(provenance), history=[])
            rows.append(row)
            self.store._write("creation_records", rows)
            return copy.deepcopy(row)

    def transition_record(self, nid, scope, actor, rid, action, expected_version, restore_version=None):
        with self.store._lock, workspace_mutation(self.store.root, "creation-workbench"):
            rows = self._rows("creation_records")
            row = self._find(rows, nid, scope, rid)
            if expected_version != row["version"]:
                raise CapabilityVersionConflict(row)
            before = self._snapshot(row)
            if action == "approve":
                # Referenced source edits must be reviewed before approval.
                for cid, version in row["source_versions"].items():
                    if self.chapters_for(scope).get(cid)["version"] != version or (cid in row.get("source_digests", {}) and content_digest(self.chapters_for(scope).get(cid)) != row["source_digests"][cid]):
                        raise ValueError("source chapter changed; edit the plan to refresh its source versions")
                row["status"] = "APPROVED"
            elif action == "archive":
                row["status"] = "ARCHIVED"
            elif action == "restore":
                old = next((r for r in row.get("history", []) if r["version"] == restore_version), None)
                if old is None:
                    raise FileNotFoundError(str(restore_version))
                body = WorkbenchRecordIn.model_validate({k: old[k] for k in WorkbenchRecordIn.model_fields if k in old})
                row.update(body.model_dump(mode="json"))
                row["source_versions"] = self._references(nid, scope, body)
                row["source_digests"] = {cid: content_digest(self.chapters_for(scope).get(cid)) for cid in row["source_versions"]}
                row["status"] = "DRAFT"
            else:
                raise ValueError("unknown record action")
            row.update(version=before["version"] + 1, actor_id=actor, updated_at=self._now(), history=row.get("history", []) + [before])
            self.store._write("creation_records", rows)
            return copy.deepcopy(row)

    def generation_inputs(self, nid, scope, style_id=None, plan_id=None):
        result = {"style": "", "instruction": "", "records": []}
        for rid, kind in ((style_id, "STYLE"), (plan_id, "PLOT")):
            if not rid:
                continue
            row = self.get_record(nid, scope, rid)
            if row["kind"] != kind or row["status"] != "APPROVED":
                raise ValueError("generation requires an approved style or plot record")
            for cid, version in row["source_versions"].items():
                if self.chapters_for(scope).get(cid)["version"] != version or (cid in row.get("source_digests", {}) and content_digest(self.chapters_for(scope).get(cid)) != row["source_digests"][cid]):
                    raise ValueError("source chapter changed; review the plan again before generation")
            if kind == "STYLE":
                result["style"] = row["instructions"]
            else:
                result["instruction"] = "作者已确认的剧情规划：\n" + json.dumps({k: row[k] for k in ("title", "description", "acts", "conflict", "climax", "ending")}, ensure_ascii=False)
            result["records"].append({"id": rid, "version": row["version"], "privacy_level": row["privacy_level"]})
        return result

    def _anchor(self, nid, cid, version, quote, scope=None):
        try: chapter = self.chapters_for(scope).get(cid)
        except FileNotFoundError:
            if scope and scope.get('mode') == 'collaboration':
                from fastapi import HTTPException
                raise HTTPException(403, {'code': 'COMMENT_SOURCE_OUTSIDE_BRANCH'}) from None
            raise
        if chapter.get("novel_id") != nid:
            raise FileNotFoundError(cid)
        if chapter["version"] != version:
            raise ValueError("comment source version is stale; reload the chapter")
        if quote and quote not in chapter.get("content", ""):
            raise ValueError("comment quote is not in the source chapter")
        return {"chapter_id": cid, "chapter_version": version, "quote": quote,
                "content_sha256": hashlib.sha256(chapter.get("content", "").encode()).hexdigest()}

    def list_comments(self, nid, scope):
        self.novels.get(nid)
        with self.store._lock, workspace_mutation(self.store.root, "creation-workbench"):
            # Derived judge threads reuse this authority but require their current
            # experimental source/permission fence. The legacy route must not
            # expose them when the experiment is disabled or evidence is stale.
            rows = [r for r in self._rows("review_threads") if self._match(r, nid, scope) and not r.get("narrative_judge")]
        for row in rows:
            try:
                chapter = self.chapters_for(scope).get(row["anchor"]["chapter_id"])
                row["anchor_state"] = "CURRENT" if chapter["version"] == row["anchor"]["chapter_version"] else "STALE"
            except FileNotFoundError:
                row["anchor_state"] = "MISSING"
        return {"items": rows, "storage": self.store.storage_mode}

    def create_comment(self, nid, scope, actor, body: CommentIn, *, reauthorize=None):
        self.novels.get(nid)
        with self.store._lock, workspace_mutation(self.store.root, "creation-workbench"):
            anchor = self._anchor(nid, body.chapter_id, body.chapter_version, body.quote, scope)
            rows = self._rows("review_threads")
            now = self._now()
            row = {"id": str(uuid.uuid4()), "novel_id": nid, "scope": copy.deepcopy(scope), "anchor": anchor,
                   "status": "OPEN", "version": 1, "created_at": now, "updated_at": now,
                   "messages": [{"id": str(uuid.uuid4()), "actor_id": actor, "text": body.text, "at": now}],
                   "history": [{"action": "CREATED", "actor_id": actor, "at": now}]}
            rows.append(row)
            if reauthorize is not None:
                reauthorize()
            self.store._write("review_threads", rows)
            return copy.deepcopy(row)

    def update_comment(self, nid, scope, actor, rid, action, version, text="", *, reauthorize=None):
        with self.store._lock, workspace_mutation(self.store.root, "creation-workbench"):
            rows = self._rows("review_threads")
            row = self._find(rows, nid, scope, rid)
            if row.get("narrative_judge"):
                raise FileNotFoundError(rid)
            if version != row["version"]:
                raise CapabilityVersionConflict(row)
            now = self._now()
            if action == "reply":
                if not text.strip() or len(text) > 8000:
                    raise ValueError("reply must be 1–8000 characters")
                if row["status"] != "OPEN":
                    raise ValueError("reopen the thread before replying")
                row["messages"].append({"id": str(uuid.uuid4()), "actor_id": actor, "text": text, "at": now})
            elif action in {"resolve", "reopen"}:
                row["status"] = "RESOLVED" if action == "resolve" else "OPEN"
            else:
                raise ValueError("unknown comment action")
            row["history"].append({"action": action.upper(), "actor_id": actor, "at": now})
            row.update(version=row["version"] + 1, updated_at=now)
            if reauthorize is not None:
                reauthorize()
            self.store._write("review_threads", rows)
            return copy.deepcopy(row)
