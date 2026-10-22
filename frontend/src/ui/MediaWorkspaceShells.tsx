/**
 * [HERMIA-FE-20261022] Lightweight ModuleSwitcher shells for IMAGE / AUDIO / ASSETS / VIDEO.
 * Align LUMEN_IMAGE_IA · LUMEN_AUDIO_IA · LUMEN_ASSETS_IA · LUMEN_VIDEO_IA.
 * Compose existing panels; no backend invention.
 * W-UX-01: IMAGE preview hero + comic sub-entry; pro canvas collapsed.
 * W-UX-04: VIDEO three-layer thickening — Shot strip + canvas hero + director entry; ≠ EDIT.
 * W-UX-08: VIDEO Shot hero bar independent of Screenplay; read-only DirectorShot* fields; ≠ NLE.
 * W-UX-02: AUDIO waveform hero + Speech/AudioGen/Manifest + send-edit confirm; 0 fake NLE tracks.
 * W-UX-03: ASSETS browser hero + Inspector lineage/version summary; drag=reference; ≠ IMAGE desk.
 * W-UX-10: IMAGE comic sub-entry clickable (rail+toolbar, no 7th chrome) + preview/comic hero thicker; ≠ VIDEO/EDIT.
 * W-UX-11: AUDIO single-clip listen visible + send-edit confirm copy aligned with VIDEO; 0 NLE tracks.
 */
import {useEffect, useState, type ReactNode} from 'react';
import {Button} from './primitives';
import {ImageGenerationPanel} from '../novel/ImageGenerationPanel';
import {VisualContextPanel} from '../novel/VisualContextPanel';
import {VisionAnalysisPanel} from '../novel/VisionAnalysisPanel';
import {MultimodalDirectorWorkspace, type DirectorShot} from '../novel/MultimodalDirectorWorkspace';
import {SpeechSynthesisPanel} from '../novel/SpeechSynthesisPanel';
import {AudioGenerationPanel} from '../novel/AudioGenerationPanel';
import {AudiobookManifestPanel} from '../novel/AudiobookManifestPanel';
import {ScreenplayPanel} from '../novel/ScreenplayPanel';
import {AssetLibraryPanel} from '../novel/AssetLibraryPanel';
import type {Asset} from '../api';
import type {ImageInspection} from '../novel/ImageTaskInspector';
import type {AudioInspection} from '../novel/AudioTaskInspector';
import './MediaWorkspaceShells.css';

export function ImageWorkspaceRail({
  subview = 'studio',
  onSubviewChange,
}: {
  subview?: 'studio' | 'comic';
  onSubviewChange?: (v: 'studio' | 'comic') => void;
}) {
  return (
    <nav className="media-ws-rail" aria-label="图片工作区导航">
      <div className="media-ws-rail__eyebrow">图片</div>
      <strong>视觉素材</strong>
      <ul>
        <li>
          <button
            type="button"
            className="media-ws-rail__item"
            aria-pressed={subview === 'studio'}
            onClick={() => onSubviewChange?.('studio')}
          >参考 / 生成 / 分析</button>
        </li>
        <li>
          <button
            type="button"
            className="media-ws-rail__item"
            aria-pressed={subview === 'comic'}
            data-image-sub="comic"
            onClick={() => onSubviewChange?.('comic')}
          >漫画制作（子入口）</button>
        </li>
      </ul>
      <p className="media-ws-rail__hint">漫画＝图片 › 子入口（不升顶栏）。≠ 视频三层 · ≠ 剪辑 NLE · 不进小说中区。</p>
      <p className="media-ws-rail__hint">专业可展开创作画布（仍属 IMAGE 作用域）。</p>
    </nav>
  );
}

/**
 * [HERMIA-FE-20261022 W-UX-08] Demo Shot strip — UI discovery only.
 * Shape mirrors DirectorShot (name/duration/camera/action/dialogue); no invent write API.
 * status = honest demo labels (候选/草稿/演示), never fake「已就绪」green.
 */
type VideoShotHeroItem = {
  id: string;
  number: number;
  status: 'demo' | 'candidate' | 'draft';
  shot: Pick<DirectorShot, 'name' | 'duration' | 'camera' | 'action' | 'dialogue'>;
};

const DEMO_SHOT_STRIP: readonly VideoShotHeroItem[] = [
  {id: 's1', number: 1, status: 'candidate', shot: {name: '开场推门', duration: '3s', camera: '中景推进', action: '手推门缝，走廊漏光', dialogue: '……'}},
  {id: 's2', number: 2, status: 'candidate', shot: {name: '走廊回头', duration: '2s', camera: '近景', action: '脚步停，回头', dialogue: '谁？'}},
  {id: 's3', number: 3, status: 'draft', shot: {name: '窗外远景', duration: '4s', camera: '远景', action: '窗外星光缓慢移动', dialogue: ''}},
  {id: 's4', number: 4, status: 'demo', shot: {name: '切近特写', duration: '2s', camera: '特写', action: '瞳孔映出门缝光', dialogue: '先别动。'}},
];

const SHOT_STATUS_LABEL: Record<VideoShotHeroItem['status'], string> = {
  demo: '演示',
  candidate: '候选',
  draft: '草稿',
};

