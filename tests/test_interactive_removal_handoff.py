"""Removal uses the original File save/restart/analysis/review/export owner unchanged."""
import base64
from copy import deepcopy
import io
import json
import zipfile

import pytest

from app.config import Settings
from app.experimental.interactive_story import InteractiveStoryService, parse_condition
from app.experimental.planning import PlanningService
from app.experimental.store import ExperimentalStore
from app.experimental.story_graph import StoryGraphService
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.services.asset_library_service import AssetLibraryService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_interactive_membership_handoff import membership_env, create, append_original, save, approve

pytestmark = pytest.mark.file_backend_only


def test_remove_unused_save_full_file_restart_analysis_review_export_preserves_sources(membership_env, tmp_path):
    e = membership_env
    original_sources = deepcopy((e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id'])))
    initial = create(e)
    expanded = append_original(e, initial)
    expanded['nodes'][-1].update(dialogue='待移除🙂é', choices=[{'id': 'outgoing', 'label': '返回', 'target': e.nodes[1], 'condition': '', 'assignments': {}}])
    before = save(e, initial, expanded)
    unused_id = e.nodes[2]
    assert unused_id != before['spec']['entry_node_id']
    assert not any(choice['target'] == unused_id for node in before['spec']['nodes'] for choice in node['choices'])
    reduced = deepcopy(before['spec'])
    reduced['nodes'] = [node for node in reduced['nodes'] if node['node_id'] != unused_id]
    saved = save(e, before, reduced)
    assert saved['version'] == before['version'] + 1 and saved['status'] == 'DRAFT'
    assert saved['spec'] == initial['spec']

    # Reconstruct all File repositories and services rather than retaining an in-memory store.
    config = Settings(storage_backend='file', database_url='', novel_data=tmp_path, mock_provider=True, enable_cloud=False)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    e.chapters, e.novels = ChapterService(bundle.chapters), NovelService(bundle.novels, bundle.chapters)
    e.store = ExperimentalStore(tmp_path, 'file', '')
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.graph_service = StoryGraphService(e.store, e.novels, e.chapters)
    e.assets = AssetLibraryService(tmp_path)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.graph_service, e.assets)
    reopened = e.service.story(e.nid, e.scope, 'author', saved['id'])
    assert reopened['spec'] == reduced and reopened['version'] == saved['version']
    assert reopened['analysis']['can_review'] and reopened['analysis']['analysis_complete']
    assert not any(issue.get('node_id') == unused_id for issue in reopened['analysis']['issues'] + reopened['analysis']['warnings'])
    history = e.service.revisions(e.nid, e.scope, 'author', saved['id'], {'expected_version': reopened['version']})
    assert any(revision['spec'] == expanded for revision in history['items'])
    play = e.service.preview(e.nid, e.scope, 'author', saved['id'], {'expected_version': reopened['version'], 'choices': ['home']})
    assert play['status'] == 'ENDING' and play['node']['ending'] == 'Home' and play['variables'] == {'trusted': False}
    approved = approve(e, reopened)
    preview = e.service.export_preview(e.nid, e.scope, 'author', saved['id'], {'expected_version': approved['version']})
    assert preview['can_export']
    exported = e.service.export(e.nid, e.scope, 'author', saved['id'], {'expected_version': approved['version'], 'preview_digest': preview['preview_digest']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported['content_base64']))) as archive:
        neutral = json.loads(archive.read(f"interactive-story-{saved['id']}/story.json"))
        expected = deepcopy(reduced)
        for node in expected['nodes']:
            for choice in node['choices']:
                choice['condition_tree'] = parse_condition(choice['condition'])
        assert neutral['spec'] == expected
        assert neutral['source_versions'] == {e.cid: original_sources[0]['version']}
        assert neutral['adaptation_version'] == approved['version']
    assert not exported['published'] and exported['target_runtime'] == 'NOT_RUN'
    assert (e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id'])) == original_sources
    # Re-adding still goes through the original candidate flow, never archived authored content.
    readded = append_original(e, approved)
    assert readded['nodes'][-1]['dialogue'] == '' and readded['nodes'][-1]['choices'] == []
    assert readded['nodes'][-1]['node_id'] == unused_id and readded['nodes'][-1]['node_version'] == 1


def test_removal_preserves_original_cas_and_atomic_reauthorization(membership_env):
    e = membership_env
    initial = create(e); expanded = save(e, initial, append_original(e, initial))
    reduced = deepcopy(expanded['spec']); reduced['nodes'].pop()
    saved = save(e, expanded, reduced)
    snapshot = e.store.read(e.nid, e.scope)
    with pytest.raises(CapabilityVersionConflict):
        save(e, expanded, reduced)
    assert e.store.read(e.nid, e.scope) == snapshot
    def revoke():
        raise PermissionError('authorization revoked')
    with pytest.raises(PermissionError):
        save(e, saved, append_original(e, saved), reauthorize=revoke)
    assert e.store.read(e.nid, e.scope) == snapshot
