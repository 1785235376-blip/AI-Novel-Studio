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
from .director_binding import _has_internal_director_record, _deny_internal_director_record
from .models import CreativeProductionDocumentIn, DirectorProposalIn, DirectorProposalReview, ProposalAction


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def director_output_digest(notes, visual_target=None):
    """Include opt-in visual goals in exact review; keep legacy note identity."""
    return digest(notes if visual_target is None else {"director_notes": notes, "visual_target": visual_target})


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
        expected_mode = row.get("provenance", {}).get("source_mode", "SCREENPLAY")
        if (source["mode"] != expected_mode or source["mode"] not in {"SCREENPLAY", "STORYBOARD"}
                or source["version"] != row["source_version"]
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
        from .camera_language import project_camera
        if _has_internal_director_record(row):
            result = deepcopy({key: value for key, value in row.items()
                if key not in {"history", "model_preview", "model_execution", "director_notes", "output_digest"}})
            result.update(status="MODEL_UNAVAILABLE", model_preview=None, model_execution=None,
                director_notes=[], output_digest=None, rule_checks=[],
                unavailable_reason="CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE")
            return result
        result = deepcopy({key: value for key, value in row.items() if key != "history"})
        # Auxiliary read-only vocabulary checks; no inferred spatial correctness.
        result["rule_checks"] = [{"note_id": note["id"], "camera": project_camera(note)}
                                 for note in row.get("director_notes", [])]
        return result

    def get(self, nid, scope, actor, rid):
        row = self._owned(nid, scope, actor, rid)
        self._current(nid, scope, row)
        if _has_internal_director_record(row): return self._public(row)
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
                result.update(status="MODEL_UNAVAILABLE", director_notes=[], rule_checks=[], model_preview=None,
                              output_digest=None, unavailable_reason="CREATIVE_MODEL_LIVE_AUTHORITY_REQUIRED")
                result["model_execution"].update(receipt_state="UNKNOWN_NO_AUTOMATIC_REPLAY")
            except HTTPException:
                result.update(status="MODEL_UNAVAILABLE", director_notes=[], rule_checks=[], model_preview=None,
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
            storyboard = source["mode"] == "STORYBOARD"
            if storyboard and not source["shots"]:
                raise ValueError("CREATIVE_PROPOSAL_STORYBOARD_SHOTS_REQUIRED: save at least one authored shot")
            if source["mode"] not in {"SCREENPLAY", "STORYBOARD"} or not source["scenes"]:
                raise ValueError("CREATIVE_PROPOSAL_SCREENPLAY_SCENES_REQUIRED")
            notes = []
            shot_sources = []
            if storyboard:
                notes, shot_sources = self._storyboard_notes(source)
            for number, scene in enumerate([] if storyboard else sorted(source["scenes"], key=lambda row: row["sequence"]), 1):
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
            candidate = CreativeProductionDocumentIn(mode="DIRECTOR", title=title,
                source_chapter_ids=source["source_chapter_ids"], scenes=source["scenes"], director_notes=notes,
                visual_target=body.visual_target)
            notes = [note.model_dump() for note in candidate.director_notes]
            visual_target = candidate.visual_target.model_dump() if candidate.visual_target is not None else None
            provenance = {"method": "RULE_ASSISTED", "model_called": False, "provider_id": None,
                "model_id": None, "model_version": None, "parameters": {"rule_version": "director-planning-v1"},
                "input_digest": self.documents.document_digest(source), "quality_verification": "HUMAN_REVIEW_REQUIRED"}
            if storyboard:
                provenance.update(source_mode="STORYBOARD", source_shots=shot_sources,
                                  parameters={"rule_version": "storyboard-director-planning-v1"})
            row = new_row(nid, scope, actor, {"status": "NEEDS_REVIEW", "title": title,
                "project_incarnation": self.documents.store.incarnation(nid),
                "source_document_id": source["id"], "source_version": source["version"],
                "source_digest": self.documents.document_digest(source), "director_notes": notes,
                "output_digest": director_output_digest(notes, visual_target), "provenance": provenance, "model_preview": None,
                "model_execution": None, "document_id": None})
            if visual_target is not None:
                row["visual_target"] = visual_target
            state["collections"].setdefault(self.COLLECTION, {})[row["id"]] = row
            self._current(nid, scope, row)
            self._capacity(state)
            guard()
            return self._public(row)

    @staticmethod
    def _storyboard_notes(source):
        """Copy authored fields exactly; retain unmapped shot data with disclosure.

        The source snapshot is evidence, not a claim that Director operational
        fields represent every storyboard field. No spatial/model inference.
        """
        from .models import DirectorSceneNote
        mapping = {"frame_prompt": "note", "action": "shot_suggestion",
                   "shot_size": "shot_size", "camera_angle": "camera_angle",
                   "camera_motion": "camera_motion", "duration_seconds": "duration_seconds",
                   "emotion": "emotion", "composition": "composition", "lens": "lens",
                   "lighting": "lighting", "color": "color_palette"}
        notes, associations = [], []
        for shot in sorted(source["shots"], key=lambda item: item["number"]):
            copied = {target: shot[field] for field, target in mapping.items()
                      if field in shot and shot[field] is not None}
            raw = {**copied, "number": shot["number"], "scene_id": shot["scene_id"],
                   "pacing": "待审建议：核对已写镜头时长与表演、剪辑节奏。",
                   "blocking": "待审建议：人工核对人物位置、视线与镜头衔接；规则不验证空间。"}
            try:
                note = DirectorSceneNote.model_validate(raw).model_dump()
            except ValueError as exc:
                raise ValueError(f"CREATIVE_PROPOSAL_STORYBOARD_FIELD_LIMIT: shot {shot['id']}; "
                                 "shorten frame_prompt/action to 8000 and emotion to 2000 characters before proposing; "
                                 f"Director validation: {exc}") from exc
            if any(note[field] != value for field, value in copied.items()):
                raise ValueError(f"CREATIVE_PROPOSAL_STORYBOARD_FIELD_NORMALIZATION: shot {shot['id']}; "
                                 "save text without surrounding whitespace before proposing")
            notes.append(note)
            associations.append({"note_id": note["id"], "source_shot_id": shot["id"],
                "source_number": shot["number"], "scene_id": shot["scene_id"], "source_shot": deepcopy(shot),
                "copied_fields": list(copied), "suggested_fields": ["pacing", "blocking"],
                "retained_source_only_fields": [field for field in shot
                    if field not in mapping and field not in {"id", "number", "scene_id"}]})
        return notes, associations

    def review(self, nid, scope, actor, rid, value, *, guard=lambda: None):
        body = DirectorProposalReview.model_validate(value)
        with self.documents.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, rid, state)
            _deny_internal_director_record(row)
            source = self._current(nid, scope, row)
            check_version(row, body.expected_version)
            if row["status"] != "NEEDS_REVIEW" or row.get("document_id"):
                raise ValueError("CREATIVE_PROPOSAL_NOT_REVIEWABLE")
            if row["output_digest"] != body.reviewed_output_digest or director_output_digest(row["director_notes"], row.get("visual_target")) != row["output_digest"]:
                raise ValueError("CREATIVE_PROPOSAL_EXACT_REVIEW_REQUIRED")
            guard()
            if source["mode"] == "STORYBOARD":
                expected = [(item["note_id"], item["scene_id"], item["source_number"])
                            for item in row["provenance"]["source_shots"]]
                if [(note.id, note.scene_id, note.number) for note in body.director_notes] != expected:
                    raise ValueError("CREATIVE_PROPOSAL_STORYBOARD_ASSOCIATION_REQUIRED: retain each note ID, scene and authored shot order")
            if row.get("model_execution"):
                if self.generation is None:
                    raise StaleSourceError("CREATIVE_MODEL_LIVE_AUTHORITY_REQUIRED")
                from ..experimental.ux import ReadContext
                self.generation.validate_result(ReadContext(nid, scope, actor), row)
            return self._adopt_review_locked(nid, scope, actor, state, row, source, body,
                notes=row["director_notes"], output_digest=row["output_digest"], provenance=row["provenance"],
                after_mutation=guard)

    def _adopt_review_locked(self, nid, scope, actor, state, row, source, body, *,
                             notes, output_digest, provenance, before_mutation=lambda: None,
                             after_mutation=lambda: None, quota_view=None):
        """Original review commit shared by already-authorized private callers.

        Caller owns the original scope transaction and review authority. This
        core never opens a transaction, strips a marker, or grants authority.
        """
        if quota_view is None:
            quota_view = lambda: state
        check_version(row, body.expected_version)
        if row.get("document_id"):
            raise ValueError("CREATIVE_PROPOSAL_NOT_REVIEWABLE")
        if (output_digest != body.reviewed_output_digest
                or director_output_digest(notes, row.get("visual_target")) != output_digest):
            raise ValueError("CREATIVE_PROPOSAL_EXACT_REVIEW_REQUIRED")
        if source["mode"] == "STORYBOARD":
            expected = [(item["note_id"], item["scene_id"], item["source_number"])
                        for item in row["provenance"]["source_shots"]]
            if [(note.id, note.scene_id, note.number) for note in body.director_notes] != expected:
                raise ValueError("CREATIVE_PROPOSAL_STORYBOARD_ASSOCIATION_REQUIRED: retain each note ID, scene and authored shot order")
        # Omitting the review extension preserves an authored visual goal;
        # an explicit null is the user's choice to clear it before adoption.
        visual_target = body.visual_target if "visual_target" in body.model_fields_set else row.get("visual_target")
        candidate = CreativeProductionDocumentIn(mode="DIRECTOR", title=body.title,
            source_chapter_ids=source["source_chapter_ids"], scenes=source["scenes"],
            director_notes=body.director_notes, visual_target=visual_target)
        payload = self.documents.prepare_content(nid, scope, candidate,
            source_documents={source["id"]: {"version": row["source_version"], "digest": row["source_digest"]}})
        provenance = {**deepcopy(provenance), "proposal_id": row["id"],
            "proposal_version": row["version"], "output_digest": output_digest,
            "reviewed_output_digest": director_output_digest(payload["director_notes"], payload.get("visual_target")), "reviewed_by": actor, "reviewed_at": now()}
        document = new_row(nid, scope, actor, {**payload, "provenance": provenance})
        before_mutation()
        state["collections"].setdefault(self.documents.COLLECTION, {})[document["id"]] = document
        self.documents.assert_current(nid, scope, document)
        self.documents.assert_capacity(quota_view())
        change_row(row, actor, body.expected_version, lambda current: current.update(
            status="APPROVED", document_id=document["id"], reviewed_by=actor, reviewed_at=provenance["reviewed_at"]))
        self._capacity(quota_view())
        after_mutation()
        self._current(nid, scope, row)
        return {"proposal": self._public(row), "document": deepcopy(document)}

    def cancel(self, nid, scope, actor, rid, value, *, guard=lambda: None):
        body = ProposalAction.model_validate(value)
        with self.documents.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, rid, state)
            _deny_internal_director_record(row)
            check_version(row, body.expected_version)
            guard()
            if row["status"] == "APPROVED":
                raise ValueError("CREATIVE_PROPOSAL_ALREADY_APPROVED")
            execution = deepcopy(row.get("model_execution"))
            if execution:
                execution["status"] = "CANCELLED"
            change_row(row, actor, body.expected_version, lambda current: current.update(
                status="CANCELLED", model_execution=execution, director_notes=[], output_digest=director_output_digest([], current.get("visual_target"))))
            self._capacity(state)
            guard()
            result = self._public(row)
        if execution and self.generation:
            try:
                self.generation.manager.cancel(execution["job_id"])
            except KeyError:
                pass
        return result
