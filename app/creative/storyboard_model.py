"""Opt-in storyboard transport, separate from legacy screenplay schemas."""
from typing import Literal

from pydantic import Field

from .models import (DirectorModelPreview, DirectorModelDispatch, DirectorModelNote,
                     DirectorPlanning, StrictCreativeModel, Identifier)

STORYBOARD_CONTRACT = "STORYBOARD_SHOT_CONTEXT_V1"
STORYBOARD_STRATEGY = "EXACT_CREATIVE_STORYBOARD_SHOTS_AND_SCENES_NO_IMPLICIT_CONTEXT"


class DirectorStoryboardModelPreview(DirectorModelPreview):
    source_contract: Literal["STORYBOARD_SHOT_CONTEXT_V1"]


class DirectorStoryboardModelDispatch(DirectorModelDispatch):
    source_contract: Literal["STORYBOARD_SHOT_CONTEXT_V1"]


class DirectorStoryboardModelNote(DirectorModelNote):
    source_shot_id: Identifier
    planning: DirectorPlanning


class DirectorStoryboardModelOutput(StrictCreativeModel):
    source_contract: Literal["STORYBOARD_SHOT_CONTEXT_V1"]
    source_document_id: Identifier
    source_version: int = Field(ge=1, strict=True)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    director_notes: list[DirectorStoryboardModelNote] = Field(min_length=1, max_length=200)


def source_mapping(row, source):
    """Validate complete frozen snapshots before consuming their associations."""
    associations = row.get("provenance", {}).get("source_shots", [])
    shots = sorted(source["shots"], key=lambda item: item["number"])
    if not shots or len(associations) != len(shots):
        raise ValueError("CREATIVE_MODEL_STORYBOARD_ASSOCIATION_CHANGED")
    result = []
    for association, shot in zip(associations, shots):
        if (association.get("source_shot") != shot or association.get("source_shot_id") != shot["id"]
                or association.get("scene_id") != shot["scene_id"]
                or association.get("source_number") != shot["number"] or not association.get("note_id")):
            raise ValueError("CREATIVE_MODEL_STORYBOARD_ASSOCIATION_CHANGED")
        result.append({key: association[key] for key in ("source_shot_id", "note_id", "scene_id", "source_number")})
    if len({item["note_id"] for item in result}) != len(result):
        raise ValueError("CREATIVE_MODEL_STORYBOARD_ASSOCIATION_CHANGED")
    return result
