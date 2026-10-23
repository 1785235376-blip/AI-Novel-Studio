/**
 * [HERMIA-FE-20261023 M1] DockLayout — isolated unified window/layout component.
 * Real pointer drag to dock zones, float drag, resize handles (pointer + keyboard), collapse,
 * close (dirty guard) / reopen menu, split switch, reset default (confirm), persistence status.
 * NOT mounted by App.tsx yet; wiring lives in artifacts/unified-workspace-refactor/patches/.
 */
import {useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState, type KeyboardEvent, type PointerEvent as RPointerEvent, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import type {LayoutScope, StorageLike} from '../../workbench/layout';
import {ActionRegistry, type ActionContext, type ExecuteResult} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';
import {actionIdForKey, displayShortcut, LAYOUT_ACTION_IDS, registerLayoutActions, ShortcutTable, type LayoutActionId, type LayoutActionOptions} from '../actions/layoutActions';
import {
  closedPanels, dropAxis, emptyZoneBox, dropIndexFromPoint, layoutReducer, panelsIn, zoneFromPoint,
  type DockZone, type LayoutAction, type LayoutPanelSpec, type LayoutState, type PanelFrame, type SplitMode, type Viewport,
} from './model';
import {loadWorkspaceLayout, saveWorkspaceLayout, type LoadOptions, type LoadResult} from './persistence';
import {useDirtyCloseGuard, type DirtySource} from './useDirtyCloseGuard';
import './DockLayout.css';

export interface PanelRenderApi { registerDirty(src: DirtySource): () => void; }
export interface DockLayoutProps {
  specs: readonly LayoutPanelSpec[];
  scope: LayoutScope;
  storage: StorageLike | null;
  renderPanel: (id: string, api: PanelRenderApi) => ReactNode;
  /** Fixed viewport for tests; otherwise window size with resize listener. */
  viewport?: Viewport;
  loadOptions?: LoadOptions;
  onLoad?: (r: LoadResult) => void;
  /** [HERMIA-FE-20261023 M1-s2] Optional shared registry / shortcut table (host app). Defaults to a private pair. */
  actionRegistry?: ActionRegistry;
  shortcutTable?: ShortcutTable;
  /** [HERMIA-FE-20261023 M1-s2fix] lifecycle tracker shared with actionRegistry (so a host command palette's ctx tokens match). */
  tracker?: LifecycleTracker;
  actionOptions?: LayoutActionOptions;
  /** [HERMIA-FE-20261023 M1-s2fix] host content at the start of the layout toolbar (e.g. command palette trigger); counted in reserveTop. */
  toolbarStart?: ReactNode;
}

const DOCK_LABEL: Record<DockZone, string> = {left: '左侧', main: '中间', right: '右侧', bottom: '底部', float: '浮动'};
const SPLIT_LABEL: Record<SplitMode, string> = {single: '单栏', 'split-h': '左右分屏', 'split-v': '上下分屏'};
const KEY_STEP = 16;
interface DropTarget { zone: DockZone; index: number; allowed: boolean; axis: 'x' | 'y'; line: {left: number; top: number; width: number; height: number}; empty: boolean; }

/** [HERMIA-FE-20261023 M1-fix] N2: layout signature without focus / z-order, which are not layout changes. */
function layoutSignature(s: LayoutState): string {
  const frames = Object.values(s.frames).map(({z: _z, ...f}) => f).sort((a, b) => a.id.localeCompare(b.id));
  return JSON.stringify({split: s.split, frames, preserved: s.preserved});
}

/**
 * [HERMIA-FE-20261023 M1-fix] MF-1: a panel's content lives in ONE stable host element per panel id and is rendered
 * through a keyed portal at a fixed position in the React tree. Zones only attach that host element, so redocking,
 * floating, or hiding a main panel in single-column mode never remounts content (no silent draft loss).
 * Only an explicit close (through the dirty-close guard) unmounts it.
 */
function PanelSlot({host}: {host: HTMLElement | undefined}) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const p = ref.current; if (!p || !host) return;
    p.appendChild(host);
    return () => { if (host.parentNode === p) p.removeChild(host); };
  }, [host]);
  return <div ref={ref} className="uw-panel__body" />;
}

