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
/** Ordered browser observations, not server revisions, approval events or historical timestamps. */
export type CanvasTaskHistoryEntry = {
  eventId: string; revision: number; operation: 'import' | 'queue' | 'adopt' | 'restore';
  taskId: string; adoption?: CanvasTaskAdoption; sourceEventId?: string;
};
type BindingFields = {owner: CanvasTaskOwner; nodeId: string; taskId: string; adoption?: CanvasTaskAdoption};
export type CanvasTaskBinding = BindingFields & (
  {schema_version: 1; revision?: never; history?: never}
  | {schema_version: 2; revision: number; history: CanvasTaskHistoryEntry[]}
);
export const MAX_CANVAS_TASK_HISTORY = 32;
const MAX_JOURNAL_LENGTH = 64 * 1024;
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
const sameAdoption = (left: CanvasTaskAdoption | undefined, right: CanvasTaskAdoption | undefined) => left === undefined && right === undefined
  || !!left && !!right && ADOPTION_KEYS.every(key => left[key] === right[key]);
const exactKeys = (value: Record<string, unknown>, required: string[], optional: string[] = []) => required.every(key => Object.hasOwn(value, key))
  && Object.keys(value).every(key => required.includes(key) || optional.includes(key));
const copyEntry = (entry: CanvasTaskHistoryEntry): CanvasTaskHistoryEntry => ({eventId: entry.eventId, revision: entry.revision,
  operation: entry.operation, taskId: entry.taskId, ...(entry.adoption ? {adoption: {...entry.adoption}} : {}),
  ...(entry.sourceEventId ? {sourceEventId: entry.sourceEventId} : {})});
function checkedBinding(value: unknown): value is CanvasTaskBinding {
  if (!object(value) || !checkedOwner(value.owner) || !taskId(value.nodeId) || !taskId(value.taskId)
    || Object.hasOwn(value, 'adoption') && !checkedAdoption(value.adoption)) return false;
  const core = ['schema_version', 'owner', 'nodeId', 'taskId'];
  if (value.schema_version === 1) return exactKeys(value, core, ['adoption']);
  if (value.schema_version !== 2 || !exactKeys(value, [...core, 'revision', 'history'], ['adoption'])
    || !Number.isSafeInteger(value.revision) || !Array.isArray(value.history) || value.history.length < 1
    || value.history.length > MAX_CANVAS_TASK_HISTORY || value.revision !== value.history.length) return false;
  const prior: CanvasTaskHistoryEntry[] = [], events = new Set<string>();
  for (const [index, entry] of value.history.entries()) {
    if (!object(entry) || !exactKeys(entry, ['eventId', 'revision', 'operation', 'taskId'], ['adoption', 'sourceEventId'])
      || !taskId(entry.eventId) || events.has(entry.eventId) || entry.revision !== index + 1 || !taskId(entry.taskId)
      || Object.hasOwn(entry, 'adoption') && !checkedAdoption(entry.adoption)) return false;
    if (entry.operation === 'import') {
      if (index !== 0 || Object.hasOwn(entry, 'sourceEventId')) return false;
    } else if (entry.operation === 'queue') {
      if (Object.hasOwn(entry, 'adoption') || Object.hasOwn(entry, 'sourceEventId')) return false;
    } else if (entry.operation === 'adopt') {
      if (!index || !checkedAdoption(entry.adoption) || Object.hasOwn(entry, 'sourceEventId') || entry.taskId !== prior[index - 1].taskId) return false;
    } else if (entry.operation === 'restore') {
      const source = prior.find(row => row.eventId === entry.sourceEventId);
      if (!index || !taskId(entry.sourceEventId) || !source?.adoption || !checkedAdoption(entry.adoption)
        || source.taskId !== entry.taskId || !sameAdoption(source.adoption, entry.adoption)
        || prior[index - 1].taskId === entry.taskId && sameAdoption(prior[index - 1].adoption, entry.adoption)) return false;
    } else return false;
    events.add(entry.eventId); prior.push(entry as CanvasTaskHistoryEntry);
  }
  const tail = prior[prior.length - 1];
  return value.taskId === tail.taskId && sameAdoption(value.adoption as CanvasTaskAdoption | undefined, tail.adoption);
}
const canonical = (value: unknown): string => JSON.stringify(value, (_key, item: unknown) => object(item)
  ? Object.fromEntries(Object.entries(item).sort(([left], [right]) => left.localeCompare(right))) : item);
