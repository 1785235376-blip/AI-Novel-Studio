"""DIF-02 author decision checkpoints, original File owners, no task/model calls."""
import copy
import json

import pytest
from pydantic import ValidationError

from app.experimental.change_impact import ChangeImpactService, DecisionInput, node_key
from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from test_r3_media_support import rig
from test_r4_change_impact import impact, edit, query


def selection(r, s):
    graphs = [s.planning.create_graph(r.nid, r.scope, r.actor, {'title': title,
        'links': {'chapter_ids': [r.chapter['id']]}}) for title in ('Keep original plan', 'Rebuild requested plan')]
    other = r.chapters.create(r.nid, {'title': 'Unaffected chapter', 'content': 'Unrelated author text'})
    unrelated = s.planning.create_graph(r.nid, r.scope, r.actor, {'title': 'Unaffected plan', 'links': {'chapter_ids': [other['id']]}})
    edit(r)
    by_key = {n['key']: n for n in query(r, s)['items']}
    body = {'source': {'kind': 'CHAPTER', 'id': r.chapter['id']}, 'selected': [
        {'key': node_key('PLANNING_NODE', graph['root_node_id']), 'expected_version': by_key[node_key('PLANNING_NODE', graph['root_node_id'])]['version'], 'choice': choice}
        for graph, choice in zip(graphs, ('KEEP', 'REBUILD'))]}
    assert node_key('PLANNING_NODE', unrelated['root_node_id']) not in by_key
    return body


def save_body(s, r, body, request='explicit-save'):
    preview = s.preview_decisions(r.nid, r.scope, r.actor, body)
    return {**body, 'preview_digest': preview['preview_digest'], 'request_id': request}


def test_decision_preview_is_read_only_and_file_reopen_recovers_choices_without_changing_any_outcome(rig, impact):
    r, s = rig, impact; body = selection(r, s)
    before = copy.deepcopy(r.store.read(r.nid, r.scope))
    preview = s.preview_decisions(r.nid, r.scope, r.actor, body)
    assert r.store.read(r.nid, r.scope) == before
    assert [i['choice'] for i in preview['items']] == ['KEEP', 'REBUILD']
    assert all(not i['refresh_candidate'] for i in preview['items'])  # Original manual-review domains stay manual.
    assert preview['decision_only'] and not preview['automatic_execution']
    saved = s.save_decisions(r.nid, r.scope, r.actor, {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'only-intent'})
    after = copy.deepcopy(r.store.read(r.nid, r.scope))
    rows = after['collections'].pop(s.DECISIONS)
    assert len(rows) == 1 and after == before
    assert saved['current'] and saved['version'] == 1
    fresh = ChangeImpactService(ExperimentalStore(r.root, r.backend, r.store.database_url), r.novels, r.chapters,
        s.graph, s.production, s.planning, s.audiobook, enabled=s.enabled)
    assert fresh.decisions(r.nid, r.scope, r.actor, {'source': body['source']}) == {'items': [saved]}
    with pytest.raises(FileNotFoundError):
        s.prepare(r.nid, r.scope, r.actor, saved['id'], {'expected_version': 1, 'preflight_digest': saved['preview_digest'], 'idempotency_key': 'cannot-execute-intent'})
    assert not r.store.read(r.nid, r.scope)['collections'].get(s.REFRESHES)
    assert not r.store.read(r.nid, r.scope)['collections'].get(s.PLANS)
    assert r.chapters.get(r.chapter['id'])['content'].startswith('The source has changed.')


@pytest.mark.parametrize('change', ['source', 'lock'])
def test_changed_source_or_lock_rejects_save_atomically_and_keeps_decisions_historical(rig, impact, change):
    r, s = rig, impact; body = selection(r, s); pending = save_body(s, r, body)
    if change == 'source': edit(r, 'New source after preview')
    else: s.set_lock(r.nid, r.scope, r.actor, {**{k: body['selected'][0][k] for k in ('key', 'expected_version')}, 'expected_lock_version': 0, 'locked': True})
    before = copy.deepcopy(r.store.read(r.nid, r.scope))
    with pytest.raises(StaleSourceError): s.save_decisions(r.nid, r.scope, r.actor, pending)
    assert r.store.read(r.nid, r.scope) == before
    saved = s.save_decisions(r.nid, r.scope, r.actor, save_body(s, r, body, 'fresh-after-change'))
    edit(r, 'Later change, never automatically rebuild')
    historical = s.decisions(r.nid, r.scope, r.actor, {'source': body['source']})['items'][0]
    assert historical['id'] == saved['id'] and not historical['current'] and all(not i['current'] for i in historical['items'])
    assert s.save_decisions(r.nid, r.scope, r.actor, save_body(s, r, body, 'next-intent'))['id'] != saved['id']


