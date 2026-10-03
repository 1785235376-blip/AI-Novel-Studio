// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {api,ExportJob,Scope,setCollaborationContext} from '../api';
import {ExportPanel} from './ExportPanel';
const clients:QueryClient[]=[];
const initialScope:Scope={workspaceId:'w',projectId:'p',storylineId:'s',branchId:'initial-branch'};
function mount(){
  setCollaborationContext({sessionToken:'initial-session',scope:initialScope});
  const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
  const view=render(<QueryClientProvider client={client}><ExportPanel novelId="novel-1"/></QueryClientProvider>);
  return {client,unmount:view.unmount,switchSession:()=>view.rerender(<QueryClientProvider client={client}><ExportPanel novelId="novel-1" scope={initialScope} sessionToken="new-session-before-api-effect"/></QueryClientProvider>),switchTo:(novelId:string,scope?:Scope)=>view.rerender(<QueryClientProvider client={client}><ExportPanel novelId={novelId} scope={scope}/></QueryClientProvider>)};
}
function job(status:ExportJob['status']='queued',extra:Partial<ExportJob>={}):ExportJob{return {id:'export-1',novel_id:'novel-1',format:'screenplay-fountain',status,created_at:'',updated_at:'',...extra};}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done});return {promise,resolve};}
function disabled(name:string){return (screen.getByRole('button',{name}) as HTMLButtonElement).disabled;}
function switchView(view:ReturnType<typeof mount>,change:string){
  if(change==='project')view.switchTo('novel-2');
  else if(change==='branch')view.switchTo('novel-1',{workspaceId:'w',projectId:'p',storylineId:'s',branchId:'new-branch'});
  else if(change==='session-prop')view.switchSession();
  else if(change==='session'){setCollaborationContext({sessionToken:'replacement-session',scope:initialScope});view.switchTo('novel-1');}
  else view.unmount();
}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals();setCollaborationContext({sessionToken:''});});

describe('ExportPanel scope isolation',()=>{
  it.each(['project','branch','session','session-prop','unmount'])('discards a late creation after a %s change',async(change)=>{
    const pending=deferred<ExportJob>();vi.spyOn(api,'createExport').mockReturnValue(pending.promise);
    const status=vi.spyOn(api,'exportJob').mockResolvedValue(job()),cancel=vi.spyOn(api,'cancelExport');
    const view=mount();fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    await waitFor(()=>expect(disabled('Word 剧本')).toBe(true));switchView(view,change);
    await act(async()=>pending.resolve(job()));
    expect(status).not.toHaveBeenCalled();expect(cancel).not.toHaveBeenCalled();
    expect(screen.queryByRole('button',{name:'取消任务'})).toBeNull();
    if(change!=='unmount')expect(disabled('Word 剧本')).toBe(false);
  });
  it('ignores an old status response while showing the new project job',async()=>{
    const pending=deferred<ExportJob>();
    vi.spyOn(api,'createExport').mockResolvedValueOnce(job()).mockResolvedValueOnce(job('queued',{id:'export-2',novel_id:'novel-2'}));
    const status=vi.spyOn(api,'exportJob').mockImplementation(id=>id==='export-1'?pending.promise:Promise.resolve(job('queued',{id:'export-2',novel_id:'novel-2'})));
    const view=mount();fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    await waitFor(()=>expect(status).toHaveBeenCalledWith('export-1'));
    view.switchTo('novel-2');fireEvent.click(screen.getByRole('button',{name:'Word 剧本'}));
    await screen.findByRole('button',{name:'取消任务'});
    await act(async()=>pending.resolve(job('succeeded',{result:{format:'screenplay-fountain',filename:'old-project.fountain'}})));
    expect(screen.queryByRole('button',{name:/下载/})).toBeNull();expect(screen.getByText(/任务 export-2/)).toBeTruthy();
  });
  it.each(['project','branch','session','session-prop','unmount'])('never saves a pending old download after a %s change',async(change)=>{
    const completed=job('succeeded',{result:{format:'screenplay-docx',filename:'old-project.docx'}});
    vi.spyOn(api,'createExport').mockResolvedValue(completed);vi.spyOn(api,'exportJob').mockResolvedValue(completed);
    const pending=deferred<Blob>(),download=vi.spyOn(api,'exportDownload').mockReturnValue(pending.promise);
    const click=vi.spyOn(HTMLAnchorElement.prototype,'click');
    const view=mount();fireEvent.click(screen.getByRole('button',{name:'Word 剧本'}));
    fireEvent.click(await screen.findByRole('button',{name:'下载 old-project.docx'}));
    await waitFor(()=>expect(download).toHaveBeenCalledTimes(1));switchView(view,change);
    await act(async()=>pending.resolve(new Blob(['old bytes'])));
    expect(click).not.toHaveBeenCalled();expect(screen.queryByRole('button',{name:/下载/})).toBeNull();
  });
  it.each(['cancel','retry'])('fences a late %s response after changing projects',async(action)=>{
    const original=job(action==='cancel'?'queued':'failed');
    vi.spyOn(api,'createExport').mockResolvedValue(original);const status=vi.spyOn(api,'exportJob').mockResolvedValue(original);
    const pending=deferred<ExportJob>(),mutation=vi.spyOn(api,action==='cancel'?'cancelExport':'retryExport').mockReturnValue(pending.promise);
    const view=mount();fireEvent.click(screen.getByRole('button',{name:'Fountain 剧本'}));
    fireEvent.click(await screen.findByRole('button',{name:action==='cancel'?'取消任务':'重新尝试'}));
    await waitFor(()=>expect(mutation).toHaveBeenCalledWith('export-1'));view.switchTo('novel-2');
    await act(async()=>pending.resolve(job(action==='cancel'?'cancelled':'queued',{id:action==='cancel'?'export-1':'late-retry'})));
    expect(status).not.toHaveBeenCalledWith('late-retry');expect(screen.queryByRole('button',{name:'取消任务'})).toBeNull();
    expect(screen.queryByRole('button',{name:'重新尝试'})).toBeNull();expect(disabled('Word 剧本')).toBe(false);
    if(action==='cancel')expect(view.client.getQueryData<ExportJob>(['export-job',JSON.stringify(['novel-1','w','p','s','initial-branch']),'export-1'])?.status).toBe('queued');
  });
});
