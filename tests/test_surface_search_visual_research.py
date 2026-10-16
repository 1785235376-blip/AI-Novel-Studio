"""Functional surface contracts against mounted original authorities, File/real PG.

All model outputs are explicit synthetic fixtures. PostgreSQL uses the same
mandatory disposable database fixture as the existing mounted regression suite.
"""
import base64
import copy
import io

import pytest

from app.experimental.embeddings import EmbeddingCapability, EmbeddingService, MockEmbeddingProvider
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_vision import SyntheticResearchVisionProvider
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import VisualMemoryIn
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_research_library import payload


@pytest.fixture
def surfaces(mounted, monkeypatch):
    e = mounted
    e.embedding = e.experimental.embedding_service
    e.research = e.experimental.research_library_service
    monkeypatch.setattr(e.embedding, 'research', e.research)
    monkeypatch.setattr(e.embedding, 'visual_memory', e.capabilities)
    monkeypatch.setattr(e.embedding, 'provider', None)
    monkeypatch.setattr(e.embedding, 'chapter_authority', None)
    monkeypatch.setattr(e.research, 'vision_provider', None)
    e.emb = e.base + '/embeddings'
    e.lib = e.base + '/research-library'
    return e


def png():
    from PIL import Image
    out = io.BytesIO(); Image.new('RGB', (2, 2), (80, 120, 140)).save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode()


def image_source(e, headers=None):
    return checked(e.client.post(e.lib + '/sources/import', headers=headers or {},
        json=payload(filename='synthetic.png', content_base64=png())), 201)


def analysis(e, source, operation='OCR', headers=None):
    return checked(e.client.post(e.lib + '/analysis/jobs', headers=headers or {}, json={
        'source_id': source['id'], 'source_version': source['version'], 'operation': operation, 'pages': [1]}), 201)


def reference(e, branch=None):
    asset = e.assets.create(e.nid, 'identity.png', png(), 'image/png', 'image', branch_id=branch)
    row = e.capabilities.create_visual_memory(e.nid, VisualMemoryIn(entity_type='CHARACTER', entity_id='alice',
        asset_id=asset['id'], appearance={'hair': {'color': 'brown'}, 'body': {'build': 'slender'},
        'accessories': ['silver pin']}, clothing={'coat': 'blue'}), branch_id=branch)
    row = e.capabilities.approve_visual_memory(e.nid, row['id'], row['version'], branch_id=branch)
    return asset, row


def check_request(asset, row, target='VIDEO'):
    return {'character_id': 'alice', 'references': [{'reference_id': row['id'], 'appearance_version': row['version']}],
            'candidate_asset_id': asset['id'], 'candidate_asset_version': asset['version'],
            'target_media': target, 'drift_threshold': 0.95}


class SemanticFixture(MockEmbeddingProvider):
    capability = EmbeddingCapability(provider_id='synthetic-semantic-fixture', model_id='fixture', model_revision='1',
        dimensions=2, input_types=['TEXT', 'IMAGE'], local=True, verification='MOCK_ONLY')

    def embed(self, values):
        return [[1.0, 0.0] if value.kind == 'IMAGE' or any(word in value.text.casefold() for word in ('healer', 'doctor'))
                else [0.0, 1.0] for value in values]


