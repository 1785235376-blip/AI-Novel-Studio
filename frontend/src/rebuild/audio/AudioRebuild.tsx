/* [HERMIA-FE-20261022 R4] 声音模块按原型 audioWSHTML 重写：模块头 + .mw-split（左 声音库 · 中 单条波形检听 · 右 声音任务检视）。
   数据来自真实接口：/api/novels/{nid}/speech-generations（人声）· /audiobook/manifest（有声书）· /api/audio/providers（服务置灰原因）。
   声音是检听和生成，不是多轨剪辑：页上没有任何轨道头。没有音频文件时不画假波形、不显示假「已就绪」。
   一页一主（规格 §3.2）：有选中时「送到剪辑…」为主，无选中时「新建配音」为主。 */
import {useEffect, useMemo, useRef, useState} from 'react';
import {api} from '../../api';
import {Drawer} from '../primitives';
import {SpeechSynthesisPanel} from '../../novel/SpeechSynthesisPanel';
import {AudioGenerationPanel} from '../../novel/AudioGenerationPanel';
import {AudiobookManifestPanel} from '../../novel/AudiobookManifestPanel';
import {NovelOrient, NovelModTabs} from '../novel/NovelOrient';
import '../novel/novelRebuild.css';
import '../image/imageRebuild.css';
import './audioRebuild.css';

export type AudioView = 'lib' | 'tts' | 'mix';
export type AudioItem = {key: string; kind: '人声' | '音效' | '有声书'; name: string; sub: string; uri?: string};
type Focus = 'speech' | 'gen' | 'manifest';
const VIEW_LABEL: Record<AudioView, string> = {lib: '声音库', tts: '配音', mix: '混音台'};

export function audioItemsFrom(speech: any[] | null, manifest: any): AudioItem[] {
  const out: AudioItem[] = [];
  (speech || []).forEach((s, i) => out.push({key: `sp${i}`, kind: '人声', name: `配音 ${i + 1}${s?.voice ? ` · ${s.voice}` : ''}`,
    sub: `人声 · ${s?.emotion || '平静'}`, uri: s?.audio_uri || s?.uri}));
  for (const c of manifest?.chapters || []) if ((c?.audio_count || 0) > 0)
    out.push({key: `bk${c.chapter_id}`, kind: '有声书', name: `${c.title || '章节'} · 有声书`, sub: `有声书 · ${c.audio_count} 段`, uri: c.audio?.[0]?.uri || c.audio?.[0]?.audio_uri});
  return out;
}
export function bookProgress(manifest: any) {
  const ch = manifest?.chapters || [];
  const done = ch.filter((c: any) => (c.audio_count || 0) > 0).length;
  const queued = ch.filter((c: any) => c.production_status && c.production_status !== 'NOT_QUEUED' && !(c.audio_count > 0)).length;
  return {total: ch.length, done, queued};
}
const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

