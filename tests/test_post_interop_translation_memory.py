"""Wave5 accepted-edition memory, locks and recovery use real File/PG owners."""
from dataclasses import replace
import json
import pytest
from fastapi import HTTPException
from app.experimental.common import StaleSourceError
from app.experimental.multilingual_editions import MultilingualEditionsService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r4_revision_intelligence import revision_env
from test_r5_multilingual_editions import editions_env, create, save, accept, review, rule


def memory(e, target):
    return e.service.translation_memory(e.nid, e.scope, 'author', target['id'], target['segments'][0]['id'], {'expected_version': target['version']})


def adopt(e, target, candidate, **kwargs):
    return e.service.adopt_memory(e.nid, e.scope, 'author', target['id'], target['segments'][0]['id'], {'expected_version': target['version'], **{k: candidate[k] for k in ('source_edition_id', 'source_segment_id', 'preview_digest')}}, **kwargs)


def test_memory_is_owner_projection_and_explicit_draft_reuse_restart(editions_env):
    e = editions_env; original = e.chapters.get(e.cid)
    source = accept(e, save(e, create(e), 'Verified translation'))
    target = create(e, title='Second edition', style_note='Different voice')
    before = e.store.read(e.nid, e.scope)
    candidate = memory(e, target)['items'][0]
    assert candidate['target_text'] == 'Verified translation' and not candidate['style_matches']
    assert e.store.read(e.nid, e.scope) == before
    e.service = MultilingualEditionsService(e.store, e.novels, e.chapters)
    result = adopt(e, target, candidate)
    assert result['segments'][0]['target_text'] == 'Verified translation'
    assert result['segments'][0]['status'] == 'DRAFT' and not result['checks']['can_export']
    assert result['segments'][0]['memory_provenance']['source_edition_id'] == source['id']
    assert e.chapters.get(e.cid) == original
    assert set(e.store.read(e.nid, e.scope)['collections']) == {e.service.COLLECTION}
    with pytest.raises(FileNotFoundError): e.service.translation_memory(e.nid, e.scope, 'other', target['id'], target['segments'][0]['id'], {'expected_version': result['version']})
    assert not memory(e, create(e, target_language='en'))['items']


def test_memory_rechecks_source_review_and_destination_cas(editions_env):
    e = editions_env; source = accept(e, save(e, create(e), 'Accepted')); target = create(e)
    candidate = memory(e, target)['items'][0]
    source = review(e, source, 'reopen')
    with pytest.raises(StaleSourceError): adopt(e, target, candidate)
    assert memory(e, target)['items'] == []
    source = accept(e, source); candidate = memory(e, target)['items'][0]
    target_new = save(e, target, 'Do not overwrite')
    with pytest.raises(CapabilityVersionConflict): adopt(e, target, candidate)
    assert e.service.edition(e.nid, e.scope, 'author', target['id'])['segments'][0]['target_text'] == 'Do not overwrite'


def test_locked_names_reject_alias_drift_revoke_requires_unlock(editions_env):
    e = editions_env; source = accept(e, save(e, create(e), 'Chia'))
    target = rule(e, create(e), target_aliases=['Chia'], category='place')
    rid = target['rules'][0]['id']
    target = e.service.review_rule(e.nid, e.scope, 'author', target['id'], rid, {'expected_version': target['version'], 'action': 'lock'})
    assert target['rules'][0]['locked']
    candidate = memory(e, target)['items'][0]
    assert not candidate['can_adopt'] and {'TERM_REQUIRED', 'LOCKED_TERM_VARIANT'} == {i['code'] for i in candidate['issues']}
    with pytest.raises(ValueError, match='locked terminology'): adopt(e, target, candidate)
    with pytest.raises(ValueError, match='unlock'): e.service.review_rule(e.nid, e.scope, 'author', target['id'], rid, {'expected_version': target['version'], 'action': 'revoke'})
    target = e.service.review_rule(e.nid, e.scope, 'author', target['id'], rid, {'expected_version': target['version'], 'action': 'unlock'})
    assert memory(e, target)['items'][0]['can_adopt']


def test_memory_final_revocation_rolls_back_and_source_drift_withholds(editions_env):
    e = editions_env; source = accept(e, save(e, create(e), 'SENSITIVE_TRANSLATION')); target = create(e)
    candidate = memory(e, target)['items'][0]; before = e.store.read(e.nid, e.scope); calls = []
    def revoked():
        calls.append(1)
        if len(calls) > 1: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): adopt(e, target, candidate, reauthorize=revoked)
    assert e.store.read(e.nid, e.scope) == before
    e.chapters.save(e.cid, {'version': e.chapters.get(e.cid)['version'], 'content': 'New source'})
    with pytest.raises(StaleSourceError): memory(e, target)
    assert 'SENSITIVE_TRANSLATION' not in json.dumps(e.service.editions(e.nid, e.scope, 'author'))


def test_history_restore_new_draft_is_version_fenced_and_old_records_supported(editions_env):
    e = editions_env; row = create(e); row = save(e, row, 'First translation'); first_version = row['version']; row = save(e, row, 'Second translation')
    sid = row['segments'][0]['id']
    history = e.service.segment_history(e.nid, e.scope, 'author', row['id'], sid, {'expected_version': row['version']})
    previous = next(h for h in history['items'] if h['version'] == first_version)
    restored = e.service.restore_segment(e.nid, e.scope, 'author', row['id'], sid, {'expected_version': row['version'], 'restore_version': first_version, 'preview_digest': previous['preview_digest']})
    assert restored['version'] == row['version'] + 1 and restored['segments'][0]['target_text'] == 'First translation'
    assert restored['segments'][0]['status'] == 'DRAFT'
    with pytest.raises(CapabilityVersionConflict): e.service.restore_segment(e.nid, e.scope, 'author', row['id'], sid, {'expected_version': row['version'], 'restore_version': first_version, 'preview_digest': previous['preview_digest']})


