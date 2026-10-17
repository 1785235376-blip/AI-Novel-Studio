"""Add-only authoring handoff through the original File owner and mounted routes.

No provider, browser, PostgreSQL, or target engine execution is claimed here.
"""
import base64
from copy import deepcopy
import io
import json
from types import SimpleNamespace
import zipfile

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.experimental.common import StaleSourceError
from app.experimental.interactive_story import InteractiveStoryService, StoryNode, StorySpec, parse_condition
from app.experimental.planning import PlanningService
from app.experimental.store import ExperimentalStore
from app.experimental.story_graph import StoryGraphService
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.services.asset_library_service import AssetLibraryService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_mounted_contracts import mounted, prefix, checked, scoped

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def membership_env(tmp_path):
    config = Settings(storage_backend='file', database_url='', novel_data=tmp_path, mock_provider=True, enable_cloud=False)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    chapters, novels = ChapterService(bundle.chapters), NovelService(bundle.novels, bundle.chapters)
    nid = 'membership-handoff'
    novels.create({'id': nid, 'title': 'Membership handoff', 'genre': 'fantasy'})
    chapter = chapters.create(nid, {'title': 'Original manuscript', 'content': '正文🙂é不可改写'})
    scope = {'mode': 'local', 'novel_id': nid}
    store = ExperimentalStore(tmp_path, 'file', '')
    planning = PlanningService(store, novels, chapters)
    graph = planning.create_graph(nid, scope, 'author', {'title': 'Original planning graph', 'links': {'chapter_ids': [chapter['id']]}})
    nodes = [graph['root_node_id']]
    for _ in range(2):
        node = planning.create_node(nid, scope, 'author', {'graph_id': graph['id'], 'parent_id': nodes[0], 'level': 'VOLUME', 'title': 'Duplicate ending title'})
        nodes.append(node['id'])
    graph_service, assets = StoryGraphService(store, novels, chapters), AssetLibraryService(tmp_path)
    service = InteractiveStoryService(store, novels, chapters, planning, graph_service, assets)
    spec = StorySpec.model_validate({'title': 'Existing subset', 'graph_id': graph['id'], 'graph_version': graph['version'], 'entry_node_id': nodes[0], 'max_steps': 8,
        'variables': [{'name': 'trusted', 'type': 'bool', 'initial': True}],
        'nodes': [{'node_id': nodes[0], 'node_version': 1, 'title': 'Gate', 'dialogue': '原对白🙂é', 'choices': [{'id': 'home', 'label': 'Original ending', 'target': nodes[1], 'condition': 'trusted', 'assignments': {'trusted': False}}]},
                  {'node_id': nodes[1], 'node_version': 1, 'title': 'Duplicate ending title', 'dialogue': 'Old ending', 'ending': 'Home'}]}).model_dump()
    return SimpleNamespace(nid=nid, cid=chapter['id'], scope=scope, store=store, chapters=chapters, novels=novels, planning=planning, graph=graph, nodes=nodes, graph_service=graph_service, assets=assets, service=service, spec=spec)


def create(e):
    return e.service.create_story(e.nid, e.scope, 'author', {'spec': e.spec})


def append_original(e, row):
    graph = next(graph for graph in e.service.catalog(e.nid, e.scope)['graphs'] if graph['id'] == row['spec']['graph_id'])
    candidate = next(node for node in graph['nodes'] if node['node_id'] == e.nodes[2])
    spec = deepcopy(row['spec'])
    spec['nodes'].append(StoryNode.model_validate(candidate).model_dump())
    return spec


def save(e, row, spec, **kwargs):
    return e.service.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'spec': spec}, **kwargs)


def approve(e, row):
    row = e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'submit'})
    receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'approve', 'preview_digest': receipt['preview_digest']})


