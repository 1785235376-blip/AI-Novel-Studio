// @vitest-environment jsdom
/** The captured File record contains a manually seeded metadata reference only:
 * it proves neither image bytes nor formal adoption, approval or model output.
 * Adversarial replies below are explicitly SOFTWARE projections. */
import {act,cleanup,render,screen,waitFor} from '@testing-library/react';
import {Blob as NodeBlob} from 'node:buffer';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_target_view.json';
import legacy from '../../../tests/fixtures/cloud_canvas_node_observe.json';
import {studioProductionClient} from './studioProductionClient';
import {studioClient} from './studioClient';
import type {StudioProductionTask} from '../taskcenter/studioProductionTask';
import {readCanvasImageNodeTargetView} from './canvasImageNodeTargetView';
import {CanvasImageNodeTargetViewPanel} from './CanvasImageNodeTargetViewPanel';

const endpoint=`/api/projects/${native.project}/studio/production/jobs/image/${native.queued_job.id}/target-view`;
const job=()=>structuredClone(native.queued_job) as unknown as StudioProductionTask;
const pin=()=>({incarnation:native.observation.incarnation,version:native.observation.canvas.version,definition_digest:native.observation.canvas.definition_digest});
const payload=()=>structuredClone(native.view);
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>;
function server(value:unknown=payload(),status=200){fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  if(url!==endpoint||init.method!=='POST')throw new Error(`Forbidden latest/other owner read: ${init.method} ${url}`);return json(value,status);
});vi.stubGlobal('fetch',fetcher);}
const client=()=>studioProductionClient(native.project,{sessionToken:''});
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);server();});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('reads the exact observed pin as the original full PUBLIC record through one protected POST',async()=>{
  const result=await client().readImageNodeTargetView(job(),pin());
  expect(result).toEqual(native.view);expect(result.canvas.definition.cards.length).toBeGreaterThan(0);
  expect(result.canvas.definition.cards).toEqual(native.view.canvas.definition.cards);
  expect(result.canvas.reference_states).toEqual(native.view.canvas.reference_states);
  expect(result.canvas.execution_authority).toBe(false);expect(result.canvas.binary_content_verified).toBe(false);expect(result.automatic_actions).toBe(false);
  expect(fetcher).toHaveBeenCalledOnce();expect(JSON.parse(String(fetcher.mock.calls[0][1].body))).toEqual({expected_version:native.queued_job.version,
    expected_request_digest:native.queued_job.request_digest,expected_incarnation:pin().incarnation,
    expected_canvas_version:pin().version,expected_canvas_digest:pin().definition_digest});
});

it.each(['job','canvas-id','scope','incarnation','canvas-version','canvas-digest','authority','binary','card-position','reference-state','extra'] as const)(
  'rejects inconsistent SOFTWARE %s without latest substitution or asset/content lookup',async kind=>{
    const value=payload();
    if(kind==='job')value.job.version++;
    if(kind==='canvas-id')value.canvas.id='other-canvas';
    if(kind==='scope')value.canvas.scope={...value.canvas.scope,novel_id:'other-project'};
    if(kind==='incarnation')value.incarnation='file:00000000-0000-0000-0000-000000000001';
    if(kind==='canvas-version')value.canvas.version++;
    if(kind==='canvas-digest')value.canvas.definition_digest='a'.repeat(64);
    if(kind==='authority')value.canvas.execution_authority=true;
    if(kind==='binary')value.canvas.binary_content_verified=true;
    if(kind==='card-position')value.canvas.definition.cards[0].position.x=Number.POSITIVE_INFINITY;
    if(kind==='reference-state')value.canvas.reference_states[0].card_id='other-card';
    const reply=kind==='extra'?{...value,internal_intent:'SOFTWARE_FORBIDDEN_FIELD'}:value;
    server(reply);await expect(client().readImageNodeTargetView(job(),pin())).rejects.toThrow();expect(fetcher).toHaveBeenCalledOnce();
  });

