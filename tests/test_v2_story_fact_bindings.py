"""Manual Story fact → original Creative shot → formal Asset, without generation."""
from copy import deepcopy
import json

import pytest

from test_v2_independent_workspace import rig, import_asset, png_bytes, reopened
from test_v2_storyboard_workspace import configured, board_value, bind, content, approve
from app.experimental.story_graph import StoryGraphService
from app.experimental.common import StaleSourceError
from app.creative.story_fact_bindings import FactUseIn, COLLECTION


def fact(e, creative, *, layer='WORLD_FACT', approved=True):
    graph = StoryGraphService(e.raw_store, e.novels, e.chapters)
    creative.story_facts.configure(graph)
    chapter = e.chapters.create(e.nid, {'title': 'Scar event', 'content': 'After the event a scar remains.'})
    row = graph.create_record(e.nid, e.scope, e.actor, {'kind': 'STORY_RELATION', 'title': 'Scar after event',
        'chapter_id': chapter['id'], 'data': {'subject': {'kind': 'CHAPTER', 'id': chapter['id']},
        'object': {'kind': 'CHAPTER', 'id': chapter['id']}, 'relation': 'ABOUT', 'layer': layer,
        'statement': 'A scar remains after this event', 'valid_from': 10}})
    if approved: row = graph.review(e.nid, e.scope, e.actor, row['id'], 'approve', row['version'])
    return graph, chapter, row


def body(e, creative, rid, *, shot_id='shot-1'):
    receipt = creative.storyboards.get(e.nid, e.scope, e.actor, rid)
    shot = next(s for s in receipt['shots'] if s['shot_id'] == shot_id)
    selected = creative.story_facts.catalog(e.nid, e.scope, e.actor)['items'][0]
    return {'expected_version': receipt['document_snapshot']['version'], 'document_digest': receipt['document_snapshot']['digest'],
        'shot_version': shot['shot_version'], 'shot_digest': shot['shot_digest'],
        'fact': {k: selected[k] for k in ('id', 'version', 'digest')}, 'purpose': 'APPEARANCE_STATE',
        'rationale': 'This shot is after the scar event.', 'confirmed': True}


def test_confirm_reopen_exact_assets_and_no_document_or_asset_mutation(rig, monkeypatch):
    creative, production = configured(rig, monkeypatch)
    graph, chapter, source = fact(rig, creative)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    asset = import_asset(rig, data=png_bytes(), filename='scar.png', kind='image')
    bind(creative, rig, row['id'], 'shot-1', asset)
    approve(creative, rig, row['id'])
    before = deepcopy(creative.get(rig.nid, rig.scope, row['id']))
    request = body(rig, creative, row['id'])
    saved = creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request)
    assert saved['status'] == 'CONFIRMED'
    assert creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request) == saved
    result = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, fact_id=source['id'])
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['state'] == 'CURRENT' and item['assets'][0]['asset_id'] == asset['id']
    assert item['target']['shot_id'] == 'shot-1' and 'shot-2' not in json.dumps(result)
    assert item['evidence_path'][0]['id'] == source['id']
    assert result['automatic_regeneration'] is result['model_called'] is False
    assert result['temporal_reasoning'] == 'NOT_EVALUATED'
    assert creative.get(rig.nid, rig.scope, row['id']) == before
    assert rig.service.asset(rig.nid, rig.scope, asset['id'])['sha256'] == asset['sha256']
    again = reopened(rig).creative
    again.configure_storyboard_production(production)
    again.story_facts.configure(graph)
    assert again.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id']) == result


