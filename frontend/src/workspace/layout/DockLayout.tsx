/**
 * [HERMIA-FE-20261023 M1] DockLayout — isolated unified window/layout component.
 * Real pointer drag to dock zones, float drag, resize handles (pointer + keyboard), collapse,
 * close (dirty guard) / reopen menu, split switch, reset default (confirm), persistence status.
 * NOT mounted by App.tsx yet; wiring lives in artifacts/unified-workspace-refactor/patches/.
 */
import {useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState, type KeyboardEvent, type PointerEvent as RPointerEvent, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import type {LayoutScope, StorageLike} from '../../workbench/layout';
import {
  closedPanels, layoutReducer, panelsIn, zoneFromPoint,
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
}

const DOCK_LABEL: Record<DockZone, string> = {left: '左侧', main: '中间', right: '右侧', bottom: '底部', float: '浮动'};
const SPLIT_LABEL: Record<SplitMode, string> = {single: '单栏', 'split-h': '左右分屏', 'split-v': '上下分屏'};
const KEY_STEP = 16;

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
  const viewport = useViewport(props.viewport);
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
  useEffect(() => { rawDispatch({type: 'viewport'}); }, [viewport.width, viewport.height]);

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

  // ---- pointer drag (header) ----
  const drag = useRef<{id: string; startX: number; startY: number; ox: number; oy: number; floating: boolean} | null>(null);
  const [dragZone, setDragZone] = useState<DockZone | null>(null);
  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = drag.current; if (!d) return;
      if (d.floating) dispatch({type: 'moveFloat', id: d.id, x: d.ox + e.clientX - d.startX, y: d.oy + e.clientY - d.startY});
      else if (rootRef.current) setDragZone(zoneFromPoint(e.clientX, e.clientY, rootRef.current.getBoundingClientRect()));
    };
    const up = (e: PointerEvent) => {
      const d = drag.current; if (!d) return; drag.current = null; setDragZone(null);
      if (d.floating || !rootRef.current) return;
      if (Math.abs(e.clientX - d.startX) + Math.abs(e.clientY - d.startY) < 4) return; // click, not drag
      dispatch({type: 'dock', id: d.id, dock: zoneFromPoint(e.clientX, e.clientY, rootRef.current.getBoundingClientRect())});
    };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
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
      <section key={f.id} role="region" aria-label={spec.title} tabIndex={-1} data-testid={`panel-${f.id}`} data-dock={f.dock}
        data-collapsed={f.collapsed} data-focused={state.focusId === f.id} data-z={f.z}
        className={`uw-panel${f.dock === 'float' ? ' uw-float' : ''}`} style={style} onFocusCapture={() => dispatch({type: 'focus', id: f.id})}>
        <header className="uw-panel__head" data-testid={`drag-${f.id}`} onPointerDown={startDrag(f)}>
          <span className="uw-panel__title">{spec.title}</span>
          <button type="button" className="uw-btn" aria-expanded={!f.collapsed} onClick={() => dispatch({type: 'collapse', id: f.id})}>{f.collapsed ? '展开' : '折叠'}</button>
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
  const pendingSpec = guard.pending ? specOf(guard.pending.panelId) : null;
  const recovered = initial.source === 'fallback-corrupt';
  const status = !saveStatus.ok ? saveStatus : recovered
    ? {ok: false, text: '布局数据无法读取，已用默认布局；原数据已备份，未被覆盖'}
    : saveStatus;

  return (
    <div className="uw-layout" ref={rootRef} data-testid="dock-layout" data-source={initial.source}>
      <div className="uw-toolbar" role="toolbar" aria-label="布局">
        <label>布局 <select className="uw-select" aria-label="分屏方式" value={state.split} onChange={e => dispatch({type: 'split', mode: e.target.value as SplitMode})}>
          {(Object.keys(SPLIT_LABEL) as SplitMode[]).map(m => <option key={m} value={m}>{SPLIT_LABEL[m]}</option>)}
        </select></label>
        <label>重新打开 <select className="uw-select" aria-label="重新打开面板" value="" disabled={!closed.length} onChange={e => { if (e.target.value) dispatch({type: 'reopen', id: e.target.value}); }}>
          <option value="">{closed.length ? '选择面板…' : '没有已关闭的面板'}</option>
          {closed.map(f => <option key={f.id} value={f.id}>{specOf(f.id).title}</option>)}
        </select></label>
        {hiddenMain.length > 0 && <label>中间显示 <select className="uw-select" aria-label="切换中间面板" value="" onChange={e => { if (e.target.value) dispatch({type: 'dock', id: e.target.value, dock: 'main', index: 0}); }}>
          <option value="">选择…</option>{hiddenMain.map(f => <option key={f.id} value={f.id}>{specOf(f.id).title}</option>)}
        </select></label>}
        <button type="button" className="uw-btn" onClick={() => setConfirmReset(true)}>恢复默认布局</button>
        <span className="uw-toolbar__status" role="status" data-tone={status.ok ? undefined : 'warn'}>{status.text}</span>
      </div>
      <div className="uw-body">
        {left.length > 0 && <div className="uw-col uw-col--left" style={{display: 'flex', flexDirection: 'row'}}><div className="uw-col">{left.map(f => panel(f))}</div>{left[0] && resizeHandle(left[0])}</div>}
        <div className="uw-main" data-split={state.split} data-testid="main-zone">
          {visibleMain.map(f => panel(f))}
        </div>
        {right.length > 0 && <div className="uw-col uw-col--right" style={{display: 'flex', flexDirection: 'row'}}>{right[0] && resizeHandle(right[0])}<div className="uw-col">{right.map(f => panel(f))}</div></div>}
      </div>
      {bottom.length > 0 && <div style={{display: 'flex', flexDirection: 'column'}}>{bottom[0] && resizeHandle(bottom[0])}<div className="uw-bottom">{bottom.map(f => panel(f))}</div></div>}
      {floats.map(f => panel(f))}
      {Object.values(state.frames).filter(f => f.open).map(f => {
        const host = hostFor(f.id); if (!host) return null;
        return createPortal(
          <div className="uw-panel__content" onFocusCapture={() => dispatch({type: 'focus', id: f.id})}>{renderPanel(f.id, api(f.id))}</div>,
          host, f.id);
      })}
      {dragZone && <div className="uw-dropzones" data-testid="drop-hint" data-zone={dragZone} aria-hidden="true" />}
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
          {guard.pending.error && <p role="alert">保存失败：{guard.pending.error}。修改仍在面板里，没有保存。</p>}
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
