"""A02/A03 deterministic closures, shared authority and File/actual-PG receipts."""
from copy import deepcopy
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.style_analysis import StyleAnalysisService, metrics
from app.experimental.style_analysis_api import create_style_analysis_router
from app.experimental.narrative_judge import NarrativeJudgeService, JudgeAdapterOutput
from app.experimental.narrative_judge_api import create_narrative_judge_router
from app.experimental.world import WorldService
from app.experimental.store import ExperimentalStore
from app.services.creation_workbench_service import CreationWorkbenchService
from app.services.v1_capability_service import V1CapabilityService, CapabilityVersionConflict
from app.source_privacy import content_digest, review_source_privacy
from test_r3_planning import planning_env


@pytest.fixture
def env(planning_env):
    e = planning_env
    e.creation = CreationWorkbenchService(V1CapabilityService(e.root, e.novels, e.chapter_service, None), e.chapter_service, e.novels)
    e.style = StyleAnalysisService(e.store, e.novels, e.chapter_service, e.creation)
    e.world = WorldService(e.store, e.novels, e.chapter_service)
    e.judge = NarrativeJudgeService(e.store, e.novels, e.chapter_service, e.creation, e.world, e.service)
    return e


def profile(e, **kwargs):
    return e.style.save_profile(e.nid, e.scope, 'author', {"title": "Spare prose", "instructions": "Use concrete verbs.", "rules": ["Allow intentional repetition."], "chapter_ids": [e.order[0]], **kwargs})


def analysis(e, p, **kwargs):
    return e.style.analyze(e.nid, e.scope, 'author', {"style_id": p['id'], "expected_style_version": p['version'], "language": "en", "samples": [{"chapter_id": e.order[0], "expected_version": e.chapters[e.order[0]]['version']}], **kwargs})


def run(e, **kwargs):
    cids = kwargs.pop('chapter_ids', e.order[:2])
    return e.judge.create_run(e.nid, e.scope, 'author', {"chapter_ids": cids, "expected_versions": {cid: e.chapters[cid]['version'] for cid in cids}, **kwargs})


def duplicate(e):
    e.chapters[e.order[0]]['content'] = 'The lantern stood beside the door.\n\nThe lantern stood beside the door.'
    return run(e, chapter_ids=e.order[:1])


def test_reproducible_raw_language_metrics_no_quality_scores():
    en = metrics('I go. "I go!"\nWe wait.', 'en')
    assert en['unit_count'] == 6
    assert en['sentence_count'] == 3 and en['paragraph_count'] == 2
    assert en['dialogue_characters'] == 5
    assert en['perspective_lexical_cues']['i'] == 2
    assert en['repeated_units'] == [{'unit': 'go', 'count': 2}, {'unit': 'i', 'count': 2}]
    zh = metrics('我走了。「你等我！」\n我回头。', 'zh')
    assert zh['unit'] == 'HAN_CHARACTER_NOT_WORD' and zh['unit_count'] == 9
    assert zh['dialogue_characters'] == 4
    assert zh == metrics('我走了。「你等我！」\n我回头。', 'zh')
    assert zh['sample_sufficiency'] == 'SHORT_SAMPLE'
    assert not any(key in en for key in ('score', 'probability', 'match_percent'))


def test_style_uses_existing_profile_and_real_restart(env):
    e = env; before = deepcopy(e.chapters); p = profile(e)
    a = analysis(e, p, comparison={"chapter_id": e.order[1], "expected_version": 1, "language": "zh"})
    assert e.creation.get_record(e.nid, e.scope, p['id'])['kind'] == 'STYLE'
    assert a['comparison']['comparable'] is False and not a['comparison']['difference_counts']
    assert a['privacy_level'] == 'LOCAL_ONLY' and not a['model_called']
    restarted = StyleAnalysisService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, e.creation)
    assert restarted.analyses(e.nid, e.scope)[0]['metrics'] == a['metrics']
    assert e.chapters == before


def test_style_edit_remove_sample_invalidates_and_hides_all_derived_metrics(env):
    e = env; p = profile(e); a = analysis(e, p)
    edited = e.style.save_profile(e.nid, e.scope, 'author', {"title": "Updated", "instructions": "Use verbs", "chapter_ids": [], "expected_version": p['version']}, p['id'])
    assert edited['id'] == p['id'] and edited['status'] == 'DRAFT'
    old = e.style.analyses(e.nid, e.scope)[0]
    assert old['stale'] and 'metrics' not in old and 'samples' not in old
    assert e.creation.get_record(e.nid, e.scope, p['id'])['chapter_ids'] == []
    with pytest.raises(ValueError, match='samples'): analysis(e, edited)
    with pytest.raises(CapabilityVersionConflict): analysis(e, p)