def test_fact_revocation_and_original_review_change_show_explicit_staleness(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    graph, _, source = fact(rig, creative)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    request = body(rig, creative, row['id'])
    creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request)
    archived = graph.review(rig.nid, rig.scope, rig.actor, source['id'], 'archive', source['version'])
    item = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, fact_id=source['id'])['items'][0]
    assert item['state'] == 'STALE' and 'FACT_NOT_CURRENT_APPROVED' in item['blockers']
    assert creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items'] == []
    with pytest.raises(StaleSourceError): creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request)
    reopened_fact = graph.review(rig.nid, rig.scope, rig.actor, source['id'], 'reopen', archived['version'])
    edited = graph.edit_record(rig.nid, rig.scope, rig.actor, source['id'], {'kind': source['kind'], 'title': source['title'],
        'chapter_id': source['chapter_id'], 'data': {**source['data'], 'statement': 'The scar is on the other cheek.'},
        'expected_version': reopened_fact['version']})
    graph.review(rig.nid, rig.scope, rig.actor, source['id'], 'approve', edited['version'])
    item = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, fact_id=source['id'])['items'][0]
    assert item['blockers'] == ['FACT_PIN_CHANGED']


@pytest.mark.parametrize('bad', ['fact_version', 'document_digest', 'shot_digest', 'confirmed', 'extra'])
def test_strict_confirmation_and_source_cas_leave_no_pointer(rig, monkeypatch, bad):
    creative, _ = configured(rig, monkeypatch); fact(rig, creative)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value()); request = body(rig, creative, row['id'])
    if bad == 'fact_version': request['fact']['version'] += 1
    elif bad == 'document_digest': request['document_digest'] = '0' * 64
    elif bad == 'shot_digest': request['shot_digest'] = '0' * 64
    elif bad == 'confirmed': request['confirmed'] = 1
    else: request['automatic_approval'] = True
    with pytest.raises(ValueError): creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request)
    assert creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])['items'] == []


def test_only_reviewed_world_fact_relations_are_catalogued(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    creative.create(rig.nid, rig.scope, rig.actor, board_value())
    fact(rig, creative, layer='SPECULATION'); fact(rig, creative, approved=False)
    assert creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items'] == []


def test_changed_shot_does_not_attach_new_assets_and_other_shot_is_preserved(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch); fact(rig, creative)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    asset = import_asset(rig, data=png_bytes(), filename='preserved.png', kind='image')
    bind(creative, rig, row['id'], 'shot-2', asset)
    before = creative.storyboards.get(rig.nid, rig.scope, rig.actor, row['id'])
    creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', body(rig, creative, row['id']))
    old = creative.get(rig.nid, rig.scope, row['id']); value = content(old); value['shots'][0]['action'] = 'Inspect the scar'
    creative.update(rig.nid, rig.scope, rig.actor, row['id'], old['version'], value)
    item = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])['items'][0]
    assert 'SHOT_PIN_CHANGED' in item['blockers'] and item['assets'] == []
    after = creative.storyboards.get(rig.nid, rig.scope, rig.actor, row['id'])
    assert after['shots'][1] == before['shots'][1]
    assert rig.service.asset(rig.nid, rig.scope, asset['id'])['sha256'] == asset['sha256']


def test_revocation_at_commit_rolls_back_pointer_only(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch); fact(rig, creative)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value()); request = body(rig, creative, row['id'])
    before = deepcopy(rig.store.read(rig.nid, rig.scope))
    def guard():
        state = creative.store.read(rig.nid, rig.scope)
        if state['collections'].get(COLLECTION): raise PermissionError('revoked')
    with pytest.raises(PermissionError): creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request, guard)
    assert rig.store.read(rig.nid, rig.scope) == before


