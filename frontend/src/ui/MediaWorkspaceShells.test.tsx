// @vitest-environment jsdom
/**
 * [HERMIA-FE-20261022] IMAGE / AUDIO / ASSETS lightweight shells (Lumen IA).
 * W-UX-10: IMAGE comic sub-entry + thicker hero.
 */
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {
  ImageWorkspaceShell, ImageWorkspaceRail, ImageEmptyCta,
  AudioWorkspaceShell, AudioWorkspaceRail, AudioEmptyCta,
  AssetsWorkspaceShell, AssetsWorkspaceRail, AssetsEmptyCta,
  VideoWorkspaceShell, VideoWorkspaceRail, VideoEmptyCta, VideoShotHeroStrip,
} from './MediaWorkspaceShells';
import {ModuleWorkspaceRoutes} from './ModuleWorkspaceRoutes';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement;
afterEach(() => { host?.remove(); });

vi.mock('../novel/ImageGenerationPanel', () => ({ImageGenerationPanel: () => <div>mock-image-gen</div>}));
vi.mock('../novel/VisualContextPanel', () => ({VisualContextPanel: () => <div>mock-visual</div>}));
vi.mock('../novel/VisionAnalysisPanel', () => ({VisionAnalysisPanel: () => <div>mock-vision</div>}));
vi.mock('../novel/MultimodalDirectorWorkspace', () => ({
  MultimodalDirectorWorkspace: ({mode}: {mode?: string}) => <div>{`mock-director-${mode || 'x'}`}</div>,
}));
vi.mock('../novel/SpeechSynthesisPanel', () => ({SpeechSynthesisPanel: () => <div>mock-speech</div>}));
vi.mock('../novel/AudioGenerationPanel', () => ({AudioGenerationPanel: () => <div>mock-audio-gen</div>}));
vi.mock('../novel/AudiobookManifestPanel', () => ({AudiobookManifestPanel: () => <div>mock-audiobook</div>}));
vi.mock('../novel/AssetLibraryPanel', () => ({AssetLibraryPanel: () => <div>mock-asset-library</div>}));
vi.mock('../novel/ScreenplayPanel', () => ({ScreenplayPanel: () => <div>mock-screenplay</div>}));
vi.mock('./CapabilityStatusCenter', () => ({CapabilityStatusCenter: () => null}));