/** [HERMIA-FE-20261023 M1-fix] N3: modal dialog — Esc cancels, Tab is trapped, focus returns to the trigger. */
function ModalDialog({label, onCancel, children}: {label: string; onCancel: () => void; children: ReactNode}) {
  const ref = useRef<HTMLDivElement>(null);
  // Capture the trigger during render: React's autoFocus runs before layout effects.
  const [prev] = useState(() => (typeof document === 'undefined' ? null : document.activeElement as HTMLElement | null));
  useLayoutEffect(() => {
    const first = ref.current?.querySelector<HTMLElement>('[autofocus],button:not([disabled])');
    first?.focus();
    return () => { if (prev && prev.isConnected) prev.focus(); };
  }, []);
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onCancel(); return; }
    if (e.key !== 'Tab' || !ref.current) return;
    const items = Array.from(ref.current.querySelectorAll<HTMLElement>('button:not([disabled]),select:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])'));
    if (!items.length) { e.preventDefault(); return; }
    const a = items[0], z = items[items.length - 1];
    if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
    else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
  };
  return (
    <div className="uw-dialog" role="dialog" aria-modal="true" aria-label={label} ref={ref} onKeyDown={onKeyDown}>
      <div className="uw-dialog__card">{children}</div>
    </div>
  );
}

function useViewport(fixed?: Viewport): Viewport {
  const read = () => fixed ?? (typeof window === 'undefined' ? {width: 1440, height: 900} : {width: window.innerWidth, height: window.innerHeight});
  const [vp, setVp] = useState<Viewport>(read);
  useEffect(() => {
    if (fixed) { setVp(fixed); return; }
    const on = () => setVp(read());
    window.addEventListener('resize', on);
    return () => window.removeEventListener('resize', on);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fixed?.width, fixed?.height]);
  return vp;
}

