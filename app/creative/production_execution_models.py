"""Commands for explicit production execution, separate from advisory contracts."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator
from .production_contracts import ProductionSourceSnapshot, Name, Digest

GraphMediaOperation = Literal["m5.image.t2i", "m5.image.i2i", "m7.video.t2v", "m7.video.i2v",
    "m7.video.v2v", "m8.audio.speech", "m8.audio.music", "m8.audio.effects", "m8.audio.trim"]

ImageRuntimeOperation = Literal["m5.image.t2i", "m5.image.i2i", "m5.image.reference", "m5.image.inpaint", "m5.image.upscale"]
MediaOperation = Literal[GraphMediaOperation, "m5.image.cutout", "m5.image.reference", "m5.image.inpaint", "m5.image.upscale"]


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ProviderSelection(ExecutionModel):
    operation_id: Literal[GraphMediaOperation, "m5.image.reference", "m5.image.inpaint", "m5.image.upscale"]
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
    target_peak_dbfs: float | None = Field(default=None, ge=-24, le=-1)
    fade_in_ms: int | None = Field(default=None, ge=0, le=120000)
    fade_out_ms: int | None = Field(default=None, ge=0, le=120000)
    gain_db: float | None = Field(default=None, ge=-60, le=12)
    sample_rate: int | None = Field(default=None, ge=8000, le=96000)
    channels: int | None = Field(default=None, ge=1, le=2)
    output_format: Literal["FLAC", "MP3"] | None = None
    denoising_strength: float | None = Field(default=None, gt=0, le=1)
    scale: Literal[2, 4] | None = None

    @field_validator("target_peak_dbfs", mode="before")
    @classmethod
    def exact_peak(cls, value):
        if type(value) not in {int, float}:
            raise ValueError("STUDIO_AUDIO_PEAK_INVALID")
        return value

    @field_validator("fade_in_ms", "fade_out_ms", mode="before")
    @classmethod
    def exact_fade(cls, value):
        # Absence alone is optional; null, bool and coercible numbers are not.
        if type(value) is not int:
            raise ValueError("STUDIO_AUDIO_FADE_INVALID")
        return value

    @field_validator("scale", mode="before")
    @classmethod
    def exact_scale(cls, value):
        if value is not None and type(value) is not int:
            raise ValueError("STUDIO_IMAGE_UPSCALE_SCALE_INVALID")
        return value

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        # Original preview and job identities include the old null fields.
        # Omit only the new unset controls, including in nested model_dump().
        value = handler(self)
        for key in ("gain_db", "sample_rate", "channels", "output_format", "denoising_strength", "scale", "fade_in_ms", "fade_out_ms", "target_peak_dbfs"):
            if value.get(key) is None:
                value.pop(key, None)
        return value


class ImageReference(ExecutionModel):
    """Weighted reference to the existing Asset owner, never copied pixels."""
    source: ProductionSourceSnapshot
    weight: float = Field(gt=0, le=1)
    purpose: Literal["character", "outfit", "environment", "style", "composition"] | None = None
    source_note: str | None = Field(default=None, min_length=1, max_length=500)

    @model_serializer(mode="wrap")
    def preserve_reference_identity(self, handler):
        value = handler(self)
        for key in ("purpose", "source_note"):
            if value.get(key) is None:
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def original_image(self):
        if self.source.kind != "ASSET" or self.source.asset_kind != "image":
            raise ValueError("STUDIO_IMAGE_REFERENCE_KIND_INVALID")
        return self


def image_snapshot(value):
    return value.model_dump(exclude_none=True, exclude={"reference_only"})


class VideoReference(ExecutionModel):
    """Authored reference purpose; never claims semantic model conditioning."""
    source: ProductionSourceSnapshot
    purpose: Literal["style", "action", "camera"]

    @model_validator(mode="after")
    def original_video(self):
        if self.source.kind != "ASSET" or self.source.asset_kind != "video":
            raise ValueError("STUDIO_VIDEO_REFERENCE_KIND_INVALID")
        return self


class StoryboardDocumentSnapshot(ExecutionModel):
    id: Name
    version: int = Field(ge=1)
    digest: Digest


class StoryboardShotPin(ExecutionModel):
    """Exact original authored shot input, never a client approval grant."""
    document_snapshot: StoryboardDocumentSnapshot
    shot_id: Name
    shot_version: int = Field(ge=1)
    shot_digest: Digest


class _MediaCommandShape(ExecutionModel):
    operation_id: MediaOperation
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    provider_id: Name | None = None
    model_id: Name | None = None
    prompt: str = Field(default="", max_length=16000)
    parameters: MediaExecutionParameters = Field(default_factory=MediaExecutionParameters)
    source_snapshots: list[ProductionSourceSnapshot] = Field(default_factory=list, max_length=8)
    allow_cloud: bool = False
    license_note: str = Field(default="", max_length=2000)
    image_source: ProductionSourceSnapshot | None = None
    image_references: list[ImageReference] | None = Field(default=None, max_length=5)
    mask_source: ProductionSourceSnapshot | None = None
    video_reference: VideoReference | None = None
    storyboard_shot: StoryboardShotPin | None = None
    audio_profile: Literal["studio-audio-mp3/1"] | None = None

    @field_validator("audio_profile", mode="before")
    @classmethod
    def explicit_audio_profile(cls, value):
        # Absence preserves the old wire identity; null is not a profile.
        if value is None:
            raise ValueError("STUDIO_AUDIO_PROFILE_INVALID")
        return value

    @model_serializer(mode="wrap")
    def legacy_image_identity(self, handler):
        value = handler(self)
        for key in ("image_source", "image_references", "mask_source", "video_reference", "storyboard_shot", "audio_profile"):
            if value.get(key) is None or (key == "image_references" and value[key] == []):
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def operation_inputs(self):
        if self.audio_profile is not None and (self.operation_id != "m8.audio.trim" or self.parameters.output_format != "MP3"):
            raise ValueError("STUDIO_AUDIO_PROFILE_INVALID")
        if self.storyboard_shot is not None:
            pin = self.storyboard_shot.document_snapshot
            if (not self.operation_id.startswith("m7.") or not any(
                    source.kind == "CREATIVE_DOCUMENT" and (source.id, source.version, source.digest) ==
                    (pin.id, pin.version, pin.digest) for source in self.source_snapshots)):
                raise ValueError("STUDIO_STORYBOARD_SOURCE_PIN_REQUIRED")
        p = self.parameters.model_dump(exclude_none=True)
        allowed = {
            "m5.image.t2i": {"width", "height", "steps", "seed", "negative_prompt", "size", "quality"},
            "m5.image.cutout": set(),
            "m5.image.i2i": {"width", "height", "steps", "seed", "negative_prompt", "size", "quality", "denoising_strength"},
            "m5.image.reference": {"width", "height", "steps", "seed", "negative_prompt", "denoising_strength"},
            "m5.image.inpaint": {"steps", "seed", "negative_prompt", "denoising_strength"},
            "m5.image.upscale": {"scale"},
            "m7.video.t2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m7.video.i2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m7.video.v2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m8.audio.speech": {"voice_id", "speech_rate"},
            "m8.audio.music": {"duration_seconds", "seed"},
            "m8.audio.effects": {"duration_seconds", "seed"},
            "m8.audio.trim": {"in_ms", "out_ms", "gain_db", "sample_rate", "channels", "output_format", "fade_in_ms", "fade_out_ms", "target_peak_dbfs"},
        }[self.operation_id]
        if set(p) - allowed:
            raise ValueError("STUDIO_OPERATION_PARAMETER_UNSUPPORTED")
        if self.parameters.scale is not None and type(self.parameters.scale) is not int:
            raise ValueError("STUDIO_IMAGE_UPSCALE_SCALE_INVALID")
        if (self.parameters.width is None) != (self.parameters.height is None):
            raise ValueError("STUDIO_OPERATION_DIMENSIONS_PAIR_REQUIRED")
        if self.operation_id.startswith("m5.") and any(p.get(k, 64) % 8 for k in ("width", "height")):
            raise ValueError("STUDIO_IMAGE_DIMENSIONS_INVALID")
        keys = [(s.kind, s.id) for s in self.source_snapshots]
        if len(set(keys)) != len(keys):
            raise ValueError("STUDIO_OPERATION_SOURCE_DUPLICATE")
        advanced = (self.image_source is not None or bool(self.image_references) or self.mask_source is not None
            or self.parameters.denoising_strength is not None)
        if advanced or self.operation_id in {"m5.image.reference", "m5.image.inpaint", "m5.image.upscale"}:
            self._image_runtime_inputs()
        if self.operation_id == "m5.image.cutout":
            if self.provider_id is not None or self.model_id is not None or self.allow_cloud or self.prompt or p:
                raise ValueError("STUDIO_IMAGE_CUTOUT_LOCAL_ONLY")
            if (len(self.source_snapshots) != 2 or any(s.kind != "ASSET" or s.asset_kind != "image" for s in self.source_snapshots)):
                raise ValueError("STUDIO_IMAGE_CUTOUT_INPUT_REQUIRED")
        elif self.operation_id == "m5.image.upscale":
            if (not self.provider_id or not self.model_id or self.provider_id == "auto" or self.prompt
                    or self.allow_cloud or self.parameters.scale is None or len(self.source_snapshots) != 1):
                raise ValueError("STUDIO_IMAGE_UPSCALE_EXPLICIT_LOCAL_SOURCE_REQUIRED")
        elif self.operation_id == "m8.audio.trim":
            if (self.parameters.output_format == "MP3" and self.parameters.in_ms is not None
                    and self.parameters.out_ms is not None and self.parameters.out_ms - self.parameters.in_ms < 10):
                raise ValueError("STUDIO_AUDIO_MP3_DURATION_INVALID")
            if self.parameters.output_format == "MP3" and (self.parameters.sample_rate or 48000) not in (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000):
                raise ValueError("STUDIO_AUDIO_MP3_SAMPLE_RATE_INVALID")
            if self.provider_id is not None or self.model_id is not None or self.allow_cloud or self.prompt:
                raise ValueError("STUDIO_AUDIO_TRIM_LOCAL_ONLY")
            if (len(self.source_snapshots) != 1 or self.source_snapshots[0].asset_kind != "audio"
                    or self.parameters.in_ms is None or self.parameters.out_ms is None
                    or self.parameters.out_ms <= self.parameters.in_ms
                    or self.parameters.out_ms - self.parameters.in_ms > 120000):
                raise ValueError("STUDIO_AUDIO_TRIM_INPUT_REQUIRED")
            if self.parameters.target_peak_dbfs is not None:
                if self.parameters.output_format is not None:
                    raise ValueError("STUDIO_AUDIO_PEAK_WAV_ONLY")
                if self.parameters.target_peak_dbfs + (self.parameters.gain_db or 0) > -1:
                    raise ValueError("STUDIO_AUDIO_PEAK_HEADROOM_INVALID")
            if (self.parameters.fade_in_ms or 0) + (self.parameters.fade_out_ms or 0) > self.parameters.out_ms - self.parameters.in_ms:
                raise ValueError("STUDIO_AUDIO_FADE_RANGE_INVALID")
        elif not self.provider_id or not self.model_id or not self.prompt.strip() or self.provider_id == "auto":
            raise ValueError("STUDIO_EXPLICIT_PROVIDER_MODEL_PROMPT_REQUIRED")
        required = {"m5.image.i2i": "image", "m5.image.reference": "image", "m5.image.inpaint": "image", "m5.image.upscale": "image",
            "m7.video.i2v": "image", "m7.video.v2v": "video"}.get(self.operation_id)
        assets = [s for s in self.source_snapshots if s.kind == "ASSET"]
        if required and (not assets or any(s.asset_kind != required for s in assets)):
            raise ValueError("STUDIO_MEDIA_REFERENCE_KIND_INVALID")
        if self.operation_id in {"m7.video.i2v", "m7.video.v2v"} and len(assets) != 1:
            raise ValueError("STUDIO_VIDEO_SINGLE_REFERENCE_REQUIRED")
        if self.video_reference is not None:
            if (self.operation_id != "m7.video.v2v" or len(assets) != 1
                    or image_snapshot(assets[0]) != image_snapshot(self.video_reference.source)):
                raise ValueError("STUDIO_VIDEO_REFERENCE_SNAPSHOT_MISMATCH")
        if self.operation_id == "m5.image.i2i" and len(assets) > 5:
            raise ValueError("STUDIO_IMAGE_REFERENCE_LIMIT")
        if not required and self.operation_id not in {"m8.audio.trim", "m5.image.cutout"} and assets:
            raise ValueError("STUDIO_OPERATION_UNUSED_ASSET_REFERENCE")
        if any(s.kind not in {"ASSET", "CREATIVE_DOCUMENT"} for s in self.source_snapshots):
            raise ValueError("STUDIO_OPERATION_SOURCE_OWNER_UNSUPPORTED")
        return self

    def _image_runtime_inputs(self):
        if self.operation_id not in {"m5.image.i2i", "m5.image.reference", "m5.image.inpaint", "m5.image.upscale"}:
            raise ValueError("STUDIO_IMAGE_RUNTIME_OPERATION_INVALID")
        refs = self.image_references or []
        snapshots = []
        for snapshot in (self.image_source, self.mask_source):
            if snapshot is not None and (snapshot.kind != "ASSET" or snapshot.asset_kind != "image"):
                raise ValueError("STUDIO_IMAGE_RUNTIME_SOURCE_KIND_INVALID")
        if self.operation_id == "m5.image.upscale":
            if self.image_source is None or self.mask_source is not None or refs:
                raise ValueError("STUDIO_IMAGE_UPSCALE_SOURCE_REQUIRED")
        elif self.operation_id == "m5.image.reference":
            if not refs or self.image_source is not None or self.mask_source is not None:
                raise ValueError("STUDIO_IMAGE_REFERENCE_INPUT_REQUIRED")
        elif self.operation_id == "m5.image.i2i":
            if self.image_source is None or self.mask_source is not None or len(refs) > 4:
                raise ValueError("STUDIO_IMAGE_RUNTIME_BASE_REQUIRED")
        elif self.image_source is None or self.mask_source is None or refs:
            raise ValueError("STUDIO_IMAGE_INPAINT_SOURCE_MASK_REQUIRED")
        if self.image_source is not None:
            snapshots.append(self.image_source)
        snapshots.extend(reference.source for reference in refs)
        if self.mask_source is not None:
            snapshots.append(self.mask_source)
        ids = [snapshot.id for snapshot in snapshots]
        if len(ids) != len(set(ids)):
            raise ValueError("STUDIO_IMAGE_RUNTIME_REFERENCE_DUPLICATE")
        assets = [source for source in self.source_snapshots if source.kind == "ASSET"]
        if [image_snapshot(source) for source in assets] != [image_snapshot(source) for source in snapshots]:
            raise ValueError("STUDIO_IMAGE_RUNTIME_SNAPSHOT_MISMATCH")


class MediaCommand(_MediaCommandShape):
    """Fresh public commands require an explicit versioned MP3 contract."""

    @model_validator(mode="after")
    def versioned_audio_submission(self):
        if self.parameters.output_format == "MP3" and self.audio_profile != "studio-audio-mp3/1":
            raise ValueError("STUDIO_AUDIO_PROFILE_REQUIRED")
        return self


class _HistoricalAudioCommand(_MediaCommandShape):
    """Decode only a validated, server-loaded pre-versioned trim receipt.

    This is deliberately not a MediaCommand subclass: public validation cannot
    accept a historical object by treating it as an already validated command.
    No persisted key, digest or recipe is upgraded during decoding.
    """

    @model_validator(mode="after")
    def original_audio_shape(self):
        if (self.operation_id != "m8.audio.trim" or self.parameters.output_format != "MP3"
                or "audio_profile" in self.model_fields_set):
            raise ValueError("STUDIO_AUDIO_HISTORICAL_COMMAND_INVALID")
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


class TimelineWaveformSource(TimelineAssetSnapshot):
    asset_kind: Literal["audio"]


class TimelineWaveformPreview(TimelinePlaybackPreview):
    clip_id: Name
    source_snapshot: TimelineWaveformSource


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
