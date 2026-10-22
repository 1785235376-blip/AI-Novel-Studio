// [HERMIA-FE-20261022 U2] 漫画制作：每页可选分格模板（不同形状/斜切/嵌入/出血），六种气泡 + 尾巴方向 + 缩放 + 删除 + 竖排。
// 仍是本地草稿：不发写请求；U5 起暂存 sessionStorage，关标签页即丢（页面写明）。保存接口已列入给 dot 的需求。
import {useEffect, useRef, useState} from 'react';
import {COMIC_TEMPLATES, templateById, remapCells, BUBBLE_KINDS, TAIL_DIRS, DEFAULT_TEXT, hasTail, type Bubble, type BubbleKind, type ComicTemplate} from './comicTemplates';
import './comic.css';

type Page = {id: string; label: string; tpl: string; cells: Bubble[][]};
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
/** [HERMIA-FE-20261022 U2] 按气泡实际尺寸夹住位置：x ≤ (格宽-泡宽)/格宽·100，y 同理，避免宽气泡被格子裁掉文字。 */
export function bubbleBounds(cellW: number, cellH: number, bubW: number, bubH: number) {
  return {maxX: Math.max(0, (cellW - bubW) / (cellW || 1) * 100), maxY: Math.max(0, (cellH - bubH) / (cellH || 1) * 100)};
}
/** [HERMIA-FE-20261022 U5] 按“实际可见外框”夹紧：取气泡框与文字（含旋转后外框，getBoundingClientRect 已含 transform）的并集，
 *  再按其相对布局原点（left/top 百分比）的外伸量算出 x/y 的上下限。旋转的拟声字、文字比框宽的旁白都不会被格子裁掉。 */
export function visibleBounds(cell: {left: number; top: number; width: number; height: number}, origin: {x: number; y: number}, vis: {left: number; top: number; right: number; bottom: number}) {
  const W = cell.width || 1, H = cell.height || 1;
  const ox = cell.left + origin.x / 100 * W, oy = cell.top + origin.y / 100 * H;
  const lo = Math.max(0, ox - vis.left), ro = vis.right - ox, to = Math.max(0, oy - vis.top), bo = vis.bottom - oy;
  const minX = lo / W * 100, minY = to / H * 100;
  return {minX, minY, maxX: Math.max(minX, (W - ro) / W * 100), maxY: Math.max(minY, (H - bo) / H * 100)};
}
function measure(el: HTMLElement, b: {x: number; y: number}) {
  const c = (el.closest('.comic-cell') as HTMLElement | null)?.getBoundingClientRect(); const r = el.getBoundingClientRect();
  const t = (el.querySelector('.bub-t') as HTMLElement | null)?.getBoundingClientRect();
  const vis = t && t.width ? {left: Math.min(r.left, t.left), top: Math.min(r.top, t.top), right: Math.max(r.right, t.right), bottom: Math.max(r.bottom, t.bottom)} : r;
  const cell = c ? {left: c.left, top: c.top, width: c.width || 1, height: c.height || 1} : {left: 0, top: 0, width: 1, height: 1};
  return {w: cell.width, h: cell.height, ...visibleBounds(cell, b, vis)};
}
const newPage = (n: number, tpl = 'big1small2'): Page => ({id: `p${n}`, label: `第 ${n} 页`, tpl, cells: templateById(tpl).panels.map(() => [])});

export function TemplateThumb({t}: {t: ComicTemplate}) {
  return <span className="cm-thumb" style={{gridTemplateColumns: t.cols, gridTemplateRows: t.rows}} aria-hidden="true">
    {t.panels.map((p, i) => <i key={i} className={p.cls ? `cm-p--${p.cls}` : undefined} style={{gridArea: p.area, clipPath: p.clip}} />)}</span>;
}