const sameBinding = (left: CanvasTaskBinding | undefined, right: CanvasTaskBinding) => !!left && canonical(left) === canonical(right);
const copyBinding = (value: CanvasTaskBinding): CanvasTaskBinding => {
  const core: BindingFields = {owner: {...value.owner}, nodeId: value.nodeId, taskId: value.taskId,
    ...(value.adoption ? {adoption: {...value.adoption}} : {})};
  return value.schema_version === 2 ? {...core, schema_version: 2, revision: value.revision, history: value.history.map(copyEntry)}
    : {...core, schema_version: 1};
};
const bindingEvent = 'poemseed:canvas-task-binding';
// Keep the existing owner/node key even when its validated payload upgrades to schema 2.
const prefix = 'poemseed.rebuild.image-task.v1:';
type StoredBinding = {state: 'missing'} | {state: 'invalid'} | {state: 'valid'; value: CanvasTaskBinding};
const sameStored = (left: StoredBinding, right: StoredBinding) => left.state === 'missing' && right.state === 'missing'
  || left.state === 'valid' && right.state === 'valid' && sameBinding(left.value, right.value);

function storedBinding(owner: CanvasTaskOwner, nodeId: string): StoredBinding {
  try {
    const raw = localStorage.getItem(canvasTaskBindingKey(owner, nodeId));
    if (raw === null) return {state: 'missing'};
    if (!raw || raw.length > MAX_JOURNAL_LENGTH) return {state: 'invalid'};
    const value: unknown = JSON.parse(raw);
    if (!checkedBinding(value) || value.schema_version === 1 && raw.length > 8_000
      || ownerIdentity(value.owner) !== ownerIdentity(owner) || value.nodeId !== nodeId) return {state: 'invalid'};
    return {state: 'valid', value: copyBinding(value)};
  } catch { return {state: 'invalid'}; }
}

function newEventId(history: CanvasTaskHistoryEntry[]): string | undefined {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const crypto = globalThis.crypto;
    const id = crypto?.randomUUID ? crypto.randomUUID() : crypto?.getRandomValues
      ? Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('') : undefined;
    if (taskId(id) && !history.some(entry => entry.eventId === id)) return id;
  }
}

function appendBinding(owner: CanvasTaskOwner, nodeId: string, previous: CanvasTaskBinding | undefined,
  operation: 'queue' | 'adopt' | 'restore', jobId: string, adoption?: CanvasTaskAdoption, sourceEventId?: string): CanvasTaskBinding | undefined {
  const history = previous?.schema_version === 2 ? previous.history.map(copyEntry) : [];
  if (previous?.schema_version === 1) {
    const eventId = newEventId(history);
    if (!eventId) return;
    // Import means first observed by this journal, never a reconstruction of past adoption or time.
    history.push({eventId, revision: 1, operation: 'import', taskId: previous.taskId,
      ...(previous.adoption ? {adoption: {...previous.adoption}} : {})});
  }
  if (history.length >= MAX_CANVAS_TASK_HISTORY) return;
  const eventId = newEventId(history);
  if (!eventId) return;
  history.push({eventId, revision: history.length + 1, operation, taskId: jobId,
    ...(adoption ? {adoption: {...adoption}} : {}), ...(sourceEventId ? {sourceEventId} : {})});
  const next: CanvasTaskBinding = {schema_version: 2, owner: {...owner}, nodeId, taskId: jobId,
    ...(adoption ? {adoption: {...adoption}} : {}), revision: history.length, history};
  return checkedBinding(next) ? next : undefined;
}

