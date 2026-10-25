/* [HERMIA-FE-20261022 R6] 资产模块按原型 assetsWSHTML 重写：模块头 + .mw-split（左 类型/集合 · 中 资产网格 · 右 血缘/版本摘要 或 下一步）。
   真实接口：/api/novels/{nid}/assets（库/上传）· /assets/{id}/references（使用处）· /asset-trash + restore（回收站，1a63d6f7）· DELETE /assets/{id}。
   送到模块沿用 W-UX-12（显式确认后切模块；送剪辑走媒体池手递）。拖出＝引用，不复制。没有数据时不编血缘、不显示假「已校验」。 */
import { AUDIO_HISTORY_TEXT } from '../../workspace/media/audioHistoryText';
import {useEffect, useMemo, useRef, useState} from 'react';
import {api, type Asset, type AssetReferences} from '../../api';
import {rbError} from '../rebuildApi';
import {NovelOrient, NovelModTabs} from '../novel/NovelOrient';
import '../novel/novelRebuild.css';
import '../image/imageRebuild.css';
import './assetsRebuild.css';
import { t as i18nT } from '../../i18n'; // [HERMIA-FE-20261025 MERGE-FEC i18n]

export type AssetsView = 'lib' | 'refs' | 'import' | 'trash';
export type AssetsSendTarget = 'IMAGE' | 'VIDEO' | 'AUDIO' | 'EDIT';
type Filter = 'all' | '图像' | '音频' | '视频' | '其他';
const VIEW_LABEL: Record<AssetsView, string> = {lib: '资产库', refs: '引用关系', import: '导入', trash: '回收站'};
const SEND_LABEL: Record<AssetsSendTarget, string> = {IMAGE: '图片', VIDEO: '视频', AUDIO: '声音', EDIT: '剪辑媒体池'};
const COLLECTION_LABEL: Record<string, string> = {chapters: '小说章节', screenplays: '剧本', characters: '角色', scenes: '场景', visual_references: '图片参考', image_jobs: '图片', storyboards: '分镜', motion_tasks: '视频'};

export function assetKind(a: Pick<Asset, 'kind' | 'media_type'>): Exclude<Filter, 'all'> {
  const k = `${a.kind || ''} ${a.media_type || ''}`.toLowerCase();
  if (/image/.test(k)) return '图像'; if (/video/.test(k)) return '视频'; if (/audio/.test(k)) return '音频'; return '其他';
}
export function integrityLabel(v?: string) {
  const s = (v || '').toLowerCase();
  if (!s) return '未核实';
  if (/^(ok|verified|valid|checksum[_ ]ok|match(ed)?)$/.test(s)) return '已校验';
  if (/partial/.test(s)) return '部分';
  return '未核实';
}
const originLabel = (o?: string) => !o ? '未声明' : /upload|import|local/i.test(o) ? '本地导入' : /image|generat/i.test(o) ? '模块生成' : /video|motion/i.test(o) ? '视频送入' : /audio|speech/i.test(o) ? '声音回写' : '其他来源';
const sizeLabel = (n?: number) => !n ? '—' : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
const KIND_IC: Record<string, string> = {图像: '▣', 音频: '♪', 视频: '▶', 其他: '·'};