def test_subset_add_save_restart_history_manual_branch_review_and_exact_export(membership_env):
    e = membership_env
    original_sources = deepcopy((e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id'])))
    row = create(e); appended = append_original(e, row)
    assert appended['nodes'][:-1] == row['spec']['nodes']
    assert appended['entry_node_id'] == row['spec']['entry_node_id'] and appended['variables'] == row['spec']['variables']
    assert appended['nodes'][-1] == {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Duplicate ending title', 'dialogue': '', 'ending': '', 'character_id': None, 'background_asset_id': None, 'music_asset_id': None, 'choices': []}
    saved = save(e, row, appended)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.graph_service, e.assets)
    reopened = e.service.story(e.nid, e.scope, 'author', row['id'])
    assert reopened['spec'] == appended and reopened['version'] == 2 and reopened['status'] == 'DRAFT'
    history = e.service.revisions(e.nid, e.scope, 'author', row['id'], {'expected_version': reopened['version']})
    assert history['items'][0]['spec'] == row['spec']
    manual = deepcopy(reopened['spec']); manual['nodes'][-1].update(dialogue='新路🙂é', ending='New ending')
    manual['nodes'][0]['choices'].append({'id': 'new_path', 'label': 'Take new path', 'target': e.nodes[2], 'condition': 'trusted', 'assignments': {'trusted': False}})
    revised = save(e, reopened, manual)
    assert revised['spec']['nodes'][0]['choices'][0] == row['spec']['nodes'][0]['choices'][0]
    for choice, ending in [('home', 'Home'), ('new_path', 'New ending')]:
        result = e.service.preview(e.nid, e.scope, 'author', row['id'], {'expected_version': revised['version'], 'choices': [choice]})
        assert result['status'] == 'ENDING' and result['node']['ending'] == ending and result['variables'] == {'trusted': False}
    approved = approve(e, revised)
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': approved['version']})
    bundle = e.service.export(e.nid, e.scope, 'author', row['id'], {'expected_version': approved['version'], 'preview_digest': preview['preview_digest']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(bundle['content_base64']))) as archive:
        neutral = json.loads(archive.read(f"interactive-story-{row['id']}/story.json"))
        exported_spec = deepcopy(manual)
        for node in exported_spec['nodes']:
            for choice in node['choices']: choice['condition_tree'] = parse_condition(choice['condition'])
        assert neutral['spec'] == exported_spec and neutral['adaptation_version'] == approved['version']
        assert neutral['source_versions'] == {e.cid: original_sources[0]['version']}
        assert [(node['node_id'], node['node_version']) for node in neutral['spec']['nodes']] == [(node, 1) for node in e.nodes]
    assert bundle['target_runtime'] == 'NOT_RUN' and not bundle['published']
    assert (e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id'])) == original_sources


def test_membership_save_cas_and_explicit_history_restore(membership_env):
    e = membership_env; row = create(e); appended = append_original(e, row); saved = save(e, row, appended)
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(CapabilityVersionConflict): save(e, row, appended)
    assert e.store.read(e.nid, e.scope) == before
    old = e.service.revisions(e.nid, e.scope, 'author', row['id'], {'expected_version': saved['version']})['items'][0]
    restored = e.service.restore_revision(e.nid, e.scope, 'author', row['id'], {'expected_version': saved['version'], 'restore_version': old['version'], 'preview_digest': old['preview_digest']})
    assert restored['spec'] == row['spec'] and restored['version'] == 3 and restored['status'] == 'DRAFT'


def test_changed_graph_requires_original_explicit_rebind_before_addition(membership_env):
    e = membership_env; row = create(e)
    archived = e.planning.transition_graph(e.nid, e.scope, 'author', e.graph['id'], 'archive', 1)
    current_graph = e.planning.transition_graph(e.nid, e.scope, 'author', e.graph['id'], 'restore', archived['version'])
    old = deepcopy(row['spec'])
    preview = e.service.refresh_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    assert e.service.story(e.nid, e.scope, 'author', row['id'])['stale']
    rebound = e.service.refresh(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'preview_digest': preview['preview_digest']})
    assert rebound['spec'] == {**old, 'graph_version': current_graph['version']}
    saved = save(e, rebound, append_original(e, rebound))
    assert saved['spec']['graph_version'] == current_graph['version']
    assert saved['spec']['nodes'][:-1] == old['nodes'] and saved['status'] == 'DRAFT'


@pytest.mark.parametrize('drift', ['graph-aba', 'candidate-version', 'candidate-archived', 'manuscript'])
def test_original_save_rejects_changed_sources_without_silent_repin(membership_env, drift):
    e = membership_env; row = create(e); appended = append_original(e, row)
    if drift == 'graph-aba':
        archived = e.planning.transition_graph(e.nid, e.scope, 'author', e.graph['id'], 'archive', 1)
        e.planning.transition_graph(e.nid, e.scope, 'author', e.graph['id'], 'restore', archived['version'])
    elif drift == 'candidate-version':
        e.planning.edit_node(e.nid, e.scope, 'author', e.nodes[2], {'expected_version': 1, 'title': 'Updated candidate'})
    elif drift == 'candidate-archived':
        e.planning.transition_node(e.nid, e.scope, 'author', e.nodes[2], 'archive', 1)
    else:
        e.chapters.save(e.cid, {'version': e.chapters.get(e.cid)['version'], 'content': 'Changed manuscript'})
    before = e.store.read(e.nid, e.scope)
    with pytest.raises((StaleSourceError, FileNotFoundError)): save(e, row, appended)
    assert e.store.read(e.nid, e.scope) == before
    if drift in {'graph-aba', 'manuscript'}:
        hidden = e.service.story(e.nid, e.scope, 'author', row['id'])
        assert hidden['stale'] and hidden['content_withheld'] and 'spec' not in hidden


@pytest.mark.parametrize('invalid', ['cross-graph', 'duplicate-id', 'wrong-pin', 'over-limit'])
def test_original_owner_rejects_invalid_membership_atomically(membership_env, invalid):
    e = membership_env; row = create(e); appended = append_original(e, row)
    if invalid == 'cross-graph':
        graph = e.planning.create_graph(e.nid, e.scope, 'author', {'title': 'Other graph'})
        appended['nodes'][-1]['node_id'] = graph['root_node_id']
    elif invalid == 'duplicate-id': appended['nodes'][-1]['node_id'] = e.nodes[0]
    elif invalid == 'wrong-pin': appended['nodes'][-1]['node_version'] = 7
    else:
        appended['nodes'].extend({**appended['nodes'][-1], 'node_id': f'excess-{i}'} for i in range(98))
    before = e.store.read(e.nid, e.scope)
    with pytest.raises((StaleSourceError, ValidationError)): save(e, row, appended)
    assert e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize('barrier', ['owner', 'scope', 'archive', 'reauthorize'])
def test_membership_preserves_original_authority_and_atomicity(membership_env, barrier):
    e = membership_env; row = create(e); appended = append_original(e, row)
    if barrier == 'archive': row = e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'archive'})
    before = e.store.read(e.nid, e.scope)
    calls = []
    def revoke():
        calls.append(True)
        if len(calls) == 3: raise HTTPException(403, 'revoked after mutation')
    with pytest.raises((FileNotFoundError, ValueError, HTTPException)):
        e.service.save(e.nid, {**e.scope, 'branch_id': 'other'} if barrier == 'scope' else e.scope, 'other' if barrier == 'owner' else 'author', row['id'], {'expected_version': row['version'], 'spec': appended}, reauthorize=revoke if barrier == 'reauthorize' else lambda: None)
    assert e.store.read(e.nid, e.scope) == before
    if barrier == 'reauthorize': assert len(calls) == 3


