"""Actual frontend helper -> original File definition save/history/reopen.

Only the editing helper executes in Node. No workflow, model or provider executes.
"""
import json
import os
from pathlib import Path
import subprocess

import pytest

from app.experimental.declarative_agents import DeclarativeAgentsService, default_definition
from app.experimental.store import ExperimentalStore
from test_r5_declarative_templates import env, storage_env

ROOT = Path(__file__).resolve().parents[1]
NODE = r"""
import { readFileSync, realpathSync } from 'node:fs';
import { createRequire } from 'node:module';
const { transform } = createRequire(realpathSync('frontend/node_modules/vite/package.json'))('esbuild');
const input = JSON.parse(readFileSync(0, 'utf8'));
const source = readFileSync('frontend/src/experimental/workflowGraphEditing.ts', 'utf8');
const { code } = await transform(source, { loader: 'ts', format: 'esm', target: 'es2022' });
const { previewCheckpointEdit } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
const result = previewCheckpointEdit(input.definition, input.edit);
process.stdout.write(JSON.stringify({ input, result }));
"""


def helper(value, operation):
    result = subprocess.run(['node', '--input-type=module', '-e', NODE], cwd=ROOT,
                            input=json.dumps({'definition': value, 'edit': operation}, ensure_ascii=False),
                            capture_output=True, text=True, timeout=20, check=True)
    assert result.stderr == ''
    return json.loads(result.stdout)


@pytest.mark.parametrize('topology', ['linear', 'branch'])
def test_exact_helper_definition_saves_restarts_and_removes_without_execution(env, topology, tmp_path):
    e = env
    value = default_definition()
    value['agent'].update(title='检查点依赖编辑', purpose='保留原用途', role_prompt='保留作者角色声明。')
    if topology == 'branch':
        value['nodes'].insert(1, {'id': 'side', 'type': 'checkpoint', 'name': '保留的旁路检查点'})
        value['edges'][0:0] = [{'source': 'prepare', 'target': 'side'}, {'source': 'side', 'target': 'review'}]
    original = e.agents.save(e.ctx, None, {'definition': value})
    before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    manuscript_before = e.chapters.get(e.cid)
    inserted = helper(original['definition'], {'kind': 'insert', 'source': 'prepare', 'target': 'review'})
    assert inserted['input']['definition'] == original['definition']
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    assert inserted['result']['definition']['agent'] == original['definition']['agent']
    validation = e.agents.preflight(e.ctx, inserted['result']['definition'])
    assert validation['valid'] and not validation['model_called'] and validation['external_calls'] == 0
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    saved = e.agents.save(e.ctx, original['id'], {'expected_version': 1, 'definition': inserted['result']['definition']})
    assert saved['version'] == 2 and saved['definition'] == inserted['result']['definition']
    fresh = DeclarativeAgentsService(ExperimentalStore(e.store.root, e.store.backend, e.store.database_url), e.novels, e.chapters, sources=e.sources)
    reopened = next(row for row in fresh.definitions(e.ctx)['items'] if row['id'] == saved['id'])
    assert reopened == {key: val for key, val in saved.items() if key != 'history'}
    assert fresh.definition_history_version(e.ctx, saved['id'], 1)['definition'] == original['definition']
    removed = helper(reopened['definition'], {'kind': 'remove', 'id': inserted['result']['nodeId']})
    assert removed['result']['definition'] == original['definition']
    final = fresh.save(e.ctx, saved['id'], {'expected_version': 2, 'definition': removed['result']['definition']})
    again = DeclarativeAgentsService(ExperimentalStore(e.store.root, e.store.backend, e.store.database_url), e.novels, e.chapters, sources=e.sources)
    assert next(row for row in again.definitions(e.ctx)['items'] if row['id'] == saved['id'])['definition'] == original['definition']
    assert final['version'] == 3 and final['definition_digest'] == original['definition_digest']
    assert again.definition_history_version(e.ctx, saved['id'], 2)['definition'] == inserted['result']['definition']
    assert again.runs(e.ctx)['items'] == [] and e.chapters.get(e.cid) == manuscript_before
    evidence = {'topology': topology, 'helper_executed': True, 'workflow_executed': False,
                'insert': inserted, 'remove': removed, 'versions': [1, 2, 3],
                'original_digest': original['definition_digest'], 'inserted_digest': saved['definition_digest'],
                'final_digest': final['definition_digest'], 'reopened_definition': reopened['definition']}
    folder = Path(os.getenv('STUDIO_CHECKPOINT_EVIDENCE', str(tmp_path / 'checkpoint-evidence')))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{topology}-helper-save-reopen.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
