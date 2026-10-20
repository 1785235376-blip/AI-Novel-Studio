import type { StoryArtifactEvidence, StoryCapability, StoryEngineProbe, StoryExportTarget } from './interactiveStoryClient';

export const CAPABILITY_KEYS = [
  'conditions', 'bool_variables', 'int_variables', 'assignment', 'dialogue',
  'choices', 'endings', 'loops', 'step_cap', 'save', 'restore', 'unicode', 'media',
] as const;

export const CAPABILITY_LABELS: Record<string, string> = {
  conditions: '条件', bool_variables: '布尔变量', int_variables: '整数变量', assignment: '赋值',
  dialogue: '对白', choices: '选择', endings: '结局', loops: '循环', step_cap: '步数上限',
  save: '存档', restore: '读档', unicode: 'Unicode 文本', media: '媒体引用',
};

export const EVIDENCE_LEVELS = [
  'SOURCE_IMPLEMENTED', 'SCHEMA_VALIDATED', 'FIXTURE_TESTED', 'GENERATED_ARTIFACT_VALIDATED',
  'TARGET_RUNTIME_EXECUTED', 'SAVE_RESTORE_VERIFIED', 'WINDOWS_USABILITY_VERIFIED',
] as const;

export const EVIDENCE_LABELS: Record<string, string> = {
  SOURCE_IMPLEMENTED: '源码实现', SCHEMA_VALIDATED: '模式校验', FIXTURE_TESTED: '夹具测试',
  GENERATED_ARTIFACT_VALIDATED: '生成产物校验', TARGET_RUNTIME_EXECUTED: '目标运行时执行',
  SAVE_RESTORE_VERIFIED: '存档/读档验证', WINDOWS_USABILITY_VERIFIED: 'Windows 可用性验证',
};

export const TARGET_KIND_LABELS: Record<string, string> = {
  RUNNABLE_PROJECT: '可运行项目', DATA_ONLY_ADAPTER: '数据适配器', LEGACY_FRAGMENT: '旧版片段',
};

export const EVIDENCE_STATUS_LABELS: Record<string, string> = {
  PASS: 'PASS', FAIL: 'FAIL', PARTIAL: 'PARTIAL', BLOCKED_ENVIRONMENT: 'BLOCKED_ENVIRONMENT',
  BLOCKED_AUTHORITY: 'BLOCKED_AUTHORITY', NOT_RUN: 'NOT_RUN',
};

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'error';

export function capabilityLabel(key: string): string { return CAPABILITY_LABELS[key] ?? key; }
export function evidenceLabel(level: string): string { return EVIDENCE_LABELS[level] ?? level; }
export function targetKindLabel(kind: string): string { return TARGET_KIND_LABELS[kind] ?? kind; }

export type CapabilityRow = { key: string; label: string; note: string };

export function splitCapabilities(capabilities: Record<string, StoryCapability> | undefined): { unsupported: CapabilityRow[]; lossy: CapabilityRow[]; supported: CapabilityRow[] } {
  const unsupported: CapabilityRow[] = [], lossy: CapabilityRow[] = [], supported: CapabilityRow[] = [];
  const known = CAPABILITY_KEYS as readonly string[];
  const keys = [...known, ...Object.keys(capabilities ?? {}).filter(key => !known.includes(key))];
  for (const key of keys) {
    const capability = capabilities?.[key];
    if (!capability) continue;
    const row = { key, label: capabilityLabel(key), note: capability.note.trim() };
    if (!capability.supported) unsupported.push(row);
    else if (capability.lossy) lossy.push(row);
    else supported.push(row);
  }
  return { unsupported, lossy, supported };
}

/** Deduplicated loss list: compatibility losses are authoritative, descriptor
 * losses are the static declaration. Order is preserved for reproducibility. */
export function targetLossRows(target: StoryExportTarget | undefined): string[] {
  if (!target) return [];
  const rows: string[] = [];
  for (const loss of [...(target.compatibility?.losses ?? []), ...(target.losses ?? [])]) {
    if (typeof loss === 'string' && loss && !rows.includes(loss)) rows.push(loss);
  }
  return rows;
}

export function capabilitySummaryText(capabilities: Record<string, StoryCapability> | undefined): string {
  const { unsupported, lossy, supported } = splitCapabilities(capabilities);
  return '支持 ' + String(supported.length) + ' 项 · 有损 ' + String(lossy.length) + ' 项 · 不支持 ' + String(unsupported.length) + ' 项';
}