@pytest.mark.parametrize('change', ['unversioned_text', 'privacy', 'branch', 'archive', 'delete'])
def test_style_current_source_fences(env, change):
    e = env; p = profile(e); analysis(e, p); cid = e.order[0]
    if change == 'unversioned_text': e.chapters[cid]['content'] += ' CHANGED'
    elif change == 'privacy':
        c = e.chapters[cid]; review_source_privacy(c, None, 'author', 'CLOUD_ALLOWED', c['version'], content_digest(c), e.root)
    elif change == 'branch': e.chapters[cid]['branch_id'] = 'other'
    elif change == 'archive': e.order.remove(cid)
    else: del e.chapters[cid]; e.order.remove(cid)
    result = e.style.analyses(e.nid, e.scope)[0]
    assert result['stale'] and 'metrics' not in result and 'comparison' not in result


def test_style_rules_approval_and_context_preview_reuse_generation_authority(env):
    e = env; p = profile(e, character_ids=['alice'])
    with pytest.raises(ValueError, match='approved'): e.style.preview(e.nid, e.scope, p['id'], {"expected_version": 1, "operation": "continue", "character_id": "alice"})
    p = e.style.transition(e.nid, e.scope, 'reviewer', p['id'], 'approve', 1)
    with pytest.raises(ValueError, match='declared characters'): e.style.preview(e.nid, e.scope, p['id'], {"expected_version": 2, "operation": "continue", "character_id": "bob"})
    preview = e.style.preview(e.nid, e.scope, p['id'], {"expected_version": 2, "operation": "continue", "character_id": "alice"})
    assert preview['instructions'] == e.creation.generation_inputs(e.nid, e.scope, p['id'])['style']
    assert preview['context_injection'] == 'INSTRUCTIONS_ONLY' and preview['rules_usage'] == 'REFERENCE_ONLY'
    assert not preview['model_called'] and len(preview['preview_digest']) == 64


def test_style_bounded_ranges_and_no_branch_source_leak(env):
    e = env; p = profile(e)
    with pytest.raises(ValueError, match='sample range'): analysis(e, p, samples=[{"chapter_id": e.order[0], "expected_version": 1, "end": 9999}])
    with pytest.raises(ValueError, match='samples'): analysis(e, p, samples=[{"chapter_id": e.order[1], "expected_version": 1}])
    e.chapters[e.order[0]]['content'] = 'a' * 100_001
    with pytest.raises(ValueError, match='100000'): analysis(e, p)
    assert not e.style.analyses(e.nid, e.scope)


def test_judge_duplicate_closed_loop_original_review_storage_and_restart(env):
    e = env; result = duplicate(e); before = deepcopy(e.chapters)
    assert len(result['findings']) == 1 and result['verification'] == 'DETERMINISTIC_RULES'
    f = result['findings'][0]
    assert len(f['evidence']) == 2 and f['origin'] == 'DETERMINISTIC'
    assert f['evidence'][0]['start'] == 0 and f['evidence'][1]['paragraph'] == 2
    reviewed = e.judge.review(e.nid, e.scope, 'reviewer', f['id'], {"expected_version": 1, "action": "ignore", "reason": "Intentional echo"})
    assert reviewed['decision'] == 'IGNORED' and reviewed['status'] == 'RESOLVED'
    assert e.creation._rows('review_threads')[0]['narrative_judge']['decision'] == 'IGNORED'
    assert run(e, chapter_ids=e.order[:1])['id'] == result['id']
    assert len(e.creation._rows('review_threads')) == 1
    with pytest.raises(CapabilityVersionConflict): e.judge.review(e.nid, e.scope, 'reviewer', f['id'], {"expected_version": 1, "action": "review", "reason": "late"})
    reopened = e.judge.review(e.nid, e.scope, 'reviewer', f['id'], {"expected_version": 2, "action": "reopen", "reason": "Reconsider"})
    assert reopened['decision'] == 'PENDING' and reopened['version'] == 3
    restarted = NarrativeJudgeService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, e.creation, e.world)
    assert restarted.run(e.nid, e.scope, result['id'])['findings'][0]['version'] == 3
    assert e.chapters == before


def test_judge_stale_invalidates_findings_counts_and_inbox(env):
    e = env; result = duplicate(e); f = result['findings'][0]
    e.chapters[e.order[0]]['content'] = 'Removed private sample'
    stale = e.judge.run(e.nid, e.scope, result['id'])
    assert stale['stale'] and stale['findings'] == []
    assert 'The lantern' not in json.dumps(stale) and 'finding_ids' not in stale and 'findings_truncated' not in stale
    assert e.judge.list_review_items(e.nid, e.scope) == []
    with pytest.raises(StaleSourceError): e.judge.review(e.nid, e.scope, 'reviewer', f['id'], {"expected_version": 1, "action": "review", "reason": "old"})


