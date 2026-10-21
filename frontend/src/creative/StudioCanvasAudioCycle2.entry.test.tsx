// @vitest-environment jsdom
// Original controller + strict SDK with synthetic recorded responses; no inference.
import { act,cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { afterEach,beforeEach,expect,it,vi } from 'vitest';
import { createHash,webcrypto } from 'node:crypto';
import native from './fixtures/canvasAudioTrim.native.json';
import { ExecutionImpactPanel } from '../experimental/executionImpact/ExecutionImpactPanel';
import { useStudioMediaExecution,type StudioMediaExecutionController,type StudioMediaExecutionProps } from './useStudioMediaExecution';
import { studioProductionClient,type ProductionJob,type MediaCommand } from './studioProductionClient';
import { deriveFailedCanvasAudioCommand } from './taskRecovery';
import { checkedCanvasReturnBinding } from './studioCanvasReturnBinding';
import type { CanvasAudioWorkflowTemplateRef } from './studioCanvasAudioProvenance';
let state:StudioMediaExecutionController,props:StudioMediaExecutionProps,fetcher:ReturnType<typeof vi.fn>,saved:MediaCommand|undefined,origin:ProductionJob;
let sourceCurrent=true,request='fresh-derived',tamper=false;
const clone=<T,>(v:T):T=>structuredClone(v),hash=(v:string)=>createHash('sha256').update(v).digest('hex');
const json=(v:unknown)=>new Response(JSON.stringify(v),{headers:{'Content-Type':'application/json'}});
function receipt(kind:'preview'|'queued'|'executed',command:MediaCommand){
 const v:any=clone(native[kind]);v.request_id=command.request_id;v.command=clone(command);v.command.source_snapshots=v.command.source_snapshots.map((s:any)=>({...s,reference_only:true}));
 v.execution_recipe.parameters=clone(command.parameters);v.request_digest=hash(command.request_id+JSON.stringify(command,(_k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v));
 if(kind==='preview')v.preview_digest=hash('preview'+v.request_digest);else v.id='job-'+command.request_id;
 if(tamper&&v.command.template_ref)v.command.template_ref.graph_version++;
 return v;
}
function Harness(){state=useStudioMediaExecution(props);return state.impact?<ExecutionImpactPanel input={state.impact.input} owner={state.impact} current={state.impact.current()} canConfirm={props.canMutate} busy={state.locked} isCurrent={state.impact.current} onConfirm={proof=>void state.confirmImpact(state.impact!,proof)}/>:null;}
beforeEach(()=>{
 sourceCurrent=true;request='fresh-derived';tamper=false;saved=undefined;
 vi.stubGlobal('crypto',{subtle:webcrypto.subtle,randomUUID:()=>request});
 origin={...clone(native.queued),status:'FAILED',version:3,output_candidate:null,approved_asset_version:null,receipt_digest:null,error_code:'LOCAL_FAILED'} as unknown as ProductionJob;
 const binding=checkedCanvasReturnBinding(clone(native.command.canvas_return));
 props={client:studioProductionClient(native.canvas.project_id,{sessionToken:''}),assets:[clone(native.source)],canMutate:true,canReview:true,busy:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),onDirtyChange:vi.fn(),onUnavailable:vi.fn(),canvasAudioTrimTask:{source:binding.source,returnBinding:binding,isCurrent:()=>sourceCurrent},audioWorkflowTemplates:{owner:{projectId:binding.project_id,incarnation:binding.incarnation,actorId:'actor',actorWorkspaceId:'',mode:'local',workspaceId:'',storylineId:'',branchId:''},list:async()=>[],read:vi.fn()}};
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/providers'))return json({items:[],automatic_runtime_start:false,health_probed:false,credentials_read:false});
  if(url.endsWith('/preview'))return json(receipt('preview',body));
  if(url.endsWith('/jobs')&&init.method==='POST'){saved=clone(body.command);return json(receipt('queued',body.command));}
  if(url.endsWith('/execute'))return json(receipt('executed',saved!));
  if(url.includes('/jobs/audio/'))return json(saved?receipt('queued',saved):origin);
  throw new Error('Unexpected original-owner request '+url);
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const calls=(suffix:string)=>fetcher.mock.calls.filter(([u,i])=>u.endsWith(suffix)&&i.method==='POST');
async function mount(){const view=render(<Harness/>);await waitFor(()=>expect(state.providerLoading).toBe(false));return view;}
async function confirm(kind:'CREATE'|'EXECUTE'){
 expect(state.impact?.input.boundary.kind).toBe(kind);const check=screen.getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));fireEvent.click(check);fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));await waitFor(()=>expect(kind==='CREATE'?state.canCreate:state.canAction('execute')).toBe(true));
}
async function inspect(){await act(async()=>state.inspect());expect(state.error).toBe('');expect(state.preview).toBeTruthy();act(()=>state.confirmPreview(true));}
it('derives FAILED into a new identity and requires both original proof gates without replaying its parent',async()=>{
 await mount();await act(async()=>state.openJob(origin));expect(state.selected?.status,state.error).toBe('FAILED');
 const command=deriveFailedCanvasAudioCommand(state.selected!,props.canvasAudioTrimTask!,request);
 act(()=>state.prepareFailedAudio(command));expect(state.selected).toBeUndefined();expect(state.draft.derived_from?.job_id).toBe(origin.id);expect(calls('/jobs')).toHaveLength(0);expect(calls('/execute')).toHaveLength(0);
 act(()=>state.changeParameter('gain_db','-6'));await inspect();await act(async()=>state.create());expect(calls('/jobs')).toHaveLength(0);
 await confirm('CREATE');await act(async()=>Promise.all([state.create(),state.create()]));expect(calls('/jobs')).toHaveLength(1);expect(state.selected?.status,state.error).toBe('QUEUED');expect(saved!.request_id).not.toBe(origin.request_id);expect(saved!.derived_from).toEqual(command.derived_from);expect(saved!.parameters.gain_db).toBe(-6);
 await act(async()=>state.action('execute'));expect(calls('/execute')).toHaveLength(0);await confirm('EXECUTE');await act(async()=>Promise.all([state.action('execute'),state.action('execute')]));expect(calls('/execute')).toHaveLength(1);
 expect(origin.status).toBe('FAILED');expect(origin.command!.parameters.gain_db).toBeUndefined();
});
it('copies a template range into this draft, retains template pin during local override and exact queued re-preview after reopen',async()=>{
 const ref:CanvasAudioWorkflowTemplateRef={contract:'studio-canvas-audio-template/1',graph_id:'template',graph_version:2,definition_digest:'a'.repeat(64),execution_digest:'b'.repeat(64),node_id:'trim',parameters:{in_ms:100,out_ms:900}};
 const view=await mount();act(()=>state.applyAudioTemplate(ref));act(()=>{state.changeParameter('in_ms','550');state.changeParameter('out_ms','850');state.changeParameter('gain_db','-3');});
 expect(ref.parameters).toEqual({in_ms:100,out_ms:900});await inspect();await confirm('CREATE');await act(async()=>state.create());expect(state.selected?.status,state.error).toBe('QUEUED');expect(saved!.template_ref).toEqual(ref);expect(saved!.parameters).toEqual({in_ms:550,out_ms:850,gain_db:-3});
 const queued=clone(state.selected!);view.unmount();await mount();await act(async()=>state.openJob(queued));expect(calls('/jobs')).toHaveLength(1);expect(calls('/execute')).toHaveLength(0);
 await act(async()=>state.inspectExecution());expect(state.error).toBe('');expect(state.impact?.input.boundary.kind).toBe('EXECUTE');expect(JSON.parse(String(calls('/preview').at(-1)![1].body)).template_ref).toEqual(ref);
 await confirm('EXECUTE');await act(async()=>state.action('execute'));expect(calls('/execute')).toHaveLength(1);
});
it('rejects a modified template echo from the real SDK instead of issuing a usable preview',async()=>{
 await mount();act(()=>state.applyAudioTemplate({contract:'studio-canvas-audio-template/1',graph_id:'template',graph_version:1,definition_digest:'a'.repeat(64),execution_digest:'b'.repeat(64),node_id:'trim',parameters:{in_ms:550,out_ms:850}}));tamper=true;
 await act(async()=>state.inspect());expect(state.preview).toBeUndefined();expect(state.canCreate).toBe(false);expect(calls('/jobs')).toHaveLength(0);
});
it('UNKNOWN has no derived recovery and old callbacks cannot turn stale origin into a new request',async()=>{
 await mount();origin.status='UNKNOWN';await act(async()=>state.openJob(origin));const stale=state.prepareFailedAudio;
 expect(()=>deriveFailedCanvasAudioCommand(state.selected!,props.canvasAudioTrimTask!,request)).toThrow();expect(calls('/jobs')).toHaveLength(0);
 origin.status='FAILED';await act(async()=>state.openJob(origin));const command=deriveFailedCanvasAudioCommand(state.selected!,props.canvasAudioTrimTask!,request);sourceCurrent=false;
 act(()=>stale(command));expect(state.selected?.id).toBe(origin.id);expect(calls('/jobs')).toHaveLength(0);expect(calls('/execute')).toHaveLength(0);
});

it('does not confuse the draft shape-check placeholder with a failed parent request identity',async()=>{
 origin.request_id='shape_check';origin.command!.request_id='shape_check';await mount();await act(async()=>state.openJob(origin));
 const command=deriveFailedCanvasAudioCommand(state.selected!,props.canvasAudioTrimTask!,request);act(()=>state.prepareFailedAudio(command));expect(state.inputError).toBe('');expect(state.canInspect).toBe(true);expect(calls('/jobs')).toHaveLength(0);
});
