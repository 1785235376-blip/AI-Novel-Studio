// @vitest-environment jsdom
/**
 * [HERMIA-FE-20261022 X-UX-10] Hand-off smoke (Atlas §0.12 fourth knife).
 * IMAGE→VIDEO · AUDIO→EDIT · ASSETS→IMAGE/VIDEO/AUDIO/EDIT
 * Novel center never mounts media/NLE · shellMode survives module switches
 * Ban fake green · no N-UX-04 · no EDIT default-writable change
 */
import {act, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {ModuleWorkspaceRoutes} from './ModuleWorkspaceRoutes';
import {clearEditHandoffs, readEditHandoffs} from './editHandoff';
import {clearVideoDirectorPins} from './MediaWorkspaceShells';
import {
  X_UX_10_FORBIDDEN_READY,
  X_UX_10_HANDOFF_PATHS,
  X_UX_10_NOVEL_CENTER_MARKERS,
  X_UX_10_SHELL_MODE_MODULES,
} from './handoffSmoke';
import type {StudioModule} from './moduleRegistry';
import {NOVEL_CENTER_FORBIDDEN_SELECTORS} from './moduleSwitchIsolation';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

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

const SCOPE = {workspace: 'w', project: 'p', storyline: 's', branch: 'b'};
const NOVEL = 'novel-xux10';

let host: HTMLDivElement;
afterEach(() => {
  host?.remove();
  clearEditHandoffs();
  clearVideoDirectorPins();
});

function HandoffHarness({
  initial,
  shellMode = 'pro',
}: {
  initial: StudioModule;
  shellMode?: 'basic' | 'pro';
}) {
  const [module, setModule] = useState<StudioModule>(initial);
  return (
    <ModuleWorkspaceRoutes
      module={module}
      onModuleChange={setModule}
      scope={SCOPE}
      actor="author"
      novelId={NOVEL}
      shellMode={shellMode}
    />
  );
}

function mount(initial: StudioModule, shellMode: 'basic' | 'pro' = 'pro') {
  host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  act(() => root.render(<HandoffHarness initial={initial} shellMode={shellMode} />));
  return root;
}

function assertNoNovelCenterLeak() {
  for (const sel of X_UX_10_NOVEL_CENTER_MARKERS) {
    expect(host.querySelector(sel)).toBeNull();
  }
  expect(host.querySelector('.app-shell')?.getAttribute('data-module')).not.toBe('NOVEL');
  expect(host.textContent || '').not.toMatch(X_UX_10_FORBIDDEN_READY);
}

describe('X-UX-10 handoff smoke paths', () => {
  it('exposes the six Atlas §0.12 handoff contracts', () => {
    expect(X_UX_10_HANDOFF_PATHS.map(p => `${p.from}→${p.to}`)).toEqual([
      'IMAGE→VIDEO',
      'AUDIO→EDIT',
      'ASSETS→IMAGE',
      'ASSETS→VIDEO',
      'ASSETS→AUDIO',
      'ASSETS→EDIT',
    ]);
    expect(X_UX_10_SHELL_MODE_MODULES).toEqual(['IMAGE', 'VIDEO', 'AUDIO', 'EDIT', 'ASSETS']);
  });

  it('IMAGE→VIDEO: confirm switches module; cancel stays; ≠ novel / ≠ NLE', () => {
    const root = mount('IMAGE', 'pro');
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('IMAGE');
    expect(host.querySelector('[data-module-shell="IMAGE"]')).toBeTruthy();
    expect(host.querySelector('[data-send-video="true"]')).toBeTruthy();
    assertNoNovelCenterLeak();

    act(() => {
      (host.querySelector('[data-image-cta="send-video"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('[data-send-video-dialog="true"]')).toBeTruthy();
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('IMAGE');

    act(() => {
      (host.querySelector('[data-send-video-cancel="true"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('IMAGE');
    expect(host.querySelector('[data-module-shell="VIDEO"]')).toBeNull();

    act(() => {
      (host.querySelector('[data-image-cta="send-video"]') as HTMLButtonElement)?.click();
    });
    act(() => {
      (host.querySelector('[data-send-video-confirm="true"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('VIDEO');
    expect(host.querySelector('[data-module-shell="VIDEO"]')).toBeTruthy();
    expect(host.querySelector('[data-module-shell="IMAGE"]')).toBeNull();
    expect(host.querySelector('.edit-nle-shell')).toBeNull();
    expect(host.querySelector('[data-nle-tracks]')).toBeNull();
    assertNoNovelCenterLeak();
    act(() => root.unmount());
  });

  it('AUDIO→EDIT: confirm pushes handoff + opens EDIT pool with AUDIO source strip', () => {
    const root = mount('AUDIO', 'basic');
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('AUDIO');
    expect(host.querySelector('[data-module-shell="AUDIO"]')).toBeTruthy();
    expect(readEditHandoffs()).toHaveLength(0);

    act(() => {
      // [HERMIA-FE-20261022 R4] 声音改挂 AudioRebuild：#audSendEdit → 确认框 → 确认送去
      (host.querySelector('#audSendEdit') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('[data-send-edit-dialog="true"]')).toBeTruthy();
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('AUDIO');

    act(() => {
      (host.querySelector('[data-send-edit-confirm="true"]') as HTMLButtonElement)?.click();
    });
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('EDIT');
    expect(host.querySelector('[data-module-shell="EDIT"]')).toBeTruthy();
    // [HERMIA-FE-20261022 R5] 剪辑改挂 EditRebuild：下段整宽时间线 + 上段媒体池
    expect(host.querySelector('.nle-tl[data-timeline-hero="true"]')).toBeTruthy();
    expect(host.querySelector('[data-edit-handoff="received"]')).toBeTruthy();
    expect(host.querySelector('[data-handoff-source="AUDIO"]')).toBeTruthy();
    expect(host.querySelector('[data-handoff-source-strip="true"]')).toBeTruthy();
    const inbox = readEditHandoffs();
    expect(inbox.some(h => h.source === 'AUDIO' && h.novelId === NOVEL)).toBe(true);
    // W-UX-09 demo-readonly still on
    expect(host.querySelector('[data-honest-badge="demo-readonly"]') || host.querySelector('[data-w-ux="09"]') || host.querySelector('[data-writable="false"]')).toBeTruthy();
    assertNoNovelCenterLeak();
    act(() => root.unmount());
  });

  // [HERMIA-FE-20261022 R6] 资产改挂 AssetsRebuild：选中一个真实资产 → 右栏「送到模块…」→ 选目标 → 确认后才切模块。
  it.each(['IMAGE', 'VIDEO', 'AUDIO', 'EDIT'] as const)(
    'ASSETS→%s: confirm switches; never NOVEL; EDIT also records handoff',
    async (target) => {
      clearEditHandoffs();
      const asset = {id: 'ast-1', novel_id: NOVEL, filename: '雾港参考.jpg', kind: 'image', media_type: 'image/jpeg', size: 10, sha256: 'x', created_at: '', updated_at: ''};
      vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
        url.includes('asset-trash') ? {items: [], total: 0} : url.includes('/references') ? {items: [], total: 0} : /\/assets(\?|$)/.test(url) ? [asset] : {}),
        {status: 200, headers: {'Content-Type': 'application/json'}}))));
      const root = mount('ASSETS', 'pro');
      expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('ASSETS');
      for (let i = 0; i < 40 && !host.querySelector('.ast-tile'); i++) await act(async () => { await new Promise(r => setTimeout(r, 10)); });
      act(() => { (host.querySelector('.ast-tile') as HTMLButtonElement).click(); });
      act(() => { (host.querySelector('#astSend') as HTMLButtonElement).click(); });
      act(() => { (host.querySelector(`[data-ast-send-target="${target}"]`) as HTMLButtonElement).click(); });
      expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('ASSETS');
      expect(host.querySelector('[data-ast-send-confirm="true"]')).toBeTruthy();
      act(() => { (host.querySelector('[data-ast-send-confirm="true"]') as HTMLButtonElement).click(); });
      expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe(target);
      expect(host.querySelector(`[data-module-shell="${target}"]`)).toBeTruthy();
      expect(host.querySelector('[data-module-shell="ASSETS"]')).toBeNull();
      if (target === 'EDIT') {
        expect(host.querySelector('[data-edit-handoff="received"]')).toBeTruthy();
        expect(host.querySelector('[data-handoff-source="ASSETS"]')).toBeTruthy();
        expect(readEditHandoffs().some(h => h.source === 'ASSETS' && h.label === '雾港参考.jpg')).toBe(true);
      }
      assertNoNovelCenterLeak();
      act(() => root.unmount());
      vi.unstubAllGlobals();
    },
  );
});

describe('X-UX-10 shellMode + novel isolation', () => {
  it('shellMode basic/pro survives IMAGE→VIDEO→AUDIO→EDIT→ASSETS remounts', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);

    for (const mode of ['pro', 'basic'] as const) {
      for (const mod of X_UX_10_SHELL_MODE_MODULES) {
        act(() => root.render(
          <ModuleWorkspaceRoutes
            module={mod}
            onModuleChange={vi.fn()}
            scope={SCOPE}
            actor="author"
            novelId={NOVEL}
            shellMode={mode}
          />,
        ));
        expect(host.querySelector('.app-shell')?.getAttribute('data-shell-mode')).toBe(mode);
        expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe(mod);
        expect(host.querySelector('[data-module-shell]')?.getAttribute('data-shell-mode')).toBe(mode);
        expect(host.querySelector('[data-x-ux-isolation="per-module"]')).toBeTruthy();
        assertNoNovelCenterLeak();
      }
    }
    act(() => root.unmount());
  });

  it('media destinations never mount novel-write-chrome or forbidden novel-center shells', () => {
    host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    for (const mod of X_UX_10_SHELL_MODE_MODULES) {
      act(() => root.render(
        <ModuleWorkspaceRoutes
          module={mod}
          onModuleChange={vi.fn()}
          scope={SCOPE}
          actor="author"
          novelId={NOVEL}
          shellMode="pro"
        />,
      ));
      expect(host.querySelector('.novel-write-chrome')).toBeNull();
      // only the active media shell marker is present
      for (const other of X_UX_10_SHELL_MODE_MODULES) {
        if (other === mod) {
          expect(host.querySelector(`[data-module-shell="${other}"]`)).toBeTruthy();
        } else {
          expect(host.querySelector(`[data-module-shell="${other}"]`)).toBeNull();
        }
      }
      if (mod !== 'EDIT') {
        expect(host.querySelector('.edit-nle-shell')).toBeNull();
      }
      expect(host.textContent || '').not.toMatch(X_UX_10_FORBIDDEN_READY);
    }
    // contract: App still early-returns ModuleWorkspaceRoutes for non-NOVEL
    const app = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    expect(app).toMatch(/if \(studioModule !== "NOVEL"\) return[\s\S]*<ModuleWorkspaceRoutes/);
    expect(app).toContain('shellMode={shellMode}');
    expect(NOVEL_CENTER_FORBIDDEN_SELECTORS.length).toBeGreaterThan(0);
    act(() => root.unmount());
  });

  it('does not touch N-UX-04 default / EDIT writable defaults in App wiring', () => {
    const app = readFileSync(resolve(__dirname, '../App.tsx'), 'utf8');
    const routes = readFileSync(resolve(__dirname, './ModuleWorkspaceRoutes.tsx'), 'utf8');
    expect(app).not.toMatch(/N-UX-04.*default.*false|defaultInspectorCollapsed\s*=\s*true/);
    // X-UX-10 must not flip EDIT inspector to writable
    expect(routes).toMatch(/editable=\{false\}/);
    expect(routes).toContain('X-UX-10');
  });
});