describe('MediaWorkspaceShells', () => {
  it('IMAGE shell: preview hero + generation panels; comic sub-entry; not NLE/video triad', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(<><ImageWorkspaceRail /><ImageWorkspaceShell novelId="n1" onInspect={vi.fn()} /><ImageEmptyCta onOpenComic={vi.fn()} /></>));
    expect(host.textContent).toContain('图像预览');
    expect(host.textContent).toContain('mock-image-gen');
    expect(host.textContent).toContain('mock-visual');
    expect(host.textContent).toMatch(/≠ 视频|≠ 剪辑|LUMEN_IMAGE|≠ VIDEO|≠ EDIT|≠ NLE/);
    expect(host.textContent).not.toContain('多轨时间线主表面');
    expect(host.querySelector('[data-open-comic="true"]')).toBeTruthy();
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.getAttribute('data-open-comic') === 'true')?.click();
    });
    expect(host.textContent).toContain('漫画制作');
    expect(host.textContent).toMatch(/子入口|不升/);
    expect(host.querySelector('.media-ws--video')).toBeNull();
    act(() => root.unmount());
  });

  it('W-UX-10 IMAGE comic sub-entry clickable from rail+toolbar; thicker hero; ≠ VIDEO/EDIT; no fake ready', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    const onSubview = vi.fn();
    act(() => root.render(
      <>
        <ImageWorkspaceRail subview="studio" onSubviewChange={onSubview} />
        <ImageWorkspaceShell novelId="n1" onInspect={vi.fn()} subview="studio" onSubviewChange={onSubview} />
      </>,
    ));
    // Thicker studio hero
    expect(host.querySelector('[data-image-hero="preview"]')).toBeTruthy();
    expect(host.querySelector('[data-image-hero-cta="true"]')).toBeTruthy();
    expect(host.querySelector('[data-image-cta="generate"]')).toBeTruthy();
    expect(host.querySelector('[data-image-cta="comic"]')).toBeTruthy();
    expect(host.querySelector('[data-image-badge="boundary"]')).toBeTruthy();
    expect(host.querySelector('[data-image-badge="no-chrome7"]')).toBeTruthy();
    expect(host.querySelectorAll('[data-image-thumb]').length).toBeGreaterThanOrEqual(3);
    expect(host.textContent).toMatch(/≠ VIDEO|≠ EDIT|≠ NLE/);
    expect(host.querySelector('[data-video-layer]')).toBeNull();
    expect(host.querySelector('[data-nle-tracks]')).toBeNull();
    expect(host.querySelectorAll('.nle-row').length).toBe(0);
    expect(host.textContent).not.toMatch(/已就绪/);

    // Rail comic entry
    act(() => {
      (host.querySelector('[data-image-sub="comic"]') as HTMLButtonElement)?.click();
    });
    expect(onSubview).toHaveBeenCalledWith('comic');

    // Controlled comic surface
    act(() => root.render(
      <>
        <ImageWorkspaceRail subview="comic" onSubviewChange={onSubview} />
        <ImageWorkspaceShell novelId="n1" onInspect={vi.fn()} subview="comic" onSubviewChange={onSubview} />
      </>,
    ));
    expect(host.querySelector('[data-image-comic="true"]')).toBeTruthy();
    expect(host.querySelector('[data-image-hero="comic"]')).toBeTruthy();
    expect(host.querySelector('.media-ws__comic-page')).toBeTruthy();
    expect(host.querySelectorAll('.media-ws__comic-cell').length).toBeGreaterThanOrEqual(3);
    expect(host.querySelectorAll('[data-comic-page-tab]').length).toBe(4);
    expect(host.textContent).toMatch(/不升|子入口/);
    expect(host.textContent).toMatch(/≠ VIDEO|≠ EDIT|≠ NLE/);
    expect(host.textContent).not.toMatch(/已就绪/);

    // Page strip switchable
    act(() => {
      (host.querySelector('[data-comic-page-tab="p2"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('[data-comic-page="p2"]')).toBeTruthy();
    expect(host.textContent).toContain('第 2 页');

    // Honest gen notice (not fake ready)
    act(() => {
      (host.querySelector('[data-comic-action="gen-cell"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('[data-comic-notice="true"]')?.textContent).toMatch(/待接通|未派发/);
    expect(host.querySelector('[data-comic-notice="true"]')?.textContent).not.toMatch(/已就绪/);

    // Return path
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.textContent?.includes('返回图片生成'))?.click();
    });
    expect(onSubview).toHaveBeenCalledWith('studio');
    act(() => root.unmount());
  });

  it('W-UX-10 ModuleWorkspaceRoutes syncs IMAGE rail ↔ shell comic subview', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    const scope = {workspace: 'w', project: 'p', storyline: 's', branch: 'b'};
    act(() => root.render(
      <ModuleWorkspaceRoutes module="IMAGE" onModuleChange={vi.fn()} scope={scope} actor="author" novelId="novel-1" />,
    ));
    expect(host.querySelector('[data-image-hero="preview"]')).toBeTruthy();
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('IMAGE');
    // chrome stays 6 modules — IMAGE workspace, not a 7th top button
    const chrome = host.querySelector('[data-module-switcher], [aria-label*="模块"], .module-switcher, nav[aria-label*="工作区"]');
    void chrome;
    act(() => {
      (host.querySelector('.media-ws-rail [data-image-sub="comic"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('[data-image-subview="comic"]')).toBeTruthy();
    expect(host.querySelector('[data-image-comic="true"]')).toBeTruthy();
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.textContent?.includes('返回图片生成'))?.click();
    });
    expect(host.querySelector('[data-image-subview="studio"]')).toBeTruthy();
    expect(host.querySelector('[data-image-hero="preview"]')).toBeTruthy();
    expect(host.querySelector('[data-video-layer]')).toBeNull();
    act(() => root.unmount());
  });

  it('AUDIO shell: waveform hero + speech/gen/manifest; send-confirm; 0 fake NLE tracks', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    const send = vi.fn();
    act(() => root.render(
      <><AudioWorkspaceRail onSendToEdit={send} /><AudioWorkspaceShell novelId="n1" onInspect={vi.fn()} onSendToEdit={send} /><AudioEmptyCta onSendToEdit={send} /></>,
    ));
    expect(host.textContent).toContain('波形');
    expect(host.textContent).toContain('mock-speech');
    expect(host.textContent).toContain('mock-audiobook');
    expect(host.textContent).toContain('Speech');
    expect(host.textContent).toContain('Audiobook');
    expect(host.querySelector('[data-nle-tracks="0"]')).toBeTruthy();
    expect(host.textContent).toMatch(/送去剪辑/);
    expect(host.textContent).toMatch(/AUDIO ≠ EDIT|≠ 剪辑|0 条假 NLE|0 假轨/);
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.getAttribute('data-send-edit') === 'true')?.click();
    });
    expect(host.textContent).toContain('显式交片');
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.textContent?.includes('确认送去剪辑'))?.click();
    });
    expect(send).toHaveBeenCalled();
    act(() => root.unmount());
  });


  it('VIDEO shell: three layers script/canvas/director; Shot strip; explicit send-edit; ≠ NLE', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    const send = vi.fn();
    act(() => root.render(
      <><VideoWorkspaceRail onSendToEdit={send} /><VideoWorkspaceShell novelId="n1" onSendToEdit={send} /><VideoEmptyCta onSendToEdit={send} /></>,
    ));
    expect(host.textContent).toContain('镜头脚本');
    expect(host.textContent).toContain('无限画布');
    expect(host.textContent).toContain('导演台');
    expect(host.textContent).toContain('mock-director-video');
    expect(host.querySelector('.media-ws__shot-strip')).toBeTruthy();
    expect(host.querySelector('[data-shot-id="s1"]')).toBeTruthy();
    expect(host.textContent).toMatch(/送去剪辑/);
    expect(host.textContent).toMatch(/VIDEO ≠ EDIT|≠ 剪辑|禁止 NLE/);
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.getAttribute('data-send-edit') === 'true')?.click();
    });
    expect(host.textContent).toContain('显式交片');
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.textContent?.includes('确认送去剪辑'))?.click();
    });
    expect(send).toHaveBeenCalled();
    act(() => root.unmount());
  });

  it('W-UX-08 VIDEO Shot hero independent of Screenplay; read-only DirectorShot; ≠ NLE; no fake ready', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    const send = vi.fn();
    act(() => root.render(
      <VideoWorkspaceShell novelId="n1" onSendToEdit={send} shellMode="basic" />,
    ));
    const hero = host.querySelector('[data-shot-hero="true"]');
    expect(hero).toBeTruthy();
    expect(host.querySelector('[data-video-layer="script"]')).toBeTruthy();
    expect(host.querySelector('[data-video-layer="canvas"]')).toBeTruthy();
    // director collapsed in basic — entry still names layer ③
    expect(host.textContent).toContain('③ 内置导演台');
    expect(host.querySelector('[data-director-shot-readonly="true"]')).toBeTruthy();
    expect(host.querySelector('[data-screenplay-outbound="true"]')).toBeTruthy();
    // Screenplay not mashed inside Shot hero
    expect(hero!.querySelector('[data-screenplay-outbound="true"]')).toBeNull();
    expect(hero!.textContent).not.toContain('mock-screenplay');
    expect(host.textContent).toMatch(/≠ 影视剧本/);
    expect(host.textContent).toMatch(/候选|草稿|演示/);
    expect(host.textContent).not.toMatch(/已就绪/);
    expect(host.querySelectorAll('.nle-row').length).toBe(0);
    expect(host.querySelector('[data-nle-tracks]')).toBeNull();
    // select another shot updates readonly summary
    act(() => {
      (host.querySelector('[data-shot-id="s3"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('[data-director-shot-readonly="true"]')?.textContent).toContain('窗外远景');
    // send-edit still explicit confirm
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.getAttribute('data-send-edit') === 'true')?.click();
    });
    expect(host.textContent).toContain('显式交片');
    expect(send).not.toHaveBeenCalled();
    act(() => {
      [...host.querySelectorAll('button')].find(b => b.textContent?.includes('确认送去剪辑'))?.click();
    });
    expect(send).toHaveBeenCalledTimes(1);
    act(() => root.unmount());
  });

  it('W-UX-08 VideoShotHeroStrip exposes DirectorShot-aligned read-only fields', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    const onSelect = vi.fn();
    act(() => root.render(<VideoShotHeroStrip selectedId="s2" onSelect={onSelect} />));
    expect(host.querySelector('[data-shot-hero="true"]')).toBeTruthy();
    expect(host.querySelector('[data-shot-id="s2"]')?.getAttribute('aria-pressed')).toBe('true');
    expect(host.querySelector('[data-director-shot-readonly="true"]')?.textContent).toMatch(/走廊回头/);
    expect(host.querySelector('[data-director-shot-readonly="true"]')?.textContent).toMatch(/运镜|近景/);
    act(() => {
      (host.querySelector('[data-shot-id="s1"]') as HTMLButtonElement)?.click();
    });
    expect(onSelect).toHaveBeenCalledWith('s1');
    act(() => root.unmount());
  });
  it('ASSETS shell: browser hero + library; lineage summary; drag=reference; ≠ IMAGE desk', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(
      <><AssetsWorkspaceRail /><AssetsWorkspaceShell novelId="n1" onSelectAsset={vi.fn()} /><AssetsEmptyCta /></>,
    ));
    expect(host.textContent).toContain('资产浏览器');
    expect(host.textContent).toContain('mock-asset-library');
    expect(host.textContent).toMatch(/引用/);
    expect(host.textContent).toContain('血缘');
    expect(host.querySelector('[data-drag-semantics="reference"]')).toBeTruthy();
    expect(host.textContent).toMatch(/不是生图台|≠ IMAGE/);
    expect(host.textContent).toMatch(/诚实|未选中/);
    act(() => root.unmount());
  });
});

