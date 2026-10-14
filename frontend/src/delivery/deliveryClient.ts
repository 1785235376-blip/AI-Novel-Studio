import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { deliveryProjectId, deliveryReceipt, deliveryReceiptPage } from './deliveryContract';
import {
  DELIVERY_CODES, DELIVERY_JOB_ID,
  type DeliveryClient, type DeliveryFormatId, type DeliveryReceipt, type DeliveryReceiptPage, type DeliveryScope,
} from './deliveryTypes';

/**
 * 注入既有 Studio 传输层。这个客户端**只有读取**：
 *
 * - `GET /api/exports`（`app/api.py::list_exports` →
 *   `ExportJobService.list()`）读取原 owner 的导出历史页；
 * - `GET /api/exports/{job_id}`（`app/api.py::get_export` →
 *   `ExportJobService.get()`）读取**同一条**原任务回执。
 *
 * 它**没有** `POST /api/exports`、**没有** `/cancel`、**没有** `/retry`：本目录不派发、
 * 不取消、不重试任何导出任务。回执丢失时的恢复只能是重新读取（见
 * `deliveryOps.ts::receiptRecovery`），因此"在这里触发第二次派发"在结构上不可能 ——
 * 不是靠约定，而是这里根本没有会写的方法。
 *
 * 凭据：客户端从不查找、也不保存任何凭据；`X-Session-Token` / `X-Branch-Id` 由注入的
 * 传输层自己附加（与 `productionWorkflowClient.ts` 同一约定）。
 */
export function createDeliveryClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): DeliveryClient {
  const expectedProject = deliveryProjectId(projectId);
  const capturedScope = scope ? { ...scope } : undefined;
  const branchId = capturedScope?.branchId ?? null;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const rejected = () => new ApiError({
    status: 403, code: DELIVERY_CODES.scopeMismatch, message: '导出交付与当前项目或分支不一致，请重新打开。',
  });
  const base = (): string => {
    const query = branchId ? `&branch_id=${encodeURIComponent(branchId)}` : '';
    return `/api/exports?novel_id=${encodeURIComponent(expectedProject)}${query}`;
  };
  return {
    readReceipts: (signal?: AbortSignal): Promise<DeliveryReceiptPage> => {
      if (foreign()) return Promise.reject(rejected());
      // `limit=50` 是原 owner `list()` 的默认页大小与其 `1..100` 上限内的合法取值。
      return transport.json<unknown>(`${base()}&limit=50`, 'GET', undefined, signal)
        .then(value => deliveryReceiptPage(value, expectedProject));
    },
    readReceipt: (jobId: string, signal?: AbortSignal): Promise<DeliveryReceipt> => {
      if (foreign()) return Promise.reject(rejected());
      if (typeof jobId !== 'string' || !DELIVERY_JOB_ID.test(jobId)) {
        return Promise.reject(new ApiError({
          status: 400, code: DELIVERY_CODES.receiptInvalid, message: '导出回执标识不合法，未发起读取。',
        }));
      }
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : '';
      return transport.json<unknown>(`/api/exports/${encodeURIComponent(jobId)}${query}`, 'GET', undefined, signal)
        .then(value => deliveryReceipt(value, expectedProject));
    },
  };
}

/** 供组合根核对：本客户端声明的稳定范围（只读）。 */
export function deliveryClientScope(projectId: string, scope?: CollaborationContext['scope']): DeliveryScope {
  return scope ? {
    mode: 'collaboration', novel_id: projectId, workspace_id: scope.workspaceId,
    project_id: scope.projectId, storyline_id: scope.storylineId, branch_id: scope.branchId,
  } : { mode: 'local', novel_id: projectId };
}

/** 已经可用的格式（用于在界面上只展示原 owner 真正会接受的取值）。 */
export type DeliveryFormatOption = { id: DeliveryFormatId; label: string };
