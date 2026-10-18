"""Exact accepted-revision candidates; no provider or inferred durable facts."""
from copy import deepcopy
import pytest
from app.canon_extraction import build_pending_canon
from app.source_privacy import content_digest
from app.services.pending_canon_review_service import CanonPreviewIn
from app.services.finding_review_service import FindingReviewConflict
from test_surface_pending_canon_review import canon_env, decision
from test_r3_mounted_contracts import mounted, prefix


def chapter(text='Canon fact: The door is sealed.\n设定事实： 月亮是蓝色的。'):
    return {'id': 'n:1', 'novel_id': 'n', 'number': 1, 'version': 3, 'content': text}


def test_exact_markers_bound_unicode_no_fabricated_fallback():
    source = chapter(); row = build_pending_canon('job', source)
    assert row['id'] == build_pending_canon('job', source)['id']
    assert row['source_version'] == 3 and row['source_digest'] == content_digest(source)
    assert row['chapter_id'] == source['id'] and row['review_owner'] == 'PENDING_CANON_REVIEW_V1'
    assert row['extraction']['method'] == 'EXPLICIT_SOURCE_MARKER' and row['extraction']['model_called'] is False
    assert [p['fact'] for p in row['proposals']] == ['The door is sealed.', '月亮是蓝色的。']
    for p in row['proposals']:
        ev = p['source_evidence'][0]
        assert source['content'][ev['start']:ev['end']] == ev['quote'] == p['fact']
        assert ev['chapter_version'] == 3 and ev['content_sha256'] == content_digest(source)
        assert p['privacy_level'] == 'LOCAL_ONLY'
    assert build_pending_canon('job', chapter('Ordinary prose with a secret.'))['proposals'] == []


def test_markers_dedup_bounds_and_scope():
    assert len(build_pending_canon('j', chapter('Canon fact: Same\nCanon fact: Same'))['proposals']) == 1
    for bad in ({'version': None}, {'branch_id': 'branch'}, {'scope': {'mode': 'collaboration'}}):
        with pytest.raises(ValueError): build_pending_canon('j', {**chapter(), **bad})
    for text in ('x' * 2_000_001, 'Canon fact: ' + 'x' * 4001, '\n'.join(f'Canon fact: {i}' for i in range(101))):
        row = build_pending_canon('j', chapter(text))
        assert row['proposals'] == [] and row['extraction']['status'] == 'LIMIT_EXCEEDED'
        assert not row['extraction']['complete'] and row['extraction']['limit_reason']


def install(e, text='Canon fact: The door is sealed.'):
    source = e.chapters.save(e.chapter['id'], {'content': text, 'version': e.chapter['version']})
    row = build_pending_canon('generated-source-test', source)
    e.canon.save_pending(row)
    return source, row


def test_generated_source_review_and_legacy_bypass_denied(canon_env):
    e = canon_env; source, row = install(e)
    preview = e.canon_review.preview(e.nid, row['id'], CanonPreviewIn())
    assert preview['lineage'] == 'SOURCE_VERSION_RECORDED' and not preview['stale_source']
    assert preview['generated_source']['version'] == source['version']
    assert preview['extraction']['method'] == 'EXPLICIT_SOURCE_MARKER'
    with pytest.raises(ValueError, match='VERSIONED_CANON_REVIEW_REQUIRED'): e.canon.approve(row['id'])
    approved = e.canon_review.review(e.nid, row['id'], 'author', decision(preview))
    assert approved['status'] == 'APPROVED' and len(e.canon.list(e.nid)) == 1


def test_generated_source_cannot_rebase_after_edit(canon_env):
    e = canon_env; source, row = install(e)
    original = e.canon_review.preview(e.nid, row['id'], CanonPreviewIn())
    e.chapters.save(source['id'], {'content': 'The door is open.', 'version': source['version']})
    with pytest.raises(FindingReviewConflict, match='CANON_PREVIEW_STALE'):
        e.canon_review.review(e.nid, row['id'], 'author', decision(original))
    current = e.canon_review.preview(e.nid, row['id'], CanonPreviewIn())
    assert current['stale_source'] and current['allowed_actions'] == ['reject']
    with pytest.raises(FindingReviewConflict, match='CANON_GENERATED_SOURCE_STALE'):
        e.canon_review.review(e.nid, row['id'], 'author', decision(current))
    assert e.canon_review.review(e.nid, row['id'], 'author', decision(current, 'reject'))['status'] == 'REJECTED'
    assert e.canon.list(e.nid) == []