describe('ModuleWorkspaceRoutes media shells', () => {
  const scope = {workspace: 'w', project: 'p', storyline: 's', branch: 'b'};
  it.each(['IMAGE', 'AUDIO', 'ASSETS'] as const)('mounts %s shell when novel open', (module) => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(
      <ModuleWorkspaceRoutes module={module} onModuleChange={vi.fn()} scope={scope} actor="author" novelId="novel-1" />,
    ));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe(module);
    expect(host.querySelector('.media-ws') || host.querySelector('[data-module-shell]')).toBeTruthy();
    act(() => root.unmount());
  });

  it('keeps VIDEO three-layer shell distinct from IMAGE preview shell', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(
      <ModuleWorkspaceRoutes module="IMAGE" onModuleChange={vi.fn()} scope={scope} actor="author" novelId="novel-1" />,
    ));
    expect(host.textContent).toContain('图像预览');
    expect(host.querySelector('.media-ws--video')).toBeNull();
    act(() => root.unmount());
    host.remove();
    host = document.createElement('div'); document.body.append(host);
    const root2 = createRoot(host);
    act(() => root2.render(
      <ModuleWorkspaceRoutes module="VIDEO" onModuleChange={vi.fn()} scope={scope} actor="author" novelId="novel-1" />,
    ));
    expect(host.querySelector('.media-ws--video')).toBeTruthy();
    expect(host.textContent).toContain('镜头脚本');
    expect(host.querySelector('[data-shot-hero="true"]')).toBeTruthy();
    expect(host.textContent).toContain('mock-director-video');
    expect(host.textContent).not.toContain('图像预览 · hero');
    act(() => root2.unmount());
  });
});

