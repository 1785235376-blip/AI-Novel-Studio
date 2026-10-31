// @vitest-environment jsdom
// [HERMIA-FE-20261025 VERA-FIX MF-4/P2] Vera re-review: pending hides next-step CTA; dev badges gated by pro;
// chapter buttons use aria-current not aria-selected; en save strings translated.
import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {NovelAssist} from './NovelAssist';
import {NovelStructureRail,NovelChapterColumn} from './NovelStructureRail';
import {SaveControls} from '../../ui/SaveControls';
import {setLocale} from '../../i18n';
afterEach(()=>{cleanup();setLocale('zh-CN');localStorage.clear();});
const assist=(extra:object)=><NovelAssist chapterTitle="t" chapterMeta="" primaryCta={{label:'在左侧选择或新建章节',onClick:vi.fn()}} links={[]} outlineItems={[]} ai={null} hasChapter={false} {...extra}/>;
describe('NovelAssist pendingState',()=>{
  it('shows the next-step CTA when nothing is pending',()=>{
    const r=render(assist({}));
    expect(r.container.querySelector('.nv-assist__next')).not.toBeNull();
    expect(screen.getByRole('button',{name:'在左侧选择或新建章节'})).toBeTruthy();
  });
  it.each(['loading','error'] as const)('hides next-step + CTA while %s',p=>{
    const r=render(assist({pendingState:p}));
    expect(r.container.querySelector('.nv-assist__next')).toBeNull();
    expect(screen.queryByRole('button',{name:'在左侧选择或新建章节'})).toBeNull();
  });
});
const panels=[{id:'a',label:'A',status:'part' as const},{id:'b',label:'B',status:'local' as const},{id:'c',label:'C',status:'off' as const}];
describe('rail badges gated by mode',()=>{
  it('normal: only honest 暂不可用 badge',()=>{
    const r=render(<NovelStructureRail chapters={[]} onSelect={vi.fn()} panels={panels} onOpenPanel={vi.fn()}/>);
    expect([...r.container.querySelectorAll('.nv-badge')].map(b=>b.textContent)).toEqual(['暂不可用']);
  });
  it('pro: dev-progress badges shown',()=>{
    const r=render(<NovelStructureRail chapters={[]} onSelect={vi.fn()} panels={panels} onOpenPanel={vi.fn()} pro/>);
    expect([...r.container.querySelectorAll('.nv-badge')].map(b=>b.textContent)).toEqual(['部分实现','仅本地交互','尚未接通后端']);
  });
});
describe('chapter buttons',()=>{
  it('use aria-current, never aria-selected (axe aria-allowed-attr)',()=>{
    const r=render(<NovelChapterColumn chapters={[{id:'1',number:1},{id:'2',number:2}]} selectedId="2" onSelect={vi.fn()}/>);
    const bs=[...r.container.querySelectorAll('.nv-chapters__ch')];
    expect(bs).toHaveLength(2);
    bs.forEach(b=>expect(b.hasAttribute('aria-selected')).toBe(false));
    expect(bs.map(b=>b.getAttribute('aria-current'))).toEqual([null,'true']);
  });
  it.each([['loading',{loading:true}],['error',{error:'x'}]] as const)('no new-chapter button while %s',(_n,st)=>{
    render(<NovelChapterColumn chapters={[]} onSelect={vi.fn()} onCreate={vi.fn()} {...st}/>);
    expect(screen.queryByRole('button',{name:/新建/})).toBeNull();
  });
});
describe('en SaveControls has no Chinese',()=>{
  it.each(['saved','dirty','failed','conflict'] as const)('%s',st=>{
    setLocale('en');
    const r=render(<SaveControls state={st} ready onSave={vi.fn()} recovery={{durability:'local' as any,onExport:vi.fn(),onConflict:vi.fn()}}/>);
    expect(r.container.textContent).not.toMatch(/[\u4e00-\u9fff]/);
  });
});
