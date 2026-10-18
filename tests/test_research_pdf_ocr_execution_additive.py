"""Original File/PG job execution with durable PDF completion provenance."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from app.experimental.research_vision import PreparedResearchOCRSource
from app.repositories.generation_repository import GenerationProjectIdentityError
from test_v2_independent_workspace import rig
from test_research_ocr_job_execution_additive import setup, wait
from test_research_ocr_job_persistence_additive import reopen
from test_local_pdf_ocr_additive import pdf_provider, native, raster
from test_local_pdf_raster_additive import PDF
from test_r4_research_library import payload


def pdf_setup(e, monkeypatch, provider):
    # Existing setup supplies exact original runtime/JobManager and enabled flags;
    # its IMAGE job is only PREPARED and never started or persisted.
    c = setup(e, monkeypatch)
    c.node.providers.register(next(d for d in c.node.providers.descriptors() if d.provider_id == 'vision'),
        c.provider, replace=True)
    from test_local_tesseract_ocr_additive import install
    install(SimpleNamespace(providers=c.node.providers, models=c.node.models), provider)
    row = c.service.import_file(e.nid, e.scope, e.actor, payload(filename='source.pdf',
        content_base64=base64.b64encode(PDF.read_bytes()).decode()), guard=lambda: None)
    source = PreparedResearchOCRSource(c.service, e.nid, e.scope, e.actor, row['id'], 1, lambda: None, page=2)
    binding = {k:v for k,v in source.binding.items() if k not in {'contract', 'access'}}
    binding.update(contract='RESEARCH_PDF_OCR_JOB_V1', language='eng',
        route_digest=c.node.binding('native-ocr', 'eng')['route_digest'], reviewed_preview_digest='c'*64)
    calls=[]
    job = c.manager._prepare_research_ocr_job(source=source, node=c.node, binding=binding,
        provider_id='native-ocr', model_id='eng', deadline=(datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat(),
        before_dispatch=lambda: calls.append('dispatch'), on_terminal=lambda: calls.append('terminal'))
    return SimpleNamespace(job=job, manager=c.manager, calls=calls, service=c.service, row=row)


def test_actual_pdf_job_preserves_immutable_evidence_after_passive_reopen(rig, monkeypatch, pdf_provider):
    c = pdf_setup(rig, monkeypatch, pdf_provider); c.manager._start_research_ocr_job(c.job); wait(c)
    assert c.job.status == 'COMPLETED', c.job.error
    assert c.calls == ['dispatch', 'terminal'] and 'PAGE 2' in c.job.output
    receipt = c.job.research_ocr_execution_authority.result().receipt
    saved = c.manager.persistence.get(c.job.id)
    assert saved['research_ocr_output_evidence'] == receipt and receipt['source_page'] == 2
    restored = reopen(rig).get(c.job.id)
    assert restored.research_ocr_output_evidence == receipt and restored.research_ocr_execution_authority is None
    with pytest.raises(ValueError, match='EXECUTION_UNAVAILABLE'): reopen(rig)._start_research_ocr_job(restored)
    for patch in [{'rendered_image_sha256': 'd'*64}, {'source_page': 1}, {'extra': 'not allowed'}]:
        altered = deepcopy(saved); altered['research_ocr_output_evidence'].update(patch)
        with pytest.raises(GenerationProjectIdentityError): c.manager.persistence.save(altered)
    removed = deepcopy(saved); removed.pop('research_ocr_output_evidence')
    with pytest.raises(GenerationProjectIdentityError): c.manager.persistence.save(removed)
    assert c.manager.persistence.get(c.job.id) == saved and rig.chapters.list(rig.nid) == []


def test_pdf_source_revoke_before_start_never_publishes(rig, monkeypatch, pdf_provider):
    c = pdf_setup(rig, monkeypatch, pdf_provider)
    c.service.transition_source(rig.nid, rig.scope, rig.actor, c.row['id'], 1, 'revoke', guard=lambda: None)
    with pytest.raises((FileNotFoundError, ValueError)): c.manager._start_research_ocr_job(c.job)
    assert not c.job.output and c.job.research_ocr_output_evidence is None and c.calls == []
