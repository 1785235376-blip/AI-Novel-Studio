// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {ResearchPanel} from './ResearchPanel';
import {api,ApiError} from '../api';

const emptyResult={items:[],total:0,storage:'durable_sidecar',external_fetch:false};
const record={
  id:'r1',novel_id:'n1',title:'港口档案',source_type:'ARTICLE',status:'ACTIVE',version:4,
  author:'林舟',url:'https://reference.example/archive',tags:['港口'],excerpt:'潮汐记录',notes:'旧港笔记',
};

function deferred<T>(){
  let resolve!:(value:T)=>void;
  let reject!:(reason?:unknown)=>void;
  const promise=new Promise<T>((ok,fail)=>{resolve=ok;reject=fail});
  return {promise,resolve,reject};
}

function renderPanel(novelId='n1'){
  const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  const view=render(<QueryClientProvider client={client}><ResearchPanel novelId={novelId}/></QueryClientProvider>);
  return {
    client,
    ...view,
    rerenderNovel:(nextId:string)=>view.rerender(<QueryClientProvider client={client}><ResearchPanel novelId={nextId}/></QueryClientProvider>),
  };
}

const fieldValue=(label:string)=>(screen.getByLabelText(label) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement).value;

beforeEach(()=>{
  vi.stubGlobal('fetch',vi.fn(()=>{throw new Error('REAL_NETWORK_REQUEST_BLOCKED')}));
});

