// [HERMIA-FE-20261031 DUALCANVAS-COMFY] 下画布：ComfyUI 风格节点图（类型化端口 + 分类可搜索菜单）。
// 只存本地结构/草稿：不执行、不连 ComfyUI、不调用模型、不发任何网络请求。
import {useCallback, useEffect, useId, useMemo, useRef, useState} from 'react';
import type {PointerEvent as RPE, MouseEvent as RME, WheelEvent as RWE, KeyboardEvent as RKE} from 'react';
import {useLocale} from '../../../i18n';
import {GROUP_LABEL, NODE_GROUPS, connect, defaultRegistry, nodeLabel, portColor, sanitizeGraph, searchDefs, typesCompatible,
  type CfGraph, type CfNode, type NodeDef, type Registry} from './comfyRegistry';
import {sessionCanvasStore} from '../RebuildCanvas';

/** 无身份时下画布的会话内存（类型化，不混入主画布 CvGraph）；随 sessionCanvasStore.clear() 一起清空。 */
const COMFY_SESSION = new Map<string, unknown>();
export const sessionComfyStore = {get: (k: string) => COMFY_SESSION.get(k), set: (k: string, v: unknown) => { COMFY_SESSION.set(k, v); }, clear: () => COMFY_SESSION.clear()};
const baseClear = sessionCanvasStore.clear;
sessionCanvasStore.clear = () => { baseClear(); COMFY_SESSION.clear(); };
import './comfyCanvas.css';

const W = 210, HEAD = 28, ROW = 20, PAD = 8;
export const nodeHeight = (d?: NodeDef) => HEAD + Math.max(1, d ? Math.max(d.inputs.length, d.outputs.length) : 1) * ROW + PAD + (d?.widgets.length ? 16 : 0);
let seq = 0; const uid = () => `cf${Date.now().toString(36)}${(seq++).toString(36)}`;

type Props = {kind: 'image' | 'video'; storageKey: string; persist: 'local' | 'session'; label: string; ariaLabel: string; badge: string; badgeTitle?: string;
  emptyHint?: string; onSelect?: (n: CfNode | null, def: NodeDef | null) => void; registry?: Registry};

function load(key: string, persist: 'local' | 'session', reg: Registry): CfGraph {
  let raw: unknown = null;
  if (persist === 'session') raw = sessionComfyStore.get(key) ?? null;
  else { try { const s = localStorage.getItem(key); raw = s ? JSON.parse(s) : null; } catch { raw = null; } }
  return sanitizeGraph(raw, reg);
}

