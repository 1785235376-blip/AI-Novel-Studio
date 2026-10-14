import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import {
  reviewActionRequest, reviewBatchReceipt, reviewBatchRequest, reviewInboxProjection, reviewInboxQuery,
  taskCancelRequest, taskCancellationReceipt, taskCenterProjection, taskCenterTaskQuery,
} from './taskCenterContract';
import {
  REVIEW_INBOX_ACTIONS, REVIEW_INBOX_BATCH_LIMIT, TASK_CENTER_BOUNDS, TASK_CENTER_ERROR_CODES, TASK_CENTER_TOKEN,
  type ReviewActionReceipt, type ReviewBatchRequest, type ReviewBatchReceipt, type ReviewInboxAction,
  type ReviewInboxItem, type ReviewInboxProjection, type ReviewInboxQuery, type TaskCancellationReceipt,
  type TaskCenterClient, type TaskCenterScope, type TaskCenterTask, type TaskCenterTaskQuery,
  type TaskCenterTasksProjection,
} from './taskCenterTypes';

/**
 * 原 owner / 传输层真实抛出的机器码 → 有界的用户文案。未登记的码保留传输层文本
 * （它本身也是后端写死的有界文案），绝不把服务端正文直接渲染出去。
 */
const TASK_CENTER_FAILURES: Record<string, string> = {
  [TASK_CENTER_ERROR_CODES.versionConflict]: '原记录的版本已经变化，本次操作未提交。请核对重新读取后的版本。',
  [TASK_CENTER_ERROR_CODES.sourceStale]: '来源或任务状态已变化，本次操作未提交。请重新读取后核对。',
  [TASK_CENTER_ERROR_CODES.notFound]: '原记录当前不可用，或此功能尚未启用。',
  [TASK_CENTER_ERROR_CODES.invalid]: '服务端未接受本次操作。请核对版本与动作后重试。',
  [TASK_CENTER_ERROR_CODES.featureDisabled]: '当前实例未启用统一任务中心或审核收件箱功能。',
  [TASK_CENTER_ERROR_CODES.authorityChanged]: '身份、项目或分支已经变化，本次操作未提交。请重新打开工作区。',
  [TASK_CENTER_ERROR_CODES.reviewAuthorityChanged]: '审核身份已经变化，本次决定未提交。请重新打开审核收件箱。',
  [TASK_CENTER_ERROR_CODES.branchScopeRequired]: '协作模式需要明确的分支范围，本次读取未执行。',
};

function refusal(reason: unknown): unknown {
  if (!(reason instanceof ApiError)) return reason;
  const problem = reason.problem;
  const message = TASK_CENTER_FAILURES[problem.code]
    ?? (problem.status === 401 || problem.status === 403 ? '当前会话无权读取或操作此内容。'
      : problem.status === 409 ? '版本或来源已经变化。请重新读取后核对，不会自动重试。'
        : problem.status === 404 ? '原记录或功能当前不可用。' : undefined);
  return message ? new ApiError({ ...problem, message }) : reason;
}

/** 本地拒绝：请求在离开客户端前就被有界校验挡住，并使用自己的稳定机器码。 */
function locally<T>(code: string, message: string, run: () => T): T {
  try {
    return run();
  } catch (reason) {
    if (reason instanceof ApiError) throw new ApiError({ status: reason.status, code, message });
    throw reason;
  }
}
const segment = encodeURIComponent;

/**
 * 注入既有 Studio 传输（形状同 `productionWorkflowClient.ts`）。这里只有"读任务 /
 * 读审核收件箱 / 取消一条原任务 / 单个审核 / 批量审核"，没有执行器，也不查凭据。
 *
 * 真实绝对 URL 前缀与既有消费者一致（`frontend/src/experimental/api.ts` 的 base 加
 * `uxClient.ts` / `InboxPanel.tsx` 的路径）：
 *   GET  /api/novels/{nid}/experimental/workspace/tasks?q=&failed_only=
 *   POST /api/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel
 *   GET  /api/novels/{nid}/experimental/review-inbox?domain=&status=&search=
 *   POST /api/novels/{nid}/experimental/review-inbox/{domain}/{item_id}/{action}
 *   POST /api/novels/{nid}/experimental/review-inbox/batch
 */
