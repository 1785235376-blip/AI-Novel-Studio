"""Neutral studio preferences and manual-import contracts.

Intent and preset are presentation hints. No authorization, asset-kind or
execution decision may be based on them.
"""
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

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
