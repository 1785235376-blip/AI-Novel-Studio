import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { checkedModelTransferCatalog, checkedModelTransferCleanupPreview, checkedModelTransferPreview, checkedModelTransferSource,
  checkedModelTransferTask, invalidModelTransfer, type ModelTransferCleanupPreview, type ModelTransferPreview, type ModelTransferSource, type ModelTransferTask } from './modelTransferContract';

const base = '/api/model-center/transfers';
/** Host transfer API using only the captured workspace transport; no invented project URL. */
export function createModelTransferClient(projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope']) {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > 200) invalidModelTransfer(true);
  const capturedScope = scope ? { ...scope } : undefined;
  function admit(signal?: AbortSignal) {
    if (capturedScope && capturedScope.projectId !== projectId) throw new ApiError({ status: 403, code: 'MODEL_TRANSFER_SCOPE_MISMATCH', message: '当前项目上下文不一致，传输操作已停用。' });
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  }
  async function request(path: string, method: 'GET' | 'POST', body?: unknown, signal?: AbortSignal): Promise<unknown> {
    admit(signal);
    return transport.json<unknown>(`${base}${path}`, method, body, signal);
  }
  function currentPreview(preview: ModelTransferPreview): ModelTransferPreview {
    const checked = checkedModelTransferPreview(preview, checkedModelTransferSource(preview.source));
    if (checked.expires_at <= Date.now() / 1000 || checked.available_bytes < checked.required_bytes) invalidModelTransfer(true);
    return checked;
  }
  async function action(task: ModelTransferTask, kind: 'pause' | 'resume' | 'cancel', signal?: AbortSignal) {
    const expected = checkedModelTransferTask(task);
    if (kind === 'pause' && expected.state !== 'TRANSFERRING') invalidModelTransfer(true);
    if (kind === 'resume' && !expected.can_resume) invalidModelTransfer(true);
    if (kind === 'cancel' && !['TRANSFERRING', 'PAUSED', 'INTERRUPTED', 'FAILED'].includes(expected.state)) invalidModelTransfer(true);
    const result = checkedModelTransferTask(await request(`/${encodeURIComponent(expected.id)}/${kind}`, 'POST', {
      expected_version: expected.version, ...(kind === 'resume' ? { confirmed: true } : {}),
    }, signal), expected);
    if (result.version <= expected.version) invalidModelTransfer();
    return result;
  }
  return {
    list: async (signal?: AbortSignal) => checkedModelTransferCatalog(await request('', 'GET', undefined, signal)),
    preview: async (source: ModelTransferSource, signal?: AbortSignal) => {
      const expected = checkedModelTransferSource(source);
      return checkedModelTransferPreview(await request('/preview', 'POST', { source_id: expected.id }, signal), expected);
    },
    start: async (preview: ModelTransferPreview, signal?: AbortSignal) => {
      const expected = currentPreview(preview);
      const task = checkedModelTransferTask(await request('/start', 'POST', { preview_id: expected.preview_id, preview_digest: expected.preview_digest, confirmed: true }, signal));
      if (task.source_id !== expected.source.id || task.model_id !== expected.source.model_id || task.total_bytes !== expected.source.size_bytes) invalidModelTransfer();
      return task;
    },
    pause: (task: ModelTransferTask, signal?: AbortSignal) => action(task, 'pause', signal),
    resume: (task: ModelTransferTask, signal?: AbortSignal) => action(task, 'resume', signal),
    cancel: (task: ModelTransferTask, signal?: AbortSignal) => action(task, 'cancel', signal),
    cleanupPreview: async (task: ModelTransferTask, signal?: AbortSignal) => {
      const expected = checkedModelTransferTask(task);
      if (!['PAUSED', 'CANCELLED', 'FAILED', 'INTERRUPTED'].includes(expected.state)) invalidModelTransfer(true);
      return checkedModelTransferCleanupPreview(await request(`/${encodeURIComponent(expected.id)}/cleanup-preview`, 'POST', { expected_version: expected.version }, signal), expected);
    },
    cleanup: async (task: ModelTransferTask, preview: ModelTransferCleanupPreview, signal?: AbortSignal) => {
      const expected = checkedModelTransferTask(task), checked = checkedModelTransferCleanupPreview(preview, expected);
      if (!['PAUSED', 'CANCELLED', 'FAILED', 'INTERRUPTED'].includes(expected.state) || checked.expires_at <= Date.now() / 1000) invalidModelTransfer(true);
      const result = checkedModelTransferTask(await request(`/${encodeURIComponent(expected.id)}/cleanup`, 'POST', {
        expected_version: expected.version, preview_id: checked.preview_id, preview_digest: checked.preview_digest, confirmed: true,
      }, signal), expected);
      if (result.version <= expected.version || result.state !== 'CLEANED') invalidModelTransfer();
      return result;
    },
  };
}
export type ModelTransferClient = ReturnType<typeof createModelTransferClient>;
