import type { CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { readModelBrokerHistory } from '../experimental/modelBrokerClient';
import { taskCostReceipt, unknownCostReceipt, type TaskCostReceipt } from './taskCostReceiptHelpers';
import type { TaskCenterScope, TaskCenterTask } from './taskCenterTypes';

/** Independent read-only companion; never expands the original task owner. */
export type TaskCostReceiptClient = {
  readCostReceipt: (task: Pick<TaskCenterTask, 'authority' | 'id'>, signal?: AbortSignal) => Promise<TaskCostReceipt>;
};

export function createTaskCostReceiptClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): TaskCostReceiptClient {
  const capturedScope = scope ? { ...scope } : undefined;
  const expected: TaskCenterScope = capturedScope ? {
    mode: 'collaboration', novel_id: projectId, workspace_id: capturedScope.workspaceId,
    storyline_id: capturedScope.storylineId, branch_id: capturedScope.branchId,
  } : { mode: 'local', novel_id: projectId };
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const segment = encodeURIComponent;
  return {
    async readCostReceipt(task, signal) {
      if (foreign()) return unknownCostReceipt('UNREADABLE');
      if (task.authority !== 'author_generation') return unknownCostReceipt('UNSUPPORTED');
      if (!task.id.trim() || task.id.length > 160) return unknownCostReceipt('INVALID');
      try {
        const history = await readModelBrokerHistory({
          get: (path, abortSignal) => transport.json(`/api/novels/${segment(projectId)}/experimental${path}`, 'GET', undefined, abortSignal),
        }, signal);
        return taskCostReceipt(history, task, projectId, expected);
      } catch {
        // This owner may be disabled/denied independently. Never fall back to
        // another access path, show server text, or erase the original task.
        return unknownCostReceipt('UNREADABLE');
      }
    },
  };
}
