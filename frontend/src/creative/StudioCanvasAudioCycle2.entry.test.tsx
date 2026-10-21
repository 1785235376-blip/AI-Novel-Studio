import {StudioMediaExecutionPanel} from './StudioMediaExecutionPanel';
import {compileCanvasAudioDraftTimeline,canvasAudioDraftFromCommand} from './studioCanvasAudioDraft';
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

const effectRef=():CanvasAudioWorkflowTemplateRef=>({contract:'studio-canvas-audio-template/1',graph_id:'effects-template',graph_version:3,definition_digest:'a'.repeat(64),execution_digest:'b'.repeat(64),node_id:'trim',parameters:{in_ms:100,out_ms:900,gain_db:-6.5,fade_in_ms:100,fade_out_ms:200}});
it('copies real template effects into the original command, keeps local overrides and re-previews all fields before execute',async()=>{
 const ref=effectRef();await mount();act(()=>state.applyAudioTemplate(ref));expect(state.draft.parameters.gain_db).toBe('-6.5');expect(state.draft.parameters.fade_in_ms).toBe('100');expect(state.draft.parameters.fade_out_ms).toBe('200');
 act(()=>{state.changeParameter('in_ms','550');state.changeParameter('out_ms','850');state.changeParameter('gain_db','-3.5');});expect(ref.parameters.gain_db).toBe(-6.5);
 await inspect();await act(async()=>state.create());expect(calls('/jobs')).toHaveLength(0);await confirm('CREATE');await act(async()=>state.create());
 expect(saved!.parameters).toEqual({in_ms:550,out_ms:850,gain_db:-3.5,fade_in_ms:100,fade_out_ms:200});expect(saved!.template_ref).toEqual(ref);
 await act(async()=>state.inspectExecution());expect(state.error).toBe('');const command=JSON.parse(String(calls('/preview').at(-1)![1].body));expect(command.parameters).toEqual(saved!.parameters);expect(command.template_ref).toEqual(ref);
 await confirm('EXECUTE');await act(async()=>Promise.all([state.action('execute'),state.action('execute')]));expect(calls('/execute')).toHaveLength(1);expect(ref.parameters.gain_db).toBe(-6.5);
});
it('keeps existing task effects when an old range-only template does not specify them',async()=>{
 await mount();act(()=>{state.changeParameter('gain_db','-4.5');state.changeParameter('fade_in_ms','10');state.changeParameter('fade_out_ms','20');});const ref=effectRef();delete ref.parameters.gain_db;delete ref.parameters.fade_in_ms;delete ref.parameters.fade_out_ms;
 act(()=>state.applyAudioTemplate(ref));expect(state.draft.parameters.gain_db).toBe('-4.5');expect(state.draft.parameters.fade_in_ms).toBe('10');expect(state.draft.parameters.fade_out_ms).toBe('20');expect(state.draft.template_ref!.parameters).toEqual({in_ms:100,out_ms:900});
});
it('retires a confirmed template effect request across gain ABA and needs a new explicit confirmation',async()=>{
 await mount();act(()=>state.applyAudioTemplate(effectRef()));await inspect();await confirm('CREATE');const create=state.create,gate=state.impact!;
 act(()=>state.changeParameter('gain_db','-5'));act(()=>state.changeParameter('gain_db','-6.5'));await act(async()=>create());expect(gate.current()).toBe(false);expect(calls('/jobs')).toHaveLength(0);
 await inspect();await confirm('CREATE');await act(async()=>state.create());expect(calls('/jobs')).toHaveLength(1);
});
it('strict SDK rejects a template effect echo detached from the reviewed reference',async()=>{
 await mount();act(()=>state.applyAudioTemplate(effectRef()));const previous=fetcher.getMockImplementation()!;
 fetcher.mockImplementation(async(url:string,init:RequestInit={})=>{if(url.endsWith('/preview')){const row=receipt('preview',JSON.parse(String(init.body)));row.command.template_ref.parameters.gain_db=-4;return json(row);}return previous(url,init);});
 await act(async()=>state.inspect());expect(state.preview).toBeUndefined();expect(state.canCreate).toBe(false);expect(calls('/jobs')).toHaveLength(0);
});

