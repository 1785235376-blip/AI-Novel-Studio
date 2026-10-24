import {getCollaborationContext} from '../../api';
import {useLocalHostSession} from '../../localHostSession';
import {canvasStorageKey} from '../canvas/RebuildCanvas';

/** Browser navigation hint only. No credential, execution state or server canvas claim. */
export type CanvasTaskOwner = {
  mode: 'local' | 'collaboration'; actorId: string; actorWorkspaceId: string;
  workspaceId: string; projectId: string; storylineId: string; branchId: string; novelId: string;
};
/** Browser-local reference to an explicitly observed approved asset, never an approval receipt. */
export type CanvasTaskAdoption = {
  assetId: string; assetVersion: number; assetSha256: string;
  /** Client observation fingerprint only; not an immutable server job revision. */
  jobObservationSha256: string;
};
export type CanvasTaskBinding = {schema_version: 1; owner: CanvasTaskOwner; nodeId: string; taskId: string; adoption?: CanvasTaskAdoption};
const OWNER_KEYS = ['mode', 'actorId', 'actorWorkspaceId', 'workspaceId', 'projectId', 'storylineId', 'branchId', 'novelId'] as const;
const safeId = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240 && value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value);
const taskId = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value);
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const ADOPTION_KEYS = ['assetId', 'assetVersion', 'assetSha256', 'jobObservationSha256'] as const;
const hex = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const checkedAdoption = (value: unknown): value is CanvasTaskAdoption => object(value)
  && Object.keys(value).length === ADOPTION_KEYS.length && ADOPTION_KEYS.every(key => Object.hasOwn(value, key))
  && taskId(value.assetId) && Number.isSafeInteger(value.assetVersion) && (value.assetVersion as number) > 0
  && hex(value.assetSha256) && hex(value.jobObservationSha256);
const checkedOwner = (value: unknown): value is CanvasTaskOwner => {
  if (!object(value) || Object.keys(value).length !== OWNER_KEYS.length || OWNER_KEYS.some(key => !Object.hasOwn(value, key))
    || !safeId(value.actorId) || !safeId(value.projectId) || value.projectId !== value.novelId) return false;
  if (value.mode === 'local') return [value.actorWorkspaceId, value.workspaceId, value.storylineId, value.branchId].every(item => item === '');
  return value.mode === 'collaboration' && [value.actorWorkspaceId, value.workspaceId, value.storylineId, value.branchId].every(safeId)
    && value.actorWorkspaceId === value.workspaceId;
};
const ownerIdentity = (owner: CanvasTaskOwner) => JSON.stringify(OWNER_KEYS.map(key => owner[key]));
const checkedBinding = (value: unknown): value is CanvasTaskBinding => object(value)
  && Object.keys(value).length === (Object.hasOwn(value, 'adoption') ? 5 : 4)
  && ['schema_version', 'owner', 'nodeId', 'taskId'].every(key => Object.hasOwn(value, key))
  && value.schema_version === 1 && checkedOwner(value.owner) && taskId(value.nodeId) && taskId(value.taskId)
  && (!Object.hasOwn(value, 'adoption') || checkedAdoption(value.adoption));
const sameBinding = (left: CanvasTaskBinding | undefined, right: CanvasTaskBinding) => !!left
  && ownerIdentity(left.owner) === ownerIdentity(right.owner) && left.nodeId === right.nodeId && left.taskId === right.taskId
  && (left.adoption === undefined && right.adoption === undefined || !!left.adoption && !!right.adoption
    && ADOPTION_KEYS.every(key => left.adoption![key] === right.adoption![key]));
const bindingEvent = 'poemseed:canvas-task-binding';
const prefix = 'poemseed.rebuild.image-task.v1:';

/** Use the actual transport identity. Anonymous or partial contexts cannot own durable hints. */
export function captureCanvasTaskOwner(novelId: string): CanvasTaskOwner | undefined {
  if (!safeId(novelId)) return;
  const context = getCollaborationContext(), host = useLocalHostSession.getState();
  if (context.sessionToken || context.actor || context.scope) {
    const {actor, scope} = context;
    if (!context.sessionToken || !actor || !scope) return;
    const owner: CanvasTaskOwner = {mode: 'collaboration', actorId: actor.id, actorWorkspaceId: actor.workspaceId,
      workspaceId: scope.workspaceId, projectId: scope.projectId, storylineId: scope.storylineId, branchId: scope.branchId, novelId};
    return checkedOwner(owner) ? owner : undefined;
  }
  if (!host.token || !safeId(host.actorId) || context.localHostToken !== undefined && context.localHostToken !== host.token) return;
  // Legacy File/local projects are addressed by novelId and have no collaboration branch.
  return {mode: 'local', actorId: host.actorId, actorWorkspaceId: '', workspaceId: '', projectId: novelId, storylineId: '', branchId: '', novelId};
}