export function ComfyCanvas({kind, storageKey, persist, label, ariaLabel, badge, badgeTitle, emptyHint, onSelect, registry}: Props) {
  const locale = useLocale(); const zh = locale.startsWith('zh');
  const L = (z: string, e: string) => (zh ? z : e);
  const reg = registry ?? defaultRegistry(kind);
  const [g, setG] = useState<CfGraph>(() => load(storageKey, persist, reg));
  const [vp, setVp] = useState({x: 30, y: 30, k: 1});
  const [sel, setSel] = useState<string | null>(null);
  const [menu, setMenu] = useState<null | {cx: number; cy: number; wx: number; wy: number; node?: string}>(null);
  const [q, setQ] = useState('');
  const addBtnRef = useRef<HTMLButtonElement>(null);
  // [VERA-3/4] Esc / Enter / 点击选项加节点后，焦点回到「＋ 节点」按钮
  const closeMenu = () => { setMenu(null); addBtnRef.current?.focus(); };
  const [msg, setMsg] = useState('');
  const [link, setLink] = useState<null | {from: string; slot: number; type: string; x: number; y: number}>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<null | {mode: 'pan' | 'node'; id?: string; sx: number; sy: number; ox: number; oy: number}>(null);
  const def = useCallback((t: string) => reg.byName.get(t), [reg]);
  useEffect(() => {
    if (persist === 'session') sessionComfyStore.set(storageKey, g);
    else { try { localStorage.setItem(storageKey, JSON.stringify(g)); } catch { /* ignore */ } }
  }, [g, storageKey, persist]);
  useEffect(() => { const n = g.nodes.find(x => x.id === sel) ?? null; onSelect?.(n, n ? def(n.t) ?? null : null); }, [sel, g.nodes, onSelect, def]);

  const world = (cx: number, cy: number) => {
    const r = svgRef.current?.getBoundingClientRect(); const lx = cx - (r?.left || 0), ly = cy - (r?.top || 0);
    return {lx, ly, wx: (lx - vp.x) / vp.k, wy: (ly - vp.y) / vp.k, W: r?.width || 1e4, H: r?.height || 1e4};
  };
  const openMenu = (cx: number, cy: number, node?: string) => {
    const {lx, ly, wx, wy, W: rw, H: rh} = world(cx, cy);
    setQ(''); setActive(0); setMenu({cx: Math.max(4, Math.min(lx, rw - 300)), cy: Math.max(4, Math.min(ly, rh - 360)), wx, wy, node});
  };
  const onContext = (e: RME) => { e.preventDefault(); openMenu(e.clientX, e.clientY, (e.target as Element).closest('[data-node-id]')?.getAttribute('data-node-id') ?? undefined); };
  const add = (d: NodeDef) => {
    if (!menu) return;
    const n: CfNode = {id: uid(), t: d.name, x: Math.round(menu.wx / 10) * 10, y: Math.round(menu.wy / 10) * 10, title: nodeLabel(d, 'zh-CN')};
    setG(x => ({...x, nodes: [...x.nodes, n]})); setSel(n.id); setMsg(''); closeMenu(); // [VERA-4 P3] 点击选项与 Esc/Enter 一样，焦点回到「＋ 节点」
  };
  const del = (id: string) => { setG(x => ({nodes: x.nodes.filter(n => n.id !== id), edges: x.edges.filter(e => e.a !== id && e.b !== id)})); setSel(s => (s === id ? null : s)); setMenu(null); };
  const tryConnect = (a: string, as: number, b: string, bs: number) => {
    const r = connect(g, reg, a, as, b, bs);
    if (r.ok) { setG(r.graph); setMsg(L('已连线（仅草稿结构）', 'Linked (draft structure only)')); }
    else setMsg(r.reason === 'type' ? L(`类型不匹配：${r.from} 不能接到 ${r.to}`, `Type mismatch: ${r.from} cannot connect to ${r.to}`)
      : r.reason === 'cycle' ? L('不能连成环', 'Would create a cycle') : L('不能这样连', 'Cannot connect here'));
    return r.ok;
  };
  const disconnect = (b: string, bs: number) => setG(x => ({...x, edges: x.edges.filter(e => !(e.b === b && e.bs === bs))}));

  const onDown = (e: RPE) => {
    const el = e.target as Element;
    const outEl = el.closest('[data-out]');
    if (outEl) {
      const [id, s] = outEl.getAttribute('data-out')!.split(':'); const {wx, wy} = world(e.clientX, e.clientY);
      const n = g.nodes.find(x => x.id === id); const t = n && def(n.t)?.outputs[Number(s)]?.type;
      if (t) setLink({from: id, slot: Number(s), type: t, x: wx, y: wy});
      e.stopPropagation(); return;
    }
    if (el.closest('[data-in]')) return;
    const nodeEl = el.closest('[data-node-id]');
    if (nodeEl) {
      const id = nodeEl.getAttribute('data-node-id')!; const n = g.nodes.find(x => x.id === id)!; setSel(id);
      drag.current = {mode: 'node', id, sx: e.clientX, sy: e.clientY, ox: n.x, oy: n.y};
    } else { setSel(null); drag.current = {mode: 'pan', sx: e.clientX, sy: e.clientY, ox: vp.x, oy: vp.y}; }
    setMenu(null);
  };
  const onMove = (e: RPE) => {
    if (link) { const {wx, wy} = world(e.clientX, e.clientY); setLink({...link, x: wx, y: wy}); return; }
    const d = drag.current; if (!d) return;
    const dx = e.clientX - d.sx, dy = e.clientY - d.sy;
    if (d.mode === 'pan') setVp(v => ({...v, x: d.ox + dx, y: d.oy + dy}));
    else setG(x => ({...x, nodes: x.nodes.map(n => (n.id === d.id ? {...n, x: d.ox + dx / vp.k, y: d.oy + dy / vp.k} : n))}));
  };
  const onUp = (e: RPE) => {
    if (link) {
      const hit = typeof document.elementFromPoint === 'function' ? document.elementFromPoint(e.clientX, e.clientY) : null;
      const inEl = hit?.closest('[data-in]') ?? (e.target as Element).closest?.('[data-in]');
      if (inEl) { const [id, s] = inEl.getAttribute('data-in')!.split(':'); tryConnect(link.from, link.slot, id, Number(s)); }
      setLink(null);
    }
    drag.current = null;
  };
  const onWheel = (e: RWE) => {
    const {lx, ly} = world(e.clientX, e.clientY);
    setVp(v => { const k = Math.min(2, Math.max(0.3, v.k * (e.deltaY < 0 ? 1.1 : 1 / 1.1))); return {k, x: lx - (lx - v.x) * (k / v.k), y: ly - (ly - v.y) * (k / v.k)}; });
  };
  const onKey = (e: RKE) => {
    if ((e.key === 'Delete' || e.key === 'Backspace') && sel && !(e.target as Element).closest('input,select,textarea')) { e.preventDefault(); del(sel); }
  };
  const zoom = (f: number) => setVp(v => ({...v, k: Math.min(2, Math.max(0.3, v.k * f))}));

  const portY = (i: number) => HEAD + i * ROW + ROW / 2 + 2;
  const nodeMap = useMemo(() => new Map(g.nodes.map(n => [n.id, n])), [g.nodes]);
  const results = useMemo(() => searchDefs(reg, q, locale), [reg, q, locale]);
  const grouped = useMemo(() => NODE_GROUPS.map(gr => [gr, results.filter(d => d.group === gr)] as const).filter(([, l]) => l.length), [results]);
  const selNode = sel ? nodeMap.get(sel) : undefined; const selDef = selNode ? def(selNode.t) : undefined;
  const mid = useId().replace(/:/g, '');
  const optId = (n: string) => `${mid}-o-${n.replace(/[^A-Za-z0-9_-]/g, '_')}`;
  const flat = useMemo(() => grouped.flatMap(([, l]) => l), [grouped]);
  const [active, setActive] = useState(0);
  const activeDef = flat.length ? flat[Math.max(0, Math.min(active, flat.length - 1))] : undefined;
  const onMenuKey = (e: RKE<HTMLInputElement>) => {
    const last = flat.length - 1; if (last < 0 && e.key !== 'Escape') return;
    const cur = Math.max(0, Math.min(active, last));
    const nx = e.key === 'ArrowDown' ? Math.min(last, cur + 1) : e.key === 'ArrowUp' ? Math.max(0, cur - 1) : e.key === 'Home' ? 0 : e.key === 'End' ? last : null;
    if (nx !== null) { e.preventDefault(); setActive(nx); document.getElementById(optId(flat[nx].name))?.scrollIntoView?.({block: 'nearest'}); return; }
    if (e.key === 'Enter' && activeDef) { e.preventDefault(); add(activeDef); closeMenu(); }
  };
  const Gl = (gr: keyof typeof GROUP_LABEL) => (zh ? GROUP_LABEL[gr].zh : GROUP_LABEL[gr].en);

  return (
    <div className="rcv cfy" data-comfy-canvas={kind} onKeyDown={onKey}>
      <span className="rcv-label">{label}</span>
      <span className="rcv-local" data-honest="no-exec" title={badgeTitle}>{badge}</span>
      <button type="button" ref={addBtnRef} className="cfy-add" data-comfy-add aria-haspopup="menu" onClick={e => { const r = svgRef.current?.getBoundingClientRect(); openMenu((r?.left || 0) + 60, (r?.top || 0) + 50); e.stopPropagation(); }}>
        {L('＋ 节点', '+ Node')}</button>
      <svg ref={svgRef} className="rcv-svg" role="application" aria-label={ariaLabel} tabIndex={0}
        onContextMenu={onContext} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={() => { drag.current = null; setLink(null); }} onWheel={onWheel}>
        <g transform={`translate(${vp.x},${vp.y}) scale(${vp.k})`}>
          {g.edges.map(e => {
            const a = nodeMap.get(e.a), b = nodeMap.get(e.b); if (!a || !b) return null;
            const t = def(a.t)?.outputs[e.as]?.type ?? '*';
            const x1 = a.x + W, y1 = a.y + portY(e.as), x2 = b.x, y2 = b.y + portY(e.bs), c = Math.max(40, Math.abs(x2 - x1) / 2);
            return <path key={e.id} className="cfy-edge" data-edge-type={t} stroke={portColor(t)} d={`M${x1},${y1} C${x1 + c},${y1} ${x2 - c},${y2} ${x2},${y2}`} />;
          })}
          {link ? (() => { const a = nodeMap.get(link.from)!; const x1 = a.x + W, y1 = a.y + portY(link.slot);
            return <path className="cfy-edge cfy-edge--draft" stroke={portColor(link.type)} d={`M${x1},${y1} L${link.x},${link.y}`} />; })() : null}
          {g.nodes.map(n => {
            const d = def(n.t); const h = nodeHeight(d);
            const head = d ? (d.output_node ? '#5b8f5b' : d.source === 'poemseed' ? 'var(--color-accent-primary)' : portColor(d.outputs[0]?.type ?? '*')) : '#888';
            return (
              <g key={n.id} className="cfy-node" data-node-id={n.id} data-node-class={n.t} data-sel={sel === n.id} transform={`translate(${n.x},${n.y})`}>
                <rect className="box" width={W} height={h} rx={7} />
                <rect className="hd" width={W} height={HEAD} rx={7} />
                <rect x={0} y={0} width={4} height={h} rx={2} fill={head} />
                <text className="ttl" x={12} y={18}>{d ? nodeLabel(d, locale) : n.t}{d ? null : ` · ${L('未知节点', 'unknown node')}`}</text>
                {d?.inputs.map((p, i) => {
                  const linked = g.edges.some(e => e.b === n.id && e.bs === i);
                  const ok = link ? typesCompatible(link.type, p.type) && link.from !== n.id : undefined;
                  return <g key={`i${i}`} data-in={`${n.id}:${i}`} data-port-type={p.type} data-compatible={ok === undefined ? undefined : String(ok)} className="cfy-port">
                    <rect className="hit" x={-9} y={portY(i) - 9} width={W / 2 + 9} height={18} fill="transparent" />
                    <circle cx={0} cy={portY(i)} r={6} fill={linked ? portColor(p.type) : 'var(--cv-node)'} stroke={portColor(p.type)} strokeWidth={2} />
                    <text className="pl" x={10} y={portY(i) + 4}>{p.name}{p.optional ? '?' : ''}</text></g>;
                })}
                {d?.outputs.map((p, i) => <g key={`o${i}`} data-out={`${n.id}:${i}`} data-port-type={p.type} className="cfy-port">
                  <rect className="hit" x={W / 2} y={portY(i) - 9} width={W / 2 + 9} height={18} fill="transparent" />
                  <circle cx={W} cy={portY(i)} r={6} fill={portColor(p.type)} />
                  <text className="pl pr" x={W - 10} y={portY(i) + 4} textAnchor="end">{p.name}</text></g>)}
                {d?.widgets.length ? <text className="sub" x={12} y={h - 8}>{L(`${d.widgets.length} 个参数（草稿，不执行）`, `${d.widgets.length} params (draft, not run)`)}</text> : null}
              </g>);
          })}
        </g>
      </svg>
      {!g.nodes.length ? <p className="rcv-empty">{emptyHint}<br />{L('右键空白处或点「＋ 节点」，按分类或搜索添加 ComfyUI 风格节点', 'Right-click or press "+ Node" to add ComfyUI-style nodes')}</p> : null}
      {menu ? (
        // [HERMIA-FE-20261031 DUALCANVAS-COMFY P2-2] combobox + listbox（APG）：分组 role=group + aria-labelledby；↑↓ / Home / End 移动，Enter 添加，Esc 关闭。
        <div className="rcv-menu cfy-menu" data-add-node-menu role="dialog" aria-label={L('添加节点', 'Add node')} style={{left: menu.cx, top: menu.cy}}
          onPointerDown={e => e.stopPropagation()} onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); closeMenu(); } }}>
          <div className="grp">{L('添加到下画布（只是草稿结构，不会执行）', 'Add to lower canvas (draft only, never runs)')}</div>
          <input type="text" role="combobox" autoFocus value={q} onChange={e => { setQ(e.target.value); setActive(0); }}
            aria-expanded="true" aria-controls={`${mid}-lb`} aria-autocomplete="list" aria-activedescendant={activeDef ? optId(activeDef.name) : undefined}
            onKeyDown={onMenuKey}
            placeholder={L('搜索节点：名称 / 分类 / 端口类型', 'Search: name / category / port type')} aria-label={L('搜索节点', 'Search nodes')} />
          {menu.node ? <button type="button" data-node-delete onClick={() => del(menu.node!)}>{L('删除这个节点', 'Delete this node')}</button> : null}
          <div className="lst" role="listbox" id={`${mid}-lb`} aria-label={L('节点', 'Nodes')}>
            {grouped.map(([gr, list]) => <div key={gr} role="group" aria-labelledby={`${mid}-g-${gr}`} data-node-group={gr}>
              <div className="grp grp--h" id={`${mid}-g-${gr}`} role="presentation">{Gl(gr)} <span aria-hidden="true">{list.length}</span></div>
              {list.map(d => <div key={d.name} id={optId(d.name)} role="option" aria-selected={activeDef?.name === d.name} className={`cfy-opt${activeDef?.name === d.name ? ' is-active' : ''}`}
                data-node-type={d.name} onClick={() => add(d)} onMouseEnter={() => setActive(flat.indexOf(d))}>
                <i style={{background: d.source === 'poemseed' ? 'var(--color-accent-primary)' : portColor(d.outputs[0]?.type ?? d.inputs[0]?.type ?? '*')}} />
                <span>{nodeLabel(d, locale)}</span>{zh && d.source !== 'poemseed' ? <small>{d.display_name}</small> : null}</div>)}
            </div>)}
          </div>
          {!results.length ? <p className="none" role="status">{L('没有匹配的节点', 'No matching node')}</p> : null}
        </div>) : null}
      {selNode && selDef && selDef.inputs.length ? (
        <div className="cfy-insp" data-comfy-inspector aria-label={L('输入端口连线', 'Input links')} role="group">
          <b>{nodeLabel(selDef, locale)}</b>
          {selDef.inputs.map((p, i) => {
            const cur = g.edges.find(e => e.b === selNode.id && e.bs === i);
            const opts = g.nodes.filter(n => n.id !== selNode.id).flatMap(n => (def(n.t)?.outputs ?? []).map((o, s) => ({n, o, s}))).filter(x => typesCompatible(x.o.type, p.type));
            const labelOf = (x: {n: CfNode; o: {name: string}}) => `${def(x.n.t) ? nodeLabel(def(x.n.t)!, locale) : x.n.t} · ${x.o.name}`;
            return <label key={i}><i style={{background: portColor(p.type)}} />{p.name} <small>{p.type}</small>
              <select data-input-select={i} value={cur ? `${cur.a}:${cur.as}` : ''} onChange={e => { const v = e.target.value; if (!v) disconnect(selNode.id, i); else { const [a, s] = v.split(':'); tryConnect(a, Number(s), selNode.id, i); } }}>
                <option value="">{L('— 未连接 —', '— not linked —')}</option>
                {opts.map(x => <option key={`${x.n.id}:${x.s}`} value={`${x.n.id}:${x.s}`}>{labelOf(x)}</option>)}
              </select></label>;
          })}
          <small className="cfy-insp__note">{L('只列出类型匹配的输出', 'Only type-compatible outputs are listed')}</small>
        </div>) : null}
      <div className="rcv-zoom"><button type="button" aria-label={L('缩小画布', 'Zoom out')} onClick={() => zoom(1 / 1.15)}>－</button><span>{Math.round(vp.k * 100)}%</span>
        <button type="button" aria-label={L('放大画布', 'Zoom in')} onClick={() => zoom(1.15)}>＋</button></div>
      <div className="rcv-status" role="status" data-comfy-status>{msg || L(`节点 ${g.nodes.length} · 连线 ${g.edges.length} · 不会执行`, `${g.nodes.length} nodes · ${g.edges.length} links · never runs`)}</div>
    </div>
  );
}
