// @vitest-environment jsdom
import { cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { QueryClient,QueryClientProvider } from '@tanstack/react-query';
import { afterEach,beforeEach,expect,it,vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
const graph=vi.hoisted(()=>vi.fn());
vi.mock('./useStudioGraphEditor',()=>({useStudioGraphEditor:graph}));
const id='dual-default-project',base=`/api/projects/${id}/studio`;
let kind='NEUTRAL_STUDIO';
beforeEach(()=>{
 localStorage.clear();kind='NEUTRAL_STUDIO';useStudio.setState({novelId:id,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:''});
 graph.mockReset();graph.mockImplementation(()=>({content:<section aria-label="default creation fixture">Creation</section>,inspector:null,dirty:false,directorPending:false,discard:vi.fn()}));
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  const body=url===base?{project:{id,title:'Dual default',entry_kind:kind},preferences:{version:1,intents:[],preset:'BLANK',custom_intent:''},capabilities:{can_mutate:true,can_review:true,manual_import:true,manual_export:true,model_required:false,chapter_required:false,intent_is_permission:false,media_validator_configured:true,asset_kinds:['image','video','audio']}}
   :url.includes('/prompts')?{...emptyPromptLibrary,project_id:id,scope:{mode:'local',novel_id:id}}:{items:[]};
  return new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}});
 }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
function mount(module:'IMAGE'|'VIDEO'='IMAGE'){const q=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});render(<QueryClientProvider client={q}><IndependentStudioWorkspace projectId={id} context={{sessionToken:''}} scope={{workspace:'Local fixture',project:'Dual default',storyline:'Main',branch:'Main'}} actor="Author" module={module} onModuleChange={vi.fn()} onProjectChoice={vi.fn()}/></QueryClientProvider>);}
it('defaults a new neutral image workspace to the creation layer and keeps the original asset workspace reachable',async()=>{
 mount();await screen.findByRole('region',{name:'default creation fixture'});expect(graph.mock.calls.at(-1)![0].active).toBe(true);
 expect(typeof graph.mock.calls.at(-1)![0].productionTaskSource.preview).toBe('function');
 fireEvent.click(screen.getByRole('button',{name:'素材工作区'}));await screen.findByRole('button',{name:'上传资产'});expect(screen.queryByRole('region',{name:'default creation fixture'})).toBeNull();
});
it('keeps the original video workspace asset entry',async()=>{
 mount('VIDEO');await screen.findByRole('button',{name:'上传资产'});await waitFor(()=>expect(graph.mock.calls.at(-1)![0].active).toBe(false));expect(screen.queryByRole('region',{name:'default creation fixture'})).toBeNull();
});
