// @vitest-environment jsdom
/** Real components/clients; HTTP replies replay original File metadata with a
 * manual reference only. This is not approved adoption, verified image content,
 * model execution or a browser/geometry acceptance. */
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {Blob as NodeBlob} from 'node:buffer';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_target_view.json';
import {useStudio} from '../store';
import {useLocalHostSession} from '../localHostSession';
import {IndependentStudioWorkspace} from './IndependentStudioWorkspace';
import {rememberLocalStudioResume} from './studioWorkspaceResume';

const base=`/api/projects/${native.project}/studio`,production=`${base}/production`;
const observationEndpoint=`${production}/jobs/image/${native.queued_job.id}/target-observation`,viewEndpoint=`${production}/jobs/image/${native.queued_job.id}/target-view`;
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>;
type Override=(url:string,init:RequestInit)=>Response|Promise<Response>|undefined;
function server(override?:Override){
  fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
    const changed=override?.(url,init);if(changed!==undefined)return await changed;
    if(url===base)return json({project:{id:native.project,title:'Manual metadata target-view fixture',incarnation:native.observation.incarnation,entry_kind:'NEUTRAL_STUDIO'},
      preferences:{version:1,intents:[],preset:'BLANK',custom_intent:''},capabilities:{can_mutate:true,can_review:false,manual_import:true,manual_export:true,
        model_required:false,chapter_required:false,intent_is_permission:false,media_validator_configured:true,asset_kinds:['image','video','audio']}});
    if(url===`${production}/jobs`&&init.method==='GET')return json({items:[native.queued_job]});
    if(url===observationEndpoint&&init.method==='POST')return json(native.observation);
    if(url===viewEndpoint&&init.method==='POST')return json(native.view);
    if(url.includes('/experimental/workspace/tasks?'))return json({items:[],unavailable:[],truncated:false,executor:false,refresh:'MANUAL',automatic_retries:false});
    if((init.method||'GET')==='GET')return json({code:'UNRELATED_READ_UNAVAILABLE',message:'Not part of this metadata fixture'},404);
    throw new Error(`Unexpected graph/editor/write or content owner: ${init.method} ${url}`);
  });vi.stubGlobal('fetch',fetcher);
}
function mount(){
  const query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={native.project} context={{sessionToken:''}}
    scope={{workspace:'本机作品',project:'Manual metadata target-view fixture',storyline:'默认故事线',branch:'主线'}} actor="作者" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()}/></QueryClientProvider>);
}
const inspectName=`核对原保存位置 ${native.queued_job.id} v${native.queued_job.version}`;
const viewButton=()=>screen.getByRole('button',{name:'查看此版本关联画布'});
const child=()=>screen.getByRole('region',{name:'原目标关联画布只读记录'});
const count=(url:string)=>fetcher.mock.calls.filter(([target])=>target===url).length;
function retained(button:HTMLElement){const key=Object.keys(button).find(name=>name.startsWith('__reactProps$'))!;return(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}
async function observed(){mount();fireEvent.click(await screen.findByRole('button',{name:inspectName}));await screen.findByText(/当前保存版本已变化/);return viewButton();}
function noOtherOwners(){
  for(const[url,init]of fetcher.mock.calls){
    expect(url).not.toMatch(/\/(?:assets|providers|preview|execute|cancel|reconcile|review|candidate|content|resolve-create|canvas-views|timelines|graphs)(?:[/?]|$)/);
    if(init.method==='POST')expect([observationEndpoint,viewEndpoint]).toContain(url);
    if(init.method==='GET')expect(url).not.toBe(`${production}/jobs/image/${native.queued_job.id}`);
  }
  expect(screen.queryByRole('heading',{name:'仅续接原节点任务'})).toBeNull();expect(screen.queryByRole('heading',{name:'只读续接原节点任务'})).toBeNull();
}
beforeEach(()=>{
  vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);localStorage.clear();
  // Existing location preference only; the operation itself must not touch storage.
  rememberLocalStudioResume(native.project,{module:'IMAGE',view:'TASKS',stage:'M4',interfaceMode:'PROFESSIONAL'});
  useStudio.setState({novelId:native.project,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:''});
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);server();
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('explicitly reads the observed full nonempty record without an editor, content fetch, latest GET or browser storage',async()=>{
  const open=await observed();expect(count(viewEndpoint)).toBe(0);const before=fetcher.mock.calls.length;
  const get=vi.spyOn(Storage.prototype,'getItem'),set=vi.spyOn(Storage.prototype,'setItem');const action=retained(open);
  await act(async()=>{action();action();});await screen.findByRole('region',{name:'原目标关联画布只读记录'});
  await waitFor(()=>expect(child().textContent).toContain(native.view.canvas.definition.cards[0].id));
  expect(count(viewEndpoint)).toBe(1);expect(fetcher.mock.calls.slice(before).map(([url,init])=>[url,init.method])).toEqual([[viewEndpoint,'POST']]);
  const request=JSON.parse(String(fetcher.mock.calls.find(([url])=>url===viewEndpoint)![1].body));
  expect(request).toEqual({expected_version:native.queued_job.version,expected_request_digest:native.queued_job.request_digest,
    expected_incarnation:native.observation.incarnation,expected_canvas_version:native.observation.canvas.version,expected_canvas_digest:native.observation.canvas.definition_digest});
  const card=native.view.canvas.definition.cards[0];expect(child().textContent).toContain(String(card.position.x));expect(child().textContent).toContain(String(card.position.y));
  expect(child().textContent).toContain('此保存版本没有原请求节点 ID 对应的卡片');
  expect(child().querySelector('img,video,audio,iframe,[src]')).toBeNull();
  expect(screen.getByRole('button',{name:'任务中心'}).getAttribute('aria-pressed')).toBe('true');expect(get).not.toHaveBeenCalled();expect(set).not.toHaveBeenCalled();noOtherOwners();
});

it('retains unsaved preferences when the record is opened and explicitly closed',async()=>{
  await observed();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep unsaved target-view preferences'}});fireEvent.click(viewButton());
  await waitFor(()=>expect(child().textContent).toContain(native.view.canvas.definition.cards[0].id));
  expect(screen.queryByRole('button',{name:'确认离开'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'关闭关联画布记录'}));
  expect(screen.queryByRole('region',{name:'原目标关联画布只读记录'})).toBeNull();
  expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep unsaved target-view preferences');noOtherOwners();
});

it('retires the child synchronously on parent refresh and rejects the late old view response',async()=>{
  let release!:(value:Response)=>void;server(url=>url===viewEndpoint?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  await observed();fireEvent.click(viewButton());await waitFor(()=>expect(release).toBeTypeOf('function'));
  fireEvent.click(screen.getByRole('button',{name:'重新核对保存状态'}));expect(screen.queryByRole('region',{name:'原目标关联画布只读记录'})).toBeNull();
  await act(async()=>release(json(native.view)));await waitFor(()=>expect(count(observationEndpoint)).toBe(2));
  expect(screen.queryByRole('region',{name:'原目标关联画布只读记录'})).toBeNull();expect(count(viewEndpoint)).toBe(1);noOtherOwners();
});

it('does not let old observation/child callbacks revive or close a new same-pin observation session',async()=>{
  await observed();const oldOpen=retained(viewButton());fireEvent.click(viewButton());
  await waitFor(()=>expect(child().textContent).toContain(native.view.canvas.definition.cards[0].id));const oldClose=retained(screen.getByRole('button',{name:'关闭关联画布记录'}));
  fireEvent.click(screen.getByRole('button',{name:'重新核对保存状态'}));await waitFor(()=>expect(count(observationEndpoint)).toBe(2));await screen.findByText(/当前保存版本已变化/);
  await act(async()=>oldOpen());expect(count(viewEndpoint)).toBe(1);expect(screen.queryByRole('region',{name:'原目标关联画布只读记录'})).toBeNull();
  fireEvent.click(viewButton());await waitFor(()=>expect(child().textContent).toContain(native.view.canvas.definition.cards[0].id));
  await act(async()=>oldClose());expect(child().textContent).toContain(native.view.canvas.definition.cards[0].id);expect(count(viewEndpoint)).toBe(2);noOtherOwners();
});

it.each([404,409])('keeps TASKS and the draft on exact-version read %s without automatically reading latest or refreshing observation',async status=>{
  server(url=>url===viewEndpoint?json({code:'TARGET_VIEW_UNAVAILABLE',message:'The exact record is unavailable'},status):undefined);
  await observed();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep draft after failed exact read'}});fireEvent.click(viewButton());
  await screen.findByRole('alert');expect(count(observationEndpoint)).toBe(1);expect(count(viewEndpoint)).toBe(1);
  expect(screen.getByRole('button',{name:'任务中心'}).getAttribute('aria-pressed')).toBe('true');
  expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep draft after failed exact read');noOtherOwners();
});

it('rejects retained view callbacks after an authoritative READ revocation',async()=>{
  server(url=>url===viewEndpoint?json({code:'READ_REVOKED',message:'Read revoked'},403):undefined);
  const open=retained(await observed());await act(async()=>open());
  await waitFor(()=>expect(screen.queryByRole('button',{name:inspectName})).toBeNull());
  await act(async()=>open());expect(count(viewEndpoint)).toBe(1);noOtherOwners();
});

it('does not expose a late full record after Workspace unmount',async()=>{
  let release!:(value:Response)=>void;server(url=>url===viewEndpoint?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  await observed();fireEvent.click(viewButton());await waitFor(()=>expect(release).toBeTypeOf('function'));cleanup();
  await act(async()=>release(json(native.view)));expect(count(viewEndpoint)).toBe(1);expect(screen.queryByRole('region',{name:'原目标关联画布只读记录'})).toBeNull();
});
