// @vitest-environment jsdom
/** Actual Workspace/TaskCenter/original panel + clients, with a real File
 * CANCELLED metadata capture. RUNNING/UNKNOWN variants are software projections.
 * No provider, media bytes, File execution, review or approval is invoked. */
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_observe.json';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
import {useStudio} from '../store';
import {useLocalHostSession} from '../localHostSession';
import {IndependentStudioWorkspace,type IndependentStudioProps} from './IndependentStudioWorkspace';

const base=`/api/projects/${native.project}/studio`;
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>,row:typeof native.job,canvas:typeof native.canvas,writable:boolean,blobs:Blob[];
type Override=(url:string,init:RequestInit)=>Response|Promise<Response>|undefined;
function server(override?:Override){
  fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
    const changed=override?.(url,init);if(changed!==undefined)return await changed;
    if(url===base)return json({...native.overview,capabilities:{...native.overview.capabilities,can_mutate:writable,can_review:false}});
    if(url===`${base}/prompts`)return json({...emptyPromptLibrary,project_id:native.project,scope:native.scope});
    if(url.startsWith(`${base}/assets`))return json({items:[]});
    if(url===`${base}/production/jobs`&&init.method==='GET')return json({...native.jobs,items:[row]});
    if(url.endsWith('/jobs/image/resolve-create'))return json(row);
    if(url.endsWith(`/canvas-views/${native.canvas.id}/history`))return json(native.history);
    if(url.endsWith(`/canvas-views/${native.canvas.id}`))return json(canvas);
    if(url.endsWith(`/jobs/image/${native.job.id}`))return json(row);
    if(url.includes('/experimental/workspace/tasks?'))return json({items:[],unavailable:[],truncated:false,executor:false,refresh:'MANUAL',automatic_retries:false});
    if((init.method||'GET')==='GET')return json({code:'UNRELATED_READ_NOT_AVAILABLE',message:'Not part of this bounded fixture'},404);
    throw new Error(`Forbidden mutation in observation fixture: ${init.method} ${url}`);
  });vi.stubGlobal('fetch',fetcher);
}
const workspaceProps=():IndependentStudioProps=>({projectId:native.project,context:{sessionToken:''},
  scope:{workspace:'本机作品',project:'Synthetic query fixture',storyline:'默认故事线',branch:'主线'},actor:'作者',module:'IMAGE',
  onModuleChange:vi.fn(),onProjectChoice:vi.fn()});
function mount(patch:Partial<IndependentStudioProps>={}){
  const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  const tree=(props:IndependentStudioProps)=><QueryClientProvider client={client}><IndependentStudioWorkspace {...props}/></QueryClientProvider>;
  const view=render(tree({...workspaceProps(),...patch}));
  return{...view,rerenderWorkspace:(props:IndependentStudioProps)=>view.rerender(tree(props))};
}
async function tasks(){mount();fireEvent.click(await screen.findByRole('button',{name:'任务中心'}));
  return screen.findByRole('button',{name:`打开原制作任务 ${native.job.id} v${native.job.version}`});}
async function observe(){fireEvent.click(await tasks());await screen.findByRole('heading',{name:'只读续接原节点任务'});}
function metadataOnly(){
  expect(fetcher.mock.calls.some(([url])=>/\/(?:providers|preview|execute|cancel|reconcile|refresh|review|candidate|content|ingest)(?:\?|$)/.test(url))).toBe(false);
  for(const[url,init]of fetcher.mock.calls)if(init.method==='POST')expect(url).toBe(`${base}/production/jobs/image/resolve-create`);
  expect(fetcher.mock.calls.some(([url])=>url.includes('/production/timelines'))).toBe(false);
}
function retained(button:HTMLElement){const key=Object.keys(button).find(name=>name.startsWith('__reactProps$'))!;
  return(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}
function blobText(blob:Blob){return new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(reader.error);reader.readAsText(blob);});}
beforeEach(()=>{
  vi.stubGlobal('crypto',webcrypto);localStorage.clear();row=structuredClone(native.job);canvas=structuredClone(native.canvas);writable=false;blobs=[];
  useStudio.setState({novelId:native.project,chapterId:'',sessionToken:'',actor:undefined,scope:undefined});
  useLocalHostSession.setState({token:'',actorId:''});
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null); // No geometry claim.
  Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn((blob:Blob)=>{blobs.push(blob);return 'blob:metadata-receipt';})});
  Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
  server();
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('opens real cancelled metadata with READ-only authority and exports only the explicit original checked JSON receipt',async()=>{
  const writes=vi.spyOn(Storage.prototype,'setItem');await observe();
  expect(native.evidence_type).toBe('REAL_ORIGINAL_FILE_API_CANCELLED_METADATA_ONLY');
  const prompt=screen.getByLabelText('原任务已确认的提示词') as HTMLTextAreaElement;
  expect(prompt.value).toBe(native.node.prompt);expect(prompt.readOnly).toBe(true);expect(screen.queryByLabelText('本次提示词')).toBeNull();
  for(const name of ['重新读取原任务服务配置','读取原入队任务预览','明确执行当前入队任务','仅创建任务并入队','读取任务列表','新建时间线','添加视频轨道','添加音频轨道'])
    expect(screen.queryByRole('button',{name})).toBeNull();
  expect(blobs).toHaveLength(0);const reads=fetcher.mock.calls.length;
  const read=retained(screen.getByRole('button',{name:'读取当前任务核对'}));
  await act(async()=>{read();read();});
  await screen.findByText('已读取当前任务版本；未重新执行。');expect(fetcher.mock.calls).toHaveLength(reads+1);
  fireEvent.click(screen.getByRole('button',{name:'下载当前已读回执（JSON）'}));expect(blobs).toHaveLength(1);
  const receipt=JSON.parse(await blobText(blobs[0]));
  expect(receipt).toMatchObject({id:native.job.id,novel_id:native.project,status:'CANCELLED',version:native.job.version,attempt:0,output_candidate:null,approved_asset_version:null});
  expect(receipt.command).toMatchObject(native.command);expect(fetcher.mock.calls).toHaveLength(reads+1);
  for(const [key,value] of writes.mock.calls){expect(key).not.toMatch(/rebuild|canvas.*(?:draft|hint|queue|create)/i);expect(value).not.toContain(native.node.prompt);expect(value).not.toContain(native.job.request_id);}
  metadataOnly();
});