export function AssetsRebuild({novelId, shellMode = 'basic', onSelectAsset, onSendToModule}: {
  novelId: string; shellMode?: 'basic' | 'pro'; onSelectAsset?: (a: Asset | undefined) => void; onSendToModule?: (m: AssetsSendTarget) => void;
}) {
  const [view, setView] = useState<AssetsView>('lib');
  // [HERMIA-FE-20261022 U4] 普通：网格 + 导入 + 送到模块；专业另有 引用关系 / 血缘与版本 / 回收站。专业→普通回落资产库，选中不丢。
  const isPro = shellMode === 'pro';
  useEffect(() => { if (!isPro && (view === 'refs' || view === 'trash')) setView('lib'); }, [isPro, view]);
  const [filter, setFilter] = useState<Filter>('all');
  const [items, setItems] = useState<Asset[] | null>(null);
  const [err, setErr] = useState('');
  const [trash, setTrash] = useState<Asset[] | null>(null);
  const [tick, setTick] = useState(0);
  const [selId, setSelId] = useState<string | null>(null);
  const [refs, setRefs] = useState<AssetReferences | null | 'err'>(null);
  const [send, setSend] = useState<AssetsSendTarget | 'pick' | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let live = true; setErr('');
    api.assets(novelId).then(d => live && setItems(Array.isArray(d) ? d : [])).catch(e => { if (live) { setItems([]); setErr(rbError(e)); } });
    api.assetTrash(novelId).then(d => live && setTrash(d.items || [])).catch(() => live && setTrash(null));
    return () => { live = false; };
  }, [novelId, tick]);
  const list = useMemo(() => (items || []).filter(a => filter === 'all' || assetKind(a) === filter), [items, filter]);
  const cur = (items || []).find(a => a.id === selId) ?? null;
  useEffect(() => { onSelectAsset?.(cur ?? undefined); }, [cur?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!cur) { setRefs(null); return; }
    let live = true; setRefs(null);
    api.assetReferences(novelId, cur.id).then(r => live && setRefs(r)).catch(() => live && setRefs('err'));
    return () => { live = false; };
  }, [novelId, cur?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const counts = useMemo(() => { const c: Record<string, number> = {all: (items || []).length}; (items || []).forEach(a => { const k = assetKind(a); c[k] = (c[k] || 0) + 1; }); return c; }, [items]);
  const usedIn = refs && refs !== 'err' ? [...new Set(refs.items.map(i => COLLECTION_LABEL[i.collection] || '其他位置'))] : [];

  async function upload(file: File) {
    setBusy(true); setNote('');
    try {
      const bytes = new Uint8Array(await file.arrayBuffer()); let bin = '';
      for (let o = 0; o < bytes.length; o += 0x8000) bin += String.fromCharCode(...bytes.subarray(o, o + 0x8000));
      const kind = file.type.startsWith('image/') ? 'image' : file.type.startsWith('video/') ? 'video' : file.type.startsWith('audio/') ? 'audio' : 'file';
      const saved = await api.uploadAsset(novelId, {filename: file.name, media_type: file.type || undefined, kind, content_base64: btoa(bin)});
      setNote(i18nT('rb.ast.imported', { name: saved.filename })); setSelId(saved.id); setView('lib'); setTick(x => x + 1);
    } catch (e) { setNote(i18nT('rb.ast.importFailed', { msg: rbError(e) })) /* [HERMIA-FE-20261025 VERA-097 P3] */; } finally { setBusy(false); }
  }
  async function remove(a: Asset) {
    if (!window.confirm(`把「${a.filename}」移到回收站？被引用的地方会失去这个资产。`)) return;
    try { await api.deleteAsset(a.id, novelId); setSelId(null); setNote(i18nT('rb.ast.deleted', { name: a.filename })) /* [HERMIA-FE-20261025 VERA-097 P3] */; setTick(x => x + 1); } catch (e) { setNote(i18nT('rb.ast.deleteFailed', { msg: rbError(e) })) /* [HERMIA-FE-20261025 VERA-097 P3] */; }
  }
  async function restore(a: Asset) {
    try { await api.restoreAsset(novelId, a.id); setNote(i18nT('rb.ast.restored', { name: a.filename })) /* [HERMIA-FE-20261025 VERA-097 P3] */; setTick(x => x + 1); } catch (e) { setNote(i18nT('rb.ast.restoreFailed', { msg: rbError(e) })) /* [HERMIA-FE-20261025 VERA-097 P3] */; }
  }
  const pickFile = () => fileRef.current?.click();
  const loaded = items !== null;

  const head = (
    <div className="mw-head" role="toolbar" aria-label="资产子入口">
      <h2>资产 · {view === 'lib' ? '浏览器' : VIEW_LABEL[view]}</h2>
      <span className="ref-badge">拖入＝引用 · 不复制</span>
      <span className="nv-spacer" />
      {view !== 'lib' ? <button type="button" className="nv-btn" onClick={() => setView('lib')}>回资产库</button> : null}
      {isPro ? <button type="button" className="nv-btn" aria-pressed={view === 'refs'} onClick={() => setView('refs')}>引用关系</button> : null}
      <button type="button" className="nv-btn nv-btn--primary" data-ast-primary="import" disabled={busy} onClick={() => setView('import')}>导入…</button>
    </div>
  );

  const left = (
    <div className="mw-left">
      <div className="mw-lh">类型 / 集合</div>
      <div className="mw-tree" role="listbox" aria-label="资产类型">
        {([['all', '全部资产'], ['图像', '图像'], ['音频', '音频'], ['视频', '视频'], ['其他', '文档 / 其他']] as [Filter, string][]).map(([f, l]) =>
          <button key={f} type="button" role="option" data-astf={f} aria-selected={view === 'lib' && filter === f} onClick={() => { setFilter(f); setView('lib'); }}>
            <span className="ic">{f === 'all' ? '◫' : KIND_IC[f]}</span><span>{l}{loaded ? <span className="sub">{counts[f] || 0} 个</span> : null}</span></button>)}
        {isPro ? <button type="button" role="option" data-astf="trash" aria-selected={view === 'trash'} onClick={() => setView('trash')}>
          <span className="ic">⌫</span><span>回收站{trash ? <span className="sub">{trash.length} 个</span> : null}</span></button> : null}
      </div>
      <div className="mw-lh">标签</div>
      <p className="mw-muted">资产还没有标签。</p>
    </div>
  );

  const thumb = (a: Asset, h?: number) => assetKind(a) === '图像'
    ? <div className="th" style={h ? {height: h} : undefined}><img alt="" loading="lazy" src={api.assetDownloadUrl(a.id, novelId)} onError={e => { e.currentTarget.style.display = 'none'; }} /></div>
    : <div className="th th--kind" style={h ? {height: h} : undefined} data-kind={assetKind(a)}><span>{KIND_IC[assetKind(a)]}</span></div>;

  const grid = (
    <div className="mw-hero" aria-label="资产浏览器">
      <div className="ast-filters" role="toolbar" aria-label="资产工具条">
        {(['all', '图像', '音频', '视频'] as Filter[]).map(f => <button key={f} type="button" data-astf={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === 'all' ? '全部' : f}</button>)}
        <span className="nv-spacer" />
        <small className="mw-muted">{cur ? `已选「${cur.filename}」` : '没有选中'}</small>
      </div>
      {/* [HERMIA-FE-20261025 DUI P0-3] one state at a time: error (with retry) replaces the empty-library copy; raw detail only in data-* */}
      <div className="ast-grid" id="astGrid">
        {err ? <div className="ws-honest-empty ast-empty ast-err" role="alert" data-error-detail={err}><h4>{i18nT('rb.ast.loadFailed')}</h4>
            <button type="button" className="nv-btn" onClick={() => { setItems(null); setTick(t => t + 1); }}>重试</button></div>
          : !loaded ? <p className="mw-muted">读取中…</p>
          : (items || []).length === 0 ? <div className="ws-honest-empty ast-empty" role="status" data-honest-kind="empty_library" data-honest-workspace="ASSETS">
            <h4>库里还没有资产</h4><p>这里会收好你在各模块生成和导入的东西。先导入一个文件试试。</p>
            <button type="button" className="nv-btn nv-btn--primary" onClick={() => setView('import')}>导入…</button></div>
          : list.length === 0 ? <div className="ws-honest-empty ast-empty" role="status" data-honest-kind="empty_filter"><h4>这个类型下还没有资产。</h4>
            <button type="button" className="nv-btn" onClick={() => setFilter('all')}>查看全部</button></div>
          : list.map(a => <button key={a.id} type="button" className="ast-tile" aria-selected={cur?.id === a.id} draggable title="拖到其它模块＝引用，不复制"
              onDragStart={e => { e.dataTransfer.setData('text/plain', a.filename); e.dataTransfer.setData('application/x-poemseed-asset-ref', a.id); e.dataTransfer.effectAllowed = 'link'; }}
              onClick={() => setSelId(s => s === a.id ? null : a.id)}>
              {thumb(a)}<div className="meta"><b>{a.filename}</b><span>{assetKind(a)} · {a.version ? `v${a.version}` : '版本未记录'} · {sizeLabel(a.size)}</span></div></button>)}
      </div>
      {loaded && !err && (items || []).length ? <div className="ast-foot">共 {(items || []).length} 个资产 · 存储占用以服务端为准</div> : null}
    </div>
  );

  const right = cur ? (
    <div className="mw-right" aria-label="血缘与版本摘要"><div className="mw-rh">{isPro ? '血缘 / 版本摘要' : '资产信息'}</div><div className="mw-rb">
      {thumb(cur, 88)}
      <dl className="ast-lineage-facts">
        <div><dt>文件</dt><dd title={cur.filename}>{cur.filename}</dd></div>
        {isPro ? <><div><dt>版本</dt><dd>{cur.version ?? cur.provenance?.version ? `v${cur.version ?? cur.provenance?.version}` : '未记录'}</dd></div>
        <div><dt>来源</dt><dd>{originLabel(cur.provenance?.origin)}</dd></div>
        <div><dt>完整性</dt><dd>{integrityLabel(cur.provenance?.integrity)}</dd></div>
        <div><dt>使用处</dt><dd data-ast-used="true">{refs === null ? '读取中…' : refs === 'err' ? i18nT('rb.ast.refsShortFailed') : usedIn.length ? usedIn.join(' · ') : '还没有被引用'}</dd></div></> : <div><dt>类型</dt><dd>{assetKind(cur)} · {sizeLabel(cur.size)}</dd></div>}
      </dl>
      {isPro ? <div className="sec" data-pro-only="lineage"><h4>血缘摘要</h4>
        <div className="lineage">{(cur.relationships || []).length ? (cur.relationships || []).slice(0, 4).map((r: any, i) => <div key={i} className="ln">→ {r?.target?.label || r?.label || '关联对象'}</div>)
          : <div className="ln">没有记录过来源或去向。</div>}</div>
        <button type="button" className="nv-btn" style={{width: '100%', marginTop: 6}} onClick={() => setView('refs')}>打开完整血缘</button></div> : null}
      <div className="mw-cta">
        <button type="button" className="nv-btn nv-btn--primary" id="astSend" style={{width: '100%'}} onClick={() => setSend('pick')}>送到模块…</button>
        <button type="button" className="nv-btn" onClick={() => setSend('IMAGE')}>在图片中打开</button>
        <button type="button" className="nv-btn" onClick={() => setSend('EDIT')}>送到剪辑媒体池</button>
        <button type="button" className="nv-btn nv-btn--danger" onClick={() => void remove(cur)}>移到回收站</button>
      </div>
    </div></div>
  ) : (
    <div className="mw-right"><div className="mw-rh">下一步</div><div className="mw-rb">
      <div className="ws-honest-empty" role="status" data-honest-kind="empty_selection" data-honest-workspace="ASSETS">
        <h4>尚未选中内容</h4><p>点一个资产看它从哪来、被用在哪。</p>
        <button type="button" className="nv-btn nv-btn--primary" onClick={() => setView('import')}>导入…</button>
        <button type="button" className="nv-btn" onClick={() => { setFilter('图像'); setView('lib'); }}>只看图像</button>
      </div></div></div>
  );

  const refsView = (
    <>
      <div className="mw-left"><div className="mw-lh">焦点资产</div><div className="mw-tree" role="listbox" aria-label="焦点资产">
        {(items || []).length === 0 ? <p className="mw-muted">还没有资产</p> : (items || []).map(a => <button key={a.id} type="button" role="option" aria-selected={cur?.id === a.id} onClick={() => setSelId(a.id)}>
          <span className="ic">⎘</span><span>{a.filename}<span className="sub">{assetKind(a)}</span></span></button>)}</div></div>
      <div className="mw-hero"><div className="hero-tools"><b>血缘 / 使用处</b></div>
        <div className="hero-stage ast-refs-stage">
          {!cur ? <div className="img-empty"><h3>先选一个资产</h3><p>在左边点一个资产，看它被哪些地方引用。</p></div> :
            <div className="sec ast-refs-card"><h4>{cur.filename}</h4>
              <div className="lineage">
                <div className="ln">← <b>来源</b> · {originLabel(cur.provenance?.origin)}</div>
                {refs === null ? <div className="ln">读取中…</div> : refs === 'err' ? <div className="ln">{i18nT('rb.ast.refsFailed')}</div>
                  : refs.items.length === 0 ? <div className="ln">还没有地方引用它。</div>
                  : refs.items.map((r, i) => <div key={i} className="ln">→ <b>{COLLECTION_LABEL[r.collection] || '其他位置'}</b> · 第 {r.version} 版</div>)}
              </div>
              <p className="nv-hint">引用不是复制：改了源文件，引用它的地方都会看到变化。删除前会先确认。</p></div>}
        </div></div>
      <div className="mw-right"><div className="mw-rh">资产检视</div><div className="mw-rb">
        {cur ? <><dl className="kv"><dt>类型</dt><dd>{assetKind(cur)}</dd><dt>引用数</dt><dd>{refs && refs !== 'err' ? `${refs.total} 处` : '—'}</dd><dt>版本</dt><dd>{cur.version ? `v${cur.version}` : '未记录'}</dd></dl>
          <button type="button" className="nv-btn nv-btn--primary" style={{width: '100%'}} onClick={() => setView('lib')}>在库中定位</button>
          <button type="button" className="nv-btn" style={{width: '100%', marginTop: 6}} onClick={() => setSend('pick')}>送到模块…</button></>
          : <p className="mw-muted">没有选中资产。</p>}
      </div></div>
    </>
  );

  const importView = (
    <>
      <div className="mw-left"><div className="mw-lh">来源</div><div className="mw-tree">
        <button type="button" aria-selected="true"><span className="ic">⤴</span>本地文件</button>
        <button type="button" disabled title="从图片页「存为资产」"><span className="ic">·</span>从图片回写</button>
        <button type="button" disabled title="从声音页「在资产中查看」"><span className="ic">·</span>从声音批次回写</button></div></div>
      <div className="mw-hero"><div className="hero-tools"><b>导入</b><span className="ref-badge">导入后可在各模块引用</span></div>
        <div className="hero-stage"><div className="sec" style={{maxWidth: 420, width: '100%'}}><h4>选择本地文件…</h4>
          <button type="button" className="nv-btn nv-btn--primary" id="astImportBtn" disabled={busy} onClick={pickFile}>{busy ? '导入中…' : '选择文件…'}</button>
          <p className="nv-hint">导入不会自动开始任何付费任务。大文件和去重还没做。</p></div></div></div>
      <div className="mw-right"><div className="mw-rh">下一步</div><div className="mw-rb mw-cta">
        <button type="button" className="nv-btn nv-btn--primary" id="astImportBtn2" disabled={busy} onClick={pickFile}>选择本地文件…</button>
        <button type="button" className="nv-btn" onClick={() => setView('lib')}>去筛选已有库</button></div></div>
    </>
  );

  const trashView = (
    <>
      {left}
      <div className="mw-hero"><div className="hero-tools"><b>回收站</b><span className="nv-spacer" /><small className="mw-muted">删掉的资产先放这里，可以恢复</small></div>
        <div className="ast-grid">
          {trash === null ? <p className="mw-muted">回收站暂时读不到。</p> : trash.length === 0 ? <div className="ws-honest-empty ast-empty" role="status"><h4>回收站是空的</h4></div>
            : trash.map(a => <div key={a.id} className="ast-tile is-trash">{thumb(a)}<div className="meta"><b>{a.filename}</b><span>{assetKind(a)}</span>
              <button type="button" className="nv-btn" onClick={() => void restore(a)} title={AUDIO_HISTORY_TEXT.assetRestoreHint}>{AUDIO_HISTORY_TEXT.assetRestore}</button></div></div>)}
        </div></div>
      <div className="mw-right"><div className="mw-rh">说明</div><div className="mw-rb"><p className="nv-hint">{i18nT('fc.aud.restoreNote')}{AUDIO_HISTORY_TEXT.assetRestoreHint}</p></div></div>
    </>
  );

  const target = send && send !== 'pick' ? send : null;
  const confirm = send ? (
    <div className="img-confirm" role="dialog" aria-label="送到模块确认" data-ast-send-dialog="true">
      {send === 'pick' ? <><strong>把「{cur?.filename || '资产'}」送到哪里？</strong><p>送过去的是引用，不会复制文件。</p>
        <div className="nv-row">{(Object.keys(SEND_LABEL) as AssetsSendTarget[]).map(t => <button key={t} type="button" className="nv-btn" data-ast-send-target={t} onClick={() => setSend(t)}>{SEND_LABEL[t]}</button>)}
          <button type="button" className="nv-btn" onClick={() => setSend(null)}>取消</button></div></>
        : <><strong>送到{SEND_LABEL[target!]}？</strong><p>{target === 'EDIT' ? '会切到剪辑，这个资产作为媒体池素材引用，不会自动摆上时间线。' : `会切到${SEND_LABEL[target!]}页，按引用使用这个资产，不复制文件。`}</p>
          <div className="nv-row"><button type="button" className="nv-btn nv-btn--primary" data-ast-send-confirm="true" onClick={() => { const t = target!; setSend(null); onSendToModule?.(t); }}>确认送去</button>
            <button type="button" className="nv-btn" onClick={() => setSend(null)}>取消</button></div></>}
    </div>
  ) : null;

  return (
    <div className="ast-ws" data-shell-mode={shellMode} data-ast-view={view} data-assets-hero="browser" data-drag-semantics="reference" aria-label="资产工作区">
      <NovelOrient storageKey="studio-assets-orient-dismissed" what="这部作品的图片、视频、声音和文档" can="导入、筛选、看来源和使用处、送到其它模块" effect="送出去的是引用，不复制文件" />
      <NovelModTabs tabs={((isPro ? ['lib', 'refs', 'import'] : ['lib', 'import']) as AssetsView[]).map(id => ({id, label: VIEW_LABEL[id], selected: view === id || (id === 'lib' && view === 'trash'), onClick: () => setView(id)}))} />
      {head}
      <div className="mw-split">{view === 'lib' ? <>{left}{grid}{right}</> : view === 'refs' ? refsView : view === 'import' ? importView : trashView}</div>
      {note ? <p className="ast-note" role="status">{note}</p> : null}
      <input ref={fileRef} type="file" hidden aria-label="选择要导入的文件" onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) void upload(f); }} />
      {confirm}
    </div>
  );
}
