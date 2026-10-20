import { describe, expect, it } from 'vitest';
import { CAPABILITY_KEYS, capabilityLabel, compatibleIssueText, evidenceRows, formatDigest, probeDescription, runtimeClaimText, splitCapabilities, targetKindLabel, targetLossRows, targetReadiness } from './interactiveStoryExportPresentation';
import type { StoryCapability, StoryExportTarget } from './interactiveStoryClient';

const caps = (overrides: Record<string, { supported: boolean; lossy?: boolean; note?: string }> = {}): Record<string, StoryCapability> => {
  const result: Record<string, StoryCapability> = {};
  for (const key of CAPABILITY_KEYS) result[key] = { supported: true, lossy: false, note: '' };
  for (const [key, value] of Object.entries(overrides)) result[key] = { supported: value.supported, lossy: value.lossy ?? false, note: value.note ?? '' };
  return result;
};

const target = (patch: Partial<StoryExportTarget> = {}): StoryExportTarget => ({
  target_id: 'GODOT_4_RUNTIME_PROJECT_V1', display_name: 'Godot 4 运行时项目', kind: 'RUNNABLE_PROJECT',
  format_version: 'godot-runtime-project-1', adapter_revision: 1,
  engine: { name: 'Godot', minimum_version: '4.0', executables: ['godot'], version_args: ['--version'], env_override: 'POEMSEED_GODOT_BIN', search_hints: [], gui: false, note: '' },
  capabilities: caps(), losses: ['NO_SAVE_OR_RESTORE'], runtime_requirements: ['Godot 4 project'], launch_instructions: '使用 Godot 打开目录', integration_notes: [], evidence: {},
  compatibility: { target_id: 'GODOT_4_RUNTIME_PROJECT_V1', can_export: true, capabilities: caps(), losses: ['MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED'], issues: [], notes: [] },
  engine_probe: { status: 'READY', detected: true, executable: 'C:/godot.exe', version: '4.7.0', version_ok: true, detail: '', declared: { name: 'Godot', minimum_version: '4.0', gui: false } },
  export_ready: true, runtime_claim: 'NOT_RUN', ...patch,
});

describe('capability presentation', () => {
  it('splits unsupported and lossy capabilities with notes and keeps supported ones', () => {
    const rows = splitCapabilities(caps({ dialogue: { supported: true, lossy: true, note: '对白空白规范化' }, save: { supported: false, note: '无存档' }, media: { supported: false, lossy: true, note: '不打包媒体' } }));
    expect(rows.unsupported.map(row => row.key)).toEqual(['save', 'media']);
    expect(rows.lossy).toEqual([{ key: 'dialogue', label: '对白', note: '对白空白规范化' }]);
    expect(rows.supported).toHaveLength(10);
  });
  it('formats capability labels and tolerates unknown keys', () => {
    expect(capabilityLabel('bool_variables')).toBe('布尔变量');
    expect(capabilityLabel('future_capability')).toBe('future_capability');
    expect(splitCapabilities(undefined)).toEqual({ unsupported: [], lossy: [], supported: [] });
  });
});

