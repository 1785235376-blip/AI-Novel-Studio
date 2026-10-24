// @vitest-environment jsdom
/** Real UI/helpers/clients with SOFTWARE HTTP replies from the synthetic File
 * capture. A second Job/list drift/ACK-loss are software interleavings only;
 * no provider, image bytes, review or real user task is executed here. */
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {Blob as NodeBlob} from 'node:buffer';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_job_discard.json';
import {STUDIO_IMAGE_NODE_JOB_FIELDS} from './studioProductionClient';
import type {StudioProductionTask} from '../taskcenter/studioProductionTask';
import {useStudio} from '../store';
import {useLocalHostSession} from '../localHostSession';
import {IndependentStudioWorkspace} from './IndependentStudioWorkspace';
import {rememberLocalStudioResume} from './studioWorkspaceResume';

type Job=StudioProductionTask&{attempt:number};
const a=()=>structuredClone(native.selected_job) as unknown as Job;
const base=`/api/projects/${native.project}/studio`,production=`${base}/production`;
const readUrl=(job:Job)=>`${production}/jobs/image/${job.id}/node-observation`,writeUrl=(job:Job)=>`${production}/jobs/image/${job.id}/node-discard`;
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const projection=(job:Job)=>Object.fromEntries(STUDIO_IMAGE_NODE_JOB_FIELDS.map(key=>[key,(job as unknown as Record<string,unknown>)[key]]));
const metadata=(job:Job)=>({...native.observation,job:projection(job),target:job.command!.canvas_image_node!,incarnation:job.command!.canvas_image_node!.incarnation});
function softwareB():Job{const original=a();return{...original,id:'software-second-job',request_id:'software-second-request',request_digest:'c'.repeat(64),
  command:{...original.command!,request_id:'software-second-request'}};}
function softwareAck(job:Job){return{...native.discard,job:{...projection(job),version:job.version+1,status:'CANCELLED',cancellation_mode:'LOCAL_RESULT_DISCARD',
  remote_compute_may_continue:true,updated_at:native.discard.job.updated_at},target:job.command!.canvas_image_node!,incarnation:job.command!.canvas_image_node!.incarnation};}
const afterJob=(version=native.after.job.version)=>({...native.selected_job,...native.after.job,version}) as unknown as Job;
let rows:Job[],canWrite:boolean,fetcher:ReturnType<typeof vi.fn>,metas:Map<string,unknown>,acks:Map<string,unknown>,onModuleChange:ReturnType<typeof vi.fn>;
type Override=(url:string,init:RequestInit)=>Response|Promise<Response>|undefined;
function server(override?:Override){fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const changed=override?.(url,init);if(changed!==undefined)return await changed;
  if(url===base)return json({project:{id:native.project,title:'Discard metadata fixture',incarnation:native.observation.incarnation,entry_kind:'NEUTRAL_STUDIO'},
    preferences:{version:1,intents:[],preset:'BLANK',custom_intent:''},capabilities:{can_mutate:canWrite,can_review:false,manual_import:true,manual_export:true,
      model_required:false,chapter_required:false,intent_is_permission:false,media_validator_configured:true,asset_kinds:['image','video','audio']}});
  if(url===`${production}/jobs`&&init.method==='GET')return json({items:rows});
  const match=url.match(/\/jobs\/image\/([^/]+)\/(node-observation|node-discard)$/);
  if(match&&init.method==='POST')return json((match[2]==='node-observation'?metas:acks).get(match[1]));
  if(url.includes('/experimental/workspace/tasks?'))return json({items:[],unavailable:[],truncated:false,executor:false,refresh:'MANUAL',automatic_retries:false});
  if((init.method||'GET')==='GET')return json({code:'UNRELATED_OWNER_UNAVAILABLE',message:'No other owner available'},404);
  throw new Error(`Forbidden fallback, Canvas or provider action: ${init.method} ${url}`);
});vi.stubGlobal('fetch',fetcher);}
function mount(){const query=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});return render(<QueryClientProvider client={query}>
  <IndependentStudioWorkspace projectId={native.project} context={{sessionToken:''}} scope={{workspace:'本机作品',project:'Discard metadata fixture',storyline:'默认故事线',branch:'主线'}}
    actor="作者" module="IMAGE" onModuleChange={onModuleChange} onProjectChoice={vi.fn()}/></QueryClientProvider>);}