def test_hybrid_combines_lexical_and_vectors_all_four_indexes_with_citations(surfaces, monkeypatch):
    e = surfaces; monkeypatch.setattr(e.embedding, 'provider', SemanticFixture())
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Doctor Alice'})
    chapter = e.chapters.save(e.chapter['id'], {'version': e.chapter['version'], 'content': 'A healer entered the harbor.'})
    research = checked(e.client.post(e.lib + '/sources/import', json=payload('Ancient doctor traditions.')), 201)
    asset = e.assets.create(e.nid, 'healer.png', png(), 'image/png', 'image')
    entities = [{'entity_type': kind, 'entity_id': rid} for kind, rid in (
        ('CHARACTER', 'alice'), ('STORY', chapter['id']), ('RESEARCH', research['id']), ('ASSET', asset['id']))]
    index = checked(e.client.post(e.emb + '/indexes', json={'title': 'Hybrid fixture', 'entities': entities}), 201)
    ready = checked(e.client.post(e.emb + f"/indexes/{index['id']}/rebuild", json={'expected_version': 1}))
    query = {'index_id': index['id'], 'text': 'healer', 'expected_index_version': 1}
    result = checked(e.client.post(e.emb + '/hybrid-query', json=query))
    assert result['retrieval_mode'] == 'HYBRID_LEXICAL_VECTOR' and result['metric'] == 'WEIGHTED_RRF'
    assert result['verification'] == 'MOCK_ONLY' and result['model_quality'] == 'NOT_RUN'
    by_kind = {row['entity']['entity_type']: row for row in result['items']}
    assert set(by_kind) == {'CHARACTER', 'STORY', 'RESEARCH', 'ASSET'}
    assert by_kind['CHARACTER']['lexical_score'] == 0 and by_kind['CHARACTER']['semantic_score'] == 1
    assert by_kind['STORY']['lexical_score'] > 0 and by_kind['STORY']['lexical_rank'] is not None
    assert by_kind['RESEARCH']['citation']['paragraph_citation']['source_version'] == research['version']
    assert all(row['citation']['source_digest'] and row['citation']['navigation']['id'] for row in result['items'])
    assert e.client.post(e.emb + '/hybrid-query', json={**query, 'expected_index_version': 2}).status_code == 409
    assert e.client.post(e.emb + f"/indexes/{index['id']}/invalidate", json={'expected_version': 1}).status_code == 409
    reopened = EmbeddingService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters,
        provider=e.embedding.provider, assets=e.assets, research=e.research)
    assert reopened.query(e.nid, e.scope, {**query, 'mode': 'HYBRID'}, actor='local-author') == result
    e.chapters.save(chapter['id'], {'version': chapter['version'], 'content': 'New current manuscript.'})
    assert e.client.post(e.emb + '/hybrid-query', json=query).status_code == 409
    rebuilt = checked(e.client.post(e.emb + f"/indexes/{index['id']}/rebuild", json={'expected_version': ready['version']}))
    assert rebuilt['index_version'] == 2


def test_hybrid_unconfigured_branch_authority_and_flags_fail_closed(surfaces, monkeypatch):
    e = surfaces
    index = checked(e.client.post(e.emb + '/indexes', json={'title': 'No model', 'entities': [{'entity_type': 'STORY', 'entity_id': e.chapter['id']}]}), 201)
    result = e.client.post(e.emb + '/hybrid-query', json={'index_id': index['id'], 'text': 'Alice'})
    assert result.status_code == 422 and 'EMBEDDING_NOT_CONFIGURED' in result.text
    e = scoped(e, monkeypatch)
    result = e.client.post(e.emb + '/indexes', headers=e.headers, json={'title': 'Branch cannot borrow mainline',
        'entities': [{'entity_type': 'STORY', 'entity_id': e.chapter['id']}]})
    assert result.status_code == 422 and 'BRANCH_MANUSCRIPT_AUTHORITY_NOT_CONFIGURED' in result.text
    for endpoint in ['/hybrid-query', '/visual-identity/checks']:
        assert e.client.post(e.emb + endpoint, json={}).status_code in {401, 403}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    disabled = e.client.get(e.emb + '/visual-identity/profiles', headers=e.headers)
    assert disabled.status_code == 501 and disabled.json()['detail']['code'] == 'COLLABORATION_ROUTE_NOT_ENABLED'
    from dataclasses import replace
    monkeypatch.setattr(e.main, 'settings', replace(e.main.settings, enable_collaboration_runtime=False))
    assert e.client.get(e.emb + '/visual-identity/profiles').status_code == 404
    assert e.client.post(e.emb + '/hybrid-query', json={}).status_code == 404


