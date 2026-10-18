// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';
import { newDocument, newScene, SCRIPT_PURPOSES, type CreativeDocument } from './types';
const body = '  独立口播稿。\n\n不修改小说正文。\n';
const saved = (version = 1): CreativeDocument => ({ ...newDocument('SCRIPT'), id:'script-1', title:'独立脚本', source_independent:true, script:{purpose:'PODCAST',body}, version, status:'DRAFT', actor_id:'author', created_at:'2026-10-10T00:00:00Z', updated_at:'2026-10-10T00:00:00Z', source_evidence:{} });
function props(): CreativeWorkspaceProps { return { enabled:true, novelId:'empty-project', context:{sessionToken:'author'}, scope:{workspace:'工作区',project:'空项目',storyline:'故事线',branch:'主线'},actor:'作者',chapterCount:0,manuscriptReady:false,novelMain:<div>小说正文编辑器</div>,novelSidebar:<div>章节树</div>,novelInspector:<div>正文信息</div>,novelStatus:<span>无正文修改</span>,onExit:vi.fn(),onModuleChange:vi.fn() }; }
const response = (value:unknown, status = 200) => ({ok:status < 400,status,json:async()=>value});
function server({rows = [],mutable = true,scriptEnabled = true,write}: {rows?:CreativeDocument[];mutable?:boolean;scriptEnabled?:boolean;write?:(url:string,init:RequestInit)=>unknown} = {}) {
 const fetch = vi.fn(async (url:string,init:RequestInit = {}) => {
  if (init?.method && init?.method !== 'GET') return write ? await write(url,init) : response({...saved(),...JSON.parse(String(init.body))});
  if(url.endsWith('/capabilities')) return response({enabled:true,can_mutate:mutable,modes:['SCREENPLAY','DIRECTOR','STORYBOARD','PRODUCTION',...(scriptEnabled?['SCRIPT']:[])]});
  if(url.endsWith('/documents')) return response({items:rows});
  if(url.endsWith('/history')) return response({document_id:'script-1',current_version:2,items:[saved(1),{...saved(2),script:{purpose:'PODCAST',body:'第二版'}}]});
  if(url.endsWith('/creation-reference-data')) return response({characters:[],locations:[],story_routes:[]});
  if(url.endsWith('/assets')) return response([]);
  if(url.endsWith('/director-proposals') || url.endsWith('/model-routes')) return response({items:[]});
  if(url.endsWith('/local-ai/environment')) return response({},404);
  throw Error(`Unexpected ${init?.method} ${url}`);
 });vi.stubGlobal('fetch',fetch);return fetch;
}
async function open() { await waitFor(()=>expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());fireEvent.click(within(screen.getByRole('tablist',{name:'创作模式'})).getByRole('tab',{name:/Screenplay/}));await screen.findByLabelText('文档标题'); }
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe('standalone Script uses original Creative workspace',()=>{
 it('creates an explicitly independent script in the existing five-stage shell',async()=>{
  const fetch=server();render(<CreativeWorkspace {...props()}/>);await open();
  expect(within(screen.getByRole('tablist',{name:'创作模式'})).getAllByRole('tab')).toHaveLength(5);
  fireEvent.click(screen.getByRole('button',{name:'新建独立通用脚本'}));
  expect(screen.queryByRole('button',{name:'添加场景'})).toBeNull();expect(screen.queryByLabelText('分镜画布')).toBeNull();
  expect((screen.getByLabelText('这是独立创作') as HTMLInputElement).checked).toBe(true);
  expect(within(screen.getByLabelText('脚本用途')).getAllByRole('option')).toHaveLength(SCRIPT_PURPOSES.length);
  fireEvent.change(screen.getByLabelText('文档标题'),{target:{value:'独立脚本'}});
  expect((screen.getByRole('button',{name:'保存草稿'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('脚本用途'),{target:{value:'PODCAST'}});fireEvent.change(screen.getByLabelText('通用脚本内容'),{target:{value:body}});
  expect((screen.getByRole('button',{name:'新建独立剧本'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'保存草稿'}));await screen.findByText('已保存“独立脚本” · v1');
  const writes=fetch.mock.calls.filter(([,init])=>init?.method!=='GET');expect(writes).toHaveLength(1);
  expect(writes[0][0]).toMatch(/\/creative\/documents$/);expect(JSON.parse(String(writes[0][1]?.body))).toMatchObject({mode:'SCRIPT',source_independent:true,source_chapter_ids:[],scenes:[],shots:[],script:{purpose:'PODCAST',body}});
  expect(screen.getByLabelText('通用脚本文本格式导出')).toBeTruthy();expect(screen.queryByRole('button',{name:'建立分镜草稿'})).toBeNull();
 });
 it('reopens the actual saved Script and keeps its type when starting another document',async()=>{
  const fetch=server({rows:[saved()]});render(<CreativeWorkspace {...props()}/>);await open();
  expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe(body);
  expect((screen.getByLabelText('脚本用途') as HTMLSelectElement).value).toBe('PODCAST');
  fireEvent.click(screen.getByRole('button',{name:'新建文档'}));expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe('');
  fireEvent.click(screen.getByRole('button',{name:'新建独立剧本'}));expect(screen.queryByLabelText('通用脚本内容')).toBeNull();expect(screen.getByRole('button',{name:'添加场景'})).toBeTruthy();
  expect(fetch.mock.calls.every(([,init])=>init?.method==='GET')).toBe(true);
 });
 it('retains the dirty Script when changing modes or cancelling exit',async()=>{
  server({rows:[saved()]});render(<CreativeWorkspace {...props()}/>);await open();fireEvent.change(screen.getByLabelText('通用脚本内容'),{target:{value:'未保存脚本'}});
  const tabs=within(screen.getByRole('tablist',{name:'创作模式'}));fireEvent.click(tabs.getByRole('tab',{name:/Novel/}));fireEvent.click(tabs.getByRole('tab',{name:/Screenplay/}));
  expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe('未保存脚本');
  fireEvent.click(screen.getByRole('button',{name:'返回经典工作区'}));fireEvent.click(screen.getByRole('button',{name:'继续编辑'}));
  expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe('未保存脚本');expect((screen.getByRole('button',{name:'导出脚本文本'}) as HTMLButtonElement).disabled).toBe(true);
 });
 it('restores reviewed Script history with the current CAS version, preserving original versions',async()=>{
  const fetch=server({rows:[{...saved(2),script:{purpose:'PODCAST',body:'第二版'}}],write:()=>response(saved(3))});render(<CreativeWorkspace {...props()}/>);await open();fireEvent.click(screen.getByRole('button',{name:'历史'}));
  await screen.findByText('版本历史 · 当前 v2');fireEvent.click(screen.getByLabelText('已核对 v1 的完整内容；恢复会新建当前版本'));fireEvent.click(screen.getByRole('button',{name:'恢复 v1 为新版本'}));
  await screen.findByText('已将所选历史内容恢复为新版本 v3，其他历史版本仍保留。');
  const write=fetch.mock.calls.find(([,init])=>init?.method==='POST')!;expect(write[0]).toMatch(/\/script-1\/restore$/);expect(JSON.parse(String(write[1]?.body))).toEqual({expected_version:2,restore_version:1});expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe(body);
 });
 it('locks a CAS-conflicted Script without erasing its local text or resubmitting',async()=>{
  const fetch=server({rows:[saved()],write:()=>response({code:'VERSION_CONFLICT',message:'版本冲突'},409)});render(<CreativeWorkspace {...props()}/>);await open();fireEvent.change(screen.getByLabelText('通用脚本内容'),{target:{value:'保留这一稿'}});fireEvent.click(screen.getByRole('button',{name:'保存草稿'}));
  await screen.findByText('需要核对版本 · 本地草稿仍保留');expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe('保留这一稿');expect(screen.getByLabelText('通用脚本内容').closest('fieldset')!.disabled).toBe(true);expect(fetch.mock.calls.filter(([,init])=>init?.method==='PUT')).toHaveLength(1);
 });
 it('keeps reader access read-only and hides creation when the server lacks this document type',async()=>{
  server({rows:[saved()],mutable:false,scriptEnabled:false});render(<CreativeWorkspace {...props()}/>);await open();expect(screen.getByLabelText('通用脚本内容').closest('fieldset')!.disabled).toBe(true);expect(screen.queryByRole('button',{name:'新建独立通用脚本'})).toBeNull();
 });
 it('drops an old identity’s late saved Script after project navigation',async()=>{
  let resolve!:(value:unknown)=>void;const fetch=server({rows:[saved()],write:()=>new Promise(done=>{resolve=done;})});const original=props(), view=render(<CreativeWorkspace {...original}/>);await open();fireEvent.change(screen.getByLabelText('通用脚本内容'),{target:{value:'旧项目稿'}});fireEvent.click(screen.getByRole('button',{name:'保存草稿'}));
  await waitFor(()=>expect(fetch.mock.calls.some(([,init])=>init?.method==='PUT')).toBe(true));view.rerender(<CreativeWorkspace {...original} novelId="another-project"/>);await act(async()=>resolve(response({...saved(2),title:'旧项目迟到结果'})));await open();expect(screen.queryByText('旧项目迟到结果')).toBeNull();expect(screen.queryByText('已保存“旧项目迟到结果” · v2')).toBeNull();
 });
});
it('stages a saved Script through the original derive route only after confirmation and opens exact source-bound text',async()=>{
 const target:CreativeDocument={...newDocument('SCREENPLAY'),id:'staged-screenplay',title:'Staged script',source_independent:false,scenes:[{...newScene(1),id:'text-1',heading:'脚本文本段 1',action:body}],version:1,status:'DRAFT',actor_id:'author',created_at:'',updated_at:'',source_evidence:{},source_documents:{'script-1':{version:1,digest:'a'.repeat(64)}}};
 const fetch=server({rows:[saved()],write:()=>response(target)});render(<CreativeWorkspace {...props()}/>);await open();
 const create=screen.getByRole('button',{name:'确认建立剧本底稿'}) as HTMLButtonElement;expect(create.disabled).toBe(true);expect(fetch.mock.calls.every(([,init])=>init?.method==='GET')).toBe(true);
 fireEvent.click(screen.getByLabelText('确认从此已保存版本建立独立的新剧本底稿'));fireEvent.click(create);
 await screen.findByText(/已从当前已保存版本建立“Staged script”/);
 const writes=fetch.mock.calls.filter(([,init])=>init?.method==='POST');expect(writes).toHaveLength(1);expect(writes[0][0]).toMatch(/\/script-1\/derive$/);expect(JSON.parse(String(writes[0][1]?.body))).toEqual({expected_version:1,mode:'SCREENPLAY',script_policy:'TEXT_CHUNKS'});
 expect((screen.getByLabelText('动作与叙事') as HTMLTextAreaElement).value).toBe(body);expect(screen.queryByLabelText('通用脚本内容')).toBeNull();
});
it('retains original Script and blocks automatic retry when a staging receipt does not preserve its source',async()=>{
 const fetch=server({rows:[saved()],write:()=>response({...saved(),mode:'SCREENPLAY',id:'bad-receipt',scenes:[]})});render(<CreativeWorkspace {...props()}/>);await open();fireEvent.click(screen.getByLabelText('确认从此已保存版本建立独立的新剧本底稿'));fireEvent.click(screen.getByRole('button',{name:'确认建立剧本底稿'}));
 await screen.findByText('需要核对版本 · 本地草稿仍保留');expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe(body);expect((screen.getByRole('button',{name:'确认建立剧本底稿'}) as HTMLButtonElement).disabled).toBe(true);expect(fetch.mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(1);
});
