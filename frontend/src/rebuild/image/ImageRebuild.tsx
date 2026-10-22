/* [HERMIA-FE-20261022 R2] 图片模块按原型 imageWSHTML 重写：模块头 + 三栏 .mw-split（左素材/队列 · 中预览 · 右生成/视觉上下文）
   + 折叠「专业 · 创作画布」+ 漫画子视图 + 图片画布视图。数据全部来自真实接口：
   /api/novels/{nid}/image-generations · image-jobs · visual-references · /api/asset-providers。
   没有接口支撑的（漫画分格/气泡、逐格生成）只做本地草稿并写「状态待核实」，不显示已就绪。 */
import {useEffect, useMemo, useRef, useState} from 'react';
import {api, type VisualReference} from '../../api';
import {Drawer} from '../primitives';
import {ImageGenerationPanel} from '../../novel/ImageGenerationPanel';
import {VisualContextPanel} from '../../novel/VisualContextPanel';
import {VisionAnalysisPanel} from '../../novel/VisionAnalysisPanel';
import {MultimodalDirectorWorkspace} from '../../novel/MultimodalDirectorWorkspace';
import {RebuildCanvas} from '../canvas/RebuildCanvas';
import {ComicView} from '../comic/ComicView';
import {DualCanvas} from '../canvas/DualCanvas';
import {safeImagePreviewUri} from '../../novel/ImageInfiniteCanvas';
import type {ImageInspection} from '../../novel/ImageTaskInspector';
import {NovelOrient, NovelModTabs} from '../novel/NovelOrient';
import '../novel/novelRebuild.css';
import './imageRebuild.css';

export type ImageView = 'browse' | 'gen' | 'canvas' | 'comic' | 'dual'; // [HERMIA-FE-20261022 U2] + 双画布
type Provider = {provider_id: string; display_name?: string; configured: boolean; registered: boolean; reachable?: boolean};
type Item = {id: string; name: string; sub: string; uri?: string; kind: 'gen' | 'ref'};
type Job = {id: string; status?: string; prompt?: string};

const VIEW_LABEL: Record<ImageView, string> = {browse: '浏览', canvas: '图片画布', gen: '生成', comic: '漫画制作', dual: '双画布'};
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
  // [HERMIA-FE-20261022 U3] 双画布 / 专业工具只在专业模式；普通模式停在双画布时回到默认「浏览」
  const isPro = shellMode === 'pro';
  // [HERMIA-FE-20261022 U4] 普通：浏览/生成/漫画 + 单画布；专业另有 双画布、多图约束、JSON 导入导出、画面分析。批量生成：后端无批量出图能力，入口隐藏（不做假按钮）。
  useEffect(() => { if (!isPro && view === 'dual') onViewChange('browse'); }, [isPro, view, onViewChange]);
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
      {isPro ? <button type="button" className="nv-btn" aria-pressed={view === 'dual'} data-open-dual="true" onClick={() => onViewChange('dual')}>双画布</button> : null}
      <button type="button" className="nv-btn" aria-pressed={view === 'gen'} onClick={() => onViewChange('gen')}>生成</button>
      <button type="button" className="nv-btn" aria-pressed={view === 'comic'} data-open-comic="true" data-image-sub="comic" onClick={() => onViewChange('comic')}>漫画制作</button>
    </div>
  );
  const chrome = (
    <>
      <NovelOrient storageKey="studio-image-orient-dismissed" what="这部作品的参考图、角色定妆和关键帧" can="写一句描述生成候选，或放参考图约束一致性" effect="生成会调用你在 AI 主控里接好的生图模型，派发前会再确认" />
      <NovelModTabs tabs={((isPro ? ['browse', 'canvas', 'dual', 'gen', 'comic'] : ['browse', 'canvas', 'gen', 'comic']) as ImageView[]).map(id => ({id, label: VIEW_LABEL[id], selected: view === id, onClick: () => onViewChange(id)}))} />
    </>
  );

  if (view === 'canvas') return (
    <div className="img-ws" data-img-view="canvas" aria-label="图片工作区">
      {chrome}
      <div className="mw-head" role="toolbar" aria-label="图片子入口"><h2>图片画布</h2>{/* [HERMIA-FE-20261022 U3b] 去掉「专业」小标：画布普通/专业都有，小标两种模式都不准确 */}<span className="nv-spacer" />
        <button type="button" className="nv-btn" onClick={() => onViewChange('browse')}>回到预览</button>
        <button type="button" className="nv-btn" onClick={() => onViewChange('comic')}>漫画制作</button></div>
      {/* [HERMIA-FE-20261022 U1] 主画布换成原型同款黑色无限画布（右键加节点）；旧的多图约束 / 导入导出收进下方「专业工具」 */}
      <div className="img-canvaswrap img-canvaswrap--rcv" data-surface="canvas"><RebuildCanvas kind="image" scope={novelId} label="图片画布" /></div>
      {isPro ? <details className="img-canvas-pro" data-pro-only="true"><summary>专业工具：多图约束 · 导入/导出 JSON · 快照</summary><div className="img-canvas-pro__body"><MultimodalDirectorWorkspace mode="image" novelId={novelId} /></div></details> : null}
    </div>
  );

  if (view === 'dual' && isPro) return (
    <div className="img-ws" data-img-view="dual" aria-label="图片工作区">
      {chrome}
      <div className="mw-head" role="toolbar" aria-label="图片子入口"><h2>双画布</h2><span className="nv-badge nv-badge--part">本机草稿</span><span className="nv-spacer" />
        <button type="button" className="nv-btn" onClick={() => onViewChange('canvas')}>只看图片画布</button>
        <button type="button" className="nv-btn" onClick={() => onViewChange('browse')}>回到预览</button></div>
      <div className="img-canvaswrap img-canvaswrap--rcv" data-surface="canvas"><DualCanvas scope={novelId} /></div>
    </div>
  );

  if (view === 'comic') return <ComicView chrome={chrome} onBack={() => onViewChange('browse')} onGen={() => onViewChange('gen')} />;

  return (
    <div className="img-ws" data-img-view={view === 'dual' ? 'browse' : view} aria-label="图片工作区">
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
      {/* [HERMIA-FE-20261022 U3b] 「专业 · 创作画布」折叠只在专业模式渲染，普通模式彻底不显示 */}
      {isPro ? <details className="img-pro" open={proOpen} onToggle={e => setProOpen((e.target as HTMLDetailsElement).open)}>
        <summary>专业 · 创作画布</summary>
        <div className="img-pro-body">参考与生成节点放在黑色无限画布上，只属于图片，不进小说正文。
          <div><button type="button" className="nv-btn" onClick={() => onViewChange('canvas')}>打开图片画布</button></div></div>
      </details> : null}

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

// [HERMIA-FE-20261022 U2] 漫画视图移到 ../comic/ComicView（分格模板 + 气泡样式）；保留 U1 的 comicCellSpans 供旧测试
/** 分格网格：两列；格数为奇数时最后一格跨整行，偶数时全部两两填满（修 4 格右下角缺块）。 */
export function comicCellSpans(count: number): boolean[] { return Array.from({length: count}, (_, i) => count % 2 === 1 && i === count - 1 && count > 1); }