export function AudioRebuild({novelId, onSendToEdit, onOpenAssets, onOpenControl}: {
  novelId: string; shellMode?: 'basic' | 'pro'; onSendToEdit?: () => void; onOpenAssets?: () => void; onOpenControl?: () => void;
}) {
  const [view, setView] = useState<AudioView>('lib');
  const [speech, setSpeech] = useState<any[] | null>(null);
  const [manifest, setManifest] = useState<any>(null);
  const [providers, setProviders] = useState<any[] | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    api.speechGenerations(novelId).then(d => live && setSpeech(d.items || [])).catch(() => live && setSpeech([]));
    api.audiobookManifest(novelId).then(d => live && setManifest(d || {})).catch(() => live && setManifest({}));
    api.audioProviders().then(d => live && setProviders(d.items || [])).catch(() => live && setProviders([]));
    return () => { live = false; };
  }, [novelId, tick]);
  const items = useMemo(() => audioItemsFrom(speech, manifest), [speech, manifest]);
  const loaded = speech !== null && manifest !== null;
  const [sel, setSel] = useState<string | null>(null);
  const cur = items.find(i => i.key === sel) ?? null;
  const [focus, setFocus] = useState<Focus>('speech');
  const [drawer, setDrawer] = useState<null | Focus>(null);
  const [sendConfirm, setSendConfirm] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState({pos: 0, dur: 0});
  const audioRef = useRef<HTMLAudioElement>(null);
  const tts = (providers || []).filter(p => (p.capabilities || []).includes('TTS') && p.configured);
  const sfx = (providers || []).filter(p => (p.capabilities || []).some((c: string) => c !== 'TTS') && p.configured);
  const prog = bookProgress(manifest);
  const close = () => { setDrawer(null); setTick(x => x + 1); };
  const open = (f: Focus) => { setFocus(f); setDrawer(f); };
  const askSend = () => setSendConfirm(true);
  const togglePlay = () => { const a = audioRef.current; if (!a || !cur?.uri) return; if (a.paused) { void a.play().catch(() => setPlaying(false)); setPlaying(true); } else { a.pause(); setPlaying(false); } };
  const pick = (k: string) => { setSel(s => s === k ? null : k); setPlaying(false); setT({pos: 0, dur: 0}); };

  const head = (
    <div className="mw-head" role="toolbar" aria-label="声音子入口">
      <h2>声音 · {VIEW_LABEL[view]}</h2>
      <span className="nv-badge nv-badge--off">{loaded ? `${items.length} 条` : '读取中'}</span>
      <span className="nv-spacer" />
      {(['lib', 'tts', 'mix'] as AudioView[]).map(v => <button key={v} type="button" className="nv-btn" aria-pressed={view === v} onClick={() => { setView(v); if (v === 'tts') setFocus('speech'); }}>{VIEW_LABEL[v]}</button>)}
      {cur ? <button type="button" className="nv-btn nv-btn--primary" data-send-edit="audio" onClick={askSend}>送到剪辑…</button>
        : <><button type="button" className="nv-btn nv-btn--primary" data-aud-primary="new-speech" onClick={() => open('speech')}>新建配音</button>
          <button type="button" className="nv-btn" data-send-edit="audio" onClick={askSend}>送到剪辑…</button></>}
    </div>
  );

  const left = (
    <div className="mw-left">
      <div className="mw-lh">人声 / 音效 / 有声书</div>
      <div className="mw-tree" role="listbox" aria-label="声音库">
        {!loaded ? <p className="mw-muted">读取中…</p> : items.length === 0 ? <p className="mw-muted">还没有声音</p> :
          items.map(it => <button key={it.key} type="button" role="option" aria-selected={cur?.key === it.key} onClick={() => pick(it.key)}>
            <span className="ic">{it.kind === '人声' ? '♪' : it.kind === '有声书' ? '☰' : '∿'}</span><span>{it.name}<span className="sub">{it.sub}</span></span></button>)}
      </div>
      <p className="aud-left-note">这里只检听和生成；要和画面、字幕对齐，请「送去剪辑」。</p>
    </div>
  );

  const ph = t.dur ? Math.min(1, t.pos / t.dur) : 0;
  const hero = (
    <div className="mw-hero">
      <div className="hero-tools"><b>{cur ? cur.name : '波形检听'}</b><span className="nv-spacer" />
        <button type="button" className="nv-btn" id="audSendEdit" data-send-edit="audio" onClick={askSend}>送去剪辑</button></div>
      <div className="hero-stage">
        {loaded && items.length === 0 && !cur ? (
          <div className="img-empty" data-audio-empty="library"><h3>声音库是空的</h3><p>这里还没有声音。写一句对白试试配音，或导入一段环境音。</p>
            <div className="nv-row"><button type="button" className="nv-btn" onClick={() => open('speech')}>写一句对白</button><button type="button" className="nv-btn" onClick={onOpenAssets}>从资产导入</button></div></div>
        ) : (
          <div className="wave-stage" aria-label="波形与配音检听" data-audio-hero="waveform">
            <div className="w-meta"><span>{cur ? cur.name : '未选中'}</span><span>{cur ? `${cur.kind} · 单条检听` : '在左边选一条'}</span></div>
            <svg className="wave-svg" viewBox="0 0 520 96" preserveAspectRatio="none" aria-hidden="true">
              <line className="base" x1="0" y1="48" x2="520" y2="48" />
              {cur?.uri ? <line className="play" x1={ph * 520} y1="4" x2={ph * 520} y2="92" /> : null}
            </svg>
            {cur && !cur.uri ? <p className="w-note">这条还没有可播放的音频文件。</p> : null}
            {cur?.uri ? <audio ref={audioRef} src={cur.uri} preload="metadata" onTimeUpdate={e => setT({pos: e.currentTarget.currentTime, dur: e.currentTarget.duration || 0})}
              onLoadedMetadata={e => setT({pos: 0, dur: e.currentTarget.duration || 0})} onEnded={() => setPlaying(false)} /> : null}
            <div className="wave-bar">
              <button type="button" className="nv-btn" id="audPlay" disabled={!cur?.uri} aria-label={playing ? '暂停' : '播放'} onClick={togglePlay}>{playing ? '❚❚' : '▶'}</button>
              <span className="tc" id="audTc">{fmt(t.pos)} / {fmt(t.dur)}</span>
              <button type="button" className="nv-btn" id="audSelRegion" disabled={!cur?.uri} title="只在本地试听，不保存">选区</button>
              <button type="button" className="nv-btn" id="audGain" disabled={!cur?.uri} title="只在本地试听，不保存">增益 0 dB</button>
            </div>
            <div className="aud-focus" role="toolbar" aria-label="声音焦点">
              {([['speech', '配音'], ['gen', '音效'], ['manifest', '有声书清单']] as [Focus, string][]).map(([f, l]) =>
                <button key={f} type="button" className="nv-btn" data-aud-focus={f} aria-pressed={focus === f} onClick={() => setFocus(f)}>{l}</button>)}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const ttsReason = providers === null ? '正在检查语音服务…' : tts.length ? '' : '需要先在 AI 主控里接好语音服务';
  const rightSel = cur ? (
    <div className="mw-right"><div className="mw-rh">声音任务检视 · {cur.kind}</div>
      <div className="mw-rb" data-audio-focus={focus}>
        <div className={`sec aud-panel ${focus === 'speech' ? 'is-focus' : ''}`} data-panel="speech"><h4>语音合成</h4>
          <p className="nv-hint">写对白、选音色，在弹层里合成候选。</p>
          <button type="button" className="nv-btn aud-sec-primary" id="ttsGo" disabled={!tts.length} onClick={() => open('speech')}>合成候选…</button>
          {ttsReason ? <p className="nv-hint" data-tts-reason="true">{ttsReason}{!tts.length && providers ? <> · <button type="button" className="nv-link" onClick={onOpenControl}>打开 AI 主控</button></> : null}</p> : null}
        </div>
        <div className={`sec aud-panel ${focus === 'gen' ? 'is-focus' : ''}`} data-panel="gen"><h4>音效 / 音乐</h4>
          <button type="button" className="nv-btn" id="sfxGo" disabled={!sfx.length} onClick={() => open('gen')}>生成音效候选…</button>
          {providers && !sfx.length ? <p className="nv-hint">需要先在 AI 主控里接好音效服务</p> : null}
        </div>
        <div className={`sec aud-panel ${focus === 'manifest' ? 'is-focus' : ''}`} data-panel="manifest"><h4>有声书清单</h4>
          <div className="aud-batch"><b>全书批次</b>{prog.total} 章 · {prog.done} 已有音频 · {prog.queued} 排队中</div>
          <button type="button" className="nv-btn" id="bookOpen" onClick={() => open('manifest')}>打开有声书清单</button>
        </div>
        <div className="nv-row"><button type="button" className="nv-btn" onClick={askSend}>送去剪辑（显式确认）</button>
          <button type="button" className="nv-btn" onClick={onOpenAssets}>在资产中查看</button>
          <button type="button" className="nv-btn" onClick={() => setView('mix')}>混音台</button></div>
      </div></div>
  ) : (
    <div className="mw-right"><div className="mw-rh">下一步</div><div className="mw-rb">
      <div className="ws-honest-empty" role="status" data-honest-kind="empty_selection" data-honest-workspace="AUDIO">
        <h4>尚未选中内容</h4><p>选一条声音来试听，或者新建一段配音。</p>
        {ttsReason ? <p className="nv-hint" data-tts-reason="true">{ttsReason}</p> : null}
        <button type="button" className="nv-btn" onClick={() => open('gen')}>新建音效</button>
        <button type="button" className="nv-btn" onClick={() => open('manifest')}>打开有声书清单</button>
      </div></div></div>
  );

  const mix = (
    <div className="mw-hero"><div className="hero-stage"><div className="img-empty" data-aud-view="mix"><h3>混音台</h3>
      <p>按章节查看有声书混音方案。混音方案的服务端状态还待核实，这里只做查看，不改动任何声音。</p>
      <div className="nv-row"><button type="button" className="nv-btn" onClick={() => open('manifest')}>打开有声书清单</button><button type="button" className="nv-btn" onClick={() => setView('lib')}>回声音库</button></div></div></div></div>
  );

  const confirm = sendConfirm ? (
    <div className="img-confirm" role="dialog" aria-label="送去剪辑确认" data-send-edit-dialog="true">
      <strong>{cur ? `把「${cur.name}」送去剪辑？` : '切到剪辑页？'}</strong>
      <p>{cur ? '会切到剪辑，这条声音作为媒体池素材引用，不会自动摆上时间线。' : '现在没有选中声音，只会切换到剪辑页，不带任何素材。'}</p>
      <div className="nv-row"><button type="button" className="nv-btn nv-btn--primary" data-send-edit-confirm="true" onClick={() => { setSendConfirm(false); onSendToEdit?.(); }}>确认送去</button><button type="button" className="nv-btn" onClick={() => setSendConfirm(false)}>取消</button></div>
    </div>
  ) : null;

  return (
    <div className="aud-ws" data-aud-view={view} data-nle-tracks="0" aria-label="声音工作区">
      <NovelOrient storageKey="studio-audio-orient-dismissed" what="这部作品的配音、音效和有声书" can="试听、合成配音、生成音效、看有声书进度" effect="这里不做多轨剪辑；准备好后「送去剪辑」" />
      <NovelModTabs tabs={(['lib', 'tts', 'mix'] as AudioView[]).map(id => ({id, label: VIEW_LABEL[id], selected: view === id, onClick: () => setView(id)}))} />
      {head}
      <div className="mw-split">{left}{view === 'mix' ? mix : hero}{rightSel}</div>
      {confirm}
      {drawer === 'speech' ? <Drawer title="语音合成" onClose={close}><SpeechSynthesisPanel novelId={novelId} /></Drawer> : null}
      {drawer === 'gen' ? <Drawer title="音效 / 音乐" onClose={close}><AudioGenerationPanel novelId={novelId} /></Drawer> : null}
      {drawer === 'manifest' ? <Drawer title="有声书清单" onClose={close}><AudiobookManifestPanel novelId={novelId} /></Drawer> : null}
    </div>
  );
}
