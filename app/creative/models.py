"""Bounded typed documents for the opt-in Creative Layer.

These are drafts and planning data, not rendered video or original screenplay
records. Source evidence and ownership are exclusively added by the service.
"""
from __future__ import annotations

from typing import Annotated, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

CreativeMode = Literal["SCREENPLAY", "DIRECTOR", "STORYBOARD", "PRODUCTION", "VIDEO_PLANNING", "SCRIPT"]
MODES = ("SCREENPLAY", "DIRECTOR", "STORYBOARD", "PRODUCTION", "VIDEO_PLANNING", "SCRIPT")
USER_MODES = ("NOVEL", "SCREENPLAY", "DIRECTOR", "STORYBOARD", "PRODUCTION")
LEGACY_MODES = ("SCREENPLAY", "STORYBOARD", "VIDEO_PLANNING")
Identifier = Annotated[str, Field(min_length=1, max_length=240, strict=True)]


def identifier() -> str:
    return str(uuid4())


class StrictCreativeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class OptionalProductionFields(StrictCreativeModel):
    """Opt-in extensions must not change existing serialized draft identities."""
    production_optional_fields: ClassVar[tuple[str, ...]] = ()

    @model_serializer(mode="wrap")
    def omit_unset_production_fields(self, handler):
        value = handler(self)
        for name in self.production_optional_fields:
            if value.get(name) is None:
                value.pop(name, None)
        return value


class DirectorVisualTarget(OptionalProductionFields):
    """The existing authored director intent.

    `genre` is an opt-in extension: it is omitted from serialization while unset,
    so an existing stored `visual_target` keeps its exact shape and digest and no
    document is force-upgraded.
    """
    production_optional_fields = ("genre",)
    style: str = Field(default="", max_length=2000, strict=True)
    atmosphere: str = Field(default="", max_length=2000, strict=True)
    reference_works: list[Annotated[str, Field(min_length=1, max_length=1000, strict=True)]] = Field(default_factory=list, max_length=20)
    color: str = Field(default="", max_length=2000, strict=True)
    rhythm: str = Field(default="", max_length=2000, strict=True)
    genre: str | None = Field(default=None, max_length=2000, strict=True)


class DirectorPerformance(StrictCreativeModel):
    character: Identifier
    action: str = Field(default="", max_length=4000, strict=True)
    expression: str = Field(default="", max_length=2000, strict=True)
    state: str = Field(default="", max_length=2000, strict=True)


class Dialogue(StrictCreativeModel):
    speaker: str = Field(min_length=1, max_length=240, strict=True)
    text: str = Field(min_length=1, max_length=16000, strict=True)
    delivery: str = Field(default="", max_length=2000, strict=True)


class DirectorPlanningText(StrictCreativeModel):
    @model_validator(mode="after")
    def nonblank_text(self):
        if any(isinstance(value, str) and not value.strip() for value in self.__dict__.values()):
            raise ValueError("CREATIVE_DIRECTOR_PLANNING_TEXT_REQUIRED")
        return self


class DirectorEvidence(DirectorPlanningText):
    """Exact source excerpt location, not proof of an interpretation."""
    scene_id: Identifier
    field: Literal["action", "dialogue", "emotion", "heading", "location", "time"]
    dialogue_index: int | None = Field(default=None, ge=0, le=199, strict=True)
    excerpt: str = Field(min_length=1, max_length=2000, strict=True)


class DirectorAlternative(DirectorPlanningText):
    choice: str = Field(min_length=1, max_length=2000, strict=True)
    tradeoff: str = Field(min_length=1, max_length=2000, strict=True)


class DirectorPlanning(DirectorPlanningText):
    rationale: str = Field(min_length=1, max_length=4000, strict=True)
    sequence_reason: str = Field(min_length=1, max_length=2000, strict=True)
    duration_reason: str = Field(min_length=1, max_length=2000, strict=True)
    evidence: list[DirectorEvidence] = Field(default_factory=list, max_length=12)
    assumptions: list[Annotated[str, Field(min_length=1, max_length=2000, strict=True)]] = Field(default_factory=list, max_length=12)
    uncertainty: str = Field(min_length=1, max_length=2000, strict=True)
    alternatives: list[DirectorAlternative] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def speculative_choice_is_labelled(self):
        if any(not value.strip() for value in self.assumptions):
            raise ValueError("CREATIVE_DIRECTOR_PLANNING_TEXT_REQUIRED")
        if not self.evidence and not self.assumptions:
            raise ValueError("CREATIVE_DIRECTOR_SPECULATIVE_ASSUMPTION_REQUIRED")
        return self