@pytest.mark.parametrize('change', ['foreign_branch', 'hidden', 'secret'])
def test_inaccessible_entity_omits_entire_usage_without_identifiers(rig, monkeypatch, change):
    creative, _ = configured(rig, monkeypatch)
    graph, chapter, source = fact(rig, creative)
    rig.novels.upsert_character(rig.nid, 'scar-person', {'name': 'SENSITIVE_ENTITY'})
    source = graph.create_record(rig.nid, rig.scope, rig.actor, {'kind': 'STORY_RELATION', 'title': 'SENSITIVE_FACT',
        'chapter_id': chapter['id'], 'data': {**source['data'], 'subject': {'kind': 'CHARACTER', 'id': 'scar-person'}}})
    source = graph.review(rig.nid, rig.scope, rig.actor, source['id'], 'approve', source['version'])
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    request = body(rig, creative, row['id'])
    pin = next(f for f in creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items'] if f['id'] == source['id'])
    request['fact'] = {k: pin[k] for k in ('id', 'version', 'digest')}; request['rationale'] = 'SENSITIVE_RATIONALE'
    saved = creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request)
    assert creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])['items'][0]['state'] == 'CURRENT'
    patch = {'branch_id': 'foreign'} if change == 'foreign_branch' else {change: True}
    rig.novels.upsert_character(rig.nid, 'scar-person', {'name': 'SENSITIVE_ENTITY', **patch})
    result = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
    assert result['items'] == []
    serialized = json.dumps(result)
    for private in (saved['id'], source['id'], row['id'], 'SENSITIVE_FACT', 'SENSITIVE_RATIONALE'):
        assert private not in serialized
    with pytest.raises(FileNotFoundError): creative.story_facts.impact(rig.nid, rig.scope, rig.actor, fact_id=source['id'])


def test_stale_accessible_derived_document_metadata_does_not_relax_get_or_list(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch); fact(rig, creative)
    parent = creative.create(rig.nid, rig.scope, rig.actor, {'mode': 'SCREENPLAY', 'title': 'Original', 'source_independent': True})
    row = creative.create_derived(rig.nid, rig.scope, rig.actor, board_value(source_independent=False),
        source_documents={parent['id']: {'version': parent['version'], 'digest': creative.document_digest(parent)}})
    creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', body(rig, creative, row['id']))
    value = content(parent); value['title'] = 'New current source title'
    creative.update(rig.nid, rig.scope, rig.actor, parent['id'], parent['version'], value)
    with pytest.raises(StaleSourceError): creative.get(rig.nid, rig.scope, row['id'])
    assert row['id'] not in {r['id'] for r in creative.list(rig.nid, rig.scope)}
    result = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
    assert result['items'][0]['blockers'] == ['DOCUMENT_SOURCE_STALE']
    parent = creative.get(rig.nid, rig.scope, parent['id'])
    creative.archive(rig.nid, rig.scope, rig.actor, parent['id'], parent['version'])
    with pytest.raises(FileNotFoundError): creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])


