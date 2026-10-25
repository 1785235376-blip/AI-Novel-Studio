/**
 * [HERMIA-FE-20261025 U1-M1] Identity resolution + scope leases (task book t150u §M1).
 * - Real identity ONLY when the collaboration bootstrap has produced an actor id AND a complete collaboration scope
 *   AND a project is selected. Otherwise the workspace is session-only ("仅本次会话"); no user id is ever invented.
 * - projectInstanceId = workspace/storyline/branch of the collaboration scope + the server project id. A project
 *   deleted and recreated with the same NAME gets a new server id ⇒ new scope ⇒ nothing of the old one is reused.
 * - Each activation of a scope gets a fresh ScopeLease. A→B→A ⇒ the first A lease stays retired forever, so its late
 *   responses, subscriptions, deferred saves and confirmation callbacks can never revive.
 */
import type {LayoutScope} from '../../workbench/layout';
import type {ScopeLease, WorkspaceIdentity} from '../contracts';

export interface IdentityInput {
  /** Actor id from api.bootstrap (store.actor.id). Undefined when no real session. */
  actorId?: string | null;
  collabScope?: {workspaceId?: string; projectId?: string; storylineId?: string; branchId?: string} | null;
  /** Selected project/novel id (server id). */
  projectId: string | null;
  /** Client namespace (store/App `namespace`); a different client is a different lease, not a different identity. */
  clientId?: string | null;
}
const blank = (v: unknown) => typeof v !== 'string' || !v.trim();
const PLACEHOLDER = new Set(['local', 'local-author', 'preview', 'unknown', 'anonymous', 'default', 'no-project']);
const fake = (v: string) => PLACEHOLDER.has(v.trim().toLowerCase());

export function resolveWorkspaceIdentity(i: IdentityInput): WorkspaceIdentity {
  const client = i.clientId ?? '';
  const sessionKey = (reason: string) => `session\u0000${reason}\u0000${i.projectId ?? ''}\u0000${client}`;
  if (blank(i.actorId) || fake(i.actorId!)) return {kind: 'session', reason: 'no-actor', key: sessionKey('no-actor')};
  if (blank(i.projectId) || fake(i.projectId!)) return {kind: 'session', reason: 'no-project', key: sessionKey('no-project')};
  const c = i.collabScope;
  if (!c || blank(c.workspaceId) || blank(c.storylineId) || blank(c.branchId)) return {kind: 'session', reason: 'no-instance', key: sessionKey('no-instance')};
  // [HERMIA-FE-20261025 U1fix P2] a collaboration scope bound to another project is never mixed into this project's scope.
  if (!blank(c.projectId) && c.projectId !== i.projectId) return {kind: 'session', reason: 'scope-mismatch', key: sessionKey('scope-mismatch')};
  const scope: LayoutScope = {userId: i.actorId!, projectId: i.projectId!, projectInstanceId: `${c.workspaceId}/${c.storylineId}/${c.branchId}`};
  return {kind: 'real', scope, key: `real\u0000${scope.userId}\u0000${scope.projectId}\u0000${scope.projectInstanceId}\u0000${client}`};
}

// [HERMIA-FE-20261025 M10-purgefix] user-level identity (no project involved) for per-user housekeeping such as purge.
// Same actor rules as resolveWorkspaceIdentity; never fabricates a user.
export function resolveWorkspaceUser(actorId: string | null | undefined): string | null {
  return blank(actorId) || fake(actorId!) ? null : actorId!;
}

export const IDENTITY_TEXT: Record<WorkspaceIdentity['kind'] | 'no-actor' | 'no-project' | 'no-instance' | 'scope-mismatch', string> = {
  real: '视图与布局会按当前账号和项目保存在本机浏览器（不跨设备同步）。',
  session: '仅本次会话：未保存到本机。',
  'no-actor': '仅本次会话：尚未登录协作账号，视图与布局不会保存。',
  'no-project': '仅本次会话：还没有选择项目。',
  'no-instance': '仅本次会话：项目范围不完整（缺少工作区或分支）。',
  'scope-mismatch': '仅本次会话：当前协作范围属于另一个项目，切回该项目或重新选择协作范围后才会保存。',
};

let EPOCH = 0;
export function createScopeLease(key: string): ScopeLease {
  const ac = new AbortController();
  const timers = new Set<ReturnType<typeof setTimeout>>();
  let live = true;
  const epoch = ++EPOCH;
  return {
    key, epoch, signal: ac.signal,
    isCurrent: () => live,
    guard: fn => (...a) => { if (live) fn(...a); },
    defer(ms, fn) {
      if (!live) return;
      const t = setTimeout(() => { timers.delete(t); if (live) fn(); }, ms); timers.add(t);
    },
    retire() {
      if (!live) return; live = false;
      for (const t of timers) clearTimeout(t); timers.clear();
      ac.abort();
    },
  };
}

/** Holds the single current lease; switching key (incl. back to an earlier key) retires the old lease. */
export class LeaseHolder {
  private cur: ScopeLease | null = null;
  current(key: string): ScopeLease {
    if (this.cur && this.cur.key === key && this.cur.isCurrent()) return this.cur;
    this.cur?.retire();
    this.cur = createScopeLease(key);
    return this.cur;
  }
  /** [HERMIA-FE-20261025 U1fix] true while a current (non-retired) lease is held. */
  isLive() { return !!this.cur && this.cur.isCurrent(); }
  /** Forced invalidation (permission revoked, logout): retires without creating a successor. */
  invalidate() { this.cur?.retire(); this.cur = null; }
}
