import type { WorkspaceNavigation } from './uxClient';

export type ReceiptPin = { kind: string; id?: string; version?: number; digest?: string; state?: string };
const id = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240 && value === value.trim() && !/[\u0000-\u0020\u007f]/.test(value) && !value.includes('://');
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const version = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0;
export function originalTaskTarget(taskId: unknown): WorkspaceNavigation | undefined {
  return id(taskId) ? { kind: 'feature', id: taskId, feature: 'cover_storyboard_generation', task_authority: 'media' } : undefined;
}
export function originalChapterTarget(pin: ReceiptPin): WorkspaceNavigation | undefined {
  return pin.kind === 'CHAPTER' && pin.state !== 'UNAVAILABLE' && id(pin.id) && version(pin.version) && digest(pin.digest)
    ? { kind: 'chapter', id: pin.id, version: pin.version } : undefined;
}
export function receiptRecoveryStage(code: string): string {
  if (['SOURCE_CHANGED_OR_UNAVAILABLE', 'SOURCE_TASK_CHANGED', 'ORIGIN_AUTHORITY_CHANGED', 'CURRENT_PRIVACY_CHANGED'].includes(code)) return '来源与原授权';
  if (['ADAPTER_OR_MODEL_CHANGED', 'CONFIGURED_ADAPTER_REQUIRED', 'ORIGINAL_RUNTIME_EVIDENCE_MISSING', 'RUNTIME_OR_IMPLEMENTATION_CHANGED', 'EXACT_MODEL_IDENTITY_REQUIRED'].includes(code)) return '环境与模型';
  if (['ORIGINAL_OUTPUT_UNAVAILABLE', 'ORIGINAL_OUTPUT_CHANGED'].includes(code)) return '原产物';
  if (['MODEL_BROKER_FEATURE_REQUIRED', 'MODEL_BROKER_NOT_CONFIGURED', 'MODEL_BROKER_NO_LEGAL_ROUTE', 'FRESH_CLOUD_AUTHORIZATION_NOT_INTEGRATED'].includes(code)) return '费用与本次授权';
  return '未分类阻断';
}
export function receiptRecoveryAdvice(code: string): string {
  const stage = receiptRecoveryStage(code);
  if (stage === '来源与原授权') return '先打开原任务核对来源；旧清单继续保留，不能用当前来源冒充原快照。选择性更新须回到原修改影响入口重新选择和预检。';
  if (stage === '环境与模型') return '核对原 Adapter、模型与运行环境；不静默替换模型，也不保证旧输出可以复用。';
  if (stage === '原产物') return '在原媒体审核中核对候选与文件；摘要缺失或不符不能当作可复用缓存。';
  if (stage === '费用与本次授权') return '在原模型路由核对当前费用和授权；旧费用、预算预留及审批不代表本次许可。';
  return '保留阻断代码并在原入口核对；没有可证明的恢复动作，不能自动重试。';
}

/** Treat malformed, withheld and conflicting references as evidence gaps. */
export function receiptPins(value: unknown): ReceiptPin[] | null {
  if (!Array.isArray(value) || value.length > 500) return null;
  return value.map(raw => {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw) || raw.state === 'UNAVAILABLE') return { kind: '来源', state: 'UNAVAILABLE' };
    return { kind: typeof raw.kind === 'string' && raw.kind.length <= 80 ? raw.kind : '未知来源',
      id: id(raw.id) ? raw.id : undefined, version: version(raw.version) ? raw.version : undefined,
      digest: digest(raw.digest) ? raw.digest : undefined };
  });
}
export function uniqueChapterTarget(pin: ReceiptPin, pins: ReceiptPin[]): WorkspaceNavigation | undefined {
  return pins.filter(item => item.kind === pin.kind && item.id === pin.id).length === 1 ? originalChapterTarget(pin) : undefined;
}
export function receiptOutputs(value: unknown): { proposal_id: string; candidate_index: number; digest: string }[] | null {
  if (!Array.isArray(value) || value.length > 500 || value.some(raw => !raw || typeof raw !== 'object' || Array.isArray(raw)
    || !id(raw.proposal_id) || !Number.isSafeInteger(raw.candidate_index) || raw.candidate_index < 0 || !digest(raw.digest))) return null;
  if (new Set(value.map(row => row.proposal_id)).size !== value.length || new Set(value.map(row => row.candidate_index)).size !== value.length) return null;
  return value;
}
