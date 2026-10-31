// @vitest-environment jsdom
/** Actual components/clients replay a cancelled original File job capture.
 * FAILED/AWAITING_REVIEW and candidate receipts are SOFTWARE projections only;
 * they do not prove File execution, image bytes, review or approval. */
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {Blob as NodeBlob} from 'node:buffer';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_job_observation.json';
import {STUDIO_IMAGE_NODE_JOB_FIELDS} from './studioProductionClient';
import type {StudioProductionTask} from '../taskcenter/studioProductionTask';
import {useStudio} from '../store';
import {useLocalHostSession} from '../localHostSession';
import {IndependentStudioWorkspace} from './IndependentStudioWorkspace';
import {rememberLocalStudioResume} from './studioWorkspaceResume';

const base=`/api/projects/${native.project}/studio`,production=`${base}/production`,endpoint=`${production}/jobs/image/${native.selected_job.id}/node-observation`;
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>,selectedReply:StudioProductionTask,observationReply:unknown;
type Override=(url:string,init:RequestInit)=>Response|Promise<Response>|undefined;
function server(override?:Override){fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const changed=override?.(url,init);if(changed!==undefined)return await changed;
  if(url===base)return json({project:{id:native.project,title:'Job-only metadata fixture',incarnation:native.observation.incarnation,entry_kind:'NEUTRAL_STUDIO'},
    preferences:{version:1,intents:[],preset:'BLANK',custom_intent:''},capabilities:{can_mutate:true,can_review:false,manual_import:true,manual_export:true,
      model_required:false,chapter_required:false,intent_is_permission:false,media_validator_configured:true,asset_kinds:['image','video','audio']}});
  if(url===`${production}/jobs`&&init.method==='GET')return json({items:[selectedReply]});
  if(url===endpoint&&init.method==='POST')return json(observationReply);
  if(url.includes('/experimental/workspace/tasks?'))return json({items:[],unavailable:[],truncated:false,executor:false,refresh:'MANUAL',automatic_retries:false});
  if((init.method||'GET')==='GET')return json({code:'UNRELATED_OWNER_UNAVAILABLE',message:'No Canvas or other owner is available in this fixture'},404);
  throw new Error(`Forbidden fallback/action/Canvas owner: ${init.method} ${url}`);
});vi.stubGlobal('fetch',fetcher);}
function mount(){const query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={native.project} context={{sessionToken:''}}
    scope={{workspace:'本机作品',project:'Job-only metadata fixture',storyline:'默认故事线',branch:'主线'}} actor="作者" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()}/></QueryClientProvider>);}