def test_judge_world_conflict_requires_all_real_quotes_and_selected_records(env):
    e = env
    e.chapters[e.order[0]]['content'] = 'Alice remained calm.'
    e.chapters[e.order[1]]['content'] = 'Alice became worried, though she had been furious.'
    def psych(ch, state, prior='', stage=0):
        row = e.world.create_record(e.nid, e.scope, 'author', {"kind": "PSYCHOLOGY", "title": "State", "chapter_id": e.order[ch], "data": {"character_id": "alice", "state": state, "from_state": prior, "arc_stage": stage}})
        return e.world.review(e.nid, e.scope, 'reviewer', row['id'], 'approve', 1)
    psych(0, 'calm'); current = psych(1, 'worried', 'furious', 1)
    result = run(e)
    assert any(f['code'] == 'CHARACTER_STATE_TIME_REVERSAL' for f in result['findings'])
    assert all(f['evidence'] for f in result['findings'])
    e.world.review(e.nid, e.scope, 'reviewer', current['id'], 'archive', current['version'])
    assert e.judge.run(e.nid, e.scope, result['id'])['stale']
    secret = 'UNSELECTED_SECRET_TITLE_AND_TEXT'
    e.chapters[e.order[2]]['content'] = secret
    hidden = psych(2, secret, 'wrong')
    other = run(e, chapter_ids=e.order[:1])
    assert secret not in json.dumps(other) and hidden['id'] not in json.dumps(other)
    assert other['findings'] == []


def test_model_opinions_are_distinct_bad_quote_rejected_before_any_write(env):
    e = env; c = e.chapters[e.order[0]]
    class Adapter:
        adapter_id = 'local-test'; model_identity = 'test-only-model'; execution_mode = 'LOCAL_MODEL'
        def judge(self, request):
            assert request['privacy_level'] == 'LOCAL_ONLY'
            return {"opinions": [{"category": "PACING", "explanation": "A subjective opinion", "suggestion": "Consider alternatives", "boundary": "Not a calibrated evaluation", "evidence": [{"chapter_id": c['id'], "chapter_version": 1, "paragraph": 1, "start": 0, "end": len(c['content']), "quote": c['content']}]}]}
    adapter = Adapter(); e.judge.adapters[adapter.adapter_id] = adapter
    result = run(e, chapter_ids=e.order[:1], adapter_id=adapter.adapter_id)
    f = result['findings'][0]
    assert f['origin'] == 'MODEL_ASSESSMENT' and f['independence'] == 'UNVERIFIED' and f['quality_verification'] == 'NOT_VERIFIED'
    before = len(e.creation._rows('review_threads'))
    original = adapter.judge
    def bad(request):
        output = original(request); output['opinions'][0]['evidence'][0]['quote'] = 'Invented quote'; return output
    adapter.judge = bad; adapter.model_identity = 'changed-test-model'
    with pytest.raises(ValueError, match='quote'): run(e, chapter_ids=e.order[:1], adapter_id=adapter.adapter_id)
    assert len(e.creation._rows('review_threads')) == before
    with pytest.raises(ValueError, match='NOT_CONFIGURED'): run(e, adapter_id='cloud')


def test_reauthorize_after_adapter_prevents_write_and_new_actor_reuse(env):
    e = env; cid = e.order[0]
    class Adapter:
        adapter_id = 'local'; model_identity = 'fixture'; execution_mode = 'LOCAL_MODEL'
        def judge(self, request):
            e.chapters[cid]['content'] += ' changed during request'
            return JudgeAdapterOutput(opinions=[])
    e.judge.adapters['local'] = Adapter()
    with pytest.raises(StaleSourceError): run(e, chapter_ids=[cid], adapter_id='local')
    assert not e.creation._rows('review_threads') and not e.judge.runs(e.nid, e.scope)
    def denied(): raise HTTPException(403, 'revoked')
    p = profile(e)
    with pytest.raises(HTTPException): e.style.analyze(e.nid, e.scope, 'author', {"style_id": p['id'], "expected_style_version": 1, "language": "en", "samples": [{"chapter_id": cid, "expected_version": 1}]}, denied)
    assert not e.style.analyses(e.nid, e.scope)


