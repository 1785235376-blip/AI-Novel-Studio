"""Storyboard operations on the original Creative, Asset and Timeline owners.

Shot revisions are derived from the original document history. Bindings store
only exact formal asset references. This adapter owns no collection or media.
"""
from __future__ import annotations

import copy
import hashlib
from contextlib import nullcontext
from typing import Literal

from pydantic import Field

from ..experimental.common import StaleSourceError, change_row, check_version, now
from ..experimental.store import canonical
from .models import CreativeProductionDocumentIn, Identifier, StrictCreativeModel
from .graph_models import AssetParameters
from .production_execution_models import ProviderSelection, MediaExecutionParameters


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def storyboard_content_digest(row):
    """Approval covers authored content, not clocks or the approval itself."""
    return digest({name: row[name] for name in CreativeProductionDocumentIn.model_fields if name in row})


def shot_versions(row):
    """Count changes and deletion/recreation using retained original history."""
    versions, previous = {}, {}
    history = row.get("history", [])
    if not isinstance(history, list) or len(history) > 200:
        raise ValueError("CREATIVE_STORYBOARD_HISTORY_CORRUPT")
    snapshots = [*history, row]
    last = 0
    for snapshot in snapshots:
        if (not isinstance(snapshot, dict) or type(snapshot.get("version")) is not int
                or snapshot["version"] <= last or snapshot.get("id") != row.get("id")):
            raise ValueError("CREATIVE_STORYBOARD_HISTORY_CORRUPT")
        last = snapshot["version"]
        shots = snapshot.get("shots")
        if not isinstance(shots, list) or len(shots) > 200:
            raise ValueError("CREATIVE_STORYBOARD_HISTORY_CORRUPT")
        current = {shot["id"]: digest(shot) for shot in shots}
        if len(current) != len(shots):
            raise ValueError("CREATIVE_STORYBOARD_HISTORY_CORRUPT")
        for shot_id, value in current.items():
            if previous.get(shot_id) != value:
                versions[shot_id] = versions.get(shot_id, 0) + 1
        previous = current
    return {shot_id: versions[shot_id] for shot_id in previous}


def storyboard_approved(row):
    approval = row.get("storyboard_approval")
    if approval is None:
        return False
    if (not isinstance(approval, dict) or set(approval) != {"contract", "version", "content_digest", "approved_by", "approved_at"}
            or approval.get("contract") != "studio-storyboard-approval/1"
            or type(approval.get("version")) is not int
            or approval["version"] != row.get("version")
            or approval.get("content_digest") != storyboard_content_digest(row)
            or not isinstance(approval.get("approved_by"), str) or not approval["approved_by"]
            or not isinstance(approval.get("approved_at"), str) or not approval["approved_at"]):
        raise StaleSourceError("CREATIVE_STORYBOARD_APPROVAL_CHANGED")
    return True


def invalidate_storyboard(row, payload):
    """Content edits revoke approval; unaffected image bindings may remain."""
    row.pop("storyboard_approval", None)
    bindings = row.get("storyboard_image_bindings")
    if bindings is not None:
        current = {shot["id"]: digest(shot) for shot in payload.get("shots", [])}
        row["storyboard_image_bindings"] = {
            shot_id: copy.deepcopy(binding) for shot_id, binding in bindings.items()
            if isinstance(binding, dict) and binding.get("shot_digest") == current.get(shot_id)}


def storyboard_receipt(row):
    """Pure validated projection; caller owns scope/source/asset fences."""
    from .service import document_digest
    from .graph_models import AssetParameters
    if row.get("mode") != "STORYBOARD":
        raise ValueError("CREATIVE_STORYBOARD_MODE_REQUIRED")
    body = CreativeProductionDocumentIn.model_validate({key: row[key] for key in CreativeProductionDocumentIn.model_fields if key in row})
    versions = shot_versions(row)
    bindings = row.get("storyboard_image_bindings", {})
    if not isinstance(bindings, dict) or set(bindings) - set(versions):
        raise ValueError("CREATIVE_STORYBOARD_BINDINGS_CORRUPT")
    shots = []
    for shot in sorted(body.shots, key=lambda item: item.number):
        value = shot.model_dump()
        bound = bindings.get(shot.id)
        image = None
        if bound is not None:
            if (not isinstance(bound, dict) or set(bound) != {"shot_id", "shot_version", "shot_digest", "asset"}
                    or bound["shot_id"] != shot.id or type(bound["shot_version"]) is not int
                    or bound["shot_version"] != versions[shot.id] or bound["shot_digest"] != digest(value)):
                raise StaleSourceError("CREATIVE_STORYBOARD_IMAGE_BINDING_CHANGED")
            image = AssetParameters.model_validate(bound["asset"]).model_dump()
            if image["kind"] != "image":
                raise ValueError("CREATIVE_STORYBOARD_IMAGE_REQUIRED")
        shots.append({"shot_id": shot.id, "shot_version": versions[shot.id], "shot_digest": digest(value),
                      "shot": value, "image_asset": image})
    return {"contract": "studio-storyboard/1", "document_snapshot": {"id": row["id"], "version": row["version"], "digest": document_digest(row)},
            "content_digest": storyboard_content_digest(row), "approved": storyboard_approved(row), "shots": shots,
            "director_sources": [{"id": key, **copy.deepcopy(value)} for key, value in sorted(row.get("source_documents", {}).items())],
            "model_called": False, "product_acceptance": "LOCAL_REQUIRED"}