describe('target losses and readiness', () => {
  it('deduplicates compatibility and descriptor losses without dropping any', () => {
    expect(targetLossRows(target({ losses: ['NO_SAVE_OR_RESTORE', 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED'] }))).toEqual(['MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED', 'NO_SAVE_OR_RESTORE']);
    expect(targetLossRows(undefined)).toEqual([]);
  });
  it('requires an approved revision and passing analysis in addition to compatibility', () => {
    expect(targetReadiness(target(), 'APPROVED', true)).toEqual({ exportReady: true, reasons: [] });
    const draft = targetReadiness(target(), 'DRAFT', true);
    expect(draft.exportReady).toBe(false);
    expect(draft.reasons.join(' ')).toContain('APPROVED');
    const analysis = targetReadiness(target(), 'APPROVED', false);
    expect(analysis.exportReady).toBe(false);
    expect(analysis.reasons.join(' ')).toContain('路径与变量分析未通过');
    const incompatible = targetReadiness(target({ export_ready: false, compatibility: { ...target().compatibility, can_export: false, issues: [{ code: 'UNSUPPORTED_LOOP' }] } }), 'APPROVED', true);
    expect(incompatible.reasons.join(' ')).toContain('UNSUPPORTED_LOOP');
    expect(targetReadiness(undefined, 'APPROVED', true).exportReady).toBe(false);
  });
  it('never treats a missing engine as an export blocker', () => {
    const missing = target({ engine_probe: { status: 'NOT_INSTALLED', detected: false, executable: null, version: null, version_ok: false, detail: 'Godot was not found', declared: { name: 'Godot', minimum_version: '4.0', gui: false } } });
    expect(targetReadiness(missing, 'APPROVED', true).exportReady).toBe(true);
  });
});

describe('evidence presentation', () => {
  it('always shows every independent evidence level with its real status', () => {
    const rows = evidenceRows({ SOURCE_IMPLEMENTED: 'PASS', FIXTURE_TESTED: 'FAIL', TARGET_RUNTIME_EXECUTED: 'BLOCKED_ENVIRONMENT' });
    expect(rows).toHaveLength(7);
    expect(rows.find(row => row.level === 'SOURCE_IMPLEMENTED')).toMatchObject({ status: 'PASS', tone: 'success', label: '源码实现' });
    expect(rows.find(row => row.level === 'FIXTURE_TESTED')).toMatchObject({ status: 'FAIL', tone: 'error' });
    expect(rows.find(row => row.level === 'TARGET_RUNTIME_EXECUTED')).toMatchObject({ tone: 'warning' });
    expect(rows.find(row => row.level === 'SAVE_RESTORE_VERIFIED')).toMatchObject({ status: 'NOT_RUN', tone: 'neutral' });
    expect(evidenceRows(undefined)).toHaveLength(7);
  });
  it('never claims runtime success from generation or missing hosts', () => {
    expect(runtimeClaimText('TARGET_RUNTIME_EXECUTED')).toMatchObject({ tone: 'success', success: true });
    expect(runtimeClaimText('SAVE_RESTORE_VERIFIED')).toMatchObject({ success: true });
    expect(runtimeClaimText('BLOCKED_ENVIRONMENT')).toMatchObject({ tone: 'warning', success: false });
    expect(runtimeClaimText('BLOCKED_AUTHORITY').text).toContain('BLOCKED_AUTHORITY');
    const notRun = runtimeClaimText('NOT_RUN');
    expect(notRun.success).toBe(false);
    expect(notRun.text).toContain('生成成功不等于运行成功');
    expect(runtimeClaimText(undefined).success).toBe(false);
  });
});

describe('engine probe presentation', () => {
  it('reports every probe status honestly and marks runtime unavailability', () => {
    expect(probeDescription({ status: 'NOT_REQUIRED', detected: false, executable: null, version: null, version_ok: false, declared: null })).toMatchObject({ tone: 'info', runtimeUnavailable: false });
    expect(probeDescription(target().engine_probe)).toMatchObject({ tone: 'success', runtimeUnavailable: false });
    const missing = probeDescription({ status: 'NOT_INSTALLED', detected: false, executable: null, version: null, version_ok: false, detail: '未找到', declared: { name: 'Godot', minimum_version: '4.0', gui: false } });
    expect(missing).toMatchObject({ tone: 'warning', runtimeUnavailable: true });
    expect(missing.headline).toContain('NOT_INSTALLED');
    expect(missing.detail).toContain('安全生成/导出不受影响');
    expect(probeDescription({ status: 'UNSUPPORTED_VERSION', detected: true, executable: 'C:/godot.exe', version: '3.5.0', version_ok: false, declared: { name: 'Godot', minimum_version: '4.0', gui: false } }).runtimeUnavailable).toBe(true);
    expect(probeDescription({ status: 'PROBE_FAILED', detected: true, executable: 'C:/godot.exe', version: null, version_ok: false, declared: { name: 'Godot', minimum_version: '4.0', gui: false } })).toMatchObject({ tone: 'error', runtimeUnavailable: true });
    expect(probeDescription(undefined).runtimeUnavailable).toBe(true);
  });
});

describe('formatting', () => {
  it('formats digests, kinds and compatibility issues for display', () => {
    expect(formatDigest('a'.repeat(64))).toBe('a'.repeat(12) + '…');
    expect(formatDigest(undefined)).toBe('（无）');
    expect(targetKindLabel('RUNNABLE_PROJECT')).toBe('可运行项目');
    expect(targetKindLabel('UNKNOWN_KIND')).toBe('UNKNOWN_KIND');
    expect(compatibleIssueText({ code: 'UNSUPPORTED', node_id: 'gate', choice_id: 'home', character_id: 'alice', detail: '详情' })).toBe('UNSUPPORTED · 节点 gate · 选择 home · 角色 alice · 详情');
  });
});
