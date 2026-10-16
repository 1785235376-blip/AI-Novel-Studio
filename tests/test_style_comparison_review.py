"""Nonsecurity original File-owner comparison evidence, no provider or dispatch."""
from copy import deepcopy
from app.experimental.style_analysis import StyleAnalysisService
from app.experimental.store import ExperimentalStore
from test_r4_style_judge import env, planning_env, profile, analysis


def test_saved_target_unicode_measurements_reopen_without_editing_original_owners(env):
    e = env
    e.chapters[e.order[0]]['content'] = '雨。\n\n雨😀。'
    e.chapters[e.order[1]]['content'] = '风😀。\n\n「风。」'
    before = deepcopy(e.chapters)
    p = profile(e)
    a = analysis(e, p, language='zh', comparison={
        'chapter_id': e.order[1], 'expected_version': e.chapters[e.order[1]]['version'], 'language': 'zh'})
    target = a['comparison']
    assert target['comparable'] is True
    assert target['interpretation'] == 'RAW_COUNT_DIFFERENCES_NOT_QUALITY_OR_NORMALIZED_DRIFT'
    assert target['metrics']['sample_sufficiency'] == 'SHORT_SAMPLE'
    assert a['sources'][target['chapter_id']]['version'] == target['expected_version']
    for paragraph in target['paragraphs']:
        assert e.chapters[target['chapter_id']]['content'][paragraph['start']:paragraph['end']] == paragraph['quote']
    reopened = StyleAnalysisService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, e.creation)
    assert reopened.analysis(e.nid, e.scope, a['id'])['comparison'] == target
    assert e.creation.get_record(e.nid, e.scope, p['id'])['version'] == p['version']
    assert e.chapters == before
    assert a['model_called'] is False
