/**
 * [HERMIA-FE-20261025 U2-M6] Wraps an existing canvas (RebuildCanvas unmodified) and adds multi-select:
 * Ctrl/⌘+click toggles a node, Shift+drag draws a selection box. Plain clicks pass through untouched (the canvas's own
 * single select stays the direct-select path). Outlines are an overlay; the canvas DOM/state is never mutated.
 * Keyboard: Esc clears the multi-selection. No network, no model call.
 */
import {useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode} from 'react';
import type {CanvasKind} from '../../rebuild/canvas/RebuildCanvas';
import {normRect, selectBox, selectToggle, type CanvasSelection, type Rect} from './selection';

const NODE_SEL = '[data-node-id]';
export function CanvasSelectionLayer({canvas, selection, onChange, children}: {
  canvas: CanvasKind; selection: CanvasSelection; onChange: (s: CanvasSelection) => void; children: ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<Rect | null>(null);
  const start = useRef<{x: number; y: number; additive: boolean} | null>(null);
  const [outlines, setOutlines] = useState<{id: string; r: Rect}[]>([]);
  const nodeRects = useCallback(() => {
    const host = root.current; if (!host) return [];
    const o = host.getBoundingClientRect();
    return [...host.querySelectorAll<Element>(NODE_SEL)].map(el => {
      const r = el.getBoundingClientRect();
      return {id: el.getAttribute('data-node-id')!, rect: {x: r.left - o.left, y: r.top - o.top, w: r.width, h: r.height}};
    });
  }, []);
  const mine = selection.canvas === canvas && selection.ids.length > 1;
  const refresh = useCallback(() => {
    if (!mine) { setOutlines([]); return; }
    const rs = nodeRects(); setOutlines(selection.ids.flatMap(id => { const n = rs.find(x => x.id === id); return n ? [{id, r: n.rect}] : []; }));
  }, [mine, nodeRects, selection.ids]);
  useLayoutEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    if (!mine) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && root.current?.contains(document.activeElement)) onChange({canvas, ids: []}); };
    document.addEventListener('keydown', onKey); return () => document.removeEventListener('keydown', onKey);
  }, [mine, onChange, canvas]);
  const local = (e: {clientX: number; clientY: number}) => { const o = root.current!.getBoundingClientRect(); return {x: e.clientX - o.left, y: e.clientY - o.top}; };
  const onDownCapture = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const nodeEl = (e.target as Element).closest?.(NODE_SEL);
    if ((e.ctrlKey || e.metaKey) && nodeEl) { e.stopPropagation(); e.preventDefault(); onChange(selectToggle(selection, canvas, nodeEl.getAttribute('data-node-id')!)); return; }
    if (e.shiftKey && !(e.target as Element).closest?.('[data-port]')) { e.stopPropagation(); e.preventDefault(); const p = local(e); start.current = {...p, additive: e.ctrlKey || e.metaKey}; setBox({x: p.x, y: p.y, w: 0, h: 0}); }
  };
  const onMoveCapture = (e: React.PointerEvent) => { if (!start.current) return; e.stopPropagation(); setBox(normRect(start.current, local(e))); };
  const onUpCapture = (e: React.PointerEvent) => {
    const s = start.current; if (!s) { refresh(); return; }
    e.stopPropagation(); start.current = null;
    const r = normRect(s, local(e)); setBox(null);
    if (r.w < 3 && r.h < 3) return;
    onChange(selectBox(selection, canvas, r, nodeRects(), s.additive));
  };
  return <div ref={root} data-testid={`uw-sel-layer-${canvas}`} data-selected-count={selection.canvas === canvas ? selection.ids.length : 0}
    style={{position: 'relative', height: '100%'}} onPointerDownCapture={onDownCapture} onPointerMoveCapture={onMoveCapture} onPointerUpCapture={onUpCapture} onWheelCapture={() => requestAnimationFrame(refresh)}>
    {children}
    {box && <div aria-hidden data-testid="uw-sel-box" style={{position: 'absolute', left: box.x, top: box.y, width: box.w, height: box.h, border: '1px dashed var(--uw-accent, #5aa0d8)', background: 'rgba(90,160,216,.12)', pointerEvents: 'none'}} />}
    {outlines.map(o => <div key={o.id} aria-hidden data-testid="uw-sel-outline" data-node-id={o.id}
      style={{position: 'absolute', left: o.r.x - 3, top: o.r.y - 3, width: o.r.w + 6, height: o.r.h + 6, border: '2px solid var(--uw-accent, #5aa0d8)', borderRadius: 10, pointerEvents: 'none'}} />)}
  </div>;
}
