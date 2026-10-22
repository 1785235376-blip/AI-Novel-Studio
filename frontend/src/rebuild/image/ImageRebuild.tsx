/* [HERMIA-FE-20261022 R2] 图片模块按原型 imageWSHTML 重写：模块头 + 三栏 .mw-split（左素材/队列 · 中预览 · 右生成/视觉上下文）
   + 折叠「专业 · 创作画布」+ 漫画子视图 + 图片画布视图。数据全部来自真实接口：
   /api/novels/{nid}/image-generations · image-jobs · visual-references · /api/asset-providers。
   没有接口支撑的（漫画分格/气泡、逐格生成）只做本地草稿并写「状态待核实」，不显示已就绪。 */
import {useEffect, useMemo, useState} from 'react';
import {api, type VisualReference} from '../../api';
import {Drawer} from '../primitives';
import {ImageGenerationPanel} from '../../novel/ImageGenerationPanel';
import {VisualContextPanel} from '../../novel/VisualContextPanel';
import {VisionAnalysisPanel} from '../../novel/VisionAnalysisPanel';
import {MultimodalDirectorWorkspace} from '../../novel/MultimodalDirectorWorkspace';
import {safeImagePreviewUri} from '../../novel/ImageInfiniteCanvas';
import type {ImageInspection} from '../../novel/ImageTaskInspector';
import {NovelOrient, NovelModTabs} from '../novel/NovelOrient';
import '../novel/novelRebuild.css';
import './imageRebuild.css';

export type ImageView = 'browse' | 'gen' | 'canvas' | 'comic';
type Provider = {provider_id: string; display_name?: string; configured: boolean; registered: boolean; reachable?: boolean};
type Item = {id: string; name: string; sub: string; uri?: string; kind: 'gen' | 'ref'};
type Job = {id: string; status?: string; prompt?: string};

const VIEW_LABEL: Record<ImageView, string> = {browse: '浏览', canvas: '图片画布', gen: '生成', comic: '漫画制作'};
const JOB_STATUS: Record<string, string> = {QUEUED: '排队', RUNNING: '进行中', SUCCEEDED: '已完成', FAILED: '失败', CANCELLED: '已取消'};

export function useImageData(novelId: string) {
  const [gens, setGens] = useState<any[] | null>(null);
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [refs, setRefs] = useState<VisualReference[] | null>(null);
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    api.imageGenerations(novelId).then(d => live && setGens(d.items || [])).catch(() => live && setGens([]));
    api.imageJobs(novelId).then(d => live && setJobs(d.items || [])).catch(() => live && setJobs([]));
    api.visualReferences(novelId).then(d => live && setRefs(d.items || [])).catch(() => live && setRefs([]));
    api.assetProviders().then(d => live && setProviders((d.items || []) as Provider[])).catch(() => live && setProviders([]));
    return () => { live = false; };
  }, [novelId, tick]);
  return {gens, jobs, refs, providers, reload: () => setTick(t => t + 1)};
}

