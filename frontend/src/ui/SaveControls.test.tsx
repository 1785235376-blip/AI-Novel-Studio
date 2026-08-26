// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {reduceSaveState,SaveControls,type SaveState} from './SaveControls';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement;
afterEach(()=>host?.remove());

describe('save state model',()=>{
  it('covers hydration, edit, saving, authoritative success, failure, and retry',()=>{
    let state:SaveState=reduceSaveState('dirty',{type:'hydrate',hasDraft:false,hasConflict:false});
    expect(state).toBe('saved');
    state=reduceSaveState(state,{type:'edit'});expect(state).toBe('dirty');
    state=reduceSaveState(state,{type:'save-started'});expect(state).toBe('saving');
    state=reduceSaveState(state,{type:'save-failed'});expect(state).toBe('failed');
    state=reduceSaveState(state,{type:'save-started'});expect(state).toBe('saving');
    state=reduceSaveState(state,{type:'save-succeeded',hasNewerChanges:false});expect(state).toBe('saved');
  });
  it('does not mark newer in-flight edits saved when an older request succeeds',()=>{
    expect(reduceSaveState('dirty',{type:'save-succeeded',hasNewerChanges:true})).toBe('dirty');
  });
  it('does not create false dirty state when a different authoritative chapter hydrates',()=>{
    expect(reduceSaveState('failed',{type:'hydrate',hasDraft:false,hasConflict:false})).toBe('saved');
    expect(reduceSaveState('saved',{type:'hydrate',hasDraft:true,hasConflict:false})).toBe('dirty');
  });
});

describe('SaveControls',()=>{
  it('uses the shared DS button and exposes persistent text for every state',()=>{
    host=document.createElement('div');document.body.append(host);const root=createRoot(host),save=vi.fn();
    const render=(state:SaveState,ready=true)=>act(()=>root.render(<SaveControls state={state} ready={ready} onSave={save}/>));
    render('saved');expect(host.querySelector('button')?.classList.contains('ui-button')).toBe(true);expect(host.textContent).toContain('已保存');
    render('dirty');expect(host.textContent).toContain('有未保存修改');
    render('saving');expect(host.textContent).toContain('保存中…');expect(host.querySelector('button')?.hasAttribute('disabled')).toBe(true);
    render('failed');expect(host.textContent).toContain('保存失败，请重试');act(()=>host.querySelector<HTMLButtonElement>('button')!.click());expect(save).toHaveBeenCalledTimes(1);
    render('dirty',false);expect(host.textContent).toContain('正在打开章节…');expect(host.textContent).not.toContain('有未保存修改');expect(host.querySelector('button')?.hasAttribute('disabled')).toBe(true);
    act(()=>root.unmount());
  });
  it('keeps editor content present when failure state is rendered',()=>{
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    act(()=>root.render(<><article data-testid="editor">未确认保存的正文</article><SaveControls state="failed" ready onSave={vi.fn()}/></>));
    expect(host.querySelector('[data-testid="editor"]')?.textContent).toBe('未确认保存的正文');expect(host.textContent).toContain('保存失败，请重试');
    act(()=>root.unmount());
  });
});