class StoryboardApproval(StrictCreativeModel):
    expected_version: int = Field(ge=1, strict=True)
    reviewed_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class ShotAction(StrictCreativeModel):
    expected_version: int = Field(ge=1, strict=True)
    shot_version: int = Field(ge=1, strict=True)
    shot_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class ShotImageBinding(ShotAction):
    asset: AssetParameters


class ShotImageRequest(ShotAction):
    operation_id: Literal["m5.image.t2i", "m5.image.i2i", "m5.image.reference"] = "m5.image.t2i"
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)
    provider: ProviderSelection
    parameters: MediaExecutionParameters = Field(default_factory=MediaExecutionParameters)


class StoryboardTimelineDraft(StoryboardApproval):
    title: str = Field(min_length=1, max_length=240, strict=True)
    shot_ids: list[Identifier] = Field(min_length=1, max_length=30)
    width: int = Field(default=1280, ge=16, le=1920, strict=True)
    height: int = Field(default=720, ge=16, le=1080, strict=True)
    fps: int = Field(default=24, ge=1, le=60, strict=True)


class OriginalSnapshot(StrictCreativeModel):
    id: Identifier
    version: int = Field(ge=1, strict=True)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class ClipShotOrigin(StrictCreativeModel):
    clip_id: Identifier
    shot_id: Identifier
    shot_version: int = Field(ge=1, strict=True)
    shot_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class StoryboardTimelineOrigin(StrictCreativeModel):
    contract: Literal["studio-storyboard-timeline-draft/1"]
    document_snapshot: OriginalSnapshot
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    timeline_snapshot: OriginalSnapshot
    shots: list[ClipShotOrigin] = Field(min_length=1, max_length=30)
    model_called: Literal[False]
    rendered: Literal[False]


def validate_storyboard_timeline_origin(row, *, history=None):
    """Validate original creation provenance without reopening other owners."""
    body = StoryboardTimelineOrigin.model_validate(row["storyboard_origin"])
    if (row["storyboard_origin"].get("model_called") is not False
            or row["storyboard_origin"].get("rendered") is not False):
        raise ValueError("CREATIVE_STORYBOARD_TIMELINE_ORIGIN_CORRUPT")
    ancestors = row.get("history", []) if history is None else history
    original = next((snapshot for snapshot in [*ancestors, row]
                     if snapshot.get("version") == body.timeline_snapshot.version), None)
    if (original is None or body.timeline_snapshot.id != row["id"]
            or original.get("id") != row["id"]
            or original["timeline_digest"] != body.timeline_snapshot.digest
            or digest(original["timeline"]) != body.timeline_snapshot.digest):
        raise StaleSourceError("CREATIVE_STORYBOARD_TIMELINE_ORIGIN_CHANGED")
    clips = [clip["id"] for track in original["timeline"]["tracks"] for clip in track["clips"]]
    if (len({shot.shot_id for shot in body.shots}) != len(body.shots)
            or [shot.clip_id for shot in body.shots] != clips):
        raise ValueError("CREATIVE_STORYBOARD_TIMELINE_ORIGIN_CORRUPT")
    return body.model_dump()