const actionName=()=>`只读查看原节点任务 ${selectedReply.id} v${selectedReply.version}`;
const panel=()=>screen.getByRole('region',{name:'原节点任务只读元数据'});
const count=()=>fetcher.mock.calls.filter(([url])=>url===endpoint).length;
const loaded=()=>screen.findByText(/这是本次读取的任务元数据快照，不是实时状态/);
function retained(button:HTMLElement){const key=Object.keys(button).find(name=>name.startsWith('__reactProps$'))!;return(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}
async function ready(){mount();return screen.findByRole('button',{name:actionName()});}
async function opened(){fireEvent.click(await ready());await loaded();}
function noOtherOwners(){for(const[url,init]of fetcher.mock.calls){
  expect(url).not.toMatch(/\/(?:assets|providers|preview|execute|cancel|reconcile|review|candidate|content|resolve-create|canvas-views|timelines|graphs|target-observation|target-view)(?:[/?]|$)/);
  if(init.method==='POST')expect(url).toBe(endpoint);if(init.method==='GET')expect(url).not.toBe(`${production}/jobs/image/${selectedReply.id}`);
}expect(screen.queryByRole('button',{name:'明确执行当前入队任务'})).toBeNull();}
beforeEach(()=>{
  vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);localStorage.clear();
  rememberLocalStudioResume(native.project,{module:'IMAGE',view:'TASKS',stage:'M4',interfaceMode:'PROFESSIONAL'});
  useStudio.setState({novelId:native.project,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:''});
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);
  selectedReply=structuredClone(native.selected_job) as unknown as StudioProductionTask;observationReply=structuredClone(native.observation);server();
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('reads original cancelled metadata without a Canvas reader, ordinary Job GET, storage or action',async()=>{
  const action=await ready();expect(count()).toBe(0);const before=fetcher.mock.calls.length;
  const get=vi.spyOn(Storage.prototype,'getItem'),set=vi.spyOn(Storage.prototype,'setItem'),open=retained(action);
  await act(async()=>{open();open();});await loaded();expect(count()).toBe(1);
  expect(fetcher.mock.calls.slice(before).map(([url,init])=>[url,init.method])).toEqual([[endpoint,'POST']]);
  expect(panel().textContent).toContain(native.selected_job.id);expect(panel().querySelector('img,video,audio,iframe,[src]')).toBeNull();
  expect(get).not.toHaveBeenCalled();expect(set).not.toHaveBeenCalled();noOtherOwners();
});

it.each(['FAILED','AWAITING_REVIEW'] as const)('shows SOFTWARE %s/candidate metadata without execution, reconciliation or media controls',async status=>{
  const candidate=status==='AWAITING_REVIEW'?{id:'software-metadata-candidate',version:1,digest:'b'.repeat(64),kind:'image'}:null;
  selectedReply={...selectedReply,status,version:selectedReply.version+1,attempt:1,cancellation_mode:null,error_code:status==='FAILED'?'SOFTWARE_ONLY_FAILURE':null,
    review_state:null,receipt_digest:status==='AWAITING_REVIEW'?'a'.repeat(64):null,output_candidate:candidate} as unknown as StudioProductionTask;
  const projection=Object.fromEntries(STUDIO_IMAGE_NODE_JOB_FIELDS.map(key=>[key,(selectedReply as unknown as Record<string,unknown>)[key]]));
  observationReply={...native.observation,job:projection};await opened();
  expect(panel().textContent).toContain(status==='FAILED'?'SOFTWARE_ONLY_FAILURE':'software-metadata-candidate');
  for(const name of ['明确执行当前入队任务','读取原入队任务预览','重新读取原任务服务配置','读取任务列表'])expect(screen.queryByRole('button',{name})).toBeNull();
  expect(count()).toBe(1);noOtherOwners();
});

it('preserves dirty input and retires old refresh/close callbacks after explicit same-pin refresh',async()=>{
  await opened();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep job-only unsaved preferences'}});
  const oldRefresh=retained(screen.getByRole('button',{name:'重新读取原任务元数据'})),oldClose=retained(screen.getByRole('button',{name:'关闭原任务元数据'}));
  fireEvent.click(screen.getByRole('button',{name:'重新读取原任务元数据'}));await waitFor(()=>expect(count()).toBe(2));await loaded();
  await act(async()=>{oldRefresh();oldClose();});expect(count()).toBe(2);expect(panel()).toBeTruthy();
  expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep job-only unsaved preferences');
  fireEvent.click(screen.getByRole('button',{name:'关闭原任务元数据'}));expect(screen.queryByRole('region',{name:'原节点任务只读元数据'})).toBeNull();
  expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep job-only unsaved preferences');noOtherOwners();
});

it('keeps TASKS and unsaved input after404 without activating or reading the project/Canvas again',async()=>{
  server(url=>url===endpoint?json({code:'JOB_UNAVAILABLE',message:'Original metadata unavailable'},404):undefined);
  const action=await ready();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep missing-job draft'}});const before=fetcher.mock.calls.length;
  fireEvent.click(action);await screen.findByRole('alert');expect(count()).toBe(1);
  expect(screen.getByRole('button',{name:'任务中心'}).getAttribute('aria-pressed')).toBe('true');expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep missing-job draft');
  expect(fetcher.mock.calls.slice(before).map(([url,init])=>[url,init.method])).toEqual([[endpoint,'POST']]);noOtherOwners();
});

it.each([401,403])('does not let late old-source %s or its close callback revoke a newly selected same-Job source',async status=>{
  let release!:(value:Response)=>void,requests=0;server(url=>{
    if(url!==endpoint)return;
    requests++;return requests===1?new Promise<Response>(resolve=>{release=resolve;}):json(native.observation);
  });
  fireEvent.click(await ready());await waitFor(()=>expect(release).toBeTypeOf('function'));const oldClose=retained(screen.getByRole('button',{name:'关闭原任务元数据'}));
  fireEvent.click(screen.getByRole('button',{name:'重新读取 Studio 制作任务'}));
  fireEvent.click(await screen.findByRole('button',{name:actionName()}));await loaded();
  await act(async()=>{release(json({code:'OLD_SOURCE_DENIED',message:'Old source denied'},status));oldClose();});
  expect(panel().textContent).toContain(native.selected_job.id);expect(count()).toBe(2);expect(screen.getByRole('button',{name:actionName()})).toBeTruthy();noOtherOwners();
});

it('does not expose a late result after the actual Workspace unmounts',async()=>{
  let release!:(value:Response)=>void;server(url=>url===endpoint?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  fireEvent.click(await ready());await waitFor(()=>expect(release).toBeTypeOf('function'));cleanup();await act(async()=>release(json(native.observation)));
  expect(count()).toBe(1);expect(screen.queryByRole('region',{name:'原节点任务只读元数据'})).toBeNull();noOtherOwners();
});