@pytest.mark.parametrize('mutation', ['digest', 'version', 'fact', 'quote', 'offset'])
def test_invalid_bound_evidence_denies_approval(canon_env, monkeypatch, mutation):
    e = canon_env; source, row = install(e); corrupt = deepcopy(row)
    if mutation == 'digest': corrupt['source_digest'] = 'f' * 64
    elif mutation == 'version': corrupt['source_version'] = None
    elif mutation == 'fact': corrupt['proposals'][0]['fact'] = 'Unquoted fact'
    elif mutation == 'quote': corrupt['proposals'][0]['source_evidence'][0]['quote'] = 'Unquoted evidence'
    else: corrupt['proposals'][0]['source_evidence'][0]['start'] += 1
    monkeypatch.setattr(e.canon.repository, 'get_pending', lambda _: corrupt)
    preview = e.canon_review.preview(e.nid, row['id'], CanonPreviewIn())
    assert preview['allowed_actions'] == ['reject']


def test_empty_bound_candidate_is_not_approvable(canon_env):
    e = canon_env; _, row = install(e, 'Ordinary prose.')
    preview = e.canon_review.preview(e.nid, row['id'], CanonPreviewIn())
    assert preview['allowed_actions'] == ['reject']
    with pytest.raises(ValueError, match='CANON_NO_SUPPORTED_CANDIDATES'):
        e.canon_review.review(e.nid, row['id'], 'author', decision(preview))

@pytest.mark.parametrize('operation', ['continue', 'rewrite', 'expand'])
def test_accept_producer_binds_override_to_exact_saved_revision(canon_env, operation):
    from app.jobs import Job, JobManager
    from uuid import uuid4
    e = canon_env
    from app.services.generation_service import GenerationService
    from app.services.context_service import ContextService
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters, contexts=ContextService(e.bundle.novels, e.bundle.chapters),
                         canon=e.canon, memory_extractor=object(), snapshot_required=False)
    job = Job(id=str(uuid4()), operation=operation, novel_id=e.nid, chapter_id=e.chapter['id'],
              instruction='', profile='LOCAL_ONLY', status='COMPLETED', output='Canon fact: Unaccepted.',
              source=e.chapter['content'], base_chapter_version=e.chapter['version'])
    manager.jobs[job.id] = job; manager._persist(job)
    result = manager.accept(job.id, accepted_output='Canon fact: Accepted override.')
    row = result['pending_canon']; saved = e.chapters.get(result['chapter']['id'])
    assert row['chapter_id'] == saved['id'] and row['source_version'] == saved['version']
    assert row['source_digest'] == content_digest(saved)
    assert [p['fact'] for p in row['proposals']] == ['Accepted override.']
    assert e.canon.list(e.nid) == []
    if operation == 'continue': assert saved['id'] != e.chapter['id']


def test_creation_projection_resolves_initial_revision_after_concurrent_edit():
    from app.jobs import JobManager
    from app.document import markdown_to_document, document_to_markdown
    from types import SimpleNamespace
    raw = chapter('# Title\n\nCanon fact: Initial.')
    raw.pop('version')
    initial_doc = markdown_to_document(raw['content'])
    newer = {**raw, 'version': 2, 'content': 'Concurrent edit', 'document': markdown_to_document('Concurrent edit')}
    chapters = SimpleNamespace(get=lambda _: newer, history=lambda _: [{'version': 1, 'document': initial_doc}])
    accepted = JobManager._accepted_canon_source(chapters, raw)
    assert accepted['version'] == 1 and accepted['content'] == document_to_markdown(initial_doc)
    assert build_pending_canon('j', accepted)['proposals'][0]['fact'] == 'Initial.'
    chapters.history = lambda _: []
    with pytest.raises(ValueError, match='CANON_ACCEPTED_REVISION_UNAVAILABLE'):
        JobManager._accepted_canon_source(chapters, raw)


def test_bound_source_deleted_same_version_bytes_and_wrong_identity(canon_env, monkeypatch):
    e = canon_env; source, row = install(e)
    original_get = e.chapters.get
    monkeypatch.setattr(e.chapters, 'get', lambda cid: {**source, 'content': 'same version changed bytes'})
    changed = e.canon_review.preview(e.nid, row['id'], CanonPreviewIn())
    assert changed['stale_source'] and changed['allowed_actions'] == ['reject']
    monkeypatch.setattr(e.chapters, 'get', original_get)
    with pytest.raises(ValueError, match='CANON_SOURCE_ID_MISMATCH'):
        e.canon_review.preview(e.nid, row['id'], CanonPreviewIn(chapter_id='other:1'))
    e.chapters.archive(source['id'])
    unavailable = e.canon_review.preview(e.nid, row['id'], CanonPreviewIn())
    assert unavailable['stale_source'] and unavailable['source_state'] == 'SOURCE_UNAVAILABLE'
    assert unavailable['allowed_actions'] == ['reject']


