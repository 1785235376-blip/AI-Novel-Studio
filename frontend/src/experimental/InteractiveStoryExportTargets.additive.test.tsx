// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { InteractiveStoryExportTargets } from './InteractiveStoryExportTargets';
import type { interactiveStoryClient, InteractiveStory, StoryArtifactEvidence, StoryCapability, StoryExportPreview, StoryExportResult, StoryExportTarget, StoryExportTargets } from './interactiveStoryClient';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

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
const baseTarget = (patch: Partial<StoryExportTarget>): StoryExportTarget => ({
  target_id: 'GODOT_4_RUNTIME_PROJECT_V1', display_name: 'Godot 4 运行时项目', kind: 'RUNNABLE_PROJECT', format_version: 'godot-runtime-project-1', adapter_revision: 1,
  engine: { name: 'Godot', minimum_version: '4.0', executables: ['godot'], version_args: ['--version'], env_override: 'POEMSEED_GODOT_BIN', search_hints: [], gui: false, note: '' },
  capabilities: caps(), losses: ['NO_SAVE_OR_RESTORE'], runtime_requirements: ['Godot 4 项目'], launch_instructions: '解压后用 Godot 打开项目目录。', integration_notes: [], evidence: { SOURCE_IMPLEMENTED: 'PASS', FIXTURE_TESTED: 'PASS' },
  compatibility: { target_id: 'GODOT_4_RUNTIME_PROJECT_V1', can_export: true, capabilities: caps({ save: { supported: false, note: '无存档运行时' }, restore: { supported: false, note: '无读档运行时' } }), losses: [], issues: [], notes: [] },
  engine_probe: { status: 'READY', detected: true, executable: 'C:/godot.exe', version: '4.7.0', version_ok: true, detail: 'Godot 4.7.0 detected.', declared: { name: 'Godot', minimum_version: '4.0', gui: false } },
  export_ready: true, runtime_claim: 'UNVERIFIED', historical_evidence: { SOURCE_IMPLEMENTED: 'PASS', FIXTURE_TESTED: 'PASS', TARGET_RUNTIME_EXECUTED: 'PASS', SAVE_RESTORE_VERIFIED: 'PASS', WINDOWS_USABILITY_VERIFIED: 'NOT_RUN' }, artifact_evidence: artifactEvidence(), artifact_evidence_status: 'UNVERIFIED', ...patch,
});
const godotTarget = (patch: Partial<StoryExportTarget> = {}) => baseTarget(patch);
const renpyTarget = (patch: Partial<StoryExportTarget> = {}) => baseTarget({
  target_id: 'RENPY_8_5_4_PROJECT_V1', display_name: 'Ren’Py 8.5.4 项目', format_version: 'renpy-project-1', adapter_revision: 2,
  engine: { name: 'Ren\'Py', minimum_version: '8.5.4', executables: ['renpy.exe'], version_args: ['--version'], env_override: 'POEMSEED_RENPY_BIN', search_hints: [], gui: true, note: '' },
  engine_probe: { status: 'NOT_INSTALLED', detected: false, executable: null, version: null, version_ok: false, detail: 'Ren’Py was not found on PATH.', declared: { name: 'Ren\'Py', minimum_version: '8.5.4', gui: true } },
  evidence: { SOURCE_IMPLEMENTED: 'PASS', TARGET_RUNTIME_EXECUTED: 'BLOCKED_ENVIRONMENT' }, historical_evidence: { SOURCE_IMPLEMENTED: 'PASS', TARGET_RUNTIME_EXECUTED: 'BLOCKED_ENVIRONMENT', SAVE_RESTORE_VERIFIED: 'BLOCKED_ENVIRONMENT', WINDOWS_USABILITY_VERIFIED: 'NOT_RUN' }, artifact_evidence: artifactEvidence({ status: 'NOT_EXPORTED' }), artifact_evidence_status: 'NOT_EXPORTED', runtime_claim: 'UNVERIFIED', ...patch,
});
const legacyTarget = (patch: Partial<StoryExportTarget> = {}) => baseTarget({
  target_id: 'GODOT_4_DATA_ADAPTER', display_name: 'Godot 4 数据适配器（旧）', kind: 'DATA_ONLY_ADAPTER', format_version: 'godot-data-adapter-1', engine: null,
  engine_probe: { status: 'NOT_REQUIRED', detected: false, executable: null, version: null, version_ok: false, detail: 'No external engine is required to generate this target.', declared: null },
  evidence: { SOURCE_IMPLEMENTED: 'PASS' }, historical_evidence: { SOURCE_IMPLEMENTED: 'PASS' }, artifact_evidence: artifactEvidence({ status: 'NOT_EXPORTED' }), artifact_evidence_status: 'NOT_EXPORTED', runtime_claim: 'UNVERIFIED', ...patch,
});
const story: InteractiveStory = { id: 'story', version: 3, status: 'APPROVED', stale: false, content_withheld: false };
const targetsResponse = (patch: Partial<StoryExportTargets> = {}): StoryExportTargets => ({
  schema: 'poemseed-interactive-export-targets/1', contract_schema: 'poemseed-interactive-export-contract/1', contract_version: 1, contract: {},
  adaptation: { id: 'story', version: 3, status: 'APPROVED' },
  story: { title: '合成互动故事', entry_node_id: 'gate', max_steps: 4, nodes: 2, variables: 1, endings: 1, spec_digest: 'a'.repeat(64), source_digest: 'b'.repeat(64) },
  witness: [{ node_id: 'end', ending: '回家', choices: ['home'] }],
  analysis: { can_review: true, analysis_complete: true, issues: [], warnings: [], states_checked: 2 },
  targets: [godotTarget(), renpyTarget(), legacyTarget()], media_manifest: [], can_export_any: true,
  target_runtime_policy: 'INDEPENDENT_EVIDENCE_LEVELS; GENERATION_IS_NOT_RUNTIME; MISSING_ENGINE_BLOCKS_RUNTIME_NOT_SAFE_EXPORT', model_called: false, ...patch,
});
const previewResponse = (patch: Partial<StoryExportPreview> = {}): StoryExportPreview => ({
  preview_digest: 'c'.repeat(64), can_export: true, losses: ['INK_TARGET_OMITTED_UNSUPPORTED:X'], target_runtime: 'NOT_RUN',
  media_manifest: [{ asset_id: 'bg', missing: true, packaged: false, reason: 'MISSING_OR_CORRUPT' }],
  analysis: { issues: [], warnings: [], endings: [], states_checked: 1, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 4, can_review: true },
  targets: [], target_id: 'GODOT_4_RUNTIME_PROJECT_V1', ...patch,
});
const resultResponse = (patch: Partial<StoryExportResult> = {}): StoryExportResult => ({
  filename: 'godot-4-runtime-project-v1-story-v3.zip', mime: 'application/zip', content_base64: btoa('synthetic zip'),
  sha256: 'd'.repeat(64), target_runtime: 'NOT_RUN', target_id: 'GODOT_4_RUNTIME_PROJECT_V1', target_format_version: 'godot-runtime-project-1',
  adapter_revision: 1, file_count: 6, files_digest: 'e'.repeat(64), runtime_claim: 'NOT_RUN', evidence: {}, published: false, ...patch,
});

