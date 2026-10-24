/**
 * [HERMIA-FE-20261024 VW-M1] View-preference consumer adapter (UI preferences only).
 *
 * Contract (GROK_CONTINUOUS_FRONTEND_TASK_20261024 §M1):
 *  - The host owner injects a real LayoutScope (user / project / projectInstance), a StorageLike, isCurrent() and an
 *    explicit `persist` capability. Missing / placeholder scope or persist=false ⇒ persistence DISABLED: zero writes,
 *    values live in this adapter's session memory only and the status says so. Scope never implies any permission.
 *  - Stores only UI geometry: per-canvas viewport {x,y,zoom} and named workset metadata + v3 layout geometry.
 *    Never prompt/text/drafts/graph/node/job/asset/credentials (enforced by whitelisting on write AND read).
 *  - Own key `poemseed.workspace.viewprefs.v1::<scope>`; never touches layout v3 / legacy / business keys and never
 *    clears storage. Corrupt or future-version data is left byte-identical and the adapter goes read-only (session).
 *  - Read/write failures keep the session value and surface a status; a write after the host scope stopped being
 *    current (late callback) is dropped.
 */
import type {LayoutScope, StorageLike} from '../../workbench/layout';

export const VIEW_PREFS_VERSION = 1 as const;
export type CanvasViewKind = 'image' | 'video';
export interface CanvasViewport { x: number; y: number; zoom: number; }
export const VIEWPORT_ZOOM_MIN = 0.1;
export const VIEWPORT_ZOOM_MAX = 4;
export const VIEWPORT_COORD_LIMIT = 1_000_000;

/** Named workset: metadata + serialized v3 layout geometry (validated by worksets.ts). */
export interface StoredWorkset { id: string; name: string; createdAt: number; layout: string; }
export interface ViewPrefsDoc { version: 1; viewports: Partial<Record<CanvasViewKind, CanvasViewport>>; worksets: StoredWorkset[]; }

/** Placeholder identities that must never be persisted as if they were a real actor/project instance. */
const PLACEHOLDER = new Set(['', 'local', 'preview', 'unknown', 'anonymous', 'default']);

export type PrefsMode = 'persistent' | 'session';
export type PrefsReason =
  | 'ok' | 'no-scope' | 'placeholder-scope' | 'persist-disabled' | 'no-storage'
  | 'read-failed' | 'corrupt' | 'future-version' | 'write-failed' | 'not-current';
export interface PrefsStatus { mode: PrefsMode; reason: PrefsReason; }

export const PREFS_REASON_TEXT: Record<PrefsReason, string> = {
  'ok': '视图偏好会保存在本机浏览器（只含界面位置，不含作品内容）。',
  'no-scope': '当前没有可用的项目身份，视图只在本次会话有效，不会写入本机。',
  'placeholder-scope': '当前是预览身份，视图只在本次会话有效，不会写入本机。',
  'persist-disabled': '宿主没有开放本机保存，视图只在本次会话有效。',
  'no-storage': '浏览器存储不可用，视图只在本次会话有效。',
  'read-failed': '读取已保存的视图失败，先用本次会话的视图；原数据未改动。',
  'corrupt': '已保存的视图数据无法识别，已保留原数据不覆盖；本次只在会话内生效。',
  'future-version': '已保存的视图来自更新的版本，已保留不覆盖；本次只在会话内生效。',
  'write-failed': '视图保存失败（可能是存储已满或被拒绝），本次会话里的视图仍然有效。',
  'not-current': '项目已切换，这次视图变化没有保存到新项目。',
};

export interface ViewPrefsHost {
  scope: LayoutScope | null;
  storage: StorageLike | null;
  /** True while this scope is still the host's current lease. */
  isCurrent: () => boolean;
  /** Explicit host persistence capability. Absent/false ⇒ session only. */
  persist: boolean;
}

const enc = (s: LayoutScope) => `${encodeURIComponent(s.userId)}::${encodeURIComponent(s.projectId)}::${encodeURIComponent(s.projectInstanceId)}`;
export function viewPrefsKey(s: LayoutScope) { return `poemseed.workspace.viewprefs.v${VIEW_PREFS_VERSION}::${enc(s)}`; }

