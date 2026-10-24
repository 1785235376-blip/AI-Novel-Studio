// @vitest-environment jsdom
/** Original synthetic File QUEUED/discard metadata capture. Transport and
 * embedded-client failures below are SOFTWARE projections; no provider, media,
 * review or real user job is invoked by these tests. */
import {act,cleanup,waitFor} from '@testing-library/react';
import {Blob as NodeBlob} from 'node:buffer';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_job_discard.json';
import {studioProductionClient,type ProductionJob,type StudioImageNodeJobDiscard,type StudioImageNodeJobObservation} from './studioProductionClient';
import type {StudioProductionTask} from '../taskcenter/studioProductionTask';
import {discardCanvasImageNodeJob} from './canvasImageNodeJobDiscard';

const endpoint=`/api/projects/${native.project}/studio/production/jobs/image/${native.selected_job.id}/node-discard`;
const selected=()=>structuredClone(native.selected_job) as unknown as StudioProductionTask&{attempt:number};
const payload=()=>structuredClone(native.discard);
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
let fetcher:ReturnType<typeof vi.fn>;
function server(value:unknown=payload(),status=200){fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  if(url!==endpoint||init.method!=='POST')throw new Error(`Forbidden fallback/Canvas/provider route: ${init.method} ${url}`);return json(value,status);
});vi.stubGlobal('fetch',fetcher);}
const client=()=>studioProductionClient(native.project,{sessionToken:''});
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('Blob',NodeBlob);server();});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('accepts only the original CAS discard ACK and never claims remote stop',async()=>{
  const before=vi.fn(),result=await client().discardImageNodeJob(selected(),undefined,before);
  expect(result).toEqual(native.discard);expect(Object.keys(result)).toHaveLength(8);expect(before).toHaveBeenCalledOnce();
  expect(result.job).toMatchObject({version:native.selected_job.version+1,status:'CANCELLED',cancellation_mode:'LOCAL_RESULT_DISCARD',remote_compute_may_continue:true});
  expect(result.local_result_discarded).toBe(true);expect(result.remote_stop_confirmed).toBe(false);
  expect(fetcher).toHaveBeenCalledOnce();expect(JSON.parse(String(fetcher.mock.calls[0][1].body))).toEqual({expected_version:native.selected_job.version,
    expected_request_digest:native.selected_job.request_digest,confirmed:true});
});

it.each(['version','status','mode','remote-may-continue','local-result','remote-stop','extra','candidate'] as const)(
  'rejects malformed SOFTWARE ACK %s rather than reporting confirmation',async kind=>{
    const value=payload();let reply:unknown=value;
    if(kind==='version')value.job.version=native.selected_job.version;
    if(kind==='status')value.job.status='QUEUED';
    if(kind==='mode')value.job.cancellation_mode='SOFTWARE_WRONG_MODE';
    if(kind==='remote-may-continue')value.job.remote_compute_may_continue=false;
    if(kind==='local-result')value.local_result_discarded=false;
    if(kind==='remote-stop')value.remote_stop_confirmed=true;
    if(kind==='extra')reply={...value,uri:'https://forbidden.invalid/not-fetched'};
    if(kind==='candidate')reply={...value,job:{...value.job,output_candidate:{id:'software-candidate',version:1,digest:'b'.repeat(64),kind:'image'}}};
    server(reply);await expect(client().discardImageNodeJob(selected())).rejects.toThrow();expect(fetcher).toHaveBeenCalledOnce();
  });

it('rejects ineligible SOFTWARE status/attempt/candidate/receipt/cloud selections before POST',async()=>{
  for(const kind of ['status','attempt','candidate','receipt','cloud'] as const){
    let job=selected();if(kind==='status')job={...job,status:'RUNNING'};if(kind==='attempt')job={...job,attempt:1};
    if(kind==='candidate')job={...job,output_candidate:{id:'software-candidate',version:1,digest:'b'.repeat(64),kind:'image'}};
    if(kind==='receipt')job={...job,receipt_digest:'a'.repeat(64)};
    if(kind==='cloud')job={...job,provider:{...job.provider!,local:false}};
    await expect(client().discardImageNodeJob(job)).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();
  }
});

it('invokes the helper confirmation/claim hook immediately before transport, allowing a late gate to stop POST',async()=>{
  const before=vi.fn(()=>{throw new Error('SOFTWARE_RETIRED_BEFORE_POST');});
  await expect(client().discardImageNodeJob(selected(),undefined,before)).rejects.toThrow('SOFTWARE_RETIRED_BEFORE_POST');
  expect(before).toHaveBeenCalledOnce();expect(fetcher).not.toHaveBeenCalled();
});

const source=()=>({job:selected(),key:'discard-source-A',isCurrent:()=>true});
const input=(patch:Partial<Parameters<typeof discardCanvasImageNodeJob>[0]>={}):Parameters<typeof discardCanvasImageNodeJob>[0]=>({projectId:native.project,branchId:null,client:client(),source:source(),
  observation:structuredClone(native.observation) as unknown as StudioImageNodeJobObservation,mutate:<T,>(work:()=>Promise<T>)=>work(),isCurrent:()=>true,confirmed:()=>true,claim:vi.fn(()=>true),...patch});

