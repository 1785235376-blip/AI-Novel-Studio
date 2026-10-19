"""Storyboard operations on the original Creative, Asset and Timeline owners.

Shot revisions are derived from the original document history. Bindings store
only exact formal asset references. This adapter owns no collection or media.
"""
from __future__ import annotations

import copy
import hashlib
import re
from contextlib import nullcontext
from typing import Literal

from pydantic import Field

from ..experimental.common import StaleSourceError, change_row, check_version, now
from ..experimental.store import canonical
from .models import CreativeProductionDocumentIn, Identifier, StrictCreativeModel
from .graph_models import AssetParameters
from .production_execution_models import (ProviderSelection, MediaExecutionParameters,
    StoryboardShotPin, MediaCommand, TimelineEdit)
from .production_contracts import Name


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
    videos = row.get("storyboard_video_bindings")
    if videos is not None:
        current = {shot["id"]: digest(shot) for shot in payload.get("shots", [])}
        row["storyboard_video_bindings"] = {
            shot_id: copy.deepcopy(binding) for shot_id, binding in videos.items()
            if isinstance(binding, dict) and binding.get("shot_digest") == current.get(shot_id)}


def validate_shot_pin(row, value, *, historical=False):
    """Validate an original approved snapshot without opening another owner."""
    from .service import document_digest
    pin = StoryboardShotPin.model_validate(value)
    snapshot = row
    if historical:
        candidates = [item for item in [*row.get("history", []), row]
                      if item.get("version") == pin.document_snapshot.version]
        if len(candidates) != 1:
            raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_SOURCE_CHANGED")
        snapshot = copy.deepcopy(candidates[0])
        snapshot["history"] = [copy.deepcopy(item) for item in row.get("history", [])
                               if item["version"] < snapshot["version"]]
    if (snapshot.get("id") != pin.document_snapshot.id or snapshot.get("mode") != "STORYBOARD"
            or snapshot.get("status") == "ARCHIVED" or snapshot.get("version") != pin.document_snapshot.version
            or document_digest(snapshot) != pin.document_snapshot.digest or not storyboard_approved(snapshot)):
        raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_SOURCE_CHANGED")
    body = CreativeProductionDocumentIn.model_validate({key: snapshot[key]
        for key in CreativeProductionDocumentIn.model_fields if key in snapshot})
    shot = next((item for item in body.shots if item.id == pin.shot_id), None)
    if shot is None or shot_versions(snapshot).get(pin.shot_id) != pin.shot_version or digest(shot.model_dump()) != pin.shot_digest:
        raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_SHOT_CHANGED")
    return shot


def validate_video_command(row, command):
    """Original current approval and exact bound first frame before admission."""
    pin = command.storyboard_shot
    shot = validate_shot_pin(row, pin)
    if command.parameters.duration_seconds is None or command.parameters.duration_seconds != shot.duration_seconds:
        raise ValueError("CREATIVE_STORYBOARD_VIDEO_DURATION_CONFLICT")
    if command.operation_id == "m7.video.i2v":
        item = next(item for item in storyboard_receipt(row)["shots"] if item["shot_id"] == pin.shot_id)
        image = item["image_asset"]
        assets = [item for item in command.source_snapshots if item.kind == "ASSET"]
        if (image is None or len(assets) != 1 or (assets[0].id, assets[0].version, assets[0].digest, assets[0].asset_kind) !=
                (image["asset_id"], image["version"], image["digest"], "image")):
            raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_IMAGE_CHANGED")