class DirectorNote(OptionalProductionFields):
    production_optional_fields = ("planning", "shot_suggestion", "composition", "lens", "character_state", "performances", "lighting", "color_palette", "material", "transition")
    id: Identifier = Field(default_factory=identifier)
    note: str = Field(default="", max_length=8000, strict=True)
    shot_size: str = Field(default="", max_length=80, strict=True)
    camera_angle: str = Field(default="", max_length=80, strict=True)
    camera_motion: str = Field(default="", max_length=80, strict=True)
    duration_seconds: int = Field(default=5, ge=1, le=600, strict=True)
    emotion: str = Field(default="", max_length=2000, strict=True)
    pacing: str = Field(default="", max_length=2000, strict=True)
    performance: str = Field(default="", max_length=4000, strict=True)
    blocking: str = Field(default="", max_length=4000, strict=True)
    planning: DirectorPlanning | None = None
    shot_suggestion: str | None = Field(default=None, max_length=8000, strict=True)
    composition: str | None = Field(default=None, max_length=4000, strict=True)
    lens: str | None = Field(default=None, max_length=1000, strict=True)
    character_state: str | None = Field(default=None, max_length=4000, strict=True)
    performances: list[DirectorPerformance] | None = Field(default=None, max_length=100)
    lighting: str | None = Field(default=None, max_length=4000, strict=True)
    color_palette: str | None = Field(default=None, max_length=2000, strict=True)
    material: str | None = Field(default=None, max_length=4000, strict=True)
    transition: str | None = Field(default=None, max_length=2000, strict=True)

    @model_validator(mode="after")
    def distinct_performers(self):
        if self.performances is not None and len({item.character for item in self.performances}) != len(self.performances):
            raise ValueError("CREATIVE_DUPLICATE_PERFORMER")
        return self


class DirectorSceneNote(DirectorNote):
    """An ordered, individually editable direction linked to a screenplay scene."""
    number: int = Field(ge=1, le=10000, strict=True)
    scene_id: Identifier


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


class ShotContinuity(OptionalProductionFields):
    """Authored continuity constraints, never inferred identity guarantees.

    `time` and `lighting` complete the phase's five continuity dimensions
    (character, costume, scene, time, lighting). They are opt-in: while unauthored
    they are omitted from serialization, so existing stored continuity blocks keep
    their exact shape. They are only needed when a dimension has no other authored
    home on the shot — lighting, for instance, is already authored on the card.
    """
    production_optional_fields = ("previous_shot_id", "next_shot_id", "time", "lighting")
    previous_shot_id: Identifier | None = None
    next_shot_id: Identifier | None = None
    characters: str = Field(default="", max_length=4000, strict=True)
    outfit: str = Field(default="", max_length=4000, strict=True)
    environment: str = Field(default="", max_length=4000, strict=True)
    camera: str = Field(default="", max_length=4000, strict=True)
    time: str | None = Field(default=None, max_length=4000, strict=True)
    lighting: str | None = Field(default=None, max_length=4000, strict=True)


class ShotCard(OptionalProductionFields):
    production_optional_fields = ("characters", "emotion", "continuity", "director_note_ids", "video_generation_hint")
    id: Identifier = Field(default_factory=identifier)
    number: int = Field(ge=1, le=10000, strict=True)
    scene_id: Identifier
    shot_size: str = Field(default="MEDIUM", max_length=80, strict=True)
    camera_angle: str = Field(default="EYE_LEVEL", max_length=80, strict=True)
    camera_motion: str = Field(default="STATIC", max_length=80, strict=True)
    duration_seconds: int = Field(default=5, ge=1, le=600, strict=True)
    frame_prompt: str = Field(default="", max_length=16000, strict=True)
    composition: str = Field(default="", max_length=4000, strict=True)
    lens: str = Field(default="", max_length=1000, strict=True)
    lighting: str = Field(default="", max_length=4000, strict=True)
    environment: str = Field(default="", max_length=4000, strict=True)
    sound: str = Field(default="", max_length=4000, strict=True)
    color: str = Field(default="", max_length=2000, strict=True)
    action: str = Field(default="", max_length=16000, strict=True)
    dialogue: list[Dialogue] = Field(default_factory=list, max_length=200)
    sound_effect: str = Field(default="", max_length=4000, strict=True)
    director_notes: list[DirectorNote] = Field(default_factory=list, max_length=100)
    characters: list[Identifier] | None = Field(default=None, max_length=100)
    emotion: str | None = Field(default=None, max_length=4000, strict=True)
    continuity: ShotContinuity | None = None
    director_note_ids: list[Identifier] | None = Field(default=None, max_length=100)
    video_generation_hint: str | None = Field(default=None, max_length=4000, strict=True)

    @model_validator(mode="after")
    def distinct_characters(self):
        if self.characters is not None and len(set(self.characters)) != len(self.characters):
            raise ValueError("CREATIVE_DUPLICATE_SHOT_CHARACTER")
        if self.director_note_ids is not None and len(set(self.director_note_ids)) != len(self.director_note_ids):
            raise ValueError("CREATIVE_DUPLICATE_SHOT_DIRECTOR_NOTE")
        return self


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