@pytest.mark.parametrize('preferred,aliases,target,mode,expected', [
    ('Anna', ['Ann'], 'Anna', 'substring', set()),
    ('Anna', ['Ann'], 'Ann', 'substring', {'TERM_REQUIRED', 'LOCKED_TERM_VARIANT'}),
    ('Anna', ['Ann'], 'Anna Ann', 'substring', {'LOCKED_TERM_VARIANT'}),
    ('Anna', ['Ann'], 'Ann Anna', 'substring', {'LOCKED_TERM_VARIANT'}),
    ('Anna', ['Ann'], 'Anna', 'word', set()),
    ('Anna', ['Ann'], 'Ann', 'word', {'TERM_REQUIRED', 'LOCKED_TERM_VARIANT'}),
    ('Anna', ['Ann'], 'Anna Ann', 'word', {'LOCKED_TERM_VARIANT'}),
    ('Anna', ['Ann'], 'Anna Anniversary', 'word', set()),
    ('Anna', ['Ann'], 'Anna Anniversary', 'substring', {'LOCKED_TERM_VARIANT'}),
    ('Annabelle', ['Ann', 'Anna', 'An'], 'Annabelle Annabelle', 'substring', set()),
    ('Annabelle', ['Ann', 'Anna', 'An'], 'Annabelle Ann', 'substring', {'LOCKED_TERM_VARIANT'}),
    ('阿青🙂', ['阿青', '青'], '阿青🙂，阿青🙂', 'substring', set()),
    ('阿青🙂', ['阿青', '青'], '阿青🙂，阿青', 'substring', {'LOCKED_TERM_VARIANT'}),
    ('e\u0301va', ['e\u0301'], 'e\u0301va', 'substring', set()),
    ('e\u0301va', ['e\u0301'], 'e\u0301va e\u0301', 'substring', {'LOCKED_TERM_VARIANT'}),
    ('e\u0301va', ['e\u0301'], 'éva', 'substring', {'TERM_REQUIRED'}),
    ('Anna', ['Anna', 'Ann'], 'Anna Anna', 'substring', set()),
])
def test_locked_alias_occurrences_only_outside_preferred_spans(preferred, aliases, target, mode, expected):
    from app.experimental.multilingual_editions import RuleIn, terminology_issues
    rule = RuleIn(expected_version=1, source_term='安娜', preferred=preferred, target_aliases=aliases, match=mode).model_dump(exclude={'expected_version'})
    rule.update(id='term', version=2, status='APPROVED', locked=True)
    issues = terminology_issues('安娜', target, [rule])
    assert {issue['code'] for issue in issues} == expected
    # Unlocked aliases retain their previous behavior; explicit forbidden terms
    # remain forbidden even if their spelling overlaps an approved name.
    if target == 'Anna' and mode == 'substring':
        rule['forbidden'] = ['Ann']
        assert {i['code'] for i in terminology_issues('安娜', target, [rule])} == {'TERM_FORBIDDEN'}


def test_locked_short_alias_correct_name_accepts_exports_and_reuses_memory(editions_env):
    e = editions_env; row = rule(e, create(e), preferred='Anna', target_aliases=['Ann'], forbidden=[], category='character')
    row = e.service.review_rule(e.nid, e.scope, 'author', row['id'], row['rules'][0]['id'], {'expected_version': row['version'], 'action': 'lock'})
    for index in range(len(row['segments'])): row = accept(e, save(e, row, 'Anna', index), index)
    assert row['checks']['can_export'] and row['segments'][0]['issues'] == []
    body = {'expected_version': row['version'], 'format': 'json'}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], body)
    exported = e.service.export(e.nid, e.scope, 'author', row['id'], {**body, 'preview_digest': preview['preview_digest']})
    assert json.loads(exported['content'])['segments'][0]['text'] == 'Anna'
    target = rule(e, create(e), preferred='Anna', target_aliases=['Ann'], forbidden=[], category='character')
    target = e.service.review_rule(e.nid, e.scope, 'author', target['id'], target['rules'][0]['id'], {'expected_version': target['version'], 'action': 'lock'})
    candidate = next(c for c in memory(e, target)['items'] if c['source_edition_id'] == row['id'])
    assert candidate['can_adopt'] and candidate['issues'] == []
    target = adopt(e, target, candidate)
    assert target['segments'][0]['target_text'] == 'Anna' and target['segments'][0]['status'] == 'DRAFT'
    mixed = accept(e, save(e, create(e), 'Anna Ann'))
    mixed_candidate = next(c for c in memory(e, target)['items'] if c['source_edition_id'] == mixed['id'])
    assert not mixed_candidate['can_adopt'] and {i['code'] for i in mixed_candidate['issues']} == {'LOCKED_TERM_VARIANT'}
    with pytest.raises(ValueError, match='locked terminology'): adopt(e, target, mixed_candidate)
    for text in ['Ann', 'Anna Ann']:
        target = review(e, save(e, target, text), 'submit')
        receipt = e.service.preview_segment(e.nid, e.scope, 'author', target['id'], target['segments'][0]['id'], {'expected_version': target['version']})
        assert not receipt['can_accept'] and 'LOCKED_TERM_VARIANT' in {i['code'] for i in receipt['issues']}
        with pytest.raises(ValueError): accept(e, target)
        check = e.service.export_preview(e.nid, e.scope, 'author', target['id'], {'expected_version': target['version'], 'format': 'txt'})
        assert not check['can_export']
