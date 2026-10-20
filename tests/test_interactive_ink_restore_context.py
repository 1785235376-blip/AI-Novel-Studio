"""F2 regression: the DELIVERED Ink restore entry requires complete context.

Hermia's independent counterexample (dsh-trust-6c857-review) showed that the
shipped helper accepted a save into a different compiled artifact when expected
was omitted/empty/partial. These checks exercise the delivered helper bytes and
prove that incomplete context fails before Ink state is loaded.
"""
import base64
import json
from pathlib import Path

from test_r4_revision_intelligence import revision_env
from test_r5_interactive_story import approve, create, interactive_env
from app.experimental.interactive_export_contract import read_zip_safely
from test_interactive_ink_current_artifact import _export_current, _runtime_env


# ---------------------------------------------------------------------------
# F2: the DELIVERED restore entry requires a complete trusted current-artifact
# context; missing/empty/partial/malformed context must fail before LoadJson.
# ---------------------------------------------------------------------------
def test_delivered_helper_requires_complete_restore_context(interactive_env, tmp_path):
    node, _root = _runtime_env()
    import subprocess
    e = interactive_env
    row = approve(e, create(e))
    value = {'expected_version': row['version']}
    _preview, out = _export_current(e, row, value)
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(base64.b64decode(out['content_base64']), prefix)
    helper_path = tmp_path / 'delivered-save_envelope.mjs'
    helper_path.write_bytes(files['ink/player/save_envelope.mjs'])
    script = tmp_path / 'context-matrix.mjs'
    script.write_text(r'''
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
const helper = await import(pathToFileURL(process.argv[2]).href);
const artifactA = JSON.stringify({ inkVersion: 21, root: ['done', null], text: 'A' });
const artifactB = JSON.stringify({ inkVersion: 21, root: ['done', null], text: 'B' });
const sha = (value) => createHash('sha256').update(value).digest('hex');
const state = JSON.stringify({ callstack: { threads: [] }, variablesState: { ans_var_0: true } });
function makeStory() {
  const story = { loadJsonCalls: 0, state: { ToJson: () => state, LoadJson: () => { story.loadJsonCalls += 1; } },
    variablesState: { $: (name) => JSON.parse(state).variablesState[name] } };
  return story;
}
const created = helper.createSaveEnvelope({ story: makeStory(), storyId: 'story-1', revision: 3,
  compiledArtifactSha256: sha(artifactA), targetFormatVersion: 'ink-current-artifact-2',
  runtime: { name: 'inkjs', version: '2.3.2', format: 'ink-current-artifact-2' },
  steps: ['first'], path: ['first'], savedAtStep: 1, variables: { ans_var_0: true }, variablesChangedBeforeSave: true });
const complete = { storyId: 'story-1', revision: 3, compiledArtifactSha256: sha(artifactA),
  targetFormatVersion: 'ink-current-artifact-2', runtime: { name: 'inkjs', version: '2.3.2', format: 'ink-current-artifact-2' } };
const results = [];
function attempt(name, input) {
  const story = makeStory();
  try { helper.loadSaveEnvelope({ bytes: created.bytes, story, ...input }); results.push({ name, accepted: true, loadJsonCalls: story.loadJsonCalls }); }
  catch (error) { results.push({ name, accepted: false, code: error.code, loadJsonCalls: story.loadJsonCalls }); }
}
attempt('omitted_expected', {});
attempt('empty_expected', { expected: {} });
for (const field of ['storyId', 'revision', 'compiledArtifactSha256', 'targetFormatVersion', 'runtime']) {
  const partial = { ...complete }; delete partial[field];
  attempt('missing_' + field, { expected: partial });
}
attempt('partial_story_only', { expected: { storyId: complete.storyId } });
attempt('bad_revision', { expected: { ...complete, revision: 0 } });
attempt('bad_digest', { expected: { ...complete, compiledArtifactSha256: 'ABC' } });
attempt('runtime_missing_format', { expected: { ...complete, runtime: { name: 'inkjs', version: '2.3.2' } } });
attempt('cross_artifact_with_complete_context', { expected: { ...complete, compiledArtifactSha256: sha(artifactB) } });
attempt('valid_complete_context', { expected: complete });
let createWithoutFormat = null;
try { helper.createSaveEnvelope({ story: makeStory(), storyId: 'story-1', revision: 3, compiledArtifactSha256: sha(artifactA),
  targetFormatVersion: 'ink-current-artifact-2', runtime: { name: 'inkjs', version: '2.3.2' }, variables: {} }); }
catch (error) { createWithoutFormat = error.code; }
const migrated = helper.migrateLegacySaveEnvelope({ legacyStateJson: state, storyId: 'story-1', revision: 3,
  compiledArtifactSha256: sha(artifactA), targetFormatVersion: 'ink-current-artifact-2',
  runtime: { name: 'inkjs', version: '2.3.2', format: 'ink-current-artifact-2' }, path: ['first'], variables: { ans_var_0: true } });
const migratedEnvelope = JSON.parse(migrated.bytes);
process.stdout.write(JSON.stringify({ results, create_without_format: createWithoutFormat,
  migrated_from: migratedEnvelope.save.migrated_from, migration_note: migratedEnvelope.save.migration_note,
  describe: helper.describeSaveEnvelope() }));
''', encoding='utf-8')
    completed = subprocess.run([node, str(script), str(helper_path)], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=120, check=False)
    assert completed.returncode == 0, completed.stderr[-3000:]
    payload = json.loads(completed.stdout)
    outcomes = {item['name']: item for item in payload['results']}
    assert outcomes['omitted_expected']['code'] == 'SAVE_ENVELOPE_CONTEXT_REQUIRED'
    assert outcomes['empty_expected']['code'] == 'SAVE_ENVELOPE_CONTEXT_INVALID'
    for field in ('storyId', 'revision', 'compiledArtifactSha256', 'targetFormatVersion', 'runtime'):
        assert outcomes['missing_' + field]['code'] == 'SAVE_ENVELOPE_CONTEXT_INVALID', field
    for name in ('partial_story_only', 'bad_revision', 'bad_digest', 'runtime_missing_format'):
        assert outcomes[name]['code'] == 'SAVE_ENVELOPE_CONTEXT_INVALID', name
        assert outcomes[name]['loadJsonCalls'] == 0, name
    assert outcomes['cross_artifact_with_complete_context']['code'] == 'SAVE_ENVELOPE_ARTIFACT_MISMATCH'
    assert outcomes['cross_artifact_with_complete_context']['loadJsonCalls'] == 0
    assert outcomes['valid_complete_context'] == {'name': 'valid_complete_context', 'accepted': True, 'loadJsonCalls': 1}
    assert payload['create_without_format'] == 'SAVE_ENVELOPE_SCHEMA_INVALID'
    assert payload['migrated_from'] == 'UNBOUND_LEGACY_INK_STATE'
    assert 'never as system-verified execution' in payload['migration_note']
    assert payload['describe']['restore_context_required'] is True
    assert payload['describe']['restore_context_errors'] == ['SAVE_ENVELOPE_CONTEXT_REQUIRED', 'SAVE_ENVELOPE_CONTEXT_INVALID']