it.each(['RUNNING','UNKNOWN'] as const)('opens software-projected %s as observation without any config read or action',async status=>{
  row={...row,status};await observe();const reads=fetcher.mock.calls.length;
  expect(screen.queryByRole('button',{name:'读取原入队任务预览'})).toBeNull();
  expect(screen.queryByRole('button',{name:'明确执行当前入队任务'})).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'读取当前任务核对'}));
  await screen.findByText('已读取当前任务版本；未重新执行。');expect(fetcher.mock.calls).toHaveLength(reads+1);metadataOnly();
});

it('preserves dirty preferences until stale cancelled source is rejected by the original Canvas contract',async()=>{
  writable=true;const open=await tasks();fireEvent.change(screen.getByLabelText('自定义意图'),{target:{value:'keep this unsaved observation draft'}});
  fireEvent.click(open);await screen.findByRole('button',{name:'确认离开'});canvas={...canvas,version:canvas.version+1};
  fireEvent.click(screen.getByLabelText('确认放弃未保存输入'));fireEvent.click(screen.getByRole('button',{name:'确认离开'}));
  await screen.findByText(/原节点画布、范围、代次或版本已改变/);
  expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep this unsaved observation draft');
  expect(screen.queryByRole('heading',{name:'只读续接原节点任务'})).toBeNull();metadataOnly();
});

it('retires old observation read and JSON callbacks after an authoritative READ denial',async()=>{
  await observe();const read=retained(screen.getByRole('button',{name:'读取当前任务核对'})),download=retained(screen.getByRole('button',{name:'下载当前已读回执（JSON）'}));
  server(url=>url.endsWith(`/jobs/image/${native.job.id}`)?json({code:'READ_REVOKED',message:'read revoked'},403):undefined);
  fireEvent.click(screen.getByRole('button',{name:'读取当前任务核对'}));
  await waitFor(()=>expect(screen.queryByRole('heading',{name:'只读续接原节点任务'})).toBeNull());
  await act(async()=>{read();download();});expect(fetcher.mock.calls).toHaveLength(1);expect(blobs).toHaveLength(0);metadataOnly();
});

it('does not adopt a late read-only source after project/client identity A/B/A',async()=>{
  let release!:(value:Response)=>void;
  server(url=>url.endsWith('/jobs/image/resolve-create')?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  const initial={...workspaceProps(),context:{sessionToken:'',localHostToken:'synthetic-observe-A'}};
  const view=mount(initial);fireEvent.click(await screen.findByRole('button',{name:'任务中心'}));
  fireEvent.click(await screen.findByRole('button',{name:`打开原制作任务 ${native.job.id} v${native.job.version}`}));
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  view.rerenderWorkspace({...initial,context:{...initial.context,localHostToken:'synthetic-observe-B'}});
  await screen.findByRole('button',{name:'任务中心'});view.rerenderWorkspace(initial);await screen.findByRole('button',{name:'任务中心'});
  await act(async()=>release(json(native.resolved_job)));
  expect(screen.queryByRole('heading',{name:'只读续接原节点任务'})).toBeNull();
  expect(fetcher.mock.calls.some(([url])=>url.endsWith(`/canvas-views/${native.canvas.id}`))).toBe(false);metadataOnly();
});