/** [HERMIA-FE-20261022 W-UX-08] Independent Shot hero — ≠ Screenplay paste; read-only DirectorShot fields. */
export function VideoShotHeroStrip({
  shots = DEMO_SHOT_STRIP,
  selectedId,
  onSelect,
}: {
  shots?: readonly VideoShotHeroItem[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const selected = shots.find(s => s.id === selectedId) ?? shots[0];
  return (
    <div className="media-ws__shot-hero" data-shot-hero="true" aria-label="Shot 英雄条">
      <div className="media-ws__shot-hero-head">
        <span className="media-ws__hero-label">① 镜头脚本 · Shot 英雄条</span>
        <span className="media-ws__shot-hero-badge" data-shot-hero-badge="true">≠ 影视剧本 · ≠ NLE</span>
      </div>
      <p className="media-ws__layer-note">
        分镜卡 / Shot 列表为本层英雄区（对照 LUMEN_VIDEO_IA · Vera V-P1-02）。
        字段对齐 <code>DirectorShot</code> 只读发现；完整可写卡在导演台 Multimodal，不在本条编造写入。
      </p>
      <div className="media-ws__shot-strip" role="list" aria-label="Shot 卡条">
        {shots.map(item => (
          <button
            type="button"
            key={item.id}
            role="listitem"
            className={`media-ws__shot-card${selectedId === item.id ? ' is-selected' : ''}`}
            aria-pressed={selectedId === item.id}
            data-shot-id={item.id}
            data-shot-status={item.status}
            onClick={() => onSelect(item.id)}
          >
            <span className="media-ws__shot-num">S{item.number}</span>
            <strong>{item.shot.name}</strong>
            <small>{item.shot.camera} · {item.shot.duration}</small>
            <small>{item.shot.dialogue || '（无对白）'}</small>
            <span className={`media-ws__shot-status media-ws__shot-status--${item.status}`}>
              {SHOT_STATUS_LABEL[item.status]}
            </span>
          </button>
        ))}
      </div>
      {selected && (
        <dl className="media-ws__shot-readonly" data-director-shot-readonly="true" aria-label="选中镜头只读摘要">
          <div><dt>名称</dt><dd>{selected.shot.name}</dd></div>
          <div><dt>时长</dt><dd>{selected.shot.duration}</dd></div>
          <div><dt>运镜</dt><dd>{selected.shot.camera}</dd></div>
          <div><dt>动作</dt><dd>{selected.shot.action}</dd></div>
          <div><dt>对白</dt><dd>{selected.shot.dialogue || '（无）'}</dd></div>
        </dl>
      )}
    </div>
  );
}

/** [HERMIA-FE-20261022 W-UX-10] Demo comic pages — UI discovery only; no invent gen API / fake ready. */
const DEMO_COMIC_PAGES: readonly {id: string; label: string}[] = [
  {id: 'p1', label: '第 1 页'},
  {id: 'p2', label: '第 2 页'},
  {id: 'p3', label: '第 3 页'},
  {id: 'p4', label: '封面'},
];

const DEMO_IMAGE_THUMBS: readonly {id: string; name: string; kind: string; tone: 'fog' | 'portrait' | 'frame'}[] = [
  {id: 'img1', name: '雾港参考_01', kind: '参考 · 演示', tone: 'fog'},
  {id: 'img2', name: '林砚定妆 v3', kind: '角色 · 演示', tone: 'portrait'},
  {id: 'img3', name: '码头关键帧', kind: '候选 · 演示', tone: 'frame'},
];

export function ImageWorkspaceShell({
  novelId, inspection, onInspect, shellMode = 'basic',
  subview: subviewProp,
  onSubviewChange,
}: {
  novelId: string;
  inspection?: ImageInspection;
  onInspect: (i?: ImageInspection) => void;
  /** [HERMIA-FE-20261022 X-UX-04] basic collapses pro canvas; pro may pin open. */
  shellMode?: 'basic' | 'pro';
  /** [HERMIA-FE-20261022 W-UX-10] Controlled subview so Rail/toolbar/EmptyCta stay in sync. */
  subview?: 'studio' | 'comic';
  onSubviewChange?: (v: 'studio' | 'comic') => void;
}) {
  const [subviewLocal, setSubviewLocal] = useState<'studio' | 'comic'>('studio');
  const subview = subviewProp ?? subviewLocal;
  const setSubview = (v: 'studio' | 'comic') => {
    if (subviewProp === undefined) setSubviewLocal(v);
    onSubviewChange?.(v);
  };
  const [proOpen, setProOpen] = useState(shellMode === 'pro');
  const [comicPage, setComicPage] = useState('p1');
  const [comicNotice, setComicNotice] = useState<string | null>(null);
  const [thumbSel, setThumbSel] = useState(DEMO_IMAGE_THUMBS[0]!.id);
  useEffect(() => {
    setProOpen(shellMode === 'pro');
  }, [shellMode]);
  const scrollPanel = (label: string) => {
    document.querySelector(`.media-ws__panel[aria-label="${label}"]`)?.scrollIntoView({block: 'nearest'});
  };
  const selectedThumb = DEMO_IMAGE_THUMBS.find(t => t.id === thumbSel) ?? DEMO_IMAGE_THUMBS[0]!;
  const pageLabel = DEMO_COMIC_PAGES.find(p => p.id === comicPage)?.label ?? '第 1 页';
  return (
    <div className="media-ws" aria-label="图片工作区" data-image-subview={subview} data-shell-mode={shellMode}>
      <div className="media-ws__toolbar" role="toolbar" aria-label="图片子入口">
        <Button type="button" aria-pressed={subview === 'studio'} data-image-sub="studio" onClick={() => setSubview('studio')}>
          图片工作台
        </Button>
        <Button type="button" aria-pressed={subview === 'comic'} data-open-comic="true" data-image-sub="comic" onClick={() => setSubview('comic')}>
          漫画制作
        </Button>
        <span className="media-ws__shot-hero-badge" data-image-badge="no-chrome7">子入口 · 不升顶栏</span>
        <span className="media-ws__shot-hero-badge" data-image-badge="boundary">≠ VIDEO · ≠ NLE</span>
        <small>项目 {novelId} · LUMEN_IMAGE_IA · W-UX-10</small>
      </div>

      {subview === 'comic' ? (
        <div className="media-ws__comic" aria-label="漫画子入口" data-image-comic="true">
          <div className="media-ws__hero media-ws__hero--comic media-ws__hero--thick" aria-label="漫画预览" data-image-hero="comic">
            <div className="media-ws__shot-hero-head">
              <span className="media-ws__hero-label">图片 › 漫画制作 · 子入口</span>
              <span className="media-ws__shot-hero-badge" data-image-badge="comic">IMAGE-COMIC-01</span>
              <span className="media-ws__shot-hero-badge" data-image-badge="no-chrome7">不升第 7 顶栏钮</span>
              <span className="media-ws__shot-hero-badge" data-image-badge="boundary">≠ VIDEO 三层 · ≠ EDIT NLE</span>
            </div>
            <div className="media-ws__comic-tools" aria-label="漫画页工具">
              <strong>当前页 · {pageLabel}</strong>
              <span className="media-ws__shot-status media-ws__shot-status--draft">分格/气泡 · 演示</span>
              <div className="media-ws__hero-actions">
                <Button type="button" data-comic-action="add-panel" onClick={() => setComicNotice('已添加分格草稿（本地演示 · 未接通写库）')}>＋ 分格</Button>
                <Button type="button" data-comic-action="add-bubble" onClick={() => setComicNotice('已添加气泡（本地演示 · 未接通写库）')}>＋ 气泡</Button>
                <Button type="button" data-image-sub="studio" onClick={() => setSubview('studio')}>回预览</Button>
              </div>
            </div>
            <div className="media-ws__comic-stage" aria-label="漫画页预览">
              <div className="media-ws__comic-page" data-comic-page={comicPage}>
                <div className="media-ws__comic-cell"><span className="media-ws__comic-bub" data-bub="tl">雾又厚了……</span></div>
                <div className="media-ws__comic-cell media-ws__comic-cell--c2"><span className="media-ws__comic-bub media-ws__comic-bub--br" data-bub="br">你也收到信了？</span></div>
                <div className="media-ws__comic-cell media-ws__comic-cell--wide"><span className="media-ws__comic-bub media-ws__comic-bub--mid" data-bub="mid">码头的灯还在亮。</span></div>
              </div>
            </div>
            <div className="media-ws__comic-strip" role="tablist" aria-label="漫画页条">
              {DEMO_COMIC_PAGES.map(p => (
                <button
                  type="button"
                  key={p.id}
                  role="tab"
                  aria-selected={comicPage === p.id}
                  data-comic-page-tab={p.id}
                  className={comicPage === p.id ? 'is-selected' : undefined}
                  onClick={() => { setComicPage(p.id); setComicNotice(null); }}
                >{p.label}</button>
              ))}
            </div>
            {comicNotice && <p className="media-ws__comic-notice" data-comic-notice="true" role="status">{comicNotice}</p>}
            <p className="media-ws__layer-note">对照 LUMEN_IMAGE_IA · Vera image_comic：分格/气泡/页条为壳向发现；逐格生成待接通，禁假绿就绪标。</p>
          </div>
          <div className="media-ws-cta" aria-label="漫画下一步">
            <strong>下一步 · 漫画</strong>
            <p>可切换页条、加分格/气泡草稿，或返回图片预览。完整 StudioComic 全屏面仍走已授权项目；本壳不升顶栏、不嵌小说中区。</p>
            <div className="media-ws__hero-actions">
              <Button type="button" data-comic-action="gen-cell" onClick={() => setComicNotice('逐格生成待接通（B06）· 未派发 · 非假绿接通')}>生成当前格候选…</Button>
              <Button type="button" data-image-sub="studio" onClick={() => setSubview('studio')}>返回图片生成 / 参考</Button>
            </div>
          </div>
          <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-10] 漫画＝IMAGE 子入口（rail+toolbar）· 不升顶栏 · ≠ VIDEO · ≠ EDIT。</p>
        </div>
      ) : (
        <>
          <div className="media-ws__hero media-ws__hero--thick" aria-label="图像预览" data-image-hero="preview">
            <div className="media-ws__shot-hero-head">
              <span className="media-ws__hero-label">图像预览 · hero</span>
              <span className="media-ws__shot-hero-badge" data-image-badge="hero">预览 hero</span>
              <span className="media-ws__shot-hero-badge" data-image-badge="boundary">≠ VIDEO 三层 · ≠ EDIT NLE</span>
              <span className="media-ws__shot-hero-badge" data-image-badge="no-chrome7">漫画不升顶栏</span>
            </div>
            <div className="media-ws__image-stage" aria-label="当前图预览台">
              {inspection?.assetUri ? (
                <img className="media-ws__hero-preview" src={inspection.assetUri} alt="当前图片生成结果" referrerPolicy="no-referrer" />
              ) : (
                <div className={`media-ws__image-placeholder media-ws__image-placeholder--${selectedThumb.tone}`} data-image-demo-thumb={selectedThumb.id}>
                  <span className="media-ws__ref-chip">参考叠看 · 演示</span>
                  <strong>{inspection ? `任务 ${inspection.status}` : selectedThumb.name}</strong>
                  <p>{inspection ? '等待真实结果 URI；不假装已出图。' : `${selectedThumb.kind} · 提交生成或从历史选择真实结果。`}</p>
                  <small>主表面是预览，不是视频导演台，也不是多轨时间线。</small>
                </div>
              )}
            </div>
            <div className="media-ws__hero-actions" aria-label="预览下一步 CTA" data-image-hero-cta="true">
              <Button type="button" data-image-cta="generate" onClick={() => scrollPanel('图片生成')}>新建生成</Button>
              <Button type="button" data-image-cta="reference" onClick={() => scrollPanel('视觉上下文')}>加参考</Button>
              <Button type="button" data-open-comic="true" data-image-cta="comic" onClick={() => setSubview('comic')}>打开漫画</Button>
            </div>
            <div className="media-ws__image-thumbs" role="list" aria-label="预览缩略条（演示）">
              {DEMO_IMAGE_THUMBS.map(t => (
                <button
                  type="button"
                  key={t.id}
                  role="listitem"
                  className={`media-ws__image-thumb${thumbSel === t.id ? ' is-selected' : ''}`}
                  aria-pressed={thumbSel === t.id}
                  data-image-thumb={t.id}
                  onClick={() => setThumbSel(t.id)}
                >
                  <span className={`media-ws__image-thumb-swatch media-ws__image-thumb-swatch--${t.tone}`} />
                  <strong>{t.name}</strong>
                  <small>{t.kind}</small>
                </button>
              ))}
            </div>
            <small>项目 {novelId} · LUMEN_IMAGE_IA · W-UX-10 · 禁假绿</small>
          </div>
          <div className="media-ws__body media-ws__body--split">
            <section className="media-ws__panel" aria-label="图片生成">
              <h3>图片生成</h3>
              <ImageGenerationPanel novelId={novelId} onInspect={onInspect} />
            </section>
            <section className="media-ws__panel" aria-label="视觉上下文">
              <h3>参考 / 视觉上下文</h3>
              <VisualContextPanel novelId={novelId} />
            </section>
            <section className="media-ws__panel" aria-label="画面分析">
              <h3>画面分析</h3>
              <VisionAnalysisPanel novelId={novelId} />
            </section>
          </div>
          <details
            className="media-ws__pro"
            data-pro-canvas="true"
            open={proOpen}
            onToggle={(e) => setProOpen((e.target as HTMLDetailsElement).open)}
          >
            <summary>专业 · 创作画布（IMAGE 作用域 · 非视频三层）</summary>
            <MultimodalDirectorWorkspace mode="image" novelId={novelId} />
          </details>
          <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-10] 图片 ≠ 小说中区 · ≠ VIDEO 三层 · ≠ EDIT NLE · 漫画不升顶栏。</p>
        </>
      )}
    </div>
  );
}