def validate_speech_command(row, command):
    """Validate speech against the exact approved original shot, never video semantics."""
    pin = command.storyboard_speech
    if pin is None or command.operation_id != "m8.audio.speech":
        raise ValueError("CREATIVE_STORYBOARD_SPEECH_COMMAND_REQUIRED")
    shot = validate_shot_pin(row, pin.model_dump(exclude={"dialogue_index"}))
    if pin.dialogue_index >= len(shot.dialogue):
        raise ValueError("CREATIVE_STORYBOARD_SPEECH_DIALOGUE_REQUIRED")
    text = shot.dialogue[pin.dialogue_index].text
    if not text.strip() or command.prompt != text:
        raise ValueError("CREATIVE_STORYBOARD_SPEECH_PROMPT_CHANGED")


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
    videos = row.get("storyboard_video_bindings", {})
    if not isinstance(videos, dict) or set(videos) - set(versions):
        raise ValueError("CREATIVE_STORYBOARD_VIDEO_BINDINGS_CORRUPT")
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
        item = {"shot_id": shot.id, "shot_version": versions[shot.id], "shot_digest": digest(value),
                "shot": value, "image_asset": image}
        if shot.id in videos:
            bound = videos[shot.id]
            if (not isinstance(bound, dict) or set(bound) != {"shot_id", "shot_version", "shot_digest", "result"}
                    or bound["shot_id"] != shot.id or type(bound["shot_version"]) is not int
                    or bound["shot_version"] != versions[shot.id] or bound["shot_digest"] != digest(value)):
                raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_BINDING_CHANGED")
            result = StoryboardVideoResult.model_validate(bound["result"])
            validate_shot_pin(row, result.source_shot, historical=True)
            if (result.asset.kind != "video" or result.source_shot.shot_id != shot.id
                    or result.source_shot.shot_version != versions[shot.id] or result.source_shot.shot_digest != digest(value)):
                raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_BINDING_CHANGED")
            item["video_result"] = result.model_dump()
        shots.append(item)
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


class ShotAudioRequest(ShotAction):
    document_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    dialogue_index: int = Field(ge=0, le=199, strict=True)
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)
    provider: ProviderSelection
    voice_id: Name
    speech_rate: float = Field(ge=0.5, le=2, strict=True)


class StoryboardVideoJob(StrictCreativeModel):
    id: Name
    version: int = Field(ge=1, strict=True)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class StoryboardVideoResult(StrictCreativeModel):
    asset: AssetParameters
    source_shot: StoryboardShotPin
    job: StoryboardVideoJob


class ShotVideoBinding(ShotAction):
    asset: AssetParameters
    video_job: StoryboardVideoJob


class ShotVideoRequest(ShotAction):
    operation_id: Literal["m7.video.t2v", "m7.video.i2v"] = "m7.video.t2v"
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)
    provider: ProviderSelection
    parameters: MediaExecutionParameters = Field(default_factory=MediaExecutionParameters)


class StoryboardTimelineDraft(StoryboardApproval):
    title: str = Field(min_length=1, max_length=240, strict=True)
    shot_ids: list[Identifier] = Field(min_length=1, max_length=30)
    width: int = Field(default=1280, ge=16, le=1920, strict=True)
    height: int = Field(default=720, ge=16, le=1080, strict=True)
    fps: int = Field(default=24, ge=1, le=60, strict=True)


class StoryboardTimelineCreate(StoryboardTimelineDraft):
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)


class StoryboardVideoAdoption(ShotAction):
    expected_timeline_version: int = Field(ge=1, strict=True)
    reviewed_timeline_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)
    clip_id: Identifier
    video_asset: AssetParameters
    video_job: StoryboardVideoJob
    in_ms: int = Field(ge=0, le=36_000_000, strict=True)
    out_ms: int = Field(ge=1, le=36_000_000, strict=True)
    include_audio: bool = Field(default=False, strict=True)


class OriginalSnapshot(StrictCreativeModel):
    id: Identifier
    version: int = Field(ge=1, strict=True)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class StoryboardCreationReceipt(StrictCreativeModel):
    contract: Literal["studio-storyboard-timeline-create/1"]
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    document_id: Identifier
    request: StoryboardTimelineCreate
    creation_snapshot: OriginalSnapshot
    origin_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class OriginalTimelineEditReceipt(StrictCreativeModel):
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    input_version: int = Field(ge=1, strict=True)
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class StoryboardAdoptionReceipt(StrictCreativeModel):
    contract: Literal["studio-storyboard-video-adoption/1"]
    document_id: Identifier
    shot_id: Identifier
    timeline_id: Identifier
    request: StoryboardVideoAdoption
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    edit_receipt: OriginalTimelineEditReceipt
    shot_pin: StoryboardShotPin
    video_result: StoryboardVideoResult