def test_old_unbound_facts_not_lazily_adopted_by_catalog_or_review(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    graph, _, old = fact(rig, creative)
    # Create through an unconfigured original graph, preserving its legacy shape.
    legacy = StoryGraphService(rig.raw_store, rig.novels, rig.chapters)
    value = {k: old[k] for k in ('kind', 'title', 'chapter_id', 'data')}
    row = legacy.create_record(rig.nid, rig.scope, rig.actor, value)
    row = legacy.review(rig.nid, rig.scope, rig.actor, row['id'], 'approve', row['version'])
    assert 'story_project_incarnation' not in row
    assert row['id'] not in {f['id'] for f in creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items']}
    assert 'story_project_incarnation' not in legacy.record(rig.nid, rig.scope, row['id'])
    assert old['id'] in {f['id'] for f in creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items']}


def test_recreated_project_identical_chapter_sources_cannot_revive_fact(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    graph, chapter, old = fact(rig, creative)
    epoch = old['story_project_incarnation']
    original = deepcopy(rig.chapters.get(chapter['id']))
    rig.novels.delete(rig.nid)
    rig.create_project(nid=rig.nid)
    replacement = rig.chapters.create(rig.nid, {'title': original['title'], 'content': 'After the event a scar remains.'})
    replacement = rig.chapters.get(replacement['id'])
    assert replacement['id'] == original['id']
    assert (replacement['version'], replacement['number'], replacement['content']) == (original['version'], original['number'], original['content'])
    # Same legacy references are deliberately still fresh; epoch must reject them.
    graph._assert_fresh(rig.nid, rig.scope, old, graph.store.read(rig.nid, rig.scope))
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    assert creative.store.incarnation(rig.nid) != epoch
    assert creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items'] == []
    with pytest.raises(FileNotFoundError): creative.story_facts.impact(rig.nid, rig.scope, rig.actor, fact_id=old['id'])
    new = graph.create_record(rig.nid, rig.scope, rig.actor, {k: old[k] for k in ('kind', 'title', 'chapter_id', 'data')})
    new = graph.review(rig.nid, rig.scope, rig.actor, new['id'], 'approve', new['version'])
    assert new['story_project_incarnation'] != epoch
    saved = creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', body(rig, creative, row['id']))
    assert saved['fact']['id'] == new['id']


def test_final_response_rechecks_access_and_never_returns_cached_private_item(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    graph, chapter, source = fact(rig, creative)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', body(rig, creative, row['id']))
    calls = []
    def guard():
        calls.append(1)
        if len(calls) == 3: raise PermissionError('authority revoked before response')
    with pytest.raises(PermissionError):
        creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'], guard=guard)
    assert creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])['items'][0]['state'] == 'CURRENT'


def test_configured_graph_creation_without_prior_creative_and_denied_no_marker(rig, monkeypatch):
    from app.creative.service import CreativeService
    nid = rig.create_project()
    scope = {'mode': 'local', 'novel_id': nid}
    creative = CreativeService(rig.raw_store, rig.novels, rig.chapters)
    graph = StoryGraphService(rig.raw_store, rig.novels, rig.chapters)
    creative.story_facts.configure(graph)
    chapter = rig.chapters.create(nid, {'title': 'First', 'content': 'A real source.'})
    payload = {'kind': 'STORY_RELATION', 'title': 'New fact', 'chapter_id': chapter['id'], 'data': {
        'subject': {'kind': 'CHAPTER', 'id': chapter['id']}, 'object': {'kind': 'CHAPTER', 'id': chapter['id']},
        'relation': 'ABOUT', 'layer': 'WORLD_FACT', 'statement': 'The first fact.'}}
    marker = rig.root / 'novels' / nid / 'creative_project_v2.json'
    if rig.backend == 'file': assert not marker.exists()
    def denied(): raise PermissionError('denied')
    with pytest.raises(PermissionError): graph.create_record(nid, scope, rig.actor, payload, reauthorize=denied)
    with pytest.raises(ValueError): graph.create_record(nid, scope, rig.actor, {**payload, 'story_project_incarnation': 'client-forged'})
    if rig.backend == 'file': assert not marker.exists()
    created = graph.create_record(nid, scope, rig.actor, payload)
    assert created['story_project_incarnation'] == creative.store.incarnation(nid)
    assert not creative.list(nid, scope)


def test_shared_fact_ancestors_are_memoized_and_request_budget_is_explicit(rig, monkeypatch):
    import app.creative.story_fact_bindings as module
    creative, _ = configured(rig, monkeypatch)
    graph, chapter, _ = fact(rig, creative)
    concepts = []
    for index in range(2):
        row = graph.create_record(rig.nid, rig.scope, rig.actor, {'kind': 'STORY_CONCEPT', 'title': f'Prop {index}',
            'chapter_id': chapter['id'], 'data': {'concept_type': 'ITEM', 'description': 'Shared approved prop'}})
        concepts.append(graph.review(rig.nid, rig.scope, rig.actor, row['id'], 'approve', row['version']))
    for index in range(5):
        row = graph.create_record(rig.nid, rig.scope, rig.actor, {'kind': 'STORY_RELATION', 'title': f'Use {index}',
            'chapter_id': chapter['id'], 'data': {'subject': {'kind': 'ITEM', 'id': concepts[0]['id']},
                'object': {'kind': 'ITEM', 'id': concepts[1]['id']}, 'relation': 'RELATED_TO',
                'layer': 'WORLD_FACT', 'statement': 'Explicit shared relation'}})
        graph.review(rig.nid, rig.scope, rig.actor, row['id'], 'approve', row['version'])
    original = graph._capture; captures = []
    def counted(*args):
        captures.append(args[2].get('id')); return original(*args)
    monkeypatch.setattr(graph, '_capture', counted)
    result = creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)
    assert len(result['items']) == 6
    # Eight unique records, each checked once per before/after observation.
    assert len(captures) == 16
    monkeypatch.setattr(module, 'MAX_FACT_VISITS', 5)
    with pytest.raises(module.FactCapacityError, match='TRAVERSAL_LIMIT'):
        creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)


def test_mid_creation_denial_leaves_no_fact_and_never_rebinds_old_epoch(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    graph, _, original = fact(rig, creative)
    before = deepcopy(graph.store.read(rig.nid, rig.scope))
    def deny_after_write():
        rows = graph.store.read(rig.nid, rig.scope)['collections'].get(graph.RECORDS, {})
        if len(rows) > len(before['collections'][graph.RECORDS]):
            raise PermissionError('review authority revoked after staging')
    with pytest.raises(PermissionError):
        graph.create_record(rig.nid, rig.scope, rig.actor, {k: original[k] for k in ('kind', 'title', 'chapter_id', 'data')}, reauthorize=deny_after_write)
    assert graph.store.read(rig.nid, rig.scope) == before
    # Original owner identity may exist after a later denied create. It is inert:
    # no record is adopted or rebound and no partial World/use write persists.
    assert graph.record(rig.nid, rig.scope, original['id'])['story_project_incarnation'] == original['story_project_incarnation']


def test_bounded_freshness_matches_original_owner_before_and_after_source_drift(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    graph, chapter, source = fact(rig, creative)
    def parity():
        state, rows = graph._rows(rig.nid, rig.scope)
        try:
            graph._assert_fresh(rig.nid, rig.scope, rows[source['id']], state)
            original = True
        except StaleSourceError:
            original = False
        assert creative.story_facts._fact(rig.nid, rig.scope, source['id'])['fresh'] is original
        return original
    assert parity() is True
    current = rig.chapters.get(chapter['id'])
    rig.chapters.save(chapter['id'], {'version': current['version'], 'content': 'The source changed under the same identity.'})
    assert parity() is False
    # Projection consumes the owner's field contract, not a parallel frozen list.
    assert graph._fresh_capture_fields(source) == ('effective_chapter', 'entity_sources', 'semantic_sources', 'effective_until')


def test_bridge_reads_missing_project_owner_do_not_initialize_it(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    nid = rig.create_project(); scope = {'mode': 'local', 'novel_id': nid}
    marker = rig.root / 'novels' / nid / 'creative_project_v2.json'
    if rig.backend == 'file':
        assert not marker.exists()
        with pytest.raises(FileNotFoundError): creative.story_facts.catalog(nid, scope, rig.actor)
        with pytest.raises(FileNotFoundError): creative.story_facts.impact(nid, scope, rig.actor, fact_id='absent')
        assert not marker.exists()
    else:
        # PostgreSQL's original project row itself is the existing incarnation.
        with pytest.raises(FileNotFoundError):
            creative.story_facts.impact(nid, scope, rig.actor, document_id='absent')


def test_archived_original_planning_scene_withholds_fact_use(rig, monkeypatch):
    from app.experimental.planning import PlanningService
    creative, _ = configured(rig, monkeypatch)
    graph, chapter, first = fact(rig, creative)
    planning = PlanningService(rig.raw_store, rig.novels, rig.chapters)
    plan = planning.create_graph(rig.nid, rig.scope, rig.actor, {'title': 'Source plan'})
    parent = plan['root_node_id']
    for level in ('VOLUME', 'CHAPTER', 'SCENE'):
        node = planning.create_node(rig.nid, rig.scope, rig.actor, {'graph_id': plan['id'], 'parent_id': parent,
            'level': level, 'title': level, 'links': {'chapter_ids': [chapter['id']]} if level != 'VOLUME' else {}})
        parent = node['id']
    source = graph.create_record(rig.nid, rig.scope, rig.actor, {'kind': 'STORY_RELATION', 'title': 'PRIVATE_SCENE_FACT',
        'chapter_id': chapter['id'], 'data': {**first['data'], 'subject': {'kind': 'SCENE', 'id': node['id']}}})
    source = graph.review(rig.nid, rig.scope, rig.actor, source['id'], 'approve', source['version'])
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    request = body(rig, creative, row['id'])
    pin = next(f for f in creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items'] if f['id'] == source['id'])
    request['fact'] = {k: pin[k] for k in ('id', 'version', 'digest')}
    creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request)
    planning.transition_node(rig.nid, rig.scope, rig.actor, node['id'], 'archive', node['version'])
    result = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
    assert result['items'] == [] and 'PRIVATE_SCENE_FACT' not in json.dumps(result)


def test_formal_asset_observation_uses_original_asset_before_project_phase(rig, monkeypatch):
    creative, production = configured(rig, monkeypatch); fact(rig, creative)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    asset = import_asset(rig, filename='phase.png', kind='image')
    bind(creative, rig, row['id'], 'shot-1', asset)
    creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', body(rig, creative, row['id']))
    original = production.timeline_inputs._read
    calls = []
    def checked_read(nid, scope, reference, guard):
        assert production.timeline_inputs.in_phase(nid, scope, rig.actor)
        calls.append(reference['asset_id'])
        return original(nid, scope, reference, guard)
    monkeypatch.setattr(production.timeline_inputs, '_read', checked_read)
    result = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
    assert result['items'][0]['assets'][0]['asset_id'] == asset['id']
    assert calls == [asset['id'], asset['id']]


def test_entity_becoming_foreign_at_response_boundary_never_returns_cached_fact(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    graph, chapter, first = fact(rig, creative)
    rig.novels.upsert_character(rig.nid, 'late-person', {'name': 'Late person'})
    source = graph.create_record(rig.nid, rig.scope, rig.actor, {'kind': 'STORY_RELATION', 'title': 'LATE_PRIVATE_FACT',
        'chapter_id': chapter['id'], 'data': {**first['data'], 'subject': {'kind': 'CHARACTER', 'id': 'late-person'}}})
    source = graph.review(rig.nid, rig.scope, rig.actor, source['id'], 'approve', source['version'])
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    request = body(rig, creative, row['id'])
    pin = next(f for f in creative.story_facts.catalog(rig.nid, rig.scope, rig.actor)['items'] if f['id'] == source['id'])
    request['fact'] = {k: pin[k] for k in ('id', 'version', 'digest')}
    creative.story_facts.confirm(rig.nid, rig.scope, rig.actor, row['id'], 'shot-1', request)
    original = creative.story_facts._item; observed = []
    if rig.backend == 'postgres':
        # The real PG project lease serializes the original repository writer.
        # A synchronous in-lease mutation would wait on this very read's lease.
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        started, finished = Event(), Event()
        def revoke():
            started.set()
            rig.novels.upsert_character(rig.nid, 'late-person', {'name': 'Late person', 'branch_id': 'foreign'})
            finished.set()
        with ThreadPoolExecutor(max_workers=1) as executor:
            def concurrent_revocation(*args, **kwargs):
                result = original(*args, **kwargs)
                if not observed:
                    observed.append(executor.submit(revoke))
                    assert started.wait(5)
                    assert not finished.wait(0.15), 'Original writer must wait for project lease'
                return result
            monkeypatch.setattr(creative.story_facts, '_item', concurrent_revocation)
            current = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
            assert current['items'][0]['state'] == 'CURRENT'
            observed[0].result(timeout=10)
        monkeypatch.setattr(creative.story_facts, '_item', original)
        result = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
        assert result['items'] == [] and 'LATE_PRIVATE_FACT' not in json.dumps(result)
        return
    def move_after_observation(*args, **kwargs):
        result = original(*args, **kwargs)
        if not observed:
            observed.append(1)
            rig.novels.upsert_character(rig.nid, 'late-person', {'name': 'Late person', 'branch_id': 'foreign'})
        return result
    monkeypatch.setattr(creative.story_facts, '_item', move_after_observation)
    with pytest.raises(FileNotFoundError): creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
    monkeypatch.setattr(creative.story_facts, '_item', original)
    result = creative.story_facts.impact(rig.nid, rig.scope, rig.actor, document_id=row['id'])
    assert result['items'] == [] and 'LATE_PRIVATE_FACT' not in json.dumps(result)