it.each([403,404,409])('preserves protected target-view HTTP %s and sends no fallback GET',async status=>{
  server({code:'TARGET_VIEW_UNAVAILABLE',message:'The exact record is unavailable'},status);
  await expect(client().readImageNodeTargetView(job(),pin())).rejects.toMatchObject({status});expect(fetcher).toHaveBeenCalledOnce();
});

it('rejects an invalid observed pin before transport',async()=>{
  await expect(client().readImageNodeTargetView(job(),{...pin(),version:0})).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
});

it('reuses the old public decoder without changing original GET/history compatibility',async()=>{
  const base=`/api/projects/${legacy.project}/studio/canvas-views/${legacy.canvas.id}`;
  fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
    if(init.method!=='GET')throw new Error('Legacy compatibility case reads metadata only');
    if(url===base)return json(legacy.canvas);if(url===`${base}/history`)return json(legacy.history);throw new Error('Unexpected legacy owner');
  });vi.stubGlobal('fetch',fetcher);
  const views=studioClient(legacy.project,{sessionToken:''}).graphs.canvasViews!;
  expect(await views.get(legacy.canvas.id)).toEqual(legacy.canvas);expect(await views.history(legacy.canvas.id)).toEqual(legacy.history);
  expect(fetcher.mock.calls.map(([url])=>url)).toEqual([base,`${base}/history`]);
});

const source=()=>({job:job(),key:'exact-observed-source-A',isCurrent:()=>true});
const input=(patch:Partial<Parameters<typeof readCanvasImageNodeTargetView>[0]>={})=>({projectId:native.project,branchId:null,client:client(),source:source(),pin:pin(),
  read:<T,>(work:()=>Promise<T>)=>work(),...patch});

it('rejects a deferred request after its exact observation pin changes, before any send',async()=>{
  let release!:()=>void;const request=input({read:async work=>{await new Promise<void>(resolve=>{release=resolve;});return work();}});
  const pending=readCanvasImageNodeTargetView(request),rejected=expect(pending).rejects.toThrow();
  await waitFor(()=>expect(release).toBeTypeOf('function'));request.pin.version++;release();await rejected;expect(fetcher).not.toHaveBeenCalled();
});

it('checks source retirement at actual deferred dispatch rather than trusting the old row',async()=>{
  let current=true,release!:()=>void;const pending=readCanvasImageNodeTargetView(input({source:{...source(),isCurrent:()=>current},read:async work=>{
    await new Promise<void>(resolve=>{release=resolve;});return work();
  }})),rejected=expect(pending).rejects.toThrow();
  await waitFor(()=>expect(release).toBeTypeOf('function'));current=false;release();await rejected;expect(fetcher).not.toHaveBeenCalled();
});

it('aborts an ignored late response without reading current/latest or another owner',async()=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  const controller=new AbortController(),pending=readCanvasImageNodeTargetView(input({signal:controller.signal})),rejected=expect(pending).rejects.toThrow();
  await waitFor(()=>expect(release).toBeTypeOf('function'));controller.abort();await rejected;
  await act(async()=>release(json(native.view)));expect(fetcher).toHaveBeenCalledOnce();
});

type ChildProps=Parameters<typeof CanvasImageNodeTargetViewPanel>[0];
let childProps:ChildProps;
function Child(){return <CanvasImageNodeTargetViewPanel {...childProps}/>;}
it.each(['client','project','pin','source'] as const)('permanently retires a mounted record after %s A/B/A',async kind=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  childProps={...input(),onUnavailable:vi.fn(),onClose:vi.fn()};const a=childProps,view=render(<Child/>);
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  if(kind==='client')childProps={...a,client:client()};if(kind==='project')childProps={...a,projectId:'other-project'};
  if(kind==='pin')childProps={...a,pin:{...a.pin,version:a.pin.version+1}};
  if(kind==='source')childProps={...a,source:{...a.source,key:'new-observation-B'}};
  view.rerender(<Child/>);childProps=a;view.rerender(<Child/>);
  await act(async()=>release(json(native.view)));
  expect(screen.queryByText(`卡片 ${native.view.canvas.definition.cards[0].id}`)).toBeNull();expect(fetcher).toHaveBeenCalledOnce();
});