def adoption_edit(body):
    asset = body.video_asset
    return TimelineEdit(expected_version=body.expected_timeline_version,
        reviewed_timeline_digest=body.reviewed_timeline_digest, request_id=body.request_id,
        operations=[{"op": "clip.update", "clip_id": body.clip_id, "changes": {
            "source_snapshot": {"kind": "ASSET", "id": asset.asset_id, "version": asset.version,
                                "digest": asset.digest, "asset_kind": "video"},
            "in_ms": body.in_ms, "out_ms": body.out_ms, "include_audio": body.include_audio}}])


def adoption_digest(rid, shot_id, tid, body):
    return digest({"contract": "studio-storyboard-video-adoption/1", "document_id": rid,
                   "shot_id": shot_id, "timeline_id": tid, "request": body.model_dump()})


def validate_adoption_receipt(row, *, history=None):
    """A durable original edit effect, not an authorization to replay a task."""
    from ..services.studio_timeline_edit import apply_timeline_edits
    proof = StoryboardAdoptionReceipt.model_validate(row["storyboard_video_adoption"])
    ancestors = row.get("history", []) if history is None else history
    snapshots = [*[item for item in ancestors if item.get("version") != row["version"]], row]
    before = [item for item in snapshots if item.get("version") == proof.edit_receipt.input_version]
    after = [item for item in snapshots if item.get("version") == proof.edit_receipt.input_version + 1]
    request, pin, result, edit = proof.request, proof.shot_pin, proof.video_result, adoption_edit(proof.request)
    if (proof.timeline_id != row["id"] or proof.request_digest != adoption_digest(proof.document_id, proof.shot_id, proof.timeline_id, request)
            or proof.edit_receipt.request_id != request.request_id or proof.edit_receipt.request_digest != digest(edit.model_dump())
            or proof.edit_receipt.input_version != request.expected_timeline_version
            or proof.edit_receipt.input_digest != request.reviewed_timeline_digest or len(before) != 1 or len(after) != 1
            or digest(before[0]["timeline"]) != proof.edit_receipt.input_digest
            or digest(after[0]["timeline"]) != proof.edit_receipt.output_digest
            or after[0].get("last_edit") != proof.edit_receipt.model_dump()
            or apply_timeline_edits(before[0]["timeline"], edit.operations) != after[0]["timeline"]
            or pin.document_snapshot.id != proof.document_id or pin.document_snapshot.version != request.expected_version
            or (pin.shot_id, pin.shot_version, pin.shot_digest) != (proof.shot_id, request.shot_version, request.shot_digest)
            or result.asset != request.video_asset or result.job != request.video_job):
        raise StaleSourceError("CREATIVE_STORYBOARD_ADOPTION_RECEIPT_CHANGED")
    if row.get("last_edit") != proof.edit_receipt.model_dump() or row["version"] != proof.edit_receipt.input_version + 1:
        return None
    return proof.model_dump()


def creation_digest(rid, body):
    return digest({"contract": "studio-storyboard-timeline-create/1", "document_id": rid, "request": body.model_dump()})


