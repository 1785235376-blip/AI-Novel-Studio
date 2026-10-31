import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from './studioGraphClient';
import { studioProductionContracts } from './studioWorkspaceOperationContract';
import type { StudioProductionScope, StudioWorkspaceProductionContracts } from './studioWorkspaceOperationTypes';

/** Inject the original Studio transport. This client exposes exactly one GET, never dispatch. */
export function createStudioWorkspaceOperationClient(projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope']) {
  const capturedScope = scope ? { ...scope } : undefined;
  const expected: StudioProductionScope = capturedScope ? {
    mode: 'collaboration', novel_id: projectId, workspace_id: capturedScope.workspaceId,
    storyline_id: capturedScope.storylineId, branch_id: capturedScope.branchId,
  } : { mode: 'local', novel_id: projectId };
  const url = `/api/projects/${encodeURIComponent(projectId)}/studio/production-contracts`;
  return {
    read: (signal?: AbortSignal): Promise<StudioWorkspaceProductionContracts> => {
      if (capturedScope && capturedScope.projectId !== projectId) {
        return Promise.reject(new ApiError({ status: 403, code: 'STUDIO_RESPONSE_SCOPE_MISMATCH',
          message: '制作操作契约与当前项目或分支不一致，请重新打开。' }));
      }
      return transport.json<unknown>(url, 'GET', undefined, signal).then(value => studioProductionContracts(value, projectId, expected));
    },
  };
}
