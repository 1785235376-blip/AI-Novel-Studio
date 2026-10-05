// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,expect,it,vi} from 'vitest';
import {api,ApiError,ExportJob,setCollaborationContext} from '../api';
import {ExportPanel} from './ExportPanel';

const scope={workspaceId:'workspace',projectId:'project',storylineId:'story',branchId:'branch-a'};
const completed:ExportJob={id:'durable-job-1',novel_id:'project',format:'screenplay-fountain',status:'succeeded',snapshot_id:'durable-snapshot-1',created_at:'2026-10-05T00:00:00Z',updated_at:'2026-10-05T00:00:00Z',result:{format:'screenplay-fountain',filename:'recovered.fountain'}};
const clients:QueryClient[]=[];
function mount(client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})){
  clients.push(client);setCollaborationContext({sessionToken:'session-a',scope});
  const view=render(<QueryClientProvider client={client}><ExportPanel novelId="project"/></QueryClientProvider>);
  return {...view,client};
}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();setCollaborationContext({sessionToken:''});});

it('rediscovers the same durable job and snapshot after full remount and downloads it',async()=>{
  const history=vi.spyOn(api,'exportHistory').mockResolvedValue({items:[completed],next_offset:null});
  vi.spyOn(api,'exportJob').mockResolvedValue(completed);
  const download=vi.spyOn(api,'exportDownload').mockResolvedValue(new Blob(['frozen bytes']));
  const clicked=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
  Object.defineProperty(URL,'createObjectURL',{value:vi.fn(()=> 'blob:frozen'),configurable:true});
  Object.defineProperty(URL,'revokeObjectURL',{value:vi.fn(),configurable:true});
  const first=mount();
  await screen.findByRole('button',{name:'下载 recovered.fountain'});
  expect(screen.getByText(/快照：durable-snapshot-1/)).toBeTruthy();
  first.unmount();
  mount();
  fireEvent.click(await screen.findByRole('button',{name:'下载 recovered.fountain'}));
  await waitFor(()=>expect(clicked).toHaveBeenCalledTimes(1));
  expect(download).toHaveBeenCalledWith('durable-job-1',expect.any(Object));
  expect(history).toHaveBeenCalledTimes(2);
  expect(clients.every(client=>!JSON.stringify(client.getQueryCache().getAll().map(query=>query.queryKey)).includes('session-a'))).toBe(true);
});

it('does not show cached prior-owner history during a new session request',async()=>{
  let release!:(value:{items:ExportJob[];next_offset:null})=>void;
  const pending=new Promise<{items:ExportJob[];next_offset:null}>(resolve=>{release=resolve});
  vi.spyOn(api,'exportHistory').mockResolvedValueOnce({items:[completed],next_offset:null}).mockReturnValueOnce(pending);
  vi.spyOn(api,'exportJob').mockResolvedValue(completed);
  const view=mount();await screen.findByRole('button',{name:'下载 recovered.fountain'});
  setCollaborationContext({sessionToken:'session-b',scope});
  view.rerender(<QueryClientProvider client={view.client}><ExportPanel novelId="project"/></QueryClientProvider>);
  expect(screen.queryByRole('button',{name:/下载/})).toBeNull();
  expect(screen.queryByText(/durable-snapshot/)).toBeNull();
  await act(async()=>release({items:[],next_offset:null}));
  await screen.findByText('暂无导出记录');
});

it('paginates/filter history and retains a readable error with retry',async()=>{
  const history=vi.spyOn(api,'exportHistory').mockResolvedValue({items:[completed],next_offset:50});
  vi.spyOn(api,'exportJob').mockResolvedValue(completed);
  mount();fireEvent.click(await screen.findByRole('button',{name:'下一页'}));
  await waitFor(()=>expect(history).toHaveBeenCalledWith('project','',50,expect.any(Object)));
  fireEvent.change(screen.getByRole('combobox',{name:'导出历史状态'}),{target:{value:'failed'}});
  await waitFor(()=>expect(history).toHaveBeenCalledWith('project','failed',0,expect.any(Object)));
  history.mockRejectedValueOnce(new ApiError({status:403,code:'EXPORT_SCOPE_FORBIDDEN',message:'权限已撤销'}));
  fireEvent.click(await screen.findByRole('button',{name:'刷新历史'}));
  await screen.findByText('EXPORT_SCOPE_FORBIDDEN');
  expect(screen.queryByRole('button',{name:/Fountain 剧本 · 已完成/})).toBeNull();
  history.mockResolvedValue({items:[],next_offset:null});
  fireEvent.click(screen.getByRole('button',{name:'刷新历史'}));
  await screen.findByText('暂无导出记录');
});

it('uses incoming scope/session props before the parent API-context effect has run',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[],next_offset:null}),{status:200})));
  setCollaborationContext({sessionToken:'old-session',scope});
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);
  const nextScope={...scope,branchId:'branch-b'};
  render(<QueryClientProvider client={client}><ExportPanel novelId="project" scope={nextScope} sessionToken="new-session"/></QueryClientProvider>);
  await screen.findByText('暂无导出记录');
  expect(fetch).toHaveBeenCalledWith('/api/exports?novel_id=project&offset=0',expect.objectContaining({headers:expect.objectContaining({'X-Session-Token':'new-session','X-Branch-Id':'branch-b'})}));
  vi.unstubAllGlobals();
});