def validate_creation_receipt(row, *, history=None):
    receipt = StoryboardCreationReceipt.model_validate(row["storyboard_create_receipt"])
    origin = validate_storyboard_timeline_origin(row, history=history)
    ancestors = row.get("history", []) if history is None else history
    candidates = [item for item in [*[item for item in ancestors if item.get("version") != row["version"]], row]
                  if item.get("version") == receipt.creation_snapshot.version]
    if (len(candidates) != 1 or receipt.creation_snapshot.id != row["id"]
            or receipt.creation_snapshot.version != 1 or receipt.request_id != receipt.request.request_id
            or receipt.request_digest != creation_digest(receipt.document_id, receipt.request)
            or receipt.origin_digest != digest(origin) or receipt.document_id != origin["document_snapshot"]["id"]
            or receipt.request.expected_version != origin["document_snapshot"]["version"]
            or receipt.request.reviewed_content_digest != origin["content_digest"]
            or receipt.creation_snapshot.model_dump() != origin["timeline_snapshot"]
            or candidates[0]["title"] != receipt.request.title
            or len(set(receipt.request.shot_ids)) != len(receipt.request.shot_ids)
            or set(receipt.request.shot_ids) != {item["shot_id"] for item in origin["shots"]}
            or any(candidates[0]["timeline"][name] != getattr(receipt.request, name) for name in ("width", "height", "fps"))):
        raise StaleSourceError("CREATIVE_STORYBOARD_CREATE_RECEIPT_CHANGED")
    return receipt.model_dump()


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
    def video_timeline_preview(self, *args, **kwargs):
        from .storyboard_video_timeline import preview
        return preview(self, *args, **kwargs)

    def video_timeline_create(self, *args, **kwargs):
        from .storyboard_video_timeline import create
        return create(self, *args, **kwargs)

    def video_timeline_creation(self, *args, **kwargs):
        from .storyboard_video_timeline import recover
        return recover(self, *args, **kwargs)

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
        for item in receipt["shots"]:
            result = item.get("video_result")
            if result is not None:
                self._video_metadata(nid, scope, receipt, result, guard)

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

    @staticmethod
    def _shot_pin(receipt, shot):
        return {"document_snapshot": copy.deepcopy(receipt["document_snapshot"]),
                **{name: shot[name] for name in ("shot_id", "shot_version", "shot_digest")}}

    def audio_request(self, nid, scope, actor, rid, shot_id, value, guard=lambda: None):
        body = ShotAudioRequest.model_validate(value)
        if self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_AUDIO_OWNER_REQUIRED")
        with self._phase(nid, scope, actor, guard):
            row = self.creative.get(nid, scope, rid)
            receipt, shot = self._owned_shot(row, shot_id, body)
            if not receipt["approved"]:
                raise StaleSourceError("CREATIVE_STORYBOARD_APPROVAL_REQUIRED")
            if receipt["document_snapshot"]["digest"] != body.document_digest:
                raise StaleSourceError("CREATIVE_STORYBOARD_AUDIO_SOURCE_CHANGED")
            if body.provider.operation_id != "m8.audio.speech":
                raise ValueError("CREATIVE_STORYBOARD_AUDIO_PROVIDER_OPERATION_INVALID")
            dialogue = shot["shot"]["dialogue"]
            if body.dialogue_index >= len(dialogue) or not dialogue[body.dialogue_index]["text"].strip():
                raise ValueError("CREATIVE_STORYBOARD_SPEECH_DIALOGUE_REQUIRED")
            pin = {**self._shot_pin(receipt, shot), "dialogue_index": body.dialogue_index}
            command = MediaCommand.model_validate({"operation_id": "m8.audio.speech", "request_id": body.request_id,
                "provider_id": body.provider.provider_id, "model_id": body.provider.model_id,
                "parameters": {"voice_id": body.voice_id, "speech_rate": body.speech_rate},
                "source_snapshots": [{"kind": "CREATIVE_DOCUMENT", **pin["document_snapshot"], "reference_only": True}],
                "storyboard_speech": pin, "prompt": dialogue[body.dialogue_index]["text"]})
            validate_speech_command(row, command)
            # Check the existing route and parameter contract without dispatching or creating a job.
            self.production._binding(command)
            self.production._parameters(command)
            guard()
            return {"contract": "studio-storyboard-audio-request/1", "shot_pin": pin, "command": command.model_dump(),
                "automatic_dispatch": False, "model_called": False,
                "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW", "product_acceptance": "LOCAL_REQUIRED"}

    def video_request(self, nid, scope, actor, rid, shot_id, value, guard=lambda: None):
        body = ShotVideoRequest.model_validate(value)
        if self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_VIDEO_OWNER_REQUIRED")
        with self._phase(nid, scope, actor, guard):
            row = self.creative.get(nid, scope, rid)
            receipt, shot = self._owned_shot(row, shot_id, body)
            if not receipt["approved"]:
                raise StaleSourceError("CREATIVE_STORYBOARD_APPROVAL_REQUIRED")
            self._formal_images(nid, scope, receipt, guard)
            if body.provider.operation_id != body.operation_id:
                raise ValueError("CREATIVE_STORYBOARD_VIDEO_PROVIDER_OPERATION_INVALID")
            data = shot["shot"]
            authored = [data["frame_prompt"]]
            for name in ("shot_size", "camera_angle", "camera_motion", "lens", "composition", "action",
                         "emotion", "lighting", "environment", "color", "sound", "sound_effect", "video_generation_hint"):
                if data.get(name) and data[name].strip():
                    authored.append(name + ": " + data[name].strip())
            if data.get("characters"):
                authored.append("characters: " + ", ".join(data["characters"]))
            parameters = body.parameters.model_dump()
            if parameters.get("duration_seconds") not in (None, data["duration_seconds"]):
                raise ValueError("CREATIVE_STORYBOARD_VIDEO_DURATION_CONFLICT")
            parameters["duration_seconds"] = data["duration_seconds"]
            pin = self._shot_pin(receipt, shot)
            sources = [{"kind": "CREATIVE_DOCUMENT", **pin["document_snapshot"], "reference_only": True}]
            if body.operation_id == "m7.video.i2v":
                image = shot["image_asset"]
                if image is None:
                    raise ValueError("CREATIVE_STORYBOARD_VIDEO_IMAGE_REQUIRED")
                sources.append({"kind": "ASSET", "id": image["asset_id"], "version": image["version"],
                                "digest": image["digest"], "asset_kind": "image", "reference_only": True})
            command = MediaCommand.model_validate({"operation_id": body.operation_id, "request_id": body.request_id,
                "provider_id": body.provider.provider_id, "model_id": body.provider.model_id,
                "parameters": parameters, "source_snapshots": sources, "storyboard_shot": pin,
                "prompt": "STORYBOARD_SHOT\n" + "\n".join(authored)})
            validate_video_command(row, command)
            guard()
            return {"contract": "studio-storyboard-video-request/1", "shot_pin": pin, "command": command.model_dump(),
                "automatic_dispatch": False, "model_called": False,
                "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW", "product_acceptance": "LOCAL_REQUIRED"}

    def _graph_video_proof(self, nid, scope, actor, job, guard, *, state=None):
        """Original saved approval receipts only; never reconcile/reexecute a run."""
        from .graph_media_binding import validate_graph_binding
        binding = validate_graph_binding(job["context"].get("graph_binding"), job["context"])
        if binding is None:
            return None
        graph = getattr(self.production, "graph_service", None)
        if graph is None or graph.media_runtime is None:
            raise ValueError("CREATIVE_STORYBOARD_GRAPH_OWNER_REQUIRED")
        row = graph._owned(nid, scope, actor, graph.RUNS, binding["run_id"], state)
        graph.media_runtime.output_authority(row)
        execution = row.get("media_executions", {}).get(binding["node_id"], {})
        if (row.get("graph_id") != binding["graph_id"] or row.get("graph_version") != binding["graph_version"]
                or row.get("graph_digest") != binding["graph_digest"] or row.get("request_digest") != binding["run_request_digest"]
                or execution.get("graph_binding") != binding or execution.get("owner") != "video"
                or execution.get("job_id") != job["id"] or execution.get("request_digest") != job["request_digest"]
                or execution.get("status") != "APPROVED" or execution.get("review_state") != "APPROVED"):
            raise StaleSourceError("CREATIVE_STORYBOARD_GRAPH_APPROVAL_CHANGED")
        graph.media_runtime._validate_job(row, binding["node_id"], execution, self.production.view(job, "video"))
        asset = job["output_candidate"]
        reviews = [edge["target_node_id"] for edge in row["typed_edges"] if edge["source_node_id"] == binding["node_id"]
                   and edge["source_port"] == "candidate" and edge["target_port"] == "candidate"]
        if not any(key in row.get("reviewed_nodes", []) and row["node_states"][key]["status"] == "SUCCEEDED"
                and row.get("typed_outputs", {}).get(key, {}).get("asset") == {"asset_id": asset["id"],
                    "version": job["approved_asset_version"], "digest": asset["digest"], "kind": "video"} for key in reviews):
            raise StaleSourceError("CREATIVE_STORYBOARD_GRAPH_REVIEW_REQUIRED")
        guard()
        return binding

    def _approved_video(self, nid, scope, actor, asset, job_pin, guard):
        """All original queue reads and first native inspection stay outside assets."""
        context = self.production._base(nid, scope, actor, guard)
        job = self.production.video.get(nid, scope.get("branch_id"), actor, job_pin.id, context=context, guard=guard)
        if (job.get("status") != "APPROVED" or job.get("review_state") != "ORIGINAL_OWNER_REVIEWED"
                or any(job.get(name) != getattr(job_pin, name) for name in ("id", "version", "request_digest", "receipt_digest"))):
            raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_APPROVAL_REQUIRED")
        if not job.get("context", {}).get("storyboard_shot"):
            raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_SOURCE_PIN_REQUIRED")
        binding = self._graph_video_proof(nid, scope, actor, job, guard)
        meta, _ = self.production.candidate(nid, scope, actor, "video", job_pin.id, guard, graph_binding=binding)
        if (asset.kind != "video" or (meta["id"], meta["version"], meta["sha256"], meta["kind"]) !=
                (asset.asset_id, asset.version, asset.digest, "video")):
            raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_ASSET_CHANGED")
        return job, {"asset": asset.model_dump(), "source_shot": copy.deepcopy(job["context"]["storyboard_shot"]),
                     "job": job_pin.model_dump()}

    def _video_metadata(self, nid, scope, receipt, result, guard, *, job=None, state=None):
        """Pure metadata/byte checks in the original scope → Asset → project phase."""
        body = StoryboardVideoResult.model_validate(result)
        self.production.timeline_inputs._read(nid, scope, body.asset.model_dump(), guard)
        meta = self.production.workspace.assets.get(body.asset.asset_id, branch_id=scope.get("branch_id"))
        origin = meta.get("_studio_result_origin", {})
        approval = meta.get("_origin_provenance", {})
        if (origin.get("storyboard_shot") != body.source_shot.model_dump() or origin.get("job_id") != body.job.id
                or origin.get("request_digest") != body.job.request_digest or meta.get("source_job_id") != body.job.id
                or approval != {"contract": "studio-production-review/1", "job_id": body.job.id,
                    "request_digest": body.job.request_digest, "output_digest": body.asset.digest,
                    "candidate_version": body.asset.version - 1, "review_actor": origin.get("actor")}
                or origin.get("scope_key") != self.creative.store.key(nid, scope)
                or origin.get("incarnation") != self.creative.store.incarnation(nid)):
            raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_RESULT_CHANGED")
        if job is not None:
            if origin != self.production._media_result_origin(job["context"], job["id"]):
                raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_RESULT_CHANGED")
            self._graph_video_proof(nid, scope, job["context"]["actor"], job, guard, state=state)
        guard()

    def bind_video(self, nid, scope, actor, rid, shot_id, value, guard=lambda: None):
        body = ShotVideoBinding.model_validate(value)
        if self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_VIDEO_OWNER_REQUIRED")
        job, result = self._approved_video(nid, scope, actor, body.asset, body.video_job, guard)
        with self._phase(nid, scope, actor, guard, write=True) as state:
            row = self.creative.get(nid, scope, rid)
            receipt, shot = self._owned_shot(row, shot_id, body)
            pin = StoryboardShotPin.model_validate(result["source_shot"])
            validate_shot_pin(row, pin, historical=True)
            if (pin.document_snapshot.id != rid or (pin.shot_id, pin.shot_version, pin.shot_digest) !=
                    (shot_id, shot["shot_version"], shot["shot_digest"])):
                raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_SHOT_CHANGED")
            self._video_metadata(nid, scope, receipt, result, guard, job=job, state=state)
            current = state["collections"][self.creative.COLLECTION][rid]
            binding = {"shot_id": shot_id, "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"], "result": result}
            def attach(target):
                target.pop("storyboard_approval", None)
                target.setdefault("storyboard_video_bindings", {})[shot_id] = copy.deepcopy(binding)
            change_row(current, actor, body.expected_version, attach)
            self.creative.assert_capacity(state)
            guard()
            return storyboard_receipt(current)

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

    def _creation_matches(self, nid, scope, actor, request_id, context, state):
        from .production_execution import TIMELINES
        matches = []
        for row in state["collections"].get(TIMELINES, {}).values():
            if row.get("created_by") != actor or "storyboard_create_receipt" not in row:
                continue
            self.production._owned_timeline(nid, scope, actor, row["id"], context, state)
            receipt = validate_creation_receipt(row)
            if receipt["request_id"] == request_id:
                matches.append(row)
        if len(matches) > 1:
            raise ValueError("CREATIVE_STORYBOARD_CREATE_RECEIPT_AMBIGUOUS")
        return matches

    def _creation_response(self, row, scope, *, replayed):
        receipt = validate_creation_receipt(row)
        return {"contract": "studio-storyboard-timeline-create/1", "creation_receipt": receipt,
                "timeline": self.production._timeline_view(row, scope),
                "storyboard_origin": copy.deepcopy(row["storyboard_origin"]), "replayed": replayed,
                "automatic_dispatch": False, "model_called": False, "rendered": False, "product_acceptance": "LOCAL_REQUIRED"}

    def timeline_create(self, nid, scope, actor, rid, value, guard=lambda: None):
        """Explicit additive request identity on the existing Timeline row."""
        from .production_execution import TIMELINES
        body = StoryboardTimelineCreate.model_validate(value)
        if self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_TIMELINE_OWNER_REQUIRED")
        context = self.production._base(nid, scope, actor, guard)
        with self._phase(nid, scope, actor, guard, write=True) as state:
            matches = self._creation_matches(nid, scope, actor, body.request_id, context, state)
            if matches:
                receipt = validate_creation_receipt(matches[0])
                if receipt["document_id"] != rid or receipt["request_digest"] != creation_digest(rid, body) or receipt["request"] != body.model_dump():
                    raise StaleSourceError("CREATIVE_STORYBOARD_CREATE_IDEMPOTENCY_CONFLICT")
                guard()
                return self._creation_response(matches[0], scope, replayed=True)
            created = self.timeline_draft(nid, scope, actor, rid, body.model_dump(exclude={"request_id"}), guard)
            row = state["collections"][TIMELINES][created["timeline"]["id"]]
            row["storyboard_create_receipt"] = {"contract": "studio-storyboard-timeline-create/1",
                "request_id": body.request_id, "request_digest": creation_digest(rid, body), "document_id": rid,
                "request": body.model_dump(), "creation_snapshot": copy.deepcopy(created["storyboard_origin"]["timeline_snapshot"]),
                "origin_digest": digest(created["storyboard_origin"])}
            self.production._capacity(state)
            guard()
            return self._creation_response(row, scope, replayed=False)

    def timeline_creation(self, nid, scope, actor, rid, request_id, guard=lambda: None):
        """Inspect the original durable receipt; never recreate a lost reply."""
        if self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_TIMELINE_OWNER_REQUIRED")
        # Reuse the exact bounded ID type even for this read-only route.
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", request_id):
            raise ValueError("CREATIVE_STORYBOARD_CREATE_REQUEST_INVALID")
        context = self.production._base(nid, scope, actor, guard)
        with self._phase(nid, scope, actor, guard) as state:
            matches = self._creation_matches(nid, scope, actor, request_id, context, state)
            if not matches or matches[0]["storyboard_create_receipt"]["document_id"] != rid:
                raise FileNotFoundError(request_id)
            guard()
            return self._creation_response(matches[0], scope, replayed=True)

    def adopt_video(self, nid, scope, actor, rid, shot_id, tid, value, guard=lambda: None):
        body = StoryboardVideoAdoption.model_validate(value)
        if self.production is None:
            raise ValueError("CREATIVE_STORYBOARD_VIDEO_OWNER_REQUIRED")
        job, result = self._approved_video(nid, scope, actor, body.video_asset, body.video_job, guard)
        snapshot = {"kind": "ASSET", "id": body.video_asset.asset_id, "version": body.video_asset.version,
                    "digest": body.video_asset.digest, "asset_kind": "video"}
        # Native decode is deliberately before taking the writable Asset phase.
        source = self.production.source(nid, scope, snapshot, guard, inspection_guard=guard)
        if not 0 <= body.in_ms < body.out_ms <= source["measured"]["duration_ms"]:
            raise ValueError("CREATIVE_STORYBOARD_VIDEO_RANGE_INVALID")
        if body.include_audio:
            from ..media_files import inspect_media
            inspect_media(source["data"], "audio", guard=guard)
        context = self.production._base(nid, scope, actor, guard)
        with self._phase(nid, scope, actor, guard, write=True) as state:
            row = self.creative.get(nid, scope, rid)
            receipt, shot = self._owned_shot(row, shot_id, body)
            if not receipt["approved"] or shot.get("video_result") != result:
                raise StaleSourceError("CREATIVE_STORYBOARD_VIDEO_BINDING_REVIEW_REQUIRED")
            validate_shot_pin(row, result["source_shot"], historical=True)
            self._video_metadata(nid, scope, receipt, result, guard, job=job, state=state)
            timeline = self.production._owned_timeline(nid, scope, actor, tid, context, state)
            prior_adoption = timeline.get("storyboard_video_adoption")
            if prior_adoption is not None:
                saved = StoryboardAdoptionReceipt.model_validate(prior_adoption)
                if (saved.request.request_id == body.request_id and
                        (saved.request_digest != adoption_digest(rid, shot_id, tid, body)
                         or saved.request.model_dump() != body.model_dump())):
                    raise StaleSourceError("CREATIVE_STORYBOARD_ADOPTION_IDEMPOTENCY_CONFLICT")
            if "storyboard_origin" not in timeline:
                raise ValueError("CREATIVE_STORYBOARD_TIMELINE_ORIGIN_REQUIRED")
            origin = validate_storyboard_timeline_origin(timeline)
            mapped = [item for item in origin["shots"] if item["clip_id"] == body.clip_id]
            if (origin["document_snapshot"]["id"] != rid or len(mapped) != 1 or
                    (mapped[0]["shot_id"], mapped[0]["shot_version"], mapped[0]["shot_digest"]) !=
                    (shot_id, shot["shot_version"], shot["shot_digest"])):
                raise StaleSourceError("CREATIVE_STORYBOARD_TIMELINE_SHOT_CHANGED")
            edit = adoption_edit(body)
            self.production.timeline_edit(nid, scope, actor, tid, edit, guard)
            timeline["storyboard_video_adoption"] = {"contract": "studio-storyboard-video-adoption/1",
                "document_id": rid, "shot_id": shot_id, "timeline_id": tid, "request": body.model_dump(),
                "request_digest": adoption_digest(rid, shot_id, tid, body), "edit_receipt": copy.deepcopy(timeline["last_edit"]),
                "shot_pin": self._shot_pin(receipt, shot), "video_result": copy.deepcopy(result)}
            self.production._capacity(state)
            updated = self.production._timeline_view(timeline, scope)
            guard()
            return {"contract": "studio-storyboard-video-adoption/1", "shot_pin": self._shot_pin(receipt, shot),
                "video_result": result, "timeline": updated, "adoption_receipt": updated["video_adoption_receipt"], "automatic_dispatch": False,
                "model_called": False, "rendered": False, "product_acceptance": "LOCAL_REQUIRED"}

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
