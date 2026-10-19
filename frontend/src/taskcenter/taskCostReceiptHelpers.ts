import { TASK_PROVIDER_IDENTIFIER, type TaskCenterScope, type TaskCenterTask } from './taskCenterTypes';

export type TaskCostReceipt = { kind: 'UNKNOWN'; reason: 'UNSUPPORTED' | 'MISSING' | 'AMBIGUOUS' | 'INVALID' | 'UNREADABLE' } | {
  kind: 'RECEIPT'; id: string; jobId: string; provider: string; model: string;
  estimate: number | null; actual: number | null; currency: 'USD'; status: string;
  costState: string; source: string | null; priceVersion: number | null; synthetic: boolean | null;
};
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const amount = (value: unknown): value is number | null => value === null
  || (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= 10 ** 12);
const identifier = (value: unknown): value is string => typeof value === 'string' && TASK_PROVIDER_IDENTIFIER.test(value);
const text = (value: unknown, max: number): value is string => typeof value === 'string'
  && value.trim().length > 0 && value.length <= max && !/[\u0000-\u001f\u007f]/.test(value);
export const unknownCostReceipt = (reason: Extract<TaskCostReceipt, { kind: 'UNKNOWN' }>['reason']): TaskCostReceipt => ({ kind: 'UNKNOWN', reason });

/** Read-only projection of the original broker ledger, never a new accounting owner.
 * History is actor-scoped by its existing endpoint and capped at 100 by the owner.
 * Missing older entries therefore mean UNKNOWN, never no charge.
 */
export function taskCostReceipt(value: unknown, task: Pick<TaskCenterTask, 'authority' | 'id'>,
  projectId: string, scope: TaskCenterScope): TaskCostReceipt {
  if (task.authority !== 'author_generation') return unknownCostReceipt('UNSUPPORTED');
  if (!text(task.id, 160) || !object(value) || !Array.isArray(value.ledger)
    || value.ledger.length > 100 || value.ledger.some(row => !object(row))) return unknownCostReceipt('INVALID');
  const matches = value.ledger.filter(row => row.job_id === task.id);
  if (!matches.length) return unknownCostReceipt('MISSING');
  if (matches.length !== 1) return unknownCostReceipt('AMBIGUOUS');
  const row = matches[0];
  const rowScope = row.scope;
  if (row.novel_id !== projectId || !object(rowScope)
    || Object.keys(rowScope).length !== Object.keys(scope).length
    || Object.entries(scope).some(([key, val]) => rowScope[key] !== val)
    || !text(row.id, 160) || !identifier(row.provider_id) || !identifier(row.model_id)
    || row.currency !== 'USD' || !amount(row.reserve_microusd) || !amount(row.actual_microusd)
    || typeof row.dispatched !== 'boolean') return unknownCostReceipt('INVALID');
  const price = row.price;
  if (price !== null && (!object(price) || !text(price.source, 240)
    || price.currency !== 'USD' || !amount(price.reserve_microusd)
    || price.reserve_microusd !== row.reserve_microusd
    || !['per_request', 'synthetic_provider_fee_only'].includes(String(price.applicability))
    || (price.applicability === 'synthetic_provider_fee_only' && price.actual_known_zero !== true)
    || (price.applicability === 'per_request' && price.actual_known_zero !== undefined))) return unknownCostReceipt('INVALID');
  if (price === null && row.reserve_microusd !== null) return unknownCostReceipt('INVALID');
  const synthetic = object(price) ? price.actual_known_zero === true : null;
  const allowed: Record<string, readonly string[]> = {
    RESERVED: ['RESERVED_ESTIMATE', 'UNKNOWN'], DISPATCHED: ['RESERVED_ESTIMATE', 'UNKNOWN'],
    SETTLED: ['KNOWN_SYNTHETIC_ZERO', 'CALCULATED_FROM_REPORTED_USAGE'],
    RELEASED: ['NOT_DISPATCHED'], UNKNOWN_UPSTREAM: ['UNKNOWN_UPSTREAM'], RECONCILED: ['USER_REPORTED_UPSTREAM_BILL'],
  };
  if (typeof row.status !== 'string' || typeof row.cost_state !== 'string'
    || !Object.hasOwn(allowed, row.status) || !allowed[row.status].includes(row.cost_state)
    || (row.status === 'RESERVED' && row.dispatched)
    || (['DISPATCHED', 'SETTLED', 'UNKNOWN_UPSTREAM'].includes(row.status) && !row.dispatched)
    || (row.cost_state === 'RESERVED_ESTIMATE' && row.reserve_microusd === null)
    || (row.cost_state === 'UNKNOWN' && row.reserve_microusd !== null)
    || (row.cost_state === 'CALCULATED_FROM_REPORTED_USAGE' && synthetic !== false)
    || (['RESERVED', 'DISPATCHED', 'UNKNOWN_UPSTREAM'].includes(row.status) && row.actual_microusd !== null)
    || (['SETTLED', 'RELEASED', 'RECONCILED'].includes(row.status) && row.actual_microusd === null)
    || (row.cost_state === 'KNOWN_SYNTHETIC_ZERO' && (!synthetic || row.actual_microusd !== 0 || !row.dispatched))
    || (row.cost_state === 'NOT_DISPATCHED' && (row.dispatched || row.actual_microusd !== 0))) return unknownCostReceipt('INVALID');
  return { kind: 'RECEIPT', id: row.id, jobId: task.id, provider: row.provider_id, model: row.model_id,
    estimate: row.reserve_microusd, actual: row.actual_microusd, currency: 'USD', status: row.status,
    costState: row.cost_state, source: object(price) ? price.source as string : null,
    priceVersion: object(price) && Number.isSafeInteger(price.version) && Number(price.version) > 0 ? Number(price.version) : null,
    synthetic };
}

/** Six decimals preserve each micro-USD, including zero; no floating-point price math. */
export function receiptAmount(value: number | null): string {
  return value === null ? '未知' : `${Math.floor(value / 1000000)}.${String(value % 1000000).padStart(6, '0')} USD（${value} micro-USD）`;
}

export function taskRecoveryGuidance(task: TaskCenterTask): string {
  const policy = task.retry_policy === 'SOURCE_AUTHORITY_ONLY'
    && task.action_limits.retry === 'SOURCE_PREFLIGHT_REQUIRED'
    && task.action_limits.resume === 'SOURCE_RECOVERY_REQUIRED';
  return `${policy ? '先重新读取原任务并核对结果；重试需原服务预检，恢复需原服务确认。' : '请在原服务核对可用操作。'}${task.progress
    ? `原服务报告已完成 ${task.progress.completed} / ${task.progress.total} ${task.progress.unit}；这不证明存在持久检查点。`
    : '原服务未报告可量化进度。'}这里不会重试、重放或恢复提供商计算。`;
}
