// @vitest-environment jsdom
/** Actual TaskCenter/Workspace/client + captured original target-observation JSON.
 * Transport replies are software projections of the File metadata fixture;
 * nothing executes, restores, opens an editor, or requests assets/media. */
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {webcrypto} from 'node:crypto';
import {Blob as NodeBlob} from 'node:buffer';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_target_observation.json';
import {useStudio} from '../store';
import {useLocalHostSession} from '../localHostSession';
import {IndependentStudioWorkspace,type IndependentStudioProps} from './IndependentStudioWorkspace';
import {rememberLocalStudioResume} from './studioWorkspaceResume';

const base=`/api/projects/${native.project}/studio`,production=`${base}/production`;
const endpoint=`${production}/jobs/image/${native.queued_job.id}/target-observation`;
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>;
type Override=(url:string,init:RequestInit)=>Response|Promise<Response>|undefined;
function server(override?:Override){
  fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
    const changed=override?.(url,init);if(changed!==undefined)return await changed;
    if(url===base)return json({project:{id:native.project,title:'Target observation metadata fixture',incarnation:native.observation.incarnation,entry_kind:'NEUTRAL_STUDIO'},
      preferences:{version:1,intents:[],preset:'BLANK',custom_intent:''},capabilities:{can_mutate:true,can_review:false,manual_import:true,manual_export:true,model_required:false,
        chapter_required:false,intent_is_permission:false,media_validator_configured:true,asset_kinds:['image','video','audio']}});
    if(url===`${production}/jobs`&&init.method==='GET')return json({items:[native.queued_job]});
    if(url===`${production}/jobs/image/${native.queued_job.id}`&&init.method==='GET')return json(native.queued_job);
    if(url===endpoint&&init.method==='POST')return json(native.observation);
    if(url.includes('/experimental/workspace/tasks?'))return json({items:[],unavailable:[],truncated:false,executor:false,refresh:'MANUAL',automatic_retries:false});
    if((init.method||'GET')==='GET')return json({code:'UNRELATED_READ_NOT_AVAILABLE',message:'Not part of this bounded fixture'},404);
    throw new Error(`Unexpected mutation outside existing-owner metadata observation: ${init.method} ${url}`);
  });vi.stubGlobal('fetch',fetcher);
}
const workspaceProps=():IndependentStudioProps=>({projectId:native.project,context:{sessionToken:''},
  scope:{workspace:'本机作品',project:'Target observation metadata fixture',storyline:'默认故事线',branch:'主线'},actor:'作者',module:'IMAGE',
  onModuleChange:vi.fn(),onProjectChoice:vi.fn()});
function mount(patch:Partial<IndependentStudioProps>={}){
  const query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  const tree=(props:IndependentStudioProps)=><QueryClientProvider client={query}><IndependentStudioWorkspace {...props}/></QueryClientProvider>;
  const view=render(tree({...workspaceProps(),...patch}));return{...view,rerenderWorkspace:(props:IndependentStudioProps)=>view.rerender(tree(props))};
}
const targetButton=()=>screen.getByRole('button',{name:`核对原保存位置 ${native.queued_job.id} v${native.queued_job.version}`});
async function ready(){mount();return screen.findByRole('button',{name:`核对原保存位置 ${native.queued_job.id} v${native.queued_job.version}`});}
const countObservation=()=>fetcher.mock.calls.filter(([url])=>url===endpoint).length;
function retained(button:HTMLElement){const key=Object.keys(button).find(name=>name.startsWith('__reactProps$'))!;return(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}
function noOtherOwners(){
  for(const[url,init]of fetcher.mock.calls){
    expect(url).not.toMatch(/\/(?:assets|providers|preview|execute|cancel|reconcile|review|candidate|content|resolve-create|canvas-views|timelines)(?:[/?]|$)/);
    if(init.method==='POST')expect(url).toBe(endpoint);
  }
  expect(fetcher.mock.calls.filter(([url,init])=>url===`${production}/jobs/image/${native.queued_job.id}`&&init.method==='GET')).toHaveLength(0);
  expect(screen.queryByRole('heading',{name:'仅续接原节点任务'})).toBeNull();expect(screen.queryByRole('heading',{name:'只读续接原节点任务'})).toBeNull();
  expect(screen.queryByRole('button',{name:'明确执行当前入队任务'})).toBeNull();
}
beforeEach(()=>{
  vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);localStorage.clear();
  // Existing presentation-location preference only, never a graph/prompt/queue hint.
  rememberLocalStudioResume(native.project,{module:'IMAGE',view:'TASKS',stage:'M4',interfaceMode:'PROFESSIONAL'});
  useStudio.setState({novelId:native.project,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:''});
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);server();
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('uses one explicit exact row action to compare the captured pin with a legitimately changed Canvas, without leaving TASKS',async()=>{
  const writes=vi.spyOn(Storage.prototype,'setItem');const button=await ready();expect(countObservation()).toBe(0);
  const before=fetcher.mock.calls.length;
  const inspect=retained(button);await act(async()=>{inspect();inspect();});
  await screen.findByText(/当前保存版本已变化/);
  expect(countObservation()).toBe(1);
  expect(fetcher.mock.calls.slice(before).map(([url,init])=>[url,init.method])).toEqual([[endpoint,'POST']]);
  expect(screen.getByRole('button',{name:'任务中心'}).getAttribute('aria-pressed')).toBe('true');
  expect(screen.getAllByText(native.observation.target.canvas_digest).length).toBeGreaterThan(0);
  expect(screen.getAllByText(native.observation.canvas.definition_digest).length).toBeGreaterThan(0);
  noOtherOwners();
  for(const[key,value]of writes.mock.calls){expect(key).not.toMatch(/rebuild|canvas.*(?:draft|hint|queue|create)/i);expect(value).not.toContain(native.queued_job.command.prompt);}
});

it('preserves dirty preferences on inspect, refresh and close without requesting a discard confirmation',async()=>{
  await ready();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep unsaved preferences while checking target'}});fireEvent.click(targetButton());
  await screen.findByText(/当前保存版本已变化/);expect(screen.queryByRole('button',{name:'确认离开'})).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'重新核对保存状态'}));await waitFor(()=>expect(countObservation()).toBe(2));
  await screen.findByText(/当前保存版本已变化/);fireEvent.click(screen.getByRole('button',{name:'关闭保存状态核对'}));
  expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep unsaved preferences while checking target');
  expect(screen.queryByRole('button',{name:'确认离开'})).toBeNull();noOtherOwners();
});

