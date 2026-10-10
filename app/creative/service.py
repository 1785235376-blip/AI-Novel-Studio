"""Creative documents over the existing scope-atomic File/PostgreSQL store."""
from __future__ import annotations

import copy
import hashlib
import re

from ..experimental.common import DomainService, StaleSourceError, change_row, new_row
from ..experimental.store import canonical
from ..source_privacy import source_privacy_status
from .models import CreativeDocumentIn, CreativeDocumentDerive, DirectorNote

COLLECTION = "creative_documents_v2"
MAX_DOCUMENTS = 100
MAX_PAYLOAD_BYTES = 2_000_000
MAX_RECORD_BYTES = 8_000_000
MAX_HISTORY = 200
MAX_SOURCE_DOCUMENTS = 8
MAX_SOURCE_DEPTH = 16
MAX_SOURCE_VISITS = 100


def document_digest(row: dict) -> str:
    """Bind the actual server snapshot, excluding its recursive history only."""
    return hashlib.sha256(canonical({key: value for key, value in row.items() if key != "history"}).encode("utf-8")).hexdigest()


class CreativeService(DomainService):
    COLLECTION = COLLECTION

    def __init__(self, store, novels, chapters):
        super().__init__(store, novels, chapters)
        from .proposals import DirectorProposalService
        self.proposals = DirectorProposalService(self)

    @property
    def store(self):
        return self._store

    @store.setter
    def store(self, value):
        from .project_store import CreativeProjectStore
        self._store = value if isinstance(value, CreativeProjectStore) else CreativeProjectStore(value)

    def configure_generation(self, broker, preparer, manager):
        from .generation import DirectorModelCoordinator
        self.proposals.generation = DirectorModelCoordinator(self.proposals, broker, preparer, manager)

    @staticmethod
    def document_digest(row):
        return document_digest(row)

    @staticmethod
    def _expected(value):
        if type(value) is not int or value < 1:
            raise ValueError("CREATIVE_EXPECTED_VERSION_INVALID")

    def _raw(self, nid, scope, rid):
        row = super().get(nid, scope, self.COLLECTION, rid)
        if type(row.get("version")) is not int or row["version"] < 1:
            raise ValueError("CREATIVE_DOCUMENT_CORRUPT")
        return row

    def _chapter_evidence(self, nid, scope, ids):
        sources = self.sources(nid, ids, scope)
        privacy = {}
        for cid in sources:
            chapter = self.chapters_for(scope).get(cid)
            if chapter.get("hidden") or chapter.get("secret"):
                raise StaleSourceError("CREATIVE_SOURCE_UNAVAILABLE")
            privacy[cid] = source_privacy_status(chapter, scope.get("branch_id"), self.store.root)
        return sources, privacy

    def _document_evidence(self, nid, scope, values):
        if not isinstance(values, dict) or len(values) > MAX_SOURCE_DOCUMENTS:
            raise ValueError("CREATIVE_SOURCE_DOCUMENTS_INVALID")
        evidence = {}
        for rid, expected in values.items():
            if (not isinstance(rid, str) or not rid or len(rid) > 240 or not isinstance(expected, dict)
                    or set(expected) != {"version", "digest"} or type(expected["version"]) is not int
                    or expected["version"] < 1 or not isinstance(expected["digest"], str)
                    or re.fullmatch(r"[0-9a-f]{64}", expected["digest"]) is None):
                raise ValueError("CREATIVE_SOURCE_DOCUMENTS_INVALID")
            source = self._raw(nid, scope, rid)
            self.assert_current(nid, scope, source)
            if source.get("status") == "ARCHIVED" or source["version"] != expected["version"] or document_digest(source) != expected["digest"]:
                raise StaleSourceError("CREATIVE_SOURCE_DOCUMENT_CHANGED")
            evidence[rid] = copy.deepcopy(expected)
        return evidence

    def prepare_content(self, nid, scope, value, *, source_documents=None):
        """Validate host-owned evidence; usable inside an existing store transaction.

        The HTTP input has no source_documents field. Only a trusted planner or
        reviewed agent may provide those server bindings.
        """
        self.novels.get(nid)
        self.store.key(nid, scope)
        body = CreativeDocumentIn.model_validate(value)
        payload = body.model_dump()
        # Author-assigned order is persistent and independent of input array order.
        payload["scenes"].sort(key=lambda item: item["sequence"])
        payload["shots"].sort(key=lambda item: item["number"])
        payload["director_notes"].sort(key=lambda item: item["number"])
        bindings = self._document_evidence(nid, scope, {} if source_documents is None else source_documents)
        if body.source_independent and (body.source_chapter_ids or bindings):
            raise ValueError("CREATIVE_INDEPENDENT_SOURCE_CONFLICT")
        if not body.source_independent and not body.source_chapter_ids and not bindings:
            raise ValueError("CREATIVE_SOURCE_REQUIRED")
        if len(canonical(payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError("CREATIVE_PAYLOAD_CAPACITY")
        sources, privacy = self._chapter_evidence(nid, scope, body.source_chapter_ids)
        payload.update(schema_version=1, source_evidence=sources, source_privacy=privacy, source_documents=bindings,
                       project_incarnation=self.store.incarnation(nid))
        return payload

    def assert_current(self, nid, scope, row, *, _stack=(), _budget=None):
        """Fence chapter changes, scope changes and derived-document ancestry."""
        if row.get("project_incarnation") != self.store.incarnation(nid):
            raise StaleSourceError("CREATIVE_PROJECT_CHANGED")
        if row.get("novel_id") != nid or row.get("scope") != scope:
            raise StaleSourceError("CREATIVE_SCOPE_CHANGED")
        if _budget is None:
            _budget = [MAX_SOURCE_VISITS]
        _budget[0] -= 1
        rid = row.get("id")
        if not isinstance(rid, str) or rid in _stack or len(_stack) >= MAX_SOURCE_DEPTH:
            raise StaleSourceError("CREATIVE_SOURCE_CYCLE_OR_DEPTH")
        if _budget[0] < 0:
            raise StaleSourceError("CREATIVE_SOURCE_GRAPH_CAPACITY")
        try:
            body = CreativeDocumentIn.model_validate({key: row[key] for key in CreativeDocumentIn.model_fields if key in row})
        except (ValueError, KeyError):
            raise ValueError("CREATIVE_DOCUMENT_CORRUPT") from None
        if not isinstance(row.get("source_evidence"), dict) or set(row["source_evidence"]) != set(body.source_chapter_ids):
            raise StaleSourceError("CREATIVE_SOURCE_BINDING_CHANGED")
        self.assert_sources(nid, row.get("source_evidence", {}), scope)
        _, privacy = self._chapter_evidence(nid, scope, body.source_chapter_ids)
        if row.get("source_privacy", {}) != privacy:
            raise StaleSourceError("CREATIVE_SOURCE_PRIVACY_CHANGED")
        bindings = row.get("source_documents", {})
        if not isinstance(bindings, dict) or len(bindings) > MAX_SOURCE_DOCUMENTS:
            raise StaleSourceError("CREATIVE_SOURCE_BINDING_CHANGED")
        if body.source_independent and (body.source_chapter_ids or bindings):
            raise StaleSourceError("CREATIVE_SOURCE_BINDING_CHANGED")
        if not body.source_independent and not body.source_chapter_ids and not bindings:
            raise StaleSourceError("CREATIVE_SOURCE_BINDING_CHANGED")
        for source_id, expected in bindings.items():
            if (not isinstance(source_id, str) or not source_id or len(source_id) > 240
                    or not isinstance(expected, dict) or set(expected) != {"version", "digest"}
                    or type(expected["version"]) is not int or expected["version"] < 1
                    or not isinstance(expected["digest"], str)
                    or re.fullmatch(r"[0-9a-f]{64}", expected["digest"]) is None):
                raise StaleSourceError("CREATIVE_SOURCE_BINDING_CHANGED")
            try:
                source = self._raw(nid, scope, source_id)
            except FileNotFoundError:
                raise StaleSourceError("CREATIVE_SOURCE_DOCUMENT_UNAVAILABLE") from None
            if (source.get("status") == "ARCHIVED" or source.get("version") != expected["version"]
                    or document_digest(source) != expected["digest"]):
                raise StaleSourceError("CREATIVE_SOURCE_DOCUMENT_CHANGED")
            self.assert_current(nid, scope, source, _stack=(*_stack, rid), _budget=_budget)

    @staticmethod
    def assert_capacity(state):
        rows = state["collections"].get(COLLECTION, {})
        if len(rows) > MAX_DOCUMENTS:
            raise ValueError("CREATIVE_DOCUMENT_CAPACITY")
        for row in rows.values():
            if len(row.get("history", [])) > MAX_HISTORY or len(canonical(row).encode("utf-8")) > MAX_RECORD_BYTES:
                raise ValueError("CREATIVE_HISTORY_CAPACITY")

    def get(self, nid, scope, rid):
        row = self._raw(nid, scope, rid)
        if row.get("status") == "ARCHIVED":
            raise FileNotFoundError(rid)
        self.assert_current(nid, scope, row)
        return row

    def list(self, nid, scope):
        rows = super().list(nid, scope, self.COLLECTION)
        result = []
        for row in rows:
            if row.get("status") == "ARCHIVED":
                continue
            try:
                self.assert_current(nid, scope, row)
            except StaleSourceError:
                continue
            result.append(copy.deepcopy(row))
        return sorted(result, key=lambda row: (row["created_at"], row["id"]))

    def create(self, nid, scope, actor, value, *, reauthorize=lambda: None, source_documents=None):
        with self.store.transaction(nid, scope) as state:
            reauthorize()
            payload = self.prepare_content(nid, scope, value, source_documents=source_documents)
            row = new_row(nid, scope, actor, payload)
            state["collections"].setdefault(self.COLLECTION, {})[row["id"]] = row
            self.assert_current(nid, scope, row)
            self.assert_capacity(state)
            reauthorize()
            return copy.deepcopy(row)

    def create_derived(self, nid, scope, actor, value, *, source_documents, reauthorize=lambda: None):
        if not source_documents:
            raise ValueError("CREATIVE_DERIVED_SOURCE_REQUIRED")
        return self.create(nid, scope, actor, value, source_documents=source_documents, reauthorize=reauthorize)

    def update(self, nid, scope, actor, rid, expected_version, value, *, reauthorize=lambda: None):
        self._expected(expected_version)
        with self.store.transaction(nid, scope) as state:
            row = state["collections"].get(self.COLLECTION, {}).get(rid)
            if row is None or row.get("novel_id") != nid or row.get("scope") != scope or row.get("status") == "ARCHIVED":
                raise FileNotFoundError(rid)
            self.assert_current(nid, scope, row)
            payload = self.prepare_content(nid, scope, value, source_documents=row.get("source_documents", {}))
            if payload["mode"] != row["mode"]:
                raise ValueError("CREATIVE_MODE_IMMUTABLE")
            reauthorize()
            change_row(row, actor, expected_version, lambda current: current.update(payload))
            self.assert_current(nid, scope, row)
            self.assert_capacity(state)
            reauthorize()
            return copy.deepcopy(row)

    def archive(self, nid, scope, actor, rid, expected_version, *, reauthorize=lambda: None):
        self._expected(expected_version)
        with self.store.transaction(nid, scope) as state:
            row = state["collections"].get(self.COLLECTION, {}).get(rid)
            if row is None or row.get("scope") != scope or row.get("status") == "ARCHIVED":
                raise FileNotFoundError(rid)
            self.assert_current(nid, scope, row)
            reauthorize()
            change_row(row, actor, expected_version, lambda current: current.update(status="ARCHIVED"))
            self.assert_capacity(state)
            reauthorize()
            return {"id": row["id"], "version": row["version"], "status": row["status"]}

    def derive(self, nid, scope, actor, rid, value, *, reauthorize=lambda: None):
        """Advance a reviewed creative stage into a separate editable draft.

        Existing authored data is copied transparently. Missing visual decisions
        remain blank, and this operation never invokes a model or renderer.
        """
        body = CreativeDocumentDerive.model_validate(value)
        with self.store.transaction(nid, scope) as state:
            reauthorize()
            source = self.get(nid, scope, rid)
            from ..experimental.common import check_version
            check_version(source, body.expected_version)
            if ((body.mode == "STORYBOARD" and source["mode"] not in {"SCREENPLAY", "DIRECTOR"})
                    or (body.mode == "PRODUCTION" and source["mode"] != "STORYBOARD")):
                raise ValueError("CREATIVE_DERIVATION_STAGE_INVALID")
            if not source.get("scenes") or (body.mode == "PRODUCTION" and not source.get("shots")):
                raise ValueError("CREATIVE_DERIVATION_ASSETS_REQUIRED")
            title = body.title or (source["title"][:220] + (" · 分镜" if body.mode == "STORYBOARD" else " · 制作"))
            content = {"mode": body.mode, "title": title, "source_chapter_ids": source["source_chapter_ids"],
                       "scenes": source["scenes"], "director_notes": source.get("director_notes", [])}
            if body.mode == "STORYBOARD":
                shots = []
                for number, scene in enumerate(sorted(source["scenes"], key=lambda item: item["sequence"]), 1):
                    notes = sorted((note for note in source.get("director_notes", []) if note["scene_id"] == scene["id"]),
                                   key=lambda note: note["number"])
                    direction = notes[0] if notes else {}
                    shots.append({"number": number, "scene_id": scene["id"], "action": scene["action"],
                        "dialogue": scene["dialogue"], "environment": scene["location"][:4000],
                        "shot_size": direction.get("shot_size") or "MEDIUM",
                        "camera_angle": direction.get("camera_angle") or "EYE_LEVEL",
                        "camera_motion": direction.get("camera_motion") or "STATIC",
                        "duration_seconds": direction.get("duration_seconds", 5),
                        "director_notes": [{key: note[key] for key in DirectorNote.model_fields if key in note} for note in notes]})
                content["shots"] = shots
            else:
                content["shots"] = source["shots"]
                content["video_plan"] = {"segments": [{"shot_id": shot["id"], "duration_seconds": shot["duration_seconds"]}
                    for shot in sorted(source["shots"], key=lambda item: item["number"])]}
            source_digest = document_digest(source)
            payload = self.prepare_content(nid, scope, content,
                source_documents={source["id"]: {"version": source["version"], "digest": source_digest}})
            payload["provenance"] = {"method": "STRUCTURED_DERIVATION", "model_called": False,
                "source_mode": source["mode"], "source_document_id": source["id"],
                "source_version": source["version"], "input_digest": source_digest,
                "parameters": {"rule_version": "creative-stage-copy-v1"}, "quality_verification": "HUMAN_REVIEW_REQUIRED"}
            row = new_row(nid, scope, actor, payload)
            state["collections"].setdefault(self.COLLECTION, {})[row["id"]] = row
            self.assert_current(nid, scope, row)
            self.assert_capacity(state)
            reauthorize()
            return copy.deepcopy(row)

    def restore(self, nid, scope, actor, rid, expected_version, restore_version, *, reauthorize=lambda: None):
        """Restore an earlier current-source draft as a new CAS revision."""
        self._expected(expected_version)
        self._expected(restore_version)
        with self.store.transaction(nid, scope) as state:
            row = state["collections"].get(self.COLLECTION, {}).get(rid)
            if row is None or row.get("novel_id") != nid or row.get("scope") != scope:
                raise FileNotFoundError(rid)
            self.assert_current(nid, scope, row)
            target = next((item for item in [*row.get("history", []), row]
                           if item.get("version") == restore_version), None)
            if target is None or target.get("status") == "ARCHIVED":
                raise ValueError("CREATIVE_RESTORE_DRAFT_VERSION_REQUIRED")
            self.assert_current(nid, scope, target)
            if target.get("mode") != row.get("mode") or target.get("source_documents", {}) != row.get("source_documents", {}):
                raise ValueError("CREATIVE_RESTORE_SOURCE_BINDING_CHANGED")
            value = {key: target[key] for key in CreativeDocumentIn.model_fields if key in target}
            payload = self.prepare_content(nid, scope, value, source_documents=row.get("source_documents", {}))
            reauthorize()
            change_row(row, actor, expected_version, lambda current: current.update(
                payload, status="DRAFT", restored_from_version=restore_version))
            self.assert_current(nid, scope, row)
            self.assert_capacity(state)
            reauthorize()
            return copy.deepcopy(row)

    def history(self, nid, scope, rid):
        row = self._raw(nid, scope, rid)
        self.assert_current(nid, scope, row)
        items = [*row.get("history", []), {key: value for key, value in row.items() if key != "history"}]
        for item in items:
            self.assert_current(nid, scope, item)
        return {"document_id": rid, "current_version": row["version"], "items": copy.deepcopy(items)}

    def export(self, nid, scope, rid):
        row = self.get(nid, scope, rid)
        snapshot = {key: value for key, value in row.items() if key != "history"}
        return {"format": "ai-novel-creative-document", "format_version": 1,
                "document_digest": document_digest(row), "document": snapshot,
                "boundary": "Structured draft/planning JSON; accepted proposals retain generation provenance. No media rendering."}