def test_same_request_recovers_once_after_source_moves_but_conflicting_reuse_cannot_overwrite(rig, impact):
    r, s = rig, impact; body = selection(r, s); request = save_body(s, r, body)
    saved = s.save_decisions(r.nid, r.scope, r.actor, request)
    edit(r, 'The response was lost; source moved afterward')
    replayed = s.save_decisions(r.nid, r.scope, r.actor, request)
    assert replayed['id'] == saved['id'] and not replayed['current']
    assert len(s.list(r.nid, r.scope, s.DECISIONS)) == 1
    bad = copy.deepcopy(request); bad['selected'][0]['choice'] = 'REBUILD'
    with pytest.raises(ValueError, match='REQUEST_REUSED'): s.save_decisions(r.nid, r.scope, r.actor, bad)
    assert s.list(r.nid, r.scope, s.DECISIONS)[0]['entries'][0]['choice'] == 'KEEP'


def test_author_source_and_current_visibility_are_required_for_whole_checkpoint(rig, impact):
    r, s = rig, impact; body = selection(r, s); saved = s.save_decisions(r.nid, r.scope, r.actor, save_body(s, r, body))
    assert s.decisions(r.nid, r.scope, 'another-author', {'source': body['source']}) == {'items': []}
    wrong = {**body, 'source': {'kind': 'CHAPTER', 'id': 'foreign-chapter'}}
    with pytest.raises(FileNotFoundError): s.preview_decisions(r.nid, r.scope, r.actor, wrong)
    s.enabled = lambda name: name in {'change_impact_v2', 'temporal_story_graph_v2', 'asset_lineage_v2'}
    result = s.decisions(r.nid, r.scope, r.actor, {'source': body['source']})
    assert result == {'items': []} and saved['id'] not in json.dumps(result)


def test_duplicate_outside_choices_capacity_and_revoked_guard_cannot_create_extra_records(rig, impact):
    r, s = rig, impact; body = selection(r, s)
    with pytest.raises(ValueError, match='DUPLICATE'): s.preview_decisions(r.nid, r.scope, r.actor, {**body, 'selected': body['selected'] * 2})
    with pytest.raises(ValidationError): DecisionInput.model_validate({**body, 'selected': body['selected'] * 11})
    with pytest.raises(ValidationError): DecisionInput.model_validate({**body, 'selected': [{**body['selected'][0], 'choice': 'EXECUTE'}]})
    with pytest.raises(FileNotFoundError): s.preview_decisions(r.nid, r.scope, r.actor, {**body, 'selected': [{**body['selected'][0], 'key': 'PLANNING_NODE:foreign'}]})
    pending = save_body(s, r, body); before = copy.deepcopy(r.store.read(r.nid, r.scope)); calls = 0
    def revoked():
        nonlocal calls
        calls += 1
        if calls >= 4: raise PermissionError('revoked')
    with pytest.raises(PermissionError): s.save_decisions(r.nid, r.scope, r.actor, pending, revoked)
    assert r.store.read(r.nid, r.scope) == before
    for index in range(s.MAX_DECISIONS_PER_AUTHOR): s.save_decisions(r.nid, r.scope, r.actor, {**pending, 'request_id': f'decision-{index}'})
    with pytest.raises(ValueError, match='CAPACITY'): s.save_decisions(r.nid, r.scope, r.actor, {**pending, 'request_id': 'one-too-many'})
    assert len(s.list(r.nid, r.scope, s.DECISIONS)) == s.MAX_DECISIONS_PER_AUTHOR
