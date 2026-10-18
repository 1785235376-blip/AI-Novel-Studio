"""Allowlisted versioned transport data over original Director owners."""
from typing import Literal
from pydantic import Field, field_validator
from .director_lifecycle import _Strict, Digest, Identifier
from .models import DirectorSceneNote, DirectorVisualTarget
from .proposals import DirectorProposalService


class PreviewInput(_Strict):
    expected_version: int = Field(ge=1)
    route_id: str = Field(min_length=1, max_length=160)
    allow_synthetic: Literal[False] = False
    max_output_tokens: int = Field(default=512, ge=1, le=2048)
    temperature: float = Field(default=0.0, ge=0, le=2, allow_inf_nan=False)

    @field_validator('allow_synthetic', mode='before')
    @classmethod
    def literal_false_boolean(cls, value):
        if type(value) is not bool or value is not False:
            raise ValueError('DIRECTOR_MODEL_NON_SYNTHETIC_REQUIRED')
        return value


class ScreenplayPreviewInput(PreviewInput):
    planning_mode: Literal['MULTI_SHOT_V1'] | None = None


class DispatchInput(_Strict):
    expected_version: int = Field(ge=1)
    reviewed_preview_digest: Digest


class PrepareInput(_Strict):
    expected_version: int = Field(ge=1)
    terminal_evidence_digest: Digest


class Parameters(_Strict):
    max_output_tokens: int = Field(ge=1, le=2048)
    temperature: float = Field(ge=0, le=2, allow_inf_nan=False)


class PreviewReceipt(_Strict):
    contract: Literal['DIRECTOR_MODEL_PREVIEW_V1'] = 'DIRECTOR_MODEL_PREVIEW_V1'
    proposal_id: Identifier
    version: int = Field(ge=1)
    reviewed_preview_digest: Digest
    prompt: str = Field(min_length=1, max_length=DirectorProposalService.MAX_RECORD_BYTES)
    parameters: Parameters
    route_id: Identifier
    route_fingerprint: Digest
    provider_id: Identifier
    model_id: Identifier
    source_document_id: Identifier
    source_version: int = Field(ge=1)
    source_digest: Digest
    source_mode: Literal['STORYBOARD'] = 'STORYBOARD'
    local_only: Literal[True] = True
    reserve_microusd: Literal[0] = 0
    model_called: Literal[False] = False
    automatic_retry: Literal[False] = False
    quality_verification: Literal['NOT_RUN'] = 'NOT_RUN'


class SourceMapping(_Strict):
    source_shot_id: Identifier
    note_id: Identifier
    scene_id: Identifier
    source_number: int = Field(ge=1, le=10000)


class PendingProvenance(_Strict):
    method: Literal['MODEL_ASSISTED']
    model_called: Literal[True]
    provider_id: Identifier
    model_id: Identifier
    model_version: str | None = Field(max_length=1000)
    route_fingerprint: Digest
    synthetic: Literal[False]
    parameters: Parameters
    source_mode: Literal['STORYBOARD']
    source_document_id: Identifier
    source_version: int = Field(ge=1)
    source_digest: Digest
    source_mapping: list[SourceMapping] = Field(min_length=1, max_length=200)
    job_id: Identifier
    request_digest: Digest
    preview_digest: Digest
    candidate_output_digest: Digest
    terminal_evidence_digest: Digest
    quality_verification: Literal['HUMAN_REVIEW_REQUIRED']


class PendingReceipt(_Strict):
    contract: Literal['DIRECTOR_MODEL_PENDING_REVIEW_V1'] = 'DIRECTOR_MODEL_PENDING_REVIEW_V1'
    proposal_id: Identifier
    expected_version: int = Field(ge=1)
    director_notes: list[DirectorSceneNote] = Field(min_length=1, max_length=200)
    output_digest: Digest
    visual_target: DirectorVisualTarget | None
    provenance: PendingProvenance


class ScreenplayPreviewReceipt(PreviewReceipt):
    contract: Literal['DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V2'] = 'DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V2'
    source_mode: Literal['SCREENPLAY'] = 'SCREENPLAY'


class ScreenplaySourceMapping(_Strict):
    note_id: Identifier
    scene_id: Identifier
    source_sequence: int = Field(ge=1, le=10000)
    number: int = Field(ge=1, le=200)