class ScriptContent(StrictCreativeModel):
    """Neutral authored text; no scene, chapter or model execution is implied."""
    purpose: Literal["CUSTOM", "ADVERTISEMENT", "MV_NARRATION", "PODCAST", "GAME_DIALOGUE", "PRESENTATION", "SHORT_VIDEO"] = "CUSTOM"
    body: str = Field(min_length=1, max_length=64000, strict=True)

    @model_validator(mode="after")
    def nonblank(self):
        if not self.body.strip():
            raise ValueError("CREATIVE_SCRIPT_BODY_REQUIRED")
        return self


class CreativeDocumentIn(StrictCreativeModel):
    mode: CreativeMode
    title: str = Field(min_length=1, max_length=240, strict=True)
    source_chapter_ids: list[Identifier] = Field(default_factory=list, max_length=64)
    source_independent: bool = Field(default=False, strict=True)
    scenes: list[Scene] = Field(default_factory=list, max_length=200)
    shots: list[ShotCard] = Field(default_factory=list, max_length=200)
    director_notes: list[DirectorSceneNote] = Field(default_factory=list, max_length=200)
    video_plan: VideoPlan | None = None
    script: ScriptContent | None = None

    @model_validator(mode="after")
    def linked_structure(self):
        if not self.title.strip():
            raise ValueError("CREATIVE_TITLE_REQUIRED")
        if self.mode == "SCRIPT":
            if self.script is None or self.scenes or self.shots or self.director_notes or self.video_plan is not None:
                raise ValueError("CREATIVE_SCRIPT_FIELDS_INVALID")
        elif self.script is not None:
            raise ValueError("CREATIVE_SCRIPT_MODE_REQUIRED")
        if len(set(self.source_chapter_ids)) != len(self.source_chapter_ids):
            raise ValueError("CREATIVE_DUPLICATE_SOURCE")
        if len({scene.id for scene in self.scenes}) != len(self.scenes) or len({scene.sequence for scene in self.scenes}) != len(self.scenes):
            raise ValueError("CREATIVE_DUPLICATE_SCENE")
        if len({shot.id for shot in self.shots}) != len(self.shots) or len({shot.number for shot in self.shots}) != len(self.shots):
            raise ValueError("CREATIVE_DUPLICATE_SHOT")
        if len({note.id for note in self.director_notes}) != len(self.director_notes) or len({note.number for note in self.director_notes}) != len(self.director_notes):
            raise ValueError("CREATIVE_DUPLICATE_DIRECTOR_NOTE")
        if any(note.scene_id not in {scene.id for scene in self.scenes} for note in self.director_notes):
            raise ValueError("CREATIVE_DIRECTOR_UNKNOWN_SCENE")
        scenes_by_id = {scene.id: scene for scene in self.scenes}
        planning_notes = [(note, note.scene_id) for note in self.director_notes]
        planning_notes.extend((note, scene.id) for scene in self.scenes for note in scene.director_notes)
        planning_notes.extend((note, shot.scene_id) for shot in self.shots for note in shot.director_notes)
        for note, scene_id in planning_notes:
            if note.planning is None:
                continue
            for evidence in note.planning.evidence:
                if evidence.scene_id != scene_id:
                    raise ValueError("CREATIVE_DIRECTOR_EVIDENCE_SCENE_MISMATCH")
                scene = scenes_by_id.get(scene_id)
                if scene is None:
                    raise ValueError("CREATIVE_DIRECTOR_EVIDENCE_SCENE_UNKNOWN")
                if evidence.field == "dialogue":
                    if evidence.dialogue_index is None or evidence.dialogue_index >= len(scene.dialogue):
                        raise ValueError("CREATIVE_DIRECTOR_EVIDENCE_DIALOGUE_UNKNOWN")
                    text = scene.dialogue[evidence.dialogue_index].text
                else:
                    if evidence.dialogue_index is not None:
                        raise ValueError("CREATIVE_DIRECTOR_EVIDENCE_INDEX_INVALID")
                    text = getattr(scene, evidence.field)
                if evidence.excerpt not in text:
                    raise ValueError("CREATIVE_DIRECTOR_EVIDENCE_EXCERPT_UNKNOWN")
        if self.mode == "DIRECTOR" and (self.shots or self.video_plan is not None):
            raise ValueError("CREATIVE_DIRECTOR_FIELDS_INVALID")
        if self.mode == "SCREENPLAY" and self.director_notes:
            raise ValueError("CREATIVE_SCREENPLAY_FIELDS_INVALID")
        if any(scene.source_chapter_id is not None and scene.source_chapter_id not in self.source_chapter_ids for scene in self.scenes):
            raise ValueError("CREATIVE_SCENE_SOURCE_NOT_BOUND")
        if any(shot.scene_id not in {scene.id for scene in self.scenes} for shot in self.shots):
            raise ValueError("CREATIVE_UNKNOWN_SCENE")
        ordered_shots = sorted(self.shots, key=lambda shot: shot.number)
        notes = {note.id: note for note in self.director_notes}
        for index, shot in enumerate(ordered_shots):
            if shot.director_note_ids is not None and any(
                    note_id not in notes or notes[note_id].scene_id != shot.scene_id for note_id in shot.director_note_ids):
                raise ValueError("CREATIVE_SHOT_DIRECTOR_NOTE_INVALID")
            if shot.continuity is not None:
                previous = ordered_shots[index - 1].id if index else None
                following = ordered_shots[index + 1].id if index + 1 < len(ordered_shots) else None
                if (shot.continuity.previous_shot_id not in (None, previous)
                        or shot.continuity.next_shot_id not in (None, following)):
                    raise ValueError("CREATIVE_SHOT_RELATIONSHIP_NOT_ADJACENT")
        if self.video_plan and any(segment.shot_id not in {shot.id for shot in self.shots} for segment in self.video_plan.segments):
            raise ValueError("CREATIVE_UNKNOWN_SHOT")
        if self.mode == "SCREENPLAY" and (self.shots or self.video_plan is not None):
            raise ValueError("CREATIVE_SCREENPLAY_FIELDS_INVALID")
        if self.mode == "STORYBOARD" and self.video_plan is not None:
            raise ValueError("CREATIVE_STORYBOARD_FIELDS_INVALID")
        return self