export function AudioWorkspaceRail({onSendToEdit}: {onSendToEdit?: () => void}) {
  const [sendConfirm, setSendConfirm] = useState(false);
  return (
    <nav className="media-ws-rail" aria-label="声音工作区导航">
      <div className="media-ws-rail__eyebrow">声音</div>
      <strong>配音 / 音效 / 有声书</strong>
      <ul>
        <li>人声 TTS</li>
        <li>音效生成</li>
        <li>有声书清单</li>
      </ul>
      {onSendToEdit && (
        <button
          type="button"
          className="media-ws-rail__item media-ws-rail__item--send"
          data-send-edit="true"
          onClick={() => setSendConfirm(true)}
        >送去剪辑（显式）</button>
      )}
      {sendConfirm && onSendToEdit && (
        <div className="media-ws__send-confirm" role="dialog" aria-label="送去剪辑确认">
          <strong>显式交片 → 剪辑</strong>
          <p>将离开声音配音工作区，打开顶栏「剪辑」多轨 NLE。声音侧选区保留；不在本区假装时间线。</p>
          <div className="media-ws__hero-actions">
            <Button type="button" onClick={() => { setSendConfirm(false); onSendToEdit(); }}>确认送去剪辑</Button>
            <Button type="button" onClick={() => setSendConfirm(false)}>取消</Button>
          </div>
        </div>
      )}
      <p className="media-ws-rail__hint">AUDIO ≠ EDIT：本区是波形/配音工作区，不做多轨 NLE hero。</p>
    </nav>
  );
}

