/* [HERMIA-FE-20261022 R5] 剪辑模块按原型 editTimelineHTML 重写：模块头 .nle-top + 上段（媒体池 · 双监视器 · 检视器）+ 下段整宽多轨时间线。
   数据：媒体池 = W-UX-14 会话手递（视频/声音/图片/资产「送去剪辑」）；导出 = 583610fd 的 /exports（ExportBody）。
   诚实（W-UX-09）：没有可写剪辑接口，时间线编排、入出点、静音/锁定只在本页本地，不保存；成片渲染（MP4）未接通，按钮置灰写原因。
   一页一主：模块头「导出成片…」。不改 EDIT 默认落地，不碰 N-UX-04。 */
import {useCallback, useEffect, useMemo, useState} from 'react';
import {WithQuery} from '../primitives';
import {ExportBody} from '../ExportMenu';
import {NovelOrient, NovelModTabs} from '../novel/NovelOrient'; // [HERMIA-FE-20261022 R6] 补原型 44px 指引行
import {EDIT_HANDOFF_SOURCE_LABEL, editHandoffsForNovel, type EditHandoffItem} from '../../ui/editHandoff';
import '../novel/novelRebuild.css';
import '../image/imageRebuild.css';
import './editRebuild.css';

export type EditView = 'tl' | 'media' | 'export';
type BinTab = 'video' | 'audio' | 'sub';
type TrackId = 'V1' | 'V2' | 'V3' | 'A1' | 'A2' | 'S1';
export type LocalClip = {key: string; track: TrackId; start: number; dur: number; name: string; kind: 'v' | 'a' | 's'};
const VIEW_LABEL: Record<EditView, string> = {tl: '多轨时间线', media: '媒体池', export: '导出成片'};
const FULL_TRACKS: TrackId[] = ['V1', 'V2', 'V3', 'A1', 'A2', 'S1'];
const EMPTY_TRACKS: TrackId[] = ['V1', 'A1', 'S1'];
export const fmtTc = (s: number) => { const m = Math.floor(s / 60), r = s - m * 60; return `${String(m).padStart(2, '0')}:${r.toFixed(2).padStart(5, '0')}`; };
export const binTabOf = (h: EditHandoffItem): BinTab => h.source === 'AUDIO' ? 'audio' : 'video';

export function placeClip(clips: LocalClip[], h: EditHandoffItem, dur = 5): LocalClip {
  const kind = binTabOf(h) === 'audio' ? 'a' : 'v';
  const track: TrackId = kind === 'a' ? 'A1' : 'V1';
  const end = clips.filter(c => c.track === track).reduce((m, c) => Math.max(m, c.start + c.dur), 0);
  return {key: `${h.id}-${clips.length}`, track, start: end, dur, kind, name: `${EDIT_HANDOFF_SOURCE_LABEL[h.source]} · ${h.label}`};
}

