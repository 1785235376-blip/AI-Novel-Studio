import { describe, expect, it } from 'vitest';
import { CAPABILITY_KEYS, artifactEvidenceRows, artifactEvidenceStatusLabel, artifactEvidenceStatusTone, capabilityLabel, compatibleIssueText, evidenceMatchText, evidenceRows, externalClaimRows, externalClaimSummary, formatDigest, probeDescription, runtimeClaimText, splitCapabilities, targetKindLabel, targetLossRows, targetReadiness } from './interactiveStoryExportPresentation';
import type { StoryArtifactEvidence, StoryCapability, StoryExportTarget } from './interactiveStoryClient';

const caps = (overrides: Record<string, { supported: boolean; lossy?: boolean; note?: string }> = {}): Record<string, StoryCapability> => {
  const result: Record<string, StoryCapability> = {};
  for (const key of CAPABILITY_KEYS) result[key] = { supported: true, lossy: false, note: '' };
  for (const [key, value] of Object.entries(overrides)) result[key] = { supported: value.supported, lossy: value.lossy ?? false, note: value.note ?? '' };
  return result;
};

const artifactEvidence = (patch: Partial<StoryArtifactEvidence> = {}): StoryArtifactEvidence => ({
  status: 'UNVERIFIED', levels: { GENERATED_ARTIFACT_VALIDATED: 'PASS', TARGET_RUNTIME_EXECUTED: 'NOT_RUN', SAVE_RESTORE_VERIFIED: 'NOT_RUN' },
  binding: null, matched_receipt: null, stale_receipts: [], checked_receipts: 0,
  policy: 'ONLY_RECEIPTS_BOUND_TO_THIS_EXACT_ARTIFACT_CAN_SET_RUNTIME_LEVELS', ...patch,
});
const target = (patch: Partial<StoryExportTarget> = {}): StoryExportTarget => ({
  target_id: 'GODOT_4_RUNTIME_PROJECT_V1', display_name: 'Godot 4 运行时项目', kind: 'RUNNABLE_PROJECT',
  format_version: 'godot-runtime-project-1', adapter_revision: 1,
  engine: { name: 'Godot', minimum_version: '4.0', executables: ['godot'], version_args: ['--version'], env_override: 'POEMSEED_GODOT_BIN', search_hints: [], gui: false, note: '' },
  capabilities: caps(), losses: ['NO_SAVE_OR_RESTORE'], runtime_requirements: ['Godot 4 project'], launch_instructions: '使用 Godot 打开目录', integration_notes: [], evidence: {},
  compatibility: { target_id: 'GODOT_4_RUNTIME_PROJECT_V1', can_export: true, capabilities: caps(), losses: ['MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED'], issues: [], notes: [] },
  engine_probe: { status: 'READY', detected: true, executable: 'C:/godot.exe', version: '4.7.0', version_ok: true, detail: '', declared: { name: 'Godot', minimum_version: '4.0', gui: false } },
  export_ready: true, historical_evidence: { SOURCE_IMPLEMENTED: 'PASS', TARGET_RUNTIME_EXECUTED: 'PASS', SAVE_RESTORE_VERIFIED: 'PASS' },
  artifact_evidence: artifactEvidence(), artifact_evidence_status: 'UNVERIFIED', runtime_claim: 'UNVERIFIED', ...patch,
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


describe('current-artifact evidence presentation', () => {
  it('treats an uploaded claim as external and never as system evidence', () => {
    const claim = { claim_digest: 'a'.repeat(64), verifier: 'self-declared', verified_at: '2026-10-20T00:00:00Z',
      runtime: { name: 'Godot', version: '4.7.0' }, commands: [], log_sha256: 'f'.repeat(64),
      checked_levels: { TARGET_RUNTIME_EXECUTED: 'PASS' }, asserted_levels: { TARGET_RUNTIME_EXECUTED: 'PASS' },
      trust: 'EXTERNAL_UNVERIFIED' };
    expect(artifactEvidenceStatusTone('EXTERNALLY_ASSERTED_PENDING', { TARGET_RUNTIME_EXECUTED: 'PASS' })).toBe('warning');
    const rows = externalClaimRows({ TARGET_RUNTIME_EXECUTED: 'PASS' });
    expect(rows.find(row => row.level === 'TARGET_RUNTIME_EXECUTED')).toMatchObject({ status: 'PASS', tone: 'warning' });
    expect(externalClaimSummary([claim])).toContain('不是系统已执行');
    expect(evidenceMatchText(claim)).toContain('外部验收声明来源');
    expect(evidenceMatchText(claim)).toContain('未经系统执行或复核');
  });

  it('labels every binding status without ever implying a pass for unverified work', () => {
    expect(artifactEvidenceStatusLabel('PASS')).toContain('已由系统实际运行验证');
    expect(artifactEvidenceStatusLabel('EXTERNALLY_ASSERTED_PENDING')).toContain('外部验收声明');
    expect(artifactEvidenceStatusLabel('EXTERNALLY_ASSERTED_PENDING')).toContain('不构成运行 PASS');
    expect(artifactEvidenceStatusLabel('UNVERIFIED')).toContain('未验证');
    expect(artifactEvidenceStatusLabel('NOT_EXPORTED')).toContain('尚未导出');
    expect(artifactEvidenceStatusLabel('STALE_REVISION')).toContain('旧修订');
    expect(artifactEvidenceStatusLabel('STALE_ARTIFACT')).toContain('旧产物摘要');
    expect(artifactEvidenceStatusTone('PASS', { TARGET_RUNTIME_EXECUTED: 'PASS' })).toBe('success');
    expect(artifactEvidenceStatusTone('UNVERIFIED', {})).toBe('neutral');
    expect(artifactEvidenceStatusTone('STALE_REVISION', {})).toBe('warning');
    expect(artifactEvidenceStatusTone('EVIDENCE_INVALID', {})).toBe('error');
    expect(runtimeClaimText('UNVERIFIED').text).toContain('生成成功不等于运行成功');
    expect(runtimeClaimText('UNVERIFIED').text).toContain('外部声明');
    expect(runtimeClaimText('UNVERIFIED').success).toBe(false);
  });
  it('shows only the current artifact levels in the artifact row set', () => {
    const rows = artifactEvidenceRows({ TARGET_RUNTIME_EXECUTED: 'NOT_RUN', SAVE_RESTORE_VERIFIED: 'NOT_RUN', GENERATED_ARTIFACT_VALIDATED: 'PASS' });
    expect(rows).toHaveLength(7);
    expect(rows.find(row => row.level === 'TARGET_RUNTIME_EXECUTED')).toMatchObject({ status: 'NOT_RUN', tone: 'neutral' });
    expect(rows.find(row => row.level === 'GENERATED_ARTIFACT_VALIDATED')).toMatchObject({ status: 'PASS', tone: 'success' });
  });
});