export function scopeProblem(scope: LayoutScope | null | undefined): PrefsReason | null {
  if (!scope) return 'no-scope';
  const parts = [scope.userId, scope.projectId, scope.projectInstanceId];
  if (parts.some(p => typeof p !== 'string' || !p.trim())) return 'no-scope';
  if (parts.some(p => PLACEHOLDER.has(p.trim().toLowerCase()))) return 'placeholder-scope';
  return null;
}

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const fin = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export function sanitizeViewport(v: unknown): CanvasViewport | null {
  if (!isObj(v) || !fin(v.x) || !fin(v.y) || !fin(v.zoom)) return null;
  if (Math.abs(v.x) > VIEWPORT_COORD_LIMIT || Math.abs(v.y) > VIEWPORT_COORD_LIMIT) return null;
  if (v.zoom < VIEWPORT_ZOOM_MIN || v.zoom > VIEWPORT_ZOOM_MAX) return null;
  return {x: v.x, y: v.y, zoom: v.zoom};
}
export const WORKSET_LIMIT = 12;
export const WORKSET_NAME_MAX = 40;
export const WORKSET_LAYOUT_MAX_BYTES = 16_000;
export function sanitizeStoredWorkset(v: unknown): StoredWorkset | null {
  if (!isObj(v) || typeof v.id !== 'string' || !v.id || typeof v.name !== 'string' || typeof v.layout !== 'string' || !fin(v.createdAt)) return null;
  const name = v.name.trim();
  if (!name || name.length > WORKSET_NAME_MAX || v.layout.length > WORKSET_LAYOUT_MAX_BYTES) return null;
  return {id: v.id.slice(0, 64), name, createdAt: v.createdAt, layout: v.layout};
}
function sanitizeDoc(raw: Partial<ViewPrefsDoc>): ViewPrefsDoc {
  const viewports: ViewPrefsDoc['viewports'] = {};
  for (const k of ['image', 'video'] as const) { const s = sanitizeViewport(raw.viewports?.[k]); if (s) viewports[k] = s; }
  const worksets = (Array.isArray(raw.worksets) ? raw.worksets : []).map(sanitizeStoredWorkset).filter((w): w is StoredWorkset => !!w).slice(0, WORKSET_LIMIT);
  return {version: 1, viewports, worksets};
}
const emptyDoc = (): ViewPrefsDoc => ({version: 1, viewports: {}, worksets: []});

export interface ViewPrefs {
  readonly key: string | null;
  status(): PrefsStatus;
  getViewport(kind: CanvasViewKind): CanvasViewport | undefined;
  /** Returns false when the value was rejected (non-finite / out of range). */
  setViewport(kind: CanvasViewKind, v: CanvasViewport): boolean;
  /** Clears only this canvas's viewport preference. */
  resetViewport(kind: CanvasViewKind): void;
  getWorksets(): StoredWorkset[];
  setWorksets(list: StoredWorkset[]): boolean;
  /** Whether the current view came from a cold read of saved preferences (honest restore label). */
  restoredFromStorage(kind: CanvasViewKind): boolean;
}

/** Create the adapter for one host scope. All state is per-instance (no cross-consumer sharing). */
export function createViewPreferences(host: ViewPrefsHost): ViewPrefs {
  const problem = scopeProblem(host.scope) ?? (!host.persist ? 'persist-disabled' : !host.storage ? 'no-storage' : null);
  const key = problem ? null : viewPrefsKey(host.scope!);
  let status: PrefsStatus = problem ? {mode: 'session', reason: problem} : {mode: 'persistent', reason: 'ok'};
  let doc = emptyDoc();
  const restored = new Set<CanvasViewKind>();
  if (key && host.storage) {
    let txt: string | null = null;
    try { txt = host.storage.getItem(key); } catch { status = {mode: 'session', reason: 'read-failed'}; }
    if (txt !== null) {
      let parsed: unknown;
      try { parsed = JSON.parse(txt); } catch { parsed = undefined; }
      if (!isObj(parsed)) status = {mode: 'session', reason: 'corrupt'};
      else if (typeof parsed.version === 'number' && parsed.version > VIEW_PREFS_VERSION) status = {mode: 'session', reason: 'future-version'};
      else if (parsed.version !== VIEW_PREFS_VERSION) status = {mode: 'session', reason: 'corrupt'};
      else {
        doc = sanitizeDoc(parsed as Partial<ViewPrefsDoc>);
        for (const k of Object.keys(doc.viewports) as CanvasViewKind[]) restored.add(k);
      }
    }
  }
  const writable = () => status.mode === 'persistent' || status.reason === 'write-failed';
  const flush = (): boolean => {
    if (!key || !host.storage || !writable()) return false;
    if (!host.isCurrent()) { status = {...status, reason: status.reason === 'write-failed' ? 'write-failed' : 'not-current'}; return false; }
    try { host.storage.setItem(key, JSON.stringify(doc)); status = {mode: 'persistent', reason: 'ok'}; return true; }
    catch { status = {mode: 'persistent', reason: 'write-failed'}; return false; }
  };
  return {
    key,
    status: () => status,
    getViewport: k => doc.viewports[k],
    setViewport(k, v) {
      // A late callback after the host lease moved must not change this scope's values either.
      if (!host.isCurrent()) { if (key) status = {...status, reason: 'not-current'}; return false; }
      const s = sanitizeViewport(v); if (!s) return false;
      doc = {...doc, viewports: {...doc.viewports, [k]: s}};
      restored.delete(k);
      flush(); return true;
    },
    resetViewport(k) {
      if (!host.isCurrent()) return;
      const {[k]: _drop, ...rest} = doc.viewports; doc = {...doc, viewports: rest}; restored.delete(k); flush();
    },
    getWorksets: () => doc.worksets,
    setWorksets(list) {
      if (!host.isCurrent()) { if (key) status = {...status, reason: 'not-current'}; return false; }
      doc = {...doc, worksets: list.map(sanitizeStoredWorkset).filter((w): w is StoredWorkset => !!w).slice(0, WORKSET_LIMIT)};
      return flush() || status.mode === 'session';
    },
    restoredFromStorage: k => restored.has(k),
  };
}