function ComicBubble({b, sel, onSel, onChange, onDelete}: {b: Bubble; sel: boolean; onSel: () => void; onChange: (p: Partial<Bubble>) => void; onDelete: () => void}) {
  const st = useRef<null | {mode: 'move' | 'size'; sx: number; sy: number; ox: number; oy: number; ow: number; w: number; h: number; minX: number; minY: number; maxX: number; maxY: number}>(null);
  const start = (mode: 'move' | 'size') => (e: React.PointerEvent<HTMLElement>) => {
    e.stopPropagation(); onSel();
    const el = (e.currentTarget.closest('.bub') as HTMLElement) || e.currentTarget; const m = measure(el, b);
    st.current = {mode, sx: e.clientX, sy: e.clientY, ox: b.x, oy: b.y, ow: b.w, w: m.w, h: m.h, minX: m.minX, minY: m.minY, maxX: m.maxX, maxY: m.maxY};
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* jsdom */ }
  };
  const move = (e: React.PointerEvent) => { const d = st.current; if (!d) return; const dx = (e.clientX - d.sx) / d.w * 100, dy = (e.clientY - d.sy) / d.h * 100;
    if (d.mode === 'move') onChange({x: clamp(d.ox + dx, d.minX, d.maxX), y: clamp(d.oy + dy, d.minY, d.maxY)}); else onChange({w: clamp(d.ow + dx, 14, Math.max(14, 100 - b.x))}); };
  return <span className={`bub bub--${b.kind}${hasTail(b.kind) && b.tail !== 'none' ? ` bub-tail--${b.tail}` : ''}${b.vertical ? ' bub--v' : ''}`}
    role="button" tabIndex={0} aria-pressed={sel} data-bubble-id={b.id} data-bubble-kind={b.kind}
    aria-label={`气泡（${BUBBLE_KINDS.find(k => k.id === b.kind)?.label}）：${b.text}。拖动移动，双击改写，Delete 删除`}
    style={{left: `${b.x}%`, top: `${b.y}%`, width: b.vertical ? undefined : `${b.w}%`}}
    onClick={e => { e.stopPropagation(); onSel(); }}
    onDoubleClick={e => { e.stopPropagation(); const t = window.prompt('改写台词', b.text); if (t != null && t.trim()) onChange({text: t.trim()}); }}
    onPointerDown={start('move')} onPointerMove={move} onPointerUp={() => { st.current = null; }}
    onKeyDown={e => { if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); onDelete(); return; }
      const k = ({ArrowLeft: [-2, 0], ArrowRight: [2, 0], ArrowUp: [0, -2], ArrowDown: [0, 2]} as Record<string, number[]>)[e.key];
      if (k) { e.preventDefault(); const m = measure(e.currentTarget, b); onChange({x: clamp(b.x + k[0]!, m.minX, m.maxX), y: clamp(b.y + k[1]!, m.minY, m.maxY)}); } }}>
    <span className="bub-t">{b.text}</span>
    {sel ? <span className="bub-size" role="presentation" title="拖动调整大小" onPointerDown={start('size')} onPointerMove={move} onPointerUp={() => { st.current = null; }} /> : null}
  </span>;
}

