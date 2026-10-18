"""Real PDF through original broker/job/review owners; no separate engine."""
import base64
from copy import deepcopy
import pytest
from app.experimental.research_native_ocr import NativeResearchOCRCoordinator
from test_v2_independent_workspace import rig
from test_research_native_ocr_coordinator_additive import setup, preview, dispatch
from test_local_pdf_ocr_additive import pdf_provider, native, raster
from test_local_pdf_raster_additive import PDF
from test_r4_research_library import payload


def pdf_setup(e, monkeypatch, provider, pages=None):
    c = setup(e, monkeypatch)
    descriptor = next(d for d in c.runtime.provider_registry.descriptors() if d.provider_id == 'native-ocr')
    c.runtime.provider_registry.register(descriptor, provider, replace=True)
    c.row = c.research.import_file(e.nid, e.scope, e.actor, payload(filename='fixture.pdf',
        content_base64=base64.b64encode(PDF.read_bytes()).decode()), guard=lambda: None)
    c.analysis = c.research.create_analysis(e.nid, e.scope, e.actor,
        {'source_id':c.row['id'], 'source_version':1, 'operation':'OCR', 'pages':[2] if pages is None else pages}, guard=lambda:None)
    return c


def test_real_pdf_page_reopens_reviews_exports_without_replay(rig, monkeypatch, pdf_provider):
    from app.experimental.research_library import ResearchLibraryService
    from app.experimental.model_broker import ModelBrokerService
    from test_research_ocr_job_persistence_additive import reopen
    c = pdf_setup(rig, monkeypatch, pdf_provider)
    ready = preview(rig, c); body, job, result = dispatch(rig, c, ready)
    assert job.status == 'COMPLETED', job.error
    assert result['status'] == 'REVIEW_REQUIRED'
    block = result['result']['blocks'][0]
    assert 'PAGE 2' in block['text'] and block['page'] == block['citation']['page'] == 2
    assert block['citation']['source_digest'] == c.row['content_sha256']
    assert block['citation']['source_id'] == c.row['id']
    research = ResearchLibraryService(rig.raw_store, rig.novels, rig.chapters, historical_inspection=True)
    broker = ModelBrokerService(rig.raw_store, rig.novels, rig.chapters, runtime=c.runtime)
    manager = reopen(rig); controller = NativeResearchOCRCoordinator(research, broker, manager)
    reviewed = research.analysis_action(rig.nid, rig.scope, rig.actor, result['id'], 'review', result['version'], guard=lambda: None)
    assert reviewed['status'] == 'REVIEWED'
    assert b'PAGE 2' in controller.export_reviewed(rig.nid, rig.scope, rig.actor, reviewed['id'], reviewed['version'], reviewed['result_digest'])
    assert controller.dispatch(rig.nid, rig.scope, rig.actor, result['id'], body, guard=lambda: None)['status'] == 'REVIEWED'
    assert len(manager.jobs) == 1 and rig.chapters.list(rig.nid) == []


@pytest.mark.parametrize('pages', [[], [1,2]])
def test_pdf_preview_requires_one_explicit_page(rig, monkeypatch, pdf_provider, pages):
    c = pdf_setup(rig, monkeypatch, pdf_provider, pages)
    with pytest.raises(ValueError, match='ONE_EXPLICIT_PAGE'): preview(rig, c)
    assert not c.manager.jobs and not c.broker.ledger(rig.nid, rig.scope, rig.actor)


def test_tampered_raster_provenance_in_review_copy_is_rejected(rig, monkeypatch, pdf_provider):
    c = pdf_setup(rig, monkeypatch, pdf_provider); ready=preview(rig,c); _,job,result=dispatch(rig,c,ready)
    assert job.status == 'COMPLETED'
    with rig.raw_store.transaction(rig.nid,rig.scope) as state:
        state['collections']['research_analysis_jobs'][result['id']]['native_ocr_execution']['runtime_receipt']['rendered_image_sha256']='a'*64
    before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    with pytest.raises(ValueError,match='DURABLE_RESULT_MISMATCH'):
        c.research.analysis_action(rig.nid,rig.scope,rig.actor,result['id'],'review',result['version'],guard=lambda:None)
    assert rig.raw_store.read(rig.nid,rig.scope)==before


def test_mounted_pdf_routes_require_review_permission_and_export_original_page(rig, monkeypatch, pdf_provider):
    from test_research_native_ocr_routes_additive import mounted
    from test_research_ocr_job_execution_additive import wait
    from types import SimpleNamespace
    c=pdf_setup(rig,monkeypatch,pdf_provider); client,state,headers,path=mounted(rig,c)
    with client:
        response=client.post(path+'/native-preview',headers=headers,json={'expected_version':1,'provider_id':'native-ocr','model_id':'eng','language':'eng'})
        assert response.status_code==200,response.text
        ready=response.json()
        response=client.post(path+'/native-dispatch',headers=headers,json={'expected_version':ready['version'],
            'reviewed_preview_digest':ready['native_ocr_preview']['reviewed_preview_digest'],'idempotency_key':'pdf-http'})
        assert response.status_code==200,response.text
        job=c.manager.get(response.json()['native_ocr_execution']['generation_id']);wait(SimpleNamespace(job=job))
        result=client.get(path,headers=headers).json(); assert result['status']=='REVIEW_REQUIRED'
        assert result['result']['blocks'][0]['citation']['page']==2
        assert client.post(path+'/review',headers=headers,json={'expected_version':result['version']}).status_code==403
        state['review']=True
        reviewed=client.post(path+'/review',headers=headers,json={'expected_version':result['version']})
        assert reviewed.status_code==200,reviewed.text
        row=reviewed.json()
        exported=client.get(path+'/native-export',headers=headers,params={'expected_version':row['version'],'result_digest':row['result_digest']})
        assert exported.status_code==200 and b'PAGE 2' in exported.content
        assert exported.headers['cache-control']=='no-store'
        assert client.get(path,headers={'X-Session-Token':'invalid','X-Branch-ID':'current'}).status_code==403