def mounted_subset(e, headers=None, linked=True):
    headers = headers or {}; plan = e.base + '/planning'
    graph = checked(e.client.post(plan + '/graphs', headers=headers, json={'title': 'Membership graph', 'links': {'chapter_ids': [e.chapter['id']]} if linked else {}}), 201)
    candidate = checked(e.client.post(plan + '/nodes', headers=headers, json={'graph_id': graph['id'], 'parent_id': graph['root_node_id'], 'level': 'VOLUME', 'title': 'New original ending'}), 201)
    spec = {'title': 'Membership subset', 'graph_id': graph['id'], 'graph_version': graph['version'], 'entry_node_id': graph['root_node_id'], 'nodes': [{'node_id': graph['root_node_id'], 'node_version': 1, 'title': 'Old ending', 'dialogue': 'MEMBERSHIP_PRIVATE_SENTINEL', 'ending': 'Home'}]}
    row = checked(e.client.post(e.base + '/interactive-stories', headers=headers, json={'spec': spec}), 201)
    appended = deepcopy(row['spec']); appended['nodes'].append(StoryNode(node_id=candidate['id'], node_version=candidate['version'], title=candidate['title']).model_dump())
    return row, appended


@pytest.mark.parametrize('mounted', ['file'], indirect=True)
def test_mounted_membership_flag_revocation_rolls_back_original_save(mounted, monkeypatch):
    e = mounted; row, appended = mounted_subset(e); before = e.store.read(e.nid, e.scope)
    service = e.experimental.interactive_story_service; original = service._current; calls = []
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs); calls.append(True)
        if len(calls) == 2: monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        return result
    monkeypatch.setattr(service, '_current', revoke)
    response = e.client.put(e.base + '/interactive-stories/' + row['id'], json={'expected_version': row['version'], 'spec': appended})
    assert response.status_code == 404 and e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize('mounted', ['file'], indirect=True)
def test_mounted_membership_stays_private_and_scoped(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); row, appended = mounted_subset(e, e.headers, linked=False)
    url = e.base + '/interactive-stories/' + row['id']; body = {'expected_version': row['version'], 'spec': appended}
    before = e.store.read(e.nid, e.scope)
    assert e.client.put(url, headers=e.viewer_headers, json=body).status_code == 403
    assert e.client.put(url, headers={**e.headers, 'X-Branch-ID': e.other_branch}, json=body).status_code in {403, 404}
    assert e.client.put(url, headers={'X-Session-Token': 'forged', 'X-Branch-ID': e.branch}, json=body).status_code in {401, 403}
    assert e.store.read(e.nid, e.scope) == before
    saved = checked(e.client.put(url, headers=e.headers, json=body))
    assert saved['spec'] == appended and saved['version'] == 2
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.put(url, headers=e.headers, json={'expected_version': 2, 'spec': appended}).status_code == 403
    denied = e.client.get(url, headers=e.headers)
    assert denied.status_code == 403 and 'MEMBERSHIP_PRIVATE_SENTINEL' not in denied.text
