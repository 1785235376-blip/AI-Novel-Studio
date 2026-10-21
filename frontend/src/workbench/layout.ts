/**
 * [HERMIA-FE-20261022 slice M1-1] Layout persistence (task book §7.1).
 * - schemaVersion + migrations; corrupt/unknown data → default layout (never throws).
 * - scope = user + project + projectInstance; layouts never cross scopes.
 * - Only UI state + controlled object refs are stored. Keys that look sensitive are dropped.
 * - resetLayout only removes the layout key; drafts/works/jobs/history are untouched.
 */
import type {PanelRegistry, DockZone} from './panels';
export const LAYOUT_SCHEMA_VERSION = 2;
export interface LayoutScope { userId: string; projectId: string; projectInstanceId: string; }
export interface PanelPlacement { panelId: string; objectRef: string | null; dock: DockZone; size?: number; collapsed?: boolean; }
export interface WorkbenchLayout { schemaVersion: number; mode: 'basic' | 'pro'; placements: PanelPlacement[]; maximized: string | null; }
export interface StorageLike { getItem(k: string): string | null; setItem(k: string, v: string): void; removeItem(k: string): void; }
export const DEFAULT_LAYOUT: WorkbenchLayout = {schemaVersion: LAYOUT_SCHEMA_VERSION, mode: 'basic', placements: [], maximized: null};
export function layoutKey(s: LayoutScope) {
  return `poemseed.workbench.layout.v${LAYOUT_SCHEMA_VERSION}::${encodeURIComponent(s.userId)}::${encodeURIComponent(s.projectId)}::${encodeURIComponent(s.projectInstanceId)}`;
}
const SENSITIVE = /token|secret|password|cookie|credential|signed|signature|apikey|api_key|authorization|content|body|prose/i;
const DOCKS: DockZone[] = ['left', 'main', 'right', 'bottom'];
/** v1 stored {panels:[{id,zone}]} with no mode. */
function migrate(raw: Record<string, unknown>): Record<string, unknown> | null {
  if (raw.schemaVersion === 1 && Array.isArray(raw.panels)) {
    return {schemaVersion: 2, mode: 'basic', maximized: null,
      placements: (raw.panels as Array<Record<string, unknown>>).map(p => ({panelId: p.id, objectRef: null, dock: p.zone}))};
  }
  return raw.schemaVersion === LAYOUT_SCHEMA_VERSION ? raw : null;
}
export interface LoadReport { layout: WorkbenchLayout; recovered: boolean; droppedPanels: string[]; }
export function sanitize(raw: unknown, reg: PanelRegistry, existingObject?: (ref: string) => boolean): LoadReport {
  const dropped: string[] = [];
  if (!raw || typeof raw !== 'object') return {layout: structuredClone(DEFAULT_LAYOUT), recovered: raw != null, droppedPanels: dropped};
  const m = migrate(raw as Record<string, unknown>);
  if (!m || !Array.isArray(m.placements)) return {layout: structuredClone(DEFAULT_LAYOUT), recovered: true, droppedPanels: dropped};
  const placements: PanelPlacement[] = [];
  for (const p of m.placements as Array<Record<string, unknown>>) {
    const id = typeof p?.panelId === 'string' ? p.panelId : '';
    const def = reg.get(id);
    const ref = typeof p?.objectRef === 'string' ? p.objectRef : null;
    if (!def) { dropped.push(id || '<invalid>'); continue; }                       // panel removed after upgrade / permission
    if (ref && existingObject && !existingObject(ref)) { dropped.push(`${id}#${ref}`); continue; } // object deleted
    if (def.instancing === 'per-object' && !ref) { dropped.push(id); continue; }
    const dock = DOCKS.includes(p.dock as DockZone) && def.docks.includes(p.dock as DockZone) ? p.dock as DockZone : def.defaultDock;
    const size = typeof p.size === 'number' && Number.isFinite(p.size) && p.size > 0 ? p.size : undefined;
    placements.push({panelId: id, objectRef: ref, dock, ...(size ? {size} : {}), ...(p.collapsed === true ? {collapsed: true} : {})});
  }
  const mode = m.mode === 'pro' ? 'pro' : 'basic';
  const maximized = typeof m.maximized === 'string' && placements.some(p => p.panelId === m.maximized) ? m.maximized : null;
  return {layout: {schemaVersion: LAYOUT_SCHEMA_VERSION, mode, placements, maximized}, recovered: dropped.length > 0, droppedPanels: dropped};
}
export function loadLayout(st: StorageLike, scope: LayoutScope, reg: PanelRegistry, existingObject?: (ref: string) => boolean): LoadReport {
  let raw: unknown = null; const txt = st.getItem(layoutKey(scope));
  if (txt == null) return {layout: structuredClone(DEFAULT_LAYOUT), recovered: false, droppedPanels: []};
  try { raw = JSON.parse(txt); } catch { return {layout: structuredClone(DEFAULT_LAYOUT), recovered: true, droppedPanels: []}; }
  return sanitize(raw, reg, existingObject);
}
export function saveLayout(st: StorageLike, scope: LayoutScope, layout: WorkbenchLayout) {
  const clean = JSON.parse(JSON.stringify(layout, (k, v) => (k && SENSITIVE.test(k) ? undefined : v)));
  clean.schemaVersion = LAYOUT_SCHEMA_VERSION;
  st.setItem(layoutKey(scope), JSON.stringify(clean));
}
/** Resets UI only. Deliberately touches nothing but the layout key. */
export function resetLayout(st: StorageLike, scope: LayoutScope): WorkbenchLayout { st.removeItem(layoutKey(scope)); return structuredClone(DEFAULT_LAYOUT); }
/** Narrow screens: collapse side docks instead of dropping them. */
export function adaptToViewport(l: WorkbenchLayout, width: number): WorkbenchLayout {
  if (width >= 1280) return l;
  return {...l, placements: l.placements.map(p => p.dock === 'main' ? p : {...p, collapsed: true})};
}
