"""Reviewed chapter-to-screenplay conversion on the original Creative store."""
from copy import deepcopy

from fastapi import HTTPException

from ..author_request import chapter_digest
from ..experimental.common import StaleSourceError, change_row, check_version, new_row, now
from ..experimental.store import canonical
from .adaptation_models import AdaptationIn, AdaptationOutput, AdaptationReview, OrderedAdaptationOutput
from .models import CreativeDocumentIn, ProposalAction
from .proposals import digest
from .adaptation_sources import is_ordered, chapter_ids, ordered_fields, snapshot, validate_snapshots


class AdaptationService:
    COLLECTION = "creative_adaptation_proposals_v2"
    MAX_PROPOSALS = 100
    MAX_HISTORY = 40
    MAX_RECORD_BYTES = 8_000_000

    def __init__(self, documents):
        self.documents, self.generation, self.assets = documents, None, None

    def _owned(self, nid, scope, actor, rid, state=None):
        state = state if state is not None else self.documents.store.read(nid, scope)
        row = state["collections"].get(self.COLLECTION, {}).get(rid)
        if not row or (row.get("novel_id"), row.get("scope"), row.get("created_by")) != (nid, scope, actor):
            raise FileNotFoundError(rid)
        return row

    def _current(self, nid, scope, row):
        if row["project_incarnation"] != self.documents.store.incarnation(nid):
            raise StaleSourceError("ADAPTATION_PROJECT_CHANGED")
        if is_ordered(row):
            validate_snapshots(row["sources"], row["ordered_sources_digest"])
            sources, privacy = self.documents._chapter_evidence(nid, scope, chapter_ids(row))
            try:
                current = [snapshot(self.documents.chapters_for(scope).get(source["chapter_id"]), index, scope)
                    for index, source in enumerate(row["sources"], 1)]
            except ValueError:
                raise StaleSourceError("ADAPTATION_SOURCE_CHANGED") from None
            if (current != row["sources"] or sources != row["source_evidence"] or privacy != row["source_privacy"]
                    or any(row[key] != current[0][key] for key in ("chapter_id", "source_version", "source_digest", "selected_text", "selection_digest"))):
                raise StaleSourceError("ADAPTATION_SOURCE_CHANGED")
            return self.documents.chapters_for(scope).get(row["chapter_id"])
        if "sources" in row or "ordered_sources_digest" in row:
            raise StaleSourceError("ADAPTATION_SOURCE_MODE_CHANGED")
        sources, privacy = self.documents._chapter_evidence(nid, scope, [row["chapter_id"]])
        chapter = self.documents.chapters_for(scope).get(row["chapter_id"])
        if (sources != row["source_evidence"] or privacy != row["source_privacy"]
                or chapter_digest(chapter) != row["source_digest"]
                or row["selected_text"] not in chapter["content"]):
            raise StaleSourceError("ADAPTATION_SOURCE_CHANGED")
        return chapter

    def _capacity(self, state):
        rows = state["collections"].get(self.COLLECTION, {})
        if len(rows) > self.MAX_PROPOSALS:
            raise ValueError("ADAPTATION_CAPACITY")
        if any(len(row.get("history", [])) > self.MAX_HISTORY or len(canonical(row).encode()) > self.MAX_RECORD_BYTES
               for row in rows.values()):
            raise ValueError("ADAPTATION_HISTORY_CAPACITY")

    @staticmethod
    def _public(row):
        return deepcopy({key: value for key, value in row.items() if key != "history"})

    def get(self, nid, scope, actor, rid, *, guard=lambda: None, reconcile=True):
        row = self._owned(nid, scope, actor, rid)
        self._current(nid, scope, row)
        guard()
        if self.assets and self.assets.enabled(row):
            from ..experimental.ux import ReadContext
            return self.assets.read(ReadContext(nid, scope, actor), rid, guard, reconcile=reconcile)
        result = self._public(row)
        if row.get("model_execution") and row["status"] not in {"APPROVED", "CANCELLED"}:
            try:
                if self.generation is None:
                    raise ValueError("ADAPTATION_LIVE_AUTHORITY_REQUIRED")
                job = self.generation.manager.get(row["model_execution"]["job_id"])
                if not callable(job.request_authorization):
                    raise ValueError("ADAPTATION_LIVE_AUTHORITY_REQUIRED")
                job.request_authorization()
                if row["status"] == "NEEDS_REVIEW":
                    from ..experimental.ux import ReadContext
                    self.generation.validate_result(ReadContext(nid, scope, actor), row)
            except (KeyError, ValueError, PermissionError, FileNotFoundError, HTTPException):
                result.update(status="MODEL_UNAVAILABLE", output=None, output_digest=None, model_preview=None,
                              unavailable_reason="ADAPTATION_LIVE_AUTHORITY_REQUIRED")
                result["model_execution"].update(receipt_state="UNKNOWN_NO_AUTOMATIC_REPLAY")
        return result

    def list(self, nid, scope, actor, *, guard=lambda: None):
        from ..experimental.ux import ReadContext
        ctx = ReadContext(nid, scope, actor)
        rows, reconciled = [], False
        for rid in self.documents.store.read(nid, scope)["collections"].get(self.COLLECTION, {}):
            try:
                row = self.get(nid, scope, actor, rid, guard=guard, reconcile=False)
                if (not reconciled and self.assets and row.get("model_asset_intent")
                        and (row.get("asset_output") or {}).get("state") in {"PENDING", "INCOMPLETE"}
                        and self.assets.can_reconcile(ctx, row)):
                    row = self.get(nid, scope, actor, rid, guard=guard)
                    reconciled = True
                rows.append(row)
            except (FileNotFoundError, StaleSourceError):
                continue
        guard()
        return sorted(rows, key=lambda row: (row["created_at"], row["id"]), reverse=True)

    def create(self, nid, scope, actor, value, *, guard=lambda: None):
        body = AdaptationIn.model_validate(value)
        if not body.title.strip():
            raise ValueError("ADAPTATION_TITLE_REQUIRED")
        with self.documents.store.transaction(nid, scope) as state:
            guard()
            ordered = {}
            if body.sources is not None:
                sources, privacy = self.documents._chapter_evidence(nid, scope, [source.chapter_id for source in body.sources])
                snapshots = []
                for ordinal, source in enumerate(body.sources, 1):
                    saved = self.documents.chapters_for(scope).get(source.chapter_id)
                    check_version(saved, source.expected_source_version)
                    snapshots.append(snapshot(saved, ordinal, scope))
                validate_snapshots(snapshots, digest(snapshots))
                ordered = {"source_mode": "ORDERED_CHAPTERS", "sources": snapshots, "ordered_sources_digest": digest(snapshots)}
                chapter = self.documents.chapters_for(scope).get(snapshots[0]["chapter_id"])
                selected = chapter["content"]
            else:
                sources, privacy = self.documents._chapter_evidence(nid, scope, [body.chapter_id])
                chapter = self.documents.chapters_for(scope).get(body.chapter_id)
                check_version(chapter, body.expected_source_version)
                selected = body.selected_text or chapter["content"]
            if not selected.strip() or selected not in chapter["content"] or len(selected) > 64000:
                raise ValueError("ADAPTATION_SAVED_SELECTION_REQUIRED_OR_TOO_LARGE")
            row = new_row(nid, scope, actor, {"status": "DRAFT", "title": body.title,
                "instruction": body.instruction, "chapter_id": chapter["id"], **ordered,
                "source_version": chapter["version"], "source_digest": chapter_digest(chapter),
                "source_evidence": sources, "source_privacy": privacy, "selected_text": selected,
                "selection_digest": digest(selected), "project_incarnation": self.documents.store.incarnation(nid),
                "output": None, "output_digest": None, "model_preview": None, "model_execution": None,
                "provenance": None, "document_id": None,
                "result_archive_contract": "creative-adaptation-text-asset/1"})
            state["collections"].setdefault(self.COLLECTION, {})[row["id"]] = row
            self._current(nid, scope, row)
            self._capacity(state)
            guard()
            return self._public(row)

    @staticmethod
    def validate_output(row, value):
        model = OrderedAdaptationOutput if is_ordered(row) else AdaptationOutput
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        output = model.model_validate(value, strict=True)
        if is_ordered(row):
            sources = {source["ordinal"]: source for source in row["sources"]}
            scenes = {scene.id: scene for scene in output.scenes}
            if any(scene.source_ordinal not in sources for scene in output.scenes):
                raise ValueError("ADAPTATION_UNKNOWN_SOURCE_ORDINAL")
            if {change.source_ordinal for change in output.report.changes} != set(sources):
                raise ValueError("ADAPTATION_SOURCE_REPORT_COVERAGE_REQUIRED")
            for change in output.report.changes:
                source = sources.get(change.source_ordinal)
                if source is None or any(scenes[sid].source_ordinal != change.source_ordinal for sid in change.scene_ids):
                    raise ValueError("ADAPTATION_UNKNOWN_OR_CROSS_SOURCE_CHANGE")
                if change.source_quote and change.source_quote not in source["selected_text"]:
                    raise ValueError("ADAPTATION_QUOTE_NOT_IN_SELECTED_SOURCE")
        else:
            for change in output.report.changes:
                if change.source_quote and change.source_quote not in row["selected_text"]:
                    raise ValueError("ADAPTATION_QUOTE_NOT_IN_SELECTED_SOURCE")
        result = output.model_dump()
        result["scenes"].sort(key=lambda scene: scene["sequence"])
        if len(canonical(result).encode()) > 128000:
            raise ValueError("ADAPTATION_OUTPUT_LIMIT")
        return result

    def review(self, nid, scope, actor, rid, value, *, guard=lambda: None):
        row = self._owned(nid, scope, actor, rid)
        if not self.assets or not self.assets.enabled(row):
            return self._review(nid, scope, actor, rid, value, guard=guard)
        from ..experimental.ux import ReadContext
        ctx = ReadContext(nid, scope, actor)
        with self.assets.phase(ctx, rid, guard, create=False):
            result = self._review(nid, scope, actor, rid, value, guard=guard)
        # The original human decision is already committed; a failed asset
        # projection is recoverable on the next authorized read, never replayed.
        result["proposal"] = self.assets.read(ctx, rid, guard)
        return result

    def _review(self, nid, scope, actor, rid, value, *, guard=lambda: None):
        body = AdaptationReview.model_validate(value)
        with self.documents.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, rid, state)
            check_version(row, body.expected_version)
            self._current(nid, scope, row)
            guard()
            if row["status"] != "NEEDS_REVIEW" or row.get("document_id"):
                raise ValueError("ADAPTATION_NOT_REVIEWABLE")
            if not row["output_digest"] or body.reviewed_output_digest != row["output_digest"]:
                raise ValueError("ADAPTATION_EXACT_REVIEW_REQUIRED")
            if self.generation is None:
                raise StaleSourceError("ADAPTATION_LIVE_AUTHORITY_REQUIRED")
            from ..experimental.ux import ReadContext
            self.generation.validate_result(ReadContext(nid, scope, actor), row)
            output = self.validate_output(row, body.output)
            scenes = [{**{key: value for key, value in scene.items() if key != "source_ordinal"},
                "source_chapter_id": row["sources"][scene["source_ordinal"] - 1]["chapter_id"] if is_ordered(row) else row["chapter_id"]}
                for scene in output["scenes"]]
            content = self.documents.prepare_content(nid, scope, CreativeDocumentIn(mode="SCREENPLAY",
                title=body.title, source_chapter_ids=chapter_ids(row), scenes=scenes))
            provenance = {**deepcopy(row["provenance"]), "proposal_id": rid,
                "proposal_version": row["version"], "generated_output_digest": row["output_digest"],
                "reviewed_output_digest": digest(output), "difference_report": output["report"],
                "report_document_version": 1, "report_semantics": "ORIGINAL_REVIEWED_ADAPTATION_NOT_LATER_EDIT_FIDELITY",
                "reviewed_by": actor, "reviewed_at": now(), **ordered_fields(row)}
            document = new_row(nid, scope, actor, {**content, "provenance": provenance})
            state["collections"].setdefault(self.documents.COLLECTION, {})[document["id"]] = document
            self.documents.assert_current(nid, scope, document)
            self.documents.assert_capacity(state)
            decision = (self.assets.decision(row, document, digest(output), provenance["reviewed_at"])
                        if self.assets and self.assets.enabled(row) else None)
            change_row(row, actor, row["version"], lambda item: item.update(
                **({"asset_review_decision": decision} if decision else {}), status="APPROVED",
                document_id=document["id"], reviewed_by=actor, reviewed_at=provenance["reviewed_at"]))
            self._capacity(state)
            self._current(nid, scope, row)
            guard()
            return {"proposal": self._public(row), "document": deepcopy(document)}

    def cancel(self, nid, scope, actor, rid, value, *, guard=lambda: None):
        body = ProposalAction.model_validate(value)
        with self.documents.store.transaction(nid, scope) as state:
            row = self._owned(nid, scope, actor, rid, state)
            check_version(row, body.expected_version)
            guard()
            if row["status"] == "APPROVED":
                raise ValueError("ADAPTATION_ALREADY_APPROVED")
            execution = deepcopy(row.get("model_execution"))
            if execution:
                execution["status"] = "CANCELLED"
            change_row(row, actor, row["version"], lambda item: item.update(status="CANCELLED",
                output=None, output_digest=None, model_preview=None, provenance=None, model_execution=execution))
            self._capacity(state)
            guard()
            result = self._public(row)
        if execution and self.generation:
            try:
                self.generation.manager.cancel(execution["job_id"])
            except KeyError:
                pass
        return result
