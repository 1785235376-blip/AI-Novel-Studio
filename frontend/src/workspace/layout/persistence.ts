/**
 * [HERMIA-FE-20261023 M1] Versioned layout persistence (format v3) with legacy migration.
 * Legacy sources actually present in this repo (cited, read-only — never rewritten or removed):
 *  - src/workbench/layout.ts  key `poemseed.workbench.layout.v2::<user>::<project>::<instance>`
 *      schemaVersion 2 {mode, placements:[{panelId,objectRef,dock,size?,collapsed?}], maximized}
 *      schemaVersion 1 {panels:[{id,zone}]}  (migrated by workbench/layout.ts `migrate`)
 *  - src/ui/AppShell.tsx  `studio-inspector-width` (px string), `studio-inspector-open` ('0'|'1')
 * Rules (contract §3.3): corrupt → diagnostics + default, raw copied to backup key, original untouched;
 * migration throw → raw intact; unknown ids preserved; save failure → session state kept + status.
 */
import {layoutKey, type LayoutScope, type StorageLike} from '../../workbench/layout';
import {
  clampRect, clampSize, createDefaultLayout, DOCK_ZONES, SPLIT_MODES,
  type DockZone, type LayoutPanelSpec, type LayoutState, type PanelFrame, type Viewport,
} from './model';

export const LAYOUT_FORMAT_VERSION = 3 as const;
export const LEGACY_INSPECTOR_WIDTH_KEY = 'studio-inspector-width';
export const LEGACY_INSPECTOR_OPEN_KEY = 'studio-inspector-open';

const enc = (s: LayoutScope) => `${encodeURIComponent(s.userId)}::${encodeURIComponent(s.projectId)}::${encodeURIComponent(s.projectInstanceId)}`;
export function workspaceLayoutKey(s: LayoutScope) { return `poemseed.workspace.layout.v${LAYOUT_FORMAT_VERSION}::${enc(s)}`; }
export function workspaceLayoutBackupKey(s: LayoutScope) { return `${workspaceLayoutKey(s)}::backup`; }
export function legacyWorkbenchKeyV1(s: LayoutScope) { return `poemseed.workbench.layout.v1::${enc(s)}`; }
export const legacyWorkbenchKeyV2 = layoutKey;

export type DiagnosticCode =
  | 'corrupt-json' | 'not-object' | 'unsupported-version' | 'migration-failed'
  | 'invalid-size' | 'invalid-dock' | 'invalid-field' | 'unknown-panel-preserved'
  | 'missing-panel-added' | 'backup-written' | 'backup-failed' | 'storage-read-failed';
export interface Diagnostic { code: DiagnosticCode; panelId?: string; detail?: string; }
export type LoadSource = 'v3' | 'migrated-workbench-v2' | 'migrated-workbench-v1' | 'migrated-inspector-keys' | 'default' | 'fallback-corrupt';
export interface LoadResult { state: LayoutState; source: LoadSource; diagnostics: Diagnostic[]; }

export interface SerializedLayoutV3 {
  version: 3;
  split: string;
  focusId: string | null;
  panels: Array<Record<string, unknown>>;
  /** Unknown-panel entries, verbatim. */
  preserved?: Record<string, unknown>;
  /** Unknown top-level fields from newer builds, verbatim. */
  extra?: Record<string, unknown>;
}

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const KNOWN_TOP = new Set(['version', 'split', 'focusId', 'panels', 'preserved', 'extra']);

export function serializeLayout(state: LayoutState, extra?: Record<string, unknown>): string {
  const out: SerializedLayoutV3 = {
    version: 3, split: state.split, focusId: state.focusId,
    panels: Object.values(state.frames).sort((a, b) => a.id.localeCompare(b.id)).map(f => {
      // [HERMIA-FE-20261023 M1] canonical key order so repeated migration is byte-identical (M1-16)
      const o: Record<string, unknown> = {id: f.id, dock: f.dock, order: f.order, size: f.size, collapsed: f.collapsed, open: f.open, z: f.z};
      if (f.floatRect) o.floatRect = f.floatRect;
      return o;
    }),
  };
  if (Object.keys(state.preserved).length) out.preserved = state.preserved;
  if (extra && Object.keys(extra).length) out.extra = extra;
  return JSON.stringify(out);
}

