"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import base64

from copy import deepcopy

import io

import json

import zipfile

import pytest

from support_reconciliation_test_r4_revision_intelligence import revision_env

from app.experimental.interactive_story import InteractiveStoryService, StorySpec

from app.experimental.planning import PlanningService

from app.experimental.story_graph import StoryGraphService

from app.services.asset_library_service import AssetLibraryService

@pytest.fixture
def interactive_env(revision_env):
    e = revision_env
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.story_graph = StoryGraphService(e.store, e.novels, e.chapters)
    e.assets = AssetLibraryService(e.store.root)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice "[literal]" {text} 〖ruby'})
    e.graph = e.planning.create_graph(e.nid, e.scope, 'author', {'title': 'Synthetic choice tree', 'links': {'chapter_ids': [e.cid], 'character_ids': ['alice']}})
    e.nodes = [e.graph['root_node_id']]
    for title in ['Harbour', 'Mountain']:
        e.nodes.append(e.planning.create_node(e.nid, e.scope, 'author', {'graph_id': e.graph['id'], 'parent_id': e.nodes[0], 'level': 'VOLUME', 'title': title})['id'])
    return e

def spec(e):
    return StorySpec.model_validate({'title': 'Synthetic interactive adaptation', 'graph_id': e.graph['id'], 'graph_version': 1, 'entry_node_id': e.nodes[0],
        'variables': [{'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3}, {'name': 'trusted', 'type': 'bool', 'initial': True}],
        'nodes': [
            {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Gate', 'character_id': 'alice', 'dialogue': 'Choose "[safe]" {safe} 〖safe🙂é\nnot code', 'choices': [
                {'id': 'harbour', 'label': 'To harbour', 'target': e.nodes[1], 'condition': 'trusted and courage >= 0', 'assignments': {'courage': 2}},
                {'id': 'mountain', 'label': 'To mountain', 'target': e.nodes[2], 'condition': 'not (courage > 3)', 'assignments': {'trusted': False}}]},
            {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Harbour', 'dialogue': 'Home🙂', 'ending': 'Harbour ending'},
            {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Mountain', 'dialogue': 'Beyond the ridge', 'ending': 'Mountain ending'},
        ]}).model_dump()

def create(e, value=None): return e.service.create_story(e.nid, e.scope, 'author', {'spec': value or spec(e)})

def review(e, row, action, **kw): return e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': action, **kw})

def approve(e, row):
    row = review(e, row, 'submit'); receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return review(e, row, 'approve', preview_digest=receipt['preview_digest'])

def test_manual_issue_repair_preserves_pins_reopens_and_exports(interactive_env):
    """Original File owner: exact issue IDs -> human repair -> explicit saved export."""
    e = interactive_env; value = spec(e)
    value['nodes'][0]['choices'][0]['condition'] = 'unknown_flag'
    row = create(e, value)
    assert {'code': 'UNDEFINED_VARIABLE', 'node_id': e.nodes[0], 'choice_id': 'harbour'} in row['analysis']['issues']
    assert not row['analysis']['can_review']
    corrected = deepcopy(row['spec']); corrected['nodes'][0]['choices'][0]['condition'] = 'trusted'
    corrected['nodes'][0]['dialogue'] = '人工修复🙂é'
    saved = e.service.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'spec': corrected})
    assert saved['spec']['graph_id'] == row['spec']['graph_id'] and saved['spec']['graph_version'] == row['spec']['graph_version']
    assert [(n['node_id'], n['node_version']) for n in saved['spec']['nodes']] == [(n['node_id'], n['node_version']) for n in row['spec']['nodes']]
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    reopened = e.service.story(e.nid, e.scope, 'author', row['id'])
    assert reopened['spec'] == corrected and reopened['analysis']['can_review'] and reopened['status'] == 'DRAFT'
    result = e.service.preview(e.nid, e.scope, 'author', row['id'], {'expected_version': reopened['version'], 'choices': ['harbour']})
    assert result['status'] == 'ENDING' and result['variables']['courage'] == 2
    history = e.service.revisions(e.nid, e.scope, 'author', row['id'], {'expected_version': reopened['version']})
    assert history['items'][0]['spec'] == row['spec']
    approved = approve(e, reopened)
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': approved['version']})
    bundle = e.service.export(e.nid, e.scope, 'author', row['id'], {'expected_version': approved['version'], 'preview_digest': preview['preview_digest']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(bundle['content_base64']))) as archive:
        name = next(n for n in archive.namelist() if n.endswith('/story.json') and '/godot/' not in n)
        exported = json.loads(archive.read(name))
        assert exported['adaptation_version'] == approved['version']
        assert exported['spec']['nodes'][0]['dialogue'] == '人工修复🙂é'
    assert bundle['target_runtime'] == 'NOT_RUN' and not bundle['published']
