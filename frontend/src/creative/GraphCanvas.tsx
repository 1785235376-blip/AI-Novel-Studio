import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react';
import { Hand, MousePointer2, Trash2, ZoomIn, ZoomOut } from 'lucide-react';
import { Badge, Button } from '../ui/primitives';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import type { StudioGraphDefinition, StudioGraphPosition, StudioGraphViewPreferences } from './studioGraphTypes';
import {
  GRAPH_MAX_ZOOM, GRAPH_MIN_ZOOM, GRAPH_NODE_HEADER_HEIGHT, GRAPH_NODE_WIDTH, GRAPH_PORT_ROW_HEIGHT,
  alignGraphNodes, clampGraphPosition, snapGraphNodes, graphEdgePath, graphNodeHeight, graphNodesInScreenRect,
  graphSelectionRect, graphPortPosition, graphScreenToWorld, isGraphEditableTarget, moveGraphNodes, removeGraphNodes, zoomGraphAt,
} from './graphCanvasGeometry';
import type { GraphAlignment, GraphCanvasNodeDefinition, GraphCanvasRect } from './graphCanvasGeometry';
import { collapseGraphDisplay, createGraphDisplayIndex, projectGraphDisplay, projectGraphMiniMap, GRAPH_VIEW_OVERSCAN } from './graphCanvasPresentation';
import { GraphNodeNavigator } from './GraphNodeNavigator';
import { GraphVisualGroups } from './GraphVisualGroups';
import './graphCanvas.css';
import { GraphNoteEditor, GraphNoteCards } from './GraphCanvasNotes';

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
  /** Advisory legality remains owned by the original graph editor, not the canvas. */
  connectionIssue?: (source: GraphCanvasPortSelection, target: GraphCanvasPortSelection) => string | undefined;
  connectionScope?: object;
  onConnectionStage?: (source: GraphCanvasPortSelection, target: GraphCanvasPortSelection, scope: object) => boolean;
  protectedNodeIds?: readonly string[];
  /** Pending connection endpoints owned by the existing editor controller. */
  connectionNodeIds?: readonly string[];
  /** Change with the active project/actor owner, even when the definition identity is reused. */
  interactionKey?: string | number;
  /** Original loaded record identity: refresh/adoption resets temporary preferences even for the same graph/version. */
  preferencesSource?: object;
  readonly?: boolean;
  busy?: boolean;
};

type Gesture = {
  kind: 'drag' | 'pan' | 'marquee' | 'connection';
  pointerId: number;
  source: StudioGraphDefinition;
  owner: GraphCanvasProps['interactionKey'];
  start: StudioGraphPosition;
  latest: StudioGraphDefinition;
  ids: string[];
  additive: boolean;
  anchorId: string;
  snapStep: number | null;
  rect?: GraphCanvasRect;
  moved: boolean;
  connection?: { port: GraphCanvasPortSelection; scope: object; fence: object };
};
type ConnectionPreview = { start: StudioGraphPosition; end: StudioGraphPosition; target?: GraphCanvasPortSelection; issue?: string };

const sameIds = (a: readonly string[], b: readonly string[]) => a.length === b.length && a.every((id, index) => id === b[index]);