export function DockLayout(props: DockLayoutProps) {
  const {specs, scope, storage, renderPanel} = props;
  const rawViewport = useViewport(props.viewport);
  // [HERMIA-FE-20261023 M1-s2] measured toolbar height is reserved so main keeps MAIN_MIN_HEIGHT for real.
  const toolbarRef = useRef<HTMLDivElement>(null);
  const [toolbarH, setToolbarH] = useState(0);
  useLayoutEffect(() => {
    const el = toolbarRef.current; if (!el) return;
    const m = () => setToolbarH(Math.ceil(el.getBoundingClientRect().height));
    m();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(m); ro.observe(el); return () => ro.disconnect();
  }, []);
  const viewport = useMemo<Viewport>(() => ({...rawViewport, reserveTop: toolbarH}), [rawViewport, toolbarH]);
  const envRef = useRef({specs, viewport}); envRef.current = {specs, viewport};
  const reducer = useMemo(() => (s: LayoutState, a: Parameters<ReturnType<typeof layoutReducer>>[1]) => layoutReducer(envRef.current)(s, a), []);
  const initial = useMemo<LoadResult>(() => storage
    ? loadWorkspaceLayout(storage, scope, specs, viewport, props.loadOptions)
    : {state: layoutReducer({specs, viewport})({} as LayoutState, {type: 'reset'}), source: 'default', diagnostics: []},
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [scope.userId, scope.projectId, scope.projectInstanceId]);
  const [state, rawDispatch] = useReducer(reducer, initial.state);
  const [saveStatus, setSaveStatus] = useState<{ok: boolean; text: string}>({ok: true, text: storage ? '' : '布局仅在本次会话有效（无本地存储）'});
  const [confirmReset, setConfirmReset] = useState(false);
  // [HERMIA-FE-20261023 M1-fix] N2: persist only after an explicit user layout action that actually changed the
  // layout signature. Hydration, viewport re-fit, focus and z-order never write — so after a corrupt load the
  // original key stays untouched (backup already holds a copy) until the user really changes the layout.
  const userTouched = useRef(false);
  const lastSig = useRef(layoutSignature(initial.state));
  const rootRef = useRef<HTMLDivElement>(null);
  const dispatch = useCallback((a: LayoutAction) => {
    if (a.type !== 'focus' && a.type !== 'viewport' && a.type !== 'replace') userTouched.current = true;
    rawDispatch(a);
  }, []);

  useEffect(() => { props.onLoad?.(initial); rawDispatch({type: 'replace', state: initial.state}); userTouched.current = false; lastSig.current = layoutSignature(initial.state); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [initial]);
  useEffect(() => { rawDispatch({type: 'viewport'}); }, [viewport.width, viewport.height, viewport.reserveTop]);

  useEffect(() => {
    if (!storage || !userTouched.current) return;
    const sig = layoutSignature(state);
    if (sig === lastSig.current) return;
    lastSig.current = sig;
    const r = saveWorkspaceLayout(storage, scope, state);
    setSaveStatus(r.ok ? {ok: true, text: '布局已保存到本机'} : {ok: false, text: `布局保存失败，仅本次会话有效：${r.error}`});
  }, [state, storage, scope]);

  const close = useCallback((id: string) => dispatch({type: 'close', id}), []);
  const guard = useDirtyCloseGuard(close);

  // [HERMIA-FE-20261023 M1-s2] layout actions via the existing workbench ActionRegistry.
  const [ownTracker] = useState(() => new LifecycleTracker());
  const tracker = props.tracker ?? ownTracker;
  const registry = useMemo(() => props.actionRegistry ?? new ActionRegistry(tracker), [props.actionRegistry, tracker]);
  const table = useMemo(() => props.shortcutTable ?? new ShortcutTable(), [props.shortcutTable]);
  const [, setPendingTick] = useState(0);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [shortcutConflicts, setShortcutConflicts] = useState<string[]>([]);
  useEffect(() => {
    const reg = registerLayoutActions(registry, table, {
      getState: () => stateRef.current, specs, dispatch, requestReset: () => setConfirmReset(true),
      // [HERMIA-FE-20261023 M1-s2fix] MUST-FIX 3: compare with what 'reset' would produce (focus / z ignored).
      isDefault: () => layoutSignature(stateRef.current) === layoutSignature(layoutReducer(envRef.current)(stateRef.current, {type: 'reset'})),
    }, undefined, props.actionOptions);
    setShortcutConflicts(reg.conflicts.map(c => `快捷键 ${displayShortcut(c.shortcut)} 已被占用，「${registry.get(c.actionId)?.label ?? ''}」未绑定快捷键`));
    return reg.dispose;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registry, table]);
  const actionCtx = (targetId: string | null = null, input?: unknown): ActionContext =>
    ({token: tracker.current(), targetId, targetVersion: null, permissions: new Set<string>(), input});
  const availability = (id: LayoutActionId, targetId: string | null = null, input?: unknown) =>
    registry.get(id) ? registry.availability(id, actionCtx(targetId, input)) : {enabled: false as const, reason: '动作未注册'};
  const runAction = async (id: LayoutActionId, targetId: string | null = null, input?: unknown): Promise<ExecuteResult> => {
    const p = registry.execute(id, actionCtx(targetId, input));
    setPendingTick(n => n + 1);
    // [HERMIA-FE-20261023 M1-s2fix] re-render on the busy edge so aria-busy is visible for MIN_BUSY_MS.
    await Promise.resolve(); setPendingTick(n => n + 1);
    const r = await p;
    setPendingTick(n => n + 1);
    if (r.status === 'blocked') setActionMsg(r.reason);
    else if (r.status === 'error') setActionMsg(`操作没有完成：${r.error instanceof Error ? r.error.message : '未知原因'}`);
    else setActionMsg(null);
    return r;
  };
  useEffect(() => {
    const ids = Object.values(LAYOUT_ACTION_IDS);
    const onKey = (e: globalThis.KeyboardEvent) => {
      const id = actionIdForKey(e, table, ids) as LayoutActionId | null; if (!id) return;
      e.preventDefault();
      void runAction(id, id === LAYOUT_ACTION_IDS.toggleCollapse ? stateRef.current.focusId : null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registry, table]);
  const pendingOf = (id: LayoutActionId, targetId: string | null = null) => registry.isPending(id, targetId);

  // ---- pointer drag (header) ----
  const drag = useRef<{id: string; startX: number; startY: number; ox: number; oy: number; floating: boolean} | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);
  const dragZone = dropTarget?.zone ?? null;
  const stateRef = useRef(state); stateRef.current = state;
  // [HERMIA-FE-20261023 M1-s2] precise drop: zone from pointer, insertion index from the zone's other panels' rects.
  const computeDrop = (id: string, x: number, y: number): DropTarget | null => {
    const root = rootRef.current; if (!root) return null;
    const rr = root.getBoundingClientRect();
    const zone = zoneFromPoint(x, y, rr);
    const fromFloat = stateRef.current.frames[id]?.dock === 'float';
    // [HERMIA-FE-20261023 M1-s2fix] nice-to-have: a floating panel docks only when released over an edge zone it
    // allows; the centre is where floats live, so no target there (and no indicator).
    if (fromFloat && (zone === 'main' || !specs.find(s => s.id === id)?.docks.includes(zone))) return null;
    const spec = specs.find(s => s.id === id);
    const allowed = !!spec?.docks.includes(zone);
    const axis = dropAxis(zone, stateRef.current.split);
    const others = Array.from(root.querySelectorAll<HTMLElement>(`section.uw-panel[data-dock="${zone}"]`)).filter(el => el.dataset.panelId !== id);
    const rects = others.map(el => el.getBoundingClientRect());
    const index = dropIndexFromPoint(axis, {x, y}, rects);
    let line: {left: number; top: number; width: number; height: number};
    if (!rects.length) {
      // [HERMIA-FE-20261023 M1-s2fix] MUST-FIX 1: every zone has a measurable box; never fall back to the root rect.
      const el = root.querySelector<HTMLElement>(`[data-zone-box="${zone}"]:not([data-zone-ghost])`);
      const zr = el?.getBoundingClientRect();
      if (zr && zr.width > 0 && zr.height > 0) line = {left: zr.left - rr.left, top: zr.top - rr.top, width: zr.width, height: zr.height};
      else {
        const bodyTop = bodyRef.current ? Math.max(0, bodyRef.current.getBoundingClientRect().top - rr.top) : 0;
        line = emptyZoneBox(zone, rr, bodyTop) ?? {left: 0, top: bodyTop, width: 0, height: 0};
      }
    } else {
      const ref = rects[Math.min(index, rects.length - 1)]; const after = index >= rects.length;
      line = axis === 'y'
        ? {left: ref.left - rr.left, top: (after ? ref.bottom : ref.top) - rr.top - 1, width: ref.width, height: 3}
        : {left: (after ? ref.right : ref.left) - rr.left - 1, top: ref.top - rr.top, width: 3, height: ref.height};
    }
    return {zone, index, allowed, axis, line, empty: !rects.length};
  };
  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = drag.current; if (!d) return;
      if (d.floating) dispatch({type: 'moveFloat', id: d.id, x: d.ox + e.clientX - d.startX, y: d.oy + e.clientY - d.startY});
      setDropTarget(computeDrop(d.id, e.clientX, e.clientY));
    };
    const up = (e: PointerEvent) => {
      const d = drag.current; if (!d) return; drag.current = null; setDropTarget(null);
      if (!rootRef.current) return;
      if (Math.abs(e.clientX - d.startX) + Math.abs(e.clientY - d.startY) < 4) return; // click, not drag
      const t = computeDrop(d.id, e.clientX, e.clientY);
      if (t && t.allowed) dispatch({type: 'dock', id: d.id, dock: t.zone, index: t.index});
    };
    // [HERMIA-FE-20261023 M1-s2fix] MUST-FIX 2: Esc cancels an active drag — no drop, float returns to its origin.
    const esc = (e: globalThis.KeyboardEvent) => {
      const d = drag.current; if (!d || e.key !== 'Escape') return;
      e.preventDefault(); e.stopPropagation();
      drag.current = null; setDropTarget(null);
      if (d.floating) dispatch({type: 'moveFloat', id: d.id, x: d.ox, y: d.oy});
    };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); window.addEventListener('keydown', esc, true);
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); window.removeEventListener('keydown', esc, true); };
  }, []);
  const startDrag = (f: PanelFrame) => (e: RPointerEvent) => {
    if ((e.target as HTMLElement).closest('button,select')) return;
    dispatch({type: 'focus', id: f.id});
    drag.current = {id: f.id, startX: e.clientX, startY: e.clientY, ox: f.floatRect?.x ?? 0, oy: f.floatRect?.y ?? 0, floating: f.dock === 'float'};
  };

  // ---- resize handle ----
  const resizeDrag = useRef<{id: string; start: number; size: number; axis: 'x' | 'y'; sign: number} | null>(null);
  useEffect(() => {
    const move = (e: PointerEvent) => {
      const r = resizeDrag.current; if (!r) return;
      const delta = (r.axis === 'x' ? e.clientX : e.clientY) - r.start;
      dispatch({type: 'resize', id: r.id, size: r.size + r.sign * delta});
    };
    const up = () => { resizeDrag.current = null; };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
  }, []);

  const specOf = (id: string) => specs.find(s => s.id === id)!;
  // [HERMIA-FE-20261023 M1-fix] MF-1 stable per-panel host elements.
  const hosts = useRef(new Map<string, HTMLDivElement>());
  const hostFor = (id: string): HTMLDivElement | undefined => {
    if (typeof document === 'undefined') return undefined;
    let el = hosts.current.get(id);
    if (!el) { el = document.createElement('div'); el.className = 'uw-panel__host'; el.dataset.panelHost = id; hosts.current.set(id, el); }
    return el;
  };
  const api = useCallback((id: string): PanelRenderApi => ({registerDirty: src => guard.register(id, src)}), [guard.register]);

  const resizeHandle = (f: PanelFrame) => {
    if (f.dock === 'main' || f.dock === 'float' || f.collapsed) return null;
    const axis = f.dock === 'bottom' ? 'y' : 'x';
    const sign = f.dock === 'left' ? 1 : -1; // right/bottom grow toward the start
    const spec = specOf(f.id);
    const onKey = (e: KeyboardEvent) => {
      const grow = axis === 'x' ? (e.key === 'ArrowRight' ? sign : e.key === 'ArrowLeft' ? -sign : 0) : (e.key === 'ArrowUp' ? 1 : e.key === 'ArrowDown' ? -1 : 0);
      if (!grow) return; e.preventDefault(); dispatch({type: 'resize', id: f.id, size: f.size + grow * KEY_STEP});
    };
    return (
      <div role="separator" tabIndex={0} aria-label={`调整「${spec.title}」大小`} aria-orientation={axis === 'x' ? 'vertical' : 'horizontal'}
        aria-valuenow={f.size} aria-valuemin={spec.minSize}
        className={`uw-resize uw-resize--${axis}`} data-testid={`resize-${f.id}`} onKeyDown={onKey}
        onPointerDown={e => { e.preventDefault(); resizeDrag.current = {id: f.id, start: axis === 'x' ? e.clientX : e.clientY, size: f.size, axis, sign}; }} />
    );
  };

  const panel = (f: PanelFrame) => {
    const spec = specOf(f.id);
    const style = f.dock === 'float' && f.floatRect
      ? {left: f.floatRect.x, top: f.floatRect.y, width: f.floatRect.w, height: f.floatRect.h, zIndex: 100 + f.z}
      : f.dock === 'left' || f.dock === 'right' ? {width: f.collapsed ? undefined : f.size} : f.dock === 'bottom' ? {height: f.collapsed ? undefined : f.size} : undefined;
    return (
      <section key={f.id} role="region" aria-label={spec.title} tabIndex={-1} data-testid={`panel-${f.id}`} data-panel-id={f.id} data-dock={f.dock}
        data-collapsed={f.collapsed} data-focused={state.focusId === f.id} data-z={f.z}
        className={`uw-panel${f.dock === 'float' ? ' uw-float' : ''}`} style={style} onFocusCapture={() => dispatch({type: 'focus', id: f.id})}>
        <header className="uw-panel__head" data-testid={`drag-${f.id}`} onPointerDown={startDrag(f)}>
          <span className="uw-panel__title">{spec.title}</span>
          <button type="button" className="uw-btn" aria-expanded={!f.collapsed} data-action-id={LAYOUT_ACTION_IDS.toggleCollapse}
            aria-busy={pendingOf(LAYOUT_ACTION_IDS.toggleCollapse, f.id) || undefined} onClick={() => { void runAction(LAYOUT_ACTION_IDS.toggleCollapse, f.id); }}>{f.collapsed ? '展开' : '折叠'}</button>
          <select className="uw-select" aria-label={`「${spec.title}」停靠位置`} value={f.dock} onChange={e => dispatch({type: 'dock', id: f.id, dock: e.target.value as DockZone})}>
            {spec.docks.map(d => <option key={d} value={d}>{DOCK_LABEL[d]}</option>)}
          </select>
          <button type="button" className="uw-btn" aria-label={`关闭「${spec.title}」`} onClick={() => guard.requestClose(f.id)}>关闭</button>
        </header>
        <PanelSlot host={hostFor(f.id)} />
      </section>
    );
  };
  const withHandle = (f: PanelFrame) => f.dock === 'left'
    ? [panel(f), <span key={`h-${f.id}`}>{resizeHandle(f)}</span>]
    : [<span key={`h-${f.id}`}>{resizeHandle(f)}</span>, panel(f)];

  const left = panelsIn(state, 'left'); const right = panelsIn(state, 'right'); const bottom = panelsIn(state, 'bottom');
  const main = panelsIn(state, 'main'); const floats = panelsIn(state, 'float');
  const visibleMain = state.split === 'single' ? main.slice(0, 1) : main.slice(0, 2);
  const hiddenMain = main.slice(visibleMain.length);
  const closed = closedPanels(state);
  const reopenAv = availability(LAYOUT_ACTION_IDS.reopen);
  const resetAv = availability(LAYOUT_ACTION_IDS.reset);
  const pendingSpec = guard.pending ? specOf(guard.pending.panelId) : null;
  const recovered = initial.source === 'fallback-corrupt';
  const status = !saveStatus.ok ? saveStatus : recovered
    ? {ok: false, text: '布局数据无法读取，已用默认布局；原数据已备份，未被覆盖'}
    : saveStatus;

  return (
    <div className="uw-layout" ref={rootRef} data-testid="dock-layout" data-source={initial.source}>
      <div className="uw-toolbar" role="toolbar" aria-label="布局" ref={toolbarRef}>
        {props.toolbarStart}
        <label>布局 <select className="uw-select" aria-label="分屏方式" data-action-id={LAYOUT_ACTION_IDS.split} value={state.split}
          aria-busy={pendingOf(LAYOUT_ACTION_IDS.split) || undefined} onChange={e => { void runAction(LAYOUT_ACTION_IDS.split, null, e.target.value as SplitMode); }}>
          {(Object.keys(SPLIT_LABEL) as SplitMode[]).map(m => <option key={m} value={m}>{SPLIT_LABEL[m]}</option>)}
        </select></label>
        <label>重新打开 <select className="uw-select" aria-label="重新打开面板" data-action-id={LAYOUT_ACTION_IDS.reopen} value=""
          disabled={!reopenAv.enabled} aria-busy={pendingOf(LAYOUT_ACTION_IDS.reopen) || undefined} title={reopenAv.enabled ? undefined : reopenAv.reason}
          onChange={e => { if (e.target.value) void runAction(LAYOUT_ACTION_IDS.reopen, e.target.value, e.target.value); }}>
          <option value="">{reopenAv.enabled ? '选择面板…' : reopenAv.reason}</option>
          {closed.map(f => <option key={f.id} value={f.id}>{specOf(f.id).title}</option>)}
        </select></label>
        {hiddenMain.length > 0 && <label>中间显示 <select className="uw-select" aria-label="切换中间面板" value="" onChange={e => { if (e.target.value) dispatch({type: 'dock', id: e.target.value, dock: 'main', index: 0}); }}>
          <option value="">选择…</option>{hiddenMain.map(f => <option key={f.id} value={f.id}>{specOf(f.id).title}</option>)}
        </select></label>}
        {/* [HERMIA-FE-20261023 M1-s2fix] MUST-FIX 3: disabled with a Chinese reason when already default. */}
        <button type="button" className="uw-btn" data-action-id={LAYOUT_ACTION_IDS.reset} aria-busy={pendingOf(LAYOUT_ACTION_IDS.reset) || undefined}
          disabled={!resetAv.enabled} title={resetAv.enabled ? undefined : resetAv.reason} aria-describedby={resetAv.enabled ? undefined : 'uw-reset-reason'}
          onClick={() => { void runAction(LAYOUT_ACTION_IDS.reset); }}>恢复默认布局</button>
        {!resetAv.enabled && <span id="uw-reset-reason" className="uw-toolbar__hint" data-testid="reset-reason">{resetAv.reason}</span>}
        <span className="uw-toolbar__status" role="status" data-tone={status.ok && !actionMsg && !shortcutConflicts.length ? undefined : 'warn'}>
          {[actionMsg, ...shortcutConflicts, status.text].filter(Boolean).join('；')}</span>
      </div>
      <div className="uw-body" ref={bodyRef}>
        {left.length > 0 && <div className="uw-col uw-col--left" data-zone-box="left" style={{display: 'flex', flexDirection: 'row'}}><div className="uw-col">{left.map(f => panel(f))}</div>{left[0] && resizeHandle(left[0])}</div>}
        <div className="uw-main" data-split={state.split} data-testid="main-zone" data-zone-box="main">
          {visibleMain.map(f => panel(f))}
        </div>
        {right.length > 0 && <div className="uw-col uw-col--right" data-zone-box="right" style={{display: 'flex', flexDirection: 'row'}}>{right[0] && resizeHandle(right[0])}<div className="uw-col">{right.map(f => panel(f))}</div></div>}
      </div>
      {bottom.length > 0 && <div data-zone-box="bottom" style={{display: 'flex', flexDirection: 'column'}}>{bottom[0] && resizeHandle(bottom[0])}<div className="uw-bottom">{bottom.map(f => panel(f))}</div></div>}
      {floats.map(f => panel(f))}
      {Object.values(state.frames).filter(f => f.open).map(f => {
        const host = hostFor(f.id); if (!host) return null;
        return createPortal(
          <div className="uw-panel__content" onFocusCapture={() => dispatch({type: 'focus', id: f.id})}>{renderPanel(f.id, api(f.id))}</div>,
          host, f.id);
      })}
      {dragZone && <div className="uw-dropzones" data-testid="drop-hint" data-zone={dragZone} aria-hidden="true" />}
      {dropTarget && (['left', 'right', 'bottom'] as const).filter(z => !panelsIn(state, z).length).map(z => {
        // [HERMIA-FE-20261023 M1-s2fix] MUST-FIX 1: faint outline of each EMPTY dock zone while dragging.
        const rr = rootRef.current?.getBoundingClientRect(); if (!rr) return null;
        const bt = bodyRef.current ? Math.max(0, bodyRef.current.getBoundingClientRect().top - rr.top) : 0;
        const b = emptyZoneBox(z, rr, bt); if (!b) return null;
        return <div key={`ghost-${z}`} className="uw-zone-ghost" data-zone-box={z} data-zone-ghost="" data-testid={`zone-ghost-${z}`} aria-hidden="true"
          style={{left: b.left, top: b.top, width: b.width, height: b.height}} />;
      })}
      {dropTarget && (
        <div className={`uw-drop-indicator${dropTarget.empty ? ' uw-drop-indicator--zone' : ''}`} data-testid="drop-indicator" aria-hidden="true"
          data-zone={dropTarget.zone} data-index={dropTarget.index} data-allowed={dropTarget.allowed} data-axis={dropTarget.axis}
          style={{left: dropTarget.line.left, top: dropTarget.line.top, width: dropTarget.line.width, height: dropTarget.line.height}} />
      )}
      {dropTarget && !dropTarget.allowed && <div className="uw-drop-note" role="status">这个面板不能放到{DOCK_LABEL[dropTarget.zone]}</div>}
      {confirmReset && (
        <ModalDialog label="恢复默认布局" onCancel={() => setConfirmReset(false)}>
          <p>只恢复面板位置和大小，不会删除作品、草稿或任务。</p>
          <div className="uw-dialog__actions">
            <button type="button" className="uw-btn" autoFocus onClick={() => setConfirmReset(false)}>取消</button>
            <button type="button" className="uw-btn" onClick={() => { dispatch({type: 'reset'}); setConfirmReset(false); }}>恢复默认</button>
          </div>
        </ModalDialog>
      )}
      {guard.pending && pendingSpec && (
        <ModalDialog label={`关闭「${pendingSpec.title}」`} onCancel={guard.cancel}>
          <p>「{pendingSpec.title}」有未保存的修改。</p>
          {guard.pending.error && <p role="alert">保存失败：{String(guard.pending.error).replace(/[。.\s]+$/u, '')}。修改仍在面板里，没有保存。</p>}
          <div className="uw-dialog__actions">
            <button type="button" className="uw-btn" autoFocus onClick={guard.cancel}>取消</button>
            <button type="button" className="uw-btn" onClick={guard.discard}>放弃修改</button>
            <button type="button" className="uw-btn" disabled={guard.pending.saving} onClick={() => { void guard.save(); }}>{guard.pending.saving ? '保存中…' : '保存并关闭'}</button>
          </div>
        </ModalDialog>
      )}
    </div>
  );
}
