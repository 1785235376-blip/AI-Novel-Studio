/**
 * [HERMIA-FE-20261022] Lightweight ModuleSwitcher shells for IMAGE / AUDIO / ASSETS / VIDEO.
 * Align LUMEN_IMAGE_IA · LUMEN_AUDIO_IA · LUMEN_ASSETS_IA · LUMEN_VIDEO_IA.
 * Compose existing panels; no backend invention.
 * W-UX-01: IMAGE preview hero + comic sub-entry; pro canvas collapsed.
 * W-UX-04: VIDEO three-layer thickening — Shot strip + canvas hero + director entry; ≠ EDIT.
 * W-UX-02: AUDIO waveform hero + Speech/AudioGen/Manifest + send-edit confirm; 0 fake NLE tracks.
 * W-UX-03: ASSETS browser hero + Inspector lineage/version summary; drag=reference; ≠ IMAGE desk.
 */
import {useState, type ReactNode} from 'react';
import {Button} from './primitives';
import {ImageGenerationPanel} from '../novel/ImageGenerationPanel';
import {VisualContextPanel} from '../novel/VisualContextPanel';
import {VisionAnalysisPanel} from '../novel/VisionAnalysisPanel';
import {MultimodalDirectorWorkspace} from '../novel/MultimodalDirectorWorkspace';
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

/** Demo / empty shot cards for VIDEO script strip — UI discovery only; no invent write API. */
const DEMO_SHOT_STRIP = [
  {id: 's1', number: 1, title: '开场推门', dialogue: '……'},
  {id: 's2', number: 2, title: '走廊回头', dialogue: '谁？'},
  {id: 's3', number: 3, title: '窗外远景', dialogue: ''},
  {id: 's4', number: 4, title: '切近特写', dialogue: '先别动。'},
] as const;

export function ImageWorkspaceShell({
  novelId, inspection, onInspect,
}: {
  novelId: string;
  inspection?: ImageInspection;
  onInspect: (i?: ImageInspection) => void;
}) {
  const [subview, setSubview] = useState<'studio' | 'comic'>('studio');
  return (
    <div className="media-ws" aria-label="图片工作区" data-image-subview={subview}>
      <div className="media-ws__toolbar" role="toolbar" aria-label="图片子入口">
        <Button type="button" aria-pressed={subview === 'studio'} onClick={() => setSubview('studio')}>
          图片工作台
        </Button>
        <Button type="button" aria-pressed={subview === 'comic'} data-open-comic="true" onClick={() => setSubview('comic')}>
          漫画制作
        </Button>
        <small>项目 {novelId} · LUMEN_IMAGE_IA · 漫画不升顶栏</small>
      </div>

      {subview === 'comic' ? (
        <div className="media-ws__comic" aria-label="漫画子入口">
          <div className="media-ws__hero media-ws__hero--comic" aria-label="漫画预览">
            <span className="media-ws__hero-label">图片 › 漫画制作 · 子入口</span>
            <strong>漫画分格 / 气泡 / 书册</strong>
            <p>挂在图片工作区内，不升第 7 顶栏钮。完整漫画编辑器沿用原项目授权与 StudioComic 能力；此处为壳向发现入口（W-UX-01）。</p>
            <small>≠ VIDEO 三层 · ≠ EDIT NLE · 不进小说中区</small>
          </div>
          <div className="media-ws-cta" aria-label="漫画下一步">
            <strong>下一步</strong>
            <p>可新建空白页、编辑分格或组织书册。需要独立工作室权限时，请从已授权项目打开漫画制作全屏面。</p>
            <Button type="button" onClick={() => setSubview('studio')}>返回图片生成 / 参考</Button>
          </div>
          <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-01] 漫画＝IMAGE 子入口。</p>
        </div>
      ) : (
        <>
          <div className="media-ws__hero" aria-label="图像预览">
            <span className="media-ws__hero-label">图像预览 · hero</span>
            {inspection?.assetUri ? (
              <img className="media-ws__hero-preview" src={inspection.assetUri} alt="当前图片生成结果" referrerPolicy="no-referrer" />
            ) : (
              <>
                <strong>{inspection ? `任务 ${inspection.status}` : '尚无预览'}</strong>
                <p>提交生成或从历史选择真实结果。主表面是预览，不是视频导演台，也不是多轨时间线。</p>
              </>
            )}
            <div className="media-ws__hero-actions">
              {!inspection?.assetUri && (
                <>
                  <Button type="button" onClick={() => document.querySelector('.media-ws__panel[aria-label="图片生成"]')?.scrollIntoView({block: 'nearest'})}>新建生成</Button>
                  <Button type="button" onClick={() => document.querySelector('.media-ws__panel[aria-label="视觉上下文"]')?.scrollIntoView({block: 'nearest'})}>加参考</Button>
                  <Button type="button" data-open-comic="true" onClick={() => setSubview('comic')}>打开漫画</Button>
                </>
              )}
            </div>
            <small>项目 {novelId} · LUMEN_IMAGE_IA</small>
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
          <details className="media-ws__pro">
            <summary>专业 · 创作画布（IMAGE 作用域 · 非视频三层）</summary>
            <MultimodalDirectorWorkspace mode="image" novelId={novelId} />
          </details>
          <p className="media-ws__foot notice">[HERMIA-FE-20261022] 图片 ≠ 小说中区 · ≠ VIDEO · ≠ EDIT。</p>
        </>
      )}
    </div>
  );
}

