"""PDF source/page identity in original stores, no dispatch admission."""
import base64
from copy import deepcopy
import pytest
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_vision import PreparedResearchOCRSource
from app.experimental.research_ocr_binding import ResearchOCRJobBinding, ResearchPDFOCRJobBinding
from app.experimental.common import StaleSourceError
from app.repositories.generation_repository import GenerationProjectIdentityError
from test_v2_independent_workspace import rig
from test_research_ocr_job_persistence_additive import record, reopen
from test_r4_research_library import payload
from test_local_pdf_raster_additive import PDF


def pdf_record(e):
    value = record(e)
    binding = value['research_ocr_binding']
    binding.update(contract='RESEARCH_PDF_OCR_JOB_V1', source_kind='PDF', media_type='application/pdf', page=2)
    value['research_ocr_binding'] = ResearchPDFOCRJobBinding.model_validate(binding).model_dump()
    return value


def test_pdf_record_is_passive_and_page_identity_cannot_be_reassigned(rig):
    e = rig; value = pdf_record(e); e.bundle.generations.save(value)
    assert e.bundle.generations.get(value['id']) == value
    job = reopen(e).get(value['id'])
    assert job.research_ocr_binding == value['research_ocr_binding']
    with pytest.raises(ValueError, match='EXECUTION_UNAVAILABLE'): reopen(e)._start_research_ocr_job(job)
    for change in [{'page': 1}, {'page': True}, {'source_kind': 'IMAGE'}, {'contract': 'RESEARCH_OCR_JOB_V1'}]:
        altered = deepcopy(value); altered['research_ocr_binding'].update(change)
        with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(altered)
    assert e.bundle.generations.get(value['id']) == value


def test_legacy_image_binding_does_not_gain_pdf_defaults(rig):
    value = record(rig)['research_ocr_binding']; before = deepcopy(value)
    assert ResearchOCRJobBinding.model_validate(value).model_dump() == before
    assert 'page' not in before
    with pytest.raises(ValueError): ResearchOCRJobBinding.model_validate({**value, 'page': 1})


def test_original_pdf_source_requires_explicit_page_and_preserves_original_bytes(rig):
    e = rig; service = ResearchLibraryService(e.raw_store, e.novels, e.chapters, historical_inspection=True)
    row = service.import_file(e.nid, e.scope, e.actor, payload(filename='synthetic.pdf',
        content_base64=base64.b64encode(PDF.read_bytes()).decode()), guard=lambda: None)
    args = dict(service=service, nid=e.nid, scope=e.scope, actor=e.actor, source_id=row['id'], source_version=1, guard=lambda: None)
    before = deepcopy(e.raw_store.read(e.nid, e.scope))
    with pytest.raises(ValueError, match='EXPLICIT_PAGE'): PreparedResearchOCRSource(**args)
    with pytest.raises(ValueError): PreparedResearchOCRSource(**args, page=True)
    prepared = PreparedResearchOCRSource(**args, page=2)
    assert prepared.read_current() == PDF.read_bytes()
    assert prepared.binding['page'] == 2 and prepared.binding['source_kind'] == 'PDF'
    assert prepared.binding['media_type'] == 'application/pdf'
    assert e.raw_store.read(e.nid, e.scope) == before
    service.transition_source(e.nid, e.scope, e.actor, row['id'], 1, 'revoke', guard=lambda: None)
    with pytest.raises((FileNotFoundError, StaleSourceError)): prepared.read_current()


def test_reused_project_cannot_inherit_pdf_record(rig):
    e = rig; value = pdf_record(e); e.bundle.generations.save(value)
    e.novels.delete(e.nid); e.create_project(nid=e.nid)
    with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(value)
    with pytest.raises(KeyError): e.bundle.generations.get(value['id'])
    fresh = pdf_record(e); e.bundle.generations.save(fresh)
    assert e.bundle.generations.get(fresh['id']) == fresh
