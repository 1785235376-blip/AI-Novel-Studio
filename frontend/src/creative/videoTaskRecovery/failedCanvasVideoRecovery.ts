import {
  canvasVideoTaskJobMatches, checkedCanvasVideoTaskJob,
  type CanvasVideoReturnBinding, type CanvasVideoSource, type CanvasVideoTaskJob,
  type CanvasVideoTrimParameters, type CanvasVideoTrimTaskBinding,
} from '../canvasVideoTrimTask';
import type { ProductionJob } from '../studioProductionClient';

export type FailedCanvasVideoOrigin = {
  owner: 'timeline'; job_id: string; job_version: number; request_id: string;
  request_digest: string; receipt_digest: string | null;
};
export type FailedCanvasVideoDraft = {
  request_id: string; derived_from: FailedCanvasVideoOrigin; parameters: CanvasVideoTrimParameters;
  source_snapshots: [CanvasVideoSource]; canvas_return: CanvasVideoReturnBinding;
};

function invalid(): never {
  throw new Error('只能从原位置仍有效、没有候选或测量的 FAILED 本地视频截取记录派生草稿；请重新读取原记录。');
}
function same(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object') return false;
  if (Array.isArray(left) !== Array.isArray(right)) return false;
  const a = Object.keys(left), b = Object.keys(right);
  return a.length === b.length && a.every(key => Object.hasOwn(right, key)
    && same((left as Record<string, unknown>)[key], (right as Record<string, unknown>)[key]));
}
function assertUnchanged(job: ProductionJob, task: CanvasVideoTrimTaskBinding, parent: CanvasVideoTaskJob) {
  if (!same(job, parent) || !same(task.source, parent.canvas_video.source_snapshots[0])
    || !same(task.returnBinding, parent.canvas_video.canvas_return)) invalid();
}

function checkedParent(job: ProductionJob, task: CanvasVideoTrimTaskBinding): CanvasVideoTaskJob {
  // Keep the real typed command, recipe and receipt parser authoritative, including future derived chains.
  const parent = checkedCanvasVideoTaskJob(job);
  if (parent.status !== 'FAILED' || parent.output_candidate !== null || parent.media_measurement !== null
    || parent.approved_asset_version !== null || parent.needs_reconciliation === true
    || !canvasVideoTaskJobMatches(task, parent)) invalid();
  assertUnchanged(job, task, parent);
  return parent;
}

/** Read-only eligibility check; never allocates a request identity. */
export function canDeriveFailedCanvasVideoDraft(job: ProductionJob, task: CanvasVideoTrimTaskBinding): boolean {
  try { checkedParent(job, task); return true; } catch { return false; }
}

/** Prepare a separate draft. The original Apply entry must explicitly save its new Timeline. */
export function deriveFailedCanvasVideoDraft(job: ProductionJob, task: CanvasVideoTrimTaskBinding,
  newRequestId: string): FailedCanvasVideoDraft {
  const parent = checkedParent(job, task);
  if (typeof newRequestId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(newRequestId)
    || newRequestId === parent.request_id || !task.isCurrent()) invalid();
  assertUnchanged(job, task, parent);
  const command = parent.canvas_video;
  return {
    request_id: newRequestId,
    derived_from: { owner: 'timeline', job_id: parent.id, job_version: parent.version,
      request_id: parent.request_id, request_digest: parent.request_digest, receipt_digest: parent.receipt_digest },
    parameters: structuredClone(command.parameters), source_snapshots: structuredClone(command.source_snapshots),
    canvas_return: structuredClone(command.canvas_return),
  };
}