@pytest.mark.parametrize('operation', ['OCR', 'IMAGE_UNDERSTANDING', 'CHART_UNDERSTANDING', 'TABLE_UNDERSTANDING'])
def test_research_analysis_review_citations_restart_and_source_replacement(surfaces, monkeypatch, operation):
    e = surfaces; source = image_source(e)
    original = e.chapters.get(e.chapter['id'])
    assert checked(e.client.get(e.lib + '/analysis/status'))['status'] == 'NOT_CONFIGURED'
    job = analysis(e, source, operation)
    assert job['status'] == 'NOT_CONFIGURED'
    assert e.client.post(e.lib + f"/analysis/jobs/{job['id']}/run", json={'expected_version': 1}).status_code == 422
    monkeypatch.setattr(e.research, 'vision_provider', SyntheticResearchVisionProvider())
    ready = checked(e.client.post(e.lib + f"/analysis/jobs/{job['id']}/run", json={'expected_version': 1}))
    assert ready['status'] == 'REVIEW_REQUIRED' and ready['model']['verification'] == 'MOCK_ONLY'
    assert ready['result']['blocks'][0]['citation']['source_digest'] == source['content_sha256']
    assert e.client.post(e.lib + f"/analysis/jobs/{job['id']}/review", json={'expected_version': 1}).status_code == 409
    reviewed = checked(e.client.post(e.lib + f"/analysis/jobs/{job['id']}/review", json={'expected_version': ready['version']}))
    reopened = ResearchLibraryService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters)
    assert reopened.analysis_job(e.nid, e.scope, 'local-author', job['id']) == reviewed
    assert e.chapters.get(e.chapter['id']) == original
    assert checked(e.client.get(e.base + '/world/canon'))['items'] == []
    replaced = checked(e.client.put(e.lib + f"/sources/{source['id']}/file", json=payload('replacement text', expected_version=source['version'])))
    current = checked(e.client.get(e.lib + f"/analysis/jobs/{job['id']}"))
    assert current['status'] == 'STALE' and current['result'] is None
    assert replaced['version'] > source['version']
    stored = e.store.read(e.nid, e.scope)['collections']['research_analysis_jobs'][job['id']]
    assert stored['status'] == 'INVALIDATED' and stored['execution_token'] is None and stored['result'] is None


def test_research_cancel_late_results_recover_and_restart_explicit(surfaces, monkeypatch):
    e = surfaces; source = image_source(e); job = analysis(e, source)
    class Cancelling(SyntheticResearchVisionProvider):
        def analyze(self, value, operation, dispatch_guard):
            result = super().analyze(value, operation, dispatch_guard)
            row = e.research.analysis_job(e.nid, e.scope, 'local-author', job['id'])
            e.research.analysis_action(e.nid, e.scope, 'local-author', job['id'], 'cancel', row['version'], guard=lambda: None)
            return result
    monkeypatch.setattr(e.research, 'vision_provider', Cancelling())
    # Provider output is discarded if cancellation wins the publish race.
    result = e.client.post(e.lib + f"/analysis/jobs/{job['id']}/run", json={'expected_version': 1})
    assert result.status_code in {200, 409}
    cancelled = checked(e.client.get(e.lib + f"/analysis/jobs/{job['id']}"))
    assert cancelled['status'] == 'CANCELLED' and cancelled['result'] is None
    recovered = checked(e.client.post(e.lib + f"/analysis/jobs/{job['id']}/recover", json={'expected_version': cancelled['version']}))
    monkeypatch.setattr(e.research, 'vision_provider', SyntheticResearchVisionProvider())
    from app.experimental.common import change_row
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections']['research_analysis_jobs'][job['id']]
        change_row(row, 'local-author', row['version'], lambda target: target.update(status='RUNNING', execution_token='abandoned'))
    restarted = ResearchLibraryService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters)
    orphan = restarted.analysis_job(e.nid, e.scope, 'local-author', job['id'])
    assert orphan['recovery_required'] and not orphan['automatic_resume']
    recovered = checked(e.client.post(e.lib + f"/analysis/jobs/{job['id']}/recover", json={'expected_version': orphan['version']}))
    assert recovered['status'] == 'DRAFT'
    ready = checked(e.client.post(e.lib + f"/analysis/jobs/{job['id']}/run", json={'expected_version': recovered['version']}))
    assert ready['status'] == 'REVIEW_REQUIRED'


