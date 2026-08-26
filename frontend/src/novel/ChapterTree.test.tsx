// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ChapterTree} from './ChapterTree';
afterEach(cleanup);

describe('ChapterTree',()=>{
  it('renders loading, error and empty states',()=>{
    const props={chapters:[],onSelect:vi.fn(),onCreate:vi.fn()};
    const {rerender}=render(<ChapterTree {...props} loading/>);expect(screen.getByRole('status').textContent).toContain('正在加载章节');
    rerender(<ChapterTree {...props} error="网络不可用"/>);expect(screen.getByRole('alert').textContent).toContain('网络不可用');
    rerender(<ChapterTree {...props}/>);expect(screen.getByText('还没有章节')).toBeTruthy();
  });
  it('selects, creates with title only, and renames',async()=>{
    const onSelect=vi.fn(),onCreate=vi.fn(),onRename=vi.fn();render(<ChapterTree chapters={[{id:'c1',title:'第一章',status:'已保存',wordCount:42}]} selectedId="c1" onSelect={onSelect} onCreate={onCreate} onRename={onRename}/>);
    fireEvent.click(screen.getByText('第一章'));expect(onSelect).toHaveBeenCalledWith('c1');
    fireEvent.click(screen.getByRole('button',{name:'新建章节'}));fireEvent.change(screen.getByLabelText('章节标题'),{target:{value:'  第二章  '}});fireEvent.click(screen.getByRole('button',{name:'创建章节'}));await waitFor(()=>expect(onCreate).toHaveBeenCalledWith('第二章'));
    fireEvent.click(screen.getByRole('button',{name:'重命名第一章'}));fireEvent.change(screen.getByLabelText('章节标题'),{target:{value:'序章'}});fireEvent.click(screen.getByRole('button',{name:'保存'}));await waitFor(()=>expect(onRename).toHaveBeenCalledWith('c1','序章'));
  });
  it('keeps current state, long titles and secondary actions accessible',()=>{
    const longTitle='这是一个用于验证章节目录不会被超长中文标题撑开的章节标题';
    render(<ChapterTree chapters={[{id:'c1',title:longTitle},{id:'c2',title:'第二章'}]} selectedId="c1" onSelect={vi.fn()} onCreate={vi.fn()} onRename={vi.fn()} onArchive={vi.fn()}/>);
    const current=screen.getByRole('button',{name:longTitle});
    expect(current.getAttribute('aria-current')).toBe('page');
    expect(current.closest('.novel-tree-row')?.classList.contains('is-selected')).toBe(true);
    expect(screen.getByRole('button',{name:'第二章'}).getAttribute('aria-current')).toBeNull();
    expect(screen.getByTitle(longTitle).textContent).toContain(longTitle);
    expect(screen.getByRole('button',{name:`重命名${longTitle}`})).toBeTruthy();
    expect(screen.getByRole('button',{name:`更多章节操作${longTitle}`})).toBeTruthy();
    expect(screen.queryByText(/永久删除|删除章节/)).toBeNull();
  });
  it('persists a drag reorder through the supplied handler',()=>{const onReorder=vi.fn();render(<ChapterTree chapters={[{id:'c1',title:'第一章'},{id:'c2',title:'第二章'}]} onSelect={vi.fn()} onCreate={vi.fn()} onReorder={onReorder}/>);const source=screen.getByText('第一章').closest('li')!,target=screen.getByText('第二章').closest('li')!;fireEvent.dragStart(source,{dataTransfer:{effectAllowed:'',setData:vi.fn()}});fireEvent.dragOver(target,{dataTransfer:{dropEffect:''}});fireEvent.drop(target,{dataTransfer:{}});expect(onReorder).toHaveBeenCalledWith('c1','c2')});
});
