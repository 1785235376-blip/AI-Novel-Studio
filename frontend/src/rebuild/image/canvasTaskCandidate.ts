import {safeImagePreviewUri} from '../../novel/ImageInfiniteCanvas';
import type {CanvasTaskBinding} from './canvasTaskBinding';

/** Read-only observation of a legacy image-job row, not a server version or output digest. */
export type CanvasTaskCandidate = Readonly<{
  jobId: string; novelId: string; nodeId: string;
  providerId: string; modelId: string; prompt: string;
  requestSha256: string; attempt: number; updatedAt: string;
  approvalStatus: 'PENDING' | 'APPROVED'; assetId?: string;
  /** Opaque source for in-memory equality only. Never render, log or persist this URI. */
  sourceUri?: string;
  /** Only attach to an image after the current owner explicitly requests a preview. */
  previewUri?: string;
}>;

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const id = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value);
// Match the existing binding owner contract; actor/scope/project IDs are not task IDs.
const ownerId = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240
  && value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value);
const text = (value: unknown, limit: number): value is string => typeof value === 'string' && value.length > 0
  && value.length <= limit && value.trim().length > 0 && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value);
const label = (value: unknown, limit: number): value is string => text(value, limit) && value.trim() === value && !/[\t\r\n]/.test(value);
const timestamp = (value: unknown): value is string => typeof value === 'string' && value.length <= 80
  && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const maxUriLength = 36 * 1024 * 1024;

/** Reuses the current URI allowlist with local syntax guards. Does not verify media or origin trust. */
function checkedPreviewUri(value: string | undefined): string | undefined {
  if (!value || value.length > maxUriLength || /[\u0000-\u001f\u007f\\]/.test(value)) return;
  const uri = safeImagePreviewUri(value);
  if (!uri) return;
  try {
    if (uri.startsWith('/')) {
      const base = 'https://canvas-preview.invalid';
      const parsed = new URL(uri, base);
      return parsed.origin === base && !parsed.username && !parsed.password ? uri : undefined;
    }
    const parsed = new URL(uri);
    if (parsed.username || parsed.password) return;
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return parsed.hostname ? uri : undefined;
    if (parsed.protocol === 'data:') return /^data:image\/(?:png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/]+={0,2}$/i.test(uri) ? uri : undefined;
    if (parsed.protocol === 'blob:') {
      const source = new URL(uri.slice(5));
      return ['http:', 'https:'].includes(source.protocol) && !!source.hostname && !source.username && !source.password ? uri : undefined;
    }
  } catch { return; }
}

/** Caller must supply the exact row from its fresh, authorized original-owner queue read. */
export function checkedCanvasTaskCandidate(binding: CanvasTaskBinding, value: unknown): CanvasTaskCandidate | undefined {
  if (!binding || !object(binding.owner) || !id(binding.taskId) || !id(binding.nodeId)) return;
  const owner = binding.owner;
  if (!ownerId(owner.actorId) || !ownerId(owner.novelId) || owner.projectId !== owner.novelId || !object(value)
    || value.id !== binding.taskId || value.novel_id !== owner.novelId || value.status !== 'SUCCEEDED'
    || value.contract !== undefined) return;
  if (owner.mode === 'collaboration') {
    if (![owner.workspaceId, owner.actorWorkspaceId, owner.storylineId, owner.branchId].every(ownerId)
      || owner.workspaceId !== owner.actorWorkspaceId || value.branch_id !== owner.branchId || value.owner_actor_id !== owner.actorId) return;
  } else if (owner.mode !== 'local' || [owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].some(field => field !== '')
    || value.branch_id !== null || value.owner_actor_id != null) return;
  if (!label(value.provider_id, 240) || !label(value.model_id, 2048) || !text(value.prompt, 8000)
    || typeof value.request_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.request_sha256)
    || typeof value.attempt !== 'number' || !Number.isSafeInteger(value.attempt) || value.attempt < 1 || !timestamp(value.updated_at)
    || !['PENDING', 'APPROVED'].includes(String(value.approval_status))) return;
  if (value.approval_status === 'APPROVED' ? !id(value.asset_id) : value.asset_id != null) return;
  // A malformed or unsupported URI still permits verified provenance, never a guessed preview.
  const sourceUri = typeof value.asset_uri === 'string' ? value.asset_uri : undefined;
  return Object.freeze({jobId: value.id as string, novelId: owner.novelId, nodeId: binding.nodeId,
    providerId: value.provider_id, modelId: value.model_id, prompt: value.prompt,
    requestSha256: value.request_sha256, attempt: value.attempt, updatedAt: value.updated_at,
    approvalStatus: value.approval_status as 'PENDING' | 'APPROVED',
    ...(value.approval_status === 'APPROVED' ? {assetId: value.asset_id as string} : {}),
    sourceUri, previewUri: checkedPreviewUri(sourceUri)});
}

/** Exact observed fields only; this is not a cryptographic proof of an immutable server revision. */
export function sameCanvasTaskCandidate(left: CanvasTaskCandidate | undefined, right: CanvasTaskCandidate | undefined): boolean {
  return !!left && !!right && (['jobId', 'novelId', 'nodeId', 'providerId', 'modelId', 'prompt', 'requestSha256',
    'attempt', 'updatedAt', 'approvalStatus', 'assetId', 'sourceUri', 'previewUri'] as const).every(key => left[key] === right[key]);
}