const prepName=(job=a())=>`放弃此排队任务的本地采用 ${job.id} v${job.version}`;
const detailName=(job:Job)=>`只读查看原节点任务 ${job.id} v${job.version}`;
const checkbox=()=>screen.getByLabelText('我确认只放弃此排队任务的本地采用资格') as HTMLInputElement;
const confirm=()=>screen.getByRole('button',{name:'确认放弃本地采用资格'});
const panel=()=>screen.getByRole('region',{name:'原节点排队任务放弃采用确认'});
const traces=()=>screen.getByRole('region',{name:'原任务放弃采用结果记录'});
const writes=()=>fetcher.mock.calls.filter(([url])=>url.endsWith('/node-discard')).length;
const reads=()=>fetcher.mock.calls.filter(([url])=>url.endsWith('/node-observation')).length;
const loaded=()=>screen.findByText(/已读取原任务元数据，尚未提交放弃采用/);
function retained(button:HTMLElement){const key=Object.keys(button).find(name=>name.startsWith('__reactProps$'))!;return(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}
async function prepare(job=a(),initial=true){if(initial)mount();const button=await screen.findByRole('button',{name:prepName(job)});
  await waitFor(()=>expect((button as HTMLButtonElement).disabled).toBe(false));fireEvent.click(button);await loaded();}
async function approve(){await waitFor(()=>expect(checkbox().disabled).toBe(false));fireEvent.click(checkbox());await waitFor(()=>expect((confirm() as HTMLButtonElement).disabled).toBe(false));}
async function submit(){await approve();fireEvent.click(confirm());}
function noOtherOwners(){for(const[url,init]of fetcher.mock.calls){
  expect(url).not.toMatch(/\/(?:assets|providers|preview|execute|cancel|reconcile|review|candidate|content|resolve-create|canvas-views|timelines|graphs|target-observation|target-view)(?:[/?]|$)/);
  if(init.method==='POST')expect(url).toMatch(/\/node-(?:observation|discard)$/);
  if(init.method==='GET')expect(url).not.toMatch(/\/jobs\/image\/[^/]+$/);
}}
async function freshList(){fireEvent.click(screen.getByRole('button',{name:'重新读取 Studio 制作任务'}));await waitFor(()=>expect((screen.getByRole('button',{name:'重新读取 Studio 制作任务'}) as HTMLButtonElement).disabled).toBe(false));}
beforeEach(()=>{
  vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);localStorage.clear();rememberLocalStudioResume(native.project,{module:'IMAGE',view:'TASKS',stage:'M4',interfaceMode:'PROFESSIONAL'});
  useStudio.setState({novelId:native.project,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:''});
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);rows=[a()];canWrite=true;onModuleChange=vi.fn();
  metas=new Map([[a().id,native.observation]]);acks=new Map([[a().id,native.discard]]);server();
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('prepares by read only, retires consent ABA, confirms once and blocks stale-snapshot close/reopen resends',async()=>{
  await prepare();expect(reads()).toBe(1);expect(writes()).toBe(0);const get=vi.spyOn(Storage.prototype,'getItem'),set=vi.spyOn(Storage.prototype,'setItem');
  await act(async()=>retained(confirm())());expect(writes()).toBe(0);await approve();const oldConfirm=retained(confirm());
  fireEvent.click(checkbox());fireEvent.click(checkbox());await act(async()=>oldConfirm());expect(writes()).toBe(0);
  const send=retained(confirm());await act(async()=>{send();send();});await screen.findByRole('region',{name:'原任务放弃采用回执'});
  expect(writes()).toBe(1);expect(within(screen.getByRole('region',{name:'原任务放弃采用回执'})).getByText(/不确认远端停止/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'关闭并返回任务列表'}));
  // SOFTWARE stale preflight after ACK: the per-workspace claim must still stop a resend.
  await prepare(a(),false);if(!checkbox().disabled)fireEvent.click(checkbox());await act(async()=>retained(confirm())());
  expect(writes()).toBe(1);expect(get).not.toHaveBeenCalled();expect(set).not.toHaveBeenCalled();noOtherOwners();
});