/**
 * [HERMIA-FE-20261022 W-UX-11] Demo audio clips — single-item listen discovery only.
 * No invent playback / NLE track API; status never fake「已就绪」.
 */
type AudioClipDemo = {
  id: string;
  kind: 'speech' | 'sfx' | 'audiobook';
  title: string;
  duration: string;
  status: 'demo' | 'candidate' | 'draft';
  note: string;
};

const DEMO_AUDIO_CLIPS: readonly AudioClipDemo[] = [
  {id: 'a1', kind: 'speech', title: '第1章 · 开场对白', duration: '0:12', status: 'candidate', note: 'TTS 草稿 · 未接通真音频'},
  {id: 'a2', kind: 'sfx', title: '门缝风声', duration: '0:04', status: 'demo', note: '音效示意 · 本地检听'},
  {id: 'a3', kind: 'audiobook', title: '有声书 · 章节点', duration: '3:20', status: 'draft', note: '清单条目 · 待生成'},
];

const AUDIO_KIND_LABEL: Record<AudioClipDemo['kind'], string> = {
  speech: '人声',
  sfx: '音效',
  audiobook: '有声书',
};

const AUDIO_STATUS_LABEL: Record<AudioClipDemo['status'], string> = {
  demo: '演示',
  candidate: '候选',
  draft: '草稿',
};

