// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ModuleWorkspaceRoutes} from './ModuleWorkspaceRoutes';
import {STUDIO_MODULES} from './moduleRegistry';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement;
afterEach(()=>host?.remove());

describe('ModuleWorkspaceRoutes',()=>{
  it('keeps the registered modules and renders the video workspace shell',()=>{
    expect(STUDIO_MODULES.map((item)=>item.id)).toEqual(['NOVEL','IMAGE','VIDEO','ASSETS','AUDIO','PLUGIN','WORKFLOW']);
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ModuleWorkspaceRoutes module="VIDEO" onModuleChange={vi.fn()} scope={{workspace:'w',project:'p',storyline:'s',branch:'b'}} actor="author"/>));
    expect(host.querySelector('.app-shell')?.getAttribute('data-module')).toBe('VIDEO');
    expect(host.textContent).toContain('视频');
    act(()=>root.unmount());
  });
});