/** [HERMIA-FE-20261022 U5] 漫画草稿暂存到 sessionStorage（按作品），切模块再回来不丢；仍不发写请求、不进服务端。 */
export const comicDraftKey = (novelId?: string) => `hermia-comic-draft:${novelId || 'local'}`;
function loadDraft(novelId?: string): {pages: Page[]; pageId: string} | null {
  try { const d = JSON.parse(sessionStorage.getItem(comicDraftKey(novelId)) || 'null'); return d && Array.isArray(d.pages) && d.pages.length ? d : null; } catch { return null; }
}
export function ComicView({chrome, onBack, onGen, novelId}: {chrome: React.ReactNode; onBack: () => void; onGen: () => void; novelId?: string}) {
  const [pages, setPages] = useState<Page[]>(() => loadDraft(novelId)?.pages ?? [newPage(1)]);
  const [pageId, setPageId] = useState(() => loadDraft(novelId)?.pageId ?? 'p1');
  useEffect(() => { try { sessionStorage.setItem(comicDraftKey(novelId), JSON.stringify({pages, pageId})); } catch { /* 配额/隐私模式 */ } }, [novelId, pages, pageId]);
  const [cellIx, setCellIx] = useState(0);
  const [bubSel, setBubSel] = useState<string | null>(null);
  const [kind, setKind] = useState<BubbleKind>('speech');
  const page = pages.find(p => p.id === pageId) ?? pages[0]!;
  const tpl = templateById(page.tpl);
  const setPage = (fn: (p: Page) => Page) => setPages(ps => ps.map(p => p.id === page.id ? fn(p) : p));
  const setCells = (fn: (c: Bubble[][]) => Bubble[][]) => setPage(p => ({...p, cells: fn(p.cells)}));
  const patch = (id: string, d: Partial<Bubble>) => setCells(cs => cs.map(c => c.map(b => b.id === id ? {...b, ...d} : b)));
  const del = (id: string) => { setCells(cs => cs.map(c => c.filter(b => b.id !== id))); setBubSel(null); };
  const chooseTpl = (id: string) => { setPage(p => ({...p, tpl: id, cells: remapCells(p.cells, templateById(id).panels.length)})); setCellIx(0); };
  const addBubble = () => { const id = `b${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
    setCells(cs => cs.map((c, i) => i === cellIx ? [...c, {id, text: DEFAULT_TEXT[kind], x: tpl.panels[cellIx]?.clip ? 30 : 8, y: (tpl.panels[cellIx]?.clip ? 45 : 8) + (c.length % 3) * 16, w: kind === 'sfx' ? 30 : 48, kind, tail: kind === 'shout' ? 'br' : 'bl'}] : c)); setBubSel(id); };
  const sb = page.cells.flat().find(b => b.id === bubSel) || null;
  return (
    <div className="img-ws" data-img-view="comic" aria-label="图片 › 漫画制作">
      {chrome}
      <div className="mw-head" role="toolbar" aria-label="图片子入口"><h2>图片 › 漫画制作</h2><span className="nv-badge nv-badge--part">本地草稿</span><span className="nv-spacer" />
        <button type="button" className="nv-btn" data-image-sub="studio" onClick={onBack}>回预览</button>
        <button type="button" className="nv-btn" onClick={onGen}>生图</button></div>
      <div className="mw-split">
        <nav className="mw-left" aria-label="漫画页">
          <div className="mw-lh">漫画页</div>
          <div className="mw-tree">
            {pages.map(p => <button key={p.id} type="button" aria-selected={p.id === page.id} onClick={() => { setPageId(p.id); setCellIx(0); setBubSel(null); }}><span className="ic">▦</span><span>{p.label}<span className="sub">{templateById(p.tpl).label} · {p.cells.length} 格</span></span></button>)}
            <button type="button" className="nv-rail__new" onClick={() => { const n = pages.length + 1; setPages(ps => [...ps, newPage(n, page.tpl)]); setPageId(`p${n}`); setCellIx(0); }}>＋ 新页（沿用当前分格）</button>
          </div>
          <div className="mw-lh">分格模板 · 本页</div>
          <div className="cm-tpls" role="radiogroup" aria-label="分格模板">
            {COMIC_TEMPLATES.map(t => <button key={t.id} type="button" role="radio" aria-checked={t.id === page.tpl} data-tpl={t.id} title={t.hint} onClick={() => chooseTpl(t.id)}>
              <TemplateThumb t={t} /><span>{t.label}</span></button>)}
          </div>
          <p className="mw-muted">分格和气泡只暂存在本浏览器标签页（切模块不丢，关掉标签页就没了），没有保存到服务端；保存到作品的接口还没接通。换模板不会丢台词：格子变少时，多出的气泡并到最后一格。</p>
        </nav>
        <section className="mw-hero" aria-label="漫画页预览">
          <div className="hero-tools"><b>{page.label} · {tpl.label}</b><span className="cm-hint">{tpl.hint}</span><span className="nv-spacer" />
            <select className="nv-btn" aria-label="新气泡样式" value={kind} onChange={e => setKind(e.target.value as BubbleKind)}>{BUBBLE_KINDS.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}</select>
            <button type="button" className="nv-btn" id="comicBubble" onClick={addBubble}>＋ 气泡到第 {cellIx + 1} 格</button></div>
          <div className="hero-stage" onClick={() => setBubSel(null)}>
            <div className="comic-page" data-tpl={tpl.id} style={{gridTemplateColumns: tpl.cols, gridTemplateRows: tpl.rows}}>
              {tpl.panels.map((pd, i) => <div key={`${tpl.id}-${i}`} role="button" tabIndex={0} className={`comic-cell${pd.cls ? ` comic-cell--${pd.cls}` : ''}${pd.clip ? ' comic-cell--slant' : ''}`}
                style={{gridArea: pd.area, clipPath: pd.clip}} aria-pressed={i === cellIx} aria-label={`第 ${i + 1} 格`}
                onClick={e => { e.stopPropagation(); setCellIx(i); setBubSel(null); }} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setCellIx(i); }}>
                {(page.cells[i] ?? []).map(b => <ComicBubble key={b.id} b={b} sel={b.id === bubSel} onSel={() => { setBubSel(b.id); setCellIx(i); }} onChange={d => patch(b.id, d)} onDelete={() => del(b.id)} />)}
                <span className="cell-n">{i + 1}</span></div>)}
            </div>
          </div>
          <div className="comic-strip" role="tablist" aria-label="漫画页条">{pages.map(p => <button key={p.id} type="button" role="tab" aria-selected={p.id === page.id} onClick={() => setPageId(p.id)}><TemplateThumb t={templateById(p.tpl)} />{p.label}</button>)}</div>
        </section>
        <aside className="mw-right" aria-label="下一步 · 漫画">
          <div className="mw-rh">{sb ? '气泡' : '下一步 · 漫画'}</div>
          <div className="mw-rb">
            {sb ? <div className="sec" data-bubble-inspector="true"><h4>选中的气泡</h4>
              <label className="cm-f">台词<textarea aria-label="气泡台词" value={sb.text} rows={2} onChange={e => patch(sb.id, {text: e.target.value})} /></label>
              <div className="cm-f">样式<div className="cm-chips">{BUBBLE_KINDS.map(k => <button key={k.id} type="button" aria-pressed={sb.kind === k.id} onClick={() => patch(sb.id, {kind: k.id})}>{k.label}</button>)}</div></div>
              {hasTail(sb.kind) ? <div className="cm-f">尾巴方向<div className="cm-chips">{TAIL_DIRS.map(t => <button key={t.id} type="button" aria-pressed={sb.tail === t.id} data-tail={t.id} onClick={() => patch(sb.id, {tail: t.id})}>{t.label}</button>)}</div></div> : null}
              <label className="cm-f">宽度 {Math.round(sb.w)}%<input type="range" min={14} max={95} value={sb.w} aria-label="气泡宽度" onChange={e => patch(sb.id, {w: Math.min(+e.target.value, Math.max(14, 100 - sb.x))})} /></label>
              <label className="cm-chk"><input type="checkbox" checked={!!sb.vertical} onChange={e => patch(sb.id, {vertical: e.target.checked})} /> 竖排文字</label>
              <button type="button" className="nv-btn img-gen-btn" data-bubble-delete="true" onClick={() => del(sb.id)}>删除气泡</button>
              <p className="nv-hint">拖气泡移动，拖右下角小方块改大小；选中后按 Delete 也能删除。</p>
            </div> : <p className="nv-hint">点一个气泡可以改样式、尾巴方向、大小和竖排。</p>}
            <div className="sec"><h4>逐格生成</h4>
              <p className="nv-hint">选中第 {cellIx + 1} 格。</p>
              <button type="button" className="nv-btn nv-btn--primary img-gen-btn" id="comicGenCell" disabled>生成当前格候选…</button>
              <p className="nv-hint">逐格生成还没接通，先在「生成」里出图再放进分格。</p>
            </div>
            <div className="sec"><h4>书册 / 导出</h4>
              <button type="button" className="nv-btn img-gen-btn" id="comicExport" disabled>导出页预览…</button>
              <p className="nv-hint">导出还没接通。</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
