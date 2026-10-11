"""Stateless Graph adapters of the original editable timeline and queue owners.

Preview compiles only closed author operations and exact formal ASSET_REFs.
The Graph's original raw transaction commits the edit and node claim together;
the original assembly owner is queued afterwards, with no native execution.
"""
from copy import deepcopy
from typing import Literal

from pydantic import Field, model_validator

from ..experimental.common import StaleSourceError, change_row
from ..services.studio_timeline_edit import apply_timeline_edits
from ..services.studio_timeline_export import export_profile_digest, validate_export_admission
from ..services.studio_timeline_render import normalize_studio_timeline, studio_sources
from .graph_models import AssetParameters, TimelineNodeParameters, TimelineSourceBinding
from .production_execution_models import TimelineEdit
from .production_execution import digest


class ResolvedTimelineSource(TimelineSourceBinding):
    asset: AssetParameters


class GraphTimelineCommand(TimelineNodeParameters):
    operation_id: Literal["m9.timeline.multitrack"] = "m9.timeline.multitrack"
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    source_bindings: list[ResolvedTimelineSource] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def bounded_original_batch(self):
        if len(self.edit_operations) + len(self.source_bindings) > 40:
            raise ValueError("STUDIO_TIMELINE_EDIT_OPERATION_LIMIT")
        return self


