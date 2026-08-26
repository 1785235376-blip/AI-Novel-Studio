// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,describe,expect,it} from 'vitest';
import {scopeKindLabels} from '../productLanguage';
import {ContextBar} from './AppShell';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement;
afterEach(()=>host?.remove());

describe('author-facing terminology',()=>{
  it('renders a Chinese-first context bar without raw hierarchy terms or ids',()=>{
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<ContextBar scope={{workspace:'我的创作空间',project:'雾港来信',storyline:'主故事线',branch:'主分支'}}/>));
    expect(host.textContent).toBe('创作空间：我的创作空间/小说：雾港来信/故事线：主故事线/创作分支：主分支');
    expect(host.textContent).not.toMatch(/Workspace|Storyline|Branch|NONE|workspace-|storyline-|branch-/);
    act(()=>root.unmount());
  });
  it('maps original internal scope values without renaming them',()=>{
    expect(Object.keys(scopeKindLabels)).toEqual(['WORKSPACE','PROJECT','STORYLINE','BRANCH','CHAPTER']);
    expect(scopeKindLabels.WORKSPACE).toBe('创作空间');expect(scopeKindLabels.STORYLINE).toBe('故事线');expect(scopeKindLabels.BRANCH).toBe('创作分支');
  });
});