function stubUrl() {
  const createObjectURL = vi.fn(() => 'blob:target'), revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  return { createObjectURL, revokeObjectURL };
}
const apiMock = (patch: Record<string, ReturnType<typeof vi.fn>> = {}) => {
  const api = { targets: vi.fn(async () => targetsResponse()), exportPreview: vi.fn(async () => previewResponse()), export: vi.fn(async () => resultResponse()), ...patch };
  return { api: api as unknown as ReturnType<typeof interactiveStoryClient>, spies: api };
};
const readTargets = async () => { fireEvent.click(screen.getByRole('button', { name: '读取导出目标' })); await screen.findByLabelText('导出目标列表'); };
const selectGodot = () => fireEvent.click(screen.getByRole('button', { name: '选择目标 Godot 4 运行时项目' }));

it('shows target format, capabilities, losses, engine probes and independent evidence without claiming runtime success', async () => {
  const { api } = apiMock();
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  await readTargets();
  expect(screen.getByText(/目标清单契约：poemseed-interactive-export-contract\/1 v1/)).toBeTruthy();
  const godot = screen.getByLabelText('导出目标 GODOT_4_RUNTIME_PROJECT_V1');
  expect(godot.textContent).toContain('Godot 4 运行时项目');
  expect(godot.textContent).toContain('格式 godot-runtime-project-1');
  expect(godot.textContent).toContain('不支持能力');
  expect(godot.textContent).toContain('存档（save）');
  expect(within(screen.getByLabelText('引擎探测 GODOT_4_RUNTIME_PROJECT_V1')).getByText(/READY/)).toBeTruthy();
  const godotEvidence = screen.getByLabelText('当前产物验证 GODOT_4_RUNTIME_PROJECT_V1');
  expect(godotEvidence.textContent).toContain('生成成功不等于运行成功');
  expect(godotEvidence.textContent).toContain('当前产物未验证');
  expect(godotEvidence.textContent).toContain('TARGET_RUNTIME_EXECUTED');
  const godotHistorical = screen.getByLabelText('历史验证 GODOT_4_RUNTIME_PROJECT_V1');
  expect(godotHistorical.textContent).toContain('历史记录不代表当前作品已运行');
  expect(godotHistorical.textContent).toContain('TARGET_RUNTIME_EXECUTED=PASS');
  const renpy = screen.getByLabelText('导出目标 RENPY_8_5_4_PROJECT_V1');
  expect(screen.getByLabelText('引擎探测 RENPY_8_5_4_PROJECT_V1').textContent).toContain('NOT_INSTALLED');
  expect(screen.getByLabelText('引擎探测 RENPY_8_5_4_PROJECT_V1').textContent).toContain('安全生成/导出不受影响');
  expect(screen.getByLabelText('当前产物验证 RENPY_8_5_4_PROJECT_V1').textContent).toContain('尚未导出');
  expect(screen.getByLabelText('历史验证 RENPY_8_5_4_PROJECT_V1').textContent).toContain('BLOCKED_ENVIRONMENT');
  expect(renpy.textContent).toContain('导出后使用步骤');
  // A missing engine never blocks safe export: the target stays selectable.
  expect((screen.getByRole('button', { name: '选择目标 Ren’Py 8.5.4 项目' }) as HTMLButtonElement).disabled).toBe(false);
  expect(screen.queryByText(/运行验证：.*已记录（PASS）/)).toBeNull();
  expect(screen.getByLabelText('当前产物验证 RENPY_8_5_4_PROJECT_V1').textContent).toContain('未验证');
});