/** [HERMIA-FE-20261022 W-UX-11] Single-clip listen strip — ≠ NLE multi-track hero. */
export function AudioListenStrip({
  clips = DEMO_AUDIO_CLIPS,
  selectedId,
  onSelect,
}: {
  clips?: readonly AudioClipDemo[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <div className="media-ws__audio-strip" role="list" aria-label="声音条目（单条检听）" data-audio-strip="true">
      {clips.map(clip => (
        <button
          type="button"
          key={clip.id}
          role="listitem"
          className={`media-ws__audio-clip${selectedId === clip.id ? ' is-selected' : ''}`}
          aria-pressed={selectedId === clip.id}
          data-audio-clip={clip.id}
          data-audio-kind={clip.kind}
          data-audio-status={clip.status}
          onClick={() => onSelect(selectedId === clip.id ? null : clip.id)}
        >
          <span className="media-ws__audio-kind">{AUDIO_KIND_LABEL[clip.kind]}</span>
          <strong>{clip.title}</strong>
          <small>{clip.duration}</small>
          <span className={`media-ws__shot-status media-ws__shot-status--${clip.status}`}>
            {AUDIO_STATUS_LABEL[clip.status]}
          </span>
        </button>
      ))}
    </div>
  );
}

/** [HERMIA-FE-20261022 W-UX-11] AUDIO = single-clip waveform listen; send-edit confirm = VIDEO copy; 0 NLE. */
export function AudioWorkspaceShell({
  novelId, onInspect, onSendToEdit,
}: {
  novelId: string;
  onInspect: (i: AudioInspection) => void;
  onSendToEdit?: () => void;
}) {
  const [focus, setFocus] = useState<'speech' | 'gen' | 'manifest'>('speech');
  const [sendConfirm, setSendConfirm] = useState(false);
  const [selectedClipId, setSelectedClipId] = useState<string | null>('a1');
  const [listening, setListening] = useState(false);
  const selected = DEMO_AUDIO_CLIPS.find(c => c.id === selectedClipId) ?? null;

  // Clearing selection stops local listen demo
  const selectClip = (id: string | null) => {
    setSelectedClipId(id);
    if (!id) setListening(false);
  };

  return (
    <div
      className="media-ws media-ws--audio"
      aria-label="声音工作区"
      data-audio-hero="waveform"
      data-audio-listen="single"
      data-nle-tracks="0"
      data-audio-listening={listening ? 'true' : 'false'}
    >
      <div className="media-ws__hero media-ws__hero--audio media-ws__hero--thick" aria-label="波形与配音检听">
        <div className="media-ws__shot-hero-head">
          <span className="media-ws__hero-label">波形 / 配音 · 单条检听 · 非 NLE</span>
          <span className="media-ws__shot-hero-badge" data-audio-badge="boundary">AUDIO ≠ EDIT · 0 轨</span>
          <span className="media-ws__shot-hero-badge" data-audio-badge="honest">演示 · 未接通真音频</span>
        </div>
        <strong>检听工作区</strong>
        <p>
          选一条人声 / 音效 / 有声书条目做本区检听（单条波形）。多轨对齐画面、字幕轨与成片导出请显式「送去剪辑」——本壳 <strong>0 条假 NLE 轨</strong>。
        </p>
        <AudioListenStrip selectedId={selectedClipId} onSelect={selectClip} />
        {selected ? (
          <div
            className="media-ws__audio-listen"
            aria-label="单条检听台"
            data-audio-listen-stage="true"
            data-audio-clip={selected.id}
          >
            <div className={`media-ws-wave${listening ? ' is-listening' : ''}`} aria-hidden="true">
              <span className="media-ws-wave__playhead" />
            </div>
            <dl className="media-ws__audio-listen-meta" data-audio-listen-meta="true">
              <div><dt>条目</dt><dd>{selected.title}</dd></div>
              <div><dt>类型</dt><dd>{AUDIO_KIND_LABEL[selected.kind]}</dd></div>
              <div><dt>时长</dt><dd>{selected.duration}</dd></div>
              <div><dt>状态</dt><dd>{AUDIO_STATUS_LABEL[selected.status]} · {selected.note}</dd></div>
            </dl>
            <div className="media-ws__hero-actions">
              <Button
                type="button"
                data-audio-play="true"
                aria-pressed={listening}
                onClick={() => setListening(v => !v)}
              >{listening ? '停止检听示意' : '播放检听示意'}</Button>
              <Button type="button" data-audio-clear="true" onClick={() => selectClip(null)}>清除选中</Button>
            </div>
            <small>检听＝本区示意，不写 NLE 轨 · 项目 {novelId}</small>
          </div>
        ) : (
          <div className="media-ws__audio-listen media-ws__audio-listen--empty" data-audio-listen-stage="empty" data-honest-kind="empty_selection">
            <p>未选中声音条目。点上方条目可检听单条波形；无条目时也是诚实空，不是假绿「已就绪」。</p>
          </div>
        )}
        <div className="media-ws__hero-actions">
          <Button type="button" aria-pressed={focus === 'speech'} data-audio-focus="speech" onClick={() => setFocus('speech')}>Speech 配音</Button>
          <Button type="button" aria-pressed={focus === 'gen'} data-audio-focus="gen" onClick={() => setFocus('gen')}>AudioGen 音效</Button>
          <Button type="button" aria-pressed={focus === 'manifest'} data-audio-focus="manifest" onClick={() => setFocus('manifest')}>Audiobook 清单</Button>
        </div>
        <small>项目 {novelId} · LUMEN_AUDIO_IA · W-UX-11 · AUDIO ≠ EDIT</small>
      </div>
      <div className="media-ws__toolbar" role="toolbar" aria-label="声音工具条">
        <Button
          type="button"
          disabled={!selected}
          data-audio-play="toolbar"
          title={selected ? '检听示意（未接通真音频）' : '先选一条声音条目'}
          aria-pressed={listening}
          onClick={() => selected && setListening(v => !v)}
        >{listening ? '停止' : '播放'}</Button>
        <Button type="button" disabled title="选区示意">选区</Button>
        <Button type="button" disabled title="增益示意（非 NLE 轨控）">增益</Button>
        {onSendToEdit && (
          <Button
            type="button"
            className="media-ws__send-edit"
            data-send-edit="true"
            onClick={() => setSendConfirm(true)}
          >送去剪辑</Button>
        )}
        <small>假 NLE 轨：0 · 选中 {selected ? selected.id : '无'}</small>
      </div>

      {sendConfirm && onSendToEdit && (
        <div className="media-ws__send-confirm" role="dialog" aria-label="送去剪辑确认">
          <strong>显式交片 → 剪辑</strong>
          <p>将离开声音配音工作区，打开顶栏「剪辑」多轨 NLE。声音侧选区保留；不在本区假装时间线。</p>
          <div className="media-ws__hero-actions">
            <Button type="button" onClick={() => { setSendConfirm(false); onSendToEdit(); }}>确认送去剪辑</Button>
            <Button type="button" onClick={() => setSendConfirm(false)}>取消</Button>
          </div>
        </div>
      )}

      <div className="media-ws__body media-ws__body--split" data-audio-focus={focus}>
        <section className={`media-ws__panel${focus === 'speech' ? ' is-focus' : ''}`} aria-label="语音合成" data-panel="speech">
          <h3>SpeechSynthesis · 语音合成</h3>
          <SpeechSynthesisPanel novelId={novelId} onInspect={onInspect} />
        </section>
        <section className={`media-ws__panel${focus === 'gen' ? ' is-focus' : ''}`} aria-label="音效生成" data-panel="gen">
          <h3>AudioGeneration · 音效 / 音乐</h3>
          <AudioGenerationPanel novelId={novelId} />
        </section>
        <section className={`media-ws__panel${focus === 'manifest' ? ' is-focus' : ''}`} aria-label="有声书" data-panel="manifest">
          <h3>AudiobookManifest · 有声书清单</h3>
          <AudiobookManifestPanel novelId={novelId} onInspect={onInspect} />
        </section>
      </div>
      <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-11] 单条检听可见 · 送剪辑确认语对齐 VIDEO · 0 假 NLE 轨 · 禁假绿。</p>
    </div>
  );
}