@pytest.mark.parametrize('revoke', ['role', 'feature'])
def test_research_analysis_permission_revoke_during_model_call_is_atomic(surfaces, monkeypatch, revoke):
    e = scoped(surfaces, monkeypatch); source = image_source(e, e.headers); job = analysis(e, source, headers=e.headers)
    for headers in [e.viewer_headers, {}, {**e.headers, 'X-Branch-ID': e.other_branch}]:
        response = e.client.get(e.lib + f"/analysis/jobs/{job['id']}", headers=headers)
        assert response.status_code in {401, 403, 404} and source['title'] not in response.text
    class Revoking(SyntheticResearchVisionProvider):
        def analyze(self, *args):
            result = super().analyze(*args)
            if revoke == 'role': e.authorization.revoke_role(e.role, e.lead)
            else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
            return result
    monkeypatch.setattr(e.research, 'vision_provider', Revoking())
    response = e.client.post(e.lib + f"/analysis/jobs/{job['id']}/run", headers=e.headers, json={'expected_version': 1})
    assert response.status_code in {403, 404} and 'Synthetic contract result' not in response.text
    stored = e.store.read(e.nid, e.scope)['collections']['research_analysis_jobs'][job['id']]
    assert stored['result'] is None and stored['status'] == 'FAILED'


def test_visual_identity_approved_profile_comparison_selection_and_stale_lineage(surfaces, monkeypatch):
    e = surfaces; asset, profile = reference(e)
    profiles = checked(e.client.get(e.emb + '/visual-identity/profiles'))
    assert profiles['embedding_status'] == 'NOT_CONFIGURED'
    assert profiles['items'][0]['hair'] == {'color': 'brown'} and profiles['items'][0]['clothing'] == {'coat': 'blue'}
    job = checked(e.client.post(e.emb + '/visual-identity/checks', json=check_request(asset, profile)), 201)
    assert job['status'] == 'NOT_CONFIGURED'
    assert e.client.get(e.emb + f"/visual-identity/checks/{job['id']}/selection").status_code == 409
    monkeypatch.setattr(e.embedding, 'provider', MockEmbeddingProvider())
    ready = checked(e.client.post(e.emb + f"/visual-identity/checks/{job['id']}/run", json={'expected_version': 1}))
    assert ready['status'] == 'REVIEW_REQUIRED' and ready['result']['verification'] == 'MOCK_ONLY'
    assert not ready['result']['drift_warning'] and ready['result']['similarities'][0]['similarity'] == pytest.approx(1)
    assert e.client.post(e.emb + f"/visual-identity/checks/{job['id']}/review", json={'expected_version': 1}).status_code == 409
    reviewed = checked(e.client.post(e.emb + f"/visual-identity/checks/{job['id']}/review", json={'expected_version': ready['version']}))
    selected = checked(e.client.get(e.emb + f"/visual-identity/checks/{job['id']}/selection"))
    assert selected['target_media'] == 'VIDEO' and selected['source_lineage']['references'][0]['asset_id'] == asset['id']
    assert selected['model_quality'] == 'NOT_RUN' and not selected['production_dispatch']
    e.capabilities.update_visual_memory(e.nid, profile['id'], VisualMemoryIn(entity_type='CHARACTER', entity_id='alice',
        asset_id=asset['id'], appearance={'hair': 'red'}), profile['version'])
    assert e.client.get(e.emb + f"/visual-identity/checks/{job['id']}/selection").status_code in {404, 409}
    assert checked(e.client.get(e.emb + '/visual-identity/profiles'))['items'] == []


