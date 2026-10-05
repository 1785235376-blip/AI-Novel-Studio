"""U05 uses the existing preparer/executor, and only A11 may apply its output."""
import copy
import json
import time
from types import SimpleNamespace as S

import pytest
from fastapi import HTTPException

from app.author_request import request_digest, request_payload
from app.experimental.author_context_api import AuthorPreviewInput, create_author_preparer
from app.experimental.flags import require_flag
from app.jobs import JobManager, require_generation_content
from app.model_runtime import TextModelNode
from app.router import Route
from app.services.context_service import ContextService
from app.services.generation_service import GenerationService
from app.services.canon_service import CanonService
from test_local_ai_discovery_egress import enabled
from test_r4_revision_intelligence import revision_env, selection


@pytest.fixture
def selection_author(revision_env, monkeypatch):
    import app.jobs as jobs_module
    import app.experimental.author_context_api as author_module
    e = revision_env
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'author_context_inspector_v2,revision_intelligence_v2,selection_assistant_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    _, registered, candidate, adapter, wire = enabled(e.store.root / 'selection-wire')
    wire.response_text = '甲改写🙂e\u0301。'
    e.wire = wire; e.permitted = True
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
        contexts=ContextService(e.bundle.novels, e.bundle.chapters, enable_lore_context=False,
            enable_narrative_context=False, enable_context_pack_v2=False),
        canon=CanonService(e.bundle.canon), snapshot_required=False)
    route = Route(candidate['provider_id'], candidate['id'])
    runtime = S(is_remote_text_provider=lambda _: False, router=lambda *_: S(routes={'writer': [route]}),
        packaged_author_route_ready=lambda _: True,
        prepare_text_route=lambda *_: TextModelNode(registered.provider_registry, registered.model_registry))
    monkeypatch.setattr(jobs_module, 'runtime', runtime); monkeypatch.setattr(author_module, 'runtime', runtime)
    monkeypatch.setattr(jobs_module, 'runtime_log', S(write=lambda **_: None))
    monkeypatch.setattr(jobs_module, 'deterministic_review', lambda *_: [])
    def auth(nid, token, branch, permission):
        if not e.permitted or nid != e.nid or token != 'session' or branch: raise HTTPException(403)
        return 'local-author', e.scope
    e.preparer = create_author_preparer(manager, auth, require_flag, lambda *_: (None, None), lambda body, *_: body.model_dump(),
        revision_selection_validator=e.service.selection)
    picked = selection(e, 0); receipt = e.service.selection(e.nid, e.scope, picked)
    e.body = AuthorPreviewInput(novel_id=e.nid, chapter_id=e.cid, chapter_version=e.chapter['version'],
        operation='rewrite', instruction='Rewrite exactly the selected text.', provider_id=candidate['provider_id'], model_id=candidate['id'],
        source=picked['text'], selected_text=picked['text'], revision_selection=picked, revision_selection_digest=receipt['selection_digest'])
    e.manager, e.route, e.receipt = manager, route, receipt
    return e


def prepared(e):
    result = e.preparer.prepare_preview(e.nid, e.body, 'session', None)
    body = e.body.model_copy(update={'preview_digest': request_digest(result.request, result.job, False)})
    return result, e.preparer.prepare_author(e.nid, body, 'session', None)


def run(e, job):
    e.manager.start_prepared(job)
    deadline = time.monotonic() + 5
    while job.status not in e.manager.terminal and time.monotonic() < deadline: time.sleep(.01)
    assert job.status in e.manager.terminal


def test_exact_selection_receipt_is_bound_to_actual_adapter_and_generic_accept_is_blocked(selection_author):
    e = selection_author; before = copy.deepcopy(e.chapters.get(e.cid))
    preview, job = prepared(e)
    assert not e.wire.calls and job.status == 'PREPARED'
    assert job.partial_revision_only is True and job.experimental_origin == 'selection_assistant'
    assert job.revision_selection_binding == {'selection': e.receipt['selection'], 'selection_digest': e.receipt['selection_digest']}
    assert set(job.required_experimental_features) == {'author_context_inspector_v2', 'revision_intelligence_v2', 'selection_assistant_v2'}
    run(e, job)
    assert job.status == 'COMPLETED', job.error
    assert e.wire.generations[0][2]['prompt'] == preview.request.prompt
    assert preview.request.prompt.endswith('SOURCE:\n' + e.body.source)
    assert job.source == e.body.source and job.operation == 'rewrite'
    stored = e.manager.persistence.get(job.id)
    assert stored['partial_revision_only'] and stored['revision_selection_binding'] == job.revision_selection_binding
    with pytest.raises(HTTPException) as exc: e.manager.accept(job.id, 'Wrong whole-chapter path', expected_version=before['version'])
    assert exc.value.status_code == 409 and exc.value.detail['code'] == 'REVISION_REVIEW_REQUIRED'
    assert e.chapters.get(e.cid) == before
    def reader(jid):
        value = e.manager.get(jid); require_generation_content(value); return value.public()
    proposal = e.service.create_proposal(e.nid, e.scope, 'local-author', {
        'selection': e.receipt['selection'], 'selection_digest': e.receipt['selection_digest'],
        'replacements': [{'anchor_id': e.receipt['blocks'][0]['anchor_id'], 'text': job.output}], 'job_id': job.id}, job_reader=reader)
    review = {'expected_version': proposal['version'], 'accept_ids': [proposal['blocks'][0]['anchor_id']]}
    receipt = e.service.preview(e.nid, e.scope, proposal['id'], review, job_reader=reader)
    applied = e.service.apply(e.nid, e.scope, 'local-author', proposal['id'], {**review, 'preview_digest': receipt['preview_digest']}, job_reader=reader)
    assert applied['chapter']['document']['content'][1:] == before['document']['content'][1:]
    assert applied['chapter']['document']['content'][0]['content'][0]['text'] == job.output