export const canvasTaskBindingKey = (owner: CanvasTaskOwner, nodeId: string) => `${prefix}${ownerIdentity(owner)}:${JSON.stringify(nodeId)}`;

/** Require the exact existing image node; never choose a title, selection or replacement node. */
export function imageDraftNodeExists(novelId: string, nodeId: string): boolean {
  if (!safeId(novelId) || !taskId(nodeId)) return false;
  try {
    const raw = localStorage.getItem(canvasStorageKey('image', novelId));
    if (!raw || raw.length > 2_000_000) return false;
    const graph: unknown = JSON.parse(raw);
    if (!object(graph) || !Array.isArray(graph.nodes)) return false;
    const matches = graph.nodes.filter(node => object(node) && node.id === nodeId);
    return matches.length === 1 && matches[0].t === 'image_generate';
  } catch { return false; }
}

export function readCanvasTaskBinding(owner: CanvasTaskOwner, nodeId: string): CanvasTaskBinding | undefined {
  if (!checkedOwner(owner) || !taskId(nodeId) || !imageDraftNodeExists(owner.novelId, nodeId)) return;
  const current = captureCanvasTaskOwner(owner.novelId);
  if (!current || ownerIdentity(current) !== ownerIdentity(owner)) return;
  try {
    const raw = localStorage.getItem(canvasTaskBindingKey(owner, nodeId));
    if (!raw || raw.length > 8_000) return;
    const value: unknown = JSON.parse(raw);
    if (!checkedBinding(value) || ownerIdentity(value.owner) !== ownerIdentity(owner) || value.nodeId !== nodeId) return;
    return {schema_version: 1, owner: {...owner}, nodeId, taskId: value.taskId,
      ...(value.adoption ? {adoption: {...value.adoption}} : {})};
  } catch { return; }
}

/** Caller also fences its request epoch/source lifetime before invoking this synchronous write. */
export function writeCanvasTaskBinding(owner: CanvasTaskOwner, nodeId: string, jobId: string): boolean {
  if (!checkedOwner(owner) || !taskId(nodeId) || !taskId(jobId)) return false;
  const current = captureCanvasTaskOwner(owner.novelId);
  if (!current || ownerIdentity(current) !== ownerIdentity(owner) || !imageDraftNodeExists(owner.novelId, nodeId)) return false;
  try {
    const binding: CanvasTaskBinding = {schema_version: 1, owner: {...owner}, nodeId, taskId: jobId};
    const key = canvasTaskBindingKey(owner, nodeId), serialized = JSON.stringify(binding);
    localStorage.setItem(key, serialized);
    if (localStorage.getItem(key) !== serialized) return false;
    window.dispatchEvent(new Event(bindingEvent));
    return true;
  } catch { return false; }
}

/**
 * Store an explicit local association only. The caller must first revalidate the
 * authorized job observation, asset metadata and bytes; this cache grants no review
 * or execution authority and cannot restore a preview/load confirmation on reopen.
 */
export function writeCanvasTaskAdoption(expectedBinding: CanvasTaskBinding, adoption: CanvasTaskAdoption, isCurrent: () => boolean): boolean {
  try {
    if (!checkedBinding(expectedBinding) || !checkedAdoption(adoption) || !isCurrent()) return false;
    const current = readCanvasTaskBinding(expectedBinding.owner, expectedBinding.nodeId);
    if (!sameBinding(current, expectedBinding)) return false;
    const binding: CanvasTaskBinding = {schema_version: 1, owner: {...expectedBinding.owner}, nodeId: expectedBinding.nodeId,
      taskId: expectedBinding.taskId, adoption: {...adoption}};
    const key = canvasTaskBindingKey(binding.owner, binding.nodeId), serialized = JSON.stringify(binding);
    // Recheck the caller's prompt/session/observation fence immediately before the write.
    if (!isCurrent()) return false;
    localStorage.setItem(key, serialized);
    if (localStorage.getItem(key) !== serialized) return false;
    window.dispatchEvent(new Event(bindingEvent));
    return true;
  } catch { return false; }
}

/** Same-page writes and external tab changes retire the caller's current snapshot. */
export function subscribeCanvasTaskBindings(listener: () => void): () => void {
  const storage = (event: StorageEvent) => { if (event.key === null || event.key.startsWith(prefix) || event.key.startsWith('poemseed.rebuild.canvas.image.')) listener(); };
  window.addEventListener(bindingEvent, listener);
  window.addEventListener('storage', storage);
  return () => { window.removeEventListener(bindingEvent, listener); window.removeEventListener('storage', storage); };
}
