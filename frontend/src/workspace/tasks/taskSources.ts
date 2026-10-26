/**
 * [HERMIA-FE-20261025 U3-M3] Read-only projections of EXISTING task owners into the shared TaskRef contract.
 * - task-center rows: `taskcenter/taskCenterClient.ts::readTasks` (already validated by taskCenterContract).
 * - production jobs: `creative/studioProductionClient.ts::list/get` (already validated by the production decoder).
 * No new endpoint, no second state system. Raw ids live in the model only (data-* attrs), never as visible text.
 * Interface gaps (recorded, not papered over):
 *  G-U3-1 task-center GET /workspace/tasks has NO pagination/cursor; production GET /jobs is capped at 1000 with no paging.
 *         We page client-side over the already-fetched bounded list and say so on screen.
 *  G-U3-2 task-center rows carry no creative node/document relation (source pointer = kind/id/feature only) → link=null.
 *  G-U3-3 task-center has no per-task detail endpoint → detail = the listed row; production has get(owner,id).
 */
import {ApiError} from '../../api';
import type {ProductionJob} from '../../creative/studioProductionClient';
import {TASK_STATUS_LABELS, type TaskCenterTask} from '../../taskcenter/taskCenterTypes';
import type {TaskPanelState, TaskRef} from '../contracts';

export const TASK_PAGE_SIZE = 20;
export const PAGING_GAP_TEXT = '服务端任务列表不分页：这里是对已读取的有限列表在本机分页显示。';

const JOB_STATUS_TEXT: Record<ProductionJob['status'], string> = {
  QUEUED: '排队中', RUNNING: '运行中', SEND_RESERVED: '准备发送', REMOTE_RUNNING: '远端运行中', RESULT_READY: '结果已返回',
  AWAITING_REVIEW: '等待审核', SUCCEEDED: '已完成', REVIEWING: '审核中', APPROVED: '已通过', UNKNOWN: '结果未知', FAILED: '失败', CANCELLED: '已取消',
};
const OWNER_TEXT: Record<ProductionJob['owner'], string> = {image: '图像', audio: '音频', video: '视频', timeline: '时间线'};

export function statusText(ref: Pick<TaskRef, 'source' | 'status'>): string {
  if (ref.source === 'production-job') return JOB_STATUS_TEXT[ref.status as ProductionJob['status']] ?? '结果未知';
  return (TASK_STATUS_LABELS as Record<string, string>)[ref.status] ?? '结果未知';
}

export function fromTaskCenter(t: TaskCenterTask): TaskRef {
  return {source: 'task-center', id: `${t.authority}:${t.id}`, owner: t.authority, status: t.status, revision: t.version,
    title: t.label || '未命名任务', link: null /* G-U3-2 */, stale: t.stale};
}

export function fromProductionJob(j: ProductionJob): TaskRef {
  const ret = j.command?.canvas_return;
  return {source: 'production-job', id: `${j.owner}:${j.id}`, owner: j.owner, status: j.status, revision: j.version,
    title: `${OWNER_TEXT[j.owner]}任务`,
    // Only the owner's own canvas-return binding is a real relation; anything else stays null (no fake node).
    link: ret ? {canvas: 'creative', documentId: ret.canvas_id, nodeId: ret.card_id} : null,
    stale: j.status === 'UNKNOWN' || j.needs_reconciliation === true};
}

export function pageOf<T>(items: T[], page: number, size = TASK_PAGE_SIZE) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const p = Math.min(Math.max(0, page), pages - 1);
  return {page: p, pages, rows: items.slice(p * size, p * size + size)};
}

/** Maps a read failure into the panel state without echoing server bodies. 401/403 ⇒ revoked (stop, clear rows). */
export function failureState(reason: unknown): TaskPanelState {
  if (reason instanceof ApiError && (reason.problem.status === 401 || reason.problem.status === 403))
    return {kind: 'revoked', text: '当前账号已无权查看这个项目的任务。已清空列表；重新登录或切换到有权限的项目后再刷新。'};
  if (reason instanceof ApiError && reason.problem.status === 404)
    return {kind: 'error', text: '这个实例没有启用任务列表，或项目已不可用。', next: '确认项目仍存在后点「刷新」。'};
  return {kind: 'error', text: '任务列表读取失败。', next: '检查网络后点「刷新」重试；不会自动重试。'};
}