export function GraphCanvas({ definition, nodeDefinitions, selectedNodeIds, onSelectionChange, onDefinitionChange,
  onPortSelect, connectionIssue, connectionScope, onConnectionStage, protectedNodeIds = [], connectionNodeIds = [], interactionKey, preferencesSource, readonly = false, busy = false }: GraphCanvasProps) {
  const blocked = readonly || busy;
  const [selectedNote, setSelectedNote] = useState<string | null>(null);
  useEffect(() => { setSelectedNote(null); }, [interactionKey, preferencesSource]);
  const viewportRef = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const [connectionPreview, setConnectionPreview] = useState<ConnectionPreview | null>(null);
  const [connectionMessage, setConnectionMessage] = useState('');
  const suppressPortClick = useRef(false);
  const connectionValues = [definition, interactionKey, preferencesSource, blocked, connectionScope, JSON.stringify(nodeDefinitions)];
  const connectionFence = useRef({ values: connectionValues, token: {} });
  if (connectionValues.some((value, index) => !Object.is(value, connectionFence.current.values[index]))) {
    connectionFence.current = { values: connectionValues, token: {} };
  }
  const connectionToken = connectionFence.current.token;
  const wheelUntil = useRef(0);
  const [preview, setPreview] = useState<{ source: StudioGraphDefinition; value: StudioGraphDefinition } | null>(null);
  const [marquee, setMarquee] = useState<GraphCanvasRect | null>(null);
  const measuredViewport = useRef<{ width: number; height: number } | null>(null);
  const [viewportSize, setViewportSize] = useState<{ width: number; height: number } | null>(null);
  const [focusedGroup, setFocusedGroup] = useState<string | null>(null);
  const [fold, setFold] = useState<{ owner: GraphCanvasProps['interactionKey'];
    groups: StudioGraphDefinition['presentation']; ids: string[] } | null>(null);
  const foldCurrent = !!fold && fold.owner === interactionKey && fold.groups?.groups === definition.presentation?.groups;
  const collapsedGroups = foldCurrent ? fold!.ids : [];
  useEffect(() => { setFold(null); }, [interactionKey, definition.presentation?.groups]);
  const [focusedNode, setFocusedNode] = useState<string | null>(null);
  const liveViewOwner = useRef({ definition, interactionKey, preferencesSource, blocked });
  liveViewOwner.current = { definition, interactionKey, preferencesSource, blocked };
  const canWriteView = () => !blocked && !gesture.current && liveViewOwner.current.definition === definition
    && liveViewOwner.current.interactionKey === interactionKey && liveViewOwner.current.preferencesSource === preferencesSource && !liveViewOwner.current.blocked;
  const savedView = definition.presentation?.view;
  const viewKey = JSON.stringify(savedView);
  const [sessionView, setSessionView] = useState<{ owner: GraphCanvasProps['interactionKey']; key: string | undefined; source?: object;
    value: StudioGraphViewPreferences } | null>(null);
  const view = sessionView && sessionView.owner === interactionKey && sessionView.key === viewKey && sessionView.source === preferencesSource ? sessionView.value
    : savedView || { show_grid: true, snap: false, grid_step: 24 as const, show_minimap: true };
  const { show_grid: showGrid, snap, grid_step: gridStep, show_minimap: showMiniMap } = view;
  useEffect(() => { setSessionView(null); }, [interactionKey, viewKey, preferencesSource]);
  const updateView = (patch: Partial<StudioGraphViewPreferences>) => setSessionView({ owner: interactionKey, key: viewKey, source: preferencesSource, value: { ...view, ...patch } });
  const [annotationLimit, setAnnotationLimit] = useState(false);
  useEffect(() => { setAnnotationLimit(false); }, [definition, interactionKey, blocked]);
  const [tool, setTool] = useState<'select' | 'pan'>('select');
  const [activeGesture, setActiveGesture] = useState<Gesture['kind'] | null>(null);
  const descriptionId = useId(), markerId = useId().replace(/:/g, '');
  const [alignment, setAlignment] = useState<{ source: StudioGraphDefinition; value: StudioGraphDefinition;
    owner: GraphCanvasProps['interactionKey']; ids: string; mode: GraphAlignment } | null>(null);
  const selectionKey = JSON.stringify(selectedNodeIds);
  const validAlignment = alignment && alignment.source === definition && alignment.owner === interactionKey
    && alignment.ids === selectionKey && !blocked && !activeGesture ? alignment : null;
  useEffect(() => { setAlignment(null); }, [definition, interactionKey, selectionKey, blocked]);
  const visible = validAlignment?.value || (preview?.source === definition ? preview.value : definition);
  const displayIndex = useMemo(() => createGraphDisplayIndex(visible.nodes, visible.edges, nodeDefinitions, visible.presentation?.groups), [visible.nodes, visible.edges, nodeDefinitions, visible.presentation?.groups]);
  const allNodeIds = useMemo(() => new Set(definition.nodes.map(node => node.id)), [definition.nodes]);
  const selected = selectedNodeIds.filter(id => allNodeIds.has(id));
  const retained = [...selected, ...(gesture.current?.ids || []), ...connectionNodeIds, ...(connectionPreview?.target ? [connectionPreview.target.nodeId] : []), ...(focusedNode ? [focusedNode] : [])];
  const collapse = collapseGraphDisplay(displayIndex, visible.edges, collapsedGroups, retained);
  // Expansion for an interaction anchor is permanent until explicitly collapsed again.
  const effectiveCollapseKey = JSON.stringify([...collapse.collapsedIds]);
  useEffect(() => {
    setFold(previous => previous ? { ...previous, ids: previous.ids.filter(id => collapse.collapsedIds.has(id)) } : null);
  }, [effectiveCollapseKey]);
  const display = projectGraphDisplay(collapse.index, visible.viewport, viewportSize, retained, GRAPH_VIEW_OVERSCAN, focusedGroup);
  function toggleGroup(id: string) {
    if (busy || gesture.current) return;
    const frame = displayIndex.frames.find(item => item.id === id);
    if (!frame || (!collapse.collapsedIds.has(id) && frame.nodeIds.some(member => retained.includes(member)))) return;
    setFold({ owner: interactionKey, groups: definition.presentation, ids: collapse.collapsedIds.has(id)
      ? collapsedGroups.filter(item => item !== id) : [...collapsedGroups, id] });
  }
  const renderedNodes = visible.nodes.filter(node => display.nodeIds.has(node.id));
  const selectedSet = new Set(selected);
  const edgeDescriptions = useMemo(() => definition.edges.map(edge => <li key={edge.id}>{edge.source_node_id} 输出 {edge.source_port} 连接至 {edge.target_node_id} 输入 {edge.target_port}</li>), [definition.edges]);
  const miniMap = useMemo(() => projectGraphMiniMap(displayIndex, visible.viewport, viewportSize), [displayIndex, visible.viewport, viewportSize]);
  const miniMapPaths = ['', ''];
  for (const card of miniMap.cards) {
    const { x, y, width, height } = card.bounds;
    miniMapPaths[selectedSet.has(card.id) ? 1 : 0] += `M${x} ${y}h${Math.max(width, 1)}v${Math.max(height, 1)}h${-Math.max(width, 1)}Z`;
  }
  const removable = selected.filter(id => !protectedNodeIds.includes(id));

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const measure = () => {
      const { width, height } = element.getBoundingClientRect();
      const previousSize = measuredViewport.current;
      if (previousSize && (previousSize.width !== width || previousSize.height !== height) && gesture.current?.kind === 'connection') cancelGesture();
      measuredViewport.current = { width, height };
      setViewportSize(previous => previous?.width === width && previous.height === height ? previous : { width, height });
    };
    measure();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    observer?.observe(element);
    window.addEventListener('resize', measure);
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure); };
  }, []);
  useEffect(() => { setFocusedNode(null); setFocusedGroup(null); }, [interactionKey]);

  const releaseCapture = useCallback((pointerId: number) => {
    const element = viewportRef.current;
    try { if (element?.hasPointerCapture?.(pointerId)) element.releasePointerCapture(pointerId); } catch { /* Capture may already be released by the browser. */ }
  }, []);

  const cancelGesture = useCallback(() => {
    const current = gesture.current;
    gesture.current = null;
    if (current?.kind === 'connection') suppressPortClick.current = true;
    setConnectionPreview(null);
    setPreview(null); setMarquee(null); setActiveGesture(null);
    if (current) releaseCapture(current.pointerId);
  }, [releaseCapture]);

  useEffect(() => {
    cancelGesture();
    const element = viewportRef.current;
    return () => {
      const current = gesture.current;
      gesture.current = null;
      // The ref may already be detached during passive unmount cleanup.
      try { if (current && element?.hasPointerCapture?.(current.pointerId)) element.releasePointerCapture(current.pointerId); } catch { /* Already released. */ }
    };
  }, [definition, interactionKey, readonly, busy, cancelGesture, releaseCapture]);

  useLayoutEffect(() => {
    if (gesture.current?.kind === 'connection') cancelGesture();
    setConnectionMessage('');
  }, [connectionToken, cancelGesture]);
  useEffect(() => {
    const cancelConnection = () => { if (gesture.current?.kind === 'connection') cancelGesture(); };
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape' && gesture.current?.kind === 'connection') {
        event.preventDefault(); event.stopPropagation(); cancelGesture();
      }
    };
    const resetClick = () => { suppressPortClick.current = false; };
    window.addEventListener('keydown', escape, true);
    window.addEventListener('scroll', cancelConnection, true);
    window.addEventListener('resize', cancelConnection);
    window.addEventListener('pointerdown', resetClick, true);
    return () => {
      window.removeEventListener('keydown', escape, true);
      window.removeEventListener('scroll', cancelConnection, true);
      window.removeEventListener('resize', cancelConnection);
      window.removeEventListener('pointerdown', resetClick, true);
    };
  }, [cancelGesture]);
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

  const startGesture = (event: PointerEvent, kind: Gesture['kind'], ids: string[] = selected, anchorId = ids[0]) => {
    if (gesture.current || busy || (blocked && kind !== 'marquee')) return;
    event.preventDefault();
    setAlignment(null);
    const rect = viewportRef.current!.getBoundingClientRect();
    gesture.current = { kind, pointerId: event.pointerId, source: definition, owner: interactionKey,
      start: kind === 'marquee' ? { x: event.clientX - rect.left, y: event.clientY - rect.top } : { x: event.clientX, y: event.clientY },
      latest: definition, ids, anchorId, snapStep: snap ? gridStep : null, additive: event.shiftKey || event.ctrlKey || event.metaKey, moved: false };
    wheelUntil.current = 0;
    setActiveGesture(kind);
    if (kind === 'marquee') setMarquee({ ...gesture.current.start, width: 0, height: 0 });
    try { viewportRef.current?.setPointerCapture?.(event.pointerId); } catch { cancelGesture(); }
    return gesture.current;
  };

  const orderedConnection = (first: GraphCanvasPortSelection, second: GraphCanvasPortSelection) =>
    first.direction === 'output' ? { source: first, target: second } : { source: second, target: first };
  const explainConnection = (first: GraphCanvasPortSelection, second: GraphCanvasPortSelection) => {
    if (first.direction === second.direction) return '请选择真实的输出端口和输入端口。';
    const pair = orderedConnection(first, second);
    return connectionIssue?.(pair.source, pair.target);
  };
  const hitPort = (x: number, y: number): GraphCanvasPortSelection | undefined => {
    const hit = document.elementFromPoint?.(x, y)?.closest<HTMLButtonElement>('button[data-graph-port]');
    if (!hit || hit.disabled || !viewportRef.current?.contains(hit)) return;
    const nodeId = hit.closest('[data-graph-node-id]')?.getAttribute('data-graph-node-id');
    const portId = hit.getAttribute('data-graph-port'), direction = hit.getAttribute('data-graph-direction');
    if (!nodeId || !portId || (direction !== 'input' && direction !== 'output')) return;
    const node = definition.nodes.find(value => value.id === nodeId);
    const descriptor = node && displayIndex.descriptors.get(node.definition_id);
    if (!(direction === 'input' ? descriptor?.inputs : descriptor?.outputs)?.some(port => port.id === portId)) return;
    return { nodeId, portId, direction };
  };
  const connectionAt = (current: Gesture, x: number, y: number): ConnectionPreview | null => {
    const connection = current.connection;
    if (!connection || connection.fence !== connectionFence.current.token || blocked) return null;
    const node = definition.nodes.find(value => value.id === connection.port.nodeId);
    const anchor = node && graphPortPosition(node, displayIndex.descriptors.get(node.definition_id), connection.port.direction, connection.port.portId);
    if (!anchor) return null;
    const rect = viewportRef.current!.getBoundingClientRect();
    const target = hitPort(x, y);
    const targetNode = target && definition.nodes.find(value => value.id === target.nodeId);
    const end = target && targetNode ? graphPortPosition(targetNode, displayIndex.descriptors.get(targetNode.definition_id), target.direction, target.portId) : null;
    const point = end || graphScreenToWorld({ x: x - rect.left, y: y - rect.top }, definition.viewport);
    return { start: connection.port.direction === 'output' ? anchor : point,
      end: connection.port.direction === 'output' ? point : anchor, target,
      issue: target ? explainConnection(connection.port, target) : undefined };
  };
  const startConnection = (event: PointerEvent, port: GraphCanvasPortSelection) => {
    event.stopPropagation();
    if (event.button !== 0 || event.altKey || tool === 'pan' || blocked || gesture.current
      || !connectionScope || !onConnectionStage || !connectionIssue) return;
    event.currentTarget instanceof HTMLElement && event.currentTarget.focus();
    const started = startGesture(event, 'connection', [port.nodeId], port.nodeId);
    if (!started) return;
    started.connection = { port, scope: connectionScope, fence: connectionToken };
    setConnectionMessage('');
    setConnectionPreview(connectionAt(started, event.clientX, event.clientY));
  };

  const moveGesture = (event: PointerEvent<HTMLDivElement>) => {
    const current = gesture.current;
    if (!current || current.pointerId !== event.pointerId) return;
    if (current.source !== definition || current.owner !== interactionKey || busy || (blocked && current.kind !== 'marquee')) { cancelGesture(); return; }
    if (current.kind === 'connection') {
      current.moved ||= Math.hypot(event.clientX - current.start.x, event.clientY - current.start.y) >= 4;
      const next = connectionAt(current, event.clientX, event.clientY);
      if (!next) { cancelGesture(); return; }
      setConnectionPreview(next); return;
    }
    if (current.kind === 'marquee') {
      const rect = event.currentTarget.getBoundingClientRect();
      current.rect = graphSelectionRect(current.start, { x: event.clientX - rect.left, y: event.clientY - rect.top });
      current.moved = Boolean(current.rect.width || current.rect.height);
      setMarquee(current.rect);
      return;
    }
    const delta = { x: event.clientX - current.start.x, y: event.clientY - current.start.y };
    current.moved = Boolean(delta.x || delta.y);
    current.latest = current.kind === 'drag' ? (current.snapStep ? snapGraphNodes(current.source, current.ids, current.anchorId, delta, current.snapStep) : moveGraphNodes(current.source, current.ids, delta))
      : { ...current.source, viewport: { ...current.source.viewport, x: clampGraphPosition(current.source.viewport.x + delta.x), y: clampGraphPosition(current.source.viewport.y + delta.y) } };
    setPreview({ source: current.source, value: current.latest });
  };

  const finishGesture = (event: PointerEvent<HTMLDivElement>) => {
    const current = gesture.current;
    if (!current || current.pointerId !== event.pointerId) return;
    if (current.kind === 'connection') {
      const next = connectionAt(current, event.clientX, event.clientY);
      current.moved ||= Math.hypot(event.clientX - current.start.x, event.clientY - current.start.y) >= 4;
      cancelGesture();
      if (!next || !current.connection) return;
      // Capture retargets the browser click to the viewport. Select here exactly
      // once, then suppress its physical click while preserving keyboard clicks.
      if (!current.moved) { onPortSelect?.(current.connection.port); return; }
      if (!next.target) { setConnectionMessage('连接已取消；请拖到真实的输入或输出端口。'); return; }
      if (next.issue) { setConnectionMessage(next.issue); return; }
      const pair = orderedConnection(current.connection.port, next.target);
      if (onConnectionStage?.(pair.source, pair.target, current.connection.scope)) {
        setConnectionMessage('已选择连接端口；请点击“连接所选端口”确认。');
      }
      return;
    }
    const valid = current.source === definition && current.owner === interactionKey && !busy && (!blocked || current.kind === 'marquee');
    cancelGesture();
    if (!valid) return;
    if (current.kind === 'marquee') {
      const hits = current.moved && current.rect ? graphNodesInScreenRect(definition.nodes, current.rect, definition.viewport, nodeDefinitions) : [];
      const next = current.additive ? [...new Set([...current.ids, ...hits])] : hits;
      if (!sameIds(next, selectedNodeIds)) onSelectionChange(next);
    } else if (current.moved && current.latest !== current.source) onDefinitionChange(current.latest, true);
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

  const navigateMiniMap = (point: StudioGraphPosition) => {
    if (blocked || gesture.current || !miniMap.camera || !viewportSize || !miniMap.cards.length) return;
    const viewport = { ...definition.viewport,
      x: clampGraphPosition(viewportSize.width / 2 - point.x * definition.viewport.zoom),
      y: clampGraphPosition(viewportSize.height / 2 - point.y * definition.viewport.zoom) };
    if (viewport.x !== definition.viewport.x || viewport.y !== definition.viewport.y) onDefinitionChange({ ...definition, viewport }, true);
    wheelUntil.current = 0;
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.nativeEvent.isComposing || event.keyCode === 229 || isGraphEditableTarget(event.target)) return;
    if (event.key === 'Escape') { event.preventDefault(); if (validAlignment) { setAlignment(null); return; } if (gesture.current) cancelGesture(); else onSelectionChange([]); return; }
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
      <Button type="button" variant="ghost" aria-label="显示小地图" aria-pressed={showMiniMap} onKeyDown={event => event.stopPropagation()} onClick={() => updateView({ show_minimap: !showMiniMap })}>小地图</Button>
      {readonly && <Badge>只读</Badge>}
      <Button type="button" variant="ghost" aria-label="删除所选图节点" disabled={blocked || !removable.length} title={selected.length && !removable.length ? '已保存的资产引用只能移动或停用' : '删除所选节点及其连接'} onClick={deleteSelected}><Trash2 size={16} /></Button>
    </header>
    <GraphNodeNavigator nodes={definition.nodes} definitions={nodeDefinitions} owner={interactionKey}
      busy={busy || !!activeGesture} readonly={readonly} onNavigate={id => {
        if (busy || gesture.current) return;
        const node = definition.nodes.find(item => item.id === id);
        if (!node) return;
        setAlignment(null);
        onSelectionChange([node.id]);
        if (!blocked && viewportSize) onDefinitionChange({ ...definition, viewport: { ...definition.viewport,
          x: clampGraphPosition(viewportSize.width / 2 - (node.position.x + GRAPH_NODE_WIDTH / 2) * definition.viewport.zoom),
          y: clampGraphPosition(viewportSize.height / 2 - (node.position.y + graphNodeHeight(displayIndex.descriptors.get(node.definition_id)) / 2) * definition.viewport.zoom) } }, true);
      }} />
    <GraphNoteEditor definition={definition} size={viewportSize} displayViewport={visible.viewport} blocked={blocked || !!activeGesture} owner={interactionKey}
      selected={selectedNote} onSelect={setSelectedNote} onChange={onDefinitionChange} />
    <GraphVisualGroups definition={definition} selected={selected} blocked={blocked || !!activeGesture} interactionKey={interactionKey}
      onChange={onDefinitionChange} onSelect={onSelectionChange} />
    <div className="graph-canvas__annotation" onKeyDown={event => event.stopPropagation()}>
      <label htmlFor={`${descriptionId}-comment`}>画布说明</label>
      <textarea id={`${descriptionId}-comment`} rows={2} maxLength={4000} value={definition.presentation?.comment || ''}
        disabled={blocked || !!activeGesture} aria-describedby={`${descriptionId}-comment-help`}
        onChange={event => {
          if (blocked || gesture.current) return;
          const comment = event.target.value;
          if (Array.from(comment).length > 2000) { setAnnotationLimit(true); return; }
          setAnnotationLimit(false);
          onDefinitionChange({ ...definition, presentation: { ...definition.presentation, comment } }, true);
        }} />
      <Button type="button" variant="ghost" disabled={blocked || !!activeGesture || definition.presentation?.comment === undefined}
        onClick={() => {
          if (blocked || gesture.current) return;
          const next: StudioGraphDefinition = { ...definition, presentation: { ...definition.presentation } }; delete next.presentation!.comment;
          if (!Object.keys(next.presentation!).length) delete next.presentation;
          onDefinitionChange(next, true);
        }}>移除画布说明</Button>
      <p id={`${descriptionId}-comment-help`} className="graph-canvas__help">最多 2000 个 Unicode 字符。仅作整张图的创作备注；使用“保存创作图”保存，可撤销。不会作为模型输入或运行节点。</p>
      {annotationLimit && <p role="alert" className="graph-canvas__help">说明超过 2000 个字符，本次输入未应用；原有说明已保留。</p>}
    </div>
    {!!displayIndex.frames.length && <section className="graph-canvas__groups" aria-label="分组折叠视图" onKeyDown={event => event.stopPropagation()}>
      <div className="graph-canvas__toolbar">{displayIndex.frames.filter(frame => !frame.parentId || !collapse.collapsedIds.has(frame.parentId)).map(frame => {
        const collapsed = collapse.collapsedIds.has(frame.id);
        const retainedMember = frame.nodeIds.some(id => retained.includes(id));
        return <Button key={frame.id} type="button" variant="ghost" aria-expanded={!collapsed}
          disabled={busy || !!activeGesture || (!collapsed && retainedMember)}
          title={retainedMember ? '请先取消成员选择或结束端口连接；正在使用的成员保持展开。' : undefined}
          onClick={() => toggleGroup(frame.id)}>{collapsed ? '展开' : '折叠'}分组 {frame.label}</Button>;
      })}</div>
      <p className="graph-canvas__help">折叠仅本次视图，不保存；切换图或重开恢复展开。已选、聚焦、拖动或正在连接的成员保持展开；请先取消选择、结束连接再折叠。折叠时隐藏成员及其连线，展开后查看或编辑真实端口。框选或目录选择成员会展开该组；小地图仍显示全部原节点。父组折叠时一并隐藏子组；先展开父组再操作子组。</p>
      {collapse.summaries.map(group => <details key={group.id} className="graph-canvas__help">
        <summary>{group.label}：{group.nodeIds.length} 个成员 · {group.externalEdges.length} 条对外连接 · {group.internalCount} 条内部连接（线条已隐藏）</summary>
        <ul>{group.externalEdges.map(edge => <li key={edge.id}>{edge.source_node_id} 输出 {edge.source_port} → {edge.target_node_id} 输入 {edge.target_port}</li>)}</ul>
      </details>)}
    </section>}
    <div className="graph-canvas__toolbar" role="group" aria-label="网格与吸附设置" onKeyDown={event => event.stopPropagation()}>
      <Button type="button" variant="ghost" aria-pressed={showGrid} disabled={!!activeGesture} onClick={() => updateView({ show_grid: !showGrid })}>显示网格</Button>
      <Button type="button" variant="ghost" aria-pressed={snap} disabled={blocked || !!activeGesture} onClick={() => updateView({ snap: !snap })}>拖拽吸附</Button>
      <label className="graph-canvas__navigator">网格间距<select aria-label="网格间距" value={gridStep} disabled={!!activeGesture}
        onChange={event => { const step = Number(event.target.value); if ([8, 16, 24, 32].includes(step)) updateView({ grid_step: step as 8 | 16 | 24 | 32 }); }}>
        {[8, 16, 24, 32].map(step => <option key={step} value={step}>{step} 世界单位</option>)}
      </select></label>
      <Button type="button" variant="ghost" disabled={blocked || !!activeGesture || JSON.stringify(view) === JSON.stringify(savedView)}
        onClick={() => {
          if (!canWriteView()) return;
          onDefinitionChange({ ...definition, presentation: { ...definition.presentation, view: { ...view } } }, true);
        }}>将视图偏好写入图草稿</Button>
      <Button type="button" variant="ghost" disabled={blocked || !!activeGesture || !savedView}
        onClick={() => {
          if (!canWriteView() || !savedView) return;
          const next = { ...definition, presentation: { ...definition.presentation } };
          delete next.presentation.view;
          if (!Object.keys(next.presentation).length) delete (next as StudioGraphDefinition).presentation;
          onDefinitionChange(next, true);
        }}>移除已存视图偏好</Button>
      <span className="graph-canvas__help">设置仅本次视图；写入草稿后需保存图才会保留，可撤销。折叠不保存；吸附抓取节点，多选保持相对位置，边界优先。方向键仍按屏幕 8 / Shift 32 像素微调。</span>
    </div>
    <div className="graph-canvas__toolbar" role="group" aria-label="所选节点对齐" onKeyDown={event => {
      event.stopPropagation();
      if (event.key === 'Escape') { event.preventDefault(); setAlignment(null); }
    }}>
      {([['left', '左对齐'], ['center', '水平中心对齐'], ['top', '顶对齐'], ['distribute', '水平等距分布']] as const).map(([mode, label]) =>
        <Button key={mode} type="button" variant="ghost" disabled={blocked || !!activeGesture || selected.length < (mode === 'distribute' ? 3 : 2)}
          onClick={() => {
            if (blocked || gesture.current) return;
            const value = alignGraphNodes(definition, selected, mode);
            setAlignment({ source: definition, value, owner: interactionKey, ids: selectionKey, mode });
          }}>预览{label}</Button>)}
      {validAlignment && <>
        <span role="status">对齐预览：移动 {validAlignment.value.nodes.filter((node, index) => node !== definition.nodes[index]).length} 个节点；仅修改位置，应用后仍需保存。</span>
        <Button type="button" disabled={validAlignment.value === definition} onClick={() => {
          if (!validAlignment || blocked || gesture.current || validAlignment.value === definition) return;
          setAlignment(null); wheelUntil.current = 0;
          onDefinitionChange(validAlignment.value, true);
        }}>应用所选节点对齐</Button>
        <Button type="button" variant="ghost" onClick={() => setAlignment(null)}>取消对齐预览</Button>
      </>}
    </div>
    <div ref={viewportRef} className={`graph-canvas__viewport${tool === 'pan' ? ' is-pan-tool' : ''}${activeGesture === 'pan' ? ' is-panning' : ''}`}
      style={{ backgroundImage: showGrid ? undefined : 'none', backgroundSize: `${gridStep * visible.viewport.zoom}px ${gridStep * visible.viewport.zoom}px`,
        backgroundPosition: `${visible.viewport.x - gridStep * visible.viewport.zoom / 2}px ${visible.viewport.y - gridStep * visible.viewport.zoom / 2}px` }}
      tabIndex={0} role="group" aria-label="节点图交互区域" aria-describedby={descriptionId}
      onFocusCapture={event => {
        setFocusedNode((event.target as Element).closest('[data-graph-node-id]')?.getAttribute('data-graph-node-id') || null);
        setFocusedGroup((event.target as Element).closest('[data-graph-group-id]')?.getAttribute('data-graph-group-id') || null);
      }}
      onBlurCapture={event => {
        const next = event.relatedTarget;
        if (!(next instanceof Element) || !event.currentTarget.contains(next)) { setFocusedNode(null); setFocusedGroup(null); }
      }}
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
        {display.frames.map(frame => {
          const fullySelected = frame.nodeIds.every(id => selectedSet.has(id));
          const summary = collapse.summaries.find(group => group.id === frame.id);
          if (summary) return <div key={frame.id} data-graph-group-id={frame.id} data-graph-collapsed="true"
            className="graph-canvas__group-frame graph-canvas__group-collapsed"
            style={{ left: frame.bounds.x, top: frame.bounds.y, width: frame.bounds.width, height: frame.bounds.height }}>
            <Button type="button" variant="ghost" className="graph-canvas__group-label" title={frame.label}
              aria-label={`展开画布分组 ${frame.label}`} aria-expanded={false} disabled={busy || !!activeGesture}
              onKeyDown={event => event.stopPropagation()} onPointerDown={event => event.stopPropagation()}
              onClick={() => toggleGroup(frame.id)}>{frame.label} · {frame.nodeIds.length} 个节点 · 展开</Button>
            <p className="graph-canvas__help">{summary.externalEdges.length} 条对外连接 · {summary.internalCount} 条内部连接<br />连线已隐藏；展开后查看或连接端口。</p>
          </div>;
          return <div key={frame.id} data-graph-group-id={frame.id} className={`graph-canvas__group-frame${fullySelected ? ' is-selected' : ''}`}
            style={{ left: frame.bounds.x, top: frame.bounds.y, width: frame.bounds.width, height: frame.bounds.height }}>
            <Button type="button" variant="ghost" className="graph-canvas__group-label" title={frame.label}
              aria-label={`选择视觉分组 ${frame.label} 的 ${frame.nodeIds.length} 个成员`} aria-pressed={fullySelected}
              disabled={busy || !!activeGesture} onKeyDown={event => event.stopPropagation()}
              onPointerDown={event => {
                if (event.button !== 0 || event.altKey || tool === 'pan') return;
                event.stopPropagation();
              }} onClick={event => {
                if (busy || gesture.current || event.altKey || (tool === 'pan' && event.detail !== 0)) return;
                setAlignment(null);
                onSelectionChange([...frame.nodeIds]);
              }}>{frame.label} · {frame.nodeIds.length} 个节点 · 选择成员</Button>
          </div>;
        })}
        <svg className="graph-canvas__edges" aria-hidden="true">
          <defs><marker id={markerId} viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" /></marker></defs>
          {connectionPreview && <path data-testid="graph-connection-preview" className={`graph-canvas__connection-preview${connectionPreview.issue ? ' is-invalid' : ''}`}
            d={graphEdgePath(connectionPreview.start, connectionPreview.end)} />}
          {display.edges.map(edge => <path key={edge.id} data-graph-edge-id={edge.id} d={graphEdgePath(edge.start, edge.end)} markerEnd={`url(#${markerId})`} />)}
        </svg>
        <GraphNoteCards definition={definition} blocked={blocked || !!activeGesture} owner={interactionKey}
          selected={selectedNote} onSelect={setSelectedNote} onChange={onDefinitionChange} size={viewportSize} panMode={tool === 'pan'} displayViewport={visible.viewport} />
        {renderedNodes.map(node => {
          const descriptor = displayIndex.descriptors.get(node.definition_id);
          const label = descriptor?.label || GRAPH_NODE_LABELS[node.definition_id] || node.definition_id;
          const style = { left: node.position.x, top: node.position.y, width: GRAPH_NODE_WIDTH, height: graphNodeHeight(descriptor), '--graph-node-header-height': `${GRAPH_NODE_HEADER_HEIGHT}px`, '--graph-port-row-height': `${GRAPH_PORT_ROW_HEIGHT}px` } as CSSProperties;
          return <article key={node.id} data-graph-node-id={node.id} className={`graph-canvas__node${selectedSet.has(node.id) ? ' is-selected' : ''}${!node.enabled ? ' is-disabled' : ''}`} style={style}>
            <Button type="button" variant="ghost" className="graph-canvas__node-select" aria-label={`选择节点 ${label} · ${node.id}`} aria-pressed={selectedSet.has(node.id)} disabled={busy}
              onPointerDown={event => {
                if (event.button !== 0 || event.altKey || tool === 'pan') return;
                event.stopPropagation();
                if (busy || gesture.current) return;
                event.currentTarget.focus();
                const ids = selectNode(node.id, event.shiftKey || event.ctrlKey || event.metaKey);
                if (!blocked && ids.includes(node.id)) startGesture(event, 'drag', ids, node.id);
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
                    const endpoint = { nodeId: node.id, portId: port.id, direction };
                    const dragging = gesture.current?.connection;
                    const compatible = !!dragging && dragging.fence === connectionToken && !explainConnection(dragging.port, endpoint);
                    const hovered = connectionPreview?.target?.nodeId === node.id && connectionPreview.target.portId === port.id && connectionPreview.target.direction === direction;
                    return onPortSelect ? <Button type="button" variant="ghost" key={port.id} data-graph-port={port.id} data-graph-direction={direction}
                      data-connection-compatible={dragging ? compatible : undefined}
                      className={`graph-canvas__port${compatible ? ' is-connection-compatible' : ''}${hovered && connectionPreview?.issue ? ' is-connection-invalid' : ''}`}
                      aria-label={ariaLabel} disabled={blocked} onPointerDown={event => startConnection(event, endpoint)}
                      onClick={event => { if (event.detail !== 0 && suppressPortClick.current) { suppressPortClick.current = false; return; } onPortSelect(endpoint); }}>{text}</Button>
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
      {!definition.nodes.length && !definition.presentation?.notes?.length && <p className="graph-canvas__empty">从节点目录添加第一个节点，再选择输入和输出端口连接。</p>}
    </div>
    {(connectionPreview || connectionMessage) && <p className="graph-canvas__help" role="status" aria-live="polite">
      {connectionPreview ? connectionPreview.issue || '拖到兼容端口以选择连接；松开后仍需点击“连接所选端口”。' : connectionMessage}
    </p>}
    {showMiniMap && <div className="graph-canvas__minimap-row">
      <Button type="button" variant="ghost" className="graph-canvas__minimap" aria-label="小地图导航" aria-describedby={`${descriptionId}-minimap`}
        disabled={blocked || !miniMap.camera || !miniMap.cards.length} onKeyDown={event => {
          event.stopPropagation();
          if (event.altKey || event.ctrlKey || event.metaKey || event.nativeEvent.isComposing || !viewportSize) return;
          const steps: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
          const step = steps[event.key];
          if (!step) return;
          event.preventDefault();
          const zoom = definition.viewport.zoom, fraction = event.shiftKey ? 1 : 0.25;
          navigateMiniMap({ x: (viewportSize.width / 2 - definition.viewport.x + step[0] * viewportSize.width * fraction) / zoom,
            y: (viewportSize.height / 2 - definition.viewport.y + step[1] * viewportSize.height * fraction) / zoom });
        }} onClick={event => {
          const rect = event.currentTarget.getBoundingClientRect();
          if (event.detail === 0) navigateMiniMap(miniMap.center);
          else if (rect.width > 0 && rect.height > 0) navigateMiniMap(miniMap.worldAt((event.clientX - rect.left) / rect.width * 200, (event.clientY - rect.top) / rect.height * 120));
        }}>
        <svg viewBox="0 0 200 120" preserveAspectRatio="none" aria-hidden="true">
          <path className="graph-canvas__minimap-nodes" d={miniMapPaths[0]} />
          <path className="graph-canvas__minimap-selected" d={miniMapPaths[1]} />
          {miniMap.camera && <rect className="graph-canvas__minimap-camera" {...miniMap.camera} />}
        </svg>
      </Button>
      <p id={`${descriptionId}-minimap`} className="graph-canvas__help">小地图：全图节点与当前视口。点击定位；方向键平移，Shift 加速；Enter / 空格居中。蓝色节点表示已选。{blocked ? '当前不可修改视图。' : ''}</p>
    </div>}
    <p id={descriptionId} className="graph-canvas__help">拖动节点移动；空白处框选；Shift 多选；Alt 拖动或平移工具移动视图；Ctrl / ⌘ + 滚轮缩放。选中节点后可用方向键移动、Delete 删除，Esc 取消操作。</p>
    <ul className="sr-only" aria-label="节点图连接">{edgeDescriptions}</ul>
  </section>;
}