def test_visual_identity_branch_permission_and_late_revoke(surfaces, monkeypatch):
    e = scoped(surfaces, monkeypatch); asset, profile = reference(e, e.branch)
    monkeypatch.setattr(e.embedding, 'provider', MockEmbeddingProvider())
    job = checked(e.client.post(e.emb + '/visual-identity/checks', headers=e.headers, json=check_request(asset, profile, 'IMAGE')), 201)
    for headers in [{}, {**e.headers, 'X-Branch-ID': e.other_branch}]:
        assert e.client.get(e.emb + f"/visual-identity/checks/{job['id']}", headers=headers).status_code in {401, 403, 404}
    class Revoke(MockEmbeddingProvider):
        def embed(self, values):
            result = super().embed(values)
            e.authorization.revoke_role(e.role, e.lead)
            return result
    monkeypatch.setattr(e.embedding, 'provider', Revoke())
    response = e.client.post(e.emb + f"/visual-identity/checks/{job['id']}/run", headers=e.headers, json={'expected_version': 1})
    assert response.status_code == 403 and 'similarities' not in response.text
    stored = e.store.read(e.nid, e.scope)['collections']['visual_identity_checks'][job['id']]
    assert stored['status'] == 'FAILED' and stored['result'] is None


@pytest.mark.parametrize('domain', ['research', 'visual'])
def test_real_thread_cancel_during_adapter_execution_cannot_publish(surfaces, monkeypatch, domain):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    e = surfaces; entered, release = Event(), Event()
    if domain == 'research':
        row = analysis(e, image_source(e)); base = e.lib + '/analysis/jobs/' + row['id']
        class Slow(SyntheticResearchVisionProvider):
            def analyze(self, *args):
                result = super().analyze(*args)
                entered.set(); assert release.wait(10)
                return result
        monkeypatch.setattr(e.research, 'vision_provider', Slow())
    else:
        asset, profile = reference(e)
        row = checked(e.client.post(e.emb + '/visual-identity/checks', json=check_request(asset, profile)), 201)
        base = e.emb + '/visual-identity/checks/' + row['id']
        class Slow(MockEmbeddingProvider):
            def embed(self, values):
                result = super().embed(values)
                entered.set(); assert release.wait(10)
                return result
        monkeypatch.setattr(e.embedding, 'provider', Slow())
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(e.client.post, base + '/run', json={'expected_version': row['version']})
        try:
            assert entered.wait(10)
            running = checked(e.client.get(base)); assert running['status'] == 'RUNNING'
            cancelled = checked(e.client.post(base + '/cancel', json={'expected_version': running['version']}))
            assert cancelled['status'] == 'CANCELLED'
        finally: release.set()
        assert pending.result(timeout=20).status_code == 409
    current = checked(e.client.get(base))
    assert current['status'] == 'CANCELLED' and current['result'] is None
    recovered = checked(e.client.post(base + '/recover', json={'expected_version': current['version']}))
    assert recovered['status'] == 'DRAFT'


