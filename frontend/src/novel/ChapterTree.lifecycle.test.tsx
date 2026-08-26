// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ChapterTree} from './ChapterTree';

const active=[{id:'novel:1',title:'第一章',number:1,version:1},{id:'novel:2',title:'第二章',number:2,version:1}];
const archived=[{id:'novel:3',title:'草稿章',number:3,version:1}];
function renderTree(overrides:any={}){const props={chapters:active,archived,onSelect:vi.fn(),onCreate:vi.fn(),onRename:vi.fn(),onArchive:vi.fn(),onRestore:vi.fn(),...overrides};return {...render(<ChapterTree {...props}/>),props}}

describe('chapter lifecycle author UX',()=>{
 afterEach(()=>cleanup());
 it('requires confirmation and supports cancel/Escape without calling archive',()=>{
  const {props}=renderTree(); fireEvent.click(screen.getByRole('button',{name:/更多章节操作第一章/}));
  expect(screen.getByRole('heading',{name:/将“第一章”移出正文目录/})).toBeTruthy();
  expect(screen.getByText(/版本历史和相关资料都会保留/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'取消'})); expect(props.onArchive).not.toHaveBeenCalled();
 });
 it('closes archive confirmation on Escape',()=>{
  renderTree(); fireEvent.click(screen.getByRole('button',{name:/更多章节操作第一章/})); fireEvent.keyDown(document,{key:'Escape'}); expect(screen.queryByRole('heading',{name:/将“第一章”移出正文目录/})).toBeNull();
 });
 it('renders archived entry and restores only after activation',async()=>{
  const {props}=renderTree(); expect(screen.getByRole('heading',{name:'已移出章节'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'恢复到正文目录'})); await waitFor(()=>expect(props.onRestore).toHaveBeenCalledWith(archived[0]));
  expect(screen.queryByText('is_archived')).toBeNull(); expect(screen.queryByText('workspace_id')).toBeNull();
 });
 it('keeps lifecycle surface free of permanent delete actions and exposes accessible controls',()=>{
  renderTree(); expect(screen.getByRole('button',{name:/更多章节操作第一章/})).toBeTruthy();
  expect(screen.queryByText(/永久删除|删除章节|清空已移出章节/)).toBeNull();
 });
 it('preserves existing select/create/rename callbacks',async()=>{
  const {props}=renderTree(); fireEvent.click(screen.getByRole('button',{name:'1. 第一章'})); expect(props.onSelect).toHaveBeenCalledWith('novel:1');
  fireEvent.click(screen.getByRole('button',{name:'新建章节'})); const input=screen.getByLabelText('章节标题'); fireEvent.change(input,{target:{value:'新章'}}); fireEvent.click(screen.getByRole('button',{name:'创建章节'})); await waitFor(()=>expect(props.onCreate).toHaveBeenCalledWith('新章'));
  fireEvent.click(screen.getAllByRole('button',{name:/重命名第一章/})[0]); const rename=screen.getByDisplayValue('第一章'); fireEvent.change(rename,{target:{value:'改名'}}); fireEvent.click(screen.getByRole('button',{name:'保存'})); await waitFor(()=>expect(props.onRename).toHaveBeenCalledWith('novel:1','改名'));
 });
});
