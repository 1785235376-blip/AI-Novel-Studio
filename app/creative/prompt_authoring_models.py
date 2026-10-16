"""Strict request DTOs for the dedicated Prompt authoring entry (R3-W).

Only fields a user is entitled to supply. Everything the server must decide — approval
time, reviewer identity, internal asset owner, project-binding markers, execution
receipts and model-run proof — is **absent from these models**, so
`extra="forbid"` makes a client that tries to send it a hard 422 rather than a silent
override (directive §W2).

Creative text is deliberately **not** stripped: leading/trailing whitespace, newlines,
CJK and emoji are authored content, and length is measured in real UTF-8 bytes.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: A prompt body's real byte budget, matching the read-side cap.
PROMPT_TEXT_MAX_BYTES = 64 * 1024
MAX_IDENTIFIER = 240
MAX_IDS = 100
MAX_NOTE = 2000

Identifier = Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER, strict=True)]
RequestId = Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER, strict=True)]


class StrictPromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)

    text: str = Field(min_length=1)
    negative_prompt: str = ""
    purpose: Literal["IMAGE", "VIDEO", "AUDIO", "TEXT"] = "IMAGE"
    origin: Literal["MANUAL", "AI_GENERATED", "IMPORTED"] = "MANUAL"
    model_reference: str = Field(default="", max_length=MAX_IDENTIFIER)
    #: Non-executing generation parameters. Applying a prompt never runs a model.
    parameters: dict[str, object] = Field(default_factory=dict)
    seed: int | None = Field(default=None, ge=0, le=2**53 - 1)
    character_ids: list[Identifier] = Field(default_factory=list, max_length=MAX_IDS)
    scene_ids: list[Identifier] = Field(default_factory=list, max_length=MAX_IDS)
    shot_ids: list[Identifier] = Field(default_factory=list, max_length=MAX_IDS)
    reference_asset_ids: list[Identifier] = Field(default_factory=list, max_length=MAX_IDS)
    change_note: str = Field(default="", max_length=MAX_NOTE)
    change_reason: str = Field(default="", max_length=MAX_NOTE)
    redacted: bool = False
    request_id: RequestId

    @field_validator("text")
    @classmethod
    def text_within_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PROMPT_TEXT_MAX_BYTES:
            raise ValueError("PROMPT_TEXT_TOO_LARGE")
        return value

    @field_validator("negative_prompt", "change_note", "change_reason")
    @classmethod
    def note_within_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PROMPT_TEXT_MAX_BYTES:
            raise ValueError("PROMPT_TEXT_TOO_LARGE")
        return value

    @field_validator("character_ids", "scene_ids", "shot_ids", "reference_asset_ids")
    @classmethod
    def distinct_ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("PROMPT_BINDING_DUPLICATE")
        return value


class PromptCreateIn(StrictPromptRequest):
    """Create a new prompt family. Revision 1 is allocated by the server."""


class PromptRevisionIn(StrictPromptRequest):
    """Save the next revision of an existing family.

    `expected_previous_asset_id` / `expected_revision` are the caller's statement of
    which revision it was editing. The server refuses to write if the family has moved
    past it, so a concurrent edit can never silently overwrite someone else's.
    """
    expected_previous_asset_id: Identifier
    expected_revision: int = Field(ge=1, le=100000)


class PromptAuthoringReceipt(BaseModel):
    """What the server actually did. Server-decided facts only."""
    model_config = ConfigDict(extra="forbid")

    family_id: str
    asset_id: str
    revision: int
    asset_version: int
    text_digest: str
    idempotent_replay: bool
    previous_asset_id: str | None = None
    payload_digest: str
