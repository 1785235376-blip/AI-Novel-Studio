"""Commands for explicit production execution, separate from advisory contracts."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator
from .production_contracts import ProductionSourceSnapshot, Name, Digest

GraphMediaOperation = Literal["m5.image.t2i", "m5.image.i2i", "m7.video.t2v", "m7.video.i2v",
    "m7.video.v2v", "m8.audio.speech", "m8.audio.music", "m8.audio.effects", "m8.audio.trim"]

MediaOperation = Literal[GraphMediaOperation, "m5.image.cutout"]


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ProviderSelection(ExecutionModel):
    operation_id: GraphMediaOperation
    provider_id: Name
    model_id: Name


class MediaParameters(ExecutionModel):
    width: int | None = Field(default=None, ge=64, le=2048)
    height: int | None = Field(default=None, ge=64, le=2048)
    steps: int | None = Field(default=None, ge=1, le=150)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    negative_prompt: str | None = Field(default=None, max_length=8000)
    size: Literal["auto", "1024x1024", "1536x1024", "1024x1536"] | None = None
    quality: Literal["auto", "low", "medium", "high", "standard", "hd"] | None = None
    duration_seconds: int | None = Field(default=None, ge=1, le=600)
    frame_rate: int | None = Field(default=None, ge=1, le=60)
    voice_id: Name | None = None
    speech_rate: float | None = Field(default=None, ge=0.5, le=2)
    in_ms: int | None = Field(default=None, ge=0, le=600000)
    out_ms: int | None = Field(default=None, ge=1, le=600000)


class MediaExecutionParameters(MediaParameters):
    """Standalone additions; the original Graph parameter schema stays closed."""
    gain_db: float | None = Field(default=None, ge=-60, le=12)
    sample_rate: int | None = Field(default=None, ge=8000, le=96000)
    channels: int | None = Field(default=None, ge=1, le=2)

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        # Original preview and job identities include the old null fields.
        # Omit only the new unset controls, including in nested model_dump().
        value = handler(self)
        for key in ("gain_db", "sample_rate", "channels"):
            if value.get(key) is None:
                value.pop(key, None)
        return value


class MediaCommand(ExecutionModel):
    operation_id: MediaOperation
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    provider_id: Name | None = None
    model_id: Name | None = None
    prompt: str = Field(default="", max_length=16000)
    parameters: MediaExecutionParameters = Field(default_factory=MediaExecutionParameters)
    source_snapshots: list[ProductionSourceSnapshot] = Field(default_factory=list, max_length=8)
    allow_cloud: bool = False
    license_note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def operation_inputs(self):
        p = self.parameters.model_dump(exclude_none=True)
        allowed = {
            "m5.image.t2i": {"width", "height", "steps", "seed", "negative_prompt", "size", "quality"},
            "m5.image.cutout": set(),
            "m5.image.i2i": {"width", "height", "steps", "seed", "negative_prompt", "size", "quality"},
            "m7.video.t2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m7.video.i2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m7.video.v2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m8.audio.speech": {"voice_id", "speech_rate"},
            "m8.audio.music": {"duration_seconds", "seed"},
            "m8.audio.effects": {"duration_seconds", "seed"},
            "m8.audio.trim": {"in_ms", "out_ms", "gain_db", "sample_rate", "channels"},
        }[self.operation_id]
        if set(p) - allowed:
            raise ValueError("STUDIO_OPERATION_PARAMETER_UNSUPPORTED")
        if (self.parameters.width is None) != (self.parameters.height is None):
            raise ValueError("STUDIO_OPERATION_DIMENSIONS_PAIR_REQUIRED")
        if self.operation_id.startswith("m5.") and any(p.get(k, 64) % 8 for k in ("width", "height")):
            raise ValueError("STUDIO_IMAGE_DIMENSIONS_INVALID")
        keys = [(s.kind, s.id) for s in self.source_snapshots]
        if len(set(keys)) != len(keys):
            raise ValueError("STUDIO_OPERATION_SOURCE_DUPLICATE")
        if self.operation_id == "m5.image.cutout":
            if self.provider_id is not None or self.model_id is not None or self.allow_cloud or self.prompt or p:
                raise ValueError("STUDIO_IMAGE_CUTOUT_LOCAL_ONLY")
            if (len(self.source_snapshots) != 2 or any(s.kind != "ASSET" or s.asset_kind != "image" for s in self.source_snapshots)):
                raise ValueError("STUDIO_IMAGE_CUTOUT_INPUT_REQUIRED")
        elif self.operation_id == "m8.audio.trim":
            if self.provider_id is not None or self.model_id is not None or self.allow_cloud or self.prompt:
                raise ValueError("STUDIO_AUDIO_TRIM_LOCAL_ONLY")
            if (len(self.source_snapshots) != 1 or self.source_snapshots[0].asset_kind != "audio"
                    or self.parameters.in_ms is None or self.parameters.out_ms is None
                    or self.parameters.out_ms <= self.parameters.in_ms
                    or self.parameters.out_ms - self.parameters.in_ms > 120000):
                raise ValueError("STUDIO_AUDIO_TRIM_INPUT_REQUIRED")
        elif not self.provider_id or not self.model_id or not self.prompt.strip() or self.provider_id == "auto":
            raise ValueError("STUDIO_EXPLICIT_PROVIDER_MODEL_PROMPT_REQUIRED")
        required = {"m5.image.i2i": "image", "m7.video.i2v": "image", "m7.video.v2v": "video"}.get(self.operation_id)
        assets = [s for s in self.source_snapshots if s.kind == "ASSET"]
        if required and (not assets or any(s.asset_kind != required for s in assets)):
            raise ValueError("STUDIO_MEDIA_REFERENCE_KIND_INVALID")
        if self.operation_id in {"m7.video.i2v", "m7.video.v2v"} and len(assets) != 1:
            raise ValueError("STUDIO_VIDEO_SINGLE_REFERENCE_REQUIRED")
        if self.operation_id == "m5.image.i2i" and len(assets) > 5:
            raise ValueError("STUDIO_IMAGE_REFERENCE_LIMIT")
        if not required and self.operation_id not in {"m8.audio.trim", "m5.image.cutout"} and assets:
            raise ValueError("STUDIO_OPERATION_UNUSED_ASSET_REFERENCE")
        if any(s.kind not in {"ASSET", "CREATIVE_DOCUMENT"} for s in self.source_snapshots):
            raise ValueError("STUDIO_OPERATION_SOURCE_OWNER_UNSUPPORTED")
        return self


class MediaCreate(ExecutionModel):
    command: MediaCommand
    reviewed_preview_digest: Digest


class MediaJobAction(ExecutionModel):
    expected_version: int = Field(ge=1)
    expected_request_digest: Digest


class MediaReview(MediaJobAction):
    reviewed_output_digest: Digest


class TimelineSave(ExecutionModel):
    title: str = Field(min_length=1, max_length=240)
    # The original render owner's closed validator validates all nested fields.
    timeline: dict
    expected_version: int = Field(ge=0)


class TimelineRender(ExecutionModel):
    expected_version: int = Field(ge=1)
    reviewed_timeline_digest: Digest
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


class TimelinePlaybackPreview(ExecutionModel):
    expected_version: int = Field(ge=1, le=2**53 - 1)
    reviewed_timeline_digest: Digest


class TimelinePlaybackBuild(TimelinePlaybackPreview):
    reviewed_playback_digest: Digest


class TimelinePlaybackAttestation(TimelinePlaybackBuild):
    expected_job_version: int = Field(ge=1, le=2**53 - 1)
    expected_request_digest: Digest


class TimelineEdit(ExecutionModel):
    expected_version: int = Field(ge=1)
    reviewed_timeline_digest: Digest
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    operations: list[dict] = Field(min_length=1, max_length=40)


class TimelineRestore(ExecutionModel):
    expected_version: int = Field(ge=1)
    reviewed_timeline_digest: Digest
    restore_version: int = Field(ge=1)
    restore_digest: Digest


class TimelineExportPreview(ExecutionModel):
    expected_version: int = Field(ge=1)
    reviewed_timeline_digest: Digest
    # Closed preset/codec/rate fields are validated by the original renderer.
    export_profile: dict


class TimelineExport(TimelineExportPreview):
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    reviewed_export_digest: Digest


class TimelineAssetSnapshot(ExecutionModel):
    id: Name
    kind: Literal["ASSET"]
    asset_kind: Literal["image", "video", "audio"]
    version: int = Field(ge=1, le=2**53 - 1)
    digest: Digest


class TimelineMediaBinding(ExecutionModel):
    reference: str = Field(min_length=1, max_length=4096)
    source_snapshot: TimelineAssetSnapshot


class TimelineTransferPreview(ExecutionModel):
    expected_version: int = Field(ge=1, le=2**53 - 1)
    reviewed_timeline_digest: Digest
    direction: Literal["IMPORT", "EXPORT"]
    format: Literal["OTIO", "SRT", "VTT"]
    content: str = Field(default="", max_length=2 * 1024 * 1024)
    media_bindings: list[TimelineMediaBinding] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def transfer_shape(self):
        if self.direction == "EXPORT" and (self.content or self.media_bindings):
            raise ValueError("STUDIO_TRANSFER_EXPORT_UNUSED_INPUT")
        if self.direction == "IMPORT" and not self.content.strip():
            raise ValueError("STUDIO_TRANSFER_IMPORT_CONTENT_REQUIRED")
        if self.format != "OTIO" and self.media_bindings:
            raise ValueError("STUDIO_TRANSFER_SUBTITLE_MEDIA_BINDINGS_UNUSED")
        try:
            size = len(self.content.encode("utf-8"))
        except UnicodeEncodeError:
            raise ValueError("STUDIO_TRANSFER_UTF8_REQUIRED") from None
        if size > (2 * 1024 * 1024 if self.format == "OTIO" else 192000):
            raise ValueError("STUDIO_TRANSFER_INPUT_BYTE_LIMIT")
        return self


class TimelineTransferDownload(TimelineTransferPreview):
    reviewed_preview_digest: Digest
    acknowledge_losses: bool = False


class TimelineTransferImport(TimelineTransferDownload):
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
