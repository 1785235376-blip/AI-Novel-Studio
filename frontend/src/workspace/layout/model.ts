/**
 * [HERMIA-FE-20261023 M1] Unified workspace layout — pure state model + reducer.
 * Contract: docs/architecture/unified-workspace-contract.md §3.
 * Isolated module: NOT wired into App.tsx / IndependentStudioWorkspace.tsx (see artifacts/.../patches).
 * Reuses DockZone vocabulary from src/workbench/panels.ts and adds 'float'.
 */
import type {DockZone as WorkbenchDockZone} from '../../workbench/panels';

export type DockZone = WorkbenchDockZone | 'float';
export const DOCK_ZONES: readonly DockZone[] = ['left', 'main', 'right', 'bottom', 'float'];
export type SplitMode = 'single' | 'split-h' | 'split-v';
export const SPLIT_MODES: readonly SplitMode[] = ['single', 'split-h', 'split-v'];

export interface Rect { x: number; y: number; w: number; h: number; }
export interface Viewport { width: number; height: number;
  /** [HERMIA-FE-20261023 M1-s2] px above the dock body (layout toolbar), measured by DockLayout. Default 0. */
  reserveTop?: number; }

/** Static, registry-side description of a panel the layout may host. */
export interface LayoutPanelSpec {
  id: string;
  title: string;
  defaultDock: DockZone;
  docks: readonly DockZone[];
  /** px along the dock axis (width for left/right/float, height for bottom). */
  defaultSize: number;
  minSize: number;
  maxSize?: number;
  defaultOpen?: boolean;
  defaultCollapsed?: boolean;
}

/** Per-panel UI state. Never contains business data. */
export interface PanelFrame {
  id: string;
  dock: DockZone;
  order: number;
  size: number;
  collapsed: boolean;
  open: boolean;
  z: number;
  floatRect?: Rect;
}

export interface LayoutState {
  version: 3;
  split: SplitMode;
  frames: Record<string, PanelFrame>;
  focusId: string | null;
  zTop: number;
  /** Frames / raw entries for panel ids not registered in this build. Kept verbatim, re-serialized. */
  preserved: Record<string, unknown>;
}

export const MIN_FLOAT_VISIBLE = 48;
export const MAX_DOCK_FRACTION = 0.6;

export function maxSizeFor(spec: LayoutPanelSpec, dock: DockZone, vp: Viewport): number {
  const axis = dock === 'bottom' ? vp.height : vp.width;
  const vpMax = Math.max(spec.minSize, Math.floor(axis * (dock === 'main' || dock === 'float' ? 1 : MAX_DOCK_FRACTION)));
  return Math.min(spec.maxSize ?? Infinity, vpMax);
}