it('allows read-only metadata under software can_mutate=false but cannot prepare or send the write action',async()=>{
  canWrite=false;mount();fireEvent.click(await screen.findByRole('button',{name:detailName(a())}));
  await screen.findByText(/这是本次读取的任务元数据快照/);const action=screen.queryByRole('button',{name:prepName()});
  if(action)await act(async()=>retained(action)());expect(reads()).toBe(1);expect(writes()).toBe(0);
  expect(screen.queryByRole('region',{name:'原节点排队任务放弃采用确认'})).toBeNull();noOtherOwners();
});

it('keeps an unacknowledged send UNKNOWN without false not-submitted text, automatic reads or close/reopen retries',async()=>{
  server(url=>url===writeUrl(a())?json({code:'ACK_LOST',message:'No acknowledgement'},500):undefined);
  await prepare();const beforeLists=fetcher.mock.calls.filter(([url])=>url===`${production}/jobs`).length;await submit();
  await within(panel()).findByText(/结果待核对（UNKNOWN）/);expect(panel().textContent).not.toContain('尚未提交放弃采用');
  expect(writes()).toBe(1);expect(reads()).toBe(1);expect(fetcher.mock.calls.filter(([url])=>url===`${production}/jobs`)).toHaveLength(beforeLists);
  fireEvent.click(screen.getByRole('button',{name:'关闭并返回任务列表'}));await prepare(a(),false);
  if(!checkbox().disabled)fireEvent.click(checkbox());await act(async()=>retained(confirm())());expect(writes()).toBe(1);noOtherOwners();
});

it('preserves A UNKNOWN after a separate SOFTWARE B ACK, then recovers only A through explicit same-ID new-pin metadata',async()=>{
  const b=softwareB();rows=[a(),b];metas.set(b.id,metadata(b));acks.set(b.id,softwareAck(b));
  server(url=>url===writeUrl(a())?json({code:'ACK_LOST',message:'No acknowledgement'},500):undefined);
  await prepare();await submit();await within(panel()).findByText(/结果待核对（UNKNOWN）/);
  await prepare(b,false);await submit();await screen.findByRole('region',{name:'原任务放弃采用回执'});
  expect(traces().textContent).toContain(a().id);expect(traces().textContent).toContain(b.id);expect(traces().textContent).toContain('UNKNOWN');
  fireEvent.click(screen.getByRole('button',{name:'关闭并返回任务列表'}));const after=afterJob();rows=[after,b];metas.set(a().id,native.after);
  await freshList();fireEvent.click(await screen.findByRole('button',{name:detailName(after)}));await screen.findByText(/原任务状态已核对为 CANCELLED/);
  expect(traces().textContent).not.toContain('UNKNOWN');expect(writes()).toBe(2);
  fireEvent.click(screen.getByRole('tab',{name:'小说'}));await waitFor(()=>expect(onModuleChange).toHaveBeenCalledWith('NOVEL'));
  expect(screen.queryByLabelText('确认保留原请求待核对后离开')).toBeNull();noOtherOwners();
});

