"""Research OCR/scan-PDF/image/chart/table trusted adapter contracts.

No default model, provider installation, external IO, or automatic Canon writes.
Output is untrusted research awaiting explicit review; original bytes stay owned
by ResearchLibraryService and are never copied into job metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from pydantic import Field, model_validator

from .research_library import StrictInput

AnalysisKind = Literal['OCR', 'SCAN_PDF_VISION', 'IMAGE_UNDERSTANDING', 'CHART_UNDERSTANDING', 'TABLE_UNDERSTANDING']


class ResearchVisionCapability(StrictInput):
    provider_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    model_revision: str = Field(min_length=1, max_length=240)
    local: bool
    operations: list[AnalysisKind] = Field(min_length=1, max_length=5)
    verification: Literal['MOCK_ONLY', 'CONTRACT_VERIFIED']


class ResearchAnalysisIn(StrictInput):
    source_id: str = Field(min_length=1, max_length=200)
    source_version: int = Field(ge=1)
    operation: AnalysisKind
    pages: list[int] = Field(default_factory=list, max_length=1000)

    @model_validator(mode='after')
    def page_bounds(self):
        if len(set(self.pages)) != len(self.pages) or any(page < 1 or page > 1000 for page in self.pages):
            raise ValueError('RESEARCH_ANALYSIS_PAGE_INVALID')
        return self


class ResearchAnalysisBlock(StrictInput):
    kind: Literal['TEXT', 'IMAGE_DESCRIPTION', 'CHART', 'TABLE']
    page: int = Field(ge=1, le=1000)
    text: str = Field(default='', max_length=8000)
    cells: list[list[str]] = Field(default_factory=list, max_length=100)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)

    @model_validator(mode='after')
    def valid(self):
        if not self.text and not self.cells: raise ValueError('RESEARCH_ANALYSIS_BLOCK_EMPTY')
        if any(len(row) > 50 or any(len(cell) > 1000 for cell in row) for row in self.cells):
            raise ValueError('RESEARCH_ANALYSIS_TABLE_LIMIT')
        if self.cells and self.kind != 'TABLE': raise ValueError('RESEARCH_ANALYSIS_TABLE_KIND_REQUIRED')
        if self.bbox is not None and (any(not 0 <= x <= 1 for x in self.bbox)
                                    or self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]):
            raise ValueError('RESEARCH_ANALYSIS_BBOX_INVALID')
        return self


class ResearchAnalysisResult(StrictInput):
    blocks: list[ResearchAnalysisBlock] = Field(min_length=1, max_length=1000)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def warnings_bounded(self):
        if any(len(warning) > 1000 for warning in self.warnings): raise ValueError('RESEARCH_ANALYSIS_WARNING_LIMIT')
        return self


@dataclass(frozen=True)
class ResearchVisionInput:
    content: bytes
    media_format: str
    pages: tuple[int, ...]
    source_id: str
    source_version: int
    source_digest: str


class ResearchVisionProvider(Protocol):
    capability: ResearchVisionCapability

    def analyze(self, value: ResearchVisionInput, operation: str, dispatch_guard) -> dict: ...


class SyntheticResearchVisionProvider:
    """Explicit synthetic contract fixture; never infers from input pixels."""
    capability = ResearchVisionCapability(provider_id='synthetic-research-vision', model_id='fixture',
        model_revision='1', local=True, operations=['OCR', 'SCAN_PDF_VISION', 'IMAGE_UNDERSTANDING',
        'CHART_UNDERSTANDING', 'TABLE_UNDERSTANDING'], verification='MOCK_ONLY')

    def analyze(self, value, operation, dispatch_guard):
        dispatch_guard()
        kind = {'IMAGE_UNDERSTANDING': 'IMAGE_DESCRIPTION', 'CHART_UNDERSTANDING': 'CHART',
                'TABLE_UNDERSTANDING': 'TABLE'}.get(operation, 'TEXT')
        return {'blocks': [{'kind': kind, 'page': (value.pages or (1,))[0],
                            'text': 'Synthetic contract result; no image understanding was performed.',
                            'cells': [['fixture', '1']] if kind == 'TABLE' else []}],
                'warnings': ['MOCK_ONLY: synthetic result, not source evidence.']}


def research_analysis_jobs(service):
    from .common import StaleSourceError
    from .review_adapter_jobs import ReviewAdapterJobs
    from .planning import digest
    from ..import_parsers import decode_base64

    def source(nid, scope, actor, request):
        value = ResearchAnalysisIn.model_validate(request)
        row = service._source(nid, scope, actor, value.source_id)
        if row['version'] != value.source_version: raise StaleSourceError('RESEARCH_ANALYSIS_SOURCE_STALE')
        if row.get('format') not in {'PDF', 'IMAGE'} or not row.get('content_base64'):
            raise ValueError('RESEARCH_ANALYSIS_IMAGE_OR_PDF_REQUIRED')
        if value.operation == 'SCAN_PDF_VISION' and row['format'] != 'PDF':
            raise ValueError('RESEARCH_ANALYSIS_SCAN_PDF_REQUIRED')
        if row['format'] == 'IMAGE' and any(page != 1 for page in value.pages):
            raise ValueError('RESEARCH_ANALYSIS_PAGE_INVALID')
        known_pages = set(row.get('unread_pages', [])) | {p['page'] for p in row.get('paragraphs', []) if p.get('page')}
        if value.pages and any(page not in known_pages for page in value.pages):
            raise ValueError('RESEARCH_ANALYSIS_PAGE_INVALID')
        provenance = {'source_id': row['id'], 'source_version': row['version'],
                      'source_digest': row['content_sha256'], 'access': row['access'], 'source_layer': 'RESEARCH'}
        return provenance, ResearchVisionInput(decode_base64(row['content_base64']), row['format'], tuple(value.pages),
            row['id'], row['version'], row['content_sha256'])

    def execute(provider, value, request, guard):
        capability = ResearchVisionCapability.model_validate(provider.capability)
        if request['operation'] not in capability.operations: raise ValueError('RESEARCH_ANALYSIS_OPERATION_UNSUPPORTED')
        guard()
        result = ResearchAnalysisResult.model_validate(provider.analyze(value, request['operation'], guard)).model_dump()
        for block in result['blocks']:
            if value.pages and block['page'] not in value.pages: raise ValueError('RESEARCH_ANALYSIS_PAGE_MISMATCH')
            if value.media_format == 'IMAGE' and block['page'] != 1: raise ValueError('RESEARCH_ANALYSIS_PAGE_MISMATCH')
            block['citation'] = {'source_id': value.source_id, 'source_version': value.source_version,
                                 'source_digest': value.source_digest, 'page': block['page'],
                                 'result_digest': digest(block), 'layer': 'RESEARCH_DERIVED'}
        result.update(verification=capability.verification, original_unchanged=True, automatic_canon=False,
                      model_quality='NOT_RUN')
        guard(); return result

    return ReviewAdapterJobs(service, 'research_analysis_jobs', source,
                            lambda: service.vision_provider, execute)