it('keeps legacy target ids as compatibility-only entries without a single-target download', async () => {
  const { api } = apiMock();
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  await readTargets();
  const legacy = screen.getByLabelText('导出目标 GODOT_4_DATA_ADAPTER');
  expect(legacy.textContent).toContain('兼容性条目，仅包含在旧的多样式导出包中');
  expect(within(legacy).queryByRole('button', { name: /选择目标/ })).toBeNull();
});

it('previews the selected target, requires loss confirmation and downloads the target bundle receipt', async () => {
  const { createObjectURL, revokeObjectURL } = stubUrl();
  const { api, spies } = apiMock();
  const view = render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  await readTargets();
  selectGodot();
  fireEvent.click(screen.getByRole('button', { name: '预检所选目标导出' }));
  const previewRegion = await screen.findByLabelText('所选目标导出预检');
  expect(spies.exportPreview).toHaveBeenCalledWith(story, 'GODOT_4_RUNTIME_PROJECT_V1');
  expect(previewRegion.textContent).toContain('缺失资源 1 / 引用 1 项');
  expect(previewRegion.textContent).toContain('INK_TARGET_OMITTED_UNSUPPORTED:X');
  const generate = screen.getByRole('button', { name: '生成所选目标包' }) as HTMLButtonElement;
  expect(generate.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(/已核对所选目标的兼容性损失、不支持能力与缺失项，确认生成 Godot 4 运行时项目 下载/));
  expect((screen.getByRole('button', { name: '生成所选目标包' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '生成所选目标包' }));
  const link = await screen.findByRole('link', { name: '下载 godot-4-runtime-project-v1-story-v3.zip' });
  expect(link.getAttribute('href')).toBe('blob:target');
  expect(createObjectURL).toHaveBeenCalledTimes(1);
  expect(spies.export).toHaveBeenCalledTimes(1);
  const exportCall = spies.export.mock.calls[0] as unknown as [InteractiveStory, { preview_digest: string }, string];
  expect(exportCall[1].preview_digest).toBe('c'.repeat(64));
  expect(exportCall[2]).toBe('GODOT_4_RUNTIME_PROJECT_V1');
  const receipt = screen.getByLabelText('所选目标下载状态');
  expect(receipt.textContent).toContain('target_id：GODOT_4_RUNTIME_PROJECT_V1');
  expect(receipt.textContent).toContain('格式版本：godot-runtime-project-1');
  expect(receipt.textContent).toContain('文件数：6');
  expect(receipt.textContent).toContain('ZIP sha256：' + 'd'.repeat(64));
  expect(receipt.textContent).toContain('文件集合摘要：' + 'e'.repeat(64));
  expect(receipt.textContent).toContain('生成不等于目标引擎运行验证');
  view.unmount();
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:target');
});

it('never enables generation for a target the server does not allow', async () => {
  const { api } = apiMock({ exportPreview: vi.fn(async () => previewResponse({ can_export: false, losses: ['TARGET_INCOMPATIBLE'] })) });
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  await readTargets(); selectGodot();
  fireEvent.click(screen.getByRole('button', { name: '预检所选目标导出' }));
  await screen.findByLabelText('所选目标导出预检');
  expect(screen.getByText(/所选目标当前不能导出/)).toBeTruthy();
  expect((screen.getByLabelText(/已核对所选目标的兼容性损失/) as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '生成所选目标包' }) as HTMLButtonElement).disabled).toBe(true);
});

