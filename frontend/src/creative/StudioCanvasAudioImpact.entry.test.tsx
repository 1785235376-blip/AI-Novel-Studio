// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {createHash,webcrypto} from 'node:crypto';
import native from './fixtures/canvasAudioTrim.native.json';
const fixture={...native,project:native.canvas.project_id,providers:{items:[],automatic_runtime_start:false,health_probed:false,credentials_read:false}};
import {executionImpactSnapshot,fingerprintExecutionImpact} from '../experimental/executionImpact/executionImpact';
import {ExecutionImpactPanel} from '../experimental/executionImpact/ExecutionImpactPanel';
import {useStudioMediaExecution,type StudioMediaExecutionController,type StudioMediaExecutionProps} from './useStudioMediaExecution';
import {checkedCanvasReturnBinding} from './studioCanvasReturnBinding';
import {studioProductionClient,type ProductionJob} from './studioProductionClient';

let state:StudioMediaExecutionController,props:StudioMediaExecutionProps,fetcher:ReturnType<typeof vi.fn>,lastRequest:string;
const hash=(v:string)=>createHash('sha256').update(v).digest('hex');
const json=(value:unknown)=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
function receipt(kind:'preview'|'queued'|'executed',request:string){
 const result:any=structuredClone(fixture[kind]);result.request_id=request;result.command.request_id=request;
 result.request_digest=hash('request:'+request);if(kind==='preview')result.preview_digest=hash('preview:'+request);
 else result.id=request===fixture.command.request_id?fixture.queued.id:'job-'+request;
 return result;
}
function Harness(){state=useStudioMediaExecution(props);return state.impact?<ExecutionImpactPanel input={state.impact.input} owner={state.impact}
 current={state.impact.current()} canConfirm={props.canMutate} busy={state.locked} isCurrent={state.impact.current}
 onConfirm={proof=>void state.confirmImpact(state.impact!,proof)}/>:null;}
beforeEach(()=>{
 lastRequest=fixture.command.request_id;vi.stubGlobal('crypto',{subtle:webcrypto.subtle,randomUUID:()=>lastRequest});
 const binding=checkedCanvasReturnBinding(structuredClone(fixture.command.canvas_return));
 props={client:studioProductionClient(fixture.project,{sessionToken:''}),assets:[structuredClone(fixture.source)],canMutate:true,canReview:true,busy:false,isCurrent:()=>true,
  read:work=>work(),mutate:work=>work(),onDirtyChange:vi.fn(),onUnavailable:vi.fn(),
  canvasAudioTrimTask:{source:binding.source,returnBinding:binding,isCurrent:()=>true}};
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/providers'))return json(fixture.providers);
  if(url.endsWith('/preview'))return json(receipt('preview',body.request_id));
  if(url.endsWith('/jobs')&&init.method==='POST')return json(receipt('queued',body.command.request_id));
  if(url.endsWith('/execute'))return json(receipt('executed',lastRequest));
  if(url.includes('/jobs/audio/'))return json(receipt('queued',lastRequest));
  throw new Error('Unexpected real owner request '+(init.method||'GET')+' '+url);
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const count=(suffix:string)=>fetcher.mock.calls.filter(([url,init])=>url.endsWith(suffix)&&init.method==='POST').length;
async function draft(){
 const view=render(<Harness/>);await waitFor(()=>expect(state.providerLoading).toBe(false));
 act(()=>{state.changeParameter('in_ms','550');state.changeParameter('out_ms','850');});return view;
}
async function preview(){await act(async()=>state.inspect());expect(state.preview).toBeTruthy();act(()=>state.confirmPreview(true));}
async function confirm(kind:'CREATE'|'EXECUTE'){
 expect(state.impact?.input.boundary.kind).toBe(kind);const check=screen.getByLabelText('已核对本次输入变化与影响范围');
 await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));fireEvent.click(check);fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));
 await waitFor(()=>expect(kind==='CREATE'?state.canCreate:state.canAction('execute')).toBe(true));
}
async function queued(){const view=await draft();await preview();await confirm('CREATE');await act(async()=>state.create());expect(state.selected?.status).toBe('QUEUED');return view;}
it('enforces real create and execute even when calling controller actions directly, consuming each confirmation once',async()=>{
 await draft();await preview();const create=state.create;
 await act(async()=>create());expect(count('/jobs')).toBe(0);expect(count('/execute')).toBe(0);
 await confirm('CREATE');expect(state.impact?.input.preview.request_digest).toBe(state.preview!.request_digest);
 await act(async()=>{await Promise.all([create(),create()]);});expect(count('/jobs')).toBe(1);expect(count('/execute')).toBe(0);
 const execute=()=>state.action('execute');await act(async()=>execute());expect(count('/execute')).toBe(0);
 await confirm('EXECUTE');expect(state.impact?.input.boundary.job?.version).toBe(state.selected!.version);
 await act(async()=>{await Promise.all([execute(),execute()]);});expect(count('/execute')).toBe(1);
 await act(async()=>{await execute();await create();});expect(count('/execute')).toBe(1);expect(count('/jobs')).toBe(1);
});
it('rechecks the persisted native queued command through strict fresh preview without dispatch',async()=>{
 await draft();await act(async()=>state.openJob(native.queued as unknown as ProductionJob));expect(state.selected?.status,state.error).toBe('QUEUED');
 expect(state.impact).toBeUndefined();await act(async()=>state.inspectExecution());expect(state.error).toBe('');expect(state.impact?.input.boundary.kind).toBe('EXECUTE');
 const body=JSON.parse(String(fetcher.mock.calls.find(([u])=>u.endsWith('/preview'))![1].body));expect(body.parameters).toEqual({in_ms:550,out_ms:850});expect(body.source_snapshots[0].reference_only).toBeUndefined();
 await confirm('EXECUTE');expect(count('/execute')).toBe(0);await act(async()=>state.action('execute'));expect(count('/execute')).toBe(1);expect(count('/jobs')).toBe(0);
});
it.each(['parameters','scope'])('retires audio create after observed %s A/B/A and accepts a fresh explicit request',async mode=>{
 const view=await draft();await preview();await confirm('CREATE');const gate=state.impact!,create=state.create;
 if(mode==='parameters'){act(()=>state.changeParameter('out_ms','900'));act(()=>state.changeParameter('out_ms','850'));}
 else {const b=props.canvasAudioTrimTask!.returnBinding!,inc=b.incarnation;b.incarnation='file:00000000-0000-0000-0000-000000000001';await act(async()=>create());b.incarnation=inc;}
 await act(async()=>create());expect(count('/jobs')).toBe(0);expect(gate.current()).toBe(false);
 lastRequest='audio-fresh-'+mode;view.rerender(<Harness/>);await preview();await confirm('CREATE');await act(async()=>state.create());expect(count('/jobs')).toBe(1);
});
