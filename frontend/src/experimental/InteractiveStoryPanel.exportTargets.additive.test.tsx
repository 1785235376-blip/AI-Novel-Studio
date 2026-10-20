// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { InteractiveStoryPanel } from './InteractiveStoryPanel';
import type { InteractiveStory, StoryArtifactEvidence, StoryCapability, StoryCatalog, StoryExportTarget, StoryExportTargets } from './interactiveStoryClient';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const client = (id = 'n') => experimentalClient(id, { sessionToken: 'session', scope: { branchId: 'branch' } as any });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const analysis = { issues: [], warnings: [], endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }], states_checked: 2, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 4, can_review: true };
function makeStory(status: InteractiveStory['status'] = 'APPROVED'): InteractiveStory {
  return { id: 'story', version: 1, status, stale: false, content_withheld: false, analysis, spec: { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 4,
    variables: [{ name: 'trusted', type: 'bool', initial: true, minimum: 0, maximum: 100 }], graph_record_ids: [], nodes: [
      { node_id: 'gate', node_version: 1, title: '城门', dialogue: '原对白🙂é', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '', choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: {} }] },
      { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
    ] } };
}
const catalog: StoryCatalog = { graphs: [{ id: 'graph', version: 1, title: '原规划图', truncated: false, nodes: makeStory().spec!.nodes }], characters: [{ id: 'alice', name: 'Alice' }], assets: [], graph_records: [], target_runtime: 'NOT_RUN' };
const caps = (overrides: Record<string, Partial<StoryCapability>> = {}): Record<string, StoryCapability> => {
  const result: Record<string, StoryCapability> = {};
  for (const key of ['conditions', 'bool_variables', 'int_variables', 'assignment', 'dialogue', 'choices', 'endings', 'loops', 'step_cap', 'save', 'restore', 'unicode', 'media']) result[key] = { supported: true, lossy: false, note: '' };
  for (const [key, value] of Object.entries(overrides)) result[key] = { supported: true, lossy: false, note: '', ...value };
  return result;
};
const artifactEvidence = (patch: Partial<StoryArtifactEvidence> = {}): StoryArtifactEvidence => ({
  status: 'UNVERIFIED',
  levels: { SOURCE_IMPLEMENTED: 'NOT_RUN', SCHEMA_VALIDATED: 'NOT_RUN', FIXTURE_TESTED: 'NOT_RUN', GENERATED_ARTIFACT_VALIDATED: 'PASS', TARGET_RUNTIME_EXECUTED: 'NOT_RUN', SAVE_RESTORE_VERIFIED: 'NOT_RUN', WINDOWS_USABILITY_VERIFIED: 'NOT_RUN' },
  binding: null, matched_receipt: null, stale_receipts: [], checked_receipts: 0,
  policy: 'ONLY_RECEIPTS_BOUND_TO_THIS_EXACT_ARTIFACT_CAN_SET_RUNTIME_LEVELS',
  reason: 'no verification receipt exists for this artifact', ...patch,
});
const godot = (): StoryExportTarget => ({
  target_id: 'GODOT_4_RUNTIME_PROJECT_V1', display_name: 'Godot 4 运行时项目', kind: 'RUNNABLE_PROJECT', format_version: 'godot-runtime-project-1', adapter_revision: 1,
  engine: { name: 'Godot', minimum_version: '4.0', executables: ['godot'], version_args: ['--version'], env_override: 'POEMSEED_GODOT_BIN', search_hints: [], gui: false, note: '' },
  capabilities: caps(), losses: [], runtime_requirements: ['Godot 4 项目'], launch_instructions: '解压后用 Godot 打开项目目录。', integration_notes: [], evidence: { SOURCE_IMPLEMENTED: 'PASS' },
  compatibility: { target_id: 'GODOT_4_RUNTIME_PROJECT_V1', can_export: true, capabilities: caps(), losses: ['NO_SAVE_OR_RESTORE'], issues: [], notes: [] },
  engine_probe: { status: 'READY', detected: true, executable: 'C:/godot.exe', version: '4.7.0', version_ok: true, detail: 'Godot 4.7.0 detected.', declared: { name: 'Godot', minimum_version: '4.0', gui: false } },
  export_ready: true, runtime_claim: 'UNVERIFIED', historical_evidence: { SOURCE_IMPLEMENTED: 'PASS', TARGET_RUNTIME_EXECUTED: 'PASS', SAVE_RESTORE_VERIFIED: 'PASS' }, artifact_evidence: artifactEvidence(), artifact_evidence_status: 'UNVERIFIED',
});
const legacy = (): StoryExportTarget => ({ ...godot(), target_id: 'GODOT_4_DATA_ADAPTER', display_name: 'Godot 4 数据适配器（旧）', kind: 'DATA_ONLY_ADAPTER', format_version: 'godot-data-adapter-1', engine: null,
  engine_probe: { status: 'NOT_REQUIRED', detected: false, executable: null, version: null, version_ok: false, detail: '无需外部引擎。', declared: null }, runtime_claim: 'UNVERIFIED', historical_evidence: { SOURCE_IMPLEMENTED: 'PASS' }, artifact_evidence: artifactEvidence({ status: 'NOT_EXPORTED' }), artifact_evidence_status: 'NOT_EXPORTED' });