// [HERMIA-FE-20261023 M1-fix] MF-2: the main area keeps MAIN_MIN_WIDTH × MAIN_MIN_HEIGHT against the SUM of docked
// side columns (left + right) and the bottom strip. Per-panel clampSize alone allowed 60% + 60% > 100%.
export const MAIN_MIN_WIDTH = 320;
export const MAIN_MIN_HEIGHT = 200;
// [HERMIA-FE-20261023 M1-s2] Vera minor: subtract real chrome. Each present side column / bottom strip renders one
// resize handle (5px, .uw-resize) + one 1px border (.uw-col--left/right, .uw-bottom). Keep in sync with DockLayout.css.
export const RESIZER_PX = 5;
export const BORDER_PX = 1;
export const DOCK_CHROME_PX = RESIZER_PX + BORDER_PX;
function hasLive(frames: Record<string, PanelFrame>, dock: DockZone): boolean {
  return Object.values(frames).some(f => f.dock === dock && f.open);
}
/** Horizontal px used by side-column chrome (handles + borders) for columns that are rendered. */
export function sideChrome(frames: Record<string, PanelFrame>): number {
  return (hasLive(frames, 'left') ? DOCK_CHROME_PX : 0) + (hasLive(frames, 'right') ? DOCK_CHROME_PX : 0);
}
/** Max bottom-strip height so the main area keeps MAIN_MIN_HEIGHT under the toolbar and bottom chrome. */
export function bottomLimit(frames: Record<string, PanelFrame>, vp: Viewport): number {
  return vp.height - (vp.reserveTop ?? 0) - MAIN_MIN_HEIGHT - (hasLive(frames, 'bottom') ? DOCK_CHROME_PX : 0);
}
/** Real main-area size implied by a layout state (used by tests and diagnostics). */
export function mainArea(frames: Record<string, PanelFrame>, vp: Viewport): {width: number; height: number} {
  return {
    width: vp.width - columnExtent(frames, 'left') - columnExtent(frames, 'right') - sideChrome(frames),
    height: vp.height - (vp.reserveTop ?? 0) - columnExtent(frames, 'bottom') - (hasLive(frames, 'bottom') ? DOCK_CHROME_PX : 0),
  };
}
/** Effective width a dock column occupies (column width = widest open, expanded panel in it). */
export function columnExtent(frames: Record<string, PanelFrame>, dock: DockZone, exceptId?: string): number {
  let w = 0;
  for (const f of Object.values(frames)) if (f.dock === dock && f.open && !f.collapsed && f.id !== exceptId) w = Math.max(w, f.size);
  return w;
}
/** Upper bound for a docked side/bottom panel so the main area keeps its minimum given the other docks. */
export function crossLimit(frames: Record<string, PanelFrame>, id: string, dock: DockZone, vp: Viewport): number {
  if (dock === 'left' || dock === 'right') return vp.width - MAIN_MIN_WIDTH - columnExtent(frames, dock === 'left' ? 'right' : 'left') - sideChrome(frames);
  if (dock === 'bottom') return bottomLimit(frames, vp);
  return Infinity;
}
/** Shrink docked panels (others before `keepId`) until main keeps its minimum; never below a panel's minSize. */
export function fitMain(frames: Record<string, PanelFrame>, specs: readonly LayoutPanelSpec[], vp: Viewport, keepId?: string): Record<string, PanelFrame> {
  const out = {...frames};
  const min = (id: string) => specs.find(s => s.id === id)?.minSize ?? 0;
  const shrink = (pred: (f: PanelFrame) => boolean, by: number) => {
    for (const f of Object.values(out)) if (pred(f)) { const ns = Math.max(min(f.id), f.size - by); if (ns !== f.size) out[f.id] = {...f, size: ns}; }
  };
  const live = (f: PanelFrame) => f.open && !f.collapsed;
  for (const pass of [false, true]) { // pass 1 spares keepId, pass 2 may shrink it too
    const over = columnExtent(out, 'left') + columnExtent(out, 'right') + sideChrome(out) + MAIN_MIN_WIDTH - vp.width;
    if (over <= 0) break;
    const L = columnExtent(out, 'left', pass ? undefined : keepId); const R = columnExtent(out, 'right', pass ? undefined : keepId);
    const first: DockZone = L >= R ? 'left' : 'right'; const second: DockZone = first === 'left' ? 'right' : 'left';
    shrink(f => f.dock === first && live(f) && (pass || f.id !== keepId), over);
    const over2 = columnExtent(out, 'left') + columnExtent(out, 'right') + sideChrome(out) + MAIN_MIN_WIDTH - vp.width;
    if (over2 > 0) shrink(f => f.dock === second && live(f) && (pass || f.id !== keepId), over2);
  }
  const hMax = bottomLimit(out, vp);
  for (const f of Object.values(out)) if (f.dock === 'bottom' && f.size > hMax) out[f.id] = {...f, size: Math.max(min(f.id), hMax)};
  return out;
}

export function clampSize(spec: LayoutPanelSpec, dock: DockZone, size: number, vp: Viewport): number {
  const s = Number.isFinite(size) ? size : spec.defaultSize;
  return Math.round(Math.max(spec.minSize, Math.min(maxSizeFor(spec, dock, vp), s)));
}

/** Keep at least MIN_FLOAT_VISIBLE px of the float header inside the viewport; respect minSize. */
export function clampRect(spec: LayoutPanelSpec, r: Rect, vp: Viewport): Rect {
  const w = Math.max(spec.minSize, Math.min(r.w, vp.width));
  const h = Math.max(MIN_FLOAT_VISIBLE, Math.min(r.h, vp.height));
  const x = Math.max(MIN_FLOAT_VISIBLE - w, Math.min(r.x, vp.width - MIN_FLOAT_VISIBLE));
  const y = Math.max(0, Math.min(r.y, vp.height - MIN_FLOAT_VISIBLE));
  return {x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h)};
}

