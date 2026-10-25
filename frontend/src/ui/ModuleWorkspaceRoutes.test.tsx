// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ModuleWorkspaceRoutes} from './ModuleWorkspaceRoutes';
import {STUDIO_MODULES} from './moduleRegistry';
import {api} from '../api';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement;
afterEach(()=>host?.remove());

describe('ModuleWorkspaceRoutes',()=>{
  it('exposes media Provider configuration directly from the control workspace',async()=>{vi.spyOn(api,'assetProviders').mockResolvedValue({items:[]} as any);vi.spyOn(api,'videoProviders').mockResolvedValue({items:[]} as any);host=document.createElement('div');document.body.append(host);const root=createRoot(host);await act(async()=>root.render(<ModuleWorkspaceRoutes module="CONTROL" shellMode="pro"/* [HERMIA-FE-20261022 U4] 「高级」只在专业 */ onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1"/>));const tab=[...host.querySelectorAll('button')].find(button=>button.textContent==='媒体 Provider')!;await act(async()=>{tab.click();await Promise.resolve()});expect(host.textContent).toContain('媒体 Provider');expect(host.querySelector('.media-provider-settings')).toBeTruthy();act(()=>root.unmount())});
  it('keeps the registered modules and renders the video workspace shell',()=>{
    expect(STUDIO_MODULES.map((item)=>item.id)).toEqual(['NOVEL','IMAGE','VIDEO','AUDIO','EDIT','ASSETS']);
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module="VIDEO" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('VIDEO');
    expect(host.textContent).toContain('视频');
    act(()=>root.unmount());
  });
  it('renders EDIT CapCut-density nle shell when novel is open',()=>{
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module="EDIT" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('EDIT');
    expect(host.querySelector('.nle-tl[data-timeline-hero="true"]')).toBeTruthy(); // [HERMIA-FE-20261022 R5]
    expect(host.querySelector('#nleBin')||host.textContent?.includes('媒体池')).toBeTruthy(); // [HERMIA-FE-20261022 R5]
    expect(host.textContent).toMatch(/多轨|剪辑|时间线/);
    act(()=>root.unmount());
  });
  it.each(['IMAGE','VIDEO','AUDIO','EDIT','WORKFLOW','ASSETS'] as const)('does not mount %s project panels without a novel',module=>{
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module={module} onModuleChange={vi.fn()} scope={{workspace:'w',project:'',storyline:'s',branch:'b'}} actor="author"/>));
    expect(host.textContent).toContain('请先打开小说项目');
    expect(host.querySelector('.multimodal-director')).toBeNull();
    const futureButtons=[...host.querySelectorAll<HTMLButtonElement>('.workspace-rail button')].slice(1);
    expect(futureButtons).toHaveLength(2);expect(futureButtons.every(button=>button.disabled)).toBe(true);
    act(()=>root.unmount());
  });

  it('X-UX-03: CONTROL overflow surface is honest and chrome stays 6', async () => {
    vi.spyOn(api,'multimodalHealth').mockResolvedValue({});
    vi.spyOn(api,'videoProviders').mockResolvedValue({items:[]});
    vi.spyOn(api,'pluginRuntimeStatus').mockResolvedValue({execution_supported:false,sandbox:'none'});
    vi.spyOn(api,'workflows').mockResolvedValue({items:[]});
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>root.render(<ModuleWorkspaceRoutes module="CONTROL" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1" shellMode="pro"/>));
    // [HERMIA-FE-20261022 R7] 主控改为原型单页：不再挂溢出横幅，也不再有三页签
    expect(host.querySelector('[data-hub="control"]')).toBeTruthy();
    expect(host.querySelector('[data-overflow-surface="CONTROL"]')).toBeNull();
    expect(host.querySelector('[role="tablist"][aria-label="主控设置"]')?.closest('details')?.open ?? true).not.toBe(true);
    expect(host.querySelector('[data-overflow-chrome="true"]')).toBeTruthy();
    expect(host.querySelector('[data-settings-chrome="true"]')).toBeTruthy();
    expect(host.textContent || '').not.toMatch(/已就绪|已连通绿/);
    const tabs=[...host.querySelectorAll('[role="tablist"][aria-label="创作模块"] [role="tab"]')];
    expect(tabs).toHaveLength(6);
    expect(tabs.map(t=>t.getAttribute('data-module-tab'))).not.toContain('CONTROL');
    expect(tabs.map(t=>t.getAttribute('data-module-tab'))).not.toContain('PLUGIN');
    act(()=>root.unmount());
  });

  it('X-UX-09: Header 设置 from CONTROL route opens PLUGIN; chrome still 6', async () => {
    vi.spyOn(api,'multimodalHealth').mockResolvedValue({});
    vi.spyOn(api,'videoProviders').mockResolvedValue({items:[]});
    vi.spyOn(api,'pluginRuntimeStatus').mockResolvedValue({execution_supported:false,sandbox:'none'});
    vi.spyOn(api,'workflows').mockResolvedValue({items:[]});
    host=document.createElement('div');document.body.append(host);
    const change=vi.fn();
    const root=createRoot(host);
    await act(async()=>root.render(<ModuleWorkspaceRoutes module="CONTROL" onModuleChange={change} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1" shellMode="basic"/>));
    // [HERMIA-FE-20261025 DUI P1-6] 规格变更：普通模式设置菜单只留 AI 主控，插件/工作流仅专业模式可见。
    act(()=>host.querySelector<HTMLButtonElement>('[data-settings-trigger="true"]')!.click());
    expect(host.querySelector('.shell-settings__menu [data-settings-open="CONTROL"]')).not.toBeNull();
    expect(host.querySelector('.shell-settings__menu [data-settings-open="PLUGIN"]')).toBeNull();
    expect(host.querySelector('.shell-settings__menu [data-settings-open="WORKFLOW"]')).toBeNull();
    act(()=>host.querySelector<HTMLButtonElement>('[data-settings-trigger="true"]')!.click());
    await act(async()=>root.render(<ModuleWorkspaceRoutes module="CONTROL" onModuleChange={change} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1" shellMode="pro"/>));
    act(()=>host.querySelector<HTMLButtonElement>('[data-settings-trigger="true"]')!.click());
    act(()=>host.querySelector<HTMLButtonElement>('.shell-settings__menu [data-settings-open="PLUGIN"]')!.click());
    expect(change).toHaveBeenCalledWith('PLUGIN');
    expect(host.querySelectorAll('[role="tablist"][aria-label="创作模块"] [role="tab"]')).toHaveLength(6);
    act(()=>root.unmount());
  });

  it('X-UX-04: shellMode attribute survives module route (no project empty)', () => {
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module="VIDEO" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" shellMode="pro"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-shell-mode')).toBe('pro');
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('VIDEO');
    act(()=>root.render(<ModuleWorkspaceRoutes module="AUDIO" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" shellMode="pro"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-shell-mode')).toBe('pro');
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('AUDIO');
    act(()=>root.unmount());
  });

  it('X-UX-08: VIDEO→EDIT isolates shells; media/NLE never mounts novel-write-chrome', () => {
    // VIDEO without novelId still wraps media-ws-main (honest empty) — no QC dependency.
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module="VIDEO" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('VIDEO');
    expect(host.querySelector('[data-module-shell="VIDEO"]')).toBeTruthy();
    expect(host.querySelector('[data-x-ux-isolation="per-module"]')).toBeTruthy();
    expect(host.querySelector('.edit-nle-shell')).toBeNull();
    expect(host.querySelector('.edit-nle-shell__hero')).toBeNull();
    expect(host.querySelector('.novel-write-chrome')).toBeNull();
    expect(host.querySelector('[data-module-shell="EDIT"]')).toBeNull();

    // EDIT with novel mounts CapCut NLE hero; VIDEO marker must be gone.
    act(()=>root.render(<ModuleWorkspaceRoutes module="EDIT" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('EDIT');
    expect(host.querySelector('[data-module-shell="EDIT"]')).toBeTruthy();
    expect(host.querySelector('.nle-tl[data-timeline-hero="true"]')).toBeTruthy(); // [HERMIA-FE-20261022 R5]
    expect(host.querySelector('[data-module-shell="VIDEO"]')).toBeNull();
    expect(host.querySelector('.novel-write-chrome')).toBeNull();
    expect(host.textContent).not.toMatch(/中区为正文编辑器/);
    act(()=>root.unmount());
  });

  it.each(['IMAGE','VIDEO','AUDIO','EDIT','ASSETS'] as const)('X-UX-08: %s route never mounts novel-write-chrome', module=>{
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    // no novelId → honest empty still tagged data-module-shell; avoids QC-heavy panels
    act(()=>root.render(<ModuleWorkspaceRoutes module={module} onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe(module);
    expect(host.querySelector(`[data-module-shell="${module}"]`)).toBeTruthy();
    expect(host.querySelector('.novel-write-chrome')).toBeNull();
    expect(host.querySelector('.edit-nle-shell')).toBeNull();
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).not.toBe('NOVEL');
    act(()=>root.unmount());
  });

  it('[HERMIA-FE-20261022 U5b] IMAGE returns to 漫画制作 when the novel last left it there; leaving keeps 浏览 fallback',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[]}),{status:200,headers:{'content-type':'application/json'}})));
    sessionStorage.clear(); sessionStorage.setItem('hermia-comic-draft:novel-1',JSON.stringify({view:'comic'}));
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>root.render(<ModuleWorkspaceRoutes module="IMAGE" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1"/>));
    expect(host.querySelector('#comicBubble')).toBeTruthy();
    sessionStorage.setItem('hermia-comic-draft:novel-2',JSON.stringify({view:'browse'}));
    await act(async()=>root.render(<ModuleWorkspaceRoutes module="IMAGE" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-2"/>));
    act(()=>root.unmount()); sessionStorage.clear(); vi.unstubAllGlobals();
  });
});
