"""Passive OCR job identity for original generation persistence, never authority.

No preparer, scheduler, execution path, provider registration or review promotion
is introduced. All three discriminators independently reserve this domain.
"""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator

OPERATION = 'research_ocr'
ORIGIN = 'research_ocr_model'
Identifier = Annotated[str, Field(min_length=1, max_length=240)]
Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class _LocalScope(_Frozen):
    mode: Literal['local']
    novel_id: Identifier


class _CollaborationScope(_Frozen):
    mode: Literal['collaboration']
    novel_id: Identifier
    workspace_id: Identifier
    storyline_id: Identifier
    branch_id: Identifier


class ResearchOCRJobBinding(_Frozen):
    contract: Literal['RESEARCH_OCR_JOB_V1']
    source_kind: Literal['IMAGE']
    project_id: Identifier
    project_incarnation: Identifier
    actor_id: Identifier
    scope: Annotated[_LocalScope | _CollaborationScope, Field(discriminator='mode')]
    source_id: Identifier
    source_version: int = Field(ge=1, le=2**53 - 1)
    source_digest: Digest
    media_type: Literal['image/png', 'image/jpeg']
    language: Annotated[str, Field(pattern=r'^[A-Za-z]{2,3}(?:-[A-Za-z]{2,8})?$')]
    route_digest: Digest
    reviewed_preview_digest: Digest

    @model_validator(mode='after')
    def identity(self):
        try:
            backend, value = self.project_incarnation.split(':', 1)
            identity = UUID(value)
            if (backend not in {'file', 'postgres'} or str(identity) != value
                    or backend == 'file' and identity.version != 4
                    or self.scope.novel_id != self.project_id):
                raise ValueError('invalid identity')
        except (ValueError, AttributeError):
            raise ValueError('RESEARCH_OCR_BINDING_IDENTITY_INVALID') from None
        return self


class ResearchPDFOCRJobBinding(ResearchOCRJobBinding):
    """Versioned PDF identity; legacy IMAGE serialization remains byte-for-byte."""
    contract: Literal['RESEARCH_PDF_OCR_JOB_V1']
    source_kind: Literal['PDF']
    media_type: Literal['application/pdf']
    page: int = Field(ge=1, le=1000)


def parse_research_ocr_binding(value):
    model = ResearchPDFOCRJobBinding if isinstance(value, dict) and value.get('contract') == 'RESEARCH_PDF_OCR_JOB_V1' else ResearchOCRJobBinding
    return model.model_validate(value)


def is_research_ocr_job(value):
    get = value.get if isinstance(value, dict) else lambda key, default=None: getattr(value, key, default)
    return (('research_ocr_binding' in value if isinstance(value, dict)
             else get('research_ocr_binding') is not None)
            or get('operation') == OPERATION or get('experimental_origin') == ORIGIN)


def research_ocr_job_binding(item):
    try:
        binding = parse_research_ocr_binding(item.get('research_ocr_binding'))
        if (item.get('operation') != OPERATION or item.get('experimental_origin') != ORIGIN
                or item.get('chapter_id') is not None or item.get('graph_binding') is not None
                or item.get('adaptation_binding') is not None or 'creative_director_binding' in item
                or item.get('novel_id') != binding.project_id or item.get('actor_id') != binding.actor_id
                or item.get('scope') != binding.scope.model_dump() or item.get('profile') != 'LOCAL_ONLY'
                or str(UUID(item['id'])) != item['id']
                or not isinstance(item.get('expected_request_digest'), str)
                or re.fullmatch('[a-f0-9]{64}', item['expected_request_digest']) is None):
            raise ValueError('invalid OCR job identity')
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('GENERATION_RESEARCH_OCR_BINDING_INVALID') from None
    return binding.model_dump()
