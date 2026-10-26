/**
 * [HERMIA-FE-20261025 UWPORT-S1] Default UI: reopen restores the last chapter (port of the U1 view-prefs scoping rules).
 * - Real identity (actor + complete scope + project) ⇒ persisted under its own key per user/project/instance; only chapterId.
 * - Otherwise 仅本次会话: in-memory only, zero storage writes, never a fabricated user.
 * - Corrupt / future-version data is left byte-identical and ignored. A chapter that no longer exists is never resurrected.
 */
import type {LayoutScope} from '../../workbench/layout';
import type {WorkspaceIdentity} from '../contracts';

type St = {getItem(k: string): string | null; setItem(k: string, v: string): void};
const session = new Map<string, string>();
const enc = encodeURIComponent;
export const LAST_POSITION_TEXT = {
  saved: '上次写到的章节会保存在本机浏览器，重开后回到这里。',
  session: '仅本次会话：没有真实登录身份，重开后不会恢复章节位置。',
} as const;

export function lastPositionKey(s: LayoutScope) { return `poemseed.default.lastpos.v1::${enc(s.userId)}::${enc(s.projectId)}::${enc(s.projectInstanceId)}`; }

type Read = {state: 'ok'; chapterId: string | null} | {state: 'locked'} | {state: 'failed'};
function readStored(st: St | null, s: LayoutScope): Read {
  let raw: string | null;
  try { raw = st ? st.getItem(lastPositionKey(s)) : null; } catch { return {state: 'failed'}; }
  if (raw == null) return {state: 'ok', chapterId: null};
  try {
    const d = JSON.parse(raw) as {v?: unknown; chapterId?: unknown};
    if (d && d.v === 1 && typeof d.chapterId === 'string' && d.chapterId) return {state: 'ok', chapterId: d.chapterId};
  } catch { /* corrupt */ }
  return {state: 'locked'};
}

export function recallChapter(st: St | null, id: WorkspaceIdentity): string | null {
  if (session.has(id.key)) return session.get(id.key)!;
  if (id.kind !== 'real') return null;
  const r = readStored(st, id.scope);
  return r.state === 'ok' ? r.chapterId : null;
}

export function rememberChapter(st: St | null, id: WorkspaceIdentity, chapterId: string): 'saved' | 'session' | 'write-failed' {
  session.set(id.key, chapterId);
  if (id.kind !== 'real' || !st) return 'session';
  const r = readStored(st, id.scope);
  if (r.state === 'locked') return 'session';
  try { st.setItem(lastPositionKey(id.scope), JSON.stringify({v: 1, chapterId})); return 'saved'; } catch { return 'write-failed'; }
}

export function pickChapter(rows: readonly {id: string}[], remembered: string | null): string | null {
  if (remembered && rows.some(r => r.id === remembered)) return remembered;
  return rows[0]?.id ?? null;
}
/** test-only */
export function __resetLastPositionSession() { session.clear(); }
