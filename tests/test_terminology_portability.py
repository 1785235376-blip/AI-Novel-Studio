"""Portable drafts over the original B05 File/opt-in actual PostgreSQL owner."""
from copy import deepcopy
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_r5_multilingual_editions import editions_env, revision_env, create, rule
from app.experimental.common import StaleSourceError
from app.experimental.multilingual_editions import MultilingualEditionsService
from app.experimental.multilingual_editions_api import create_multilingual_editions_router
from app.experimental.terminology_portability import (
    TerminologyPortability, GlossaryAdoptIn, MAX_GLOSSARY_BYTES, parse_glossary,
)
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture
def glossary_env(editions_env):
    from app.creative.project_store import CreativeProjectStore
    CreativeProjectStore(editions_env.store).incarnation(editions_env.nid)
    return editions_env


def term(source='甲🙂é', preferred='تشينغ', **changes):
    return {'source_term': source, 'source_aliases': [], 'preferred': preferred, 'target_aliases': [], 'forbidden': [],
            'category': 'term', 'strategy': 'meaning', 'match': 'substring', 'note': '', **changes}


def document(rules=None, **changes):
    return json.dumps({'schema': 'language-terminology-v1', 'source_language': 'zh-Hant', 'target_language': 'ar',
                       'rules': rules if rules is not None else [term()], **changes}, ensure_ascii=False)


def preview(e, row, text):
    return TerminologyPortability(e.service).preview(e.nid, e.scope, 'author', row['id'],
                                                     {'expected_version': row['version'], 'document': text})


def adopt(e, row, text, receipt, selected=(0,), **kw):
    return TerminologyPortability(e.service).adopt(e.nid, e.scope, 'author', row['id'],
        {'expected_version': row['version'], 'document': text, 'preview_digest': receipt['preview_digest'], 'selected_indices': list(selected)}, **kw)


def test_atomic_selected_draft_roundtrip_history_reopen_and_original_approval(glossary_env):
    e = glossary_env; row = create(e); original = deepcopy(e.chapters.get(e.cid)); before = deepcopy(e.store.read(e.nid, e.scope))
    text = document([term(), term('港口', '=HYPERLINK("https://invalid.example")'), term('Skip', '<b>literal</b>')])
    receipt = preview(e, row, text)
    assert e.store.read(e.nid, e.scope) == before
    saved = adopt(e, row, text, receipt, (0, 1))
    assert saved['version'] == row['version'] + 1 and len(saved['rules']) == 2
    assert all(r['status'] == 'DRAFT' and r['version'] == 1 and not r.get('locked') for r in saved['rules'])
    assert saved['term_revision'] == row['term_revision'] and saved['segments'] == row['segments']
    stored = e.service._owned(e.nid, e.scope, 'author', row['id'])
    assert len(stored['history']) == 1 and stored['history'][0]['rules'] == []
    reopened = MultilingualEditionsService(e.store, e.novels, e.chapters).edition(e.nid, e.scope, 'author', row['id'])
    assert reopened['rules'] == saved['rules']
    artifact = TerminologyPortability(e.service).export(e.nid, e.scope, 'author', row['id'], {'expected_version': saved['version']})
    portable = parse_glossary(artifact['content'])
    assert portable['rules'] == json.loads(text)['rules'][:2]
    assert not {'status', 'id', 'locked', 'created_by', 'history'} & set(portable['rules'][0])
    other = create(e, title='Second edition')
    copied = adopt(e, other, artifact['content'], preview(e, other, artifact['content']), (0, 1))
    assert copied['rules'][0]['id'] != saved['rules'][0]['id']
    approved = e.service.review_rule(e.nid, e.scope, 'author', saved['id'], saved['rules'][0]['id'], {'expected_version': saved['version'], 'action': 'approve'})
    assert approved['rules'][0]['status'] == 'APPROVED' and approved['term_revision'] == 1
    assert e.chapters.get(e.cid) == original


