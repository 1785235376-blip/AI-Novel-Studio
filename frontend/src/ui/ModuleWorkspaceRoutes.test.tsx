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
  it('exposes media Provider configuration directly from the control workspace',async()=>{vi.spyOn(api,'assetProviders').mockResolvedValue({items:[]} as any);vi.spyOn(api,'videoProviders').mockResolvedValue({items:[]} as any);host=document.createElement('div');document.body.append(host);const root=createRoot(host);await act(async()=>root.render(<ModuleWorkspaceRoutes module="CONTROL" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author" novelId="novel-1"/>));const tab=[...host.querySelectorAll('button')].find(button=>button.textContent==='媒体 Provider')!;await act(async()=>{tab.click();await Promise.resolve()});expect(host.textContent).toContain('媒体 Provider');expect(host.querySelector('.media-provider-settings')).toBeTruthy();act(()=>root.unmount())});
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
    expect(host.querySelector('.edit-nle-shell__hero')).toBeTruthy();
    expect(host.querySelector('.edit-nle-rail')||host.textContent?.includes('媒体池')).toBeTruthy();
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
    expect(host.querySelector('[data-overflow-surface="CONTROL"]')).toBeTruthy();
    expect(host.querySelector('[data-capability-tone="neutral"]')).toBeTruthy();
    expect(host.querySelector('[data-overflow-chrome="true"]')).toBeTruthy();
    const tabs=[...host.querySelectorAll('[role="tablist"][aria-label="创作模块"] [role="tab"]')];
    expect(tabs).toHaveLength(6);
    expect(tabs.map(t=>t.getAttribute('data-module-tab'))).not.toContain('CONTROL');
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
});