function persistBinding(next: CanvasTaskBinding, expected: StoredBinding, isCurrent: () => boolean): boolean {
  const owner = captureCanvasTaskOwner(next.owner.novelId);
  if (!owner || ownerIdentity(owner) !== ownerIdentity(next.owner) || !imageDraftNodeExists(owner.novelId, next.nodeId)
    || !sameStored(storedBinding(owner, next.nodeId), expected)) return false;
  const key = canvasTaskBindingKey(owner, next.nodeId), serialized = JSON.stringify(next);
  if (serialized.length > MAX_JOURNAL_LENGTH || !isCurrent()) return false;
  localStorage.setItem(key, serialized);
  if (localStorage.getItem(key) !== serialized) return false;
  window.dispatchEvent(new Event(bindingEvent));
  return true;
}

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
  const stored = storedBinding(owner, nodeId);
  return stored.state === 'valid' ? stored.value : undefined;
}

/** Caller also fences its request epoch/source lifetime before invoking this synchronous write. */
export function writeCanvasTaskBinding(owner: CanvasTaskOwner, nodeId: string, jobId: string): boolean {
  if (!checkedOwner(owner) || !taskId(nodeId) || !taskId(jobId)) return false;
  const current = captureCanvasTaskOwner(owner.novelId);
  if (!current || ownerIdentity(current) !== ownerIdentity(owner) || !imageDraftNodeExists(owner.novelId, nodeId)) return false;
  try {
    const previous = storedBinding(owner, nodeId);
    if (previous.state === 'invalid') return false;
    const next = appendBinding(owner, nodeId, previous.state === 'valid' ? previous.value : undefined, 'queue', jobId);
    return !!next && persistBinding(next, previous, () => true);
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
    const previous = storedBinding(expectedBinding.owner, expectedBinding.nodeId);
    if (previous.state !== 'valid' || !sameBinding(previous.value, expectedBinding)) return false;
    const next = appendBinding(expectedBinding.owner, expectedBinding.nodeId, previous.value, 'adopt', expectedBinding.taskId, adoption);
    return !!next && persistBinding(next, previous, isCurrent);
  } catch { return false; }
}

/** Restore only after the caller freshly verifies this exact historical task and all asset pins. */
export function restoreCanvasTaskAdoption(expectedBinding: CanvasTaskBinding, targetEntry: CanvasTaskHistoryEntry,
  freshAdoption: CanvasTaskAdoption, isCurrent: () => boolean): boolean {
  try {
    if (!checkedBinding(expectedBinding) || expectedBinding.schema_version !== 2 || !checkedAdoption(freshAdoption) || !isCurrent()) return false;
    if (!object(targetEntry) || !exactKeys(targetEntry, ['eventId', 'revision', 'operation', 'taskId'], ['adoption', 'sourceEventId'])
      || !checkedAdoption(targetEntry.adoption) || Object.hasOwn(targetEntry, 'sourceEventId') && !taskId(targetEntry.sourceEventId)) return false;
    const source = expectedBinding.history.find(entry => entry.eventId === targetEntry?.eventId);
    if (!source?.adoption || canonical(source) !== canonical(targetEntry) || !sameAdoption(source.adoption, freshAdoption)
      || expectedBinding.taskId === source.taskId && sameAdoption(expectedBinding.adoption, source.adoption)) return false;
    const previous = storedBinding(expectedBinding.owner, expectedBinding.nodeId);
    if (previous.state !== 'valid' || !sameBinding(previous.value, expectedBinding)) return false;
    const next = appendBinding(expectedBinding.owner, expectedBinding.nodeId, previous.value, 'restore', source.taskId, source.adoption, source.eventId);
    return !!next && persistBinding(next, previous, isCurrent);
  } catch { return false; }
}

/** Same-page writes and external tab changes retire the caller's current snapshot. */
export function subscribeCanvasTaskBindings(listener: () => void): () => void {
  const storage = (event: StorageEvent) => { if (event.key === null || event.key.startsWith(prefix) || event.key.startsWith('poemseed.rebuild.canvas.image.')) listener(); };
  window.addEventListener(bindingEvent, listener);
  window.addEventListener('storage', storage);
  return () => { window.removeEventListener(bindingEvent, listener); window.removeEventListener('storage', storage); };
}