it('returns CONFIRMED only after one claimed dispatch and the exact valid ACK',async()=>{
  const request=input(),result=await discardCanvasImageNodeJob(request);expect(result.state).toBe('CONFIRMED');
  if(result.state==='CONFIRMED')expect(result.receipt).toEqual(native.discard);
  expect(request.claim).toHaveBeenCalledOnce();expect(fetcher).toHaveBeenCalledOnce();
});

it('blocks a previously claimed snapshot without another method send',async()=>{
  const request=input({claim:vi.fn(()=>false)});expect((await discardCanvasImageNodeJob(request)).state).toBe('BLOCKED');expect(fetcher).not.toHaveBeenCalled();
});

it.each(['permission','capsule','confirmation'] as const)('checks changed %s at deferred operation entry without claiming or sending',async kind=>{
  let current=true,confirmed=true,release!:()=>void;const request=input({isCurrent:()=>current,confirmed:()=>confirmed,mutate:async work=>{
    await new Promise<void>(resolve=>{release=resolve;});return work();
  }}),pending=discardCanvasImageNodeJob(request),rejected=expect(pending).rejects.toThrow();
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  if(kind==='permission')current=false;if(kind==='confirmation')confirmed=false;if(kind==='capsule')request.source.job.command!.canvas_image_node!.node_id='changed-node';
  release();await rejected;
  expect(request.claim).not.toHaveBeenCalled();expect(fetcher).not.toHaveBeenCalled();
});

it.each([403,409,500])('reports UNKNOWN for actual-dispatch HTTP %s, consumes the claim and never retries',async status=>{
  server({code:'SOFTWARE_DISCARD_NO_ACK',message:'No valid acknowledgement'},status);const request=input();
  expect((await discardCanvasImageNodeJob(request)).state).toBe('UNKNOWN');expect(request.claim).toHaveBeenCalledOnce();expect(fetcher).toHaveBeenCalledOnce();
});

it('reports UNKNOWN for an invalid post-dispatch ACK rather than rolling back or retrying',async()=>{
  server({...payload(),remote_stop_confirmed:true});const request=input();
  expect((await discardCanvasImageNodeJob(request)).state).toBe('UNKNOWN');expect(request.claim).toHaveBeenCalledOnce();expect(fetcher).toHaveBeenCalledOnce();
});

it.each(['omits-hook','throws-before-hook'] as const)('conservatively blocks an invoked embedded client that %s',async kind=>{
  const ack=await client().discardImageNodeJob(selected());fetcher.mockClear();
  const method=vi.fn(async()=>{if(kind==='throws-before-hook')throw new Error('Untrusted embedded failure');return ack;});
  const request=input({client:{discardImageNodeJob:method}});
  expect((await discardCanvasImageNodeJob(request)).state).toBe('UNKNOWN');
  expect(method).toHaveBeenCalledOnce();expect(request.claim).toHaveBeenCalledOnce();expect(fetcher).not.toHaveBeenCalled();
});

it('treats a host wrapper that never invokes the operation as NOT_SENT, not a forged ACK',async()=>{
  const ack=await client().discardImageNodeJob(selected());fetcher.mockClear();
  const request=input({mutate:async<T,>()=>ack as unknown as T});await expect(discardCanvasImageNodeJob(request)).rejects.toThrow();
  expect(request.claim).not.toHaveBeenCalled();expect(fetcher).not.toHaveBeenCalled();
});

it('keeps post-dispatch abort UNKNOWN even if a valid ACK arrives late',async()=>{
  let release!:(value:Response)=>void;fetcher=vi.fn(()=>new Promise<Response>(resolve=>{release=resolve;}));vi.stubGlobal('fetch',fetcher);
  const controller=new AbortController(),request=input({signal:controller.signal}),pending=discardCanvasImageNodeJob(request);
  await waitFor(()=>expect(release).toBeTypeOf('function'));controller.abort();expect((await pending).state).toBe('UNKNOWN');
  await act(async()=>release(json(native.discard)));expect(request.claim).toHaveBeenCalledOnce();expect(fetcher).toHaveBeenCalledOnce();
});

it('releases the host mutation finally on deadline even if the invoked embedded method ignores abort forever',async()=>{
  const clock=vi.spyOn(globalThis,'setTimeout');let release!:(value:StudioImageNodeJobDiscard)=>void,lateHook!:(()=>void),released=false;
  const method=vi.fn((_job:ProductionJob,_signal?:AbortSignal,beforeDispatch?:()=>void)=>{
    lateHook=beforeDispatch!;beforeDispatch?.();return new Promise<StudioImageNodeJobDiscard>(resolve=>{release=resolve;});
  });
  const request=input({client:{discardImageNodeJob:method},mutate:async work=>{try{return await work();}finally{released=true;}}});
  const pending=discardCanvasImageNodeJob(request);await waitFor(()=>expect(method).toHaveBeenCalledOnce());
  const expire=clock.mock.calls.find(([,delay])=>delay===15_000)?.[0];expect(expire).toBeTypeOf('function');(expire as()=>void)();
  expect((await pending).state).toBe('UNKNOWN');await waitFor(()=>expect(released).toBe(true));expect(()=>lateHook()).toThrow();
  await act(async()=>release(payload() as unknown as StudioImageNodeJobDiscard));
  expect(request.claim).toHaveBeenCalledOnce();expect(method).toHaveBeenCalledOnce();expect(fetcher).not.toHaveBeenCalled();
});