afterEach(()=>{
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('research panel',()=>{
  it('shows author and source URL as non-clickable local reference text',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue({...emptyResult,items:[record],total:1} as any);
    renderPanel();
    const list=await screen.findByRole('list',{name:'研究资料列表'});
    await waitFor(()=>expect(list.textContent).toContain('作者：林舟'));
    expect(list.textContent).toContain('来源网址：https://reference.example/archive');
    expect(list.querySelector('a')).toBeNull();
    expect(screen.getByText(/仅保存引用信息，不读取网址内容/)).toBeTruthy();
  });

  it('creates with the complete current payload including author and URL',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue(emptyResult as any);
    const create=vi.spyOn(api,'createResearch').mockResolvedValue({id:'r2',title:'新资料',version:1});
    renderPanel();
    fireEvent.change(await screen.findByLabelText('标题'),{target:{value:'新资料'}});
    fireEvent.change(screen.getByLabelText('来源类型'),{target:{value:'WEBSITE'}});
    fireEvent.change(screen.getByLabelText('资料状态'),{target:{value:'ARCHIVED'}});
    fireEvent.change(screen.getByLabelText('作者'),{target:{value:'资料员'}});
    fireEvent.change(screen.getByLabelText('来源网址'),{target:{value:'https://source.example/item'}});
    fireEvent.change(screen.getByLabelText('资料标签'),{target:{value:'港口，史料'}});
    fireEvent.change(screen.getByLabelText('摘要'),{target:{value:'摘要'}});
    fireEvent.change(screen.getByLabelText('笔记'),{target:{value:'笔记'}});
    fireEvent.click(screen.getByRole('button',{name:'新建资料'}));
    await waitFor(()=>expect(create).toHaveBeenCalledWith('n1',{
      title:'新资料',source_type:'WEBSITE',status:'ARCHIVED',author:'资料员',url:'https://source.example/item',
      tags:['港口','史料'],excerpt:'摘要',notes:'笔记',
    }));
  });

  it('rejects a non-http URL locally without an API or network request',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue(emptyResult as any);
    const create=vi.spyOn(api,'createResearch');
    renderPanel();
    fireEvent.change(await screen.findByLabelText('标题'),{target:{value:'本地引用'}});
    fireEvent.change(screen.getByLabelText('来源网址'),{target:{value:'file:///private/archive'}});
    fireEvent.click(screen.getByRole('button',{name:'新建资料'}));
    expect(await screen.findByText(/来源网址仅支持 http\/https/)).toBeTruthy();
    expect(create).not.toHaveBeenCalled();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('fills every editable field and saves with the exact novel, record, version and payload',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue({...emptyResult,items:[record],total:1} as any);
    const update=vi.spyOn(api,'updateResearch').mockResolvedValue({...record,title:'修订档案'} as any);
    renderPanel();
    fireEvent.click(await screen.findByRole('button',{name:'编辑'}));
    expect(fieldValue('标题')).toBe('港口档案');
    expect(fieldValue('来源类型')).toBe('ARTICLE');
    expect(fieldValue('资料状态')).toBe('ACTIVE');
    expect(fieldValue('作者')).toBe('林舟');
    expect(fieldValue('来源网址')).toBe('https://reference.example/archive');
    expect(fieldValue('资料标签')).toBe('港口');
    expect(fieldValue('摘要')).toBe('潮汐记录');
    expect(fieldValue('笔记')).toBe('旧港笔记');
    fireEvent.change(screen.getByLabelText('标题'),{target:{value:'修订档案'}});
    fireEvent.change(screen.getByLabelText('作者'),{target:{value:'新作者'}});
    fireEvent.change(screen.getByLabelText('来源网址'),{target:{value:'http://source.example/revised'}});
    fireEvent.click(screen.getByRole('button',{name:'保存修改'}));
    await waitFor(()=>expect(update).toHaveBeenCalledWith('n1','r1',{
      title:'修订档案',source_type:'ARTICLE',status:'ACTIVE',author:'新作者',url:'http://source.example/revised',
      tags:['港口'],excerpt:'潮汐记录',notes:'旧港笔记',
    },4));
    await waitFor(()=>expect(screen.getByRole('heading',{name:'新建资料'})).toBeTruthy());
    expect(fieldValue('标题')).toBe('');
  });

  it('passes status, source and tag filters without fake empty values',async()=>{
    const list=vi.spyOn(api,'listResearch').mockResolvedValue(emptyResult as any);
    renderPanel();
    await waitFor(()=>expect(list).toHaveBeenCalledWith('n1',{status:undefined,source_type:undefined,tag:undefined}));
    fireEvent.change(screen.getByLabelText('研究资料状态筛选'),{target:{value:'ARCHIVED'}});
    fireEvent.change(screen.getByLabelText('研究资料来源筛选'),{target:{value:'BOOK'}});
    fireEvent.change(screen.getByLabelText('研究资料标签筛选'),{target:{value:'港口'}});
    await waitFor(()=>expect(list).toHaveBeenLastCalledWith('n1',{status:'ARCHIVED',source_type:'BOOK',tag:'港口'}));
  });

  it('keeps the unsaved draft, reports 409 and refreshes the same novel',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue({...emptyResult,items:[record],total:1} as any);
    vi.spyOn(api,'updateResearch').mockRejectedValue(new ApiError({status:409,code:'CONFLICT',message:'server detail'}));
    const {client}=renderPanel();
    const invalidate=vi.spyOn(client,'invalidateQueries');
    fireEvent.click(await screen.findByRole('button',{name:'编辑'}));
    fireEvent.change(screen.getByLabelText('标题'),{target:{value:'尚未保存的修订'}});
    fireEvent.change(screen.getByLabelText('作者'),{target:{value:'未保存作者'}});
    fireEvent.click(screen.getByRole('button',{name:'保存修改'}));
    expect(await screen.findByText('版本冲突：记录已被更新，请重新加载后再编辑。')).toBeTruthy();
    expect(fieldValue('标题')).toBe('尚未保存的修订');
    expect(fieldValue('作者')).toBe('未保存作者');
    expect(screen.getByRole('heading',{name:'编辑资料'})).toBeTruthy();
    expect(invalidate).toHaveBeenCalledWith({queryKey:['research','n1']});
  });

  it('requires delete confirmation and cancel never calls the API',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue({...emptyResult,items:[record],total:1} as any);
    const remove=vi.spyOn(api,'deleteResearch');
    renderPanel();
    fireEvent.click(await screen.findByRole('button',{name:'删除'}));
    expect(screen.getByRole('alertdialog',{name:'删除确认'})).toBeTruthy();
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'取消'}));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(remove).not.toHaveBeenCalled();
  });

  it('deletes only after second confirmation with the exact novel, ID and version',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue({...emptyResult,items:[record],total:1} as any);
    const remove=vi.spyOn(api,'deleteResearch').mockResolvedValue({id:'r1',deleted:true,version:5});
    renderPanel();
    fireEvent.click(await screen.findByRole('button',{name:'删除'}));
    fireEvent.click(screen.getByRole('button',{name:'再次确认删除'}));
    await waitFor(()=>expect(remove).toHaveBeenCalledWith('n1','r1',4));
    expect(await screen.findByText('资料已删除')).toBeTruthy();
  });

  it('keeps deletion pending and reports a truthful failure',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue({...emptyResult,items:[record],total:1} as any);
    vi.spyOn(api,'deleteResearch').mockRejectedValue(new ApiError({status:409,code:'CONFLICT',message:'server detail'}));
    renderPanel();
    fireEvent.click(await screen.findByRole('button',{name:'删除'}));
    fireEvent.click(screen.getByRole('button',{name:'再次确认删除'}));
    expect(await screen.findByText('删除冲突：请刷新后重试。')).toBeTruthy();
    expect(screen.getByRole('alertdialog',{name:'删除确认'})).toBeTruthy();
    expect(screen.queryByText('资料已删除')).toBeNull();
  });

  it('resets draft, editing, deletion and messages when the novel changes',async()=>{
    vi.spyOn(api,'listResearch').mockImplementation(async(id:string)=>id==='n1'?{...emptyResult,items:[record],total:1} as any:emptyResult as any);
    const {rerenderNovel}=renderPanel('n1');
    fireEvent.click(await screen.findByRole('button',{name:'编辑'}));
    fireEvent.change(screen.getByLabelText('标题'),{target:{value:'旧小说草稿'}});
    fireEvent.change(screen.getByLabelText('来源网址'),{target:{value:'invalid'}});
    fireEvent.click(screen.getByRole('button',{name:'保存修改'}));
    expect(await screen.findByText(/来源网址仅支持/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'删除'}));
    expect(screen.getByRole('alertdialog')).toBeTruthy();
    rerenderNovel('n2');
    expect(await screen.findByText('暂无研究资料')).toBeTruthy();
    expect(screen.getByRole('heading',{name:'新建资料'})).toBeTruthy();
    expect(fieldValue('标题')).toBe('');
    expect(fieldValue('来源网址')).toBe('');
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(screen.queryByText(/来源网址仅支持/)).toBeNull();
    expect(screen.queryByText('港口档案')).toBeNull();
  });

  it('reads only the new novel after switching scope',async()=>{
    const list=vi.spyOn(api,'listResearch').mockImplementation(async(id:string)=>({...emptyResult,items:[{...record,id:`${id}-record`,novel_id:id,title:`${id} 资料`}],total:1}) as any);
    const {rerenderNovel}=renderPanel('n1');
    expect(await screen.findByText('n1 资料')).toBeTruthy();
    rerenderNovel('n2');
    expect(await screen.findByText('n2 资料')).toBeTruthy();
    expect(screen.queryByText('n1 资料')).toBeNull();
    expect(list).toHaveBeenCalledWith('n2',{status:undefined,source_type:undefined,tag:undefined});
  });

  it('does not let a delayed old-novel mutation pollute the new novel UI',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue(emptyResult as any);
    const pending=deferred<any>();
    vi.spyOn(api,'createResearch').mockReturnValue(pending.promise);
    const {client,rerenderNovel}=renderPanel('n1');
    const invalidate=vi.spyOn(client,'invalidateQueries');
    fireEvent.change(await screen.findByLabelText('标题'),{target:{value:'旧小说延迟资料'}});
    fireEvent.change(screen.getByLabelText('作者'),{target:{value:'旧作者'}});
    fireEvent.click(screen.getByRole('button',{name:'新建资料'}));
    rerenderNovel('n2');
    expect(await screen.findByText('暂无研究资料')).toBeTruthy();
    await act(async()=>pending.resolve({id:'old-record',title:'旧小说延迟资料',version:1}));
    expect(fieldValue('标题')).toBe('');
    expect(fieldValue('作者')).toBe('');
    expect(screen.queryByText(/已新建资料 old-record/)).toBeNull();
    expect(invalidate).toHaveBeenCalledWith({queryKey:['research','n1']});
    expect(invalidate).not.toHaveBeenCalledWith({queryKey:['research','n2']});
  });

  it('keeps the existing empty state when no novel is selected',()=>{
    const list=vi.spyOn(api,'listResearch');
    renderPanel('');
    expect(screen.getByText('未选择小说')).toBeTruthy();
    expect(list).not.toHaveBeenCalled();
  });

  it('never performs a real fetch, Provider request or database request',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue(emptyResult as any);
    renderPanel();
    expect(await screen.findByText('暂无研究资料')).toBeTruthy();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
