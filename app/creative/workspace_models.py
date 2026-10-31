"""Neutral studio preferences and manual-import contracts.

Intent and preset are presentation hints. No authorization, asset-kind or
execution decision may be based on them.
"""
from typing import Literal

from pydantic import ConfigDict, Field, TypeAdapter, field_validator, model_validator

from ..experimental.media import StrictModel
from ..experimental.production_lineage import LineageInput

CreativeIntent = Literal["NOVEL_WRITING", "NOVEL_ADAPTATION", "AI_SHORT_FILM", "COMMERCIAL_CG",
                         "ADVERTISEMENT", "MUSIC_VIDEO", "GAME_PREVIS", "IMAGE_DESIGN", "PODCAST_VOICE",
                         "BLANK", "CUSTOM"]
WorkspacePreset = Literal["BLANK", "TEXT", "IMAGE", "VIDEO", "AUDIO", "EDITING", "MIXED"]
# CONTENT_POLICY_FRAMEWORK: RESERVED (not IMPLEMENTED).
# A project-level policy vocabulary for a future content policy framework. It is
# reserved as an OPTIONAL field on the existing preference owner so an older row
# that never stored it still validates, and so no existing client, filter, export
# or permission decision changes today. `None` means "not set" and is read as
# STANDARD through `app/creative/content_policy.py`. Unknown values are refused by
# the literal itself.
ContentPolicy = Literal["STANDARD", "MATURE", "RESTRICTED", "CUSTOM"]


class BlankProjectIn(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    id: str | None = Field(default=None, max_length=240)


class WorkspacePreferences(StrictModel):
    intents: list[CreativeIntent] = Field(default_factory=list, max_length=11)
    preset: WorkspacePreset = "BLANK"
    custom_intent: str = Field(default="", max_length=240)
    # CONTENT_POLICY_FRAMEWORK: RESERVED — optional on purpose: a row written before
    # this field existed validates with `None`, and the effective value is STANDARD.
    content_policy: ContentPolicy | None = None

    @model_validator(mode="after")
    def unique_intents(self):
        if len(set(self.intents)) != len(self.intents):
            raise ValueError("CREATIVE_INTENTS_DUPLICATE")
        return self


class WorkspacePreferencesUpdate(WorkspacePreferences):
    expected_version: int = Field(ge=0, strict=True)


StudioAssetKind = Literal["image", "video", "audio", "model", "text", "prompt"]


class StudioAssetQuery(StrictModel):
    """Read-only filters over existing Studio metadata, with opt-in paging."""
    q: str | None = Field(default=None, max_length=255)
    kind: StudioAssetKind | None = None
    limit: int | None = Field(default=None, ge=1, le=100, strict=True)
    offset: int | None = Field(default=None, ge=0, le=1_000_000, strict=True)
    page_mode: Literal["cursor"] | None = None
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("cursor", mode="before")
    @classmethod
    def raw_cursor(cls, value):
        # StrictModel trims strings; enforce the token wire bound beforehand.
        if value is not None and (not isinstance(value, str) or not value.isascii()
                or not 1 <= len(value) <= 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in value)):
            raise ValueError("ASSET_QUERY_INVALID")
        return value

    @model_validator(mode="after")
    def pagination_mode(self):
        if ((self.page_mode == "cursor" and self.offset is not None)
                or (self.cursor is not None and self.page_mode != "cursor")):
            raise ValueError("ASSET_QUERY_INVALID")
        return self

    @classmethod
    def from_query_params(cls, params):
        """Decode only after the original route authority has admitted a read.

        QueryParams.get keeps the existing last-scalar-wins contract. Pydantic
        wire decoding retains integral decimal strings (e.g. 1.0); the internal
        DTO remains strict. Check the raw keyword bound before whitespace trim.
        """
        try:
            q = params.get("q")
            if q is not None and len(q) > 255:
                raise ValueError("ASSET_QUERY_INVALID")
            query = cls(q=q, kind=params.get("kind"), page_mode=params.get("page_mode"), cursor=params.get("cursor"),
                        limit=TypeAdapter(int).validate_python(params["limit"]) if "limit" in params else None,
                        offset=TypeAdapter(int).validate_python(params["offset"]) if "offset" in params else None)
            deleted = TypeAdapter(bool).validate_python(params.get("include_deleted", "false"))
            return query, deleted
        except ValueError:
            raise ValueError("ASSET_QUERY_INVALID") from None

    @classmethod
    def openapi_parameters(cls):
        properties = cls.model_json_schema()["properties"]
        properties["include_deleted"] = {"type": "boolean", "default": False}
        return [{"name": name, "in": "query", "required": False, "schema": schema}
                for name, schema in properties.items()]

    @field_validator("q", mode="before")
    @classmethod
    def safe_keyword(cls, value):
        if isinstance(value, str) and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("ASSET_QUERY_INVALID")
        return value


