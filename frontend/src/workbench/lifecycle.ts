/**
 * [HERMIA-FE-20261022 slice M1-1] Lifecycle epoch + confirmation binding (task book §11.2).
 * Any context change (project/document/node/job/client/identity/permission/selection)
 * bumps a monotonically increasing epoch. A→B→A yields a NEW epoch, so stale
 * callbacks/confirmations from the first "A" can never be revived by comparing IDs.
 * Pure frontend; no backend contract is changed. Server-side CAS/idempotency still authoritative.
 */
export interface LifecycleContext {
  projectId: string | null;
  projectInstanceId?: string | null;
  documentId?: string | null;
  nodeId?: string | null;
  jobId?: string | null;
  clientId?: string | null;
  identity?: string | null;
  permissionDigest?: string | null;
}
export interface LifecycleToken { readonly epoch: number; readonly context: Readonly<LifecycleContext>; }

export class LifecycleTracker {
  private epoch = 0;
  private ctx: LifecycleContext = {projectId: null};
  current(): LifecycleToken { return {epoch: this.epoch, context: {...this.ctx}}; }
  /** Always bumps when any field differs, including a return to a previous value (ABA). */
  update(next: LifecycleContext): LifecycleToken {
    const keys = new Set([...Object.keys(this.ctx), ...Object.keys(next)]) as Set<keyof LifecycleContext>;
    let changed = false;
    for (const k of keys) if ((this.ctx[k] ?? null) !== (next[k] ?? null)) changed = true;
    if (changed) { this.epoch += 1; this.ctx = {...next}; }
    return this.current();
  }
  /** Forced invalidation (e.g. re-login, permission revoked event). */
  invalidate(): LifecycleToken { this.epoch += 1; return this.current(); }
  isCurrent(token: LifecycleToken): boolean { return token.epoch === this.epoch; }
}

/** Confirmation bound to lifecycle + action + target + version/digest + input digest. */
export interface ConfirmationBinding {
  epoch: number; actionId: string; targetId: string; targetVersion: string | null; inputDigest: string;
}
export function bindConfirmation(token: LifecycleToken, actionId: string, targetId: string, targetVersion: string | null, input: unknown): ConfirmationBinding {
  return {epoch: token.epoch, actionId, targetId, targetVersion, inputDigest: stableDigest(input)};
}
export type ConfirmationCheck = {ok: true} | {ok: false; reason: 'lifecycle-changed' | 'action-mismatch' | 'target-mismatch' | 'version-changed' | 'input-changed'};
export function checkConfirmation(b: ConfirmationBinding, tracker: LifecycleTracker, actionId: string, targetId: string, targetVersion: string | null, input: unknown): ConfirmationCheck {
  if (b.epoch !== tracker.current().epoch) return {ok: false, reason: 'lifecycle-changed'};
  if (b.actionId !== actionId) return {ok: false, reason: 'action-mismatch'};
  if (b.targetId !== targetId) return {ok: false, reason: 'target-mismatch'};
  if (b.targetVersion !== targetVersion) return {ok: false, reason: 'version-changed'};
  if (b.inputDigest !== stableDigest(input)) return {ok: false, reason: 'input-changed'};
  return {ok: true};
}
/** Deterministic, non-cryptographic digest of JSON-like input (UI binding only, NOT a security digest). */
export function stableDigest(value: unknown): string {
  const s = canonical(value); let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return `fnv1a:${h.toString(16).padStart(8, '0')}:${s.length}`;
}
function canonical(v: unknown): string {
  if (v === null || typeof v !== 'object') return JSON.stringify(v ?? null);
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  return `{${Object.keys(v as object).sort().map(k => `${JSON.stringify(k)}:${canonical((v as Record<string, unknown>)[k])}`).join(',')}}`;
}
/** Guard a late async result: apply only if the token is still current. */
export function guardLate<T>(tracker: LifecycleTracker, token: LifecycleToken, apply: (v: T) => void): (v: T) => boolean {
  return (v: T) => { if (!tracker.isCurrent(token)) return false; apply(v); return true; };
}