/** Normalise one raw frame against its spec; fixes invalid parts, keeps valid ones. */
function normaliseFrame(raw: Record<string, unknown>, spec: LayoutPanelSpec, order: number, vp: Viewport, diags: Diagnostic[]): PanelFrame {
  let dock = raw.dock as DockZone;
  if (!DOCK_ZONES.includes(dock) || !spec.docks.includes(dock)) {
    if (raw.dock !== undefined) diags.push({code: 'invalid-dock', panelId: spec.id, detail: String(raw.dock)});
    dock = spec.defaultDock;
  }
  let size = typeof raw.size === 'number' && Number.isFinite(raw.size) && raw.size > 0 ? raw.size : NaN;
  if (Number.isNaN(size)) { if (raw.size !== undefined) diags.push({code: 'invalid-size', panelId: spec.id, detail: String(raw.size)}); size = spec.defaultSize; }
  const clamped = clampSize(spec, dock, size, vp);
  if (clamped !== Math.round(size)) diags.push({code: 'invalid-size', panelId: spec.id, detail: `${size}→${clamped}`});
  const f: PanelFrame = {
    id: spec.id, dock, size: clamped,
    order: typeof raw.order === 'number' && Number.isFinite(raw.order) ? raw.order : order,
    collapsed: typeof raw.collapsed === 'boolean' ? raw.collapsed : (spec.defaultCollapsed ?? false),
    open: typeof raw.open === 'boolean' ? raw.open : (spec.defaultOpen ?? true),
    z: typeof raw.z === 'number' && Number.isFinite(raw.z) && raw.z >= 0 ? raw.z : 0,
  };
  if (dock === 'float') {
    const r = isObj(raw.floatRect) ? raw.floatRect : {};
    const num = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? v : d);
    f.floatRect = clampRect(spec, {x: num(r.x, 80), y: num(r.y, 80), w: num(r.w, clamped), h: num(r.h, 320)}, vp);
  }
  return f;
}

/** Build a v3 state from a list of raw panel entries (shared by v3 parse and every migration). */
function buildState(entries: Array<Record<string, unknown>>, top: {split?: unknown; focusId?: unknown; preserved?: unknown}, specs: readonly LayoutPanelSpec[], vp: Viewport, diags: Diagnostic[]): LayoutState {
  const base = createDefaultLayout(specs, vp);
  const preserved: Record<string, unknown> = isObj(top.preserved) ? {...top.preserved} : {};
  const seen = new Set<string>();
  entries.forEach((e, i) => {
    const id = typeof e?.id === 'string' ? e.id : '';
    if (!id) { diags.push({code: 'invalid-field', detail: 'panel without id'}); preserved[`__invalid_${i}`] = e; return; }
    const spec = specs.find(s => s.id === id);
    if (!spec) { preserved[id] = e; diags.push({code: 'unknown-panel-preserved', panelId: id}); return; }
    if (seen.has(id)) { diags.push({code: 'invalid-field', panelId: id, detail: 'duplicate entry ignored'}); return; }
    seen.add(id);
    base.frames[id] = normaliseFrame(e, spec, i, vp, diags);
  });
  for (const s of specs) if (!seen.has(s.id)) diags.push({code: 'missing-panel-added', panelId: s.id});
  const split = SPLIT_MODES.includes(top.split as never) ? top.split as LayoutState['split'] : 'single';
  if (top.split !== undefined && split !== top.split) diags.push({code: 'invalid-field', detail: `split=${String(top.split)}`});
  const focusId = typeof top.focusId === 'string' && base.frames[top.focusId]?.open ? top.focusId : null;
  const zTop = Math.max(0, ...Object.values(base.frames).map(f => f.z));
  return {...base, split, focusId, zTop, preserved};
}

export function parseLayoutV3(raw: unknown, specs: readonly LayoutPanelSpec[], vp: Viewport): {state: LayoutState; diagnostics: Diagnostic[]; extra: Record<string, unknown>} {
  const diags: Diagnostic[] = [];
  if (!isObj(raw)) throw Object.assign(new Error('not-object'), {code: 'not-object'});
  if (raw.version !== 3) throw Object.assign(new Error('unsupported-version'), {code: 'unsupported-version'});
  const extra: Record<string, unknown> = isObj(raw.extra) ? {...raw.extra} : {};
  for (const k of Object.keys(raw)) if (!KNOWN_TOP.has(k)) extra[k] = raw[k];
  const panels = Array.isArray(raw.panels) ? raw.panels.filter(isObj) : [];
  if (!Array.isArray(raw.panels)) diags.push({code: 'invalid-field', detail: 'panels missing'});
  return {state: buildState(panels, raw, specs, vp, diags), diagnostics: diags, extra};
}

