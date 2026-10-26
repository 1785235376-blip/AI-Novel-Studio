/**
 * [HERMIA-FE-20261025 U4-M9b] After refresh / offline / unknown outcome / process restart: READ the original task first.
 * Only a successful read of the original owner record can confirm state. Anything else stays UNKNOWN with a next step.
 * This module has no write path at all — it cannot regenerate, re-enqueue, re-review or re-adopt.
 */
import type {ExecutionTruth, ScopeLease} from '../contracts';
import type {ProductionJob} from '../../creative/studioProductionClient';

const TERMINAL = new Set(['APPROVED', 'FAILED', 'CANCELLED', 'SUCCEEDED', 'RESULT_READY', 'AWAITING_REVIEW']);
export const STATUS_TEXT: Record<string, string> = {QUEUED: '排队中', RUNNING: '执行中', SEND_RESERVED: '正在发送', REMOTE_RUNNING: '远端执行中',
  RESULT_READY: '候选已返回', AWAITING_REVIEW: '等待审核', SUCCEEDED: '候选已返回', REVIEWING: '审核中', APPROVED: '已审核', UNKNOWN: '结果未知',
  FAILED: '执行失败', CANCELLED: '已取消'};

export async function resolveExecutionTruth(read: () => Promise<ProductionJob>, lease: Pick<ScopeLease, 'epoch' | 'isCurrent'>,
  opts: {online: boolean}): Promise<ExecutionTruth | {state: 'RETIRED'}> {
  const epoch = lease.epoch;
  if (!opts.online) return {state: 'UNKNOWN', next: '当前离线，无法核实原任务。恢复网络后点「重新读取原任务」。不会自动重新生成。'};
  let job: ProductionJob;
  try { job = await read(); } catch {
    if (!lease.isCurrent() || lease.epoch !== epoch) return {state: 'RETIRED'};
    return {state: 'UNKNOWN', next: '读取原任务失败，结果仍未确认。请稍后点「重新读取原任务」，或到任务面板查看。不会自动重新生成。'};
  }
  if (!lease.isCurrent() || lease.epoch !== epoch) return {state: 'RETIRED'};
  if (job.status === 'UNKNOWN' || job.needs_reconciliation)
    return {state: 'UNKNOWN', next: '原任务自己也无法确认结果（可能远端仍在计算）。请在原生产入口手动「核对结果」；系统不会自动重发。'};
  return {state: 'CONFIRMED', status: STATUS_TEXT[job.status] ?? (TERMINAL.has(job.status) ? '已结束' : '处理中')};
}
