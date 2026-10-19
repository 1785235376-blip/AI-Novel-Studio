// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {api,ApiError,ExportJob,setCollaborationContext} from '../api';
import {ExportPanel} from './ExportPanel';

const clients:QueryClient[]=[];
function mount(novelId:string|undefined='novel-1'){
  const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  clients.push(client);
  render(<QueryClientProvider client={client}><ExportPanel novelId={novelId}/></QueryClientProvider>);
  return client;
}
function job(status:ExportJob['status']='queued',extra:Partial<ExportJob>={}):ExportJob{
  return {id:'export-1',novel_id:'novel-1',format:'screenplay-fountain',status,created_at:'',updated_at:'',...extra};
}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done});return {promise,resolve};}
function disabled(name:string){return (screen.getByRole('button',{name}) as HTMLButtonElement).disabled;}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals();setCollaborationContext({sessionToken:''});});

describe('ExportPanel industry formats',()=>{
  it.each([['Fountain 剧本','screenplay-fountain'],['Word 剧本','screenplay-docx']])('submits %s through the authenticated durable queue',async(label,format)=>{
    setCollaborationContext({sessionToken:'session-test'});
    const fetchMock=vi.fn().mockImplementation(async()=>new Response(JSON.stringify(job('queued',{format})),{status:200,headers:{'Content-Type':'application/json'}}));
    vi.stubGlobal('fetch',fetchMock);
    mount();
    fireEvent.click(screen.getByRole('button',{name:label}));
    await screen.findByRole('button',{name:'取消任务'});
    expect(fetchMock.mock.calls[0][0]).toBe('/api/exports?novel_id=novel-1');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({method:'POST',body:JSON.stringify({format}),headers:{'X-Session-Token':'session-test'}});
    expect(fetchMock.mock.calls.some(([url])=>url==='/api/exports/export-1')).toBe(true);
    expect(fetchMock.mock.calls.every(([url])=>!url.includes('/novels/'))).toBe(true);
  });
  it('explains the immutable creation-time snapshot and keeps ZIP formats unexposed',()=>{
    mount();
    expect(screen.getByText(/任务创建时保存的只读项目快照，后续编辑不会改变该任务的导出内容/)).toBeTruthy();
    expect(screen.queryByText(/任务执行时/)).toBeNull();
    expect(screen.getByRole('button',{name:'影视剧本预览'})).toBeTruthy();
    expect(screen.getByRole('button',{name:'Word 文档'})).toBeTruthy();
    expect(screen.getAllByRole('button')).toHaveLength(11);
    expect(screen.queryByRole('button',{name:/ZIP|资源包/i})).toBeNull();
  });
  it('disables every format without a selected project',()=>{
    mount('');
    expect(screen.getByText('尚未选择项目')).toBeTruthy();
    expect(screen.getAllByRole('button').every(button=>(button as HTMLButtonElement).disabled)).toBe(true);
  });
  it('prevents duplicate creation and does not offer a file while queued',async()=>{
    const pending=deferred<ExportJob>();
    const create=vi.spyOn(api,'createExport').mockReturnValue(pending.promise);
    vi.spyOn(api,'exportJob').mockResolvedValue(job());
    mount();
    fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    await waitFor(()=>expect(disabled('Word 剧本')).toBe(true));
    fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    expect(create).toHaveBeenCalledTimes(1);
    await act(async()=>pending.resolve(job()));
    await screen.findByRole('button',{name:'取消任务'});
    expect(disabled('Word 剧本')).toBe(false);
    expect(screen.queryByRole('button',{name:/下载/})).toBeNull();
  });
  it('surfaces creation errors and restores available format buttons',async()=>{
    vi.spyOn(api,'createExport').mockRejectedValue(new ApiError({status:422,code:'SCREENPLAY_MISSING',message:'请先创建剧本',request_id:'create-request'}));
    mount();fireEvent.click(screen.getByRole('button',{name:'Word 剧本'}));
    await screen.findByText('SCREENPLAY_MISSING');
    expect(screen.getByText('create-request')).toBeTruthy();
    expect(disabled('Word 剧本')).toBe(false);
    expect(screen.queryByRole('button',{name:/下载/})).toBeNull();
  });
  it('preserves cancel, retry and pending button states',async()=>{
    vi.spyOn(api,'createExport').mockResolvedValue(job());
    vi.spyOn(api,'exportJob').mockImplementation(async id=>id==='export-2'?job('queued',{id}):job());
    const cancelling=deferred<ExportJob>(),retrying=deferred<ExportJob>();
    const cancel=vi.spyOn(api,'cancelExport').mockReturnValue(cancelling.promise);
    const retry=vi.spyOn(api,'retryExport').mockReturnValue(retrying.promise);
    mount();fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    fireEvent.click(await screen.findByRole('button',{name:'取消任务'}));
    await waitFor(()=>expect(disabled('取消任务')).toBe(true));
    expect(disabled('Word 剧本')).toBe(true);
    expect(cancel).toHaveBeenCalledWith('export-1');
    await act(async()=>cancelling.resolve(job('cancelled')));
    fireEvent.click(await screen.findByRole('button',{name:'重新尝试'}));
    await waitFor(()=>expect(disabled('重新尝试')).toBe(true));
    expect(disabled('Fountain 剧本')).toBe(true);
    expect(retry).toHaveBeenCalledWith('export-1');
    await act(async()=>retrying.resolve(job('queued',{id:'export-2',retry_of:'export-1',attempt:2})));
    await screen.findByRole('button',{name:'取消任务'});
    expect(disabled('Fountain 剧本')).toBe(false);
  });
  it('shows a cancellation error without inventing a cancelled job or a download',async()=>{
    vi.spyOn(api,'createExport').mockResolvedValue(job());
    vi.spyOn(api,'exportJob').mockResolvedValue(job());
    vi.spyOn(api,'cancelExport').mockRejectedValue(new ApiError({status:409,code:'CANCEL_CONFLICT',message:'取消失败，请重试',request_id:'cancel-request'}));
    mount();fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    fireEvent.click(await screen.findByRole('button',{name:'取消任务'}));
    await screen.findByText('CANCEL_CONFLICT');
    expect(screen.getByText('cancel-request')).toBeTruthy();
    expect(disabled('取消任务')).toBe(false);
    expect(screen.queryByRole('button',{name:'重新尝试'})).toBeNull();
    expect(screen.queryByRole('button',{name:/下载/})).toBeNull();
  });
  it('keeps 404 status failures explicit and allows a status refresh',async()=>{
    vi.spyOn(api,'createExport').mockResolvedValue(job());
    const get=vi.spyOn(api,'exportJob').mockRejectedValueOnce(new ApiError({status:404,code:'EXPORT_NOT_FOUND',message:'任务不存在',request_id:'lookup-request'})).mockResolvedValue(job());
    mount();fireEvent.click(screen.getByRole('button',{name:'Word 剧本'}));
    await screen.findByText('EXPORT_NOT_FOUND');
    expect(screen.getByText('lookup-request')).toBeTruthy();
    expect(screen.queryByRole('button',{name:/下载/})).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'刷新任务状态'}));
    await screen.findByRole('button',{name:'取消任务'});
    expect(get).toHaveBeenCalledTimes(2);
  });
  it('uses the authenticated download route and surfaces a missing artifact without a fake file',async()=>{
    const completed=job('succeeded',{result:{format:'screenplay-docx',filename:'screenplay.docx'}});
    setCollaborationContext({sessionToken:'session-test'});
    const fetchMock=vi.fn().mockImplementation(async(url:string)=>url.endsWith('/download')?new Response(JSON.stringify({code:'EXPORT_FILE_NOT_FOUND',message:'导出文件不存在',request_id:'download-request'}),{status:404}):new Response(JSON.stringify(completed),{status:200}));
    vi.stubGlobal('fetch',fetchMock);
    const click=vi.spyOn(HTMLAnchorElement.prototype,'click');
    mount();fireEvent.click(screen.getByRole('button',{name:'Word 剧本'}));
    fireEvent.click(await screen.findByRole('button',{name:'下载 screenplay.docx'}));
    await screen.findByText('EXPORT_FILE_NOT_FOUND');
    expect(fetchMock).toHaveBeenCalledWith('/api/exports/export-1/download',expect.objectContaining({headers:expect.objectContaining({'X-Session-Token':'session-test'})}));
    expect(screen.getByText('download-request')).toBeTruthy();
    expect(click).not.toHaveBeenCalled();
    expect(disabled('下载 screenplay.docx')).toBe(false);
  });
  it('downloads only returned artifact bytes and disables repeated download clicks',async()=>{
    const completed=job('succeeded',{result:{format:'screenplay-fountain',filename:'screenplay.fountain'}});
    vi.spyOn(api,'createExport').mockResolvedValue(completed);
    vi.spyOn(api,'exportJob').mockResolvedValue(completed);
    const pending=deferred<Blob>();
    const download=vi.spyOn(api,'exportDownload').mockReturnValue(pending.promise);
    const createObjectURL=vi.fn().mockReturnValue('blob:export-test'),revokeObjectURL=vi.fn();
    const OriginalURL=URL;
    class DownloadURL extends OriginalURL {static createObjectURL=createObjectURL;static revokeObjectURL=revokeObjectURL;}
    vi.stubGlobal('URL',DownloadURL);
    let savedFilename='';
    const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(function(this:HTMLAnchorElement){savedFilename=this.download;});
    mount();fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    fireEvent.click(await screen.findByRole('button',{name:'下载 screenplay.fountain'}));
    await waitFor(()=>expect(disabled('准备下载…')).toBe(true));
    fireEvent.click(screen.getByRole('button',{name:'准备下载…'}));
    expect(download).toHaveBeenCalledTimes(1);
    expect(download).toHaveBeenCalledWith('export-1');
    expect(click).not.toHaveBeenCalled();
    const blob=new Blob(['INT. STUDIO - DAY'],{type:'text/x-fountain'});
    await act(async()=>pending.resolve(blob));
    await waitFor(()=>expect(click).toHaveBeenCalledTimes(1));
    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(savedFilename).toBe('screenplay.fountain');
    await waitFor(()=>expect(revokeObjectURL).toHaveBeenCalledWith('blob:export-test'));
    expect(disabled('下载 screenplay.fountain')).toBe(false);
  });
  it('disables downloads when completion has no artifact metadata',async()=>{
    vi.spyOn(api,'createExport').mockResolvedValue(job('succeeded'));
    vi.spyOn(api,'exportJob').mockResolvedValue(job('succeeded'));
    const download=vi.spyOn(api,'exportDownload');
    mount();fireEvent.click(screen.getByRole('button',{name:'Word 剧本'}));
    await screen.findByText('任务已完成，但下载文件信息缺失，请重新导出。');
    expect(disabled('下载 导出文件')).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'下载 导出文件'}));
    expect(download).not.toHaveBeenCalled();
  });
});