export function createTaskCenterClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): TaskCenterClient {
  const capturedScope = scope ? { ...scope } : undefined;
  const expected: TaskCenterScope = capturedScope ? {
    mode: 'collaboration', novel_id: projectId, workspace_id: capturedScope.workspaceId,
    storyline_id: capturedScope.storylineId, branch_id: capturedScope.branchId,
  } : { mode: 'local', novel_id: projectId };
  const tasksBase = `/api/novels/${segment(projectId)}/experimental/workspace/tasks`;
  const inboxBase = `/api/novels/${segment(projectId)}/experimental/review-inbox`;
  // 捕获的身份在构造时克隆；之后的导航不能把请求改指到别的项目。
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const rejected = () => new ApiError({
    status: 403, code: TASK_CENTER_ERROR_CODES.tasksScopeMismatch,
    message: '任务中心与当前项目或分支不一致，请重新打开。',
  });
  const inboxRejected = () => new ApiError({
    status: 403, code: TASK_CENTER_ERROR_CODES.inboxScopeMismatch,
    message: '审核收件箱与当前项目或分支不一致，请重新打开。',
  });
  const inboxTarget = (domain: string, id: string) => {
    if (!TASK_CENTER_TOKEN.test(domain) || !id.trim() || id.length > TASK_CENTER_BOUNDS.item_id) throw new ApiError({
      status: 200, code: TASK_CENTER_ERROR_CODES.reviewLocalInvalid,
      message: '审核项标识不可用，请重新读取审核项后再提交。',
    });
    return `${inboxBase}/${segment(domain)}/${segment(id)}`;
  };

  return {
    async readTasks(query: TaskCenterTaskQuery, signal?: AbortSignal): Promise<TaskCenterTasksProjection> {
      if (foreign()) throw rejected();
      // 查询参数在本地就有界（`ux_api.py::tasks` 的 `q` 上限 160）。
      const checked = locally(TASK_CENTER_ERROR_CODES.tasksQueryLocalInvalid,
        '任务查询过长或含不可用字符，请缩短后重试。',
        () => taskCenterTaskQuery({ q: query?.q ?? '', failed_only: query?.failed_only === true }));
      // 与既有消费者完全一致的查询串（`uxClient.ts::tasks`）：两个参数总是发送。
      const search = new URLSearchParams({ q: checked.q, failed_only: String(checked.failed_only) });
      try {
        return taskCenterProjection(await transport.json<unknown>(`${tasksBase}?${search}`, 'GET', undefined, signal),
          projectId, expected);
      } catch (reason) { throw refusal(reason); }
    },
    async readInbox(query: ReviewInboxQuery, signal?: AbortSignal): Promise<ReviewInboxProjection> {
      if (foreign()) throw inboxRejected();
      const checked = locally(TASK_CENTER_ERROR_CODES.inboxQueryLocalInvalid,
        '审核筛选过长或含不可用字符，请缩短后重试。',
        () => reviewInboxQuery({ domain: query?.domain ?? '', status: query?.status ?? '', search: query?.search ?? '' }));
      const params = new URLSearchParams();
      // 与既有消费者一致：只发送非空过滤参数（`InboxPanel.tsx`）。
      if (checked.domain) params.set('domain', checked.domain);
      if (checked.status) params.set('status', checked.status);
      if (checked.search) params.set('search', checked.search);
      const suffix = params.toString();
      try {
        return reviewInboxProjection(await transport.json<unknown>(`${inboxBase}${suffix ? `?${suffix}` : ''}`,
          'GET', undefined, signal), projectId, expected);
      } catch (reason) { throw refusal(reason); }
    },
    async cancelTask(task: Pick<TaskCenterTask, 'authority' | 'id' | 'revision'>,
      signal?: AbortSignal): Promise<TaskCancellationReceipt> {
      if (foreign()) throw rejected();
      // `TaskCancelIn` 只接受 64 位十六进制 `expected_revision`；绝不发送猜测的版本。
      const body = locally(TASK_CENTER_ERROR_CODES.cancelLocalInvalid,
        '取消请求缺少原任务版本，请重新读取任务后再取消。',
        () => taskCancelRequest({ expected_revision: task.revision }));
      const url = `${tasksBase}/${segment(task.authority)}/${segment(task.id)}/cancel`;
      try {
        return taskCancellationReceipt(await transport.json<unknown>(url, 'POST', body, signal), projectId, expected);
      } catch (reason) { throw refusal(reason); }
    },
    async reviewItem(item: Pick<ReviewInboxItem, 'domain' | 'id' | 'version'>, action: ReviewInboxAction,
      signal?: AbortSignal): Promise<ReviewActionReceipt> {
      if (foreign()) throw inboxRejected();
      // `inbox_api.py` 的路由 Literal 只接受这三个动作；其余动作属于原领域自己的界面。
      if (!(REVIEW_INBOX_ACTIONS as readonly string[]).includes(action)) throw new ApiError({
        status: 200, code: TASK_CENTER_ERROR_CODES.reviewLocalInvalid,
        message: '此动作不由统一收件箱执行，请在原领域审核界面处理。',
      });
      const url = `${inboxTarget(item.domain, item.id)}/${segment(action)}`;
      const body = locally(TASK_CENTER_ERROR_CODES.reviewLocalInvalid,
        '审核请求缺少候选版本，请重新读取审核项后再提交。',
        () => reviewActionRequest({ expected_version: item.version }));
      try {
        // 领域服务返回的载荷一律不读取、不渲染：2xx 是这里唯一采纳的证据。
        await transport.json<unknown>(url, 'POST', body, signal);
      } catch (reason) { throw refusal(reason); }
      return { domain: item.domain, id: item.id, action, accepted: true };
    },
    async reviewBatch(request: ReviewBatchRequest, signal?: AbortSignal): Promise<ReviewBatchReceipt> {
      if (foreign()) throw inboxRejected();
      const body = locally(TASK_CENTER_ERROR_CODES.batchLocalInvalid,
        `批量审核需要 1–${REVIEW_INBOX_BATCH_LIMIT} 条不重复的候选，请重新核对选择。`,
        () => reviewBatchRequest(request));
      try {
        return reviewBatchReceipt(await transport.json<unknown>(`${inboxBase}/batch`, 'POST', body, signal));
      } catch (reason) {
        if (reason instanceof ApiError && reason.problem.code === TASK_CENTER_ERROR_CODES.inboxInvalid) {
          throw new ApiError({ ...reason.problem, code: TASK_CENTER_ERROR_CODES.batchInvalid });
        }
        throw refusal(reason);
      }
    },
  };
}
