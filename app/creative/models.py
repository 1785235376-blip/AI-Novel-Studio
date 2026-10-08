"""Bounded typed documents for the opt-in Creative Layer.

These are drafts and planning data, not rendered video or original screenplay
records. Source evidence and ownership are exclusively added by the service.
"""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

CreativeMode = Literal["SCREENPLAY", "STORYBOARD", "VIDEO_PLANNING"]
MODES = ("SCREENPLAY", "STORYBOARD", "VIDEO_PLANNING")
Identifier = Annotated[str, Field(min_length=1, max_length=240, strict=True)]


def identifier() -> str:
    return str(uuid4())


class StrictCreativeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Dialogue(StrictCreativeModel):
    speaker: str = Field(min_length=1, max_length=240, strict=True)
    text: str = Field(min_length=1, max_length=16000, strict=True)
    delivery: str = Field(default="", max_length=2000, strict=True)


class DirectorNote(StrictCreativeModel):
    id: Identifier = Field(default_factory=identifier)
    note: str = Field(default="", max_length=8000, strict=True)
    shot_size: str = Field(default="", max_length=80, strict=True)
    camera_angle: str = Field(default="", max_length=80, strict=True)
    camera_motion: str = Field(default="", max_length=80, strict=True)
    duration_seconds: int = Field(default=5, ge=1, le=600, strict=True)
    emotion: str = Field(default="", max_length=2000, strict=True)
    pacing: str = Field(default="", max_length=2000, strict=True)
    performance: str = Field(default="", max_length=4000, strict=True)


class Scene(StrictCreativeModel):
    id: Identifier = Field(default_factory=identifier)
    sequence: int = Field(ge=1, le=10000, strict=True)
    source_chapter_id: Identifier | None = None
    heading: str = Field(min_length=1, max_length=500, strict=True)
    time: str = Field(default="", max_length=1000, strict=True)
    location: str = Field(default="", max_length=1000, strict=True)
    characters: list[Identifier] = Field(default_factory=list, max_length=100)
    action: str = Field(default="", max_length=32000, strict=True)
    dialogue: list[Dialogue] = Field(default_factory=list, max_length=200)
    emotion: str = Field(default="", max_length=4000, strict=True)
    director_notes: list[DirectorNote] = Field(default_factory=list, max_length=100)


class ShotCard(StrictCreativeModel):
    id: Identifier = Field(default_factory=identifier)
    number: int = Field(ge=1, le=10000, strict=True)
    scene_id: Identifier
    shot_size: str = Field(default="MEDIUM", max_length=80, strict=True)
    camera_angle: str = Field(default="EYE_LEVEL", max_length=80, strict=True)
    camera_motion: str = Field(default="STATIC", max_length=80, strict=True)
    duration_seconds: int = Field(default=5, ge=1, le=600, strict=True)
    frame_prompt: str = Field(default="", max_length=16000, strict=True)
    composition: str = Field(default="", max_length=4000, strict=True)
    color: str = Field(default="", max_length=2000, strict=True)
    action: str = Field(default="", max_length=16000, strict=True)
    dialogue: list[Dialogue] = Field(default_factory=list, max_length=200)
    sound_effect: str = Field(default="", max_length=4000, strict=True)
    director_notes: list[DirectorNote] = Field(default_factory=list, max_length=100)


class VideoSegment(StrictCreativeModel):
    shot_id: Identifier
    duration_seconds: int = Field(default=5, ge=1, le=600, strict=True)
    note: str = Field(default="", max_length=4000, strict=True)


class VideoPlan(StrictCreativeModel):
    frame_rate: int = Field(default=24, ge=1, le=120, strict=True)
    width: int = Field(default=1920, ge=16, le=7680, strict=True)
    height: int = Field(default=1080, ge=16, le=7680, strict=True)
    notes: str = Field(default="", max_length=8000, strict=True)
    segments: list[VideoSegment] = Field(default_factory=list, max_length=200)


class CreativeDocumentIn(StrictCreativeModel):
    mode: CreativeMode
    title: str = Field(min_length=1, max_length=240, strict=True)
    source_chapter_ids: list[Identifier] = Field(default_factory=list, max_length=64)
    source_independent: bool = Field(default=False, strict=True)
    scenes: list[Scene] = Field(default_factory=list, max_length=200)
    shots: list[ShotCard] = Field(default_factory=list, max_length=200)
    video_plan: VideoPlan | None = None

    @model_validator(mode="after")
    def linked_structure(self):
        if not self.title.strip():
            raise ValueError("CREATIVE_TITLE_REQUIRED")
        if len(set(self.source_chapter_ids)) != len(self.source_chapter_ids):
            raise ValueError("CREATIVE_DUPLICATE_SOURCE")
        if len({scene.id for scene in self.scenes}) != len(self.scenes) or len({scene.sequence for scene in self.scenes}) != len(self.scenes):
            raise ValueError("CREATIVE_DUPLICATE_SCENE")
        if len({shot.id for shot in self.shots}) != len(self.shots) or len({shot.number for shot in self.shots}) != len(self.shots):
            raise ValueError("CREATIVE_DUPLICATE_SHOT")
        if any(scene.source_chapter_id is not None and scene.source_chapter_id not in self.source_chapter_ids for scene in self.scenes):
            raise ValueError("CREATIVE_SCENE_SOURCE_NOT_BOUND")
        if any(shot.scene_id not in {scene.id for scene in self.scenes} for shot in self.shots):
            raise ValueError("CREATIVE_UNKNOWN_SCENE")
        if self.video_plan and any(segment.shot_id not in {shot.id for shot in self.shots} for segment in self.video_plan.segments):
            raise ValueError("CREATIVE_UNKNOWN_SHOT")
        if self.mode == "SCREENPLAY" and (self.shots or self.video_plan is not None):
            raise ValueError("CREATIVE_SCREENPLAY_FIELDS_INVALID")
        if self.mode == "STORYBOARD" and self.video_plan is not None:
            raise ValueError("CREATIVE_STORYBOARD_FIELDS_INVALID")
        return self


class CreativeDocumentUpdate(CreativeDocumentIn):
    expected_version: int = Field(ge=1, strict=True)