def test_scanned_pdf_vision_contract_and_real_runtime_admission_fail_closed(surfaces, monkeypatch):
    from pypdf import PdfWriter
    e = surfaces; writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    out = io.BytesIO(); writer.write(out)
    source = checked(e.client.post(e.lib + '/sources/import', json=payload(filename='scan.pdf', content_base64=base64.b64encode(out.getvalue()).decode())), 201)
    assert source['format'] == 'PDF' and source['extraction_status'] == 'OCR_NOT_CONFIGURED'
    row = analysis(e, source, 'SCAN_PDF_VISION')
    called = []
    class NotAdmitted(SyntheticResearchVisionProvider):
        capability = SyntheticResearchVisionProvider.capability.model_copy(update={'verification': 'CONTRACT_VERIFIED'})
        def analyze(self, *args):
            called.append(True); return super().analyze(*args)
    monkeypatch.setattr(e.research, 'vision_provider', NotAdmitted())
    response = e.client.post(e.lib + f"/analysis/jobs/{row['id']}/run", json={'expected_version': row['version']})
    assert response.status_code == 422 and 'ADAPTER_MODEL_ADMISSION_NOT_CONFIGURED' in response.text and not called
    monkeypatch.setattr(e.research, 'vision_provider', SyntheticResearchVisionProvider())
    result = checked(e.client.post(e.lib + f"/analysis/jobs/{row['id']}/run", json={'expected_version': row['version']}))
    assert result['result']['blocks'][0]['citation']['page'] == 1 and result['status'] == 'REVIEW_REQUIRED'
    assert result['durable_worker'] is False and result['runtime_admission'] == 'NOT_CONFIGURED'


def test_story_hybrid_consumes_real_branch_owner_and_feature_revocation(surfaces, monkeypatch):
    from app.services.branch_manuscript_service import BranchManuscriptService
    from app.experimental.flags import RUNTIME_FLAGS as FLAGS
    e = scoped(surfaces, monkeypatch)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))
    authority = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    branch = authority.for_scope(e.scope)
    chapter = branch.create(e.nid, {'title': 'Branch-only healer', 'content': 'This doctor lives only on the branch.'})
    monkeypatch.setattr(e.embedding, 'chapter_authority', authority.for_scope)
    monkeypatch.setattr(e.embedding, 'provider', SemanticFixture())
    catalog = checked(e.client.get(e.emb + '/sources', headers=e.headers))
    story = [row for row in catalog['items'] if row['entity']['entity_type'] == 'STORY']
    assert [row['entity']['entity_id'] for row in story] == [chapter['id']]
    index = checked(e.client.post(e.emb + '/indexes', headers=e.headers, json={'title': 'Branch story',
        'entities': [{'entity_type': 'STORY', 'entity_id': chapter['id']}]}), 201)
    checked(e.client.post(e.emb + f"/indexes/{index['id']}/rebuild", headers=e.headers, json={'expected_version': 1}))
    query = {'index_id': index['id'], 'text': 'doctor'}
    result = checked(e.client.post(e.emb + '/hybrid-query', headers=e.headers, json=query))
    assert result['items'][0]['citation']['branch_id'] == e.branch
    assert e.client.post(e.emb + '/hybrid-query', headers={**e.headers, 'X-Branch-ID': e.other_branch}, json=query).status_code in {403, 404}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in FLAGS if flag != 'branch_manuscript_v1'))
    response = e.client.post(e.emb + '/hybrid-query', headers=e.headers, json=query)
    assert response.status_code == 404 and 'branch_manuscript_v1' in response.text
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_hybrid_query_revoke_and_vector_provenance_tamper_do_not_return_results(surfaces, monkeypatch):
    e = scoped(surfaces, monkeypatch)
    source = image_source(e, e.headers)
    # Use current branch-private text Research evidence for a query authority test.
    source = checked(e.client.post(e.lib + '/sources/import', headers=e.headers, json=payload('Synthetic healer record.')), 201)
    provider = MockEmbeddingProvider(); monkeypatch.setattr(e.embedding, 'provider', provider)
    row = checked(e.client.post(e.emb + '/indexes', headers=e.headers, json={'title': 'Private query',
        'entities': [{'entity_type': 'RESEARCH', 'entity_id': source['id']}]}), 201)
    ready = checked(e.client.post(e.emb + f"/indexes/{row['id']}/rebuild", headers=e.headers, json={'expected_version': 1}))
    query = {'index_id': row['id'], 'text': 'healer'}
    with e.store.transaction(e.nid, e.scope) as state:
        record = state['collections']['embedding_vectors'][ready['record_ids'][0]]
        original = record['source_digest']; record['source_digest'] = '0' * 64
    response = e.client.post(e.emb + '/hybrid-query', headers=e.headers, json=query)
    assert response.status_code == 422 and 'EMBEDDING_VECTOR_SOURCE_INTEGRITY_FAILED' in response.text
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections']['embedding_vectors'][ready['record_ids'][0]]['source_digest'] = original
    original_embed = provider.embed
    def revoking(values):
        result = original_embed(values); e.authorization.revoke_role(e.role, e.lead); return result
    monkeypatch.setattr(provider, 'embed', revoking)
    response = e.client.post(e.emb + '/hybrid-query', headers=e.headers, json=query)
    assert response.status_code == 403 and 'Private query' not in response.text and 'Synthetic healer' not in response.text