export function ImageRebuild({novelId, view, onViewChange, shellMode = 'basic', onInspect, onSendToVideo, onOpenAssets, onOpenControl}: {
  novelId: string; view: ImageView; onViewChange: (v: ImageView) => void; shellMode?: 'basic' | 'pro';
  onInspect?: (i?: ImageInspection) => void; onSendToVideo?: () => void; onOpenAssets?: () => void; onOpenControl?: () => void;
}) {
  const {gens, jobs, refs, providers, reload} = useImageData(novelId);
  const items: Item[] = useMemo(() => [
    ...(refs || []).map(r => ({id: `ref:${r.id}`, name: r.notes?.trim() || `${r.entity_type} 参考`, sub: r.approval_status === 'APPROVED' ? '参考 · 已确认' : '参考 · 草稿', kind: 'ref' as const})),
    ...(gens || []).map((g, i) => ({id: `gen:${g.id ?? i}`, name: String(g.filename || g.prompt || `生成结果 ${i + 1}`).slice(0, 24), sub: '生成结果', uri: g.asset_uri || g.uri, kind: 'gen' as const})),
  ], [gens, refs]);
  const [sel, setSel] = useState<string>();
  const cur = items.find(i => i.id === sel) ?? items[0];
  const [refOverlay, setRefOverlay] = useState(true);
  const [prompt, setPrompt] = useState('');
  const [refSel, setRefSel] = useState('');
  const [drawer, setDrawer] = useState<null | 'gen' | 'refs'>(null);
  const [sendConfirm, setSendConfirm] = useState(false);
  const [proOpen, setProOpen] = useState(shellMode === 'pro');
  useEffect(() => setProOpen(shellMode === 'pro'), [shellMode]);
  const loaded = gens !== null && refs !== null;
  const ready = (providers || []).filter(p => p.configured && p.registered && p.reachable !== false);
  const canGen = ready.length > 0;
  const previewUri = cur?.uri ? safeImagePreviewUri(cur.uri) : undefined;

  const head = (title: string) => (
    <div className="mw-head" role="toolbar" aria-label="图片子入口">
      <h2>{title}</h2>
      <span className="nv-badge nv-badge--off" data-image-provider-state>{providers === null ? '生图模型 · 检查中' : canGen ? `生图模型 · 已接通 ${ready.length}` : '生图模型 · 未接通'}</span>
      <span className="nv-spacer" />
      <button type="button" className="nv-btn" aria-pressed={view === 'browse'} data-image-sub="studio" onClick={() => onViewChange('browse')}>图片工作台</button>
      <button type="button" className="nv-btn" aria-pressed={view === 'gen'} onClick={() => onViewChange('gen')}>生成</button>
      <button type="button" className="nv-btn" aria-pressed={view === 'comic'} data-open-comic="true" data-image-sub="comic" onClick={() => onViewChange('comic')}>漫画制作</button>
    </div>
  );
  const chrome = (
    <>
      <NovelOrient storageKey="studio-image-orient-dismissed" what="这部作品的参考图、角色定妆和关键帧" can="写一句描述生成候选，或放参考图约束一致性" effect="生成会调用你在 AI 主控里接好的生图模型，派发前会再确认" />
      <NovelModTabs tabs={(['browse', 'canvas', 'gen', 'comic'] as ImageView[]).map(id => ({id, label: VIEW_LABEL[id], selected: view === id, onClick: () => onViewChange(id)}))} />
    </>
  );

  if (view === 'canvas') return (
    <div className="img-ws" data-img-view="canvas" aria-label="图片工作区">
      {chrome}
      <div className="mw-head" role="toolbar" aria-label="图片子入口"><h2>图片画布</h2><span className="nv-badge nv-badge--off">专业</span><span className="nv-spacer" />
        <button type="button" className="nv-btn" onClick={() => onViewChange('browse')}>回到预览</button>
        <button type="button" className="nv-btn" onClick={() => onViewChange('comic')}>漫画制作</button></div>
      <div className="img-canvaswrap" data-surface="canvas"><MultimodalDirectorWorkspace mode="image" novelId={novelId} /></div>
    </div>
  );

  if (view === 'comic') return <ComicView chrome={chrome} onBack={() => onViewChange('browse')} onGen={() => onViewChange('gen')} />;

  return (
    <div className="img-ws" data-img-view={view} aria-label="图片工作区">
      {chrome}
      {head(view === 'gen' ? '图片 · 生成' : '图片 · 浏览 / 预览')}
      <div className="mw-split">
        <nav className="mw-left" aria-label="视觉素材">
          <div className="mw-lh">视觉素材 / 参考</div>
          <div className="mw-tree">
            {!loaded ? <p className="mw-muted">读取中…</p> : items.length === 0 ? <p className="mw-muted">还没有参考图或生成结果</p> :
              items.map(it => <button key={it.id} type="button" aria-selected={cur?.id === it.id} onClick={() => setSel(it.id)}><span className="ic">{it.kind === 'ref' ? '▣' : '▭'}</span><span>{it.name}<span className="sub">{it.sub}</span></span></button>)}
            <button type="button" onClick={() => onViewChange('comic')} data-open-comic="true"><span className="ic">▦</span><span>漫画制作<span className="sub">图片 › 子入口</span></span></button>
          </div>
          <div className="mw-lh">生成队列</div>
          <div className="mw-tree">
            {jobs === null ? <p className="mw-muted">读取中…</p> : jobs.length === 0 ? <p className="mw-muted">没有排队中的任务</p> :
              jobs.slice(0, 8).map(j => <button key={j.id} type="button"><span className="ic">·</span><span>{(j.prompt || `任务 ${j.id}`).slice(0, 14)}<span className="sub">{JOB_STATUS[j.status || ''] || '状态待核实'}</span></span></button>)}
          </div>
        </nav>

        <section className="mw-hero" aria-label="图像预览" data-image-hero="preview">
          <div className="hero-tools">
            <b>{view === 'gen' ? '生成检视' : '图像预览'}</b>
            <span className="nv-spacer" />
            <button type="button" className="nv-btn" aria-pressed={refOverlay} id="imgToggleRef" disabled={!cur} onClick={() => setRefOverlay(v => !v)}>参考叠看 {refOverlay ? '开' : '关'}</button>
          </div>
          <div className="hero-stage">
            {!loaded ? <p className="mw-muted">读取中…</p> : !cur ? (
              <div className="img-empty" data-image-empty="true">
                <h3>还没有图片</h3>
                <p>先放一张参考图，或者直接写一句描述开始生成。</p>
                <div className="nv-row"><button type="button" className="nv-btn" onClick={() => document.getElementById('imgPrompt')?.focus()}>新建生成</button><button type="button" className="nv-btn" onClick={onOpenAssets}>从资产导入</button></div>
              </div>
            ) : (
              <div className="img-preview" aria-label="当前图预览">
                {previewUri ? <img src={previewUri} alt={cur.name} referrerPolicy="no-referrer" /> : null}
                {refOverlay && refSel ? <span className="ref-chip">参考叠看 · {refSel}</span> : null}
                <span className="cap">{cur.name} · {cur.sub}{previewUri ? '' : ' · 暂无可预览文件'}</span>
              </div>
            )}
          </div>
          <div className="img-hero-actions" aria-label="预览下一步">
            <button type="button" className="nv-btn" id="imgCtaGen" onClick={() => { onViewChange('gen'); setTimeout(() => document.getElementById('imgPrompt')?.focus(), 0); }}>新建生成</button>
            <button type="button" className="nv-btn" id="imgCtaRef" onClick={() => setDrawer('refs')}>加参考</button>
            <button type="button" className="nv-btn" data-open-comic="true" onClick={() => onViewChange('comic')}>打开漫画</button>
          </div>
          {items.length > 0 ? <div className="img-thumb-row" role="list" aria-label="缩略条">
            {items.map(it => <button key={it.id} type="button" role="listitem" aria-selected={cur?.id === it.id} onClick={() => setSel(it.id)}><div className={`th th--${it.kind}`}>{it.uri && safeImagePreviewUri(it.uri) ? <img src={safeImagePreviewUri(it.uri)} alt="" /> : null}</div><div className="nm">{it.name}</div></button>)}
          </div> : null}
        </section>

        <aside className="mw-right" aria-label="图片生成">
          <div className="mw-rh">{view === 'gen' || !cur ? '图片生成' : `检视 · ${cur.name}`}</div>
          <div className="mw-rb">
            <div className="sec"><h4>生成</h4>
              <label className="f" htmlFor="imgPrompt">提示词</label>
              <textarea className="inp" id="imgPrompt" rows={3} value={prompt} placeholder="例如：雾港码头，冷灰蓝，一盏煤油灯" onChange={e => setPrompt(e.target.value)} />
              <label className="f" htmlFor="imgRefSel">参考约束</label>
              <select className="inp" id="imgRefSel" value={refSel} onChange={e => setRefSel(e.target.value)}>
                <option value="">无参考</option>
                {(refs || []).map(r => <option key={r.id} value={r.notes || r.id}>{r.notes || r.id}</option>)}
              </select>
              <button type="button" className="nv-btn nv-btn--primary img-gen-btn" id="imgGen" disabled={!canGen} onClick={() => setDrawer('gen')}>生成候选…</button>
              {providers !== null && !canGen ? <p className="nv-hint">需要先在 AI 主控里接好生图模型。<button type="button" className="nv-link" onClick={onOpenControl}>打开主控</button></p> : <p className="nv-hint">派发前会再确认模型和费用，不会自动扣费。</p>}
            </div>
            <div className="sec"><h4>视觉上下文</h4>
              <dl className="kv"><dt>主参考</dt><dd>{refSel || '无'}</dd><dt>参考数</dt><dd>{refs ? refs.length : '…'}</dd><dt>角色一致性</dt><dd><span className="nv-badge nv-badge--off">状态待核实</span></dd></dl>
              {/* [HERMIA-FE-20261022 R3] 去掉原型没有的「管理参考…」，参考入口统一走中区「加参考」 */}
            </div>
            {shellMode === 'pro' ? <details className="sec"><summary><h4>画面分析</h4></summary><VisionAnalysisPanel novelId={novelId} /></details> : null}
            <div className="mw-cta">
              <button type="button" className="nv-btn" onClick={() => onViewChange('comic')}>打开漫画制作</button>
              {onSendToVideo ? <button type="button" className="nv-btn" data-send-video="true" data-image-cta="send-video" onClick={() => setSendConfirm(true)}>送去视频当参考…</button> : null}
              <button type="button" className="nv-btn" onClick={onOpenAssets}>在资产中查看引用</button>
            </div>
          </div>
        </aside>
      </div>
      <details className="img-pro" open={proOpen} onToggle={e => setProOpen((e.target as HTMLDetailsElement).open)}>
        <summary>专业 · 创作画布</summary>
        <div className="img-pro-body">参考与生成节点放在黑色无限画布上，只属于图片，不进小说正文。
          <div><button type="button" className="nv-btn" onClick={() => onViewChange('canvas')}>打开图片画布</button></div></div>
      </details>

      {drawer === 'gen' ? <Drawer title="生成候选" onClose={() => { setDrawer(null); reload(); }}><ImageGenerationPanel novelId={novelId} initialPrompt={prompt || undefined} onInspect={onInspect} /></Drawer> : null}
      {drawer === 'refs' ? <Drawer title="参考与视觉上下文" onClose={() => { setDrawer(null); reload(); }}><VisualContextPanel novelId={novelId} /></Drawer> : null}
      {sendConfirm && onSendToVideo ? (
        <div className="img-confirm" role="dialog" aria-label="送去视频当参考确认" data-send-video-dialog="true">
          <strong>{cur ? `把「${cur.name}」送去视频当参考？` : '切到视频工作区？'}</strong>
          <p>{cur ? '会切到视频工作区，这张图作为参考候选，不会自动写进任何镜头。' : '当前没有选中的图片，只会切换到视频工作区，不带任何参考。'}</p>
          <div className="nv-row"><button type="button" className="nv-btn nv-btn--primary" data-send-video-confirm="true" onClick={() => { setSendConfirm(false); onSendToVideo(); }}>确认送去</button><button type="button" className="nv-btn" data-send-video-cancel="true" onClick={() => setSendConfirm(false)}>取消</button></div>
        </div>
      ) : null}
    </div>
  );
}