class AudioHistoryRestorePreview(StrictModel):
    expected_version: int = Field(ge=1, strict=True)


class AudioHistoryRestoreConfirm(AudioHistoryRestorePreview):
    expected_restore_digest: str = Field(pattern=r"^[a-f0-9]{64}$", strict=True)


class ProjectCapacityLimitUpdate(StrictModel):
    limit_bytes: int = Field(ge=1, le=64 * 1024 * 1024 * 1024, strict=True)
    expected_version: int = Field(ge=0, strict=True)


class ManualAssetImport(StrictModel):
    filename: str = Field(min_length=1, max_length=255)
    kind: Literal["image", "video", "audio"] = "image"
    content_base64: str = Field(min_length=1, max_length=4 * ((25 * 1024 * 1024 + 2) // 3))
    idempotency_key: str = Field(min_length=1, max_length=120)


class ManualModelReferenceImport(StrictModel):
    contract: Literal["studio-static-glb-import/1"]
    filename: str = Field(min_length=1, max_length=255)
    kind: Literal["model"] = "model"
    content_base64: str = Field(min_length=1, max_length=4 * ((8 * 1024 * 1024 + 2) // 3))
    idempotency_key: str = Field(min_length=1, max_length=120)


class ManualBinaryMask(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)
    contract: Literal["manual-binary-mask/1"]
    source_version: int = Field(ge=1, le=2**53 - 1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: int = Field(ge=64, le=1024, multiple_of=8)
    height: int = Field(ge=64, le=1024, multiple_of=8)
    bitplane_base64: str = Field(min_length=1, max_length=174764)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")


class AssetVersion(StrictModel):
    expected_version: int = Field(ge=1, strict=True)


class StudioLineageInput(LineageInput):
    expected_version: int = Field(ge=1, strict=True)


RelationshipKind = Literal["SOURCE_OF", "DERIVED_FROM", "REFERENCES", "USED_IN",
                           "ALTERNATE_VERSION", "APPROVED_FOR", "LINKED_CONTEXT"]


class RelationshipTarget(StrictModel):
    kind: Literal["ASSET", "CHAPTER", "SCREENPLAY"]
    id: str = Field(min_length=1, max_length=240)
    version: int = Field(ge=0, strict=True)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class AssetRelationshipIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    type: RelationshipKind
    target: RelationshipTarget
    reason: str = Field(default="", max_length=1000)


class StaticSceneDepthExport(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract: Literal["studio-static-glb-depth-export/1"]
    source_version: int = Field(ge=1, le=2**53 - 1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    yaw: float = Field(default=35.0, ge=-180, le=180, allow_inf_nan=False)
    pitch: float = Field(default=25.0, ge=-89, le=89, allow_inf_nan=False)


class StaticSceneClayExport(StaticSceneDepthExport):
    contract: Literal["studio-static-glb-clay-export/1"]


class StaticSceneClaySave(StaticSceneClayExport):
    contract: Literal["studio-static-glb-clay-asset/1"]
    reviewed_png_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm_reference: Literal[True]
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")


class StaticCameraExport(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract: Literal["studio-static-glb-camera-export/1"]
    source_version: int = Field(ge=1, le=2**53 - 1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    scene_index: int = Field(ge=0, le=63)
    node_index: int = Field(ge=0, le=255)
    camera_index: int = Field(ge=0, le=63)
    profile: Literal["GLTF_2_CAMERA_ONLY"]


