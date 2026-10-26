// @vitest-environment jsdom
/** Original File CANCELLED task metadata. All altered status/candidate cases
 * below are SOFTWARE projections, not File execution/review/media evidence. */
import {act,cleanup,render,screen,waitFor} from '@testing-library/react';
import {Blob as NodeBlob} from 'node:buffer';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_job_observation.json';
import {studioProductionClient,STUDIO_IMAGE_NODE_JOB_FIELDS} from './studioProductionClient';
import type {StudioProductionTask} from '../taskcenter/studioProductionTask';
import {readCanvasImageNodeJobObservation} from './canvasImageNodeJobObservation';
import {CanvasImageNodeJobObservationPanel} from './CanvasImageNodeJobObservationPanel';

const endpoint=`/api/projects/${native.project}/studio/production/jobs/image/${native.selected_job.id}/node-observation`;
const fields=[...STUDIO_IMAGE_NODE_JOB_FIELDS];
const selected=()=>structuredClone(native.selected_job) as unknown as StudioProductionTask;
const payload=()=>structuredClone(native.observation);
const project=(job:StudioProductionTask)=>Object.fromEntries(fields.map(key=>[key,(job as unknown as Record<string,unknown>)[key]]));
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>;
function server(value:unknown=payload(),status=200){fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  if(url!==endpoint||init.method!=='POST')throw new Error(`Forbidden Canvas/Job GET or other owner: ${init.method} ${url}`);return json(value,status);
});vi.stubGlobal('fetch',fetcher);}
const client=()=>studioProductionClient(native.project,{sessionToken:''});
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);server();});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('reads only the original fixed 26-field job projection even when no Canvas/graph reader exists in the test transport',async()=>{
  const result=await client().observeImageNodeJob(selected());expect(result).toEqual(native.observation);
  expect(Object.keys(result.job)).toHaveLength(26);expect(result.canvas_read).toBe(false);expect(result.automatic_actions).toBe(false);
  expect(Object.keys(result.job).sort()).toEqual([...STUDIO_IMAGE_NODE_JOB_FIELDS].sort());
  for(const key of ['execution_recipe','sources','timeline_snapshot','media_measurement'])expect(result.job).not.toHaveProperty(key);
  expect(fetcher).toHaveBeenCalledOnce();expect(JSON.parse(String(fetcher.mock.calls[0][1].body))).toEqual({expected_version:native.selected_job.version,expected_request_digest:native.selected_job.request_digest});
});

it.each(['envelope-extra','full-job','missing-null','canvas-read','command','provider','target','incarnation','job-version','receipt'] as const)(
  'rejects SOFTWARE closed-projection or immutable %s mismatch without a fallback read',async kind=>{
    const value=payload();let reply:unknown=value;
    if(kind==='envelope-extra')reply={...value,canvas:{id:'forbidden-canvas-projection'}};
    if(kind==='full-job')reply={...value,job:native.selected_job};
    if(kind==='missing-null'){const{receipt_digest:_removed,...rest}=value.job;reply={...value,job:rest};}
    if(kind==='canvas-read')reply={...value,canvas_read:true};
    if(kind==='command')reply={...value,job:{...value.job,command:{...value.job.command,prompt:'changed request'}}};
    if(kind==='provider')reply={...value,job:{...value.job,provider:{...value.job.provider,local:false}}};
    if(kind==='target')value.target.node_id='other-node';
    if(kind==='incarnation')value.incarnation='file:00000000-0000-0000-0000-000000000001';
    if(kind==='job-version')value.job.version++;
    if(kind==='receipt')reply={...value,job:{...value.job,receipt_digest:'not-a-receipt-digest'}};
    server(reply);await expect(client().observeImageNodeJob(selected())).rejects.toThrow();expect(fetcher).toHaveBeenCalledOnce();
  });

it.each(['uri','kind'] as const)('rejects SOFTWARE candidate %s outside four image-only metadata keys',async kind=>{
  const candidate={id:'software-metadata-candidate',version:1,digest:'b'.repeat(64),kind:kind==='kind'?'video':'image'};
  const expected={...selected(),status:'AWAITING_REVIEW',receipt_digest:'a'.repeat(64),output_candidate:candidate} as unknown as StudioProductionTask;
  const output=kind==='uri'?{...candidate,uri:'https://forbidden.invalid/not-fetched'}:candidate;
  server({...payload(),job:{...project(expected),output_candidate:output}});
  await expect(client().observeImageNodeJob(expected)).rejects.toThrow();
  expect(fetcher.mock.calls.every(([url])=>url===endpoint)).toBe(true);
});

