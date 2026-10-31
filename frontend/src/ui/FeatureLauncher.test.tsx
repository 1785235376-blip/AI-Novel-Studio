// @vitest-environment jsdom
import {useState} from 'react';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {FEATURE_GROUP_DEFAULTS,FeatureLauncher} from './FeatureLauncher';

afterEach(cleanup);

function Harness({initialSelected='history',initialGroups=FEATURE_GROUP_DEFAULTS,onSelect}:{initialSelected?:string;initialGroups?:Record<string,boolean>;onSelect?:(id:string)=>void}){
  const [selected,setSelected]=useState(initialSelected);
  const [groups,setGroups]=useState(initialGroups);
  return <FeatureLauncher
    selectedId={selected}
    expandedGroups={groups}
    onSelect={(id)=>{setSelected(id);onSelect?.(id)}}
    onToggleGroup={(id)=>setGroups(current=>({...current,[id]:!current[id]}))}
  />;
}

describe('FeatureLauncher',()=>{
  it('opens upward navigation with the current feature focused and clearly selected',()=>{
    render(<Harness/>);
    const toggle=screen.getByRole('button',{name:'打开功能导航'});
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    const current=screen.getByRole('button',{name:'版本历史'});
    expect(screen.getByRole('navigation',{name:'功能面板导航'})).toBeTruthy();
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(current.getAttribute('aria-current')).toBe('page');
    expect(document.activeElement).toBe(current);
    expect(screen.getByRole('tooltip').textContent).toBe('关闭功能导航');
  });

  it('selects with the existing feature ID and keeps that selection after closing',()=>{
    const selected=vi.fn();
    render(<Harness onSelect={selected}/>);
    fireEvent.click(screen.getByRole('button',{name:'打开功能导航'}));
    fireEvent.click(screen.getByRole('button',{name:'故事资料库'}));
    expect(selected).toHaveBeenCalledWith('story');
    expect(screen.getByRole('button',{name:'故事资料库'}).getAttribute('aria-current')).toBe('page');
    fireEvent.pointerDown(document.body);
    const toggle=screen.getByRole('button',{name:'打开功能导航'});
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(toggle);
    fireEvent.click(toggle);
    expect(document.activeElement).toBe(screen.getByRole('button',{name:'故事资料库'}));
  });

  it('closes on outside pointer, Escape, and a second launcher click with focus restoration',()=>{
    render(<Harness/>);
    let toggle=screen.getByRole('button',{name:'打开功能导航'});
    fireEvent.click(toggle);
    fireEvent.pointerDown(document.body);
    toggle=screen.getByRole('button',{name:'打开功能导航'});
    expect(document.activeElement).toBe(toggle);
    fireEvent.click(toggle);
    fireEvent.keyDown(document,{key:'Escape'});
    toggle=screen.getByRole('button',{name:'打开功能导航'});
    expect(document.activeElement).toBe(toggle);
    fireEvent.click(toggle);
    const close=screen.getByRole('button',{name:'关闭功能导航'});
    fireEvent.click(close);
    expect(screen.queryByRole('navigation',{name:'功能面板导航'})).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button',{name:'打开功能导航'}));
  });

  it('expands a collapsed active group before focusing its current item',()=>{
    render(<Harness initialSelected="members" initialGroups={{create:false,production:false,collaboration:false,system:false}}/>);
    fireEvent.click(screen.getByRole('button',{name:'打开功能导航'}));
    expect(screen.getByRole('button',{name:/协作/}).getAttribute('aria-expanded')).toBe('true');
    expect(document.activeElement).toBe(screen.getByRole('button',{name:'团队成员'}));
  });

  it('contains Tab focus and supports arrow-key navigation inside the overlay',()=>{
    render(<Harness/>);
    fireEvent.click(screen.getByRole('button',{name:'打开功能导航'}));
    const overlay=screen.getByRole('navigation',{name:'功能面板导航'});
    const buttons=[...overlay.querySelectorAll<HTMLButtonElement>('[data-feature-focusable="true"]')];
    buttons.at(-1)!.focus();
    fireEvent.keyDown(buttons.at(-1)!,{key:'Tab'});
    expect(document.activeElement).toBe(buttons[0]);
    fireEvent.keyDown(buttons[0],{key:'ArrowDown'});
    expect(document.activeElement).toBe(buttons[1]);
    fireEvent.keyDown(buttons[1],{key:'Home'});
    expect(document.activeElement).toBe(buttons[0]);
  });

  it('N-UX-05 shows first-tier strip and N-UX-02 marks workflow as orchestration',()=>{
    render(<Harness/>);
    fireEvent.click(screen.getByRole('button',{name:'打开功能导航'}));
    expect(screen.getByRole('group',{name:'第一梯队面板'})).toBeTruthy();
    expect(screen.getByRole('button',{name:'第一梯队：故事资料库'})).toBeTruthy();
    expect(screen.getByRole('button',{name:'第一梯队：一致性检查'})).toBeTruthy();
    const workflow=screen.getByRole('button',{name:'工作流编排'});
    expect(workflow.getAttribute('title')||'').toMatch(/非 AI 写作旁路|编排面|多步骤编排/); // [HERMIA-FE-20261022 REBUILD-W3] 文案去内部名
    expect(workflow.className).toContain('feature-item--workflow');
    fireEvent.click(screen.getByRole('button',{name:'第一梯队：一致性检查'}));
    expect(screen.getByRole('button',{name:'一致性检查'}).getAttribute('aria-current')).toBe('page');
  });

  it('N-UX-10 story hint points to novel World* not storyboard Bible',()=>{
    render(<Harness/>);
    fireEvent.click(screen.getByRole('button',{name:'打开功能导航'}));
    const story=screen.getByRole('button',{name:'故事资料库'});
    const hint=story.getAttribute('title')||'';
    expect(hint).toMatch(/World\*|世界观|小说设定/);
    // [HERMIA-FE-20261022 REBUILD-W3] 作者可见提示不再出现「分镜 Bible」等内部说明
    expect(hint).not.toMatch(/Bible|World\*/);
    expect(hint).not.toMatch(/^规划 · 设定 · bible/);
    // Stable FL id — no invented bible/world FL
    expect(story.getAttribute('data-feature-id')).toBe('story');
  });
});
