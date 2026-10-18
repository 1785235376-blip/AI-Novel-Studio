import { useLayoutEffect, useRef, useState } from 'react';
import { Button } from '../ui/primitives';
import { clampGraphPosition, graphWorldToScreen, zoomGraphAt } from './graphCanvasGeometry';
import { MEDIA_CARD_HEIGHT, MEDIA_CARD_WIDTH, visibleMediaCards } from './mediaCanvasGeometry';
import type { CanvasDefinition, CanvasReferenceState } from './studioCanvasViewClient';
type Props = { definition: CanvasDefinition; states: Map<string, CanvasReferenceState>; selected: string; query: string; owner: object;
  disabled: boolean; isCurrent: () => boolean; onSelect: (id: string) => void; onChange: (definition: CanvasDefinition) => void;
  onSize: (size: { width: number; height: number }) => void };
type Gesture = { pointer: number; card?: string; start: { x: number; y: number }; source: CanvasDefinition; token: object; latest: CanvasDefinition; moved: boolean };
/** Presentation interaction only. One explicit pointer completion changes the original local draft. */
export function MediaCardViewport(props: Props) {
  const root = useRef<HTMLDivElement>(null), alive = useRef(true), gesture = useRef<Gesture>();
  const live = useRef(props); live.current = props;
  const [preview, setPreview] = useState<{ token: object; value: CanvasDefinition }>();
  const [size, setSize] = useState({ width: 800, height: 480 });
  const values = [props.definition, props.owner, props.disabled];
  const fence = useRef({ values, token: {} });
  if (values.some((v, i) => !Object.is(v, fence.current.values[i]))) fence.current = { values, token: {} };
  const token = fence.current.token;
  const current = () => alive.current && fence.current.token === token && !live.current.disabled && live.current.isCurrent();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; gesture.current = undefined; }; }, []);
  useLayoutEffect(() => { gesture.current = undefined; setPreview(undefined); }, [token]);
  useLayoutEffect(() => {
    const node = root.current; if (!node) return;
    const resize = () => { const r = node.getBoundingClientRect(); if (r.width > 0 && r.height > 0) { const next = { width: r.width, height: r.height }; setSize(next); live.current.onSize(next); } };
    resize(); if (typeof ResizeObserver === 'undefined') return; const observer = new ResizeObserver(resize); observer.observe(node); return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => {
    const node = root.current; if (!node) return;
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey || !current() || gesture.current || event.deltaY === 0) return;
      event.preventDefault(); const rect = node.getBoundingClientRect();
      live.current.onChange({ ...props.definition, viewport: zoomGraphAt(props.definition.viewport, { x: event.clientX - rect.left, y: event.clientY - rect.top }, props.definition.viewport.zoom * (event.deltaY < 0 ? 1.1 : 1 / 1.1)) });
    };
    node.addEventListener('wheel', wheel, { passive: false });
    return () => node.removeEventListener('wheel', wheel);
  }, [token]);
  const definition = preview?.token === token ? preview.value : props.definition;
  const shown = visibleMediaCards(definition, size.width, size.height, props.query);
  function start(event: React.PointerEvent<HTMLDivElement>) {
    if (!current() || gesture.current || event.button !== 0) return;
    const card = (event.target as HTMLElement).closest<HTMLElement>('[data-media-card]')?.dataset.mediaCard;
    if (card && !props.definition.cards.some(c => c.id === card)) return;
    if (!card && event.target !== event.currentTarget) return;
    gesture.current = { pointer: event.pointerId, card, start: { x: event.clientX, y: event.clientY }, source: props.definition, token, latest: props.definition, moved: false };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  function move(event: React.PointerEvent<HTMLDivElement>) {
    const g = gesture.current; if (!g || g.pointer !== event.pointerId || g.token !== token || !current()) return;
    const x = event.clientX - g.start.x, y = event.clientY - g.start.y;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !g.moved && Math.abs(x) + Math.abs(y) < 3) return;
    g.moved = true;
    g.latest = g.card ? { ...g.source, cards: g.source.cards.map(c => c.id === g.card ? { ...c, position: {
      x: clampGraphPosition(c.position.x + x / g.source.viewport.zoom), y: clampGraphPosition(c.position.y + y / g.source.viewport.zoom) } } : c) }
      : { ...g.source, viewport: { ...g.source.viewport, x: clampGraphPosition(g.source.viewport.x + x), y: clampGraphPosition(g.source.viewport.y + y) } };
    setPreview({ token, value: g.latest });
  }
  function finish(event: React.PointerEvent<HTMLDivElement>, cancel = false) {
    const g = gesture.current; if (!g || g.pointer !== event.pointerId) return;
    gesture.current = undefined; setPreview(undefined);
    if (!cancel && g.moved && g.token === token && current()) live.current.onChange(g.latest);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }
  return <><div className="media-canvas__viewport" ref={root} aria-label="媒体卡片视口" tabIndex={0}
    onPointerDown={start} onPointerMove={move} onPointerUp={event => finish(event)} onPointerCancel={event => finish(event, true)} onLostPointerCapture={event => finish(event, true)}
    onKeyDown={event => {
      if (event.key === 'Escape') { gesture.current = undefined; setPreview(undefined); return; }
      if (!current() || gesture.current || event.ctrlKey || event.altKey || event.metaKey || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      event.preventDefault(); const step = event.shiftKey ? 64 : 16, x = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0, y = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
      const card = (event.target as HTMLElement).closest<HTMLElement>('[data-media-card]')?.dataset.mediaCard;
      live.current.onChange(card ? { ...props.definition, cards: props.definition.cards.map(c => c.id === card ? { ...c, position: { x: clampGraphPosition(c.position.x + x), y: clampGraphPosition(c.position.y + y) } } : c) }
        : { ...props.definition, viewport: { ...props.definition.viewport, x: clampGraphPosition(props.definition.viewport.x + x), y: clampGraphPosition(props.definition.viewport.y + y) } });
    }}>
    {shown.cards.map(card => { const point = graphWorldToScreen(card.position, definition.viewport), state = props.states.get(card.id); return <div key={card.id} data-media-card={card.id} className="media-canvas__card" style={{ left: point.x, top: point.y, width: MEDIA_CARD_WIDTH * definition.viewport.zoom, height: MEDIA_CARD_HEIGHT * definition.viewport.zoom }}>
      <Button aria-pressed={card.id === props.selected} onClick={() => live.current.onSelect(card.id)}>{state?.filename ?? card.id}</Button><p>{card.asset?.kind ?? '不可用'} · {state?.state ?? '待保存校验'}</p><small>{card.asset?.asset_id ?? '源绑定已隐藏'}</small>
    </div>; })}
  </div><p>共 {props.definition.cards.length}/1000 张，匹配 {shown.matched} 张，当前视口渲染 {shown.cards.length} 张。{shown.clipped && '重叠卡片较多，仅显示前 128 张；请缩小查找范围或调整视口。'}</p>
  <p>拖动卡片调整位置，拖动空白处平移；Ctrl＋滚轮缩放。方向键移动焦点卡片或视口，Shift 加快，Esc 取消拖动。完成后仍需保存。</p></>;
}