export function evidenceTone(status: string): Tone {
  if (status === 'PASS') return 'success';
  if (status === 'FAIL') return 'error';
  if (status === 'PARTIAL' || status === 'BLOCKED_ENVIRONMENT' || status === 'BLOCKED_AUTHORITY') return 'warning';
  return 'neutral';
}

export type EvidenceRow = { level: string; label: string; status: string; tone: Tone };

export function evidenceRows(evidence: Record<string, string> | undefined): EvidenceRow[] {
  return EVIDENCE_LEVELS.map(level => {
    const status = evidence?.[level] ?? 'NOT_RUN';
    return { level, label: evidenceLabel(level), status, tone: evidenceTone(status) };
  });
}

export type ProbeDescription = { tone: Tone; headline: string; detail: string; runtimeUnavailable: boolean };

/** The probe only decides whether runtime evidence could have been collected on
 * this host. A missing engine never blocks safe generation/export. */
export function probeDescription(probe: StoryEngineProbe | undefined): ProbeDescription {
  const declared = probe?.declared;
  const name = declared?.name ?? '目标引擎';
  const minimum = declared?.minimum_version ? '（要求 ≥ ' + declared.minimum_version + '）' : '';
  const detected = probe?.version ? '检测到 ' + probe.version + (probe.executable ? ' · ' + probe.executable : '') : probe?.executable ? '可执行文件 ' + probe.executable : '';
  switch (probe?.status) {
    case 'NOT_REQUIRED':
      return { tone: 'info', headline: '无需外部引擎', detail: '生成此目标不需要外部引擎，因此不需要运行验证。', runtimeUnavailable: false };
    case 'READY':
      return { tone: 'success', headline: name + ' 就绪（READY）' + minimum, detail: detected || (probe.detail ?? '版本探测通过。'), runtimeUnavailable: false };
    case 'NOT_INSTALLED':
      return { tone: 'warning', headline: name + ' 未安装（NOT_INSTALLED）' + minimum, detail: (probe?.detail ?? '未在 PATH 或声明的安装位置找到引擎。') + ' 运行验证无法在本机执行；安全生成/导出不受影响。', runtimeUnavailable: true };
    case 'UNSUPPORTED_VERSION':
      return { tone: 'warning', headline: name + ' 版本不满足（UNSUPPORTED_VERSION）' + minimum, detail: (probe?.detail ?? '') + (detected ? ' ' + detected : '') + ' 运行验证被阻止；安全生成/导出不受影响。', runtimeUnavailable: true };
    case 'PROBE_FAILED':
      return { tone: 'error', headline: name + ' 探测失败（PROBE_FAILED）' + minimum, detail: (probe?.detail ?? '版本探测未完成。') + ' 运行验证被阻止；安全生成/导出不受影响。', runtimeUnavailable: true };
    default:
      return { tone: 'neutral', headline: '引擎探测结果未知（' + (probe?.status ?? 'NOT_PROBED') + '）', detail: '无法确认目标运行时；不声明运行验证。', runtimeUnavailable: true };
  }
}

export type RuntimeClaim = { tone: Tone; text: string; success: boolean };

export const ARTIFACT_EVIDENCE_STATUS_LABELS: Record<string, string> = {
  PASS: '当前产物已通过匹配的运行时验证',
  UNVERIFIED: '当前产物未验证（导出后尚未记录运行时验证回执）',
  NOT_EXPORTED: '当前修订尚未导出到该目标',
  EVIDENCE_INVALID: '验证回执无效，已拒绝',
  TARGET_MISMATCH: '验证回执属于其他目标',
  FORMAT_MISMATCH: '验证回执属于其他目标格式版本',
  RUNTIME_MISMATCH: '验证回执的运行时身份/版本不匹配',
  STALE_STORY: '验证回执属于其他作品',
  STALE_REVISION: '验证回执属于旧修订，当前修订需重新运行验证',
  STALE_SOURCE: '验证回执的来源摘要已过期',
  STALE_ARTIFACT: '验证回执对应旧产物摘要，当前导出产物需重新验证',
};

export function artifactEvidenceStatusLabel(status: string | undefined): string {
  return ARTIFACT_EVIDENCE_STATUS_LABELS[status ?? ''] ?? ('未知证据状态 ' + (status ?? 'NOT_RUN'));
}

export function artifactEvidenceStatusTone(status: string | undefined, levels: Record<string, string> | undefined): Tone {
  if (status === 'PASS' && (levels?.TARGET_RUNTIME_EXECUTED === 'PASS' || levels?.SAVE_RESTORE_VERIFIED === 'PASS')) return 'success';
  if (status === 'UNVERIFIED' || status === 'NOT_EXPORTED') return 'neutral';
  if (status === 'EVIDENCE_INVALID') return 'error';
  return 'warning';
}

