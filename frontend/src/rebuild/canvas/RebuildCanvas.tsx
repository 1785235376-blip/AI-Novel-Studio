/* [HERMIA-FE-20261022 U1] 原型同款黑色无限画布（图片画布 / 视频画布共用）。
   - 点阵网格、节点卡（左色条 + 标题 + 类型 + 本地标）、左右端口、贝塞尔连线、滚轮缩放、空白拖拽平移、拖动节点、从输出端口拖线连接。
   - 右键空白处 → 在点击位置弹「添加节点」菜单（类型取自现存 StudioGraphDefinitionId 目录，按画布过滤）；右键节点 → 删除。
   - 持久化：前端还没有可直接写入的画布图接口接到这里，所以只存本机浏览器 localStorage，并在画布上写明「仅本机草稿」。不发任何写请求。 */
import {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import type {PointerEvent as RPE, MouseEvent as RME, WheelEvent as RWE} from 'react';
import type {StudioGraphDefinitionId} from '../../creative/studioGraphTypes';
import './rebuildCanvas.css';

export type CanvasKind = 'image' | 'video';
export type NodeType = {id: StudioGraphDefinitionId; label: string; color: string; icon: string; ins: boolean; outs: boolean};
export type CvNode = {id: string; t: StudioGraphDefinitionId; x: number; y: number; title: string};
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
const typeOf = (k: CanvasKind, t: string) => NODE_TYPES[k].find(x => x.id === t);
let seq = 0; const uid = (p: string) => `${p}${Date.now().toString(36)}${(seq++).toString(36)}`;
export const canvasStorageKey = (k: CanvasKind, scope: string) => `poemseed.rebuild.canvas.${k}.${scope}`;

function load(key: string, seed: CvGraph): CvGraph {
  try { const raw = localStorage.getItem(key); if (raw) { const g = JSON.parse(raw); if (Array.isArray(g?.nodes) && Array.isArray(g?.edges)) return g; } } catch { /* ignore */ }
  return seed;
}

export type CvViewport = {x: number; y: number; k: number};
// [HERMIA-FE-20261024 M3-s1] optional initialSelected / initialViewport / onViewport so a host that remounts the canvas
// (after an external local-draft write) keeps the user's selection and pan/zoom. Defaults unchanged.
export function RebuildCanvas({kind, scope, seed, label, onSelect, initialSelected, initialViewport, onViewport, revealLast}: {kind: CanvasKind; scope: string; seed?: CvGraph; label?: string; onSelect?: (n: CvNode | null) => void;
  initialSelected?: string | null; initialViewport?: CvViewport; onViewport?: (vp: CvViewport) => void; revealLast?: boolean}) {
  const key = canvasStorageKey(kind, scope);
  const [g, setG] = useState<CvGraph>(() => load(key, seed || {nodes: [], edges: []}));
  const [vp, setVp] = useState<CvViewport>(() => initialViewport ?? {x: 40, y: 40, k: 1});
  const [sel, setSel] = useState<string | null>(() => (initialSelected && g.nodes.some(n => n.id === initialSelected) ? initialSelected : null));
  useEffect(() => { onViewport?.(vp); }, [vp, onViewport]);
  const [menu, setMenu] = useState<null | {cx: number; cy: number; wx: number; wy: number; node?: string}>(null);
  const [q, setQ] = useState('');
  const [link, setLink] = useState<null | {from: string; x: number; y: number}>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  // [HERMIA-FE-20261024 M3-s1fix] revealLast: on mount, if the last node is outside the visible svg, pan just enough to show it (zoom kept).
  useLayoutEffect(() => {
    const r = svgRef.current?.getBoundingClientRect(); const n = g.nodes[g.nodes.length - 1];
    if (!revealLast || !n || !r || !r.width || !r.height) return;
    setVp(v => {
      const M = 16, l = v.x + n.x * v.k, t = v.y + n.y * v.k, rr = l + REVEAL_W * v.k, b = t + NH * v.k;
      const dx = l < M ? M - l : rr > r.width - M ? (r.width - M) - rr : 0;
      const dy = t < M ? M - t : b > r.height - M ? (r.height - M) - b : 0;
      return dx || dy ? {...v, x: v.x + dx, y: v.y + dy} : v;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount only
  }, []);
  const drag = useRef<null | {mode: 'pan' | 'node'; id?: string; sx: number; sy: number; ox: number; oy: number}>(null);
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(g)); } catch { /* ignore */ } }, [g, key]);
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
    setG(c => ({...c, nodes: [...c.nodes, n]})); setSel(n.id); setMenu(null);
  };
  const delNode = (id: string) => { setG(c => ({nodes: c.nodes.filter(n => n.id !== id), edges: c.edges.filter(e => e.a !== id && e.b !== id)})); setSel(null); setMenu(null); };

  const onDown = (e: RPE<SVGSVGElement>) => {
    if (e.button !== 0) return; setMenu(null);
    const tgt = e.target as Element; const port = tgt.closest('[data-port=out]'); const nodeEl = tgt.closest('[data-node-id]');
    const {wx, wy} = world(e.clientX, e.clientY);
    try { (e.currentTarget as Element).setPointerCapture?.(e.pointerId); } catch { /* jsdom */ }
    if (port) { setLink({from: port.getAttribute('data-for')!, x: wx, y: wy}); return; }
    // [HERMIA-FE-20261024 M3-s1fix] re-clicking the already-selected node re-reports it (host may be showing the other canvas's node).
    if (nodeEl) { const id = nodeEl.getAttribute('data-node-id')!; const n = g.nodes.find(m => m.id === id)!; if (id === sel) onSelect?.(n); setSel(id); drag.current = {mode: 'node', id, sx: e.clientX, sy: e.clientY, ox: n.x, oy: n.y}; return; }
    setSel(null); drag.current = {mode: 'pan', sx: e.clientX, sy: e.clientY, ox: vp.x, oy: vp.y};
  };
  const onMove = (e: RPE<SVGSVGElement>) => {
    if (link) { const {wx, wy} = world(e.clientX, e.clientY); setLink({...link, x: wx, y: wy}); return; }
    const d = drag.current; if (!d) return;
    const dx = e.clientX - d.sx, dy = e.clientY - d.sy;
    if (d.mode === 'pan') setVp(v => ({...v, x: d.ox + dx, y: d.oy + dy}));
    else setG(c => ({...c, nodes: c.nodes.map(n => n.id === d.id ? {...n, x: d.ox + dx / vp.k, y: d.oy + dy / vp.k} : n)}));
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
  const types = NODE_TYPES[kind].filter(t => !q || t.label.includes(q));

  return (
    <div className="rcv" data-rebuild-canvas={kind} style={{backgroundPosition: `${vp.x}px ${vp.y}px`, backgroundSize: `${22 * vp.k}px ${22 * vp.k}px`}}>
      {label ? <span className="rcv-label">{label}</span> : null}
      <span className="rcv-local" title="还没有接到服务端画布图接口；切换作品或清浏览器数据会丢">仅本机草稿 · 未同步服务端</span>
      <svg ref={svgRef} className="rcv-svg" role="application" aria-label={kind === 'image' ? '图片无限画布' : '视频无限画布'} tabIndex={0}
        onContextMenu={onContext} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onWheel={onWheel}
        onKeyDown={e => { if ((e.key === 'Delete' || e.key === 'Backspace') && sel) delNode(sel); }}>
        <g transform={`translate(${vp.x},${vp.y}) scale(${vp.k})`}>
          {g.edges.map(ed => { const a = by[ed.a], b = by[ed.b]; if (!a || !b) return null; return <path key={ed.id} className="rcv-edge" d={curve(a.x + NW, a.y + NH / 2, b.x, b.y + NH / 2)} />; })}
          {link && by[link.from] ? <path className="rcv-edge rcv-edge--draft" d={curve(by[link.from].x + NW, by[link.from].y + NH / 2, link.x, link.y)} /> : null}
          {g.nodes.map(n => { const ty = typeOf(kind, n.t); const c = ty?.color || '#888';
            return <g key={n.id} className="rcv-node" data-node-id={n.id} data-sel={sel === n.id} transform={`translate(${n.x},${n.y})`}>
              <rect className="box" width={NW} height={NH} rx={8} /><rect className="bar" width={5} height={NH} rx={2} fill={c} />
              <text className="ttl" x={16} y={24}>{ty?.icon} {n.title.length > 12 ? n.title.slice(0, 12) + '…' : n.title}</text>
              <text className="sub" x={16} y={44}>{ty?.label || n.t}</text><text className="sub" x={NW - 10} y={44} textAnchor="end">本地</text>
              {ty?.ins ? <circle className="port" cx={0} cy={NH / 2} r={5.5} fill="#8a93a5" data-port="in"><title>输入端口</title></circle> : null}
              {ty?.outs ? <circle className="port" cx={NW} cy={NH / 2} r={5.5} fill={c} data-port="out" data-for={n.id}><title>输出端口（拖动连线）</title></circle> : null}
            </g>; })}
        </g>
      </svg>
      {g.nodes.length === 0 ? <p className="rcv-empty">在空白处<b>右键</b>添加节点 · 滚轮缩放 · 拖动空白平移</p> : null}
      <div className="rcv-zoom" aria-label="缩放">
        <button type="button" onClick={() => zoom(1 / 1.2)} aria-label="缩小">−</button><span>{Math.round(vp.k * 100)}%</span>
        <button type="button" onClick={() => zoom(1.2)} aria-label="放大">＋</button><button type="button" onClick={fit}>适配</button>
      </div>
      <div className="rcv-status">节点 {g.nodes.length} · 连线 {g.edges.length} · 只改图结构，不触发生成</div>
      {menu ? <div className="rcv-menu" role="menu" data-add-node-menu="rebuild" style={{left: menu.cx, top: menu.cy}} onPointerDown={e => e.stopPropagation()}>
        {menu.node ? <>
          <div className="grp">节点</div>
          <button type="button" role="menuitem" onClick={() => delNode(menu.node!)}>删除节点</button>
        </> : <>
          <div className="grp">添加到{kind === 'image' ? '图片' : '视频'}画布（本机草稿）</div>
          <input autoFocus placeholder="搜索节点类型" aria-label="搜索节点类型" value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === 'Escape') setMenu(null); if (e.key === 'Enter' && types[0]) addNode(types[0]); }} />
          <div className="lst">{types.map(t => <button key={t.id} type="button" role="menuitem" data-node-type={t.id} onClick={() => addNode(t)}><i style={{background: t.color}} />{t.icon} {t.label}</button>)}
            {types.length === 0 ? <p className="none">没有匹配的类型</p> : null}</div>
        </>}
      </div> : null}
    </div>
  );
}
