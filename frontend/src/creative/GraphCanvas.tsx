import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react';
import { Hand, MousePointer2, Trash2, ZoomIn, ZoomOut } from 'lucide-react';
import { Badge, Button } from '../ui/primitives';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import type { StudioGraphDefinition, StudioGraphPosition } from './studioGraphTypes';
import {
  GRAPH_MAX_ZOOM, GRAPH_MIN_ZOOM, GRAPH_NODE_HEADER_HEIGHT, GRAPH_NODE_WIDTH, GRAPH_PORT_ROW_HEIGHT,
  clampGraphPosition, graphEdgePath, graphNodeHeight, graphNodesInScreenRect, graphPortPosition,
  graphSelectionRect, isGraphEditableTarget, moveGraphNodes, removeGraphNodes, zoomGraphAt,
} from './graphCanvasGeometry';
import type { GraphCanvasNodeDefinition, GraphCanvasRect } from './graphCanvasGeometry';
import './graphCanvas.css';

export type { GraphCanvasNodeDefinition, GraphCanvasPort } from './graphCanvasGeometry';
export type GraphCanvasPortSelection = { nodeId: string; portId: string; direction: 'input' | 'output' };
export type GraphCanvasProps = {
  definition: StudioGraphDefinition;
  nodeDefinitions: readonly GraphCanvasNodeDefinition[];
  selectedNodeIds: readonly string[];
  onSelectionChange: (ids: string[]) => void;
  /** Pointer gestures preview locally, then publish one record. Wheel bursts record their first change only. */
  onDefinitionChange: (definition: StudioGraphDefinition, record?: boolean) => void;
  onPortSelect?: (selection: GraphCanvasPortSelection) => void;
  protectedNodeIds?: readonly string[];
  /** Change with the active project/actor owner, even when the definition identity is reused. */
  interactionKey?: string | number;
  readonly?: boolean;
  busy?: boolean;
};

type Gesture = {
  kind: 'drag' | 'pan' | 'marquee';
  pointerId: number;
  source: StudioGraphDefinition;
  owner: GraphCanvasProps['interactionKey'];
  start: StudioGraphPosition;
  latest: StudioGraphDefinition;
  ids: string[];
  additive: boolean;
  rect?: GraphCanvasRect;
  moved: boolean;
};

const sameIds = (a: readonly string[], b: readonly string[]) => a.length === b.length && a.every((id, index) => id === b[index]);

