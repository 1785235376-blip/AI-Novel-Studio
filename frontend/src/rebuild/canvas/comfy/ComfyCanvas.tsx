// [HERMIA-FE-20261031 DUALCANVAS-COMFY] 下画布：ComfyUI 风格节点图（类型化端口 + 分类可搜索菜单）。
// 只存本地结构/草稿：不执行、不连 ComfyUI、不调用模型、不发任何网络请求。
import {useCallback, useEffect, useId, useMemo, useRef, useState} from 'react';
import type {PointerEvent as RPE, MouseEvent as RME, WheelEvent as RWE, KeyboardEvent as RKE} from 'react';
import {useLocale} from '../../../i18n';
import {GROUP_LABEL, NODE_GROUPS, connect, defaultRegistry, defaultWidgetParams, nodeLabel, portColor, sanitizeGraph, searchDefs, typesCompatible, widgetDefault,
  type CfGraph, type CfNode, type NodeDef, type Registry, type WidgetDef, type WidgetPrimitive} from './comfyRegistry';
import {sessionCanvasStore} from '../RebuildCanvas';
import {dispatchLowerCanvasRun, downloadAssetBlob, fetchLowerCanvasRun, loadRemoteComfyGraph, preflightLowerCanvasRun, saveRemoteComfyGraph,
  type ComfyRemoteContext, type LowerCanvasRun, type RunAsset, type RunQuote} from './comfyRemote';

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
  emptyHint?: string; onSelect?: (n: CfNode | null, def: NodeDef | null) => void; registry?: Registry; remote?: ComfyRemoteContext;
  onAdoptAsset?: (asset: RunAsset) => void};

function load(key: string, persist: 'local' | 'session', reg: Registry): CfGraph {
  let raw: unknown = null;
  if (persist === 'session') raw = sessionComfyStore.get(key) ?? null;
  else { try { const s = localStorage.getItem(key); raw = s ? JSON.parse(s) : null; } catch { raw = null; } }
  return sanitizeGraph(raw, reg);
}

