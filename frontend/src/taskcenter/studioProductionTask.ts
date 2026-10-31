import { ApiError } from '../api';
import type { ProductionJob } from '../creative/studioProductionClient';

export type StudioProductionTask = ProductionJob & { owner: 'image' | 'video' };

function invalid(): never {
  throw new ApiError({ status: 200, code: 'STUDIO_TASK_RECEIPT_CHANGED', message: '所选制作回执已变化。请重新读取列表后明确选择。' });
}
function supported(job: ProductionJob): job is StudioProductionTask {
  return job.owner === 'image' || job.owner === 'video';
}
function inScope(job: ProductionJob, projectId: string, branchId: string | null) {
  return job.novel_id === projectId && job.branch_id === branchId;
}

/** These are already decoded original-owner receipts, never generic task DTOs. */
export function studioProductionTaskRows(jobs: ProductionJob[], projectId: string, branchId: string | null): StudioProductionTask[] {
  if (jobs.some(job => !inScope(job, projectId, branchId))) invalid();
  const rows = jobs.filter(supported), keys = rows.map(job => `${job.owner}:${job.id}`);
  if (new Set(keys).size !== keys.length) invalid();
  return rows;
}

// JSON object key order is not receipt identity. Arrays retain their owner order.
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value)
    .sort(([left], [right]) => left.localeCompare(right)).map(([key, entry]) => [key, canonical(entry)]));
  return value;
}

/** No latest-version substitution: both inputs must first pass the production client decoder. */
export function exactStudioProductionTask(value: ProductionJob, selected: StudioProductionTask, projectId: string, branchId: string | null): StudioProductionTask {
  if (!supported(value) || !supported(selected) || !inScope(value, projectId, branchId) || !inScope(selected, projectId, branchId)
    || value.owner !== selected.owner || value.id !== selected.id || value.version !== selected.version
    || value.request_digest !== selected.request_digest
    || JSON.stringify(canonical(value)) !== JSON.stringify(canonical(selected))) invalid();
  return value;
}
