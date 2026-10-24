"""Commands for explicit production execution, separate from advisory contracts."""
from __future__ import annotations

from typing import Literal, ClassVar
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator
from .production_contracts import ProductionSourceSnapshot, Name, Digest, PUBLIC_SCOPE_KEYS

GraphMediaOperation = Literal["m5.image.t2i", "m5.image.i2i", "m7.video.t2v", "m7.video.i2v",
    "m7.video.v2v", "m8.audio.speech", "m8.audio.music", "m8.audio.effects", "m8.audio.trim"]

ImageRuntimeOperation = Literal["m5.image.t2i", "m5.image.i2i", "m5.image.reference", "m5.image.inpaint", "m5.image.upscale"]
MediaOperation = Literal[GraphMediaOperation, "m5.image.cutout", "m5.image.reference", "m5.image.inpaint", "m5.image.upscale", "m5.image.composite"]


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ProviderSelection(ExecutionModel):
    operation_id: Literal[GraphMediaOperation, "m5.image.reference", "m5.image.inpaint", "m5.image.upscale"]
    provider_id: Name
    model_id: Name


class CanvasReturnBinding(ExecutionModel):
    """Immutable return intent in the original Job command; never authority."""
    allowed_asset_kinds: ClassVar[frozenset[str]] = frozenset({'image', 'audio'})
    contract: Literal['studio-canvas-return/1']
    project_id: Name
    scope: dict[str, str | None]
    incarnation: str = Field(pattern=r'^(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    canvas_id: Name
    canvas_version: int = Field(ge=1, strict=True)
    canvas_digest: Digest
    card_id: Name
    source: ProductionSourceSnapshot

    @model_validator(mode='after')
    def exact_origin(self):
        if (set(self.scope) - PUBLIC_SCOPE_KEYS or self.scope.get('novel_id') != self.project_id
                or self.scope.get('mode') not in {'local', 'collaboration'}
                or any(v is not None and not 1 <= len(v) <= 240 for v in self.scope.values())
                or self.scope['mode'] == 'collaboration' and any(not self.scope.get(k) for k in ('workspace_id', 'storyline_id', 'branch_id'))
                or self.source.kind != 'ASSET' or self.source.asset_kind not in self.allowed_asset_kinds):
            raise ValueError('STUDIO_CANVAS_RETURN_BINDING_INVALID')
        return self

    @model_serializer(mode='wrap')
    def reference_identity(self, handler):
        value = handler(self)
        value['source'] = self.source.model_dump(exclude={'reference_only'}, exclude_none=True)
        return value


class CanvasImageNodePosition(ExecutionModel):
    x: float = Field(ge=-100_000, le=100_000, strict=True)
    y: float = Field(ge=-100_000, le=100_000, strict=True)


class CanvasImageNodeBinding(ExecutionModel):
    """Captured display intent only; original owners resolve all authority."""
    contract: Literal['studio-canvas-image-node/1']
    project_id: Name
    scope: dict[str, str | None]
    incarnation: str = Field(pattern=r'^(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    canvas_id: Name
    canvas_version: int = Field(ge=1, le=2**53 - 1, strict=True)
    canvas_digest: Digest
    node_id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
    title: str = Field(min_length=1, max_length=160)
    position: CanvasImageNodePosition
    prompt_digest: Digest

    @model_validator(mode='after')
    def exact_origin(self):
        if (set(self.scope) - PUBLIC_SCOPE_KEYS or self.scope.get('novel_id') != self.project_id
                or self.scope.get('mode') not in {'local', 'collaboration'}
                or any(v is not None and not 1 <= len(v) <= 240 for v in self.scope.values())
                or self.scope['mode'] == 'collaboration' and any(not self.scope.get(k) for k in ('workspace_id', 'storyline_id', 'branch_id'))
                or not self.title.strip()):
            raise ValueError('STUDIO_CANVAS_IMAGE_NODE_INVALID')
        return self


class MediaParameters(ExecutionModel):
    width: int | None = Field(default=None, ge=64, le=2048)
    height: int | None = Field(default=None, ge=64, le=2048)
    steps: int | None = Field(default=None, ge=1, le=150)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    cfg: float | None = Field(default=None, ge=0, le=100)
    negative_prompt: str | None = Field(default=None, max_length=8000)
    size: Literal["auto", "1024x1024", "1536x1024", "1024x1536"] | None = None
    quality: Literal["auto", "low", "medium", "high", "standard", "hd"] | None = None
    duration_seconds: int | None = Field(default=None, ge=1, le=600)
    frame_rate: int | None = Field(default=None, ge=1, le=60)
    voice_id: Name | None = None
    speech_rate: float | None = Field(default=None, ge=0.5, le=2)
    in_ms: int | None = Field(default=None, ge=0, le=600000)
    out_ms: int | None = Field(default=None, ge=1, le=600000)

    @field_validator('cfg', mode='before')
    @classmethod
    def exact_cfg(cls, value):
        # Original commands round-trip all absent optional fields as None.
        if value is None: return None
        if type(value) not in {int, float}:
            raise ValueError('STUDIO_IMAGE_CFG_INVALID')
        return value


class MediaExecutionParameters(MediaParameters):
    """Standalone additions; the original Graph parameter schema stays closed."""
    cutout_output: Literal["WEBP_LOSSLESS_V1"] | None = None
    denoise_profile: Literal["STATIONARY_FFT_V1"] | None = None
    target_lufs: float | None = Field(default=None, ge=-30, le=-14)
    target_peak_dbfs: float | None = Field(default=None, ge=-24, le=-1)
    fade_in_ms: int | None = Field(default=None, ge=0, le=120000)
    fade_out_ms: int | None = Field(default=None, ge=0, le=120000)
    gain_db: float | None = Field(default=None, ge=-60, le=12)
    sample_rate: int | None = Field(default=None, ge=8000, le=96000)
    channels: int | None = Field(default=None, ge=1, le=2)
    output_format: Literal["FLAC", "MP3"] | None = None
    denoising_strength: float | None = Field(default=None, gt=0, le=1)
    scale: Literal[2, 4] | None = None

    @field_validator("cutout_output", mode="before")
    @classmethod
    def exact_cutout_output(cls, value):
        if value != "WEBP_LOSSLESS_V1":
            raise ValueError("STUDIO_IMAGE_CUTOUT_OUTPUT_INVALID")
        return value

    @field_validator("denoise_profile", mode="before")
    @classmethod
    def exact_denoise(cls, value):
        if value != "STATIONARY_FFT_V1":
            raise ValueError("STUDIO_AUDIO_DENOISE_PROFILE_INVALID")
        return value

    @field_validator("target_lufs", mode="before")
    @classmethod
    def exact_loudness(cls, value):
        if type(value) not in {int, float}:
            raise ValueError("STUDIO_AUDIO_LOUDNESS_TARGET_INVALID")
        return value

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
        for key in ("gain_db", "sample_rate", "channels", "output_format", "denoising_strength", "scale", "fade_in_ms", "fade_out_ms", "target_peak_dbfs", "target_lufs", "denoise_profile", "cutout_output"):
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


class VideoFrame(ExecutionModel):
    """One exact first/last image frame of an existing Asset owner, in role order."""
    role: Literal["FIRST", "LAST"]
    source: ProductionSourceSnapshot

    @model_validator(mode="after")
    def original_image(self):
        if self.source.kind != "ASSET" or self.source.asset_kind != "image":
            raise ValueError("STUDIO_VIDEO_FRAME_KIND_INVALID")
        return self

    @model_serializer(mode="wrap")
    def canonical_source(self, handler):
        value = handler(self); value["source"] = image_snapshot(self.source)
        return value


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


class StoryboardSpeechPin(StoryboardShotPin):
    """One explicitly selected authored dialogue; separate from video provenance."""
    dialogue_index: int = Field(ge=0, le=199, strict=True)


class ImageCompositeLayer(ExecutionModel):
    source: ProductionSourceSnapshot
    visible: bool
    opacity: int = Field(ge=0, le=255)

    @model_serializer(mode="wrap")
    def canonical_source(self, handler):
        value = handler(self); value['source'] = image_snapshot(self.source)
        return value


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
    video_frames: list[VideoFrame] | None = Field(default=None, min_length=1, max_length=2)
    storyboard_shot: StoryboardShotPin | None = None
    storyboard_speech: StoryboardSpeechPin | None = None
    audio_profile: Literal["studio-audio-mp3/1"] | None = None
    image_layers: list[ImageCompositeLayer] | None = Field(default=None, min_length=2, max_length=2)
    canvas_return: CanvasReturnBinding | None = None
    canvas_image_node: CanvasImageNodeBinding | None = None

    @field_validator('canvas_image_node', mode='before')
    @classmethod
    def explicit_canvas_image_node(cls, value):
        if value is None: raise ValueError('STUDIO_CANVAS_IMAGE_NODE_INVALID')
        return value

    @field_validator('canvas_return', mode='before')
    @classmethod
    def explicit_canvas_return(cls, value):
        if value is None: raise ValueError('STUDIO_CANVAS_RETURN_BINDING_INVALID')
        return value

    @field_validator('image_layers', mode='before')
    @classmethod
    def explicit_composite_layers(cls, value):
        if value is None: raise ValueError('STUDIO_IMAGE_COMPOSITE_TWO_LAYERS_REQUIRED')
        return value

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
        for key in ("image_source", "image_references", "mask_source", "video_reference", "video_frames", "storyboard_shot", "storyboard_speech", "audio_profile", "image_layers", "canvas_return", "canvas_image_node"):
            if value.get(key) is None or (key == "image_references" and value[key] == []):
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def operation_inputs(self):
        if self.canvas_image_node is not None:
            import hashlib
            if (self.operation_id != 'm5.image.t2i' or self.allow_cloud or self.source_snapshots
                    or self.canvas_return is not None or self.image_source is not None or self.image_references is not None
                    or self.mask_source is not None or self.video_reference is not None or self.video_frames is not None
                    or self.storyboard_shot is not None or self.storyboard_speech is not None
                    or self.audio_profile is not None or self.image_layers is not None
                    or self.canvas_image_node.prompt_digest != hashlib.sha256(self.prompt.encode('utf-8')).hexdigest()):
                raise ValueError('STUDIO_CANVAS_IMAGE_NODE_COMMAND_INVALID')
        if self.canvas_return is not None:
            origin = self.canvas_return.source
            if origin.asset_kind == 'image':
                if (self.operation_id != 'm5.image.i2i' or self.allow_cloud
                        or len(self.source_snapshots) != 1 or self.image_source is None or self.image_references or self.mask_source is not None
                        or image_snapshot(origin) != image_snapshot(self.source_snapshots[0])
                        or image_snapshot(origin) != image_snapshot(self.image_source)):
                    raise ValueError('STUDIO_CANVAS_RETURN_COMMAND_INVALID')
            elif (self.operation_id != 'm8.audio.trim' or self.allow_cloud or self.provider_id is not None
                    or self.model_id is not None or self.prompt or len(self.source_snapshots) != 1
                    or image_snapshot(origin) != image_snapshot(self.source_snapshots[0])
                    or not {'in_ms', 'out_ms'} <= set(self.parameters.model_dump(exclude_none=True))
                    or set(self.parameters.model_dump(exclude_none=True)) - {'in_ms', 'out_ms', 'gain_db', 'fade_in_ms', 'fade_out_ms'}
                    or any(getattr(self.parameters, key) is None for key in
                        self.parameters.model_fields_set & {'gain_db', 'fade_in_ms', 'fade_out_ms'})
                    or self.image_source is not None or self.image_references or self.mask_source is not None
                    or self.video_reference is not None or self.video_frames is not None or self.audio_profile is not None
                    or self.storyboard_shot is not None or self.storyboard_speech is not None):
                raise ValueError('STUDIO_CANVAS_RETURN_COMMAND_INVALID')
        if self.image_layers is not None and self.operation_id != 'm5.image.composite':
            raise ValueError('STUDIO_IMAGE_COMPOSITE_OPERATION_REQUIRED')
        if self.audio_profile is not None and (self.operation_id != "m8.audio.trim" or self.parameters.output_format != "MP3"):
            raise ValueError("STUDIO_AUDIO_PROFILE_INVALID")
        if self.storyboard_shot is not None:
            pin = self.storyboard_shot.document_snapshot
            if (not self.operation_id.startswith("m7.") or not any(
                    source.kind == "CREATIVE_DOCUMENT" and (source.id, source.version, source.digest) ==
                    (pin.id, pin.version, pin.digest) for source in self.source_snapshots)):
                raise ValueError("STUDIO_STORYBOARD_SOURCE_PIN_REQUIRED")
        if self.storyboard_speech is not None:
            pin = self.storyboard_speech.document_snapshot
            if (self.operation_id != "m8.audio.speech" or self.storyboard_shot is not None
                    or len(self.source_snapshots) != 1 or self.provider_id is None or self.model_id is None
                    or self.parameters.voice_id is None or self.parameters.speech_rate is None):
                raise ValueError("STUDIO_STORYBOARD_SPEECH_COMMAND_INVALID")
            source = self.source_snapshots[0]
            if (source.kind != "CREATIVE_DOCUMENT" or (source.id, source.version, source.digest) !=
                    (pin.id, pin.version, pin.digest)):
                raise ValueError("STUDIO_STORYBOARD_SPEECH_SOURCE_PIN_REQUIRED")
        comic = [s for s in self.source_snapshots if s.kind == "COMIC_PANEL"]
        if comic and (len(self.source_snapshots) != 1 or self.operation_id != "m5.image.t2i"
                or self.allow_cloud or self.image_source is not None or self.image_references is not None
                or self.mask_source is not None or self.storyboard_shot is not None or self.storyboard_speech is not None):
            raise ValueError("STUDIO_COMIC_EXPLICIT_LOCAL_T2I_ONLY")
        p = self.parameters.model_dump(exclude_none=True)
        allowed = {
            "m5.image.t2i": {"width", "height", "steps", "seed", "cfg", "negative_prompt", "size", "quality"},
            "m5.image.cutout": {"cutout_output"},
            "m5.image.composite": set(),
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
            "m8.audio.trim": {"in_ms", "out_ms", "gain_db", "sample_rate", "channels", "output_format", "fade_in_ms", "fade_out_ms", "target_peak_dbfs", "target_lufs", "denoise_profile"},
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
        if self.operation_id == 'm5.image.composite':
            from ..services.studio_image_composite import layers
            checked_layers = layers(self.image_layers)
            if (self.provider_id is not None or self.model_id is not None or self.allow_cloud or self.prompt or p
                    or [image_snapshot(s) for s in self.source_snapshots] != [item['source'] for item in checked_layers]):
                raise ValueError('STUDIO_IMAGE_COMPOSITE_LOCAL_INPUT_REQUIRED')
        elif self.operation_id == "m5.image.cutout":
            if self.provider_id is not None or self.model_id is not None or self.allow_cloud or self.prompt or set(p) - {"cutout_output"}:
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
            if self.parameters.target_lufs is not None:
                from ..services.studio_audio_loudness import validate_parameters
                from ..services.audiobook_service import AudiobookError
                try:
                    validate_parameters(p)
                except AudiobookError as exc:
                    raise ValueError(exc.code) from None
            if self.parameters.denoise_profile is not None:
                from ..services.studio_audio_denoise import validate_parameters
                from ..services.audiobook_service import AudiobookError
                try:
                    validate_parameters(self.parameters.model_dump(exclude_none=True))
                except AudiobookError as exc:
                    raise ValueError(exc.code) from None
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
        if self.operation_id == "m7.video.v2v" and len(assets) != 1:
            raise ValueError("STUDIO_VIDEO_SINGLE_REFERENCE_REQUIRED")
        if self.video_reference is not None:
            if (self.operation_id != "m7.video.v2v" or len(assets) != 1
                    or image_snapshot(assets[0]) != image_snapshot(self.video_reference.source)):
                raise ValueError("STUDIO_VIDEO_REFERENCE_SNAPSHOT_MISMATCH")
        if self.video_frames is not None:
            if self.operation_id != "m7.video.i2v":
                raise ValueError("STUDIO_VIDEO_FRAME_OPERATION_INVALID")
            roles = [frame.role for frame in self.video_frames]
            if roles not in (["FIRST"], ["FIRST", "LAST"]):
                raise ValueError("STUDIO_VIDEO_FRAME_ROLE_ORDER_INVALID")
            if [image_snapshot(source) for source in assets] != [image_snapshot(frame.source) for frame in self.video_frames]:
                raise ValueError("STUDIO_VIDEO_FRAME_SNAPSHOT_MISMATCH")
        if self.operation_id == "m7.video.i2v" and len(assets) != (len(self.video_frames) if self.video_frames is not None else 1):
            raise ValueError("STUDIO_VIDEO_FRAME_COUNT_REQUIRED")
        if self.operation_id == "m5.image.i2i" and len(assets) > 5:
            raise ValueError("STUDIO_IMAGE_REFERENCE_LIMIT")
        if not required and self.operation_id not in {"m8.audio.trim", "m5.image.cutout", "m5.image.composite"} and assets:
            raise ValueError("STUDIO_OPERATION_UNUSED_ASSET_REFERENCE")
        if any(s.kind not in {"ASSET", "CREATIVE_DOCUMENT", "COMIC_PANEL"} for s in self.source_snapshots):
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


class CanvasImageNodeQueueResolve(ExecutionModel):
    """A read of one original queue admission, never a new command."""
    request_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
    request_digest: Digest
    canvas_image_node: CanvasImageNodeBinding


class MediaJobAction(ExecutionModel):
    expected_version: int = Field(ge=1)
    expected_request_digest: Digest


class CanvasImageNodeTargetView(MediaJobAction):
    """Read an exact current display record derived from the original Job."""
    expected_incarnation: str = Field(pattern=r'^(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    expected_canvas_version: int = Field(ge=1, le=2**53 - 1)
    expected_canvas_digest: Digest


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
    preview_resolution: Literal["HALF"] | None = None

    @field_validator("preview_resolution", mode="before")
    @classmethod
    def explicit_playback_resolution(cls, value):
        if value != "HALF":
            raise ValueError("STUDIO_PLAYBACK_RESOLUTION_INVALID")
        return value

    @model_serializer(mode="wrap")
    def omit_default_resolution(self, handler):
        value = handler(self)
        if self.preview_resolution is None:
            value.pop("preview_resolution", None)
        return value


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
    @model_validator(mode="after")
    def no_playback_resolution(self):
        if "preview_resolution" in self.model_fields_set:
            raise ValueError("STUDIO_WAVEFORM_PLAYBACK_RESOLUTION_UNSUPPORTED")
        return self

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
