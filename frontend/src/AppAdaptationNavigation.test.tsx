// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import App from './App';
import {api,ApiError,type Chapter} from './api';
import {useStudio} from './store';
import {drafts} from './drafts';
vi.mock('./Editor',async original=>({...await original<typeof import('./Editor')>(),ChapterEditor:({content,onChange,onCompositionChange}:any)=><textarea aria-label="Test chapter editor" value={content} onChange={event=>onChange(event.target.value,doc(event.target.value))} onCompositionStart={()=>onCompositionChange?.(true)}/>}));
vi.mock('./ui/AppShell',()=>({AppShell:({main,status,sidebar}:any)=><>{sidebar}<main>{main}</main><footer>{status}</footer></>}));
vi.mock('./novel/AiWritingPanel',()=>({AiWritingPanel:()=>null}));
vi.mock('./novel/SourcePrivacyControl',()=>({SourcePrivacyControl:()=>null}));
vi.mock('./novel/ChapterTree',()=>({ChapterTree:()=>null}));
vi.mock('./ui/FeatureLauncher',()=>({FeatureLauncher:({onSelect}:any)=><button onClick={()=>onSelect('experimental')}>Open tasks</button>}));
vi.mock('./novel/AdaptationPanel',()=>({AdaptationPanel:(props:any)=><output aria-label="Exact adaptation request">{JSON.stringify(props)}</output>}));
vi.mock('./experimental/DeferredExperimentalWorkbench',()=>({DeferredExperimentalWorkbench:({onNavigate}:any)=><>
  <button onClick={()=>onNavigate({kind:'feature',feature:'adaptation_lifecycle_v1',task_authority:'adaptation',novel_id:'adapt-nav',id:'task',parent_id:'proposal',version:7,signal:controller.signal})}>Open original adaptation</button>
  <button onClick={()=>onNavigate({kind:'feature',feature:'history',id:'history'})}>Leave tasks</button>
</>}));
function doc(text:string){return {type:'doc',content:[{type:'paragraph',content:[{type:'text',text}]}]};}
const chapter:Chapter={id:'adapt-nav:1',novel_id:'adapt-nav',number:1,title:'Synthetic',content:'SAVED',document:doc('SAVED'),version:3,word_count:5,status:'DRAFT'};
let controller:AbortController;const clients:QueryClient[]=[];
const valid=()=>({proposal_id:'proposal',proposal_revision:7,task:{id:'task'},stale:false});
beforeEach(()=>{
  controller=new AbortController();localStorage.clear();sessionStorage.clear();useStudio.getState().setCollaboration('');useStudio.setState({novelId:'adapt-nav',chapterId:chapter.id,textModel:null});
  vi.spyOn(api,'legacyHistory').mockResolvedValue([]);vi.spyOn(api,'chapters').mockResolvedValue([chapter]);vi.spyOn(api,'adaptationTask').mockResolvedValue(valid());
  vi.spyOn(api,'generateAdaptationDraft').mockRejectedValue(new Error('must not generate'));vi.spyOn(api,'applyAdaptationDraft').mockRejectedValue(new Error('must not apply'));
});
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.restoreAllMocks();localStorage.clear();sessionStorage.clear();});
async function setup(flag=true){
  const query=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity},mutations:{retry:false}}});clients.push(query);
  query.setQueryData(['novels'],[{id:'adapt-nav',title:'Synthetic'}]);query.setQueryData(['chapter','file',chapter.id],chapter);query.setQueryData(['chapters','file','adapt-nav'],[chapter]);query.setQueryData(['archived-chapters','file','adapt-nav'],[]);query.setQueryData(['text-models'],[]);query.setQueryData(['media-tasks','adapt-nav'],{audiobook:[],motion:[]});query.setQueryData(['writing-goal','adapt-nav'],{current_words:0,target_words:0,current_chapters:1,target_chapters:0,words_progress:0});query.setQueryData(['experimental-features','file'],{experimental:true,default_enabled:false,features:{'experimental.workspace_tools_v2':true,'experimental.adaptation_lifecycle_v1':flag}});
  render(<QueryClientProvider client={query}><App/></QueryClientProvider>);await waitFor(()=>expect((screen.getByLabelText('Test chapter editor') as HTMLTextAreaElement).value).toBe('SAVED'));
  fireEvent.click(screen.getByRole('button',{name:'Open tasks'}));await screen.findByRole('button',{name:'Open original adaptation'});return query;
}
const open=()=>fireEvent.click(screen.getByRole('button',{name:'Open original adaptation'}));
it('opens exact original proposal/task/revision without switching manuscript or executing work',async()=>{
  await setup();open();const result=await screen.findByLabelText('Exact adaptation request');expect(JSON.parse(result.textContent!)).toMatchObject({novelId:'adapt-nav',requestedProposalId:'proposal',requestedTaskId:'task',requestedRevision:7});
  expect(useStudio.getState().chapterId).toBe(chapter.id);expect(api.generateAdaptationDraft).not.toHaveBeenCalled();expect(api.applyAdaptationDraft).not.toHaveBeenCalled();
});
it.each(['wrong proposal','wrong task','stale revision','stale source','revoked'])('rejects %s rather than opening another adaptation',async reason=>{
  if(reason==='revoked')vi.mocked(api.adaptationTask).mockRejectedValue(new ApiError({status:403,code:'FORBIDDEN',message:'Denied'}));
  else vi.mocked(api.adaptationTask).mockResolvedValue({...valid(),...(reason==='wrong proposal'?{proposal_id:'other'}:reason==='wrong task'?{task:{id:'other'}}:reason==='stale revision'?{proposal_revision:8}:{stale:true})});
  await setup();open();await screen.findByText(/原改编任务已过期/);expect(screen.queryByLabelText('Exact adaptation request')).toBeNull();expect(useStudio.getState().chapterId).toBe(chapter.id);
});
it.each(['dirty','composing','flag off'])('blocks navigation for %s before reading task',async reason=>{
  await setup(reason!=='flag off');if(reason==='dirty')fireEvent.change(screen.getByLabelText('Test chapter editor'),{target:{value:'UNSAVED'}});if(reason==='composing')fireEvent.compositionStart(screen.getByLabelText('Test chapter editor'));open();expect(api.adaptationTask).not.toHaveBeenCalled();expect(useStudio.getState().chapterId).toBe(chapter.id);if(reason==='dirty')expect(drafts.load(chapter.id,'file')?.content).toBe('UNSAVED');
});
it.each(['abort','leave','new input'])('fences late original task result after %s',async reason=>{
  let resolve!:(row:any)=>void;vi.mocked(api.adaptationTask).mockImplementation(()=>new Promise(done=>{resolve=done;}));await setup();open();await waitFor(()=>expect(api.adaptationTask).toHaveBeenCalledOnce());
  if(reason==='abort')controller.abort();if(reason==='leave')fireEvent.click(screen.getByRole('button',{name:'Leave tasks'}));if(reason==='new input')fireEvent.change(screen.getByLabelText('Test chapter editor'),{target:{value:'NEW INPUT'}});
  await act(async()=>resolve(valid()));expect(screen.queryByLabelText('Exact adaptation request')).toBeNull();expect(useStudio.getState().chapterId).toBe(chapter.id);
});