it('does not clear an unknown trace for an unmatched newer version or a late retired matching read',async()=>{
  let release!:(value:Response)=>void,holdRead=false;
  server((url,init)=>{
    if(url===writeUrl(a()))return json({code:'ACK_LOST',message:'No acknowledgement'},500);
    if(url===readUrl(a())&&holdRead){const body=JSON.parse(String(init.body));if(body.expected_version===native.after.job.version)return new Promise<Response>(resolve=>{release=resolve;});}
  });
  await prepare();await submit();await within(panel()).findByText(/结果待核对（UNKNOWN）/);fireEvent.click(screen.getByRole('button',{name:'关闭并返回任务列表'}));
  const correct=afterJob();rows=[correct];metas.set(a().id,native.after);holdRead=true;await freshList();
  fireEvent.click(await screen.findByRole('button',{name:detailName(correct)}));await waitFor(()=>expect(release).toBeTypeOf('function'));
  const other=afterJob(correct.version+1);rows=[other];metas.set(a().id,{...native.after,job:{...native.after.job,version:other.version}});await freshList();
  fireEvent.click(await screen.findByRole('button',{name:detailName(other)}));await screen.findByText(/这是本次读取的任务元数据快照/);
  await act(async()=>release(json(native.after)));expect(traces().textContent).toContain('UNKNOWN');expect(traces().textContent).not.toContain('状态已核对');expect(writes()).toBe(1);noOtherOwners();
});

it('does not let a stale dispatched403 revoke a new source or make another write',async()=>{
  const b=softwareB();rows=[a(),b];metas.set(b.id,metadata(b));let release!:(value:Response)=>void;
  server(url=>url===writeUrl(a())?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  await prepare();await submit();await waitFor(()=>expect(release).toBeTypeOf('function'));
  fireEvent.click(screen.getByRole('button',{name:'关闭并返回任务列表'}));
  await prepare(b,false);await act(async()=>release(json({code:'OLD_SOURCE_DENIED',message:'Old source denied'},403)));
  expect(screen.getByRole('button',{name:prepName(b)})).toBeTruthy();expect(panel().textContent).toContain(b.id);expect(writes()).toBe(1);noOtherOwners();
});

it('keeps generic UNKNOWN leave protection after current403 while hiding old Job/request identifiers even in the leave dialog',async()=>{
  server(url=>url===writeUrl(a())?json({code:'CURRENT_DENIED',message:'Current write denied'},403):undefined);
  await prepare();await submit();await waitFor(()=>expect(screen.queryByRole('button',{name:prepName()})).toBeNull());
  expect(traces().textContent).toMatch(/待核对|尚未核对/);
  for(const privateValue of [a().id,a().request_digest,a().request_id])expect(document.body.textContent).not.toContain(privateValue);
  fireEvent.click(screen.getByRole('tab',{name:'小说'}));await screen.findByLabelText('确认保留原请求待核对后离开');
  expect((screen.getByRole('button',{name:'确认离开'}) as HTMLButtonElement).disabled).toBe(true);expect(onModuleChange).not.toHaveBeenCalled();
  for(const privateValue of [a().id,a().request_digest,a().request_id])expect(document.body.textContent).not.toContain(privateValue);
  expect(writes()).toBe(1);noOtherOwners();
});

it('does not adopt a late ACK after actual Workspace unmount or send another request',async()=>{
  let release!:(value:Response)=>void;server(url=>url===writeUrl(a())?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  await prepare();await submit();await waitFor(()=>expect(release).toBeTypeOf('function'));cleanup();await act(async()=>release(json(native.discard)));
  expect(writes()).toBe(1);expect(screen.queryByRole('region',{name:'原任务放弃采用回执'})).toBeNull();noOtherOwners();
});

it('protects beforeunload while the actual host write is pending before the dispatch claim exists',async()=>{
  await prepare();await approve();const digest=webcrypto.subtle.digest.bind(webcrypto.subtle);let calls=0,release!:()=>void;
  vi.spyOn(webcrypto.subtle,'digest').mockImplementation(async(algorithm,data)=>{
    if(++calls===2)await new Promise<void>(resolve=>{release=resolve;});
    return digest(algorithm,data);
  });
  fireEvent.click(confirm());await waitFor(()=>expect(release).toBeTypeOf('function'));
  expect(calls).toBe(2);expect(writes()).toBe(0);expect(screen.queryByRole('region',{name:'原任务放弃采用结果记录'})).toBeNull();
  const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(true);
  await act(async()=>release());await screen.findByRole('region',{name:'原任务放弃采用回执'});expect(writes()).toBe(1);noOtherOwners();
});