export function ComfyCanvas({kind, storageKey, persist, label, ariaLabel, badge, badgeTitle, emptyHint, onSelect, registry, remote, onAdoptAsset}: Props) {
  const locale = useLocale(); const zh = locale.startsWith('zh');
  const L = (z: string, e: string) => (zh ? z : e);
  const reg = registry ?? defaultRegistry(kind);
  const [g, setG] = useState<CfGraph>(() => load(storageKey, persist, reg));
  const [vp, setVp] = useState({x: 30, y: 30, k: 1});
  const [remoteState, setRemoteState] = useState<'off' | 'loading' | 'ready' | 'unavailable' | 'conflict'>(remote ? 'loading' : 'off');
  const [remoteNote, setRemoteNote] = useState('');
  const remoteVersion = useRef(0);
  const [runPhase, setRunPhase] = useState<'idle' | 'saving' | 'quoted' | 'running' | 'done' | 'error'>('idle');
  const [runQuote, setRunQuote] = useState<RunQuote | null>(null);
  const [runResult, setRunResult] = useState<LowerCanvasRun | null>(null);
  const [runMessage, setRunMessage] = useState('');
  const [runThumbs, setRunThumbs] = useState<Record<string, string>>({});
  const skipRemoteSave = useRef(true);
  const graphRef = useRef(g);
  const [sel, setSel] = useState<string | null>(null);
  const [menu, setMenu] = useState<null | {cx: number; cy: number; wx: number; wy: number; node?: string}>(null);
  const [q, setQ] = useState('');
  const addBtnRef = useRef<HTMLButtonElement>(null);
  // [VERA-3 P2] 菜单由键盘关闭（Esc）或添加节点后，焦点回到「＋ 节点」按钮
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

  useEffect(() => { graphRef.current = g; }, [g]);
  // [HERMIA-FE-20261031 DUALCANVAS-COMFY WIRING] Real identity → load/save the lower canvas draft
  // through the project API. No identity keeps the old session-memory path and makes no request.
  useEffect(() => {
    if (!remote) { setRemoteState('off'); setRemoteNote(''); return; }
    const ac = new AbortController(); let alive = true;
    setRemoteState('loading'); setRemoteNote(L('读取云端草稿…', 'Loading cloud draft…'));
    loadRemoteComfyGraph(kind, remote, ac.signal).then(loaded => {
      if (!alive) return;
      remoteVersion.current = loaded.version;
      const local = graphRef.current;
      const localEmpty = !local.nodes.length && !local.edges.length;
      if (!loaded.version && localEmpty) {
        skipRemoteSave.current = true;
      } else if (!localEmpty) {
        // Keep the local draft (user data wins) and sync it against the loaded version.
        skipRemoteSave.current = false;
        setRemoteNote(L('本机草稿将同步到云端', 'Local draft will sync to the cloud'));
      } else {
        skipRemoteSave.current = true;
        setG(sanitizeGraph(loaded.graph, reg));
        setRemoteNote(L('已读取云端草稿', 'Cloud draft loaded'));
      }
      setRemoteState('ready');
    }).catch(() => {
      if (!alive) return;
      setRemoteState('unavailable');
      setRemoteNote(L('云端草稿不可用，保留本机草稿', 'Cloud draft unavailable; local draft kept'));
    });
    return () => { alive = false; ac.abort(); };
  }, [remote?.projectId, remote?.token, remote?.branchId, kind]);

  useEffect(() => {
    if (!remote || remoteState !== 'ready') return;
    if (skipRemoteSave.current) { skipRemoteSave.current = false; return; }
    const timer = setTimeout(() => {
      saveRemoteComfyGraph(kind, remote, remoteVersion.current, graphRef.current).then(result => {
        if (result.ok) {
          remoteVersion.current = result.version;
          setRemoteNote(L(`云端草稿已保存 v${result.version}`, `Cloud draft saved v${result.version}`));
        } else {
          setRemoteState('conflict');
          setRemoteNote(L(`云端版本冲突（当前 v${result.currentVersion}），本机草稿未覆盖`,
            `Cloud version conflict (current v${result.currentVersion}); local draft not overwritten`));
        }
      }).catch(() => {
        setRemoteState('unavailable');
        setRemoteNote(L('云端保存失败，保留本机草稿', 'Cloud save failed; local draft kept'));
      });
    }, 500);
    return () => clearTimeout(timer);
  }, [g, remote, remoteState, kind]);
  useEffect(() => {
    if (!remote || !runResult?.assets.length) { setRunThumbs({}); return; }
    let alive = true; const urls: string[] = [];
    (async () => {
      for (const asset of runResult.assets.slice(0, 8)) {
        try {
          const blob = await downloadAssetBlob(remote, asset.id);
          if (!alive) return;
          const url = URL.createObjectURL(blob); urls.push(url);
          setRunThumbs(prev => ({...prev, [asset.id]: url}));
        } catch { /* preview is optional; the asset id remains visible */ }
      }
    })();
    return () => { alive = false; urls.forEach(url => URL.revokeObjectURL(url)); };
  }, [remote?.projectId, remote?.token, remote?.branchId, runResult?.id]);

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
    const params = defaultWidgetParams(d);
    const n: CfNode = {id: uid(), t: d.name, x: Math.round(menu.wx / 10) * 10, y: Math.round(menu.wy / 10) * 10,
      title: nodeLabel(d, 'zh-CN'), ...(params ? {params} : {})};
    setG(x => ({...x, nodes: [...x.nodes, n]})); setSel(n.id); setMenu(null); setMsg('');
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

  const setWidgetParam = (name: string, value: WidgetPrimitive) => {
    if (!sel) return;
    setG(x => ({...x, nodes: x.nodes.map(n => n.id === sel
      ? {...n, params: {...(n.params ?? {}), [name]: value}} : n)}));
  };
  const widgetValue = (node: CfNode, widget: WidgetDef): WidgetPrimitive => {
    const value = node.params?.[widget.name];
    if (widget.kind === 'BOOLEAN') return typeof value === 'boolean' ? value : widgetDefault(widget);
    if (widget.kind === 'INT' || widget.kind === 'FLOAT') return typeof value === 'number' ? value : widgetDefault(widget);
    return typeof value === 'string' ? value : widgetDefault(widget);
  };
  const commitNumber = (widget: WidgetDef, raw: string) => {
    if (!raw.trim()) return;
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    if (widget.kind === 'INT' && !Number.isSafeInteger(value)) return;
    if (widget.min != null && value < widget.min) return;
    if (widget.max != null && value > widget.max) return;
    setWidgetParam(widget.name, value);
  };

  // [HERMIA-FE-20261031 DUALCANVAS-COMFY RUN] Quote → explicit confirmation → local ComfyUI run.
  // No automatic retry, no cloud provider, and no execution when the draft is not saved/ready.
  const beginRun = async () => {
    if (!remote || runPhase === 'saving' || runPhase === 'running') return;
    setRunPhase('saving'); setRunMessage(L('正在保存草稿…', 'Saving draft…'));
    setRunQuote(null); setRunResult(null);
    try {
      const saved = await saveRemoteComfyGraph(kind, remote, remoteVersion.current, graphRef.current);
      if (!saved.ok) {
        setRunPhase('error');
        setRunMessage(L(`草稿版本冲突（当前 v${saved.currentVersion}），请刷新后再运行。`,
          `Draft version conflict (current v${saved.currentVersion}); refresh before running.`));
        return;
      }
      remoteVersion.current = saved.version;
      const quote = await preflightLowerCanvasRun(remote, kind, saved.version);
      setRunQuote(quote); setRunPhase('quoted'); setRunMessage('');
    } catch {
      setRunPhase('error');
      setRunMessage(L('无法预检运行：本地 ComfyUI/provider 不可用，或草稿不合法。',
        'Run preflight failed: local ComfyUI/provider unavailable or draft invalid.'));
    }
  };
  const confirmRun = async () => {
    if (!remote || !runQuote) return;
    setRunPhase('running'); setRunMessage(L('本地 ComfyUI 正在执行…', 'Running on local ComfyUI…'));
    try {
      let result = await dispatchLowerCanvasRun(remote, kind, runQuote);
      for (let attempt = 0; attempt < 60 && result.status === 'RUNNING'; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
        result = await fetchLowerCanvasRun(remote, kind, result.id);
      }
      setRunResult(result);
      setRunPhase(result.status === 'COMPLETED' ? 'done' : 'error');
      setRunMessage(result.status === 'COMPLETED'
        ? L(`运行完成，写入 ${result.assets.length} 个资产`, `Run completed; ${result.assets.length} assets written`)
        : L(`运行失败：${result.error?.code ?? 'UNKNOWN'}`, `Run failed: ${result.error?.code ?? 'UNKNOWN'}`));
    } catch {
      setRunPhase('error');
      setRunMessage(L('运行请求失败，未自动重试。', 'Run request failed; no automatic retry.'));
    }
  };
  const closeRun = () => { setRunPhase('idle'); setRunQuote(null); setRunResult(null); setRunMessage(''); };

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
      {selNode && selDef && (selDef.inputs.length || selDef.widgets.length) ? (
        <div className="cfy-insp" data-comfy-inspector aria-label={L('节点检查器', 'Node inspector')} role="group">
          <b>{nodeLabel(selDef, locale)}</b>
          {selDef.widgets.length ? (
            <div className="cfy-params" data-comfy-params aria-label={L('节点参数', 'Node parameters')} role="group">
              <b>{L('参数', 'Parameters')} <small>{L(`· ${selDef.widgets.length} 个`, `· ${selDef.widgets.length}`)}</small></b>
              {selDef.widgets.map(widget => {
                const value = widgetValue(selNode, widget);
                return <label key={widget.name}><span>{widget.name} <small>{widget.kind}</small></span>
                  {widget.kind === 'BOOLEAN' ? <input type="checkbox" data-widget-name={widget.name}
                    checked={value === true} onChange={e => setWidgetParam(widget.name, e.target.checked)} />
                    : widget.kind === 'COMBO' && widget.choices?.length ? <select data-widget-name={widget.name}
                        value={String(value)} onChange={e => setWidgetParam(widget.name, e.target.value)}>
                        {(widget.choices.includes(String(value)) ? widget.choices : [String(value), ...widget.choices]).slice(0, 256)
                          .map(choice => <option key={choice} value={choice}>{choice}</option>)}
                      </select>
                    : widget.kind === 'STRING' ? (widget.multiline
                      ? <textarea data-widget-name={widget.name} value={String(value)} onChange={e => setWidgetParam(widget.name, e.target.value)} />
                      : <input type="text" data-widget-name={widget.name} value={String(value)} onChange={e => setWidgetParam(widget.name, e.target.value)} />)
                    : <input type="number" data-widget-name={widget.name} value={String(value)}
                        min={widget.min} max={widget.max} step={widget.kind === 'INT' ? 1 : widget.step ?? 'any'}
                        onChange={e => commitNumber(widget, e.target.value)} />}
                </label>;
              })}
              <small className="cfy-insp__note">{L('仅草稿参数，不会执行', 'Draft parameters only; never runs')}</small>
            </div>) : null}
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
      {remote ? <div className="cfy-runbar">
        <button type="button" className="nv-btn cfy-runbtn" data-comfy-run
          disabled={remoteState !== 'ready' || runPhase === 'saving' || runPhase === 'running'}
          title={L('仅本地 ComfyUI，需确认报价', 'Local ComfyUI only; quote confirmation required')}
          onClick={beginRun}>{L('运行…', 'Run…')}</button>
        {runMessage ? <span className="cfy-runmsg" role="status" data-comfy-run-status>{runMessage}</span> : null}
      </div> : null}
      {runPhase === 'quoted' && runQuote ? <div className="cfy-runpanel" data-comfy-run-quote role="dialog"
        aria-label={L('运行报价', 'Run quote')}>
        <b>{L('运行报价', 'Run quote')}</b>
        <p>{L(`本地 ComfyUI · ${runQuote.node_count} 节点 · ${runQuote.edge_count} 连线`,
          `Local ComfyUI · ${runQuote.node_count} nodes · ${runQuote.edge_count} links`)}</p>
        <p>{L(`费用：0 ${runQuote.price.currency}（本地） · 请在 5 分钟内确认`,
          `Price: 0 ${runQuote.price.currency} (local) · confirm within 5 minutes`)}</p>
        <div className="cfy-runpanel__actions">
          <button type="button" data-run-confirm onClick={confirmRun}>{L('确认运行', 'Confirm run')}</button>
          <button type="button" data-run-cancel onClick={closeRun}>{L('取消', 'Cancel')}</button>
        </div>
      </div> : null}
      {(runPhase === 'done' || runPhase === 'error') ? <div className="cfy-runpanel" data-comfy-run-result
        data-run-status={runResult?.status ?? 'ERROR'} role="status">
        <b>{runPhase === 'done' ? L('运行完成', 'Run completed') : L('运行未完成', 'Run not completed')}</b>
        <p>{runMessage}</p>
        {runResult?.assets.length ? <div className="cfy-runassets" data-run-assets>
          {runResult.assets.slice(0, 8).map(asset => <div key={asset.id} className="cfy-runasset" data-run-asset={asset.id}>
            {runThumbs[asset.id] ? <img data-run-thumb src={runThumbs[asset.id]} alt={asset.filename || asset.id} /> : <span className="cfy-runasset__pending" aria-hidden="true" />}
            <small>{asset.filename || asset.id}</small>
            {onAdoptAsset ? <button type="button" data-run-adopt onClick={() => onAdoptAsset(asset)}>{L('接入上画布', 'Adopt to upper')}</button> : null}
          </div>)}
        </div> : null}
        <div className="cfy-runpanel__actions"><button type="button" onClick={closeRun}>{L('关闭', 'Close')}</button></div>
      </div> : null}
      <div className="rcv-zoom"><button type="button" aria-label={L('缩小画布', 'Zoom out')} onClick={() => zoom(1 / 1.15)}>－</button><span>{Math.round(vp.k * 100)}%</span>
        <button type="button" aria-label={L('放大画布', 'Zoom in')} onClick={() => zoom(1.15)}>＋</button></div>
      <div className="rcv-status" role="status" data-comfy-status data-comfy-remote={remoteState}>{msg || remoteNote || L(`节点 ${g.nodes.length} · 连线 ${g.edges.length} · 不会执行`, `${g.nodes.length} nodes · ${g.edges.length} links · never runs`)}</div>
    </div>
  );
}