class GraphTimelineExecution:
    """No collections or scheduler: every write stays in original TIMELINES."""

    def __init__(self, production):
        self.owner = production

    def _base(self, nid, scope, actor, snapshot, document, guard):
        context = self.owner._base(nid, scope, actor, guard)
        row = self.owner._owned_timeline(nid, scope, actor, snapshot["id"], context, document)
        if (row["version"], row["timeline_digest"]) != (snapshot["version"], snapshot["digest"]):
            raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        return row, context

    def _sources(self, nid, scope, timeline, guard):
        self.owner._timeline_sources_current(nid, scope, timeline, guard)
        from ..services.studio_timeline_render import MAX_SOURCE_BYTES
        total = sum(self.owner.workspace._row(nid, scope, source["id"])["size"] for source in studio_sources(timeline))
        if total > MAX_SOURCE_BYTES:
            raise ValueError("STUDIO_TIMELINE_SOURCE_BYTES_LIMIT")

    @staticmethod
    def _clips(timeline):
        return {clip["id"]: (track, clip) for track in timeline["tracks"] for clip in track["clips"]}

    @staticmethod
    def _kind(timeline, track, kind):
        allowed = {"audio"} if track["kind"] == "AUDIO" else (
            {"video", "image"} if timeline.get("schema_version") == 2 else {"video"})
        if kind not in allowed:
            raise ValueError("CREATIVE_GRAPH_TIMELINE_SOURCE_KIND_MISMATCH")

    def preflight(self, nid, scope, actor, parameters, guard, *, document, source_kinds):
        body = TimelineNodeParameters.model_validate(parameters)
        row, _ = self._base(nid, scope, actor, body.timeline_snapshot.model_dump(), document, guard)
        timeline = apply_timeline_edits(row["timeline"], body.edit_operations) if body.edit_operations else deepcopy(row["timeline"])
        clips = self._clips(timeline)
        bindings = {binding.port: binding.clip_id for binding in body.source_bindings}
        if set(bindings) != set(source_kinds) or len(body.edit_operations) + len(bindings) > 40:
            raise ValueError("CREATIVE_GRAPH_TIMELINE_SOURCE_BINDING_REQUIRED")
        for port, clip_id in bindings.items():
            if clip_id not in clips:
                raise ValueError("STUDIO_TIMELINE_EDIT_CLIP_NOT_FOUND")
            self._kind(timeline, clips[clip_id][0], source_kinds[port])
        # Future media_review outputs have no asset identity yet. Only the
        # unchanged sources are checked here; preview checks all resolved bytes.
        for track in timeline["tracks"]:
            for clip in track["clips"]:
                if clip["id"] not in bindings.values():
                    self.owner._timeline_sources_current(nid, scope, {"tracks": [{"clips": [clip]}]}, guard)
        validate_export_admission(timeline, body.export_profile, self.owner.workspace.assets.MAX_BYTES)
        if (body.edit_operations or bindings) and len(row["history"]) >= 100:
            raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")
        if (body.edit_operations or bindings) and row["version"] >= 2**53 - 1:
            raise ValueError("STUDIO_TIMELINE_VERSION_LIMIT")
        return timeline

    @staticmethod
    def operations(command):
        return deepcopy(command.edit_operations) + [{"op": "clip.update", "clip_id": binding.clip_id,
            "changes": {"source_snapshot": {"kind": "ASSET", "id": binding.asset.asset_id,
                "version": binding.asset.version, "digest": binding.asset.digest, "asset_kind": binding.asset.kind}}}
            for binding in command.source_bindings]

    def prepare(self, nid, scope, actor, value, guard, *, document, graph_binding):
        from .graph_media_binding import validate_graph_binding
        command = GraphTimelineCommand.model_validate(value)
        snapshot = command.timeline_snapshot.model_dump()
        row, context = self._base(nid, scope, actor, snapshot, document, guard)
        operations = self.operations(command)
        timeline = apply_timeline_edits(row["timeline"], operations) if operations else deepcopy(row["timeline"])
        self._sources(nid, scope, timeline, guard)
        if operations and len(row["history"]) >= 100:
            raise ValueError("STUDIO_TIMELINE_HISTORY_LIMIT")
        if operations and row["version"] >= 2**53 - 1:
            raise ValueError("STUDIO_TIMELINE_VERSION_LIMIT")
        profile = command.export_profile
        validate_export_admission(timeline, profile, self.owner.workspace.assets.MAX_BYTES)
        final = {"id": snapshot["id"], "version": snapshot["version"] + bool(operations), "digest": digest(timeline)}
        proof = None
        if operations:
            edit = TimelineEdit(expected_version=snapshot["version"], reviewed_timeline_digest=snapshot["digest"],
                request_id=command.request_id, operations=operations)
            proof = {"request_id": command.request_id, "request_digest": digest(edit.model_dump()),
                "input_version": snapshot["version"], "input_digest": snapshot["digest"], "output_digest": final["digest"]}
        recipe = {"contract": "studio-execution-recipe/1", "operation_id": command.operation_id,
            "adapter": "LOCAL_FFMPEG", "output_profile": profile["preset"],
            "timeline": timeline, "export_profile": deepcopy(profile), "automatic_fallback": False}
        recipe["recipe_digest"] = digest(recipe)
        context.update(graph_binding=validate_graph_binding(graph_binding, context), request_id=command.request_id,
            operation_id=command.operation_id, sources=studio_sources(timeline), provider_binding=None,
            license_note="", rights={"license_note": ""}, execution_recipe=recipe,
            timeline_snapshot=final, source_timeline_snapshot=snapshot, timeline_edit_proof=proof,
            export_profile=deepcopy(profile), export_profile_digest=export_profile_digest(profile))
        if context["graph_binding"] is None or context["graph_binding"]["command_digest"] != digest(command.model_dump()):
            raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_COMMAND_BINDING_CHANGED")
        context["request_digest"] = digest({"context": context, "command": command.model_dump()})
        preview = {"contract": "studio-production-preview/1", "novel_id": nid, "branch_id": scope.get("branch_id"),
            "operation_id": command.operation_id, "request_id": command.request_id, "request_digest": context["request_digest"],
            "provider": None, "sources": [{"snapshot": deepcopy(source), "measured": None} for source in context["sources"]],
            "execution_recipe": deepcopy(recipe), "command": command.model_dump(), "product_acceptance": "LOCAL_REQUIRED",
            "execution_available": True, "automatic_dispatch": False, "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW",
            "timeline_snapshot": deepcopy(final), "source_timeline_snapshot": deepcopy(snapshot),
            "timeline_edit_proof": deepcopy(proof), "export_profile": deepcopy(profile)}
        preview["preview_digest"] = digest(preview)
        guard()
        return preview, context, command

    def context(self, nid, scope, actor, preview, graph_binding, incarnation):
        """Reconstruct only the immutable server preview, without base replay."""
        self.validate_preview(preview)
        if preview["novel_id"] != nid or preview["branch_id"] != scope.get("branch_id"):
            raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_SCOPE_CHANGED")
        from .graph_media_binding import validate_graph_binding
        context = {"actor": actor, "scope_key": self.owner.store.key(nid, scope), "incarnation": incarnation}
        context.update(graph_binding=validate_graph_binding(graph_binding, context), request_id=preview["request_id"],
            operation_id="m9.timeline.multitrack", sources=[deepcopy(row["snapshot"]) for row in preview["sources"]],
            provider_binding=None, license_note="", rights={"license_note": ""}, execution_recipe=deepcopy(preview["execution_recipe"]),
            timeline_snapshot=deepcopy(preview["timeline_snapshot"]), source_timeline_snapshot=deepcopy(preview["source_timeline_snapshot"]),
            timeline_edit_proof=deepcopy(preview["timeline_edit_proof"]), export_profile=deepcopy(preview["export_profile"]),
            export_profile_digest=export_profile_digest(preview["export_profile"]))
        if context["graph_binding"] is None or context["graph_binding"]["command_digest"] != digest(preview["command"]):
            raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_COMMAND_BINDING_CHANGED")
        if preview["request_digest"] != digest({"context": context, "command": preview["command"]}):
            raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_REQUEST_CHANGED")
        context["request_digest"] = preview["request_digest"]
        return context

    @staticmethod
    def validate_preview(preview):
        """Pure stored preview proof; no scope, asset, queue or native reads."""
        try:
            command = GraphTimelineCommand.model_validate(preview["command"])
            recipe = preview["execution_recipe"]
            timeline = normalize_studio_timeline(recipe["timeline"])
            final, base = preview["timeline_snapshot"], command.timeline_snapshot.model_dump()
            operations = GraphTimelineExecution.operations(command)
            proof = None if not operations else {"request_id": command.request_id,
                "request_digest": digest(TimelineEdit(expected_version=base["version"], reviewed_timeline_digest=base["digest"],
                    request_id=command.request_id, operations=operations).model_dump()),
                "input_version": base["version"], "input_digest": base["digest"], "output_digest": digest(timeline)}
            expected_recipe = {"contract": "studio-execution-recipe/1", "operation_id": command.operation_id,
                "adapter": "LOCAL_FFMPEG", "output_profile": command.export_profile["preset"], "timeline": timeline,
                "export_profile": command.export_profile, "automatic_fallback": False}
            expected_recipe["recipe_digest"] = digest(expected_recipe)
            expected = {"contract", "novel_id", "branch_id", "operation_id", "request_id", "request_digest", "provider", "sources",
                "execution_recipe", "command", "product_acceptance", "execution_available", "automatic_dispatch", "output_policy",
                "timeline_snapshot", "source_timeline_snapshot", "timeline_edit_proof", "export_profile", "preview_digest"}
            if (set(preview) != expected or preview["contract"] != "studio-production-preview/1"
                    or preview["command"] != command.model_dump() or preview["operation_id"] != command.operation_id
                    or preview["request_id"] != command.request_id or preview["provider"] is not None
                    or preview["product_acceptance"] != "LOCAL_REQUIRED" or preview["execution_available"] is not True
                    or preview["automatic_dispatch"] is not False or preview["output_policy"] != "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW"
                    or recipe != expected_recipe or preview["source_timeline_snapshot"] != base
                    or final != {"id": base["id"], "version": base["version"] + bool(operations), "digest": digest(timeline)}
                    or preview["timeline_edit_proof"] != proof or preview["export_profile"] != command.export_profile
                    or preview["sources"] != [{"snapshot": source, "measured": None} for source in studio_sources(timeline)]
                    or preview["preview_digest"] != digest({key: value for key, value in preview.items() if key != "preview_digest"})):
                raise ValueError("CREATIVE_GRAPH_TIMELINE_PREVIEW_CHANGED")
        except (KeyError, TypeError, ValueError) as error:
            raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_PREVIEW_CHANGED") from error

    def commit(self, nid, scope, actor, preview, graph_binding, guard, *, document):
        # Called only by the original Graph writable raw+asset transaction.
        fresh, context, command = self.prepare(nid, scope, actor, preview["command"], guard,
            document=document, graph_binding=graph_binding)
        if fresh != preview:
            raise StaleSourceError("STUDIO_PRODUCTION_PREVIEW_CHANGED")
        proof = context["timeline_edit_proof"]
        if proof is not None:
            row = self.owner._owned_timeline(nid, scope, actor, context["timeline_snapshot"]["id"], context, document)
            if (row.get("last_edit") or {}).get("request_id") == command.request_id or any(
                    (entry.get("last_edit") or {}).get("request_id") == command.request_id for entry in row["history"]):
                raise ValueError("STUDIO_TIMELINE_EDIT_IDEMPOTENCY_CONFLICT")
            change_row(row, actor, command.timeline_snapshot.version, lambda current: current.update(
                timeline=deepcopy(context["execution_recipe"]["timeline"]), timeline_digest=proof["output_digest"], last_edit=deepcopy(proof)))
        self.owner._capacity(document)
        self.current(nid, scope, actor, context, document, guard, assets=True)
        return context

    def current(self, nid, scope, actor, context, document, guard, *, assets=False):
        row = self.owner._timeline_context_current(nid, scope, actor, context, document)
        base, final, proof = context["source_timeline_snapshot"], context["timeline_snapshot"], context["timeline_edit_proof"]
        if row["timeline"] != context["execution_recipe"]["timeline"]:
            raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_CHANGED")
        if proof is None:
            if base != final:
                raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_EDIT_RECEIPT_CHANGED")
        elif (row.get("last_edit") != proof or final["version"] != base["version"] + 1 or base["id"] != final["id"]
                or not any(entry.get("version") == base["version"] and entry.get("timeline_digest") == base["digest"]
                    for entry in row["history"])):
            raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_EDIT_RECEIPT_CHANGED")
        if assets:
            self._sources(nid, scope, row["timeline"], guard)
        guard()
        return row
