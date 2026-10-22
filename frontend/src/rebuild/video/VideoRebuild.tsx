/* [HERMIA-FE-20261022 R3] 视频模块按原型 videoStudioHTML 重写：模块头 + .vid-body（左 .vid-rail · 主区三层：
   ①镜头脚本卡条 ②黑色无限画布 ③内置导演台）。没有右栏，检视并入导演台层；「送去剪辑」仅模块头为主色。
   数据来自真实接口：/api/novels/{nid}/screenplays（镜头）· /api/video-providers（图生视频置灰原因）。
   没有导演建议接口数据时只写空态说明，不画假节点、不显示假「已就绪」。 */
import {useEffect, useMemo, useState} from 'react';
import {api} from '../../api';
import {Drawer} from '../primitives';
import {ScreenplayPanel} from '../../novel/ScreenplayPanel';
import {MultimodalDirectorWorkspace} from '../../novel/MultimodalDirectorWorkspace';
import {NovelOrient, NovelModTabs} from '../novel/NovelOrient';
import '../novel/novelRebuild.css';
import '../image/imageRebuild.css';
import './videoRebuild.css';

export type VideoView = 'studio' | 'script' | 'gen';
type Shot = {key: string; n: number; title: string; size: string; dialogue: string; status: string; hasFrame: boolean};
const VIEW_LABEL: Record<VideoView, string> = {studio: '视频工作室', script: '镜头脚本', gen: '图生视频'};
const STATUS: Record<string, string> = {APPROVED: '已确认', DRAFT: '草稿', PENDING: '待处理'};

export function shotsFromScreenplays(list: any[] | null): Shot[] {
  const out: Shot[] = [];
  for (const s of list || []) for (const x of (s?.shots || [])) {
    const n = out.length + 1;
    out.push({key: `${s.id}:${x.id ?? n}`, n, title: String(x.action || x.description || `镜头 ${n}`).slice(0, 18), size: x.shot_size || '景别未定',
      dialogue: String(x.dialogue || '').slice(0, 24), status: STATUS[s.shot_status] || '草稿', hasFrame: Boolean(x.keyframe_uri || x.keyframe || x.image_uri)});
  }
  return out;
}