def test_api_current_actor_permission_branch_flag_fences_and_no_store(env):
    e = env; active = {'enabled': True, 'actor': 'author', 'calls': 0, 'flip': False}
    def flag(name):
        if not active['enabled']: raise HTTPException(404, 'off')
    def authorize(nid, token, branch, permission):
        active['calls'] += 1
        if token != 'trusted' or permission == 'domain.write' and active['actor'] == 'reader': raise HTTPException(403, 'denied')
        if nid != e.nid or branch: raise HTTPException(404, 'scope')
        actor = active['actor']
        if active['flip'] and active['calls'] % 2 == 0: actor = 'different'
        return actor, e.scope
    app = FastAPI(); app.include_router(create_style_analysis_router(e.style, authorize, flag)); app.include_router(create_narrative_judge_router(e.judge, authorize, flag))
    client = TestClient(app); headers = {'X-Session-Token': 'trusted'}; base = f'/novels/{e.nid}/experimental'
    for path in ('/style-analysis/catalog', '/narrative-judge/catalog', '/style-analysis/analyses', '/narrative-judge/runs'):
        response = client.get(base + path, headers=headers)
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
        active['enabled'] = False; assert client.get(base + path, headers=headers).status_code == 404; active['enabled'] = True
        assert client.get(base + path, headers={**headers, 'X-Branch-Id': 'other'}).status_code == 404
        active['actor'] = 'reader'; assert client.get(base + path, headers=headers).status_code == 403; active['actor'] = 'author'
    active.update(calls=0, flip=True)
    assert client.get(base + '/style-analysis/catalog', headers=headers).status_code == 409
    assert not e.style.analyses(e.nid, e.scope)


def test_source_ranges_never_double_count_and_ratios_are_recomputable(env):
    e = env; p = profile(e)
    with pytest.raises(ValueError, match='overlap'):
        analysis(e, p, samples=[{'chapter_id': e.order[0], 'expected_version': 1, 'start': 0, 'end': 8}, {'chapter_id': e.order[0], 'expected_version': 1, 'start': 4, 'end': 10}])
    value = metrics('A short sentence. Another sentence!', 'en')
    assert value['sentence_length_mean'] == {'numerator': sum(value['sentence_lengths_nonspace']), 'denominator': value['sentence_count']}
    assert value['repeated_unit_share'] == {'numerator': value['unit_count'] - value['unique_units'], 'denominator': value['unit_count']}


def test_review_store_failure_has_no_receipt_and_retry_deduplicates(env, monkeypatch):
    e = env
    original = e.creation.store._write
    calls = []
    def failing(collection, rows):
        calls.append(collection)
        if collection == 'review_threads': raise OSError('simulated storage failure')
        return original(collection, rows)
    monkeypatch.setattr(e.creation.store, '_write', failing)
    with pytest.raises(OSError): duplicate(e)
    assert not e.judge.runs(e.nid, e.scope) and not e.creation._rows('review_threads')
    monkeypatch.setattr(e.creation.store, '_write', original)
    first = duplicate(e); second = duplicate(e)
    assert first['id'] == second['id'] and len(e.creation._rows('review_threads')) == 1


def test_judge_rejects_wrong_paragraph_and_hidden_chapter_evidence(env):
    from app.experimental.narrative_judge import validate_evidence
    e = env; c = e.chapters[e.order[0]]
    evidence = {'chapter_id': c['id'], 'chapter_version': c['version'], 'paragraph': 2, 'start': 0, 'end': len(c['content']), 'quote': c['content']}
    with pytest.raises(ValueError, match='paragraph'): validate_evidence([evidence], {c['id']: c})
    evidence['paragraph'] = 1; evidence['chapter_id'] = e.order[1]
    with pytest.raises(ValueError, match='unselected'): validate_evidence([evidence], {c['id']: c})


def test_judge_privacy_and_source_deletion_redact_without_leaking_counts(env):
    e = env; result = duplicate(e); c = e.chapters[e.order[0]]
    review_source_privacy(c, None, 'author', 'CLOUD_ALLOWED', c['version'], content_digest(c), e.root)
    assert e.judge.run(e.nid, e.scope, result['id'])['findings'] == []
    newer = run(e, chapter_ids=e.order[:1]); assert newer['id'] != result['id']
    cid = e.order[0]; del e.chapters[cid]; e.order.remove(cid)
    redacted = e.judge.run(e.nid, e.scope, newer['id'])
    assert redacted['stale'] and redacted['findings'] == [] and 'finding_ids' not in redacted


def test_invalid_model_output_schema_never_echoes_unverified_text(env):
    e = env
    class Adapter:
        adapter_id = 'local-invalid'; model_identity = 'fixture'; execution_mode = 'LOCAL_MODEL'
        def judge(self, request):
            return {'opinions': [{'UNEXPECTED': 'UNKNOWN_PRIVATE_MODEL_STRING'}]}
    e.judge.adapters['local-invalid'] = Adapter()
    with pytest.raises(ValueError) as failure:
        run(e, adapter_id='local-invalid')
    assert str(failure.value) == 'JUDGE_ADAPTER_OUTPUT_INVALID'
    assert 'UNKNOWN_PRIVATE_MODEL_STRING' not in str(failure.value)
    assert not e.creation._rows('review_threads')