/** workbench/layout.ts v2 (or v1) document → v3 entries. Pure; throws on shapes it cannot read. */
export function migrateWorkbenchLayout(raw: unknown): {entries: Array<Record<string, unknown>>; from: 1 | 2} {
  if (!isObj(raw)) throw new Error('legacy layout is not an object');
  if (raw.schemaVersion === 1 && Array.isArray(raw.panels)) {
    return {from: 1, entries: raw.panels.filter(isObj).map(p => ({id: p.id, dock: p.zone}))};
  }
  if (raw.schemaVersion === 2 && Array.isArray(raw.placements)) {
    const entries: Array<Record<string, unknown>> = [];
    const seen = new Set<string>();
    for (const p of raw.placements.filter(isObj)) {
      // v2 allowed per-object instances (panelId#objectRef); v3 layout is per panel id, first wins.
      const id = p.panelId; if (typeof id !== 'string' || seen.has(id)) continue; seen.add(id);
      entries.push({id, dock: p.dock, ...(p.size !== undefined ? {size: p.size} : {}), ...(p.collapsed !== undefined ? {collapsed: p.collapsed} : {}), ...(p.objectRef ? {legacyObjectRef: p.objectRef} : {})});
    }
    return {from: 2, entries};
  }
  throw new Error(`unsupported legacy schemaVersion ${String(raw.schemaVersion)}`);
}

export interface LoadOptions {
  /** Panel id that legacy `studio-inspector-*` keys map onto (right dock). */
  inspectorPanelId?: string;
  /** Test seam: replace the legacy migration function (e.g. to simulate a throw). */
  migrate?: typeof migrateWorkbenchLayout;
}

function safeGet(st: StorageLike, k: string, diags: Diagnostic[]): string | null {
  try { return st.getItem(k); } catch (e) { diags.push({code: 'storage-read-failed', detail: `${k}: ${String(e)}`}); return null; }
}

export function loadWorkspaceLayout(st: StorageLike, scope: LayoutScope, specs: readonly LayoutPanelSpec[], vp: Viewport, opts: LoadOptions = {}): LoadResult {
  const diags: Diagnostic[] = [];
  const key = workspaceLayoutKey(scope);
  const txt = safeGet(st, key, diags);
  const fallback = (): LoadResult => ({state: createDefaultLayout(specs, vp), source: 'fallback-corrupt', diagnostics: diags});
  const backup = (raw: string) => {
    // Copy, never move: the original key is left as-is so nothing is lost if we are wrong.
    try { st.setItem(workspaceLayoutBackupKey(scope), raw); diags.push({code: 'backup-written'}); }
    catch (e) { diags.push({code: 'backup-failed', detail: String(e)}); }
  };
  if (txt != null) {
    let raw: unknown;
    try { raw = JSON.parse(txt); } catch (e) { diags.push({code: 'corrupt-json', detail: String(e)}); backup(txt); return fallback(); }
    try {
      const r = parseLayoutV3(raw, specs, vp);
      return {state: r.state, source: 'v3', diagnostics: [...diags, ...r.diagnostics]};
    } catch (e) {
      const code = ((e as {code?: DiagnosticCode}).code) ?? 'not-object';
      diags.push({code, detail: String(e)}); backup(txt); return fallback();
    }
  }
  // No v3 yet → try legacy sources (read-only).
  const legacyTxt = safeGet(st, legacyWorkbenchKeyV2(scope), diags) ?? safeGet(st, legacyWorkbenchKeyV1(scope), diags);
  let state: LayoutState | null = null; let source: LoadSource = 'default';
  if (legacyTxt != null) {
    try {
      const m = (opts.migrate ?? migrateWorkbenchLayout)(JSON.parse(legacyTxt));
      state = buildState(m.entries, {}, specs, vp, diags);
      source = m.from === 2 ? 'migrated-workbench-v2' : 'migrated-workbench-v1';
    } catch (e) {
      diags.push({code: 'migration-failed', detail: String(e)});
      return {state: createDefaultLayout(specs, vp), source: 'fallback-corrupt', diagnostics: diags};
    }
  }
  const inspectorId = opts.inspectorPanelId;
  const spec = inspectorId ? specs.find(s => s.id === inspectorId) : undefined;
  if (spec && spec.docks.includes('right')) {
    const w = safeGet(st, LEGACY_INSPECTOR_WIDTH_KEY, diags); const open = safeGet(st, LEGACY_INSPECTOR_OPEN_KEY, diags);
    if (w != null || open != null) {
      state ??= createDefaultLayout(specs, vp);
      const f = state.frames[spec.id]; const n = Number(w);
      state.frames[spec.id] = {
        ...f, dock: 'right',
        size: w != null && Number.isFinite(n) && n > 0 ? clampSize(spec, 'right', n, vp) : f.size,
        collapsed: open === '0' ? true : open === '1' ? false : f.collapsed,
      };
      if (source === 'default') source = 'migrated-inspector-keys';
    }
  }
  return {state: state ?? createDefaultLayout(specs, vp), source, diagnostics: diags};
}

export type SaveResult = {ok: true} | {ok: false; error: string};
export function saveWorkspaceLayout(st: StorageLike, scope: LayoutScope, state: LayoutState, extra?: Record<string, unknown>): SaveResult {
  try { st.setItem(workspaceLayoutKey(scope), serializeLayout(state, extra)); return {ok: true}; }
  catch (e) { return {ok: false, error: e instanceof Error ? e.message : String(e)}; }
}