export function GraphCanvas({ definition, nodeDefinitions, selectedNodeIds, onSelectionChange, onDefinitionChange,
  onPortSelect, protectedNodeIds = [], interactionKey, readonly = false, busy = false }: GraphCanvasProps) {
  const blocked = readonly || busy;
  const viewportRef = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const wheelUntil = useRef(0);
  const [preview, setPreview] = useState<{ source: StudioGraphDefinition; value: StudioGraphDefinition } | null>(null);
  const [marquee, setMarquee] = useState<GraphCanvasRect | null>(null);
  const [tool, setTool] = useState<'select' | 'pan'>('select');
  const [activeGesture, setActiveGesture] = useState<Gesture['kind'] | null>(null);
  const descriptionId = useId(), markerId = useId().replace(/:/g, '');
  const visible = preview?.source === definition ? preview.value : definition;
  const selected = selectedNodeIds.filter(id => definition.nodes.some(node => node.id === id));
  const removable = selected.filter(id => !protectedNodeIds.includes(id));

  const releaseCapture = useCallback((pointerId: number) => {
    const element = viewportRef.current;
    try { if (element?.hasPointerCapture?.(pointerId)) element.releasePointerCapture(pointerId); } catch { /* Capture may already be released by the browser. */ }
  }, []);

  const cancelGesture = useCallback(() => {
    const current = gesture.current;
    gesture.current = null;
    setPreview(null); setMarquee(null); setActiveGesture(null);
    if (current) releaseCapture(current.pointerId);
  }, [releaseCapture]);

  useEffect(() => {
    cancelGesture();
    return () => {
      const current = gesture.current;
      gesture.current = null;
      if (current) releaseCapture(current.pointerId);
    };
  }, [definition, interactionKey, readonly, busy, cancelGesture, releaseCapture]);

  useEffect(() => { wheelUntil.current = 0; }, [interactionKey, readonly, busy]);

  useEffect(() => {
    window.addEventListener('blur', cancelGesture);
    return () => window.removeEventListener('blur', cancelGesture);
  }, [cancelGesture]);

  // A non-passive listener prevents browser zoom while this focused canvas handles the wheel.
  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const handleWheel = (event: WheelEvent) => {
      if (blocked || gesture.current || (!event.ctrlKey && !event.metaKey) || !event.deltaY || isGraphEditableTarget(event.target)) return;
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientHeight || 480 : 1;
      const next = zoomGraphAt(definition.viewport, { x: event.clientX - rect.left, y: event.clientY - rect.top }, definition.viewport.zoom * Math.exp(-event.deltaY * unit * 0.002));
      if (next.zoom === definition.viewport.zoom) return;
      const now = Date.now(), record = now >= wheelUntil.current;
      wheelUntil.current = now + 180;
      onDefinitionChange({ ...definition, viewport: next }, record);
    };
    element.addEventListener('wheel', handleWheel, { passive: false });
    return () => element.removeEventListener('wheel', handleWheel);
  }, [blocked, definition, onDefinitionChange]);

  const selectNode = (id: string, additive: boolean) => {
    const next = additive ? selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id]
      : selected.includes(id) ? selected : [id];
    if (!sameIds(next, selectedNodeIds)) onSelectionChange(next);
    return next;
  };

  const startGesture = (event: PointerEvent, kind: Gesture['kind'], ids: string[] = selected) => {
    if (gesture.current || busy || (blocked && kind !== 'marquee')) return;
    event.preventDefault();
    const rect = viewportRef.current!.getBoundingClientRect();
    gesture.current = { kind, pointerId: event.pointerId, source: definition, owner: interactionKey,
      start: kind === 'marquee' ? { x: event.clientX - rect.left, y: event.clientY - rect.top } : { x: event.clientX, y: event.clientY },
      latest: definition, ids, additive: event.shiftKey || event.ctrlKey || event.metaKey, moved: false };
    wheelUntil.current = 0;
    setActiveGesture(kind);
    if (kind === 'marquee') setMarquee({ ...gesture.current.start, width: 0, height: 0 });
    try { viewportRef.current?.setPointerCapture?.(event.pointerId); } catch { cancelGesture(); }
  };

  const moveGesture = (event: PointerEvent<HTMLDivElement>) => {
    const current = gesture.current;
    if (!current || current.pointerId !== event.pointerId) return;
    if (current.source !== definition || current.owner !== interactionKey || busy || (blocked && current.kind !== 'marquee')) { cancelGesture(); return; }
    if (current.kind === 'marquee') {
      const rect = event.currentTarget.getBoundingClientRect();
      current.rect = graphSelectionRect(current.start, { x: event.clientX - rect.left, y: event.clientY - rect.top });
      current.moved = Boolean(current.rect.width || current.rect.height);
      setMarquee(current.rect);
      return;
    }
    const delta = { x: event.clientX - current.start.x, y: event.clientY - current.start.y };
    current.moved = Boolean(delta.x || delta.y);
    current.latest = current.kind === 'drag' ? moveGraphNodes(current.source, current.ids, delta)
      : { ...current.source, viewport: { ...current.source.viewport, x: clampGraphPosition(current.source.viewport.x + delta.x), y: clampGraphPosition(current.source.viewport.y + delta.y) } };
    setPreview({ source: current.source, value: current.latest });
  };

  const finishGesture = (event: PointerEvent<HTMLDivElement>) => {
    const current = gesture.current;
    if (!current || current.pointerId !== event.pointerId) return;
    const valid = current.source === definition && current.owner === interactionKey && !busy && (!blocked || current.kind === 'marquee');
    cancelGesture();
    if (!valid) return;
    if (current.kind === 'marquee') {
      const hits = current.moved && current.rect ? graphNodesInScreenRect(definition.nodes, current.rect, definition.viewport, nodeDefinitions) : [];
      const next = current.additive ? [...new Set([...current.ids, ...hits])] : hits;
      if (!sameIds(next, selectedNodeIds)) onSelectionChange(next);
    } else if (current.moved) onDefinitionChange(current.latest, true);
  };

  const deleteSelected = () => {
    if (blocked || !removable.length || gesture.current) return;
    onDefinitionChange(removeGraphNodes(definition, removable, protectedNodeIds), true);
    onSelectionChange(selected.filter(id => !removable.includes(id)));
  };

  const zoomBy = (factor: number) => {
    if (blocked || gesture.current) return;
    const rect = viewportRef.current!.getBoundingClientRect();
    const viewport = zoomGraphAt(definition.viewport, { x: rect.width / 2, y: rect.height / 2 }, definition.viewport.zoom * factor);
    if (viewport.zoom !== definition.viewport.zoom) onDefinitionChange({ ...definition, viewport }, true);
    wheelUntil.current = 0;
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (isGraphEditableTarget(event.target)) return;
    if (event.key === 'Escape') { event.preventDefault(); if (gesture.current) cancelGesture(); else onSelectionChange([]); return; }
    if (busy) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') { event.preventDefault(); onSelectionChange(definition.nodes.map(node => node.id)); return; }
    if (blocked || gesture.current) return;
    if ((event.key === 'Delete' || event.key === 'Backspace') && removable.length) { event.preventDefault(); deleteSelected(); return; }
    if (!selected.length || event.altKey || event.ctrlKey || event.metaKey || (event.target instanceof Element && event.target.closest('[data-graph-port]'))) return;
    const distance = event.shiftKey ? 32 : 8;
    const directions: Record<string, StudioGraphPosition> = { ArrowLeft: { x: -distance, y: 0 }, ArrowRight: { x: distance, y: 0 }, ArrowUp: { x: 0, y: -distance }, ArrowDown: { x: 0, y: distance } };
    const delta = directions[event.key];
    if (delta) { event.preventDefault(); onDefinitionChange(moveGraphNodes(definition, selected, delta), true); wheelUntil.current = 0; }
  };

  return <section className="graph-canvas" aria-label="节点图画布" aria-busy={busy || undefined} onKeyDown={handleKeyDown}>
    <header className="graph-canvas__toolbar" aria-label="节点图画布工具">
      <div className="graph-canvas__tools" role="group" aria-label="画布操作方式">
        <Button type="button" variant="ghost" aria-label="选择节点" aria-pressed={tool === 'select'} disabled={busy} onClick={() => { cancelGesture(); setTool('select'); }}><MousePointer2 size={16} /></Button>
        <Button type="button" variant="ghost" aria-label="平移画布" aria-pressed={tool === 'pan'} disabled={blocked} onClick={() => { cancelGesture(); setTool('pan'); }}><Hand size={16} /></Button>
      </div>
      <Button type="button" variant="ghost" aria-label="缩小节点图" disabled={blocked || visible.viewport.zoom <= GRAPH_MIN_ZOOM} onClick={() => zoomBy(1 / 1.2)}><ZoomOut size={16} /></Button>
      <output aria-label="节点图缩放">{Math.round(visible.viewport.zoom * 100)}%</output>
      <Button type="button" variant="ghost" aria-label="放大节点图" disabled={blocked || visible.viewport.zoom >= GRAPH_MAX_ZOOM} onClick={() => zoomBy(1.2)}><ZoomIn size={16} /></Button>
      <span className="graph-canvas__count" role="status">{selected.length ? `已选 ${selected.length} 个节点` : `${definition.nodes.length} 个节点 · ${definition.edges.length} 条连接`}</span>
      {readonly && <Badge>只读</Badge>}
      <Button type="button" variant="ghost" aria-label="删除所选图节点" disabled={blocked || !removable.length} title={selected.length && !removable.length ? '已保存的资产引用只能移动或停用' : '删除所选节点及其连接'} onClick={deleteSelected}><Trash2 size={16} /></Button>
    </header>
    <div ref={viewportRef} className={`graph-canvas__viewport${tool === 'pan' ? ' is-pan-tool' : ''}${activeGesture === 'pan' ? ' is-panning' : ''}`}
      tabIndex={0} role="group" aria-label="节点图交互区域" aria-describedby={descriptionId}
      onPointerDown={event => {
        if (busy || isGraphEditableTarget(event.target) || (event.button !== 0 && event.button !== 1)) return;
        if (event.button === 1 || event.altKey || tool === 'pan') { startGesture(event, 'pan'); return; }
        if (event.target instanceof Element && event.target.closest('[data-graph-node-id]')) return;
        event.currentTarget.focus(); startGesture(event, 'marquee');
      }}
      onPointerMove={moveGesture} onPointerUp={finishGesture}
      onPointerCancel={event => { if (gesture.current?.pointerId === event.pointerId) cancelGesture(); }}
      onLostPointerCapture={event => { if (gesture.current?.pointerId === event.pointerId) cancelGesture(); }}>
      <div className="graph-canvas__world" style={{ transform: `translate(${visible.viewport.x}px, ${visible.viewport.y}px) scale(${visible.viewport.zoom})` }}>
        <svg className="graph-canvas__edges" aria-hidden="true">
          <defs><marker id={markerId} viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" /></marker></defs>
          {visible.edges.map(edge => {
            const source = visible.nodes.find(node => node.id === edge.source_node_id), target = visible.nodes.find(node => node.id === edge.target_node_id);
            if (!source || !target) return null;
            const start = graphPortPosition(source, nodeDefinitions.find(item => item.id === source.definition_id), 'output', edge.source_port);
            const end = graphPortPosition(target, nodeDefinitions.find(item => item.id === target.definition_id), 'input', edge.target_port);
            return start && end ? <path key={edge.id} data-graph-edge-id={edge.id} d={graphEdgePath(start, end)} markerEnd={`url(#${markerId})`} /> : null;
          })}
        </svg>
        {visible.nodes.map(node => {
          const descriptor = nodeDefinitions.find(item => item.id === node.definition_id);
          const label = descriptor?.label || GRAPH_NODE_LABELS[node.definition_id] || node.definition_id;
          const style = { left: node.position.x, top: node.position.y, width: GRAPH_NODE_WIDTH, height: graphNodeHeight(descriptor), '--graph-node-header-height': `${GRAPH_NODE_HEADER_HEIGHT}px`, '--graph-port-row-height': `${GRAPH_PORT_ROW_HEIGHT}px` } as CSSProperties;
          return <article key={node.id} data-graph-node-id={node.id} className={`graph-canvas__node${selected.includes(node.id) ? ' is-selected' : ''}${!node.enabled ? ' is-disabled' : ''}`} style={style}>
            <Button type="button" variant="ghost" className="graph-canvas__node-select" aria-label={`选择节点 ${label} · ${node.id}`} aria-pressed={selected.includes(node.id)} disabled={busy}
              onPointerDown={event => {
                if (event.button !== 0 || event.altKey || tool === 'pan') return;
                event.stopPropagation();
                if (busy || gesture.current) return;
                event.currentTarget.focus();
                const ids = selectNode(node.id, event.shiftKey || event.ctrlKey || event.metaKey);
                if (!blocked && ids.includes(node.id)) startGesture(event, 'drag', ids);
              }}
              onClick={event => { if (event.detail === 0 && !busy) selectNode(node.id, event.shiftKey || event.ctrlKey || event.metaKey); }}>
              <span className="graph-canvas__node-label"><strong>{label}</strong><small>{node.id} · v{node.definition_version}</small></span>
              <Badge tone={node.enabled ? 'neutral' : 'warning'}>{node.enabled ? '启用' : '停用'}</Badge>
            </Button>
            <div className="graph-canvas__ports">
              {(['input', 'output'] as const).map(direction => {
                const ports = direction === 'input' ? descriptor?.inputs : descriptor?.outputs;
                return <div key={direction} className={`graph-canvas__port-column graph-canvas__port-column--${direction}`}>
                  {ports?.map(port => {
                    const text = <><span className="graph-canvas__port-dot" aria-hidden="true" /><span className="graph-canvas__port-copy"><span>{direction === 'input' ? '输入' : '输出'} · {port.label || port.id}{port.required ? ' *' : ''}</span><small>{port.type}</small></span></>;
                    const ariaLabel = `${label} ${node.id} ${direction === 'input' ? '输入' : '输出'}端口 ${port.label || port.id} · ${port.type}${port.required ? ' · 必需' : ''}`;
                    return onPortSelect ? <Button type="button" variant="ghost" key={port.id} data-graph-port={port.id} className="graph-canvas__port" aria-label={ariaLabel} disabled={blocked} onPointerDown={event => event.stopPropagation()} onClick={() => onPortSelect({ nodeId: node.id, portId: port.id, direction })}>{text}</Button>
                      : <span key={port.id} className="graph-canvas__port" aria-label={ariaLabel}>{text}</span>;
                  })}
                </div>;
              })}
              {!descriptor && <span className="graph-canvas__unknown">节点定义不可用</span>}
            </div>
          </article>;
        })}
      </div>
      {marquee && <div className="graph-canvas__marquee" data-testid="graph-selection-marquee" style={marquee} />}
      {!definition.nodes.length && <p className="graph-canvas__empty">从节点目录添加第一个节点，再选择输入和输出端口连接。</p>}
    </div>
    <p id={descriptionId} className="graph-canvas__help">拖动节点移动；空白处框选；Shift 多选；Alt 拖动或平移工具移动视图；Ctrl / ⌘ + 滚轮缩放。选中节点后可用方向键移动、Delete 删除，Esc 取消操作。</p>
    <ul className="sr-only" aria-label="节点图连接">{definition.edges.map(edge => <li key={edge.id}>{edge.source_node_id} 输出 {edge.source_port} 连接至 {edge.target_node_id} 输入 {edge.target_port}</li>)}</ul>
  </section>;
}