def test_visual_drift_warning_and_receipt_restart_preserve_approved_authority(surfaces, monkeypatch):
    e = surfaces; asset, profile = reference(e)
    class Drift(SemanticFixture):
        def embed(self, values): return [[1.0, 0.0], *[[-1.0, 0.0] for _ in values[1:]]]
    provider = Drift(); monkeypatch.setattr(e.embedding, 'provider', provider)
    job = checked(e.client.post(e.emb + '/visual-identity/checks', json=check_request(asset, profile)), 201)
    ready = checked(e.client.post(e.emb + f"/visual-identity/checks/{job['id']}/run", json={'expected_version': 1}))
    assert ready['result']['drift_warning'] and ready['result']['similarities'][0]['similarity'] == -1
    assert e.capabilities._get('visual_memory', profile['id'], e.nid)['version'] == profile['version']
    reopened = EmbeddingService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters,
        provider=provider, assets=e.assets)
    reopened.visual_memory = e.capabilities
    assert reopened.visual_check(e.nid, e.scope, 'local-author', job['id']) == ready
    from app.experimental.common import StaleSourceError
    with pytest.raises(StaleSourceError): reopened.visual_selection(e.nid, e.scope, 'local-author', job['id'])


def test_functional_surface_contract_requires_every_state_and_original_owner():
    import json
    from pathlib import Path
    contract = json.loads((Path(__file__).parents[1] / 'contracts/functional-surfaces/search-visual-research.v1.json').read_text())
    assert contract['top_level_modules_added'] == []
    assert {'LOADING', 'EMPTY', 'ERROR', 'UNAUTHORIZED', 'NOT_CONFIGURED', 'DISABLED', 'CONFLICT', 'REVIEW', 'RECOVERY', 'PARTIAL'} <= set(contract['shared_states'])
    assert {item['id'] for item in contract['surfaces']} == {'hybrid-search', 'visual-identity', 'research-analysis'}
    assert all(item['owner'] and item['permissions'] and item['version'] and item['apis'] and item['navigation'] for item in contract['surfaces'])


def test_cross_project_receipts_and_source_ids_never_resolve(surfaces):
    from uuid import uuid4
    e = surfaces
    source = image_source(e); job = analysis(e, source)
    asset, profile = reference(e)
    visual = checked(e.client.post(e.emb + '/visual-identity/checks', json=check_request(asset, profile)), 201)
    other = e.novels.create({'id': 'other-surface-' + uuid4().hex, 'title': 'Synthetic isolated project'})['id']
    try:
        root = e.prefix + f'/novels/{other}/experimental'
        assert e.client.get(root + '/research-library/analysis/jobs/' + job['id']).status_code == 404
        assert e.client.get(root + '/embeddings/visual-identity/checks/' + visual['id']).status_code == 404
        response = e.client.post(root + '/research-library/analysis/jobs', json={
            'source_id': source['id'], 'source_version': source['version'], 'operation': 'OCR'})
        assert response.status_code == 404 and source['title'] not in response.text
        response = e.client.post(root + '/embeddings/indexes', json={'title': 'Cross-project rejected',
            'entities': [{'entity_type': 'STORY', 'entity_id': e.chapter['id']}]})
        assert response.status_code == 404
    finally: e.novels.delete(other)
