"""Bounded DSH/df07 combination checks; original File owners, no engines or models."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_public_build_profile import ROOT, build
from test_public_build_c40_closure import REVIEWED_MODULES
from test_interactive_export_evidence_binding import env, revision_env, make_approved, export, receipt, record, GODOT


INK_RESOURCES = {
    'app/experimental/interactive_targets/ink/player/save_envelope.mjs',
    'app/experimental/interactive_targets/ink/player/save-envelope.schema.json',
}


def test_combined_public_payload_keeps_both_closures_and_real_ink_resources(tmp_path):
    manifest = build.load_manifest(ROOT / 'packaging/public-build.json')
    source = build.check_source(ROOT, manifest)
    auxiliary = build.check_docker_inputs(ROOT, manifest)
    assert len(source) == 611 and len(auxiliary) == 43
    assert REVIEWED_MODULES | INK_RESOURCES <= set(source)
    stage = tmp_path / 'public-stage'
    receipt_value = build.stage_public(ROOT, stage, manifest, docker=True)
    assert len(receipt_value['files']) == 654
    assert not (stage / build.PRIVATE).exists()
    for name in INK_RESOURCES:
        assert (stage / name).read_bytes() == (ROOT / name).read_bytes()
    code = r'''
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
import app.creative.graph as graph
import app.experimental.interactive_story as story
from app.experimental.interactive_targets.ink import current_artifact,runtime
from app.experimental.interactive_targets.godot import __name__ as godot_name
from app.experimental.interactive_targets.renpy import project as renpy
for module in [graph,story,current_artifact,runtime,renpy]:
    assert pathlib.Path(module.__file__).resolve().is_relative_to(root),module.__file__
description=runtime.save_envelope_document()
assert description['restore_context']['required'] is True
assert description['restore_context']['policy'].endswith('NEVER_FROM_SAVE')
assert runtime.save_envelope_module_sha256()==hashlib.sha256(runtime.player_asset_bytes('save_envelope.mjs')).hexdigest()
assert runtime.save_envelope_schema_sha256()==hashlib.sha256(runtime.player_asset_bytes('save-envelope.schema.json')).hexdigest()
print(json.dumps({'staged_imports':True,'ink_resources':True,'restore_context_required':True}))
'''
    process_env = {**os.environ, 'PYTHONPATH': str(stage), 'PYTHONDONTWRITEBYTECODE': '1',
                   'PROJECT_ROOT': str(stage), 'NOVEL_DATA_PATH': str(tmp_path / 'runtime'),
                   'LOCALAPPDATA': str(tmp_path / 'localapp'), 'STORAGE_BACKEND': 'file', 'ENABLE_CLOUD': 'false'}
    completed = subprocess.run([sys.executable, '-B', '-c', code, str(stage)], cwd=stage,
                               env=process_env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert completed.returncode == 0, completed.stderr[-4000:]
    assert json.loads(completed.stdout)['staged_imports']
    # The import must not alter the reviewed staged source payload.
    assert build.verify_stage(ROOT, stage, manifest, docker=True) == receipt_value


def test_same_file_scope_keeps_creative_graph_and_interactive_claim_owners_separate(env, monkeypatch):
    from app.creative.graph import CreativeGraphService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.common import new_row
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.interactive_story import InteractiveStoryService
    from app.experimental.planning import PlanningService
    from app.experimental.story_graph import StoryGraphService
    from app.experimental.store import ExperimentalStore

    e = env
    story = make_approved(e)
    original_sources = deepcopy((e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id'])))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', os.getenv('EXPERIMENTAL_FEATURES', '') +
                       ',narrative_production_v2,asset_lineage_v2')
    media = MediaService(e.store, e.novels, e.chapters, e.assets)
    lineage = ProductionLineageService(e.store, e.novels, e.chapters, e.assets, media)
    workspace = IndependentWorkspaceService(CreativeService(e.store, e.novels, e.chapters), e.assets, lineage)
    workspace.activate(e.nid, e.scope, 'author')
    graphs = CreativeGraphService(workspace.store, workspace)
    definition = {'schema_version': 1, 'title': 'Independent original Graph', 'nodes': [
        {'id': 'AuthorText', 'definition_id': 'text_input', 'parameters': {'text': '中文图草稿'}}], 'edges': []}
    graph = graphs.create(e.nid, e.scope, 'author', {'request_id': 'combined-graph', 'definition': definition})
    definition['title'] = 'Explicit Graph save'
    graph = graphs.save(e.nid, e.scope, 'author', graph['id'],
                        {'expected_version': graph['version'], 'definition': definition})
    assert original_sources == (e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id']))
    out = export(e, story)
    claim = receipt(e, story, out)
    with e.store.transaction(e.nid, e.scope) as document:
        legacy = new_row(e.nid, e.scope, 'author', {'status': 'RECORDED',
            'export_record_id': out['export_record_id'], 'story_id': story['id'], 'revision': story['version'],
            'target_id': GODOT, 'artifact_sha256': out['sha256'], 'files_digest': out['files_digest'], 'receipt': claim})
        document['collections'].setdefault(e.service.EVIDENCE_COLLECTION, {})[legacy['id']] = legacy
    before = deepcopy(e.store.read(e.nid, e.scope))
    replay = record(e, story, claim)
    assert replay['status'] == 'IDEMPOTENT' and replay['evidence_record_id'] == legacy['id']
    assert replay['system_verification'] == 'NOT_PERFORMED' and replay['runtime_claim'] == 'UNVERIFIED'
    assert replay['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert e.store.read(e.nid, e.scope) == before
    assert graphs.get(e.nid, e.scope, 'author', graph['id']) == graph
    assert graphs.runs(e.nid, e.scope, 'author', graph['id'])['items'] == []
    def revoked():
        raise PermissionError('combined revoke')
    with pytest.raises(PermissionError, match='combined revoke'):
        graphs.save(e.nid, e.scope, 'author', graph['id'],
                    {'expected_version': graph['version'], 'definition': definition}, guard=revoked)
    assert e.store.read(e.nid, e.scope) == before
    # Reopen original File stores: both authorities must retain their own records.
    fresh = ExperimentalStore(e.store.root, e.backend, '')
    restarted = InteractiveStoryService(fresh, e.novels, e.chapters,
        PlanningService(fresh, e.novels, e.chapters), StoryGraphService(fresh, e.novels, e.chapters), e.assets)
    assert restarted.story(e.nid, e.scope, 'author', story['id'])['version'] == story['version']
    assert fresh.read(e.nid, e.scope)['collections'][graphs.GRAPHS][graph['id']]['version'] == graph['version']