const targetsData = (): StoryExportTargets => ({
  schema: 'poemseed-interactive-export-targets/1', contract_schema: 'poemseed-interactive-export-contract/1', contract_version: 1, contract: {},
  adaptation: { id: 'story', version: 1, status: 'APPROVED' },
  story: { title: '合成互动故事', entry_node_id: 'gate', max_steps: 4, nodes: 2, variables: 1, endings: 1, spec_digest: 'a'.repeat(64), source_digest: 'b'.repeat(64) },
  witness: [{ node_id: 'end', ending: '回家', choices: ['home'] }], analysis: { can_review: true, analysis_complete: true, issues: [], warnings: [], states_checked: 2 },
  targets: [godot(), legacy()], media_manifest: [], can_export_any: true,
  target_runtime_policy: 'INDEPENDENT_EVIDENCE_LEVELS; GENERATION_IS_NOT_RUNTIME; MISSING_ENGINE_BLOCKS_RUNTIME_NOT_SAFE_EXPORT', model_called: false,
});
function backend() {
  const story = makeStory();
  return vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (init.method === 'GET') return reply(url.endsWith('/story') ? story : { items: [story], truncated: false });
    const body = JSON.parse(String(init.body));
    if (url.endsWith('/export-targets')) return reply(targetsData());
    if (url.endsWith('/export-preview')) return reply({ preview_digest: 'c'.repeat(64), can_export: true, losses: ['NO_SAVE_OR_RESTORE'], media_manifest: [], target_runtime: 'NOT_RUN', analysis, targets: targetsData().targets, target_id: body.target_id });
    if (url.endsWith('/export')) {
      return reply({ filename: 'godot-4-runtime-project-v1-story-v1.zip', mime: 'application/zip', content_base64: btoa('synthetic zip'), sha256: 'd'.repeat(64), target_runtime: 'NOT_RUN',
        target_id: body.target_id, target_format_version: 'godot-runtime-project-1', adapter_revision: 1, file_count: 6, files_digest: 'e'.repeat(64), runtime_claim: 'NOT_RUN', evidence: {}, published: false });
    }
    return reply(story);
  });
}
function stubUrl() {
  const createObjectURL = vi.fn(() => 'blob:target'), revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
}
const selectStory = async () => fireEvent.click(await screen.findByRole('button', { name: /合成互动故事 · v/ }));

it('reads targets, preflights and downloads a single target through the real panel without removing the legacy flow', async () => {
  stubUrl();
  const fetch = backend(); vi.stubGlobal('fetch', fetch);
  render(<InteractiveStoryPanel client={client()} />); await selectStory();
  expect(screen.getByRole('button', { name: '预检互动导出' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  await screen.findByLabelText('导出目标列表');
  const targetsCall = fetch.mock.calls.find(([url]) => String(url).endsWith('/export-targets'))!;
  expect(JSON.parse(String(targetsCall[1].body))).toEqual({ expected_version: 1 });
  expect(screen.getByLabelText('导出目标 GODOT_4_RUNTIME_PROJECT_V1')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '选择目标 Godot 4 运行时项目' }));
  fireEvent.click(screen.getByRole('button', { name: '预检所选目标导出' }));
  await screen.findByLabelText('所选目标导出预检');
  const previewCall = fetch.mock.calls.find(([url]) => String(url).endsWith('/export-preview'))!;
  expect(JSON.parse(String(previewCall[1].body))).toEqual({ expected_version: 1, target_id: 'GODOT_4_RUNTIME_PROJECT_V1' });
  fireEvent.click(screen.getByLabelText(/已核对所选目标的兼容性损失/));
  fireEvent.click(screen.getByRole('button', { name: '生成所选目标包' }));
  const link = await screen.findByRole('link', { name: '下载 godot-4-runtime-project-v1-story-v1.zip' });
  expect(link.getAttribute('href')).toBe('blob:target');
  const exportCall = fetch.mock.calls.find(([url]) => String(url).endsWith('/export'))!;
  expect(JSON.parse(String(exportCall[1].body))).toEqual({ expected_version: 1, preview_digest: 'c'.repeat(64), target_id: 'GODOT_4_RUNTIME_PROJECT_V1' });
  expect(screen.getByLabelText('所选目标下载状态').textContent).toContain('文件数：6');
  // The legacy multi-target flow is still available and untouched.
  expect((screen.getByRole('button', { name: '预检互动导出' }) as HTMLButtonElement).disabled).toBe(false);
});

it('hides read target data and blocks export when unsaved input appears', async () => {
  stubUrl();
  const fetch = backend(); vi.stubGlobal('fetch', fetch);
  render(<InteractiveStoryPanel client={client()} />); await selectStory();
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  await screen.findByLabelText('导出目标列表');
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '未保存的新对白' } });
  await waitFor(() => expect(screen.queryByLabelText('导出目标列表')).toBeNull());
  expect((screen.getByRole('button', { name: '读取导出目标' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/有未保存的互动草稿/)).toBeTruthy();
});
