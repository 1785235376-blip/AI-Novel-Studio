// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { InteractiveStoryPanel } from './InteractiveStoryPanel';
import type { InteractiveStory, StoryArtifactEvidence, StoryCatalog, StoryExportTarget, StoryExportTargets, StoryPlay } from './interactiveStoryClient';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const client = (id = 'n') => experimentalClient(id, { sessionToken: 'session', scope: { branchId: 'branch' } as any });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const analysis = { issues: [], warnings: [], endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }], states_checked: 2, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 4, can_review: true };
function makeStory(status: InteractiveStory['status'] = 'APPROVED', version = 1): InteractiveStory {
  return { id: 'story', version, status, stale: false, content_withheld: false, analysis, spec: { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 4,
    variables: [{ name: 'trusted', type: 'bool', initial: true, minimum: 0, maximum: 100 }], graph_record_ids: [], nodes: [
      { node_id: 'gate', node_version: 1, title: '城门', dialogue: '原对白🙂é', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '', choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: {} }] },
      { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
    ] } };
}
const catalog: StoryCatalog = { graphs: [{ id: 'graph', version: 1, title: '原规划图', truncated: false, nodes: makeStory().spec!.nodes }], characters: [{ id: 'alice', name: 'Alice' }], assets: [], graph_records: [], target_runtime: 'NOT_RUN' };
const caps = () => Object.fromEntries(['conditions', 'bool_variables', 'int_variables', 'assignment', 'dialogue', 'choices', 'endings', 'loops', 'step_cap', 'save', 'restore', 'unicode', 'media'].map(key => [key, { supported: true, lossy: false, note: '' }]));
const artifactEvidence = (patch: Partial<StoryArtifactEvidence> = {}): StoryArtifactEvidence => ({
  status: 'UNVERIFIED',
  levels: { SOURCE_IMPLEMENTED: 'NOT_RUN', SCHEMA_VALIDATED: 'NOT_RUN', FIXTURE_TESTED: 'NOT_RUN', GENERATED_ARTIFACT_VALIDATED: 'PASS', TARGET_RUNTIME_EXECUTED: 'NOT_RUN', SAVE_RESTORE_VERIFIED: 'NOT_RUN', WINDOWS_USABILITY_VERIFIED: 'NOT_RUN' },
  binding: null, matched_receipt: null, stale_receipts: [], checked_receipts: 0,
  policy: 'ONLY_RECEIPTS_BOUND_TO_THIS_EXACT_ARTIFACT_CAN_SET_RUNTIME_LEVELS',
  reason: 'no verification receipt exists for this artifact', ...patch,
});
const target = (): StoryExportTarget => ({
  target_id: 'GODOT_4_RUNTIME_PROJECT_V1', display_name: 'Godot 4 运行时项目', kind: 'RUNNABLE_PROJECT', format_version: 'godot-runtime-project-1', adapter_revision: 1, engine: null,
  capabilities: caps(), losses: [], runtime_requirements: ['Godot 4 项目'], launch_instructions: '解压后用 Godot 打开项目目录。', integration_notes: [], evidence: { SOURCE_IMPLEMENTED: 'PASS' },
  compatibility: { target_id: 'GODOT_4_RUNTIME_PROJECT_V1', can_export: true, capabilities: caps(), losses: [], issues: [], notes: [] },
  engine_probe: { status: 'NOT_REQUIRED', detected: false, executable: null, version: null, version_ok: false, detail: '无需外部引擎。', declared: null },
  export_ready: true, runtime_claim: 'UNVERIFIED', historical_evidence: { SOURCE_IMPLEMENTED: 'PASS' }, artifact_evidence: artifactEvidence(), artifact_evidence_status: 'UNVERIFIED',
});
const targetsData = (): StoryExportTargets => ({
  schema: 'poemseed-interactive-export-targets/1', contract_schema: 'poemseed-interactive-export-contract/1', contract_version: 1, contract: {},
  adaptation: { id: 'story', version: 1, status: 'APPROVED' },
  story: { title: '合成互动故事', entry_node_id: 'gate', max_steps: 4, nodes: 2, variables: 1, endings: 1, spec_digest: 'a'.repeat(64), source_digest: 'b'.repeat(64) },
  witness: [{ node_id: 'end', ending: '回家', choices: ['home'] }], analysis: { can_review: true, analysis_complete: true, issues: [], warnings: [], states_checked: 2 },
  targets: [target()], media_manifest: [], can_export_any: true, target_runtime_policy: 'INDEPENDENT_EVIDENCE_LEVELS; GENERATION_IS_NOT_RUNTIME; MISSING_ENGINE_BLOCKS_RUNTIME_NOT_SAFE_EXPORT', model_called: false,
});
function backend(options: { story?: () => InteractiveStory; targets?: (url: string) => Response | undefined } = {}) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const row = options.story?.() ?? makeStory();
    const special = options.targets?.(url); if (special) return special;
    if (url.endsWith('/catalog')) return reply(catalog);
    if (init.method === 'GET') return reply(url.endsWith('/story') ? row : { items: [row], truncated: false });
    const body = JSON.parse(String(init.body));
    if (url.endsWith('/export-targets')) return reply(targetsData());
    if (url.endsWith('/preview')) {
      const node = row.spec!.nodes[body.choices.length ? 1 : 0];
      const play: StoryPlay = { node, character_name: body.choices.length ? undefined : 'Alice', choices: body.choices.length ? [] : [{ id: 'home', label: '回家', enabled: true }], variables: { trusted: true }, steps: body.choices.length, max_steps: 4, path: body.choices, status: body.choices.length ? 'ENDING' : 'PLAYING' };
      return reply(play);
    }
    return reply(row);
  });
}
const selectStory = async () => fireEvent.click(await screen.findByRole('button', { name: /合成互动故事 · v/ }));
const playToEnding = async () => {
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  fireEvent.click(await screen.findByRole('button', { name: /^回家$/ }));
  await screen.findByText('结局：回家');
};

