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
    expect(STUDIO_MODULES.map((item)=>item.id)).toEqual(['NOVEL','IMAGE','VIDEO','ASSETS','AUDIO','CONTROL','PLUGIN','WORKFLOW']);
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module="VIDEO" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('VIDEO');
    expect(host.textContent).toContain('视频');
    act(()=>root.unmount());
  });
  it.each(['IMAGE','VIDEO','AUDIO','WORKFLOW','ASSETS'] as const)('does not mount %s project panels without a novel',module=>{
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module={module} onModuleChange={vi.fn()} scope={{workspace:'w',project:'',storyline:'s',branch:'b'}} actor="author"/>));
    expect(host.textContent).toContain('请先打开小说项目');
    expect(host.querySelector('.multimodal-director')).toBeNull();
    const futureButtons=[...host.querySelectorAll<HTMLButtonElement>('.workspace-rail button')].slice(1);
    expect(futureButtons).toHaveLength(2);expect(futureButtons.every(button=>button.disabled)).toBe(true);
    act(()=>root.unmount());
  });
});