function draftTransport(){
 let row:any;let tampered=false;let blockedGet:Promise<Response>|undefined;const prior=fetcher.getMockImplementation()!;
 fetcher.mockImplementation(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/timelines')&&init.method==='GET')return json({items:row?[clone(row)]:[]});
  if((url.endsWith('/timelines')&&init.method==='POST')||(url.endsWith('/timelines/audio-input')&&init.method==='PUT')){
   if(body.expected_version!==(row?.version??0))return new Response(JSON.stringify({detail:'CAS conflict'}),{status:409,headers:{'Content-Type':'application/json'}});
   const version=(row?.version??0)+1,timeline=clone(body.timeline),digest=hash(JSON.stringify(timeline));
   row={contract:'studio-production-timeline/1',novel_id:native.canvas.project_id,branch_id:null,id:'audio-input',version,title:body.title,timeline,timeline_digest:digest,created_at:'2026-10-21T00:00:00Z',updated_at:'2026-10-21T00:00:00Z',
    canvas_audio_draft:{...clone(body.canvas_audio_draft),timeline_snapshot:{id:'audio-input',version,digest}},canvas_audio_draft_digest:hash(JSON.stringify(body.canvas_audio_draft))};
   const value=clone(row);if(tampered)value.canvas_audio_draft.parameters.gain_db=-2;return json(value);
  }
  if(url.endsWith('/timelines/audio-input')&&init.method==='GET')return blockedGet??json(row);
  return prior(url,init);
 });
 return {row:()=>row,tamper:()=>{tampered=true;},block:(p:Promise<Response>)=>{blockedGet=p;}};
}
async function savedInput(){const transport=draftTransport(),view=await mount();act(()=>state.applyAudioTemplate(effectRef()));act(()=>{state.changeParameter('in_ms','550');state.changeParameter('out_ms','850');state.changeParameter('gain_db','-3.5');});await act(async()=>state.audioDraft.save());expect(state.error).toBe('');return {...transport,view};}
it('saves applied audio inputs without proof, remounts, restores explicitly and requires fresh original CREATE/EXECUTE gates',async()=>{
 const api=await savedInput();expect(state.audioDraft.saved?.version).toBe(1);expect(calls('/jobs')).toHaveLength(0);expect(calls('/preview')).toHaveLength(0);expect(calls('/execute')).toHaveLength(0);
 expect(api.row().canvas_audio_draft.parameters).toEqual({in_ms:550,out_ms:850,gain_db:-3.5,fade_in_ms:100,fade_out_ms:200});expect(api.row().canvas_audio_draft.template_ref).toEqual(effectRef());
 expect(Object.keys(api.row().canvas_audio_draft).some(k=>k.includes('proof')||k.includes('preview'))).toBe(false);
 api.view.unmount();await mount();let rows:any[]=[];await act(async()=>{rows=await state.audioDraft.onList();});expect(rows).toHaveLength(1);expect(state.draft.template_ref).toBeUndefined();
 await act(async()=>state.audioDraft.onResume(rows[0]));expect(state.error).toBe('');expect(state.draft.template_ref).toEqual(effectRef());expect(state.draft.parameters.gain_db).toBe('-3.5');expect(state.preview).toBeUndefined();expect(state.impact).toBeUndefined();expect(state.canCreate).toBe(false);expect(calls('/jobs')).toHaveLength(0);
 await inspect();await act(async()=>state.create());expect(calls('/jobs')).toHaveLength(0);await confirm('CREATE');await act(async()=>state.create());expect(calls('/jobs')).toHaveLength(1);await act(async()=>state.inspectExecution());await confirm('EXECUTE');await act(async()=>state.action('execute'));expect(calls('/execute')).toHaveLength(1);
});
it('saves one CAS revision for duplicate clicks and keeps session input after a later CAS conflict',async()=>{
 const api=await savedInput();act(()=>state.changeParameter('gain_db','-5'));await act(async()=>Promise.all([state.audioDraft.save(),state.audioDraft.save()]));expect(api.row().version).toBe(2);expect(state.audioDraft.saved?.version).toBe(2);
 api.row().version++;act(()=>state.changeParameter('gain_db','-4'));await act(async()=>state.audioDraft.save());expect(state.error).not.toBe('');expect(state.draft.parameters.gain_db).toBe('-4');expect(state.audioDraft.saved?.version).toBe(2);expect(calls('/jobs')).toHaveLength(0);
});
it.each(['pin','client ABA','input ABA'] as const)('ignores a late saved-input read after %s and preserves session edits',async kind=>{
 const api=await savedInput();let rows:any[]=[];await act(async()=>{rows=await state.audioDraft.onList();});let resolve!:(v:Response)=>void;api.block(new Promise(r=>{resolve=r;}));
 let reading!:Promise<void>;act(()=>{reading=state.audioDraft.onResume(rows[0]);});
 if(kind==='pin')sourceCurrent=false;
 if(kind==='client ABA'){const original=props.client;props={...props,client:studioProductionClient('another-project',{sessionToken:''})};api.view.rerender(<Harness/>);props={...props,client:original};api.view.rerender(<Harness/>);}
 if(kind==='input ABA'){const original=props.canvasAudioTrimTask!;props={...props,canvasAudioTrimTask:{...original,returnBinding:{...original.returnBinding!,card_id:'other'}}};api.view.rerender(<Harness/>);props={...props,canvasAudioTrimTask:original};api.view.rerender(<Harness/>);}
 await act(async()=>{resolve(json(api.row()));await reading;});expect(state.notice).not.toContain('已恢复输入草稿');expect(calls('/jobs')).toHaveLength(0);expect(calls('/execute')).toHaveLength(0);
});
it('strict SDK refuses a changed saved-input echo and refuses proof-bearing draft input before sending',async()=>{
 const api=draftTransport();api.tamper();await mount();act(()=>state.applyAudioTemplate(effectRef()));await act(async()=>state.audioDraft.save());expect(state.audioDraft.saved).toBeUndefined();expect(state.error).not.toBe('');
 const input=canvasAudioDraftFromCommand({...clone(native.command),request_id:'save-only',parameters:{in_ms:550,out_ms:850}} as unknown as MediaCommand);fetcher.mockClear();
 await expect(props.client.timelineSave(undefined,{title:'Input only',timeline:compileCanvasAudioDraftTimeline(input),expected_version:0,canvas_audio_draft:{...input,proof:{confirmed:true}}} as never)).rejects.toBeInstanceOf(Error);expect(fetcher).not.toHaveBeenCalled();
});
it('actual media panel lists and explicitly restores saved audio input without its own pending-state retiring the selection',async()=>{
 const api=await savedInput();api.view.unmount();render(<StudioMediaExecutionPanel {...props}/>);
 await waitFor(()=>expect((screen.getByRole('button',{name:'读取已保存音频输入草稿'}) as HTMLButtonElement).disabled).toBe(false));fireEvent.click(screen.getByRole('button',{name:'读取已保存音频输入草稿'}));
 const select=await screen.findByLabelText('已保存的音频输入草稿');fireEvent.change(select,{target:{value:'audio-input'}});
 const check=await screen.findByLabelText('我已核对所选版本与来源，同意用已保存草稿替换当前会话输入');fireEvent.click(check);fireEvent.click(screen.getByRole('button',{name:'明确仅恢复音频输入草稿'}));
 await waitFor(()=>expect((screen.getByLabelText('本任务增益（-60–12 dB，可选）') as HTMLInputElement).value).toBe('-3.5'));expect(calls('/jobs')).toHaveLength(0);expect(calls('/execute')).toHaveLength(0);
});