export function VideoRebuild({novelId, shellMode = 'basic', onSendToEdit, onOpenControl}: {
  novelId: string; shellMode?: 'basic' | 'pro'; onSendToEdit?: () => void; onOpenControl?: () => void;
}) {
  const [view, setView] = useState<VideoView>('studio');
  const [plays, setPlays] = useState<any[] | null>(null);
  const [providers, setProviders] = useState<any[] | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    api.screenplays(novelId).then(d => live && setPlays(Array.isArray(d) ? d : [])).catch(() => live && setPlays([]));
    api.videoProviders().then(d => live && setProviders(d.items || [])).catch(() => live && setProviders([]));
    return () => { live = false; };
  }, [novelId, tick]);
  const shots = useMemo(() => shotsFromScreenplays(plays), [plays]);
  const [sel, setSel] = useState<string>();
  const cur = shots.find(s => s.key === sel) ?? shots[0];
  const [scriptOpen, setScriptOpen] = useState(true);
  const [dirOpen, setDirOpen] = useState(true); // [HERMIA-FE-20261022 R3] 原型默认展开导演台
  const [drawer, setDrawer] = useState<null | 'screenplay' | 'director'>(null);
  const [sendConfirm, setSendConfirm] = useState(false);
  const ready = (providers || []).filter(p => p.available && p.registered && p.reachable !== false);
  const loaded = plays !== null;
  const addShot = () => setDrawer('screenplay');
  const askSend = () => setSendConfirm(true);

  const emptyLine = '这一章还没有镜头。从剧本拆一版，或手动加第一个镜头。';
  const cls = ['vid-ws', scriptOpen ? '' : 'script-collapsed', dirOpen ? '' : 'director-collapsed'].filter(Boolean).join(' ');

  const head = (
    <div className="mw-head" role="toolbar" aria-label="视频子入口">
      <h2>{view === 'studio' ? '视频工作室' : view === 'script' ? '视频 › 分镜表' : '视频 › 图生视频'}</h2>
      <span className="nv-badge nv-badge--off">{plays === null ? '镜头 · 读取中' : `镜头 · ${shots.length}`}</span>
      <span className="nv-spacer" />
      {view === 'studio' ? <>
        <button type="button" className="nv-btn" id="vidToggleScript" aria-pressed={scriptOpen} onClick={() => setScriptOpen(o => !o)}>{scriptOpen ? '收起镜头脚本' : '镜头脚本'}</button>
        <button type="button" className="nv-btn" id="vidToggleDirector" aria-pressed={dirOpen} onClick={() => setDirOpen(o => !o)}>{dirOpen ? '收起导演台' : '导演台'}</button>
      </> : <button type="button" className="nv-btn" onClick={() => setView('studio')}>回视频工作室</button>}
      <button type="button" className="nv-btn nv-btn--primary" id="vidSendEdit" data-send-edit="true" onClick={askSend}>送去剪辑</button>
      <button type="button" className="nv-btn" aria-pressed={view === 'script'} onClick={() => setView('script')}>分镜表</button>
      <button type="button" className="nv-btn" aria-pressed={view === 'gen'} onClick={() => setView('gen')}>图生视频</button>
    </div>
  );

  const rail = (
    <nav className="vid-rail" aria-label="视频工作区导航">
      <div className="eyebrow">视频</div>
      <strong>三层工作区</strong>
      <ul><li>① 镜头脚本</li><li>② 无限画布</li><li>③ 内置导演台</li></ul>
      <button type="button" className="nv-btn" id="vidSendEditRail" onClick={askSend}>送去剪辑</button>
      <p className="hint">这里排镜头和画面关系；剪成片在剪辑页。</p>
      <div className="mw-lh vid-rail-lh">场景 / 镜头树</div>
      <div className="mw-tree">
        {!loaded ? <p className="mw-muted">读取中…</p> : shots.length === 0 ? <p className="mw-muted">还没有镜头</p> :
          shots.map(s => <button key={s.key} type="button" aria-selected={cur?.key === s.key} onClick={() => setSel(s.key)}><span className="ic">·</span><span>镜头 {s.n} {s.title}<span className="sub">{s.size} · {s.status}</span></span></button>)}
      </div>
      <div className="mw-lh vid-rail-lh">素材引用</div>
      <p className="mw-muted">从图片页「送去视频当参考」后会出现在这里。</p>
    </nav>
  );

  const confirm = sendConfirm ? (
    <div className="img-confirm" role="dialog" aria-label="送去剪辑确认" data-send-edit-dialog="true">
      <strong>{shots.length ? `把 ${shots.length} 个镜头送去剪辑？` : '切到剪辑页？'}</strong>
      <p>{shots.length ? '会切到剪辑，镜头作为媒体池素材引用，不会自动摆上时间线。' : '现在还没有镜头，只会切换到剪辑页，不带任何素材。'}</p>
      <div className="nv-row"><button type="button" className="nv-btn nv-btn--primary" data-send-edit-confirm="true" onClick={() => { setSendConfirm(false); onSendToEdit?.(); }}>确认送去</button><button type="button" className="nv-btn" onClick={() => setSendConfirm(false)}>取消</button></div>
    </div>
  ) : null;

  const drawers = <>
    {drawer === 'screenplay' ? <Drawer title="剧本与镜头" onClose={() => { setDrawer(null); setTick(t => t + 1); }}><ScreenplayPanel novelId={novelId} /></Drawer> : null}
    {drawer === 'director' ? <Drawer title="内置导演台" onClose={() => setDrawer(null)}><MultimodalDirectorWorkspace mode="video" novelId={novelId} /></Drawer> : null}
  </>;

  const chrome = <>
    <NovelOrient storageKey="studio-video-orient-dismissed" what="这一章的镜头、画面关系和导演建议" can="拆镜头、在画布上连参考、采用导演建议" effect="这里不剪成片；准备好后「送去剪辑」" />
    <NovelModTabs tabs={(['studio', 'script', 'gen'] as VideoView[]).map(id => ({id, label: VIEW_LABEL[id], selected: view === id, onClick: () => setView(id)}))} />
  </>;

  let main: React.ReactNode;
  if (view === 'script') main = (
    <div className="vid-main vid-sub">
      {shots.length === 0 ? <div className="img-empty"><h3>分镜表还是空的</h3><p>{emptyLine}</p><div className="nv-row"><button type="button" className="nv-btn nv-btn--primary" onClick={addShot}>＋ 镜头</button><button type="button" className="nv-btn" onClick={addShot}>从剧本拆镜头</button></div></div> :
        <table className="vid-table"><thead><tr><th>镜头</th><th>景别</th><th>内容</th><th>状态</th><th /></tr></thead><tbody>
          {shots.map(s => <tr key={s.key}><td>镜头 {s.n}</td><td>{s.size}</td><td>{s.title}{s.dialogue ? ` · ${s.dialogue}` : ''}</td><td>{s.status}</td>
            <td><button type="button" className="nv-btn" disabled={!s.hasFrame} onClick={() => { setSel(s.key); setView('studio'); }}>{s.hasFrame ? '在画布查看' : '缺少关键帧'}</button></td></tr>)}
        </tbody></table>}
      <div className="nv-row vid-sub-foot"><button type="button" className="nv-btn" onClick={addShot}>编辑剧本与镜头…</button></div>
    </div>
  );
  else if (view === 'gen') main = (
    <div className="vid-main vid-sub">
      <div className="img-empty"><h3>从关键帧生成片段</h3>
        <p>{providers === null ? '正在检查视频服务…' : ready.length ? `可用视频服务 ${ready.length} 个，派发前会再确认模型和费用。` : '需要先在 AI 主控里接好视频服务。'}</p>
        <div className="nv-row">
          <button type="button" className="nv-btn nv-btn--primary" id="vidGenGo" disabled={!ready.length || !cur?.hasFrame}>生成候选…</button>
          {!ready.length ? <button type="button" className="nv-btn" onClick={onOpenControl}>打开 AI 主控</button> : null}
        </div>
        {ready.length && !cur?.hasFrame ? <p className="nv-hint">当前镜头还没有关键帧。</p> : null}
      </div>
    </div>
  );
  else main = (
    <div className="vid-main">
      <section className="vid-layer vid-layer--script" aria-label="① 镜头脚本">
        <div className="vl-h"><span className="lab">① 镜头脚本</span><span className="nv-spacer" />{cur ? <span className="vl-meta">选中 镜头 {cur.n}</span> : null}</div>
        <div className="shot-row" role="list" aria-label="镜头卡条">
          {shots.length === 0 ? <p className="vl-note">{loaded ? emptyLine : '读取中…'}</p> : shots.map(s =>
            <button key={s.key} type="button" className="vid-shot" role="listitem" aria-selected={cur?.key === s.key} onClick={() => setSel(s.key)}>
              <span className="shot-num">S{s.n}</span><b>{s.title}</b><span className="meta">{s.size}{s.dialogue ? <><br />{s.dialogue}</> : null}<br /><span className="nv-badge nv-badge--off">{s.status}</span></span></button>)}
          <button type="button" className="nv-btn vid-add" id="addShot" onClick={addShot}>＋ 镜头</button>
          {shots.length === 0 && loaded ? <button type="button" className="nv-btn vid-add" onClick={addShot}>从剧本拆镜头</button> : null}
        </div>
      </section>
      <section className="vid-layer vid-layer--canvas" aria-label="② 无限画布">
        <div className="vl-h"><span className="lab">② 无限画布</span><span className="nv-spacer" /><span className="vl-meta">节点 · 素材引用 · 关系边</span></div>
        <div className="vid-canvas-host" id="vidCanvasHost" data-surface="canvas">
          {shots.length === 0 ? <p className="vid-canvas-empty">{loaded ? '还没有镜头，画布是空的。' : '读取中…'}</p> :
            <svg id="vidCv" role="application" aria-label="视频无限画布" viewBox={`0 0 ${Math.max(900, 40 + shots.length * 210)} 300`} preserveAspectRatio="xMinYMin meet">
              <defs><marker id="vidArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#9aa3b2" /></marker></defs>
              {shots.slice(1).map((s, i) => <path key={`e${s.key}`} className="vid-edge" d={`M${40 + i * 210 + 140},82 L${40 + (i + 1) * 210},82`} />)}
              {shots.map((s, i) => <g key={s.key} className="vid-node" data-sel={cur?.key === s.key} transform={`translate(${40 + i * 210},50)`} onClick={() => setSel(s.key)}>
                <rect width="140" height="64" rx="8" /><text className="title" x="12" y="24">镜头 {s.n}</text><text className="sub" x="12" y="44">{s.size} · {s.title.slice(0, 6)}</text></g>)}
            </svg>}
        </div>
      </section>
      <section className="vid-layer vid-layer--director" aria-label="③ 内置导演台">
        <div className="vl-h"><span className="lab">③ 内置导演台</span><span className="nv-spacer" />
          <button type="button" className="nv-btn" id="vidAdopt" disabled title="还没有可采用的导演建议">采用到镜头卡…</button>
          <button type="button" className="nv-btn" id="vidSendEditDir" onClick={askSend}>送去剪辑（交片）</button></div>
        <div className="dir-grid">
          <div className="sugg"><b>{cur ? `镜头 ${cur.n} · 导演建议` : '导演建议'}</b>
            <p>选一个镜头，导演会给出景别和运镜建议；采用前你会看到改动。</p>
            {cur ? <dl className="kv"><dt>当前景别</dt><dd>{cur.size}</dd><dt>状态</dt><dd>{cur.status}</dd></dl> : null}</div>
          <div className="note">采用只改镜头卡，不写剪辑轨、不生成成片。<button type="button" className="nv-link" onClick={() => setDrawer('director')}>打开完整导演台</button></div>
        </div>
        <div className="vid-director-entry"><strong>③ 内置导演台</strong><p>建议 → 确认采用，只属于视频工作区。</p>
          <button type="button" className="nv-btn" id="vidOpenDirector" onClick={() => setDirOpen(true)}>打开内置导演台</button></div>
      </section>
    </div>
  );

  return (
    <div className={cls} data-video-layers="script-canvas-director" data-vid-view={view} aria-label="视频工作区">
      {chrome}{head}
      <div className="vid-body">{rail}{main}</div>
      {confirm}{drawers}
    </div>
  );
}