it('does not switch the editor node while a Chinese IME composition is in progress', async () => {
  vi.stubGlobal('fetch', backend()); render(<InteractiveStoryPanel client={client()} />); await selectStory();
  await playToEnding();
  const dialogue = screen.getByLabelText('对白或叙述');
  fireEvent.compositionStart(dialogue);
  fireEvent.click(screen.getByRole('button', { name: '定位回编辑节点 终章' }));
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('0');
  fireEvent.compositionEnd(dialogue);
  fireEvent.click(screen.getByRole('button', { name: '定位回编辑节点 终章' }));
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('1');
  // Locating only switches the editor node: no draft was created or modified.
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('抵达');
  expect((screen.getByRole('button', { name: '保存互动草稿' }) as HTMLButtonElement).disabled).toBe(true);
});

it('keeps the existing play state across unrelated target reads', async () => {
  vi.stubGlobal('fetch', backend()); render(<InteractiveStoryPanel client={client()} />); await selectStory();
  await playToEnding();
  const before = screen.getByLabelText('互动故事播放').textContent;
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  await screen.findByLabelText('导出目标列表');
  expect(screen.getByLabelText('互动故事播放').textContent).toBe(before);
});

it('drops loaded target and play state when a newer saved revision replaces the source', async () => {
  let current = makeStory();
  vi.stubGlobal('fetch', backend({ story: () => current })); render(<InteractiveStoryPanel client={client()} />); await selectStory();
  await playToEnding();
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  await screen.findByLabelText('导出目标列表');
  current = makeStory('APPROVED', 2);
  fireEvent.click(screen.getByRole('button', { name: '核对当前互动版本' }));
  await waitFor(() => expect(screen.queryByLabelText('导出目标列表')).toBeNull());
  expect(screen.queryByLabelText('互动故事播放')).toBeNull();
  expect(screen.getAllByText('APPROVED · v2').length).toBeGreaterThan(0);
});

it('hides target data when the client scope changes and keeps late responses out', async () => {
  let finishTargets: (value: Response) => void = () => {};
  const fetch = backend({ targets: url => url.endsWith('/export-targets') ? new Promise<Response>(resolve => { finishTargets = resolve; }) as unknown as Response : undefined });
  vi.stubGlobal('fetch', fetch);
  const view = render(<InteractiveStoryPanel client={client()} />); await selectStory();
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  view.rerender(<InteractiveStoryPanel client={client('other')} />);
  await act(async () => finishTargets(reply(targetsData())));
  expect(screen.queryByLabelText('导出目标列表')).toBeNull();
  expect(screen.queryByLabelText('导出目标 GODOT_4_RUNTIME_PROJECT_V1')).toBeNull();
});
