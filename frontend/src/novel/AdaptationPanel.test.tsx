// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {api,ApiError} from '../api';
import {AdaptationPanel} from './AdaptationPanel';

const catalog={enabled:true,can_write:true,can_review:true,model_runtime:'NOT_CONFIGURED'};
function proposal(id='p',revision=1){return {id,title:`Proposal ${id}`,revision,blueprint_revision:1,blueprint:{focus:'Original focus',pacing:'Pace',format:'Screen',constraints:[],chapter_map:[]},status:'DRAFT',target:'SCREEN',source_chapter_count:0,source_versions:[],source_digest:'source-digest'};}
function error(status:number){return new ApiError({status,code:'ERROR',message:'Synthetic failure'});}
function wrap(novelId='n',extra={}){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});return {client,element:<QueryClientProvider client={client}><AdaptationPanel novelId={novelId} {...extra}/></QueryClientProvider>};}
beforeEach(()=>{vi.spyOn(api,'adaptationCatalog').mockResolvedValue(catalog);vi.spyOn(api,'adaptationProposals').mockResolvedValue([]);});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('shows loading, empty and honest missing model configuration',async()=>{
  const view=wrap();render(view.element);await screen.findByText('暂无改编方案');expect(screen.getByText(/模型改写：NOT_CONFIGURED/)).toBeTruthy();
});
it('hides cached proposals after unauthorized reads',async()=>{
  vi.mocked(api.adaptationProposals).mockResolvedValue([proposal()]);const view=wrap();render(view.element);await screen.findByText('Proposal p');
  vi.mocked(api.adaptationProposals).mockRejectedValue(error(403));fireEvent.click(screen.getByRole('button',{name:'读取最新状态'}));
  await screen.findByRole('alert');expect(screen.queryByText('Proposal p')).toBeNull();
});
it('preserves edited blueprint on CAS conflict, never silently rebases',async()=>{
  vi.mocked(api.adaptationProposals).mockResolvedValue([proposal()]);vi.spyOn(api,'updateAdaptationBlueprint').mockRejectedValue(error(409));
  const view=wrap();render(view.element);await screen.findByText('Proposal p');fireEvent.click(screen.getByText('编辑改编蓝图'));
  fireEvent.change(screen.getByLabelText('改编重点'),{target:{value:'Unsaved thought'}});fireEvent.click(screen.getByRole('button',{name:'保存蓝图修订'}));
  await screen.findByRole('alert');expect((screen.getByLabelText('改编重点') as HTMLTextAreaElement).value).toBe('Unsaved thought');
  expect(api.updateAdaptationBlueprint).toHaveBeenCalledWith('n','p',expect.objectContaining({expected_revision:1,focus:'Unsaved thought'}),undefined);
  vi.mocked(api.adaptationProposals).mockResolvedValue([proposal('p',2)]);fireEvent.click(screen.getByRole('button',{name:'读取最新状态'}));
  await screen.findByText(/服务器已有版本 2/);expect((screen.getByRole('button',{name:'保存蓝图修订'}) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('改编重点') as HTMLTextAreaElement).value).toBe('Unsaved thought');
});
it('sends exact revision and suppresses duplicate approval clicks',async()=>{
  vi.mocked(api.adaptationProposals).mockResolvedValue([proposal('p',7)]);let finish:(value:any)=>void=()=>{};
  vi.spyOn(api,'approveAdaptationProposal').mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));const view=wrap();render(view.element);await screen.findByText('Proposal p');
  const button=screen.getByRole('button',{name:'批准方案'});act(()=>{fireEvent.click(button);fireEvent.click(button);});
  await waitFor(()=>expect(api.approveAdaptationProposal).toHaveBeenCalledTimes(1));expect(api.approveAdaptationProposal).toHaveBeenCalledWith('n','p',undefined,7);
  await act(async()=>finish({...proposal('p',8),status:'APPROVED'}));
});
it('only reopens the exact requested proposal and task; missing pointer never falls back',async()=>{
  const row={...proposal('wanted',8),status:'MATERIALIZED',execution_manifest:[{id:'task-wanted',status:'AWAITING_REVIEW',source_chapter_id:'source',source_version:3,target_chapter_id:'target',target_version:4,unit:'One',action:'Rewrite',draft:{content:'Exact requested draft'}}]};
  vi.mocked(api.adaptationProposals).mockResolvedValue([proposal('wrong'),row]);const view=wrap('n',{requestedProposalId:'wanted',requestedTaskId:'task-wanted',requestedRevision:8});const rendered=render(view.element);
  await screen.findByLabelText('改编任务 task-wanted');expect(screen.queryByText('Proposal wrong')).toBeNull();
  rendered.rerender(<QueryClientProvider client={view.client}><AdaptationPanel novelId="n" requestedProposalId="wrong-parent" requestedTaskId="task-wanted" requestedRevision={8}/></QueryClientProvider>);
  await screen.findByText(/不会打开其他方案/);expect(screen.queryByLabelText('改编任务 task-wanted')).toBeNull();
});
it('does not render recovery actions when disabled and fences late project results',async()=>{
  vi.mocked(api.adaptationCatalog).mockResolvedValue({...catalog,enabled:false});let release:(rows:any[])=>void=()=>{};
  vi.mocked(api.adaptationProposals).mockImplementation(nid=>nid==='old'?new Promise(resolve=>{release=resolve;}):Promise.resolve([proposal('new')]));
  const view=wrap('old');const rendered=render(view.element);await waitFor(()=>expect(api.adaptationProposals).toHaveBeenCalledWith('old',undefined));
  rendered.rerender(<QueryClientProvider client={view.client}><AdaptationPanel novelId="new"/></QueryClientProvider>);await screen.findByText('Proposal new');
  await act(async()=>release([proposal('old')]));expect(screen.queryByText('Proposal old')).toBeNull();expect(screen.queryByRole('button',{name:'取消方案'})).toBeNull();
});
