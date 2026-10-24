import { checkedCanvasImageNodeBinding, canonicalImageNode, type CanvasImageNodeBinding } from './canvasImageNode';
import type { CanvasDefinition } from './studioCanvasViewClient';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';

/** A creation/recovery hint, never a grant, server identity or execution record. */
export type CanvasImageNodeCreateIntent = Omit<CanvasImageNodeBinding, 'contract' | 'canvas_id' | 'canvas_version' | 'canvas_digest'> & {
  contract: 'studio-canvas-image-node-create/1';
};
export type CanvasImageNodeCreateHint = { schema_version: 1; owner: StudioGraphDraftOwner; request_id: string; intent: CanvasImageNodeCreateIntent };
export type CanvasImageNodeCreateHintState = { state: 'absent' } | { state: 'present'; hint: CanvasImageNodeCreateHint; raw: string } | { state: 'blocked'; message: string };
const LIMIT = 8192;
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const exact = (value: Record<string, unknown>, names: string[]) => Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
const requestId = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(value);
function invalid(): never { throw new Error('空白位置创建意图无法核对；保留原记录，不会再次创建或入队。'); }
export function checkedCanvasImageNodeCreateIntent(value: unknown): CanvasImageNodeCreateIntent {
  if (!object(value) || !exact(value, ['contract', 'project_id', 'scope', 'incarnation', 'node_id', 'title', 'position', 'prompt_digest'])
    || value.contract !== 'studio-canvas-image-node-create/1') invalid();
  checkedCanvasImageNodeBinding({ ...value, contract: 'studio-canvas-image-node/1', canvas_id: 'syntax-check-only', canvas_version: 1, canvas_digest: '0'.repeat(64) });
  return structuredClone(value) as CanvasImageNodeCreateIntent;
}
export function emptyImageNodeDefinition(intent: CanvasImageNodeCreateIntent): CanvasDefinition {
  const value = checkedCanvasImageNodeCreateIntent(intent);
  return { schema_version: 1, title: value.title, cards: [], viewport: { x: 0, y: 0, zoom: 1 } };
}
function ownerIdentity(owner: StudioGraphDraftOwner) {
  const names = ['projectId', 'incarnation', 'actorId', 'actorWorkspaceId', 'mode', 'workspaceId', 'storylineId', 'branchId'];
  if (!object(owner) || !exact(owner, names) || names.some(name => typeof owner[name as keyof StudioGraphDraftOwner] !== 'string'
      || owner[name as keyof StudioGraphDraftOwner].length > 240 || /[\u0000-\u001f\u007f]/.test(owner[name as keyof StudioGraphDraftOwner]))
    || !['local','collaboration'].includes(owner.mode) || !owner.projectId || !owner.incarnation || !owner.actorId
    || owner.mode === 'local' && [owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].some(Boolean)
    || owner.mode === 'collaboration' && !owner.actorWorkspaceId) invalid();
  return names.map(name => owner[name as keyof StudioGraphDraftOwner]);
}
function ownerMatches(owner: StudioGraphDraftOwner, nodeId: string, intent: CanvasImageNodeCreateIntent) {
  ownerIdentity(owner);
  const scope = owner.mode === 'local' ? { mode: 'local', novel_id: owner.projectId }
    : { mode: 'collaboration', novel_id: owner.projectId, workspace_id: owner.workspaceId, storyline_id: owner.storylineId, branch_id: owner.branchId };
  if (intent.project_id !== owner.projectId || intent.incarnation !== owner.incarnation || intent.node_id !== nodeId
    || canonicalImageNode(intent.scope) !== canonicalImageNode(scope)) invalid();
}
export function canvasImageNodeCreateHintKey(owner: StudioGraphDraftOwner, nodeId: string): string {
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(nodeId)) invalid();
  return `studio-canvas-image-node-create:v1:${JSON.stringify([...ownerIdentity(owner), nodeId])}`;
}
function decode(raw: string, owner: StudioGraphDraftOwner, nodeId: string): CanvasImageNodeCreateHint {
  if (new TextEncoder().encode(raw).length > LIMIT) invalid();
  const value: unknown = JSON.parse(raw);
  if (!object(value) || !exact(value, ['schema_version', 'owner', 'request_id', 'intent']) || value.schema_version !== 1 || !requestId(value.request_id)
    || !object(value.owner) || canonicalImageNode(value.owner) !== canonicalImageNode(owner)) invalid();
  const intent = checkedCanvasImageNodeCreateIntent(value.intent); ownerMatches(owner, nodeId, intent);
  return { schema_version: 1, owner: structuredClone(owner), request_id: value.request_id, intent };
}
export function readCanvasImageNodeCreateHint(owner: StudioGraphDraftOwner, nodeId: string): CanvasImageNodeCreateHintState {
  try {
    const raw = localStorage.getItem(canvasImageNodeCreateHintKey(owner, nodeId));
    return raw === null ? { state: 'absent' } : { state: 'present', hint: decode(raw, owner, nodeId), raw };
  } catch { return { state: 'blocked', message: '无法核对本浏览器的空白位置创建记录；保留原记录，不能再次创建或入队。' }; }
}
export function persistCanvasImageNodeCreateHint(owner: StudioGraphDraftOwner, nodeId: string, id: string, value: CanvasImageNodeCreateIntent): Extract<CanvasImageNodeCreateHintState, { state: 'present' }> {
  if (!requestId(id)) invalid();
  const intent = checkedCanvasImageNodeCreateIntent(value); ownerMatches(owner, nodeId, intent);
  if (readCanvasImageNodeCreateHint(owner, nodeId).state !== 'absent') invalid();
  const hint: CanvasImageNodeCreateHint = { schema_version: 1, owner: structuredClone(owner), request_id: id, intent };
  const raw = canonicalImageNode(hint);
  if (new TextEncoder().encode(raw).length > LIMIT) invalid();
  localStorage.setItem(canvasImageNodeCreateHintKey(owner, nodeId), raw);
  const result = readCanvasImageNodeCreateHint(owner, nodeId);
  if (result.state !== 'present' || result.raw !== raw) invalid();
  return result;
}
export function clearCanvasImageNodeCreateHint(owner: StudioGraphDraftOwner, nodeId: string, expectedRaw: string): boolean {
  try {
    const current = readCanvasImageNodeCreateHint(owner, nodeId);
    if (current.state !== 'present' || current.raw !== expectedRaw) return false;
    localStorage.removeItem(canvasImageNodeCreateHintKey(owner, nodeId));
    return localStorage.getItem(canvasImageNodeCreateHintKey(owner, nodeId)) === null;
  } catch { return false; }
}