export function defaultFrame(spec: LayoutPanelSpec, order: number, vp: Viewport): PanelFrame {
  const f: PanelFrame = {
    id: spec.id, dock: spec.defaultDock, order, size: clampSize(spec, spec.defaultDock, spec.defaultSize, vp),
    collapsed: spec.defaultCollapsed ?? false, open: spec.defaultOpen ?? true, z: 0,
  };
  if (f.dock === 'float') f.floatRect = clampRect(spec, {x: 80, y: 80, w: spec.defaultSize, h: 320}, vp);
  return f;
}

export function createDefaultLayout(specs: readonly LayoutPanelSpec[], vp: Viewport, preserved: Record<string, unknown> = {}): LayoutState {
  const frames: Record<string, PanelFrame> = {};
  specs.forEach((s, i) => { frames[s.id] = defaultFrame(s, i, vp); });
  return {version: 3, split: 'single', frames, focusId: null, zTop: 0, preserved: {...preserved}};
}

export type LayoutAction =
  | {type: 'dock'; id: string; dock: DockZone; index?: number}
  | {type: 'resize'; id: string; size: number}
  | {type: 'moveFloat'; id: string; x: number; y: number}
  | {type: 'resizeFloat'; id: string; w: number; h: number}
  | {type: 'collapse'; id: string; collapsed?: boolean}
  | {type: 'close'; id: string}
  | {type: 'reopen'; id: string}
  | {type: 'focus'; id: string}
  | {type: 'split'; mode: SplitMode}
  | {type: 'viewport'}
  | {type: 'reset'}
  | {type: 'replace'; state: LayoutState};

export interface ReducerEnv { specs: readonly LayoutPanelSpec[]; viewport: Viewport; }

function specOf(env: ReducerEnv, id: string) { return env.specs.find(s => s.id === id); }

function reorder(frames: Record<string, PanelFrame>, dock: DockZone): Record<string, PanelFrame> {
  const out = {...frames};
  Object.values(out).filter(f => f.dock === dock).sort((a, b) => a.order - b.order)
    .forEach((f, i) => { if (f.order !== i) out[f.id] = {...f, order: i}; });
  return out;
}

function bump(state: LayoutState, id: string, frames: Record<string, PanelFrame>): LayoutState {
  const z = state.zTop + 1;
  return {...state, frames: {...frames, [id]: {...frames[id], z}}, zTop: z, focusId: id};
}

