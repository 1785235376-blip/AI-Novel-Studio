/**
 * [HERMIA-FE-20261022] Lightweight ModuleSwitcher shells for IMAGE / AUDIO / ASSETS.
 * Align LUMEN_IMAGE_IA · LUMEN_AUDIO_IA · LUMEN_ASSETS_IA. Compose existing panels; no backend invention.
 * VIDEO (三层) and EDIT (NLE) stay on their own routes — not reused here.
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
import {AssetLibraryPanel} from '../novel/AssetLibraryPanel';
import type {Asset} from '../api';
import type {ImageInspection} from '../novel/ImageTaskInspector';
import type {AudioInspection} from '../novel/AudioTaskInspector';
import type {StudioModule} from './moduleRegistry';
import './MediaWorkspaceShells.css';

export function ImageWorkspaceRail() {
  return (
    <nav className="media-ws-rail" aria-label="图片工作区导航">
      <div className="media-ws-rail__eyebrow">图片</div>
      <strong>视觉素材</strong>
      <ul>
        <li>参考图</li>
        <li>生成任务</li>
        <li>画面分析</li>
      </ul>
      <p className="media-ws-rail__hint">漫画＝图片 › 子入口（不升顶栏）。≠ 视频三层 · ≠ 剪辑 NLE · 不进小说中区。</p>
      <p className="media-ws-rail__hint">专业可展开创作画布（仍属 IMAGE 作用域）。</p>
    </nav>
  );
}

export function ImageWorkspaceShell({
  novelId, inspection, onInspect,
}: {
  novelId: string;
  inspection?: ImageInspection;
  onInspect: (i?: ImageInspection) => void;
}) {
  return (
    <div className="media-ws" aria-label="图片工作区">
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

export function AudioWorkspaceShell({
  novelId, onInspect, onSendToEdit,
}: {
  novelId: string;
  onInspect: (i: AudioInspection) => void;
  onSendToEdit?: () => void;
}) {
  return (
    <div className="media-ws" aria-label="声音工作区">
      <div className="media-ws__hero" aria-label="波形与配音检听">
        <span className="media-ws__hero-label">波形 / 配音 · hero</span>
        <div className="media-ws-wave" aria-hidden="true" />
        <strong>检听工作区</strong>
        <p>单条或批次波形示意。多轨对齐画面与成片导出请显式前往「剪辑」。</p>
        <small>项目 {novelId} · LUMEN_AUDIO_IA</small>
      </div>
      <div className="media-ws__toolbar" role="toolbar" aria-label="声音工具条">
        <Button type="button" disabled title="检听控件随真实音频结果启用">播放</Button>
        <Button type="button" disabled title="选区示意">选区</Button>
        {onSendToEdit && <Button type="button" onClick={onSendToEdit}>送去剪辑</Button>}
      </div>
      <div className="media-ws__body media-ws__body--split">
        <section className="media-ws__panel" aria-label="语音合成">
          <h3>语音合成</h3>
          <SpeechSynthesisPanel novelId={novelId} onInspect={onInspect} />
        </section>
        <section className="media-ws__panel" aria-label="音效生成">
          <h3>音效 / 音乐</h3>
          <AudioGenerationPanel novelId={novelId} />
        </section>
        <section className="media-ws__panel" aria-label="有声书">
          <h3>有声书清单</h3>
          <AudiobookManifestPanel novelId={novelId} onInspect={onInspect} />
        </section>
      </div>
      <p className="media-ws__foot notice">[HERMIA-FE-20261022] 声音 ≠ 剪辑 NLE · 交片须显式导航。</p>
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

export function AssetsWorkspaceShell({
  novelId, selectedAssetId, onSelectAsset,
}: {
  novelId: string;
  selectedAssetId?: string;
  onSelectAsset: (asset: Asset | undefined) => void;
}) {
  return (
    <div className="media-ws" aria-label="资产工作区">
      <div className="media-ws__hero" aria-label="资产浏览器说明">
        <span className="media-ws__hero-label">资产浏览器 · hero</span>
        <strong>共享库</strong>
        <p>查找、筛选、检视与建立引用。生图主路径在「图片」；多轨在「剪辑」。</p>
        <small>项目 {novelId} · LUMEN_ASSETS_IA · 引用语义</small>
      </div>
      <div className="media-ws__body">
        <section className="media-ws__panel" aria-label="资产库">
          <AssetLibraryPanel
            novelId={novelId}
            selectedAssetId={selectedAssetId}
            onSelectAsset={onSelectAsset}
          />
        </section>
      </div>
      <p className="media-ws__foot notice">[HERMIA-FE-20261022] ASSETS＝共享引用层，≠ IMAGE 生图台 ≠ EDIT 媒体池主面。</p>
    </div>
  );
}

/** Empty-selection CTA blocks for inspectors (禁空白占位). */
export function ImageEmptyCta({onScrollGenerate}: {onScrollGenerate?: () => void}): ReactNode {
  return (
    <div className="media-ws-cta" aria-label="图片下一步">
      <strong>下一步</strong>
      <p>暂无选中任务。可新建生成、加参考，或打开漫画子入口（图片工作区内）。</p>
      {onScrollGenerate && <Button type="button" onClick={onScrollGenerate}>去图片生成</Button>}
    </div>
  );
}

export function AudioEmptyCta({onSendToEdit}: {onSendToEdit?: () => void}): ReactNode {
  return (
    <div className="media-ws-cta" aria-label="声音下一步">
      <strong>下一步</strong>
      <p>暂无选中声音任务。可新建配音 / 音效 / 有声书条目；成片组装请送去剪辑。</p>
      {onSendToEdit && <Button type="button" onClick={onSendToEdit}>送去剪辑</Button>}
    </div>
  );
}

export function AssetsEmptyCta(): ReactNode {
  return (
    <div className="media-ws-cta" aria-label="资产下一步">
      <strong>下一步</strong>
      <p>未选中资产。可导入或筛选库；拖出到其它模块＝引用，不复制。</p>
    </div>
  );
}

// silence unused if tree-shaken — keep hook for future comic tab
export function useMediaShellTab(initial: string) {
  return useState(initial);
}