it('rejects SUCCEEDED even when the SOFTWARE selected and returned statuses agree',async()=>{
  const expected={...selected(),status:'SUCCEEDED'} as StudioProductionTask;server({...payload(),job:project(expected)});
  await expect(client().observeImageNodeJob(expected)).rejects.toThrow();expect(fetcher.mock.calls.every(([url])=>url===endpoint)).toBe(true);
});

it.each([401,403,404,409])('preserves original job-only HTTP %s without reading Canvas or latest',async status=>{
  server({code:'NODE_OBSERVATION_UNAVAILABLE',message:'Original job metadata is unavailable'},status);
  await expect(client().observeImageNodeJob(selected())).rejects.toMatchObject({status});expect(fetcher).toHaveBeenCalledOnce();
});

const source=()=>({job:selected(),key:'job-only-source-A',isCurrent:()=>true});
const input=(patch:Partial<Parameters<typeof readCanvasImageNodeJobObservation>[0]>={})=>({projectId:native.project,branchId:null,client:client(),source:source(),
  read:<T,>(work:()=>Promise<T>)=>work(),...patch});

it('does not forward extra URI/recipe fields from an embedded structural client',async()=>{
  const good=await client().observeImageNodeJob(selected());
  expect(await readCanvasImageNodeJobObservation(input({client:{observeImageNodeJob:async()=>good}}))).toEqual(good);
  const method=vi.fn(async()=>({...good,uri:'https://forbidden.invalid/not-fetched',recipe:{private:'SOFTWARE_FORBIDDEN_FIELD'}}));
  await expect(readCanvasImageNodeJobObservation(input({client:{observeImageNodeJob:method}}))).rejects.toThrow();
  expect(method).toHaveBeenCalledOnce();expect(fetcher).toHaveBeenCalledOnce();
});

it('rechecks its source lease when a deferred host read actually dispatches',async()=>{
  let current=true,release!:()=>void;const result=readCanvasImageNodeJobObservation(input({source:{...source(),isCurrent:()=>current},read:async work=>{
    await new Promise<void>(resolve=>{release=resolve;});return work();
  }})),rejected=expect(result).rejects.toThrow();
  await waitFor(()=>expect(release).toBeTypeOf('function'));current=false;release();await rejected;expect(fetcher).not.toHaveBeenCalled();
});

it('aborts an ignored late response without requesting a different owner',async()=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  const controller=new AbortController(),result=readCanvasImageNodeJobObservation(input({signal:controller.signal})),rejected=expect(result).rejects.toThrow();
  await waitFor(()=>expect(release).toBeTypeOf('function'));controller.abort();await rejected;await act(async()=>release(json(native.observation)));
  expect(fetcher).toHaveBeenCalledOnce();
});

type PanelProps=Parameters<typeof CanvasImageNodeJobObservationPanel>[0];
let props:PanelProps;
function Panel(){return <CanvasImageNodeJobObservationPanel {...props}/>;}
function retained(button:HTMLElement){const key=Object.keys(button).find(name=>name.startsWith('__reactProps$'))!;return(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}

it('retires a denied current panel even when its embedded host onUnavailable callback does nothing',async()=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  props={...input(),onUnavailable:vi.fn(),onClose:vi.fn()};render(<Panel/>);await waitFor(()=>expect(release).toBeTypeOf('function'));
  const refresh=retained(screen.getByRole('button',{name:'重新读取原任务元数据'})),close=retained(screen.getByRole('button',{name:'关闭原任务元数据'}));
  await act(async()=>release(json({code:'READ_DENIED',message:'Read denied'},403)));await waitFor(()=>expect(props.onUnavailable).toHaveBeenCalledOnce());
  await act(async()=>{refresh();close();});expect(fetcher).toHaveBeenCalledOnce();expect(props.onClose).not.toHaveBeenCalled();
});

it.each(['client','project','source','read-method'] as const)('retires the mounted job-only panel across %s A/B/A',async kind=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  props={...input(),onUnavailable:vi.fn(),onClose:vi.fn()};const a=props,view=render(<Panel/>);
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  if(kind==='client')props={...a,client:client()};if(kind==='project')props={...a,projectId:'other-project'};
  if(kind==='source')props={...a,source:{...a.source,key:'job-only-source-B'}};if(kind==='read-method')props={...a,read:work=>work()};
  view.rerender(<Panel/>);props=a;view.rerender(<Panel/>);await act(async()=>release(json(native.observation)));
  expect(screen.queryByText(/这是本次读取的任务元数据快照/)).toBeNull();expect(fetcher).toHaveBeenCalledOnce();
});