type Cell = {id: string; bubbles: string[]};
function ComicView({chrome, onBack, onGen}: {chrome: React.ReactNode; onBack: () => void; onGen: () => void}) {
  const [pages, setPages] = useState<{id: string; label: string; cells: Cell[]}[]>([{id: 'p1', label: '第 1 页', cells: [{id: 'c1', bubbles: []}, {id: 'c2', bubbles: []}, {id: 'c3', bubbles: []}]}]);
  const [pageId, setPageId] = useState('p1');
  const [cellId, setCellId] = useState('c1');
  const page = pages.find(p => p.id === pageId) ?? pages[0]!;
  const mut = (fn: (cells: Cell[]) => Cell[]) => setPages(ps => ps.map(p => p.id === page.id ? {...p, cells: fn(p.cells)} : p));
  return (
    <div className="img-ws" data-img-view="comic" aria-label="图片 › 漫画制作">
      {chrome}
      <div className="mw-head" role="toolbar" aria-label="图片子入口"><h2>图片 › 漫画制作</h2><span className="nv-badge nv-badge--part">本地草稿</span><span className="nv-spacer" />
        <button type="button" className="nv-btn" data-image-sub="studio" onClick={onBack}>回预览</button>
        <button type="button" className="nv-btn" onClick={onGen}>生图</button></div>
      <div className="mw-split">
        <nav className="mw-left" aria-label="漫画页">
          <div className="mw-lh">漫画页 / 分格</div>
          <div className="mw-tree">
            {pages.map(p => <button key={p.id} type="button" aria-selected={p.id === page.id} onClick={() => setPageId(p.id)}><span className="ic">▦</span><span>{p.label}<span className="sub">{p.cells.length} 格 · 本地草稿</span></span></button>)}
            <button type="button" className="nv-rail__new" onClick={() => { const id = `p${pages.length + 1}`; setPages(ps => [...ps, {id, label: `第 ${ps.length + 1} 页`, cells: [{id: 'c1', bubbles: []}]}]); setPageId(id); }}>＋ 新页</button>
          </div>
          <p className="mw-muted">分格和气泡现在只存在本页面，刷新会丢失；保存到作品的接口状态待核实。</p>
        </nav>
        <section className="mw-hero" aria-label="漫画页预览">
          <div className="hero-tools"><b>当前页 · {page.label}</b><span className="nv-spacer" />
            <button type="button" className="nv-btn" id="comicAddPanel" onClick={() => mut(cs => [...cs, {id: `c${cs.length + 1}`, bubbles: []}])}>＋ 分格</button>
            <button type="button" className="nv-btn" id="comicBubble" onClick={() => mut(cs => cs.map(c => c.id === cellId ? {...c, bubbles: [...c.bubbles, '双击改写台词']} : c))}>＋ 气泡</button></div>
          <div className="hero-stage">
            <div className="comic-page">
              {page.cells.map((c, i) => <button key={c.id} type="button" className={`comic-cell${i === 2 ? ' c3' : ''}`} aria-pressed={c.id === cellId} onClick={() => setCellId(c.id)}>
                {c.bubbles.map((b, j) => <span key={j} className="bub" style={{top: 8 + j * 28, left: 8}}>{b}</span>)}
                <span className="cell-n">{i + 1}</span></button>)}
            </div>
          </div>
          <div className="comic-strip" role="tablist" aria-label="漫画页条">{pages.map(p => <button key={p.id} type="button" role="tab" aria-selected={p.id === page.id} onClick={() => setPageId(p.id)}>{p.label}</button>)}</div>
        </section>
        <aside className="mw-right" aria-label="下一步 · 漫画">
          <div className="mw-rh">下一步 · 漫画</div>
          <div className="mw-rb">
            <div className="sec"><h4>逐格生成</h4>
              <p className="nv-hint">选中第 {Math.max(1, page.cells.findIndex(c => c.id === cellId) + 1)} 格。</p>
              <button type="button" className="nv-btn nv-btn--primary img-gen-btn" id="comicGenCell" disabled>生成当前格候选…</button>
              <p className="nv-hint">逐格生成还没接通，先在「生成」里出图再放进分格。</p>
            </div>
            <div className="sec"><h4>书册 / 导出</h4>
              <button type="button" className="nv-btn img-gen-btn" id="comicExport" disabled>导出页预览…</button>
              <p className="nv-hint">导出状态待核实。</p>
              <button type="button" className="nv-btn img-gen-btn" onClick={onBack}>用预览检视原图</button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