export function AssetsWorkspaceRail() {
  return (
    <nav className="media-ws-rail" aria-label="资产工作区导航">
      <div className="media-ws-rail__eyebrow">资产</div>
      <strong>共享引用层</strong>
      <ul>
        <li>全部类型</li>
        <li>图片 / 视频 / 音频</li>
        <li>集合 / 标签（示意）</li>
      </ul>
      <p className="media-ws-rail__hint">拖入＝引用，不复制源文件，不自动开任务。非创作强制上游。</p>
    </nav>
  );
}

/** [HERMIA-FE-20261022 W-UX-03] ASSETS = shared browser + inspector; drag=reference; ≠ IMAGE desk. */
export function AssetsWorkspaceShell({
  novelId, selectedAssetId, onSelectAsset, selectedAsset,
}: {
  novelId: string;
  selectedAssetId?: string;
  onSelectAsset: (asset: Asset | undefined) => void;
  /** Optional selected asset for inline lineage/version summary (honest when absent). */
  selectedAsset?: Asset;
}) {
  const lineageCount = selectedAsset?.relationships?.length ?? 0;
  const version = selectedAsset?.version ?? selectedAsset?.provenance?.version;
  const hasSelection = Boolean(selectedAssetId || selectedAsset);

  return (
    <div
      className="media-ws media-ws--assets"
      aria-label="资产工作区"
      data-assets-hero="browser"
      data-drag-semantics="reference"
    >
      <div className="media-ws__hero media-ws__hero--assets" aria-label="资产浏览器">
        <span className="media-ws__hero-label">资产浏览器 · hero</span>
        <strong>共享库 · 查找与引用</strong>
        <p>网格/列表浏览、筛选与检视。拖出到其它模块＝<strong>建立引用</strong>（不复制源文件、不自动开花钱任务）。生图主路径在「图片」；多轨在「剪辑」——本区不是生图台。</p>
        <div className="media-ws__ref-chip" aria-label="拖入语义">拖入＝引用 · 非复制</div>
        <small>项目 {novelId} · LUMEN_ASSETS_IA</small>
      </div>

      <div className="media-ws__toolbar" role="toolbar" aria-label="资产工具条">
        <span className="media-ws__ref-chip">引用语义可见</span>
        <small>{hasSelection ? `已选 ${selectedAssetId || selectedAsset?.id}` : '未选中 · 见右栏 CTA'}</small>
      </div>

      <div className="media-ws__body media-ws__body--assets">
        <section className="media-ws__panel" aria-label="资产库">
          <h3>浏览器</h3>
          <AssetLibraryPanel
            novelId={novelId}
            selectedAssetId={selectedAssetId}
            onSelectAsset={onSelectAsset}
          />
        </section>
        <aside className="media-ws__panel media-ws__lineage" aria-label="血缘与版本摘要">
          <h3>血缘 / 版本摘要</h3>
          {hasSelection && selectedAsset ? (
            <dl className="media-ws__lineage-facts">
              <div><dt>文件</dt><dd title={selectedAsset.filename}>{selectedAsset.filename}</dd></div>
              <div><dt>版本</dt><dd>{version != null ? `v${version}` : '未记录（诚实 partial）'}</dd></div>
              <div><dt>关系条数</dt><dd>{lineageCount === 0 ? '0（无已声明关系）' : lineageCount}</dd></div>
              <div><dt>来源</dt><dd>{selectedAsset.provenance?.origin || '未声明'}</dd></div>
              <div><dt>完整性</dt><dd>{selectedAsset.provenance?.integrity || '未核实'}</dd></div>
            </dl>
          ) : (
            <p className="media-ws-rail__hint">未选中资产时不假装有血缘。选中后显示版本与关系摘要；缺字段标 partial，不编造 API。</p>
          )}
        </aside>
      </div>
      <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-03] ASSETS＝共享引用层 · ≠ IMAGE 生图台 · ≠ EDIT 媒体池主面。</p>
    </div>
  );
}

