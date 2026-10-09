"""Screenplay-to-direction proposals on the original scope-atomic document store.

The rules are transparent planning prompts, not inferred camera geography or
model output. An explicit human review creates a separate derived document.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

from fastapi import HTTPException

from ..experimental.common import StaleSourceError, check_version, change_row, new_row, now
from ..experimental.store import canonical
from .models import CreativeDocumentIn, DirectorProposalIn, DirectorProposalReview, ProposalAction


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class DirectorProposalService:
    COLLECTION = "creative_director_proposals_v2"
    MAX_PROPOSALS = 100
    MAX_HISTORY = 100
    MAX_RECORD_BYTES = 8_000_000

    def __init__(self, documents):
        self.documents = documents
        self.generation = None

    def _owned(self, nid, scope, actor, rid, state=None):
        # Resolve store via document service so composed repository fixtures and
        # live host ownership never retain a stale storage binding.
        state = state if state is not None else self.documents.store.read(nid, scope)
        row = state["collections"].get(self.COLLECTION, {}).get(rid)
        if (row is None or row.get("created_by") != actor or row.get("novel_id") != nid
                or row.get("scope") != scope):
            raise FileNotFoundError(rid)
        return row

    def _current(self, nid, scope, row):
        source = self.documents.get(nid, scope, row["source_document_id"])
        if (source["mode"] != "SCREENPLAY" or source["version"] != row["source_version"]
                or self.documents.document_digest(source) != row["source_digest"]):
            raise StaleSourceError("CREATIVE_PROPOSAL_SOURCE_CHANGED")
        return source

    def _capacity(self, state):
        rows = state["collections"].get(self.COLLECTION, {})
        if len(rows) > self.MAX_PROPOSALS:
            raise ValueError("CREATIVE_PROPOSAL_CAPACITY")
        if any(len(row.get("history", [])) > self.MAX_HISTORY or len(canonical(row).encode()) > self.MAX_RECORD_BYTES
               for row in rows.values()):
            raise ValueError("CREATIVE_PROPOSAL_HISTORY_CAPACITY")

    @staticmethod
    def _public(row):
        return deepcopy({key: value for key, value in row.items() if key != "history"})

    def get(self, nid, scope, actor, rid):
        row = self._owned(nid, scope, actor, rid)
        self._current(nid, scope, row)
        result = self._public(row)
        if row.get("model_execution") and row["status"] not in {"APPROVED", "CANCELLED"}:
            try:
                if self.generation is None:
                    raise StaleSourceError("CREATIVE_MODEL_LIVE_AUTHORITY_REQUIRED")
                job = self.generation.manager.get(row["model_execution"]["job_id"])
                if not callable(job.request_authorization):
                    raise StaleSourceError("CREATIVE_MODEL_LIVE_AUTHORITY_REQUIRED")
                job.request_authorization()
                if row["status"] == "NEEDS_REVIEW":
                    from ..experimental.ux import ReadContext
                    self.generation.validate_result(ReadContext(nid, scope, actor), row)
            except (KeyError, ValueError, PermissionError, FileNotFoundError):
                result.update(status="MODEL_UNAVAILABLE", director_notes=[], model_preview=None,
                              output_digest=None, unavailable_reason="CREATIVE_MODEL_LIVE_AUTHORITY_REQUIRED")
                result["model_execution"].update(receipt_state="UNKNOWN_NO_AUTOMATIC_REPLAY")
            except HTTPException:
                result.update(status="MODEL_UNAVAILABLE", director_notes=[], model_preview=None,
                              output_digest=None, unavailable_reason="CREATIVE_MODEL_AUTHORITY_REVOKED")
        return result

    def list(self, nid, scope, actor):
        result = []
        state = self.documents.store.read(nid, scope)
        for rid in state["collections"].get(self.COLLECTION, {}):
            try:
                result.append(self.get(nid, scope, actor, rid))
            except (StaleSourceError, FileNotFoundError):
                continue
        return sorted(result, key=lambda row: (row["created_at"], row["id"]), reverse=True)

    def create(self, nid, scope, actor, value, *, guard=lambda: None):
        body = DirectorProposalIn.model_validate(value)
        with self.documents.store.transaction(nid, scope) as state:
            guard()
            source = self.documents.get(nid, scope, body.source_document_id)
            check_version(source, body.expected_source_version)
            if source["mode"] != "SCREENPLAY" or not source["scenes"]:
                raise ValueError("CREATIVE_PROPOSAL_SCREENPLAY_SCENES_REQUIRED")
            notes = []
            for number, scene in enumerate(sorted(source["scenes"], key=lambda row: row["sequence"]), 1):
                # Copy explicitly authored emotion and delivery; suggestions
                # remain visibly hypothetical and editable before adoption.
                notes.append({"scene_id": scene["id"], "number": number,
                    "note": "待审建议：先核对场景目的与人物关系，再选择景别和机位。",
                    "shot_size": "MEDIUM", "camera_angle": "EYE_LEVEL", "camera_motion": "STATIC",
                    "duration_seconds": 5, "emotion": scene.get("emotion", ""),
                    "pacing": "待审建议：对白后保留反应停顿；时长由表演与剪辑试排确定。",
                    "performance": "；".join(dialogue["delivery"] for dialogue in scene.get("dialogue", []) if dialogue.get("delivery"))[:4000],
                    "blocking": "待人工确认人物位置、视线和出入方向；文字不足以确定实际空间。"})
            title = body.title or (source["title"][:220] + " · 导演方案")
            candidate = CreativeDocumentIn(mode="DIRECTOR", title=title,
                source_chapter_ids=source["source_chapter_ids"], scenes=source["scenes"], director_notes=notes)
            notes = [note.model_dump() for note in candidate.director_notes]
            provenance = {"method": "RULE_ASSISTED", "model_called": False, "provider_id": None,
                "model_id": None, "model_version": None, "parameters": {"rule_version": "director-planning-v1"},
                "input_digest": self.documents.document_digest(source), "quality_verification": "HUMAN_REVIEW_REQUIRED"}
            row = new_row(nid, scope, actor, {"status": "NEEDS_REVIEW", "title": title,
                "source_document_id": source["id"], "source_version": source["version"],
                "source_digest": self.documents.document_digest(source), "director_notes": notes,
                "output_digest": digest(notes), "provenance": provenance, "model_preview": None,
                "model_execution": None, "document_id": None})
            state["collections"].setdefault(self.COLLECTION, {})[row["id"]] = row
            self._current(nid, scope, row)
            self._capacity(state)
            guard()
            return self._public(row)

    def review(self, nid, scope, actor, rid, value, *, guard=lambda: None):
        body = DirectorProposalReview.model_validate(value)
        with self.documents.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, rid, state)
            source = self._current(nid, scope, row)
            check_version(row, body.expected_version)
            if row["status"] != "NEEDS_REVIEW" or row.get("document_id"):
                raise ValueError("CREATIVE_PROPOSAL_NOT_REVIEWABLE")
            if row["output_digest"] != body.reviewed_output_digest or digest(row["director_notes"]) != row["output_digest"]:
                raise ValueError("CREATIVE_PROPOSAL_EXACT_REVIEW_REQUIRED")
            guard()
            if row.get("model_execution"):
                if self.generation is None:
                    raise StaleSourceError("CREATIVE_MODEL_LIVE_AUTHORITY_REQUIRED")
                from ..experimental.ux import ReadContext
                self.generation.validate_result(ReadContext(nid, scope, actor), row)
            candidate = CreativeDocumentIn(mode="DIRECTOR", title=body.title,
                source_chapter_ids=source["source_chapter_ids"], scenes=source["scenes"],
                director_notes=body.director_notes)
            payload = self.documents.prepare_content(nid, scope, candidate,
                source_documents={source["id"]: {"version": row["source_version"], "digest": row["source_digest"]}})
            provenance = {**deepcopy(row["provenance"]), "proposal_id": row["id"],
                "proposal_version": row["version"], "output_digest": row["output_digest"],
                "reviewed_output_digest": digest(payload["director_notes"]), "reviewed_by": actor, "reviewed_at": now()}
            document = new_row(nid, scope, actor, {**payload, "provenance": provenance})
            state["collections"].setdefault(self.documents.COLLECTION, {})[document["id"]] = document
            self.documents.assert_current(nid, scope, document)
            self.documents.assert_capacity(state)
            change_row(row, actor, body.expected_version, lambda current: current.update(
                status="APPROVED", document_id=document["id"], reviewed_by=actor, reviewed_at=provenance["reviewed_at"]))
            self._capacity(state)
            guard()
            self._current(nid, scope, row)
            return {"proposal": self._public(row), "document": deepcopy(document)}

    def cancel(self, nid, scope, actor, rid, value, *, guard=lambda: None):
        body = ProposalAction.model_validate(value)
        with self.documents.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, rid, state)
            check_version(row, body.expected_version)
            guard()
            if row["status"] == "APPROVED":
                raise ValueError("CREATIVE_PROPOSAL_ALREADY_APPROVED")
            execution = deepcopy(row.get("model_execution"))
            if execution:
                execution["status"] = "CANCELLED"
            change_row(row, actor, body.expected_version, lambda current: current.update(
                status="CANCELLED", model_execution=execution, director_notes=[], output_digest=digest([])))
            self._capacity(state)
            guard()
            result = self._public(row)
        if execution and self.generation:
            try:
                self.generation.manager.cancel(execution["job_id"])
            except KeyError:
                pass
        return result
