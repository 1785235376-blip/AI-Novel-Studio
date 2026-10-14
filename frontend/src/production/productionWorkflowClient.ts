import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { productionWorkflowIntent, productionWorkflowIntentRequest, productionWorkflowProjection } from './productionWorkflowContract';
import {
  PRODUCTION_WORKFLOW_CAPACITY_CODES, PRODUCTION_WORKFLOW_ERROR_CODES,
  type ProductionWorkflowClient, type ProductionWorkflowIntent, type ProductionWorkflowIntentDraft,
  type ProductionWorkflowProjection, type ProductionWorkflowScope,
} from './productionWorkflowTypes';

/** Bounded, user-facing text per original owner error code. Unknown codes keep the transport text. */
const INTENT_FAILURES: Record<string, string> = {
  [PRODUCTION_WORKFLOW_ERROR_CODES.conflict]: '创作意图已被其他会话更新。当前输入仍保留，请核对最新版本后重新提交。',
  [PRODUCTION_WORKFLOW_ERROR_CODES.invalid]: '服务端未接受这次创作意图。当前输入仍保留，请核对意图标识与自定义名称。',
  [PRODUCTION_WORKFLOW_ERROR_CODES.authorityInvalid]: '当前会话无权修改创作意图。请重新核对身份与项目范围。',
  [PRODUCTION_WORKFLOW_ERROR_CODES.authorityChanged]: '身份或项目范围已变化，创作意图未保存。请重新打开工作区。',
  [PRODUCTION_WORKFLOW_ERROR_CODES.storageLowSpace]: '项目所在磁盘可用空间不足，创作意图未保存。请释放空间后重试。',
  [PRODUCTION_WORKFLOW_ERROR_CODES.storageUnavailable]: '暂时无法确认项目存储状态，创作意图未保存。',
};
const CAPACITY_FAILURE = '项目存储空间不足或不可用，创作意图未保存。请释放空间或稍后重试。';

function refusal(reason: unknown): unknown {
  if (!(reason instanceof ApiError)) return reason;
  const problem = reason.problem, message = INTENT_FAILURES[problem.code]
    ?? (reason.status === 507 || PRODUCTION_WORKFLOW_CAPACITY_CODES.includes(problem.code) ? CAPACITY_FAILURE : undefined);
  return message ? new ApiError({ ...problem, message }) : reason;
}

/**
 * Inject the original Studio transport. This client exposes exactly one GET and one
 * versioned intent replacement; it never looks up credentials and never dispatches work.
 */
export function createProductionWorkflowClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): ProductionWorkflowClient {
  const capturedScope = scope ? { ...scope } : undefined;
  const expected: ProductionWorkflowScope = capturedScope ? {
    mode: 'collaboration', novel_id: projectId, workspace_id: capturedScope.workspaceId,
    storyline_id: capturedScope.storylineId, branch_id: capturedScope.branchId,
  } : { mode: 'local', novel_id: projectId };
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio/production/workflow`;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const rejected = () => new ApiError({
    status: 403, code: PRODUCTION_WORKFLOW_ERROR_CODES.scopeMismatch, message: '制作工作流与当前项目或分支不一致，请重新打开。',
  });
  return {
    read: (signal?: AbortSignal): Promise<ProductionWorkflowProjection> => {
      if (foreign()) return Promise.reject(rejected());
      return transport.json<unknown>(base, 'GET', undefined, signal).then(value => productionWorkflowProjection(value, projectId, expected));
    },
    updateIntent: async (input: ProductionWorkflowIntentDraft, signal?: AbortSignal): Promise<ProductionWorkflowIntent> => {
      if (foreign()) throw rejected();
      // The request is validated before it leaves this client: an unknown key or an
      // unbounded label is refused locally instead of being sent to the owner.
      const body = productionWorkflowIntentRequest(input);
      try {
        return productionWorkflowIntent(await transport.json<unknown>(`${base}/intent`, 'POST', body, signal));
      } catch (reason) { throw refusal(reason); }
    },
  };
}