export function EditRebuild({novelId, shellMode = 'basic', onBackToVideo, handoffs: handoffsOverride}: {
  novelId: string; shellMode?: 'basic' | 'pro'; editable: false; onBackToVideo?: () => void; handoffs?: EditHandoffItem[];
}) {
  const [view, setView] = useState<EditView>('tl');
  // [HERMIA-FE-20261022 U4] 普通：预览 + 三条基础轨（V1/A1/字幕）；专业：完整 V1–V3/A1–A2 + 检视器参数 + 快捷键提示。仍只读本地编排（editable={false}）。
  const isPro = shellMode === 'pro';
  const handoffs = useMemo(() => handoffsOverride ?? editHandoffsForNovel(novelId), [handoffsOverride, novelId]);
  const [binTab, setBinTab] = useState<BinTab>(() => handoffs.length && handoffs.every(h => binTabOf(h) === 'audio') ? 'audio' : 'video');
  const [binOpen, setBinOpen] = useState(true);
  const [binSel, setBinSel] = useState<string | null>(null);
  const [clips, setClips] = useState<LocalClip[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [playhead, setPlayhead] = useState(0);
  const [mark, setMark] = useState<{in: number | null; out: number | null}>({in: null, out: null});
  const [snap, setSnap] = useState(true);
  const [zoom, setZoom] = useState(100);
  const [playing, setPlaying] = useState(false);
  const [tracks, setTracks] = useState<Record<string, {mute: boolean; lock: boolean}>>({});
  const duration = Math.max(20, clips.reduce((m, c) => Math.max(m, c.start + c.dur), 0));
  const cur = clips.find(c => c.key === sel) ?? null;
  const px = (zoom / 100) * 40;
  const rows = isPro && clips.length ? FULL_TRACKS : EMPTY_TRACKS;

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setPlayhead(p => { if (p + 0.1 >= duration) { setPlaying(false); return duration; } return Math.round((p + 0.1) * 100) / 100; }), 100);
    return () => clearInterval(id);
  }, [playing, duration]);

  const cut = useCallback(() => {
    if (!cur || playhead <= cur.start || playhead >= cur.start + cur.dur || tracks[cur.track]?.lock) return;
    const a = {...cur, dur: playhead - cur.start}, b = {...cur, key: `${cur.key}-b${clips.length}`, start: playhead, dur: cur.start + cur.dur - playhead};
    setClips(cs => cs.flatMap(c => c.key === cur.key ? [a, b] : [c]));
  }, [cur, playhead, tracks, clips.length]);
  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).closest('input,select,textarea')) return;
    const k = e.key.toLowerCase();
    if (k === ' ') { e.preventDefault(); setPlaying(p => !p); }
    else if (k === 'i') setMark(m => ({...m, in: playhead}));
    else if (k === 'o') setMark(m => ({...m, out: playhead}));
    else if (k === 'c' || k === 'b') cut();
  };
  const addToTimeline = (h: EditHandoffItem) => { const c = placeClip(clips, h); setClips(cs => [...cs, c]); setSel(c.key); setView('tl'); };
  const scrub = (e: React.MouseEvent<HTMLDivElement>) => { const r = e.currentTarget.getBoundingClientRect(); let t = Math.max(0, Math.min((e.clientX - r.left) / px, duration));
    if (snap) { const edges = clips.flatMap(c => [c.start, c.start + c.dur]); const near = edges.find(x => Math.abs(x - t) * px < 6); if (near != null) t = near; }
    setPlayhead(Math.round(t * 100) / 100); };
  const toggleTrack = (tid: string, f: 'mute' | 'lock') => setTracks(t => ({...t, [tid]: {...(t[tid] ?? {mute: false, lock: false}), [f]: !t[tid]?.[f]}}));

  const binItems = handoffs.filter(h => binTabOf(h) === binTab);
  const binEmpty = binTab === 'sub' ? '字幕轨还没接到这里。字幕请先在声音页准备好。' : '还没有可用素材。去视频或声音页把成品送过来，或从资产拖进来。';
  const grid = (big = false) => (
    <div className="bin-grid" role="listbox" aria-label="媒体池素材" style={big ? {gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))'} : undefined}>
      {binItems.length === 0 ? <p className="bin-empty" data-edit-handoff="empty">{binEmpty}</p> : binItems.map(h =>
        <button key={h.id} type="button" role="option" className="bin-item" aria-selected={binSel === h.id} data-handoff-source={h.source} data-handoff-source-strip="true"
          title="放到时间线＝引用，不复制" onClick={() => setBinSel(s => s === h.id ? null : h.id)} onDoubleClick={() => addToTimeline(h)}>
          <div className={`th ${binTabOf(h) === 'audio' ? 'aud' : ''}`} /><em className="ref-em">引用</em>
          <div className="nm">{h.label}<span className="src">来自{EDIT_HANDOFF_SOURCE_LABEL[h.source]}</span></div>
        </button>)}
    </div>
  );
  const picked = handoffs.find(h => h.id === binSel) ?? null;
  const bin = (
    <div className="nle-bin" id="nleBin" aria-label="剪辑媒体池" data-edit-handoff={handoffs.length ? 'received' : 'empty'}>
      <div className="bin-h"><span>媒体池 · 引用</span><button type="button" className="nv-btn" id="nleBinToggle" onClick={() => setBinOpen(false)}>收起</button></div>
      <div className="bin-tabs" role="tablist">
        {([['video', '视频'], ['audio', '音频'], ['sub', '字幕']] as [BinTab, string][]).map(([id, l]) =>
          <button key={id} type="button" role="tab" data-bintab={id} aria-selected={binTab === id} onClick={() => setBinTab(id)}>{l}</button>)}
      </div>
      {grid()}
      {picked ? <button type="button" className="nv-btn" style={{margin: '0 8px 8px'}} data-bin-place="true" onClick={() => addToTimeline(picked)}>放到时间线</button> : null}
    </div>
  );

  const insp = cur ? (
    <><div className="insp-h">片段检视</div><div className="insp-b">
      <dl className="kv"><dt>名称</dt><dd>{cur.name}</dd><dt>轨道</dt><dd>{cur.track === 'S1' ? '字幕' : cur.track}</dd>
        <dt>入点</dt><dd>{fmtTc(cur.start)}</dd><dt>出点</dt><dd>{fmtTc(cur.start + cur.dur)}</dd>
        {isPro ? <><dt>速度</dt><dd>100%</dd>{cur.kind === 'a' ? <><dt>音量</dt><dd>0 dB</dd></> : <><dt>透明度</dt><dd>100%</dd></>}</> : null}</dl>
      {isPro ? <p className="edr-note" data-w-ux="09" data-writable="false" data-pro-only="inspector-params">速度、透明度、音量暂时只能看，改动和保存的接口还待核实。</p> : null}
    </div></>
  ) : (
    <><div className="insp-h">序列属性</div><div className="insp-b">
      <div className="ws-honest-empty" role="status" data-honest-kind="empty_selection" data-honest-workspace="EDIT"><h4>尚未选中片段</h4><p>点一个片段看它的入出点和音量。</p></div>
      <dl className="kv" style={{marginTop: 8}}><dt>时长</dt><dd>{fmtTc(clips.length ? duration : 0)}</dd>
        <dt>入 / 出</dt><dd>{mark.in == null ? '—' : fmtTc(mark.in)} → {mark.out == null ? '—' : fmtTc(mark.out)}</dd>
        <dt>画面</dt><dd>1920×1080 · 24 fps</dd><dt>轨道 / 片段</dt><dd>{rows.length} / {clips.length}</dd></dl>
      <div style={{display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12}}>
        <button type="button" className="nv-btn" onClick={onBackToVideo}>从视频送入</button>
        <button type="button" className="nv-btn" onClick={() => setView('export')}>导出成片…</button>
      </div>
      <p className="edr-note" data-w-ux="09" data-writable="false" data-honest-badge="local-only">这里的编排只留在本页，不会保存。</p>
    </div></>
  );

  const mons = (
    <div className="nle-mons" aria-label="监视器">
      <div className="nle-mon" data-monitor="source"><div className="mon-frame"><span className="io" style={{top: 8, bottom: 'auto'}}>源监视器</span>
        <div className="ph">{cur ? <>{cur.name}<br /><span style={{fontSize: 11, opacity: .75}}>还没有可预览的画面</span></> : <>—<br /><span style={{fontSize: 11, opacity: .75}}>选中片段后在这里看</span></>}</div></div></div>
      <div className="nle-mon" data-monitor="program"><div className="mon-frame"><span className="io" style={{top: 8, bottom: 'auto'}}>节目监视器</span>
        <div className="ph">{playhead.toFixed(2)}s<br /><span style={{fontSize: 11, opacity: .75}}>1920×1080 · 24 fps · {clips.length} 片段</span></div>
        <span className="io">入 {mark.in == null ? '—' : fmtTc(mark.in)}</span><span className="io r">出 {mark.out == null ? '—' : fmtTc(mark.out)}</span></div>
        <div className="mon-bar"><button type="button" className="nv-btn" id="nlePlay2" aria-label={playing ? '暂停' : '播放'} onClick={() => setPlaying(p => !p)}>{playing ? '❚❚' : '▶'}</button>
          <span style={{fontVariantNumeric: 'tabular-nums'}}>{fmtTc(playhead)} / {fmtTc(clips.length ? duration : 0)}</span></div></div>
    </div>
  );

  const ticks: JSX.Element[] = [];
  for (let t = 0; t <= duration; t++) { const major = t % 5 === 0; if (zoom < 60 && !major) continue; if (zoom < 40 && t % 10) continue;
    ticks.push(<div key={t} className={`tick ${major ? 'major' : 'minor'}`} style={{left: t * px}}>{major ? <span>{t}s</span> : null}</div>); }
  const timeline = (
    <div className="nle-tl" aria-label="多轨时间线" data-timeline-hero="true">
      <div className="nle-track-meta"><span>{rows.length} 轨 · {clips.length} 片段</span><small>视频 / 音频 / 字幕并行</small></div>
      <div className="nle-tl-tools"><span>工具</span><button type="button" className="nv-btn" id="nleCut" disabled={!cur} onClick={cut} title="在播放头处切开选中片段（C）">切割</button>
        <span>{snap ? '吸附开 · 对齐片段边缘' : '吸附关'}</span>
        {isPro ? <span data-pro-only="shortcuts" className="nle-keys">快捷键：空格 播放 · I 入点 · O 出点 · C 切割</span> : null}</div>
      <div className="nle-scroll">
        <div className="nle-board" id="nleBoard" style={{width: Math.max(960, duration * px + 80), ['--nle-step' as string]: `${px}px`}}>
          <div className="nle-ruler" id="nleRuler" onMouseDown={scrub}>{ticks}</div>
          <div className="nle-playhead" id="nlePlayhead" style={{left: playhead * px}} />
          {rows.map(tid => { const tr = tracks[tid] || {mute: false, lock: false}; const cs = clips.filter(c => c.track === tid);
            return <div key={tid} className={`nle-row ${tid.toLowerCase()} ${cs.length ? '' : 'empty'}`} data-track={tid}>
              <div className="thdr"><span className="tn">{tid === 'S1' ? '字幕' : tid}</span><div className="tbtns">
                <button type="button" title="静音" aria-pressed={tr.mute} onClick={() => toggleTrack(tid, 'mute')}>M</button>
                <button type="button" title="锁定" aria-pressed={tr.lock} onClick={() => toggleTrack(tid, 'lock')}>L</button></div></div>
              <div className="trk">{cs.map(c => <button key={c.key} type="button" className={`clip ${c.kind} ${sel === c.key ? 'sel' : ''}`} style={{left: c.start * px, width: Math.max(28, c.dur * px), opacity: tr.mute ? .5 : 1}}
                title={c.name} onClick={() => setSel(s => s === c.key ? null : c.key)}>{c.name}</button>)}</div>
            </div>; })}
          {clips.length === 0 ? <div className="tl-empty" data-edit-empty="timeline"><span>把镜头或声音拖到这里开始剪。也可以从视频页一键送来。</span>
            <div className="nv-row"><button type="button" className="nv-btn" onClick={onBackToVideo}>从视频送入</button>{/* [HERMIA-FE-20261022 R6] 空时间线不再用主色（一页一主＝导出成片…） */}
              <button type="button" className="nv-btn" onClick={() => setView('media')}>导入媒体</button></div></div> : null}
        </div>
      </div>
    </div>
  );

  const media = (
    <div className="edr-sub nle-bin" data-edit-view="media" style={{background: 'var(--color-bg-app)'}}>
      <div className="nv-row" style={{alignItems: 'center'}}><h3>媒体池</h3><span className="nv-spacer" /><button type="button" className="nv-btn" onClick={() => setView('tl')}>回到时间线</button></div>
      <div className="bin-tabs" role="tablist">{([['video', '视频'], ['audio', '音频'], ['sub', '字幕']] as [BinTab, string][]).map(([id, l]) =>
        <button key={id} type="button" role="tab" aria-selected={binTab === id} onClick={() => setBinTab(id)}>{l}</button>)}</div>
      {grid(true)}
      {picked ? <div><button type="button" className="nv-btn" onClick={() => addToTimeline(picked)}>放到时间线</button></div> : null}
    </div>
  );
  const exportView = (
    <div className="edr-sub" data-edit-view="export">
      <div className="nv-row" style={{alignItems: 'center'}}><h3>导出成片</h3><span className="nv-spacer" /><button type="button" className="nv-btn" onClick={() => setView('tl')}>回到时间线</button></div>
      <div className="card" data-export-render="video"><b>视频成片 · MP4 1080p</b>
        <p className="edr-note">导出功能还没接好，现在点了不会生成文件。</p>
        <button type="button" className="nv-btn" disabled data-export-disabled="true">导出（不可用）</button></div>
      <div className="card"><b>文档与分镜</b><p className="edr-note">剧本、分镜表等文件可以走导出任务，状态以下方列表为准。</p>
        <WithQuery><ExportBody novelId={novelId} initialTab="render" /></WithQuery></div>
    </div>
  );

  return (
    <div className="edr nle" tabIndex={-1} onKeyDown={onKey} data-shell-mode={shellMode} data-edit-view={view} data-nle-tracks={rows.length} data-snap={snap ? 'on' : 'off'} data-writable="false" aria-label="剪辑工作区">
      <NovelOrient storageKey="studio-edit-orient-dismissed" what="这部作品的成片剪辑" can="把镜头和声音放上多轨时间线、切割、打入出点" effect="现在只在本页编排，不会保存；成片导出还没接好" />
      <NovelModTabs tabs={(['tl', 'media', 'export'] as EditView[]).map(id => ({id, label: VIEW_LABEL[id], selected: view === id, onClick: () => setView(id)}))} />
      <div className="nle-top" role="toolbar" aria-label="剪辑工具">
        <h2>剪辑 · {VIEW_LABEL[view]}</h2>
        <span className="nle-tc" id="nleTc" title="播放头">{fmtTc(playhead)}</span>
        <span className="nv-spacer" />
        <button type="button" className="nv-btn" id="nlePlay" onClick={() => setPlaying(p => !p)}>{playing ? '❚❚ 暂停' : '▶ 播放'}</button>
        <button type="button" className="nv-btn" id="nleMarkIn" onClick={() => setMark(m => ({...m, in: playhead}))}>I 入点</button>
        <button type="button" className="nv-btn" id="nleMarkOut" onClick={() => setMark(m => ({...m, out: playhead}))}>O 出点</button>
        <button type="button" className="nv-btn" id="nleSnap" aria-pressed={snap} onClick={() => setSnap(s => !s)}>{snap ? '吸附开' : '吸附关'}</button>
        <span className="nle-zoom"><button type="button" className="nv-btn" id="nleZoomOut" aria-label="缩小" onClick={() => setZoom(z => Math.max(25, z - 25))}>−</button>
          <span className="zp" id="nleZoomPct">{zoom}%</span><button type="button" className="nv-btn" id="nleZoomIn" aria-label="放大" onClick={() => setZoom(z => Math.min(400, z + 25))}>＋</button></span>
        <small style={{fontSize: 11, color: 'var(--color-text-muted)'}}>入 {mark.in == null ? '—' : fmtTc(mark.in)} · 出 {mark.out == null ? '—' : fmtTc(mark.out)} · 轨 {rows.length}</small>
        <button type="button" className="nv-btn nv-btn--primary" data-edit-primary="export" onClick={() => setView('export')}>导出成片…</button>
        <button type="button" className="nv-btn" onClick={onBackToVideo}>回视频改镜头</button>
      </div>
      {view === 'tl' ? <>
        <div className={`nle-upper ${binOpen ? '' : 'bin-collapsed'}`}>{bin}{mons}<div className="nle-insp">{insp}</div></div>
        {!binOpen ? <button type="button" className="nv-btn" style={{position: 'absolute', left: 8, top: 120, zIndex: 6}} onClick={() => setBinOpen(true)}>展开媒体池</button> : null}
        {timeline}
      </> : view === 'media' ? media : exportView}
    </div>
  );
}