it('compares the full captured metadata before restoring even when the visible summary and echoed digest are unchanged',async()=>{
 const api=await savedInput();let rows:any[]=[];await act(async()=>{rows=await state.audioDraft.onList();});api.row().canvas_audio_draft.template_ref.execution_digest='c'.repeat(64);
 await act(async()=>{await expect(state.audioDraft.onResume(rows[0])).rejects.toBeInstanceOf(Error);});expect(state.notice).not.toContain('已恢复输入草稿');expect(state.canCreate).toBe(false);expect(calls('/jobs')).toHaveLength(0);
});

it('latches an observed client-method ABA and requires a new saved-input list before any restore read',async()=>{
 await savedInput();let rows:any[]=[];await act(async()=>{rows=await state.audioDraft.onList();});const resume=state.audioDraft.onResume,original=props.client.timelineGet,changed=vi.fn();props.client.timelineGet=changed;
 await act(async()=>resume(rows[0]));expect(changed).not.toHaveBeenCalled();props.client.timelineGet=original;const count=()=>fetcher.mock.calls.filter(([u,i])=>u.endsWith('/timelines/audio-input')&&i.method==='GET').length;
 await act(async()=>resume(rows[0]));expect(count()).toBe(0);await act(async()=>{rows=await state.audioDraft.onList();});await act(async()=>state.audioDraft.onResume(rows[0]));expect(count()).toBe(1);
});
it('an observed false original source getter cannot revive a retained restore after returning true',async()=>{
 await savedInput();let rows:any[]=[];await act(async()=>{rows=await state.audioDraft.onList();});const resume=state.audioDraft.onResume;sourceCurrent=false;expect(state.audioDraft.isCurrent()).toBe(false);sourceCurrent=true;
 await act(async()=>resume(rows[0]));expect(fetcher.mock.calls.filter(([u,i])=>u.endsWith('/timelines/audio-input')&&i.method==='GET')).toHaveLength(0);expect(calls('/jobs')).toHaveLength(0);
});

it('an uncertain input Save is not retried; explicit original read resolves it without granting any execution proof',async()=>{
 const api=draftTransport(),prior=fetcher.getMockImplementation()!;let fail=true;
 fetcher.mockImplementation(async(url:string,init:RequestInit={})=>{const response=await prior(url,init);if(fail&&url.endsWith('/timelines')&&init.method==='POST'){fail=false;return new Response(JSON.stringify({detail:'synthetic response lost'}),{status:503,headers:{'Content-Type':'application/json'}});}return response;});
 await mount();act(()=>state.applyAudioTemplate(effectRef()));await act(async()=>state.audioDraft.save());expect(api.row()).toBeTruthy();expect(state.uncertain).toBe(true);expect(state.audioDraft.saveUnknown).toBe(true);
 await act(async()=>state.audioDraft.save());expect(calls('/timelines')).toHaveLength(1);let rows:any[]=[];await act(async()=>{rows=await state.audioDraft.onList();});await act(async()=>state.audioDraft.onResume(rows[0]));expect(state.uncertain).toBe(false);expect(state.preview).toBeUndefined();expect(state.canCreate).toBe(false);expect(calls('/jobs')).toHaveLength(0);expect(calls('/execute')).toHaveLength(0);
});