def test_duplicate_alias_conflicts_and_locked_rules_never_overwrite(glossary_env):
    e = glossary_env; row = rule(e, create(e), source_term='甲', source_aliases=['Alias'], preferred='Jia')
    row = e.service.review_rule(e.nid, e.scope, 'author', row['id'], row['rules'][0]['id'], {'expected_version': row['version'], 'action': 'lock'})
    from app.experimental.terminology_portability import portable_rule
    text = document([portable_rule(row['rules'][0]), term('Alias', 'Different'), term('New', 'N'), term('New', 'N'), term('Other', 'O', source_aliases=['FileAlias']), term('FileAlias', 'F')])
    receipt = preview(e, row, text)
    assert [entry['eligible'] for entry in receipt['entries']] == [False, False, True, False, False, False]
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(ValueError): adopt(e, row, text, receipt, (2, 1))
    assert e.store.read(e.nid, e.scope) == before
    saved = adopt(e, row, text, receipt, (2,))
    assert saved['rules'][:-1] == row['rules'] and saved['rules'][-1]['source_term'] == 'New'


def test_changed_payload_cas_actor_scope_source_and_final_revoke_fail_closed(glossary_env):
    e = glossary_env; row = create(e); text = document(); receipt = preview(e, row, text)
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(StaleSourceError): adopt(e, row, document([term('changed')]), receipt)
    for actor, scope in [('intruder', e.scope), ('author', {**e.scope, 'branch_id': 'wrong'})]:
        with pytest.raises(FileNotFoundError):
            TerminologyPortability(e.service).preview(e.nid, scope, actor, row['id'], {'expected_version': row['version'], 'document': text})
    calls = []
    def revoked():
        calls.append(1)
        if len(calls) == 3: raise HTTPException(403)
    with pytest.raises(HTTPException): adopt(e, row, text, receipt, reauthorize=revoked)
    assert e.store.read(e.nid, e.scope) == before
    saved = adopt(e, row, text, receipt)
    with pytest.raises(CapabilityVersionConflict): adopt(e, row, text, receipt)
    e.chapters.save(e.cid, {'version': e.chapters.get(e.cid)['version'], 'content': 'changed source'})
    with pytest.raises((ValueError, StaleSourceError)): preview(e, saved, text)
    with pytest.raises((ValueError, StaleSourceError)):
        TerminologyPortability(e.service).export(e.nid, e.scope, 'author', saved['id'], {'expected_version': saved['version']})


def test_capacity_is_atomic_and_language_pairs_are_exact(glossary_env):
    e = glossary_env; row = create(e)
    text = document([term(str(index), 'Target') for index in range(99)])
    row = adopt(e, row, text, preview(e, row, text), range(99))
    text = document([term('New A'), term('New B')]); receipt = preview(e, row, text)
    assert receipt['remaining_capacity'] == 1
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(ValueError): adopt(e, row, text, receipt, (0, 1))
    assert e.store.read(e.nid, e.scope) == before
    mismatched = json.loads(text); mismatched['target_language'] = 'AR'
    with pytest.raises(ValueError): preview(e, row, json.dumps(mismatched))


@pytest.mark.parametrize('change', [
    lambda v: v.update(schema='v2'), lambda v: v.update(status='APPROVED'),
    lambda v: v['rules'][0].update(locked=True), lambda v: v['rules'][0].update(id='from-other-owner'),
    lambda v: v['rules'][0].update(source_term=' padded '), lambda v: v['rules'][0].update(source_term='\ud800'),
    lambda v: v['rules'][0].update(source_term='x\x00'), lambda v: v['rules'][0].update(preferred='x' * 161),
    lambda v: v['rules'][0].update(source_aliases=['same', 'same']), lambda v: v['rules'][0].update(forbidden=['تشينغ']),
    lambda v: v['rules'][0].update(strategy='preserve'), lambda v: v['rules'][0].update(note='n' * 1001),
    lambda v: v.update(rules=[term(str(i)) for i in range(101)]),
])
def test_closed_schema_validation_does_not_echo_imported_content(change):
    value = json.loads(document()); change(value)
    with pytest.raises(ValueError, match='invalid glossary') as exc: parse_glossary(json.dumps(value))
    assert 'تشينغ' not in str(exc.value)