@pytest.mark.parametrize('field', ['digest', 'source', 'chapter_version', 'position'])
def test_caller_cannot_forge_selection_binding(selection_author, field):
    e = selection_author
    if field == 'digest': body = e.body.model_copy(update={'revision_selection_digest': '0' * 64})
    elif field == 'source': body = e.body.model_copy(update={'source': 'wrong text', 'selected_text': 'wrong text'})
    elif field == 'chapter_version': body = e.body.model_copy(update={'chapter_version': e.body.chapter_version + 1})
    else:
        picked = e.body.revision_selection.model_copy(update={'from_pos': e.body.revision_selection.from_pos + 1})
        body = e.body.model_copy(update={'revision_selection': picked})
    with pytest.raises(HTTPException) as exc: e.preparer.prepare_preview(e.nid, body, 'session', None)
    assert exc.value.status_code == 409 and not e.wire.calls


@pytest.mark.parametrize('change', ['source', 'binding', 'flags', 'permission'])
def test_selection_is_revalidated_at_final_local_adapter_send(selection_author, monkeypatch, change):
    e = selection_author; _, job = prepared(e)
    def mutate():
        e.wire.on_show = None
        if change == 'source': e.chapters.save(e.cid, {'version': e.chapter['version'], 'content': 'Changed current manuscript.'})
        elif change == 'binding': job.revision_selection_binding['selection_digest'] = 'b' * 64
        elif change == 'flags': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'author_context_inspector_v2')
        else: e.permitted = False
    e.wire.on_show = mutate
    run(e, job)
    assert job.status == 'FAILED' and not e.wire.generations


@pytest.mark.parametrize('case', ['one_field', 'character', 'wrong_operation', 'extra_marker'])
def test_strict_selection_input_cannot_downgrade_scope(selection_author, case):
    e = selection_author; raw = e.body.model_dump()
    if case == 'one_field': raw.pop('revision_selection_digest')
    elif case == 'character': raw['character_id'] = 'alice'
    elif case == 'wrong_operation': raw['operation'] = 'continue'
    else: raw['partial_revision_only'] = False
    with pytest.raises(ValueError): AuthorPreviewInput.model_validate(raw)
    assert not e.wire.calls


def test_binding_is_in_receipt_and_cannot_be_removed_for_generic_accept(selection_author):
    e = selection_author; preview, job = prepared(e)
    original = request_digest(preview.request, job, False)
    job.revision_selection_binding = {**job.revision_selection_binding, 'selection_digest': 'b' * 64}
    assert request_digest(preview.request, job, False) != original
    job.partial_revision_only = False
    job.status = 'COMPLETED'; e.manager.jobs[job.id] = job; e.manager._persist(job)
    with pytest.raises(HTTPException) as exc: e.manager.accept(job.id, 'Bypass attempt')
    assert exc.value.detail['code'] == 'REVISION_REVIEW_REQUIRED'
    job.revision_selection_binding = None
    e.manager._persist(job)
    with pytest.raises(HTTPException) as exc: e.manager.accept(job.id, 'Origin downgrade attempt')
    assert exc.value.detail['code'] == 'REVISION_REVIEW_REQUIRED'


def test_selection_source_whitespace_survives_preparer_and_exact_request(selection_author):
    from test_r4_revision_intelligence import document, paragraph
    e = selection_author; exact = '  甲🙂e\u0301。  '
    current = e.chapters.get(e.cid)
    current = e.chapters.save(e.cid, {'version': current['version'], 'document': document(paragraph(exact), paragraph('未选中。'))})
    picked = selection(e, 0); receipt = e.service.selection(e.nid, e.scope, picked)
    e.body = e.body.model_copy(update={'chapter_version': current['version'], 'source': exact, 'selected_text': exact,
        'revision_selection': e.body.revision_selection.model_validate(picked), 'revision_selection_digest': receipt['selection_digest']})
    preview, job = prepared(e)
    assert job.source == exact and job.revision_selection_binding['selection']['text'] == exact
    assert preview.request.prompt.endswith('SOURCE:\n' + exact)