/** Empty-selection CTA blocks for inspectors (禁空白占位). */
export function ImageEmptyCta({
  onScrollGenerate,
  onOpenComic,
}: {
  onScrollGenerate?: () => void;
  onOpenComic?: () => void;
}): ReactNode {
  return (
    <div className="media-ws-cta" aria-label="图片下一步">
      <strong>下一步</strong>
      <p>暂无选中任务。可新建生成、加参考，或打开漫画子入口（图片工作区内）。</p>
      <div className="media-ws__hero-actions">
        {onScrollGenerate && <Button type="button" onClick={onScrollGenerate}>去图片生成</Button>}
        {onOpenComic && <Button type="button" data-open-comic="true" onClick={onOpenComic}>打开漫画</Button>}
      </div>
    </div>
  );
}

export function AudioEmptyCta({onSendToEdit}: {onSendToEdit?: () => void}): ReactNode {
  const [sendConfirm, setSendConfirm] = useState(false);
  return (
    <div className="media-ws-cta" aria-label="声音下一步" data-honest-kind="empty_selection">
      <strong>下一步</strong>
      <p>暂无选中声音任务。可新建配音 / 音效 / 有声书条目；成片组装请显式送去剪辑（本区无假 NLE 轨）。</p>
      {onSendToEdit && (
        <Button type="button" data-send-edit="true" onClick={() => setSendConfirm(true)}>送去剪辑</Button>
      )}
      {sendConfirm && onSendToEdit && (
        <div className="media-ws__send-confirm" role="dialog" aria-label="送去剪辑确认">
          <strong>显式交片 → 剪辑</strong>
          <p>将离开声音配音工作区，打开顶栏「剪辑」多轨 NLE。声音侧选区保留；不在本区假装时间线。</p>
          <div className="media-ws__hero-actions">
            <Button type="button" onClick={() => { setSendConfirm(false); onSendToEdit(); }}>确认送去剪辑</Button>
            <Button type="button" onClick={() => setSendConfirm(false)}>取消</Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function AssetsEmptyCta({onImportHint}: {onImportHint?: () => void} = {}): ReactNode {
  return (
    <div className="media-ws-cta" aria-label="资产下一步" data-honest-kind="empty_selection">
      <strong>下一步</strong>
      <p>未选中资产。可导入或筛选库；拖出到其它模块＝引用，不复制。库为空时也是诚实 0 条，不是假绿「已就绪」。</p>
      <div className="media-ws__ref-chip">拖入＝引用</div>
      {onImportHint && <Button type="button" onClick={onImportHint}>导入 / 筛选引导</Button>}
    </div>
  );
}

export function VideoWorkspaceRail({onSendToEdit}: {onSendToEdit?: () => void}) {
  return (
    <nav className="media-ws-rail" aria-label="视频工作区导航">
      <div className="media-ws-rail__eyebrow">视频</div>
      <strong>三层工作区</strong>
      <ul>
        <li>① 镜头脚本 · Shot 英雄条</li>
        <li>② 无限画布</li>
        <li>③ 内置导演台</li>
      </ul>
      {onSendToEdit && (
        <button type="button" className="media-ws-rail__item media-ws-rail__item--send" onClick={onSendToEdit}>
          送去剪辑（显式）
        </button>
      )}
      <p className="media-ws-rail__hint">VIDEO ≠ EDIT NLE · ≠ 小说写作台。导演仅属本工作区。</p>
    </nav>
  );
}

/** [HERMIA-FE-20261022 W-UX-08] LUMEN_VIDEO_IA — Shot hero independent of Screenplay; three layers; send-edit explicit. */
export function VideoWorkspaceShell({
  novelId, onInspect, onSendToEdit, shellMode = 'basic',
}: {
  novelId: string;
  onInspect?: (inspection: unknown) => void;
  onSendToEdit?: () => void;
  /** [HERMIA-FE-20261022 H-P1-01] basic hides director chrome by default (command still opens). */
  shellMode?: 'basic' | 'pro';
}) {
  const [directorOpen, setDirectorOpen] = useState(shellMode === 'pro');
  const [scriptOpen, setScriptOpen] = useState(true);
  const [selectedShot, setSelectedShot] = useState<string>('s1');
  const [sendConfirm, setSendConfirm] = useState(false);
  // [HERMIA-FE-20261022 X-UX-04] mode survives module hops; basic collapses director chrome
  useEffect(() => {
    setDirectorOpen(shellMode === 'pro');
  }, [shellMode]);

  return (
    <div className="media-ws media-ws--video" aria-label="视频工作区 · 三层" data-video-layers="script-canvas-director" data-shell-mode={shellMode}>
      <div className="media-ws__toolbar" role="toolbar" aria-label="视频工具条">
        <Button type="button" aria-pressed={scriptOpen} onClick={() => setScriptOpen(v => !v)}>
          {scriptOpen ? '收起镜头脚本' : '镜头脚本'}
        </Button>
        <Button type="button" aria-pressed={directorOpen} data-director-entry="true" onClick={() => setDirectorOpen(v => !v)}>
          {directorOpen ? '收起导演台' : '打开内置导演台'}
        </Button>
        {onSendToEdit && (
          <Button
            type="button"
            className="media-ws__send-edit"
            data-send-edit="true"
            onClick={() => setSendConfirm(true)}
          >送去剪辑</Button>
        )}
        <small>LUMEN_VIDEO_IA · 项目 {novelId} · ≠ EDIT NLE</small>
      </div>

      {sendConfirm && onSendToEdit && (
        <div className="media-ws__send-confirm" role="dialog" aria-label="送去剪辑确认">
          <strong>显式交片 → 剪辑</strong>
          <p>将离开视频三层，打开顶栏「剪辑」多轨 NLE。视频选区保留；不在本画布假装时间线。</p>
          <div className="media-ws__hero-actions">
            <Button type="button" onClick={() => { setSendConfirm(false); onSendToEdit(); }}>确认送去剪辑</Button>
            <Button type="button" onClick={() => setSendConfirm(false)}>取消</Button>
          </div>
        </div>
      )}

      {scriptOpen && (
        <section className="media-ws__layer media-ws__layer--script" aria-label="① 镜头脚本" data-video-layer="script">
          <VideoShotHeroStrip selectedId={selectedShot} onSelect={setSelectedShot} />
          <details className="media-ws__screenplay-outbound" data-screenplay-outbound="true">
            <summary>影视剧本 · 外出（≠ Shot 英雄条 · 不替换画布）</summary>
            <p className="media-ws__layer-note">
              完整影视剧本可侧开/外出；LUMEN_VIDEO_IA：脚本层＝Shot 卡，Screenplay 不糊进英雄条。
            </p>
            <div className="media-ws__panel">
              <ScreenplayPanel novelId={novelId} onInspect={onInspect as never} />
            </div>
          </details>
        </section>
      )}

      <section className="media-ws__hero media-ws__layer--canvas" aria-label="② 无限画布" data-video-layer="canvas">
        <span className="media-ws__hero-label">② 无限画布 · hero（VIDEO 作用域）</span>
        <strong>创意编排主表面</strong>
        <p>节点与素材引用。≠ 剪辑多轨 · ≠ 全 Studio mega-graph · 导演不挂小说。</p>
        <div className="media-ws__canvas-host">
          <MultimodalDirectorWorkspace mode="video" novelId={novelId} />
        </div>
      </section>

      {!directorOpen && (
        <div className="media-ws__director-entry" aria-label="导演台入口">
          <strong>③ 内置导演台</strong>
          <p>建议 → 确认采用；仅属视频工作区。普通模式可收为入口；专业可钉住。</p>
          <Button type="button" data-director-entry="true" onClick={() => setDirectorOpen(true)}>打开内置导演台</Button>
        </div>
      )}

      {directorOpen && (
        <section className="media-ws__layer media-ws__layer--director" aria-label="③ 内置导演台" data-video-layer="director">
          <span className="media-ws__hero-label">③ 内置导演台 · 可识别入口</span>
          <div className="media-ws-cta">
            <strong>导演下一步</strong>
            <p>建议与采用确认在 MultimodalDirector（video）内完成。选中 Shot：{selectedShot}（壳示意）。</p>
            <p className="media-ws-rail__hint">导演不挂小说主面；改镜头请留在视频工作区，成片组装请显式「送去剪辑」。</p>
            <div className="media-ws__hero-actions">
              <Button type="button" onClick={() => setDirectorOpen(false)}>收起导演台</Button>
              {onSendToEdit && (
                <Button type="button" data-send-edit="true" onClick={() => setSendConfirm(true)}>送去剪辑（交片）</Button>
              )}
            </div>
          </div>
        </section>
      )}

      <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-08] Shot 英雄条独立 · 三层可辨 · 禁止 NLE 冒充本区主 Tab · 禁假绿。</p>
    </div>
  );
}

export function VideoEmptyCta({onSendToEdit}: {onSendToEdit?: () => void}): ReactNode {
  return (
    <div className="media-ws-cta" aria-label="视频下一步">
      <strong>下一步</strong>
      <p>暂无选中镜头任务。可在画布选节点、展开导演台，或显式送去剪辑做多轨。</p>
      {onSendToEdit && <Button type="button" data-send-edit="true" onClick={onSendToEdit}>送去剪辑</Button>}
    </div>
  );
}