class CreativeProductionDocumentIn(CreativeDocumentIn, OptionalProductionFields):
    """Same document owner and endpoint, with explicitly authored visual goals."""
    production_optional_fields = ("visual_target",)
    visual_target: DirectorVisualTarget | None = None

    @model_validator(mode="after")
    def visual_target_mode(self):
        if self.visual_target is not None and self.mode not in {"DIRECTOR", "STORYBOARD", "PRODUCTION"}:
            raise ValueError("CREATIVE_VISUAL_TARGET_MODE_REQUIRED")
        return self


class CreativeDocumentUpdate(CreativeProductionDocumentIn):
    expected_version: int = Field(ge=1, strict=True)


class CreativeDocumentRestore(StrictCreativeModel):
    expected_version: int = Field(ge=1, strict=True)
    restore_version: int = Field(ge=1, strict=True)


class DirectorProposalIn(OptionalProductionFields):
    production_optional_fields = ("visual_target",)
    source_document_id: Identifier
    expected_source_version: int = Field(ge=1, strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=240, strict=True)
    visual_target: DirectorVisualTarget | None = None


class ProposalAction(StrictCreativeModel):
    expected_version: int = Field(ge=1, strict=True)


class DirectorProposalReview(ProposalAction, OptionalProductionFields):
    production_optional_fields = ("visual_target",)
    reviewed_output_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    title: str = Field(min_length=1, max_length=240, strict=True)
    director_notes: list[DirectorSceneNote] = Field(min_length=1, max_length=200)
    visual_target: DirectorVisualTarget | None = None


class DirectorModelPreview(ProposalAction):
    route_id: Identifier


class DirectorModelDispatch(ProposalAction):
    reviewed_preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class DirectorModelNote(DirectorSceneNote):
    # Stable model IDs are required so reparsing cannot mint a new output digest.
    id: Identifier


class DirectorModelOutput(StrictCreativeModel):
    director_notes: list[DirectorModelNote] = Field(min_length=1, max_length=200)


class CreativeDocumentDerive(StrictCreativeModel):
    expected_version: int = Field(ge=1, strict=True)
    mode: Literal["SCREENPLAY", "STORYBOARD", "PRODUCTION"]
    title: str | None = Field(default=None, min_length=1, max_length=240, strict=True)
    shot_policy: Literal["SCENE", "DIRECTOR_NOTES"] = "SCENE"
    script_policy: Literal["TEXT_CHUNKS"] | None = None

    @model_validator(mode="after")
    def shot_policy_mode(self):
        if (self.mode == "SCREENPLAY") != (self.script_policy == "TEXT_CHUNKS"):
            raise ValueError("CREATIVE_SCRIPT_DERIVATION_POLICY_REQUIRED")
        if self.shot_policy != "SCENE" and self.mode != "STORYBOARD":
            raise ValueError("CREATIVE_SHOT_POLICY_MODE_REQUIRED")
        return self