def test_duplicate_json_keys_bytes_and_literal_unicode():
    assert parse_glossary(document())['rules'][0]['source_term'] == '甲🙂é'
    for text in ['{"schema":"x","schema":"language-terminology-v1"}', document() + ' ' * MAX_GLOSSARY_BYTES, '{"rules": NaN}', '[' * 2000]:
        with pytest.raises(ValueError): parse_glossary(text)
    for selection in [[True], [1.5], ['0'], [-1], [100]]:
        with pytest.raises(ValueError): GlossaryAdoptIn(expected_version=1, document=document(), preview_digest='a' * 64, selected_indices=selection)


def test_routes_preserve_gate_no_store_and_bounded_validation(glossary_env):
    e = glossary_env; row = create(e); enabled = [True]; allowed = [True]
    def flag(name):
        if not enabled[0]: raise HTTPException(404)
    def authorize(nid, token, branch, permission):
        if not allowed[0]: raise HTTPException(403)
        return 'author', e.scope
    app = FastAPI(); app.include_router(create_multilingual_editions_router(e.service, authorize, flag))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/language-editions/{row["id"]}/glossary'
    request = {'expected_version': row['version'], 'document': document()}
    response = client.post(base + '/preview', json=request)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    receipt = response.json()
    result = client.post(base + '/adopt', json={**request, 'preview_digest': receipt['preview_digest'], 'selected_indices': [0]})
    assert result.status_code == 200 and result.json()['rules'][0]['status'] == 'DRAFT'
    exported = client.post(base + '/export', json={'expected_version': 2})
    assert exported.status_code == 200 and exported.headers['cache-control'] == 'no-store'
    before = e.store.read(e.nid, e.scope)
    assert client.post(base + '/preview', json={**request, 'document': 'x' * (MAX_GLOSSARY_BYTES + 1)}).status_code == 422
    for control in [allowed, enabled]:
        control[0] = False
        for suffix in ['/preview', '/adopt', '/export']:
            payload = {**request, 'preview_digest': receipt['preview_digest'], 'selected_indices': [0]} if suffix == '/adopt' else request if suffix == '/preview' else {'expected_version': 2}
            assert client.post(base + suffix, json=payload).status_code in {403, 404}
        control[0] = True
    assert e.store.read(e.nid, e.scope) == before


def test_same_version_replacement_incarnation_cannot_replay_preview(glossary_env):
    e = glossary_env; row = create(e); text = document(); receipt = preview(e, row, text)
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections'][e.service.COLLECTION][row['id']]['created_at'] = '2099-01-01T00:00:00+00:00'
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(StaleSourceError): adopt(e, row, text, receipt)
    assert e.store.read(e.nid, e.scope) == before


def test_revoked_rule_overlap_stays_ineligible(glossary_env):
    e = glossary_env; row = rule(e, create(e), source_term='Old', source_aliases=['Old alias'])
    row = e.service.review_rule(e.nid, e.scope, 'author', row['id'], row['rules'][0]['id'], {'expected_version': row['version'], 'action': 'revoke'})
    text = document([term('Old alias', 'New meaning')]); receipt = preview(e, row, text)
    assert not receipt['entries'][0]['eligible'] and receipt['entries'][0]['conflicts']
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(ValueError): adopt(e, row, text, receipt)
    assert e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize('drift', ['authority', 'source'])