export function layoutReducer(env: ReducerEnv) {
  return (state: LayoutState, action: LayoutAction): LayoutState => {
    const vp = env.viewport;
    switch (action.type) {
      case 'replace': return action.state;
      case 'reset': {
        // Unknown-panel configs survive reset (preserved bag); business data is never in layout state.
        const d = createDefaultLayout(env.specs, vp, state.preserved);
        return {...d, frames: fitMain(d.frames, env.specs, vp)};
      }
      case 'split':
        return SPLIT_MODES.includes(action.mode) && action.mode !== state.split ? {...state, split: action.mode} : state;
      case 'viewport': {
        let changed = false; const frames = {...state.frames};
        for (const f of Object.values(frames)) {
          const s = specOf(env, f.id); if (!s) continue;
          const size = clampSize(s, f.dock, f.size, vp);
          const floatRect = f.floatRect ? clampRect(s, f.floatRect, vp) : undefined;
          if (size !== f.size || JSON.stringify(floatRect) !== JSON.stringify(f.floatRect)) { frames[f.id] = {...f, size, ...(floatRect ? {floatRect} : {})}; changed = true; }
        }
        // [HERMIA-FE-20261023 M1-fix] MF-2: viewport shrink re-fits side columns so main keeps its minimum.
        const fitted = fitMain(frames, env.specs, vp);
        if (JSON.stringify(fitted) !== JSON.stringify(frames)) changed = true;
        return changed ? {...state, frames: fitted} : state;
      }
    }
    const spec = specOf(env, action.id); const cur = state.frames[action.id];
    if (!spec || !cur) return state; // unknown id: no-op, never invent a panel
    switch (action.type) {
      case 'dock': {
        if (!spec.docks.includes(action.dock)) return state;
        const others = Object.values(state.frames).filter(f => f.dock === action.dock && f.id !== cur.id).sort((a, b) => a.order - b.order);
        const idx = Math.max(0, Math.min(action.index ?? others.length, others.length));
        let frames = {...state.frames};
        others.forEach((f, i) => { const o = i < idx ? i : i + 1; if (f.order !== o) frames[f.id] = {...f, order: o}; });
        const next: PanelFrame = {...cur, dock: action.dock, order: idx, size: clampSize(spec, action.dock, cur.size, vp), open: true};
        if (action.dock === 'float') next.floatRect = clampRect(spec, cur.floatRect ?? {x: 80, y: 80, w: cur.size, h: 320}, vp);
        frames[cur.id] = next;
        if (cur.dock !== action.dock) frames = reorder(frames, cur.dock);
        return bump(state, cur.id, fitMain(frames, env.specs, vp, cur.id)); // [HERMIA-FE-20261023 M1-fix] MF-2
      }
      case 'resize': {
        // [HERMIA-FE-20261023 M1-fix] MF-2: also bounded by the opposite column + main minimum.
        const size = Math.max(spec.minSize, Math.min(clampSize(spec, cur.dock, action.size, vp), crossLimit(state.frames, cur.id, cur.dock, vp)));
        return size === cur.size ? state : {...state, frames: {...state.frames, [cur.id]: {...cur, size}}};
      }
      case 'moveFloat': case 'resizeFloat': {
        if (cur.dock !== 'float' || !cur.floatRect) return state;
        const r = action.type === 'moveFloat' ? {...cur.floatRect, x: action.x, y: action.y} : {...cur.floatRect, w: action.w, h: action.h};
        return bump(state, cur.id, {...state.frames, [cur.id]: {...cur, floatRect: clampRect(spec, r, vp)}});
      }
      case 'collapse': {
        const collapsed = action.collapsed ?? !cur.collapsed;
        return collapsed === cur.collapsed ? state : {...state, frames: fitMain({...state.frames, [cur.id]: {...cur, collapsed}}, env.specs, vp, cur.id)};
      }
      case 'close':
        if (!cur.open) return state;
        return {...state, frames: {...state.frames, [cur.id]: {...cur, open: false}}, focusId: state.focusId === cur.id ? null : state.focusId};
      case 'reopen':
        // Keyed by id: reopening never creates a second instance.
        return bump(state, cur.id, fitMain({...state.frames, [cur.id]: {...cur, open: true, collapsed: false}}, env.specs, vp, cur.id));
      case 'focus':
        return state.focusId === cur.id && cur.z === state.zTop ? state : bump(state, cur.id, state.frames);
    }
    return state;
  };
}

export function panelsIn(state: LayoutState, dock: DockZone): PanelFrame[] {
  return Object.values(state.frames).filter(f => f.dock === dock && f.open).sort((a, b) => a.order - b.order);
}
export function closedPanels(state: LayoutState): PanelFrame[] {
  return Object.values(state.frames).filter(f => !f.open);
}

/** Drop-zone hit test used by pointer drag: edges dock, centre = main. */
export function zoneFromPoint(x: number, y: number, rect: {left: number; top: number; width: number; height: number}): DockZone {
  const rx = (x - rect.left) / Math.max(1, rect.width); const ry = (y - rect.top) / Math.max(1, rect.height);
  if (rx < 0.2) return 'left';
  if (rx > 0.8) return 'right';
  if (ry > 0.75) return 'bottom';
  return 'main';
}

/**
 * [HERMIA-FE-20261023 M1-s2] Precise drop: insertion index inside a dock zone from the pointer position and the
 * on-screen rects of the zone's OTHER panels (dragged panel excluded), in display order. Columns (left/right, main in
 * split-v) stack vertically; bottom strip and main in split-h/single flow horizontally. Index is in the same
 * "others" space the 'dock' reducer uses, so the result can be dispatched as-is.
 */
export interface SlotRect { left: number; top: number; width: number; height: number; }
export function dropAxis(dock: DockZone, split: SplitMode): 'x' | 'y' {
  if (dock === 'left' || dock === 'right') return 'y';
  if (dock === 'main') return split === 'split-v' ? 'y' : 'x';
  return 'x';
}
export function dropIndexFromPoint(axis: 'x' | 'y', point: {x: number; y: number}, others: readonly SlotRect[]): number {
  for (let i = 0; i < others.length; i++) {
    const r = others[i];
    const mid = axis === 'y' ? r.top + r.height / 2 : r.left + r.width / 2;
    if ((axis === 'y' ? point.y : point.x) < mid) return i;
  }
  return others.length;
}
