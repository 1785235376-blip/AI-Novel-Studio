// @vitest-environment jsdom
/** Original route JSON capture through the real client. Adversarial and
 * unchanged variants are SOFTWARE metadata projections, never media evidence. */
import {act,cleanup,render,screen,waitFor} from '@testing-library/react';
import {webcrypto} from 'node:crypto';
import {Blob as NodeBlob} from 'node:buffer';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_target_observation.json';
import {studioProductionClient} from './studioProductionClient';
import type {StudioProductionTask} from '../taskcenter/studioProductionTask';
import {readCanvasImageNodeTarget} from './canvasImageNodeTargetObservation';
import {CanvasImageNodeTargetPanel} from './CanvasImageNodeTargetPanel';

const endpoint=`/api/projects/${native.project}/studio/production/jobs/image/${native.queued_job.id}/target-observation`;
const selected=()=>structuredClone(native.queued_job) as unknown as StudioProductionTask;
const payload=()=>structuredClone(native.observation);
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>;
function server(value:unknown=payload(),status=200){fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  if(url!==endpoint||init.method!=='POST')throw new Error(`Unexpected owner fallback: ${init.method} ${url}`);
  return json(value,status);
});vi.stubGlobal('fetch',fetcher);}
const client=()=>studioProductionClient(native.project,{sessionToken:''});
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);server();});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('decodes the original CURRENT_CHANGED observation using only the existing-owner observation route',async()=>{
  const result=await client().observeImageNodeTarget(selected());
  expect(result).toEqual(native.observation);expect(result.comparison).toBe('CURRENT_CHANGED');
  expect(fetcher).toHaveBeenCalledOnce();const[url,init]=fetcher.mock.calls[0];expect(url).toBe(endpoint);
  expect(JSON.parse(String(init.body))).toEqual({expected_version:native.queued_job.version,expected_request_digest:native.queued_job.request_digest});
  expect(result.automatic_actions).toBe(false);expect(result.canvas.execution_authority).toBe(false);expect(result.canvas.binary_content_verified).toBe(false);
});

it('admits SOFTWARE current-match metadata without treating the target pin as execution authority',async()=>{
  const value=payload();value.canvas.version=value.target.canvas_version;value.canvas.definition_digest=value.target.canvas_digest;
  value.history.current_version=value.target.canvas_version;value.history.current_definition_digest=value.target.canvas_digest;value.comparison='CURRENT_MATCH';
  server(value);const result=await client().observeImageNodeTarget(selected());expect(result.comparison).toBe('CURRENT_MATCH');expect(result.automatic_actions).toBe(false);
});

it('classifies SOFTWARE higher version with the same digest as changed rather than current-match',async()=>{
  const value=payload();value.canvas.version=value.target.canvas_version+1;value.canvas.definition_digest=value.target.canvas_digest;
  value.history.current_version=value.canvas.version;value.history.current_definition_digest=value.target.canvas_digest;value.comparison='CURRENT_CHANGED';
  server(value);expect((await client().observeImageNodeTarget(selected())).comparison).toBe('CURRENT_CHANGED');
});

it.each(['history-version','history-digest','history-empty','history-current','incarnation','scope','job-version','job-status','target-node','comparison','automatic-actions'] as const)(
  'rejects inconsistent SOFTWARE %s with no GET/resume/config/content fallback',async kind=>{
    const value=payload();
    if(kind==='history-version')value.history.target_version++;
    if(kind==='history-digest')value.history.target_definition_digest='a'.repeat(64);
    if(kind==='history-empty')value.history.target_empty=false;
    if(kind==='history-current')value.history.current_version++;
    if(kind==='incarnation')value.incarnation='file:00000000-0000-0000-0000-000000000001';
    if(kind==='scope')value.canvas.scope={...value.canvas.scope,novel_id:'other-project'};
    if(kind==='job-version')value.job.version++;
    if(kind==='job-status')value.job.status='UNKNOWN';
    if(kind==='target-node')value.target.node_id='other-node';
    if(kind==='comparison')value.comparison='CURRENT_MATCH';
    if(kind==='automatic-actions')value.automatic_actions=true;
    server(value);await expect(client().observeImageNodeTarget(selected())).rejects.toThrow();expect(fetcher).toHaveBeenCalledOnce();
  });

it.each([401,403,404,409])('preserves original observation HTTP %s and does not probe other owners',async status=>{
  server({code:'TARGET_OBSERVATION_UNAVAILABLE',message:'Original observation unavailable'},status);
  await expect(client().observeImageNodeTarget(selected())).rejects.toMatchObject({status});expect(fetcher).toHaveBeenCalledOnce();
});

it.each(['project','owner','capsule'] as const)('rejects a foreign selected %s before any HTTP call',async kind=>{
  const job=selected();if(kind==='project')job.novel_id='other-project';if(kind==='owner')job.owner='video';if(kind==='capsule')delete job.command!.canvas_image_node;
  await expect(client().observeImageNodeTarget(job)).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
});

const source=()=>({job:selected(),key:'explicit-source-A',isCurrent:()=>true});
const helper=(patch:Partial<Parameters<typeof readCanvasImageNodeTarget>[0]>={})=>({projectId:native.project,branchId:null,client:client(),source:source(),
  read:<T,>(work:()=>Promise<T>)=>work(),...patch});

it('checks the helper lease at actual deferred read dispatch',async()=>{
  let current=true,release!:()=>void;
  const result=readCanvasImageNodeTarget(helper({source:{...source(),isCurrent:()=>current},read:async work=>{
    await new Promise<void>(resolve=>{release=resolve;});return work();
  }}));const rejected=expect(result).rejects.toThrow();
  await waitFor(()=>expect(release).toBeTypeOf('function'));current=false;release();await rejected;expect(fetcher).not.toHaveBeenCalled();
});

it('aborts promptly even if the observation transport ignores cancellation, without another owner read',async()=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  const controller=new AbortController(),result=readCanvasImageNodeTarget(helper({signal:controller.signal}));
  const rejected=expect(result).rejects.toThrow();await waitFor(()=>expect(release).toBeTypeOf('function'));
  controller.abort();await rejected;release(json(native.observation));expect(fetcher).toHaveBeenCalledOnce();
});

type PanelProps=Parameters<typeof CanvasImageNodeTargetPanel>[0];
let props:PanelProps;
function Panel(){return <CanvasImageNodeTargetPanel {...props}/>;}
const panelProps=():PanelProps=>({projectId:native.project,branchId:null,client:client(),source:source(),read:work=>work(),onUnavailable:vi.fn(),onClose:vi.fn()});
function retained(button:HTMLElement){const key=Object.keys(button).find(name=>name.startsWith('__reactProps$'))!;return(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}

it.each(['client','project','source','view','read-method'] as const)('permanently retires the same panel after observed %s A/B/A',async kind=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  props=panelProps();const a=props,view=render(<Panel/>);
  await waitFor(()=>expect(release).toBeTypeOf('function'));const refresh=retained(screen.getByRole('button',{name:'重新核对保存状态'}));
  if(kind==='client')props={...a,client:client()};if(kind==='project')props={...a,projectId:'other-project'};
  if(kind==='source')props={...a,source:{...a.source,key:'explicit-source-B'}};
  if(kind==='view')props={...a,source:{...a.source,isCurrent:()=>false}};
  if(kind==='read-method')props={...a,read:work=>work()};view.rerender(<Panel/>);props=a;view.rerender(<Panel/>);
  await act(async()=>{release(json(native.observation));refresh();});
  expect(screen.queryByText(/当前保存版本已变化/)).toBeNull();expect(fetcher).toHaveBeenCalledOnce();
});