def test_export_rechecks_final_authority_and_source(glossary_env, monkeypatch, drift):
    e = glossary_env; row = rule(e, create(e)); calls = []
    def reauthorize():
        if drift == 'authority':
            calls.append(1)
            if len(calls) == 2: raise HTTPException(403)
    if drift == 'source':
        original = e.service._current
        def current(*args):
            result = original(*args); calls.append(1)
            if len(calls) == 1:
                e.chapters.save(e.cid, {'version': e.chapters.get(e.cid)['version'], 'content': 'changed during export'})
            return result
        monkeypatch.setattr(e.service, '_current', current)
    before = e.store.read(e.nid, e.scope)
    with pytest.raises((HTTPException, ValueError)):
        TerminologyPortability(e.service).export(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']}, reauthorize=reauthorize)
    assert e.store.read(e.nid, e.scope) == before


def test_missing_original_file_identity_never_provisions(editions_env):
    e = editions_env
    if e.backend != 'file': pytest.skip('File marker-specific fail-closed check')
    row = create(e); marker = e.store.root / 'novels' / e.nid / 'creative_project_v2.json'
    assert not marker.exists()
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(FileNotFoundError): preview(e, row, document())
    with pytest.raises(FileNotFoundError):
        TerminologyPortability(e.service).export(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    assert not marker.exists() and e.store.read(e.nid, e.scope) == before


def test_original_project_delete_recreate_invalidates_identical_old_edition(glossary_env):
    from app.creative.project_store import CreativeProjectStore
    e = glossary_env; row = create(e); text = document(); receipt = preview(e, row, text)
    original_identity = CreativeProjectStore(e.store).incarnation(e.nid)
    e.novels.delete(e.nid)
    e.novels.create({'id': e.nid, 'title': 'Recreated original owner', 'genre': 'fantasy'})
    assert CreativeProjectStore(e.store).incarnation(e.nid) != original_identity
    # Isolate project identity from source drift: copied old edition/source
    # bindings cannot replay even if another source adapter reports identical.
    from unittest.mock import patch
    before = e.store.read(e.nid, e.scope)
    with patch.object(e.service, '_current', return_value={}):
        with pytest.raises(StaleSourceError): adopt(e, row, text, receipt)
    assert e.store.read(e.nid, e.scope) == before


def test_unknown_old_request_late_commit_cannot_duplicate_new_user_adoption(glossary_env):
    e = glossary_env; row = create(e); text = document(); old = preview(e, row, text)
    # A fresh GET may still see the pre-commit version. A new explicit preview
    # does not cancel the original outstanding request or prove its failure.
    fresh = e.service.edition(e.nid, e.scope, 'author', row['id'])
    second = preview(e, fresh, text)
    saved = adopt(e, row, text, old)
    with pytest.raises(CapabilityVersionConflict): adopt(e, fresh, text, second)
    assert len(e.service.edition(e.nid, e.scope, 'author', row['id'])['rules']) == 1
    assert not preview(e, saved, text)['entries'][0]['eligible']


def test_feff_literal_roundtrip_and_nel_no_silent_trim():
    value = parse_glossary(document([term('\ufeffExact', '\ufeffTarget')]))
    assert value['rules'][0]['source_term'] == '\ufeffExact'
    with pytest.raises(ValueError): parse_glossary(document([term('\u0085Trimmed')]))


@pytest.mark.parametrize('where', ['root', 'rule', 'escaped_rule'])
def test_otherwise_valid_duplicate_keys_rejected_before_any_write(glossary_env, where):
    e = glossary_env; row = create(e); text = document()
    if where == 'root':
        text = text.replace('{', '{"schema":"language-terminology-v1",', 1)
    else:
        spelling = 'source_term' if where == 'rule' else r'source_\u0074erm'
        text = text.replace('"source_term":', '"' + spelling + '": "discarded", "source_term":', 1)
    # A normal last-key-wins parser produces a fully valid original document;
    # only duplicate-key detection rejects these otherwise legal payloads.
    assert json.loads(text) == json.loads(document())
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(ValueError, match='invalid glossary'): preview(e, row, text)
    with pytest.raises(ValueError, match='invalid glossary'):
        adopt(e, row, text, {'preview_digest': 'a' * 64})
    assert e.store.read(e.nid, e.scope) == before