export type ArtifactEvidenceRow = EvidenceRow & { currentArtifact: true };

/** Current-artifact levels only; historical adapter evidence must not be shown here. */
export function artifactEvidenceRows(levels: Record<string, string> | undefined): EvidenceRow[] {
  return EVIDENCE_LEVELS.map(level => {
    const status = levels?.[level] ?? 'NOT_RUN';
    return { level, label: evidenceLabel(level), status, tone: evidenceTone(status) };
  });
}

export function evidenceMatchText(matched: StoryArtifactEvidence['matched_receipt'] | undefined): string {
  if (!matched) return '';
  return '验证器 ' + matched.verifier + ' · ' + matched.verified_at + ' · 运行时 ' + matched.runtime.name + ' ' + matched.runtime.version + (matched.runtime.format ? '（' + matched.runtime.format + '）' : '');
}

/** Runtime claims are independent evidence records. Nothing here ever upgrades
 * generation success into a runtime success claim. */
export function runtimeClaimText(claim: string | undefined): RuntimeClaim {
  if (claim === 'TARGET_RUNTIME_EXECUTED' || claim === 'SAVE_RESTORE_VERIFIED') {
    return { tone: 'success', text: '当前产物运行验证：' + claim + ' 已记录（PASS，绑定当前作品/修订/产物摘要）', success: true };
  }
  if (claim === 'BLOCKED_ENVIRONMENT') return { tone: 'warning', text: '运行验证：BLOCKED_ENVIRONMENT（未执行；缺少引擎/运行时）', success: false };
  if (claim === 'BLOCKED_AUTHORITY') return { tone: 'warning', text: '运行验证：BLOCKED_AUTHORITY（未执行；缺少授权）', success: false };
  if (claim === 'UNVERIFIED') return { tone: 'neutral', text: '当前产物未验证：生成成功不等于运行成功；需在目标运行时实际执行后提交绑定该产物摘要的验证回执。', success: false };
  return { tone: 'neutral', text: '运行验证：' + (claim || 'NOT_RUN') + '（未执行；生成成功不等于运行成功）', success: false };
}

export function historicalEvidenceText(evidence: Record<string, string> | undefined): string {
  const runtime = evidence?.TARGET_RUNTIME_EXECUTED ?? 'NOT_RUN';
  const save = evidence?.SAVE_RESTORE_VERIFIED ?? 'NOT_RUN';
  return '模板/适配器历史记录：TARGET_RUNTIME_EXECUTED=' + runtime + ' · SAVE_RESTORE_VERIFIED=' + save + '。历史记录不代表当前作品已运行。';
}

export type TargetReadiness = { exportReady: boolean; reasons: string[] };

export function targetReadiness(target: StoryExportTarget | undefined, adaptationStatus: string, analysisCanReview: boolean): TargetReadiness {
  if (!target) return { exportReady: false, reasons: ['请先选择导出目标。'] };
  const reasons: string[] = [];
  if (adaptationStatus !== 'APPROVED') reasons.push('当前修订状态为 ' + adaptationStatus + '，只有 APPROVED 修订可以生成导出。');
  if (!analysisCanReview) reasons.push('路径与变量分析未通过（或达到分析边界），导出被阻止。');
  if (!target.compatibility?.can_export) {
    const codes = (target.compatibility?.issues ?? []).map(issue => issue.code).slice(0, 5);
    reasons.push('目标兼容性检查不通过' + (codes.length ? '：' + codes.join('、') : '：该目标不支持当前故事内容'));
  }
  const exportReady = target.compatibility?.can_export === true && target.export_ready === true
    && adaptationStatus === 'APPROVED' && analysisCanReview;
  return { exportReady, reasons };
}

export function formatDigest(value: string | undefined, visible = 12): string {
  if (!value) return '（无）';
  return value.length > visible ? value.slice(0, visible) + '…' : value;
}

export function compatibleIssueText(issue: { code: string; node_id?: string | null; choice_id?: string | null; character_id?: string | null; detail?: string }): string {
  const parts = [issue.code];
  if (issue.node_id) parts.push('节点 ' + issue.node_id);
  if (issue.choice_id) parts.push('选择 ' + issue.choice_id);
  if (issue.character_id) parts.push('角色 ' + issue.character_id);
  if (issue.detail) parts.push(issue.detail);
  return parts.join(' · ');
}
