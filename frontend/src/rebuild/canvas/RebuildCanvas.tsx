/* [HERMIA-FE-20261022 U1] 原型同款黑色无限画布（图片画布 / 视频画布共用）。
   - 点阵网格、节点卡（左色条 + 标题 + 类型 + 本地标）、左右端口、贝塞尔连线、滚轮缩放、空白拖拽平移、拖动节点、从输出端口拖线连接。
   - 右键空白处 → 在点击位置弹「添加节点」菜单（类型取自现存 StudioGraphDefinitionId 目录，按画布过滤）；右键节点 → 删除。
   - 持久化：前端还没有可直接写入的画布图接口接到这里，所以只存本机浏览器 localStorage，并在画布上写明「仅本机草稿」。不发任何写请求。 */
import {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import type {PointerEvent as RPE, MouseEvent as RME, WheelEvent as RWE, ReactNode} from 'react';
import type {StudioGraphDefinitionId} from '../../creative/studioGraphTypes';
import {Button, Panel, StatusMessage} from '../../ui/primitives';
import './rebuildCanvas.css';
import {useLocale, useT, useTz} from '../../i18n'; // [HERMIA-FE-20261031 VERA-EN]
import {displayNodeTitle} from '../../i18n/defaultNodeTitle';

export type CanvasKind = 'image' | 'video';
export type NodeType = {id: StudioGraphDefinitionId; label: string; color: string; icon: string; ins: boolean; outs: boolean};
export type CvNode = {id: string; t: StudioGraphDefinitionId; x: number; y: number; title: string; prompt?: string};
export type CvEdge = {id: string; a: string; b: string};
export type CvGraph = {nodes: CvNode[]; edges: CvEdge[]};

const T = (id: StudioGraphDefinitionId, label: string, color: string, icon: string, ins = true, outs = true): NodeType => ({id, label, color, icon, ins, outs});
export const NODE_TYPES: Record<CanvasKind, NodeType[]> = {
  image: [
    T('text_input', '文本输入', '#8a93a5', '✎', false), T('image_reference', '参考图', '#5aa0d8', '▣', false), T('asset_reference', '资产引用', '#6b8fb0', '⛁', false),
    T('image_prompt', '图片提示词', '#c4a14d', '❝'), T('image_style', '风格', '#b27ad1', '✦'), T('image_generate', '生成图片', '#4db8c4', '◈'),
    T('image_upscale', '放大', '#4db8a0', '⤢'), T('human_review', '人工审核', '#d07a5a', '✓', true, false),
  ],
  video: [
    T('text_input', '文本输入', '#8a93a5', '✎', false), T('storyboard_plan', '分镜规划', '#c4a14d', '▦'), T('storyboard_shot', '镜头', '#5aa0d8', '▭'),
    T('storyboard_prompt', '镜头提示词', '#b8a060', '❝'), T('director_note', '导演备注', '#b27ad1', '✦'), T('image_reference', '参考图', '#6b8fb0', '▣', false),
    T('video_generate', '生成视频', '#4db8c4', '▶'), T('media_review', '素材审核', '#d07a5a', '✓', true, false), T('timeline_export', '送剪辑时间线', '#4db8a0', '⇥', true, false),
  ],
};
const NW = 180, NH = 60;
const REVEAL_W = 186; // [HERMIA-FE-20261024 M3-s1fix] rendered box incl. border/ports (Chrome)
let seq = 0; const uid = (p: string) => `${p}${Date.now().toString(36)}${(seq++).toString(36)}`;
export const canvasStorageKey = (k: CanvasKind, scope: string) => `poemseed.rebuild.canvas.${k}.${scope}`;

// [HERMIA-FE-20261026 DUAL] in-memory store for 「仅本次会话」 canvases (no identity → never written to localStorage).
const SESSION_GRAPHS = new Map<string, CvGraph>();
export const sessionCanvasStore = {get: (k: string) => SESSION_GRAPHS.get(k), set: (k: string, g: CvGraph) => { SESSION_GRAPHS.set(k, g); }, clear: () => SESSION_GRAPHS.clear()};
export function readCanvasGraph(key: string, persist: 'local' | 'session' = 'local'): CvGraph | null {
  if (persist === 'session') return SESSION_GRAPHS.get(key) ?? null;
  try { const raw = localStorage.getItem(key); if (raw) { const g = JSON.parse(raw); if (Array.isArray(g?.nodes) && Array.isArray(g?.edges)) return g; } } catch { /* corrupt: leave untouched */ }
  return null;
}
export function writeCanvasGraph(key: string, g: CvGraph, persist: 'local' | 'session' = 'local') {
  if (persist === 'session') { SESSION_GRAPHS.set(key, g); return; }
  try { localStorage.setItem(key, JSON.stringify(g)); } catch { /* ignore */ }
}
function load(key: string, seed: CvGraph, persist: 'local' | 'session' = 'local'): CvGraph {
  if (persist === 'session') return SESSION_GRAPHS.get(key) ?? seed;
  try { const raw = localStorage.getItem(key); if (raw) { const g = JSON.parse(raw); if (Array.isArray(g?.nodes) && Array.isArray(g?.edges)) return g; } } catch { /* ignore */ }
  return seed;
}

export type CvViewport = {x: number; y: number; k: number};
// [HERMIA-FE-20261024 M3-s1] optional initialSelected / initialViewport / onViewport so a host that remounts the canvas
// (after an external local-draft write) keeps the user's selection and pan/zoom. Defaults unchanged.
type RebuildCanvasProps = {kind: CanvasKind; scope: string; seed?: CvGraph; label?: string; onSelect?: (n: CvNode | null) => void;
  initialSelected?: string | null; initialViewport?: CvViewport; onViewport?: (vp: CvViewport) => void; revealLast?: boolean; onRevealed?: () => void;
  storageKey?: string; persist?: 'local' | 'session'; types?: NodeType[]; ariaLabel?: string; menuTitle?: string; badge?: string; badgeTitle?: string; emptyHint?: string;
  onImageTaskIntent?: (node: CvNode, isSourceCurrent?: () => boolean) => void; renderImageTaskBinding?: (node: CvNode, isSourceCurrent?: () => boolean, sourceRevision?: number, formalSourceCurrent?: () => boolean) => ReactNode};

/** Remount when owner storage key changes so selection/prompt/source guards never leak across projects. */
export function RebuildCanvas(props: RebuildCanvasProps) {
  return <RebuildCanvasSession key={props.storageKey ?? canvasStorageKey(props.kind, props.scope)} {...props} />;
}

function RebuildCanvasSession({kind, scope, seed, label, onSelect, initialSelected, initialViewport, onViewport, revealLast, onRevealed,
  storageKey, persist = 'local', types: typesProp, ariaLabel, menuTitle, badge, badgeTitle, emptyHint,
  onImageTaskIntent, renderImageTaskBinding}: RebuildCanvasProps) {
  const locale = useLocale(); // [HERMIA-FE-20261031 VERA-EN]
  const tk = useT(); // [HERMIA-FE-20261031 VERA-P3 zoom] keyed: 「放大」 must not resolve to Upscale
  const z = useTz();
  const key = storageKey ?? canvasStorageKey(kind, scope);
  const palette = typesProp ?? NODE_TYPES[kind];
  const typeOf = (_k: CanvasKind, t: string) => palette.find(x => x.id === t) ?? NODE_TYPES[_k].find(x => x.id === t);
  const [g, setG] = useState<CvGraph>(() => load(key, seed || {nodes: [], edges: []}, persist));
  const [vp, setVp] = useState<CvViewport>(() => initialViewport ?? {x: 40, y: 40, k: 1});
  const [sel, setSel] = useState<string | null>(() => (initialSelected && g.nodes.some(n => n.id === initialSelected) ? initialSelected : null));
  useEffect(() => { onViewport?.(vp); }, [vp, onViewport]);
  const [menu, setMenu] = useState<null | {cx: number; cy: number; wx: number; wy: number; node?: string}>(null);
  const [q, setQ] = useState('');
  const [link, setLink] = useState<null | {from: string; x: number; y: number}>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const active = useRef(true);
  const removedNodes = useRef(new Set<string>());
  const promptRevisions = useRef(new Map<string, number>());
  const positionRevisions = useRef(new Map<string, number>());
  const liveGraph = useRef(g); liveGraph.current = g;
  const selectedTask = useRef<CvNode>();
  const selectionEpoch = useRef(0);
  useLayoutEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  // [HERMIA-FE-20261024 M3-s1fix] revealLast: if the last node is outside the visible svg, pan just enough to show it (zoom kept).
  // [HERMIA-FE-20261024 M3-s1fix2] the request is kept pending until the svg first has a non-zero size (tab-switch mounts
  // measure 0×0 in Chrome), executed once via ResizeObserver (rAF polling fallback), then cleared so later manual pans,
  // resizes or tab switches never pull the view back.
  const revealPending = useRef(!!revealLast);
  const onRevealedRef = useRef(onRevealed); onRevealedRef.current = onRevealed;
  useLayoutEffect(() => {
    const svg = svgRef.current; if (!revealPending.current || !svg) return;
    const n = g.nodes[g.nodes.length - 1]; if (!n) { revealPending.current = false; onRevealedRef.current?.(); return; }
    const tryReveal = () => {
      if (!revealPending.current) return true;
      const r = svg.getBoundingClientRect(); if (!r.width || !r.height) return false;
      revealPending.current = false; onRevealedRef.current?.(); // [HERMIA-FE-20261024 M3-s1fix2] host clears its request
      setVp(v => {
        const M = 16, l = v.x + n.x * v.k, t = v.y + n.y * v.k, rr = l + REVEAL_W * v.k, b = t + NH * v.k;
        const dx = l < M ? M - l : rr > r.width - M ? (r.width - M) - rr : 0;
        const dy = t < M ? M - t : b > r.height - M ? (r.height - M) - b : 0;
        return dx || dy ? {...v, x: v.x + dx, y: v.y + dy} : v;
      });
      return true;
    };
    if (tryReveal()) return;
    let ro: ResizeObserver | undefined, raf = 0;
    if (typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(() => { if (tryReveal()) ro?.disconnect(); }); ro.observe(svg); }
    else { const tick = () => { if (!tryReveal()) raf = requestAnimationFrame(tick); }; raf = requestAnimationFrame(tick); }
    return () => { ro?.disconnect(); if (raf) cancelAnimationFrame(raf); };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount only; request consumed once
  }, []);
  const drag = useRef<null | {mode: 'pan' | 'node'; id?: string; sx: number; sy: number; ox: number; oy: number}>(null);
  useEffect(() => { writeCanvasGraph(key, g, persist); }, [g, key, persist]);
  useEffect(() => { onSelect?.(g.nodes.find(n => n.id === sel) || null); }, [sel, g.nodes, onSelect]);

  const world = useCallback((cx: number, cy: number) => {
    const r = svgRef.current?.getBoundingClientRect(); const lx = cx - (r?.left || 0), ly = cy - (r?.top || 0);
    return {lx, ly, wx: (lx - vp.x) / vp.k, wy: (ly - vp.y) / vp.k};
  }, [vp]);

  const onContext = (e: RME) => {
    e.preventDefault();
    const nodeEl = (e.target as Element).closest('[data-node-id]');
    const {lx, ly, wx, wy} = world(e.clientX, e.clientY);
    const r = svgRef.current?.getBoundingClientRect(); const W = r?.width || 1e4, H = r?.height || 1e4;
    setQ(''); setMenu({cx: Math.max(4, Math.min(lx, W - 248)), cy: Math.max(4, Math.min(ly, H - 330)), wx, wy, node: nodeEl?.getAttribute('data-node-id') || undefined});
  };
  const addNode = (t: NodeType) => {
    if (!menu) return;
    const n: CvNode = {id: uid('n'), t: t.id, x: Math.round(menu.wx / 10) * 10, y: Math.round(menu.wy / 10) * 10, title: `新${t.label}`};
    selectionEpoch.current++; setG(c => ({...c, nodes: [...c.nodes, n]})); setSel(n.id); setMenu(null);
  };
  const delNode = (id: string) => { selectionEpoch.current++; removedNodes.current.add(id); setG(c => ({nodes: c.nodes.filter(n => n.id !== id), edges: c.edges.filter(e => e.a !== id && e.b !== id)})); setSel(null); setMenu(null); };

  const onDown = (e: RPE<SVGSVGElement>) => {
    if (e.button !== 0) return; setMenu(null);
    const tgt = e.target as Element; const port = tgt.closest('[data-port=out]'); const nodeEl = tgt.closest('[data-node-id]');
    const {wx, wy} = world(e.clientX, e.clientY);
    try { (e.currentTarget as Element).setPointerCapture?.(e.pointerId); } catch { /* jsdom */ }
    if (port) { setLink({from: port.getAttribute('data-for')!, x: wx, y: wy}); return; }
    // [HERMIA-FE-20261024 M3-s1fix] re-clicking the already-selected node re-reports it (host may be showing the other canvas's node).
    if (nodeEl) { const id = nodeEl.getAttribute('data-node-id')!; const n = g.nodes.find(m => m.id === id)!; if (id === sel) onSelect?.(n); if (id !== sel) selectionEpoch.current++; setSel(id); drag.current = {mode: 'node', id, sx: e.clientX, sy: e.clientY, ox: n.x, oy: n.y}; return; }
    if (sel !== null) selectionEpoch.current++; setSel(null); drag.current = {mode: 'pan', sx: e.clientX, sy: e.clientY, ox: vp.x, oy: vp.y};
  };
  const onMove = (e: RPE<SVGSVGElement>) => {
    if (link) { const {wx, wy} = world(e.clientX, e.clientY); setLink({...link, x: wx, y: wy}); return; }
    const d = drag.current; if (!d) return;
    const dx = e.clientX - d.sx, dy = e.clientY - d.sy;
    if (d.mode === 'pan') setVp(v => ({...v, x: d.ox + dx, y: d.oy + dy}));
    else {
      if (d.id && (dx || dy)) positionRevisions.current.set(d.id, (positionRevisions.current.get(d.id) || 0) + 1);
      setG(c => ({...c, nodes: c.nodes.map(n => n.id === d.id ? {...n, x: d.ox + dx / vp.k, y: d.oy + dy / vp.k} : n)}));
    }
  };
  const onUp = (e: RPE<SVGSVGElement>) => {
    if (link) {
      const {wx, wy} = world(e.clientX, e.clientY);
      const hit = g.nodes.find(n => n.id !== link.from && wx >= n.x - 8 && wx <= n.x + NW && wy >= n.y && wy <= n.y + NH && typeOf(kind, n.t)?.ins);
      if (hit && !g.edges.some(x => x.a === link.from && x.b === hit.id)) setG(c => ({...c, edges: [...c.edges, {id: uid('e'), a: link.from, b: hit.id}]}));
      setLink(null);
    }
    drag.current = null;
  };
  const onWheel = (e: RWE<SVGSVGElement>) => {
    const {lx, ly} = world(e.clientX, e.clientY); const f = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    setVp(v => { const k = Math.min(2.5, Math.max(0.25, v.k * f)); return {k, x: lx - (lx - v.x) * (k / v.k), y: ly - (ly - v.y) * (k / v.k)}; });
  };
  const zoom = (f: number) => setVp(v => ({...v, k: Math.min(2.5, Math.max(0.25, v.k * f))}));
  const fit = () => {
    const r = svgRef.current?.getBoundingClientRect(); if (!g.nodes.length || !r) { setVp({x: 40, y: 40, k: 1}); return; }
    const x0 = Math.min(...g.nodes.map(n => n.x)), y0 = Math.min(...g.nodes.map(n => n.y)), x1 = Math.max(...g.nodes.map(n => n.x + NW)), y1 = Math.max(...g.nodes.map(n => n.y + NH));
    const k = Math.min(1.5, Math.max(0.25, Math.min((r.width - 80) / (x1 - x0 || 1), (r.height - 80) / (y1 - y0 || 1))));
    setVp({k, x: 40 - x0 * k, y: 40 - y0 * k});
  };
  const by = Object.fromEntries(g.nodes.map(n => [n.id, n]));
  const curve = (x1: number, y1: number, x2: number, y2: number) => { const m = Math.max(40, Math.abs(x2 - x1) / 2); return `M${x1},${y1} C${x1 + m},${y1} ${x2 - m},${y2} ${x2},${y2}`; };
  const types = palette.filter(t => !q || t.label.includes(q));
  const selectedNode = g.nodes.find(n => n.id === sel);
  const imageTaskNode = kind === 'image' && selectedNode?.t === 'image_generate' ? selectedNode : undefined;
  selectedTask.current = imageTaskNode;
  const taskPrompt = typeof imageTaskNode?.prompt === 'string' ? imageTaskNode.prompt : '';
  const sourceCurrent = (nodeId: string) => () => active.current && !removedNodes.current.has(nodeId)
    && liveGraph.current.nodes.filter(node => node.id === nodeId).length === 1
    && liveGraph.current.nodes.some(node => node.id === nodeId && node.t === 'image_generate');
  const promptRevision = imageTaskNode ? promptRevisions.current.get(imageTaskNode.id) || 0 : 0;
  const readSourceCurrent = (nodeId: string, revision: number) => () => sourceCurrent(nodeId)()
    && (promptRevisions.current.get(nodeId) || 0) === revision;
  const formalSourceCurrent = (node: CvNode, revision: number) => {
    const epoch = selectionEpoch.current, placement = positionRevisions.current.get(node.id) || 0, snapshot = JSON.stringify(node);
    return () => readSourceCurrent(node.id, revision)() && selectionEpoch.current === epoch
      && (positionRevisions.current.get(node.id) || 0) === placement
      && selectedTask.current?.id === node.id && JSON.stringify(liveGraph.current.nodes.find(row => row.id === node.id)) === snapshot;
  };

  return (
    <div data-rcv-wrap="" style={{display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'auto', alignSelf: 'stretch', flex: '1 1 auto', width: '100%', minWidth: 0}}>
    <div className="rcv" data-rebuild-canvas={kind} style={{backgroundPosition: `${vp.x}px ${vp.y}px`, backgroundSize: `${22 * vp.k}px ${22 * vp.k}px`}}>
      {label ? <span className="rcv-label">{z(label)}</span> : null}
      <span className="rcv-local" title={z(badgeTitle ?? '还没有接到服务端画布图接口；切换作品或清浏览器数据会丢')}>{z(badge ?? '仅本机草稿 · 未同步服务端')}</span>
      <svg ref={svgRef} className="rcv-svg" role="application" aria-label={z(ariaLabel ?? (kind === 'image' ? '图片无限画布' : '视频无限画布'))} tabIndex={0}
        onContextMenu={onContext} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onWheel={onWheel}
        onKeyDown={e => { if ((e.key === 'Delete' || e.key === 'Backspace') && sel) delNode(sel); }}>
        <g transform={`translate(${vp.x},${vp.y}) scale(${vp.k})`}>
          {g.edges.map(ed => { const a = by[ed.a], b = by[ed.b]; if (!a || !b) return null; return <path key={ed.id} className="rcv-edge" d={curve(a.x + NW, a.y + NH / 2, b.x, b.y + NH / 2)} />; })}
          {link && by[link.from] ? <path className="rcv-edge rcv-edge--draft" d={curve(by[link.from].x + NW, by[link.from].y + NH / 2, link.x, link.y)} /> : null}
          {g.nodes.map(n => { const ty = typeOf(kind, n.t); const c = ty?.color || '#888';
            return <g key={n.id} className="rcv-node" data-node-id={n.id} data-sel={sel === n.id} transform={`translate(${n.x},${n.y})`}>
              <rect className="box" width={NW} height={NH} rx={8} /><rect className="bar" width={5} height={NH} rx={2} fill={c} />
              <text className="ttl" x={16} y={24}>{ty?.icon} {(tl => tl.length > 12 ? tl.slice(0, 12) + '…' : tl)(displayNodeTitle(locale, n.title))}</text>
              <text className="sub" x={16} y={44}>{ty?.label ? z(ty.label) : n.t}</text><text className="sub" x={NW - 10} y={44} textAnchor="end">{z('本地')}</text>
              {ty?.ins ? <circle className="port" cx={0} cy={NH / 2} r={5.5} style={{fill: 'var(--cv-port-in)'}} data-port="in"><title>{z('输入端口')}</title></circle> : null}
              {ty?.outs ? <circle className="port" cx={NW} cy={NH / 2} r={5.5} fill={c} data-port="out" data-for={n.id}><title>{z('输出端口（拖动连线）')}</title></circle> : null}
            </g>; })}
        </g>
      </svg>
      {g.nodes.length === 0 ? <p className="rcv-empty">{emptyHint ? <>{z(emptyHint)}<br /></> : null}{z('在空白处右键添加节点 · 滚轮缩放 · 拖动空白平移')}</p> : null}
      <div className="rcv-zoom" aria-label={tk('zoom.group')}>
        <button type="button" onClick={() => zoom(1 / 1.2)} aria-label={tk('zoom.out')}>−</button><span>{Math.round(vp.k * 100)}%</span>
        <button type="button" onClick={() => zoom(1.2)} aria-label={tk('zoom.in')}>＋</button><button type="button" onClick={fit}>{tk('zoom.fit')}</button>
      </div>
      <div className="rcv-status">{z('节点')} {g.nodes.length} · {z('连线')} {g.edges.length} · {z('只改图结构，不触发生成')}</div>
      {menu ? <div className="rcv-menu" role="menu" data-add-node-menu="rebuild" style={{left: menu.cx, top: menu.cy}} onPointerDown={e => e.stopPropagation()}>
        {menu.node ? <>
          <div className="grp">{z('节点')}</div>
          <button type="button" role="menuitem" onClick={() => delNode(menu.node!)}>{z('删除节点')}</button>
        </> : <>
          <div className="grp">{z(menuTitle ?? (kind === 'image' ? '添加到图片画布（本机草稿）' : '添加到视频画布（本机草稿）'))}</div>
          <input autoFocus placeholder={z('搜索节点类型')} aria-label={z('搜索节点类型')} value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === 'Escape') setMenu(null); if (e.key === 'Enter' && types[0]) addNode(types[0]); }} />
          <div className="lst">{types.map(t => <button key={t.id} type="button" role="menuitem" data-node-type={t.id} onClick={() => addNode(t)}><i style={{background: t.color}} />{t.icon} {z(t.label)}</button>)}
            {types.length === 0 ? <p className="none">{z('没有匹配的类型')}</p> : null}</div>
        </>}
      </div> : null}
    </div>
    {imageTaskNode ? <Panel title={z('所选图片节点参数')} aria-label={z('所选图片节点参数')} style={{flexShrink: 0}}>
      <p>{z('节点：')}{displayNodeTitle(locale, imageTaskNode.title)}{z('。这里只保存本次提示词草稿；节点标题、连线和参考节点不会自动作为生成参数。')}</p>
      <label>{z('本次提示词')}<textarea aria-label={z('本次提示词')} rows={3} maxLength={8000} value={taskPrompt}
        onChange={event => { const prompt = event.target.value; promptRevisions.current.set(imageTaskNode.id, (promptRevisions.current.get(imageTaskNode.id) || 0) + 1); setG(current => ({...current, nodes: current.nodes.map(node => node.id === imageTaskNode.id ? {...node, prompt} : node)})); }} /></label>
      <Button disabled={!onImageTaskIntent || !taskPrompt.trim()} onClick={() => {
        if (active.current && selectedTask.current === imageTaskNode && onImageTaskIntent && taskPrompt.trim()) {
          onImageTaskIntent({...imageTaskNode, prompt: taskPrompt.trim()}, sourceCurrent(imageTaskNode.id));
        }
      }}>{z('为此节点准备图片任务')}</Button>
      {renderImageTaskBinding?.(imageTaskNode, readSourceCurrent(imageTaskNode.id, promptRevision), promptRevision, formalSourceCurrent(imageTaskNode, promptRevision))}
      <StatusMessage>{z(onImageTaskIntent ? '只打开真实图片任务准备面板。保存入队、执行与接受入库仍需分别确认；不会自动派发或把结果写回草稿图。' : '此入口尚未接入持久图片任务；这里只保存提示词草稿。')}</StatusMessage>
    </Panel> : selectedNode?.t === 'video_generate' ? <StatusMessage data-unsupported="video-node">{z('视频节点的正式任务参数尚未接线；这里只保存草稿图，不会创建或执行视频任务。')}</StatusMessage>
      : kind === 'video' && selectedNode ? <StatusMessage data-unsupported="video-canvas">{z('VIDEO 画布节点正式执行未接线（unsupported）。')}</StatusMessage> : null}
    </div>
  );
}