export function AudioWorkspaceRail({onSendToEdit}: {onSendToEdit?: () => void}) {
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
        <button type="button" className="media-ws-rail__item" onClick={onSendToEdit}>送去剪辑（显式）</button>
      )}
      <p className="media-ws-rail__hint">AUDIO ≠ EDIT：本区是波形/配音工作区，不做多轨 NLE hero。</p>
    </nav>
  );
}

/** [HERMIA-FE-20261022 W-UX-02] AUDIO = waveform/dubbing workspace; ≠ EDIT NLE (0 fake tracks). */
export function AudioWorkspaceShell({
  novelId, onInspect, onSendToEdit,
}: {
  novelId: string;
  onInspect: (i: AudioInspection) => void;
  onSendToEdit?: () => void;
}) {
  const [focus, setFocus] = useState<'speech' | 'gen' | 'manifest'>('speech');
  const [sendConfirm, setSendConfirm] = useState(false);

  return (
    <div
      className="media-ws media-ws--audio"
      aria-label="声音工作区"
      data-audio-hero="waveform"
      data-nle-tracks="0"
    >
      <div className="media-ws__hero media-ws__hero--audio" aria-label="波形与配音检听">
        <span className="media-ws__hero-label">波形 / 配音 · hero · 非 NLE</span>
        <div className="media-ws-wave" aria-hidden="true">
          <span className="media-ws-wave__playhead" />
        </div>
        <strong>检听工作区</strong>
        <p>单条或批次波形示意（本区检听）。多轨对齐画面、字幕轨与成片导出请显式「送去剪辑」——本壳 <strong>0 条假 NLE 轨</strong>。</p>
        <div className="media-ws__hero-actions">
          <Button type="button" aria-pressed={focus === 'speech'} data-audio-focus="speech" onClick={() => setFocus('speech')}>Speech 配音</Button>
          <Button type="button" aria-pressed={focus === 'gen'} data-audio-focus="gen" onClick={() => setFocus('gen')}>AudioGen 音效</Button>
          <Button type="button" aria-pressed={focus === 'manifest'} data-audio-focus="manifest" onClick={() => setFocus('manifest')}>Audiobook 清单</Button>
        </div>
        <small>项目 {novelId} · LUMEN_AUDIO_IA · AUDIO ≠ EDIT</small>
      </div>
      <div className="media-ws__toolbar" role="toolbar" aria-label="声音工具条">
        <Button type="button" disabled title="检听控件随真实音频结果启用">播放</Button>
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
        <small>假 NLE 轨：0</small>
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
      <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-02] 声音 ≠ 剪辑 NLE · 0 假轨 · 交片须显式确认。</p>
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
  return (
    <div className="media-ws-cta" aria-label="声音下一步" data-honest-kind="empty_selection">
      <strong>下一步</strong>
      <p>暂无选中声音任务。可新建配音 / 音效 / 有声书条目；成片组装请显式送去剪辑（本区无假 NLE 轨）。</p>
      {onSendToEdit && <Button type="button" data-send-edit="true" onClick={onSendToEdit}>送去剪辑</Button>}
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
        <li>① 镜头脚本</li>
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

/** [HERMIA-FE-20261022 W-UX-04] LUMEN_VIDEO_IA three layers thickened — Shot strip + canvas hero + director entry. */
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

  return (
    <div className="media-ws media-ws--video" aria-label="视频工作区 · 三层" data-video-layers="script-canvas-director">
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
        <section className="media-ws__layer media-ws__layer--script" aria-label="① 镜头脚本">
          <span className="media-ws__hero-label">① 镜头脚本 · Shot 卡条</span>
          <p className="media-ws__layer-note">分镜 / Shot 在画布上方；卡条为壳向发现（演示数据）。真实 Shot 写入走导演 / 剧本面板，不编造 API。</p>
          <div className="media-ws__shot-strip" role="list" aria-label="Shot 卡条">
            {DEMO_SHOT_STRIP.map(shot => (
              <button
                type="button"
                key={shot.id}
                role="listitem"
                className={`media-ws__shot-card${selectedShot === shot.id ? ' is-selected' : ''}`}
                aria-pressed={selectedShot === shot.id}
                data-shot-id={shot.id}
                onClick={() => setSelectedShot(shot.id)}
              >
                <span className="media-ws__shot-num">S{shot.number}</span>
                <strong>{shot.title}</strong>
                <small>{shot.dialogue || '（无对白）'}</small>
              </button>
            ))}
          </div>
          <div className="media-ws__panel">
            <ScreenplayPanel novelId={novelId} onInspect={onInspect as never} />
          </div>
        </section>
      )}

      <section className="media-ws__hero media-ws__layer--canvas" aria-label="② 无限画布">
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
        <section className="media-ws__layer media-ws__layer--director" aria-label="③ 内置导演台">
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

      <p className="media-ws__foot notice">[HERMIA-FE-20261022 W-UX-04] 视频三层加厚 · 禁止 NLE 冒充本区主 Tab。</p>
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