it.each([403,404,422])('shows original observation %s unavailable without probing Canvas, other Job or assets',async status=>{
  server(url=>url===endpoint?json({code:'TARGET_OBSERVATION_UNAVAILABLE',message:'original observation unavailable'},status):undefined);
  const button=await ready();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep draft when observation is unavailable'}});
  fireEvent.click(button);await waitFor(()=>expect(countObservation()).toBe(1));
  if(status===404)await screen.findByText(/本次未确认是否删除/);
  else if(status===422)await screen.findByRole('alert');
  else await waitFor(()=>expect(screen.queryByRole('button',{name:`核对原保存位置 ${native.queued_job.id} v${native.queued_job.version}`})).toBeNull());
  expect(screen.queryByText(/当前保存版本已变化/)).toBeNull();
  if(status!==403){
    expect(screen.getByRole('button',{name:'任务中心'}).getAttribute('aria-pressed')).toBe('true');
    expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep draft when observation is unavailable');
    expect(screen.queryByText('权限失效')).toBeNull();
  }
  noOtherOwners();
});

it('rejects a changed original Job through protected observation without a plain Job GET',async()=>{
  server(url=>url===endpoint?json({...native.observation,job:{...native.queued_job,version:native.queued_job.version+1}}):undefined);
  fireEvent.click(await ready());await screen.findByRole('alert');expect(countObservation()).toBe(1);noOtherOwners();
});

it('does not adopt a late metadata response after explicit close',async()=>{
  let release!:(value:Response)=>void;server(url=>url===endpoint?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  fireEvent.click(await ready());await waitFor(()=>expect(release).toBeTypeOf('function'));
  fireEvent.click(screen.getByRole('button',{name:'关闭保存状态核对'}));await act(async()=>release(json(native.observation)));
  expect(screen.queryByText(/当前保存版本已变化/)).toBeNull();expect(countObservation()).toBe(1);noOtherOwners();
});

it('retires a pending selected source when the existing selector is explicitly refreshed',async()=>{
  let release!:(value:Response)=>void;server(url=>url===endpoint?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  fireEvent.click(await ready());await waitFor(()=>expect(release).toBeTypeOf('function'));
  fireEvent.click(screen.getByRole('button',{name:'重新读取 Studio 制作任务'}));await act(async()=>release(json(native.observation)));
  expect(screen.queryByText(/当前保存版本已变化/)).toBeNull();expect(countObservation()).toBe(1);noOtherOwners();
});

it('does not adopt a late response after the real Workspace unmounts',async()=>{
  let release!:(value:Response)=>void;server(url=>url===endpoint?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  fireEvent.click(await ready());await waitFor(()=>expect(release).toBeTypeOf('function'));cleanup();
  await act(async()=>release(json(native.observation)));expect(countObservation()).toBe(1);noOtherOwners();
});

it('does not let callbacks from closed source A close or refresh a newly selected same-Job source A',async()=>{
  fireEvent.click(await ready());await screen.findByText(/当前保存版本已变化/);
  const oldClose=retained(screen.getByRole('button',{name:'关闭保存状态核对'})),oldRefresh=retained(screen.getByRole('button',{name:'重新核对保存状态'}));
  fireEvent.click(targetButton());await waitFor(()=>expect(countObservation()).toBe(2));await screen.findByText(/当前保存版本已变化/);
  await act(async()=>{oldClose();oldRefresh();});
  expect(screen.getByText(/当前保存版本已变化/)).toBeTruthy();expect(countObservation()).toBe(2);noOtherOwners();
});