class ScreenplayPendingProvenance(PendingProvenance):
    source_mode: Literal['SCREENPLAY']
    source_mapping: list[ScreenplaySourceMapping] = Field(min_length=1, max_length=200)


class ScreenplayPendingReceipt(PendingReceipt):
    contract: Literal['DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V2'] = 'DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V2'
    provenance: ScreenplayPendingProvenance


class ScreenplayAllowedSlot(_Strict):
    note_id: Identifier
    scene_id: Identifier
    source_sequence: int = Field(ge=1, le=10000)
    slot: int = Field(ge=1, le=3)


class ScreenplayShotPlanPreviewReceipt(ScreenplayPreviewReceipt):
    contract: Literal['DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V3'] = 'DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V3'
    planning_mode: Literal['MULTI_SHOT_V1'] = 'MULTI_SHOT_V1'
    allowed_source_mapping: list[ScreenplayAllowedSlot] = Field(min_length=3, max_length=6)


class ScreenplayShotPlanPendingProvenance(ScreenplayPendingProvenance):
    output_contract: Literal['INDEPENDENT_SCREENPLAY_SHOT_PLAN_V1']
    allowed_source_mapping: list[ScreenplayAllowedSlot] = Field(min_length=3, max_length=6)
    source_mapping: list[ScreenplaySourceMapping] = Field(min_length=1, max_length=6)


class ScreenplayShotPlanPendingReceipt(ScreenplayPendingReceipt):
    contract: Literal['DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V3'] = 'DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V3'
    provenance: ScreenplayShotPlanPendingProvenance
    director_notes: list[DirectorSceneNote] = Field(min_length=1, max_length=6)


def project_preview(row, *, screenplay=False):
    if type(screenplay) is not bool: raise ValueError("DIRECTOR_MODEL_TRANSPORT_OPTION_INVALID")
    preview = row['model_preview']
    route = preview['broker_decision']['chosen']
    binding = preview['source_binding']
    expected_contract = 'CREATIVE_DIRECTOR_SCREENPLAY_SOURCE_V2' if screenplay else 'CREATIVE_DIRECTOR_SOURCE_V1'
    expected_kind = 'SCREENPLAY' if screenplay else 'STORYBOARD'
    if binding.get('contract') != expected_contract or binding.get('source_kind') != expected_kind:
        raise ValueError('DIRECTOR_MODEL_TRANSPORT_SOURCE_VERSION_UNSUPPORTED')
    if preview['allow_synthetic'] is not False or route['synthetic'] is not False:
        raise ValueError('DIRECTOR_MODEL_NON_SYNTHETIC_REQUIRED')
    from .screenplay_model import SHOT_PLAN_CONTRACT
    shot_plan = screenplay and preview.get('output_contract') == SHOT_PLAN_CONTRACT
    model = ScreenplayShotPlanPreviewReceipt if shot_plan else ScreenplayPreviewReceipt if screenplay else PreviewReceipt
    extra = {'allowed_source_mapping': preview['allowed_source_mapping']} if shot_plan else {}
    return model(**extra, proposal_id=row['id'], version=row['version'],
        reviewed_preview_digest=preview['preview_digest'], prompt=preview['prompt'],
        parameters=preview['parameters'], route_id=preview['route_id'], route_fingerprint=preview['route_fingerprint'],
        provider_id=route['provider_id'], model_id=route['model_id'],
        source_document_id=binding['source_document_id'], source_version=binding['source_version'],
        source_digest=binding['source_digest']).model_dump()


def project_pending(candidate, *, screenplay=False):
    if type(screenplay) is not bool: raise ValueError("DIRECTOR_MODEL_TRANSPORT_OPTION_INVALID")
    provenance = candidate['provenance']
    # Reservation internals, raw output digest and any future fields are not
    # automatically added to the public projection.
    from .screenplay_model import SHOT_PLAN_CONTRACT
    shot_plan = screenplay and provenance.get('output_contract') == SHOT_PLAN_CONTRACT
    provenance_model = ScreenplayShotPlanPendingProvenance if shot_plan else ScreenplayPendingProvenance if screenplay else PendingProvenance
    model = ScreenplayShotPlanPendingReceipt if shot_plan else ScreenplayPendingReceipt if screenplay else PendingReceipt
    selected = {key: provenance[key] for key in provenance_model.model_fields}
    return model(**{key: candidate[key] for key in ('proposal_id', 'expected_version',
        'director_notes', 'output_digest', 'visual_target')}, provenance=selected).model_dump()