class StoryboardWorkspace:
    def __init__(self, creative):
        self.creative = creative
        self.production = None

    def _phase(self, nid, scope, actor, guard, *, write=False):
        if self.production is not None:
            return self.production.timeline_inputs.phase(nid, scope, actor, guard, writable=write)
        return self.creative.store.transaction(nid, scope) if write else nullcontext()

    def _formal_images(self, nid, scope, receipt, guard):
        images = [shot["image_asset"] for shot in receipt["shots"] if shot["image_asset"] is not None]
        if images and self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_ASSET_OWNER_REQUIRED")
        for image in images:
            self.production.timeline_inputs._read(nid, scope, image, guard)

    def get(self, nid, scope, actor, rid, guard=lambda: None):
        with self._phase(nid, scope, actor, guard):
            guard()
            result = storyboard_receipt(self.creative.get(nid, scope, rid))
            self._formal_images(nid, scope, result, guard)
            guard()
            return result

    def _owned_shot(self, row, shot_id, body):
        check_version(row, body.expected_version)
        receipt = storyboard_receipt(row)
        shot = next((shot for shot in receipt["shots"] if shot["shot_id"] == shot_id), None)
        if shot is None:
            raise FileNotFoundError(shot_id)
        if (shot["shot_version"], shot["shot_digest"]) != (body.shot_version, body.shot_digest):
            raise StaleSourceError("CREATIVE_STORYBOARD_SHOT_CHANGED")
        return receipt, shot

    def approve(self, nid, scope, actor, rid, value, guard=lambda: None):
        body = StoryboardApproval.model_validate(value)
        with self._phase(nid, scope, actor, guard, write=True):
            guard()
            row = self.creative.get(nid, scope, rid)
            check_version(row, body.expected_version)
            receipt = storyboard_receipt(row)
            if not receipt["shots"] or receipt["content_digest"] != body.reviewed_content_digest:
                raise StaleSourceError("CREATIVE_STORYBOARD_REVIEW_CHANGED")
            self._formal_images(nid, scope, receipt, guard)
            approval = {"contract": "studio-storyboard-approval/1", "version": row["version"] + 1,
                        "content_digest": receipt["content_digest"], "approved_by": actor, "approved_at": now()}
            state = self.creative.store.read(nid, scope)
            current = state["collections"][self.creative.COLLECTION][rid]
            change_row(current, actor, body.expected_version, lambda target: target.update(storyboard_approval=approval))
            # read() is detached even in a lease. Write to the existing active
            # view, never a second transaction under asset/project locks.
            key = self.creative.store.key(nid, scope)
            self.creative.store._local.active[key]["collections"][self.creative.COLLECTION][rid] = current
            self.creative.assert_capacity(self.creative.store._local.active[key])
            guard()
            return storyboard_receipt(current)

    def bind_image(self, nid, scope, actor, rid, shot_id, value, guard=lambda: None):
        from .graph_models import AssetParameters
        body = ShotImageBinding.model_validate(value)
        image = body.asset.model_dump()
        if image["kind"] != "image" or self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_FORMAL_IMAGE_REQUIRED")
        with self._phase(nid, scope, actor, guard, write=True):
            guard()
            row = self.creative.get(nid, scope, rid)
            _, shot = self._owned_shot(row, shot_id, body)
            self.production.timeline_inputs._read(nid, scope, image, guard)
            key = self.creative.store.key(nid, scope)
            state = self.creative.store._local.active[key]
            current = state["collections"][self.creative.COLLECTION][rid]
            binding = {"shot_id": shot_id, "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"], "asset": image}
            def attach(target):
                target.pop("storyboard_approval", None)
                target.setdefault("storyboard_image_bindings", {})[shot_id] = binding
            change_row(current, actor, body.expected_version, attach)
            self.creative.assert_capacity(state)
            guard()
            return storyboard_receipt(current)

    def image_request(self, nid, scope, actor, rid, shot_id, value, guard=lambda: None):
        from .production_execution_models import MediaCommand
        body = ShotImageRequest.model_validate(value)
        with self._phase(nid, scope, actor, guard):
            row = self.creative.get(nid, scope, rid)
            receipt, shot = self._owned_shot(row, shot_id, body)
            self._formal_images(nid, scope, receipt, guard)
            content = shot["shot"]
            prompt = content["frame_prompt"].strip() or content["action"].strip()
            if not prompt:
                raise ValueError("CREATIVE_STORYBOARD_IMAGE_PROMPT_REQUIRED")
            pin = receipt["document_snapshot"]
            sources = [{"kind": "CREATIVE_DOCUMENT", **pin, "asset_kind": None, "reference_only": True}]
            if body.provider.operation_id != body.operation_id:
                raise ValueError("CREATIVE_STORYBOARD_IMAGE_PROVIDER_OPERATION_INVALID")
            command = {"operation_id": body.operation_id, "request_id": body.request_id, "prompt": prompt,
                       "provider_id": body.provider.provider_id, "model_id": body.provider.model_id,
                       "parameters": body.parameters.model_dump(), "source_snapshots": sources}
            if body.operation_id != "m5.image.t2i":
                image = shot["image_asset"]
                if image is None:
                    raise ValueError("CREATIVE_STORYBOARD_IMAGE_REFERENCE_REQUIRED")
                source = {"kind": "ASSET", "id": image["asset_id"], "version": image["version"], "digest": image["digest"],
                          "asset_kind": "image", "reference_only": True}
                command["source_snapshots"].append(source)
                if body.operation_id == "m5.image.i2i":
                    command["image_source"] = source
                else:
                    command["image_references"] = [{"source": source, "weight": 1.0, "purpose": "composition"}]
            result = MediaCommand.model_validate(command).model_dump()
            guard()
            return {"contract": "studio-storyboard-image-request/1", "shot_pin": {"document_snapshot": pin,
                "shot_id": shot_id, "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"]},
                "command": result, "automatic_dispatch": False, "model_called": False,
                "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW", "product_acceptance": "LOCAL_REQUIRED"}

    def timeline_draft(self, nid, scope, actor, rid, value, guard=lambda: None):
        from .production_execution import TIMELINES
        body = StoryboardTimelineDraft.model_validate(value)
        if self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_TIMELINE_OWNER_REQUIRED")
        if len(set(body.shot_ids)) != len(body.shot_ids):
            raise ValueError("CREATIVE_STORYBOARD_TIMELINE_DUPLICATE_SHOT")
        self.production._base(nid, scope, actor, guard)
        with self._phase(nid, scope, actor, guard, write=True) as state:
            row = self.creative.get(nid, scope, rid)
            check_version(row, body.expected_version)
            receipt = storyboard_receipt(row)
            if not receipt["approved"] or receipt["content_digest"] != body.reviewed_content_digest:
                raise StaleSourceError("CREATIVE_STORYBOARD_APPROVAL_REQUIRED")
            by_id = {shot["shot_id"]: shot for shot in receipt["shots"]}
            if set(body.shot_ids) - set(by_id):
                raise ValueError("CREATIVE_STORYBOARD_TIMELINE_UNKNOWN_SHOT")
            ordered = [shot for shot in receipt["shots"] if shot["shot_id"] in body.shot_ids]
            clips, mapping, start = [], [], 0
            for index, shot in enumerate(ordered):
                image = shot["image_asset"]
                if image is None:
                    raise ValueError("CREATIVE_STORYBOARD_TIMELINE_IMAGE_REQUIRED")
                duration = shot["shot"]["duration_seconds"] * 1000
                clip_id = f"storyboard-{index + 1}"
                clips.append({"id": clip_id, "source_snapshot": {"kind": "ASSET", "id": image["asset_id"],
                    "asset_kind": "image", "version": image["version"], "digest": image["digest"]},
                    "start_ms": start, "in_ms": 0, "out_ms": duration, "include_audio": False})
                mapping.append({"clip_id": clip_id, "shot_id": shot["shot_id"], "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"]})
                start += duration
            if start > 600_000:
                raise ValueError("CREATIVE_STORYBOARD_TIMELINE_DURATION_LIMIT")
            timeline = {"schema_version": 2, "duration_ms": start, "width": body.width, "height": body.height,
                "fps": body.fps, "tracks": [{"id": "storyboard-video", "kind": "VIDEO", "order": 0, "clips": clips}], "captions": []}
            result = self.production.timeline_save(nid, scope, actor, None,
                {"expected_version": 0, "title": body.title, "timeline": timeline}, guard)
            proof = {"contract": "studio-storyboard-timeline-draft/1", "document_snapshot": receipt["document_snapshot"],
                     "content_digest": receipt["content_digest"], "shots": mapping,
                     "timeline_snapshot": {"id": result["id"], "version": result["version"], "digest": result["timeline_digest"]},
                     "model_called": False, "rendered": False}
            state["collections"][TIMELINES][result["id"]]["storyboard_origin"] = copy.deepcopy(proof)
            result = self.production._timeline_view(state["collections"][TIMELINES][result["id"]], scope)
            self.production._capacity(state)
            guard()
            return {"contract": "studio-storyboard-timeline-draft/1", "timeline": result, "storyboard_origin": proof,
                    "automatic_dispatch": False, "model_called": False, "rendered": False, "product_acceptance": "LOCAL_REQUIRED"}

    def director_advice(self, nid, scope, rid):
        from .service import document_digest
        row = self.creative.get(nid, scope, rid)
        if row["mode"] != "DIRECTOR":
            raise ValueError("CREATIVE_DIRECTOR_MODE_REQUIRED")
        target = row.get("visual_target", {})
        notes = []
        for note in row.get("director_notes", []):
            notes.append({"note_id": note["id"], "scene_id": note["scene_id"],
                "camera": {"shot_size": note["shot_size"], "angle": note["camera_angle"], "movement": note["camera_motion"],
                           "lens": note.get("lens") or "", "composition": note.get("composition") or ""},
                "visual_style": {"color": note.get("color_palette") or target.get("color", ""), "lighting": note.get("lighting") or "",
                                 "material": note.get("material") or "", "style": target.get("style", "")},
                "rhythm": {"pacing": note["pacing"] or target.get("rhythm", ""), "duration_seconds": note["duration_seconds"],
                           "transition": note.get("transition") or ""}})
        return {"contract": "studio-director-advice/1", "document_snapshot": {"id": rid, "version": row["version"], "digest": document_digest(row)},
                "notes": notes, "advice_only": True, "automatic_apply": False, "model_called": False, "product_acceptance": "LOCAL_REQUIRED"}