it('dispatches one request for repeated target read, preflight and export clicks', async () => {
  stubUrl();
  const { api, spies } = apiMock();
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  const read = screen.getByRole('button', { name: '读取导出目标' });
  fireEvent.click(read); fireEvent.click(read);
  await screen.findByLabelText('导出目标列表');
  expect(spies.targets).toHaveBeenCalledTimes(1);
  selectGodot();
  const preflight = screen.getByRole('button', { name: '预检所选目标导出' });
  fireEvent.click(preflight); fireEvent.click(preflight);
  await screen.findByLabelText('所选目标导出预检');
  expect(spies.exportPreview).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByLabelText(/已核对所选目标的兼容性损失/));
  const generate = screen.getByRole('button', { name: '生成所选目标包' });
  fireEvent.click(generate); fireEvent.click(generate);
  await screen.findByLabelText('所选目标下载状态');
  expect(spies.export).toHaveBeenCalledTimes(1);
});

it('keeps late target data out of a newer saved revision and survives an unmount', async () => {
  let finish: (value: StoryExportTargets) => void = () => {};
  const targets = vi.fn(() => new Promise<StoryExportTargets>(resolve => { finish = resolve; }));
  const { api } = apiMock({ targets });
  const view = render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  view.rerender(<InteractiveStoryExportTargets api={api} story={{ ...story, version: 4 }} blocked={false} />);
  await act(async () => finish(targetsResponse()));
  expect(screen.queryByLabelText('导出目标列表')).toBeNull();
  // Unmount while another read is pending: no late state update is attempted.
  view.rerender(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  view.unmount();
  await act(async () => finish(targetsResponse()));
});

it('shows an explicit permission failure and clears stale target data', async () => {
  const targets = vi.fn()
    .mockResolvedValueOnce(targetsResponse())
    .mockRejectedValueOnce(new ApiError({ status: 403, code: 'FORBIDDEN', message: '当前身份没有此操作权限。' }));
  const { api } = apiMock({ targets });
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  await readTargets();
  fireEvent.click(screen.getByRole('button', { name: '读取导出目标' }));
  await screen.findByText(/FORBIDDEN/);
  expect(screen.queryByLabelText('导出目标列表')).toBeNull();
  expect(screen.queryByLabelText('所选目标导出')).toBeNull();
});

it('resets the workflow when the project is reopened', async () => {
  const { api } = apiMock();
  const view = render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  await readTargets(); selectGodot();
  expect(screen.getByLabelText('所选目标导出')).toBeTruthy();
  view.unmount();
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  expect(screen.queryByLabelText('导出目标列表')).toBeNull();
  expect(screen.queryByLabelText('所选目标导出')).toBeNull();
  expect(screen.getByText(/尚未读取导出目标/)).toBeTruthy();
});

it('does not offer single-target export before the revision is approved', async () => {
  const draftStory: InteractiveStory = { ...story, status: 'DRAFT' };
  const { api } = apiMock({ targets: vi.fn(async () => targetsResponse({ can_export_any: false, adaptation: { id: 'story', version: 3, status: 'DRAFT' }, targets: [godotTarget({ export_ready: false })] })) });
  render(<InteractiveStoryExportTargets api={api} story={draftStory} blocked={false} />);
  await readTargets();
  expect(screen.getByText(/当前修订不是 APPROVED/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '选择目标 Godot 4 运行时项目' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByLabelText('不可导出原因 GODOT_4_RUNTIME_PROJECT_V1').textContent).toContain('APPROVED');
});

it('shows an explicit export failure without producing a download link', async () => {
  stubUrl();
  const { api, spies } = apiMock({ export: vi.fn(async () => { throw new ApiError({ status: 409, code: 'STALE_SOURCE', message: '导出预览已改变，请重新预检。' }); }) });
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  await readTargets(); selectGodot();
  fireEvent.click(screen.getByRole('button', { name: '预检所选目标导出' }));
  await screen.findByLabelText('所选目标导出预检');
  fireEvent.click(screen.getByLabelText(/已核对所选目标的兼容性损失/));
  fireEvent.click(screen.getByRole('button', { name: '生成所选目标包' }));
  await screen.findByText(/STALE_SOURCE/);
  expect(spies.export).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('link', { name: /^下载 / })).toBeNull();
  expect(screen.queryByLabelText('所选目标下载状态')).toBeNull();
});

it('does not read targets on mount and hides loaded targets when input becomes unsaved', async () => {
  const { api, spies } = apiMock();
  const view = render(<InteractiveStoryExportTargets api={api} story={story} blocked={false} />);
  expect(spies.targets).not.toHaveBeenCalled();
  await readTargets();
  expect(screen.getByLabelText('导出目标列表')).toBeTruthy();
  view.rerender(<InteractiveStoryExportTargets api={api} story={story} blocked={true} />);
  expect(screen.queryByLabelText('导出目标列表')).toBeNull();
  expect((screen.getByRole('button', { name: '读取导出目标' }) as HTMLButtonElement).disabled).toBe(true);
});

it('does not read targets while input is unsaved and reports the blocked state', () => {
  const { api, spies } = apiMock();
  render(<InteractiveStoryExportTargets api={api} story={story} blocked={true} />);
  expect((screen.getByRole('button', { name: '读取导出目标' }) as HTMLButtonElement).disabled).toBe(true);
  expect(spies.targets).not.toHaveBeenCalled();
});
