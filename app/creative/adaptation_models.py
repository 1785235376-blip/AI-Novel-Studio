"""Source-bound screenplay proposals; model data never carries write authority."""
from typing import Literal

from pydantic import Field, model_validator, model_serializer

from .models import Identifier, ProposalAction, Scene, StrictCreativeModel


class AdaptationIn(StrictCreativeModel):
    chapter_id: Identifier
    expected_source_version: int = Field(ge=1, strict=True)
    title: str = Field(min_length=1, max_length=240, strict=True)
    instruction: str = Field(default="", max_length=4000, strict=True)
    # Empty means the complete saved chapter, never an implicit context tail.
    selected_text: str = Field(default="", max_length=64000, strict=True)


class AdaptedScene(Scene):
    id: Identifier

    @model_validator(mode="after")
    def screenplay_only(self):
        if self.director_notes or self.source_chapter_id is not None or self.characters:
            raise ValueError("ADAPTATION_HOST_SOURCE_AND_CHARACTER_BINDING_REQUIRED")
        return self


class AdaptationChange(StrictCreativeModel):
    id: Identifier
    kind: Literal["SCENE_SPLIT", "VISUALIZATION", "DIALOGUE", "OMISSION", "INFERENCE"]
    source_quote: str = Field(default="", max_length=8000, strict=True)
    scene_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    note: str = Field(min_length=1, max_length=4000, strict=True)


class AdaptationReport(StrictCreativeModel):
    summary: str = Field(min_length=1, max_length=4000, strict=True)
    changes: list[AdaptationChange] = Field(min_length=1, max_length=100)


class AdaptationOutput(StrictCreativeModel):
    scenes: list[AdaptedScene] = Field(min_length=1, max_length=100)
    report: AdaptationReport

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        # AdaptedScene already rejects all nested director notes. Keep its model
        # prompt schema unchanged when the authored DirectorNote gains geometry.
        schema = super().model_json_schema(*args, **kwargs)
        definitions = schema.get("$defs", {})
        definitions.get("DirectorNote", {}).get("properties", {}).pop("camera_grammar", None)
        for name in ("CameraGrammar", "Point", "Movement"):
            definitions.pop(name, None)
        return schema

    @model_validator(mode="after")
    def linked(self):
        ids = {row.id for row in self.scenes}
        if len(ids) != len(self.scenes) or len({row.sequence for row in self.scenes}) != len(self.scenes):
            raise ValueError("ADAPTATION_DUPLICATE_SCENE")
        if len({row.id for row in self.report.changes}) != len(self.report.changes):
            raise ValueError("ADAPTATION_DUPLICATE_CHANGE")
        for change in self.report.changes:
            if len(set(change.scene_ids)) != len(change.scene_ids) or not set(change.scene_ids).issubset(ids):
                raise ValueError("ADAPTATION_UNKNOWN_SCENE")
            if change.kind != "INFERENCE" and not change.source_quote.strip():
                raise ValueError("ADAPTATION_SOURCE_QUOTE_REQUIRED")
            if change.kind != "OMISSION" and not change.scene_ids:
                raise ValueError("ADAPTATION_CHANGE_SCENE_REQUIRED")
        return self


class AdaptationReview(ProposalAction):
    reviewed_output_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    title: str = Field(min_length=1, max_length=240, strict=True)
    output: AdaptationOutput


class AdaptationPreview(ProposalAction):
    route_id: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    allow_synthetic: bool = Field(default=False, strict=True)


class AdaptationArchiveBinding(StrictCreativeModel):
    contract: Literal["creative-adaptation-text-asset/1"]
    execution_receipt_contract: Literal["creative-adaptation-text-execution/1"]
    final_publication_contract: Literal["creative-adaptation-terminal-publication/1"]
    source_proposal_version: int = Field(ge=1, le=2**53 - 1, strict=True)


class AdaptationJobBinding(StrictCreativeModel):
    contract: Literal["CREATIVE_ADAPTATION_V1"] = "CREATIVE_ADAPTATION_V1"
    proposal_id: Identifier
    project_id: Identifier
    actor_id: Identifier
    scope: dict
    project_incarnation: str = Field(pattern=r"^(file|postgres):[0-9a-f-]{36}$", strict=True)
    chapter_id: Identifier
    source_version: int = Field(ge=1, strict=True)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    archive: AdaptationArchiveBinding | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_shape(self, handler):
        result = handler(self)
        if self.archive is None: result.pop("archive", None)
        return result


def terminal_publication(job):
    """Passive proof minted only by the original executor's final durable publish."""
    from hashlib import sha256
    return {"schema_version": 1, "contract": "creative-adaptation-terminal-publication/1",
        "job_id": job.id, "request_digest": job.expected_request_digest,
        "output_digest": sha256(job.output.encode("utf-8")).hexdigest()}
