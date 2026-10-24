import { assertCanvasImageNodeJob, canonicalImageNode, checkedCanvasImageNodeBinding, type CanvasImageNodeBinding } from './canvasImageNode';
import { canvasImageNodeCreateHintKey } from './canvasImageNodeCreateIntent';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { ProductionJob } from './studioProductionClient';

/** Recovery metadata only; original Job/Canvas owners supply all authority. */
export type CanvasImageNodeQueueHint = { schema_version: 1; owner: StudioGraphDraftOwner; request_id: string; request_digest: string; binding: CanvasImageNodeBinding };
export type CanvasImageNodeQueueHintState = { state: 'absent' } | { state: 'present'; hint: CanvasImageNodeQueueHint; raw: string } | { state: 'blocked'; message: string };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const exact = (value: Record<string, unknown>, names: string[]) => Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
const requestId = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(value);
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function invalid(): never { throw new Error('原图片任务入队意图无法核对；保留原记录，不会再次入队。'); }
export function canvasImageNodeQueueHintKey(owner: StudioGraphDraftOwner, nodeId: string): string {
  return canvasImageNodeCreateHintKey(owner, nodeId).replace('studio-canvas-image-node-create:', 'studio-canvas-image-node-queue:');
}
function checkedBinding(owner: StudioGraphDraftOwner, nodeId: string, value: unknown) {
  canvasImageNodeQueueHintKey(owner, nodeId);
  const binding = checkedCanvasImageNodeBinding(value);
  const scope = owner.mode === 'local' ? { mode: 'local', novel_id: owner.projectId }
    : { mode: 'collaboration', novel_id: owner.projectId, workspace_id: owner.workspaceId, storyline_id: owner.storylineId, branch_id: owner.branchId };
  if (binding.project_id !== owner.projectId || binding.incarnation !== owner.incarnation || binding.node_id !== nodeId
    || canonicalImageNode(binding.scope) !== canonicalImageNode(scope)) invalid();
  return binding;
}
function decode(raw: string, owner: StudioGraphDraftOwner, nodeId: string): CanvasImageNodeQueueHint {
  if (new TextEncoder().encode(raw).length > 8192) invalid();
  const value: unknown = JSON.parse(raw);
  if (!object(value) || !exact(value, ['schema_version', 'owner', 'request_id', 'request_digest', 'binding']) || value.schema_version !== 1
    || canonicalImageNode(value.owner) !== canonicalImageNode(owner) || !requestId(value.request_id) || !digest(value.request_digest)) invalid();
  return { schema_version: 1, owner: structuredClone(owner), request_id: value.request_id, request_digest: value.request_digest,
    binding: checkedBinding(owner, nodeId, value.binding) };
}
export function readCanvasImageNodeQueueHint(owner: StudioGraphDraftOwner, nodeId: string): CanvasImageNodeQueueHintState {
  try { const raw = localStorage.getItem(canvasImageNodeQueueHintKey(owner, nodeId));
    return raw === null ? { state: 'absent' } : { state: 'present', hint: decode(raw, owner, nodeId), raw };
  } catch { return { state: 'blocked', message: '本浏览器的原任务入队记录无法核对；保留原记录，不能重新创建位置或入队。' }; }
}
export function persistCanvasImageNodeQueueHint(owner: StudioGraphDraftOwner, nodeId: string, id: string, sha: string, value: CanvasImageNodeBinding): Extract<CanvasImageNodeQueueHintState, { state: 'present' }> {
  if (!requestId(id) || !digest(sha) || readCanvasImageNodeQueueHint(owner, nodeId).state !== 'absent') invalid();
  const hint: CanvasImageNodeQueueHint = { schema_version: 1, owner: structuredClone(owner), request_id: id, request_digest: sha,
    binding: checkedBinding(owner, nodeId, value) };
  const raw = canonicalImageNode(hint); if (new TextEncoder().encode(raw).length > 8192) invalid();
  localStorage.setItem(canvasImageNodeQueueHintKey(owner, nodeId), raw);
  const actual = readCanvasImageNodeQueueHint(owner, nodeId);
  if (actual.state !== 'present' || actual.raw !== raw) invalid(); return actual;
}
export function assertCanvasImageNodeQueueReceipt(hint: CanvasImageNodeQueueHint, job: ProductionJob): void {
  assertCanvasImageNodeJob(hint.binding, job);
  if (job.request_id !== hint.request_id || job.request_digest !== hint.request_digest) invalid();
}
export function clearCanvasImageNodeQueueHint(owner: StudioGraphDraftOwner, nodeId: string, expectedRaw: string): boolean {
  try {
    const actual = readCanvasImageNodeQueueHint(owner, nodeId); if (actual.state !== 'present' || actual.raw !== expectedRaw) return false;
    localStorage.removeItem(canvasImageNodeQueueHintKey(owner, nodeId));
    return localStorage.getItem(canvasImageNodeQueueHintKey(owner, nodeId)) === null;
  } catch { return false; }
}
