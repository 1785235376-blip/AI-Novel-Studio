import type {CanvasTaskOwner} from '../rebuild/image/canvasTaskBinding';
import type {ImageJobExecutionSnapshot} from './imageJobExecution';

type Pending = {schema_version: 1; jobId: string; requestSha256: string; attempt: number; updatedAt: string; operation: string};
type Read = {kind: 'none'} | {kind: 'unavailable'} | {kind: 'pending'; value: Pending; raw: string};
const key = (owner: CanvasTaskOwner, jobId: string) => 'poemseed.image.execute.pending.v1.' + JSON.stringify([
  owner.mode, owner.actorId, owner.actorWorkspaceId, owner.workspaceId, owner.projectId, owner.storylineId, owner.branchId, owner.novelId, jobId,
]);
/** A navigation/recovery marker, never an execution receipt or authorization credential. */
export function readImageExecutionPending(owner: CanvasTaskOwner, jobId: string): Read {
  try {
    const raw = localStorage.getItem(key(owner, jobId));
    if (raw === null) return {kind: 'none'};
    const value = JSON.parse(raw) as Pending;
    if (!value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).sort().join(',') !== 'attempt,jobId,operation,requestSha256,schema_version,updatedAt'
      || value.schema_version !== 1 || value.jobId !== jobId || typeof value.requestSha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.requestSha256)
      || !Number.isSafeInteger(value.attempt) || value.attempt < 0 || typeof value.updatedAt !== 'string' || value.updatedAt.length > 80
      || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(value.updatedAt) || !Number.isFinite(Date.parse(value.updatedAt))
      || typeof value.operation !== 'string' || !/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(value.operation)) return {kind: 'unavailable'};
    return {kind: 'pending', value, raw};
  } catch { return {kind: 'unavailable'}; }
}
export function pendingMatchesSnapshot(pending: Pending, snapshot: ImageJobExecutionSnapshot): boolean {
  return pending.jobId === snapshot.jobId && pending.requestSha256 === snapshot.requestSha256
    && pending.attempt === snapshot.attempt && pending.updatedAt === snapshot.updatedAt;
}
export function markImageExecutionPending(owner: CanvasTaskOwner, snapshot: ImageJobExecutionSnapshot): string | undefined {
  if (readImageExecutionPending(owner, snapshot.jobId).kind !== 'none') return;
  try {
    const raw = JSON.stringify({schema_version: 1, jobId: snapshot.jobId, requestSha256: snapshot.requestSha256,
      attempt: snapshot.attempt, updatedAt: snapshot.updatedAt, operation: crypto.randomUUID()} satisfies Pending);
    localStorage.setItem(key(owner, snapshot.jobId), raw);
    return localStorage.getItem(key(owner, snapshot.jobId)) === raw ? raw : undefined;
  } catch { return; }
}
/** Best-effort compare-before-clear; localStorage does not provide a cross-tab CAS. */
export function clearImageExecutionPending(owner: CanvasTaskOwner, jobId: string, expectedRaw: string): boolean {
  try {
    if (localStorage.getItem(key(owner, jobId)) !== expectedRaw) return false;
    localStorage.removeItem(key(owner, jobId));
    return localStorage.getItem(key(owner, jobId)) === null;
  } catch { return false; }
}