describe('X-UX-04 shellMode consistency', () => {
  it('IMAGE pro canvas opens in pro and collapses in basic', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(<ImageWorkspaceShell novelId="n1" shellMode="pro" onInspect={vi.fn()} />));
    const pro = host.querySelector('[data-pro-canvas="true"]') as HTMLDetailsElement;
    expect(pro).toBeTruthy();
    expect(pro.open).toBe(true);
    expect(host.querySelector('[data-shell-mode="pro"]')).toBeTruthy();
    act(() => root.render(<ImageWorkspaceShell novelId="n1" shellMode="basic" onInspect={vi.fn()} />));
    const basic = host.querySelector('[data-pro-canvas="true"]') as HTMLDetailsElement;
    expect(basic.open).toBe(false);
    expect(host.querySelector('[data-shell-mode="basic"]')).toBeTruthy();
    act(() => root.unmount());
  });

  it('VIDEO director follows shellMode without inventing selection', () => {
    host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(<VideoWorkspaceShell novelId="n1" shellMode="basic" />));
    expect(host.querySelector('[data-shell-mode="basic"]')).toBeTruthy();
    expect(host.querySelector('[aria-label="③ 内置导演台"]')).toBeNull();
    act(() => root.render(<VideoWorkspaceShell novelId="n1" shellMode="pro" />));
    expect(host.querySelector('[data-shell-mode="pro"]')).toBeTruthy();
    expect(host.querySelector('[aria-label="③ 内置导演台"]')).toBeTruthy();
    act(() => root.unmount());
  });
});