def test_producer_failure_retains_uncertain_claim_without_replay(canon_env, monkeypatch):
    from app.jobs import Job, JobManager
    from app.services.generation_service import GenerationService
    from app.services.context_service import ContextService
    from uuid import uuid4
    e = canon_env
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=ContextService(e.bundle.novels, e.bundle.chapters), canon=e.canon,
                         memory_extractor=object(), snapshot_required=False)
    job = Job(id=str(uuid4()), operation='continue', novel_id=e.nid, chapter_id=e.chapter['id'],
              instruction='', profile='LOCAL_ONLY', status='COMPLETED', output='Canon fact: Accepted.',
              base_chapter_version=e.chapter['version'])
    manager.jobs[job.id] = job; manager._persist(job)
    def fail(*args): raise ValueError('CANON_ACCEPTED_REVISION_UNAVAILABLE')
    monkeypatch.setattr(manager, '_accepted_canon_source', fail)
    before = len(e.chapters.list(e.nid))
    with pytest.raises(ValueError, match='CANON_ACCEPTED_REVISION_UNAVAILABLE'): manager.accept(job.id)
    assert manager.persistence.get(job.id)['status'] == 'ACCEPTANCE_UNCERTAIN'
    assert len(e.chapters.list(e.nid)) == before + 1
    with pytest.raises(ValueError, match='interrupted acceptance requires manual review'): manager.accept(job.id)
    assert len(e.chapters.list(e.nid)) == before + 1 and e.canon.list(e.nid) == []


def test_save_return_snapshot_is_not_rebased_and_projection_mismatch_fails():
    from app.jobs import JobManager
    from app.document import markdown_to_document
    from types import SimpleNamespace
    def unexpected(*args): raise AssertionError('must not reread a save-returned revision')
    saved = chapter('Canon fact: Saved.')
    assert JobManager._accepted_canon_source(SimpleNamespace(get=unexpected), saved) == saved
    raw = {k: v for k, v in saved.items() if k != 'version'}
    altered = {**saved, 'version': 1, 'document': markdown_to_document('Unrelated v1')}
    with pytest.raises(ValueError, match='CANON_ACCEPTED_REVISION_MISMATCH'):
        JobManager._accepted_canon_source(SimpleNamespace(get=lambda _: altered), raw)


def test_historical_source_version_without_contract_retains_explicit_review(canon_env):
    e = canon_env
    legacy = {**e.pending_row, 'source_version': e.chapter['version']}
    e.canon.save_pending(legacy)
    preview = e.canon_review.preview(e.nid, legacy['id'], CanonPreviewIn(chapter_id=e.chapter['id']))
    assert preview['generated_source'] is None and preview['allowed_actions'] == ['approve', 'reject']
    assert e.canon_review.review(e.nid, legacy['id'], 'author', decision(preview))['status'] == 'APPROVED'


def test_extraction_budget_does_not_fail_accepted_text(canon_env):
    from app.jobs import Job, JobManager
    from app.services.generation_service import GenerationService
    from app.services.context_service import ContextService
    from uuid import uuid4
    e = canon_env
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=ContextService(e.bundle.novels, e.bundle.chapters), canon=e.canon,
                         memory_extractor=object(), snapshot_required=False)
    text = '\n'.join(f'Canon fact: {i}' for i in range(101))
    job = Job(id=str(uuid4()), operation='continue', novel_id=e.nid, chapter_id=e.chapter['id'],
              instruction='', profile='LOCAL_ONLY', status='COMPLETED', output=text,
              base_chapter_version=e.chapter['version'])
    manager.jobs[job.id] = job; manager._persist(job)
    result = manager.accept(job.id)
    assert manager.persistence.get(job.id)['status'] == 'ACCEPTED'
    assert text in e.chapters.get(result['chapter']['id'])['content']
    assert result['pending_canon']['extraction']['status'] == 'LIMIT_EXCEEDED'
    assert result['pending_canon']['proposals'] == [] and e.canon.list(e.nid) == []
