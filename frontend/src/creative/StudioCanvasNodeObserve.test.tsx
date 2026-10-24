// @vitest-environment jsdom
/** Real File CANCELLED metadata is replayed through original clients. RUNNING,
 * UNKNOWN and adversarial replies below are declared software projections only.
 * No execution, media bytes, review, approval or ingestion occurs. */
import {act,cleanup,render,waitFor} from '@testing-library/react';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_observe.json';
import {prepareCanvasImageNodeResume,type CanvasImageNodeResumeInput} from './canvasImageNodeResume';
import {studioClient} from './studioClient';
import {studioProductionClient,type ProductionJob} from './studioProductionClient';
import {canvasImageNodeInCommand} from './canvasImageNode';
import type {StudioProductionTask} from '../taskcenter/studioProductionTask';
import {useStudioMediaExecution,type StudioMediaExecutionController,type StudioMediaExecutionProps} from './useStudioMediaExecution';

const base=`/api/projects/${native.project}/studio`;
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const original=()=>structuredClone(native.job) as unknown as StudioProductionTask;
let fetcher:ReturnType<typeof vi.fn>;
type Override=(url:string,init:RequestInit)=>Response|Promise<Response>|undefined;
function server(override?:Override){
  fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
    const changed=override?.(url,init);if(changed!==undefined)return await changed;
    if(url===base)return json({...native.overview,capabilities:{...native.overview.capabilities,can_mutate:false,can_review:false}});
    if(url.endsWith('/jobs/image/resolve-create'))return json(native.resolved_job);
    if(url.endsWith(`/canvas-views/${native.canvas.id}/history`))return json(native.history);
    if(url.endsWith(`/canvas-views/${native.canvas.id}`))return json(native.canvas);
    if(url.endsWith(`/jobs/image/${native.job.id}`))return json(native.job);
    throw new Error(`Forbidden or unrelated request in read-only metadata fixture: ${init.method} ${url}`);
  });vi.stubGlobal('fetch',fetcher);
}
const input=(patch:Partial<CanvasImageNodeResumeInput>={}):CanvasImageNodeResumeInput=>({selected:original(),projectId:native.project,branchId:null,
  readOnly:true,client:studioClient(native.project,{sessionToken:''}),production:studioProductionClient(native.project,{sessionToken:''}),
  isCurrent:()=>true,read:work=>work(),...patch});
function onlyMetadata(){
  for(const [url,init] of fetcher.mock.calls){
    expect(url).not.toMatch(/\/(?:providers|preview|execute|review|cancel|reconcile|refresh|content|candidate|ingest)(?:\?|$)/);
    if(init.method==='POST')expect(url).toBe(`${base}/production/jobs/image/resolve-create`);
  }
}
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);localStorage.clear();server();});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

it('prepares real File CANCELLED metadata under READ with can_mutate=false and grants no review or execution capability',async()=>{
  const writes=vi.spyOn(Storage.prototype,'setItem'),result=await prepareCanvasImageNodeResume(input());
  expect(native.evidence_type).toBe('REAL_ORIGINAL_FILE_API_CANCELLED_METADATA_ONLY');
  expect(result.readOnly).toBe(true);expect(result.canReview).toBe(false);
  expect(result.job).toMatchObject({id:native.job.id,status:'CANCELLED',version:native.job.version,attempt:0,output_candidate:null});
  expect(result.binding).toEqual(native.command.canvas_image_node);expect(result.canvas).toEqual(native.canvas);
  expect(fetcher.mock.calls.map(([url])=>url)).toEqual([base,`${base}/production/jobs/image/resolve-create`,
    `${base}/canvas-views/${native.canvas.id}`,`${base}/canvas-views/${native.canvas.id}/history`,`${base}/production/jobs/image/${native.job.id}`]);
  expect(writes).not.toHaveBeenCalled();onlyMetadata();
});

it('does not reinterpret cancelled metadata as the default queued execution-capable mode',async()=>{
  await expect(prepareCanvasImageNodeResume(input({readOnly:undefined}))).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});

it.each(['RUNNING','UNKNOWN'] as const)('admits software-projected %s only as explicit immutable read-only mode',async status=>{
  const selected={...original(),status};
  server(url=>url.endsWith('/resolve-create')||url.endsWith(`/jobs/image/${native.job.id}`)?json({...native.job,status}):undefined);
  const result=await prepareCanvasImageNodeResume(input({selected}));
  expect(result.readOnly).toBe(true);expect(result.canReview).toBe(false);expect(result.job.status).toBe(status);onlyMetadata();
});

it('rejects explicit read-only QUEUED rather than silently changing the selected mode',async()=>{
  await expect(prepareCanvasImageNodeResume(input({selected:{...original(),status:'QUEUED'}}))).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});

it.each([401,403])('requires original production READ proof despite Canvas metadata availability (%s)',async status=>{
  server(url=>url.endsWith('/resolve-create')?json({code:'ORIGINAL_READ_DENIED',message:'read denied'},status):undefined);
  await expect(prepareCanvasImageNodeResume(input())).rejects.toMatchObject({status});
  expect(fetcher.mock.calls).toHaveLength(2);onlyMetadata();
});

it('rejects a stale read-only selected receipt without silently upgrading its version',async()=>{
  server(url=>url.endsWith('/resolve-create')?json({...native.job,version:native.job.version+1}):undefined);
  await expect(prepareCanvasImageNodeResume(input())).rejects.toThrow();onlyMetadata();
});

let state:StudioMediaExecutionController,props:StudioMediaExecutionProps;
function Hook(){state=useStudioMediaExecution(props);return null;}
function observeProps():StudioMediaExecutionProps{
  const job=original(),binding=canvasImageNodeInCommand(job.command)!;
  return{client:studioProductionClient(native.project,{sessionToken:''}),assets:[],externalJob:job as ProductionJob,
    resumeOnly:true,resumeReadOnly:true,canvasNodeTask:{binding,initialPrompt:native.node.prompt,isCurrent:()=>true},
    canMutate:false,canReview:false,busy:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),onDirtyChange:vi.fn(),onUnavailable:vi.fn()};
}
async function hook(){props=observeProps();const view=render(<Hook/>);await waitFor(()=>expect(state.selected?.id,state.error).toBe(native.job.id));return view;}
async function forbiddenCallbacks(){
  act(()=>{state.changeField('prompt','changed');state.changeField('allowCloud',true);state.changeField('providerKey','other');
    state.changeRoute('cloud');state.changeParameter('steps','99');state.clearInputs();state.clearSources();state.confirmPreview(true);state.confirmReview(true);});
  await act(async()=>{await state.loadProviders();await state.inspect();await state.inspectExecution();await state.create();await state.listJobs();
    await state.openJob({...original(),id:'other-job'} as ProductionJob);await state.loadCandidate();
    for(const kind of ['execute','refresh','reconcile','cancel','review'] as const)await state.action(kind);
  });
}

it('does not autoload config and hard-blocks every retained non-GET callback even when canMutate is true',async()=>{
  props={...observeProps(),canMutate:true,canReview:true};render(<Hook/>);
  await waitFor(()=>expect(state.selected?.status).toBe('CANCELLED'));
  expect(fetcher).not.toHaveBeenCalled();const draft=structuredClone(state.draft);
  await forbiddenCallbacks();expect(fetcher).not.toHaveBeenCalled();expect(state.draft).toEqual(draft);
  expect(state.resumeReadOnly).toBe(true);expect(state.canRead).toBe(true);expect(state.canEdit).toBe(false);expect(state.canCreate).toBe(false);
  for(const action of ['execute','refresh','reconcile','cancel','review'] as const)expect(state.canAction(action)).toBe(false);
});

it('allows only explicit same-original Job GET and keeps read-only authority after a software QUEUED reply',async()=>{
  await hook();server(url=>url.endsWith(`/jobs/image/${native.job.id}`)?json({...native.job,version:native.job.version+1,status:'QUEUED'}):undefined);
  await act(async()=>state.openJob(original() as ProductionJob));
  expect(state.selected?.id).toBe(native.job.id);expect(fetcher.mock.calls).toHaveLength(1);
  await forbiddenCallbacks();expect(fetcher.mock.calls).toHaveLength(1);expect(state.canAction('execute')).toBe(false);onlyMetadata();
});

it.each(['no-resume','queued','missing-binding'] as const)('fails closed for invalid initial read-only combination %s',async kind=>{
  props=observeProps();if(kind==='no-resume')props={...props,resumeOnly:false};
  if(kind==='queued')props={...props,externalJob:{...props.externalJob!,status:'QUEUED'}};
  if(kind==='missing-binding')props={...props,canvasNodeTask:undefined};render(<Hook/>);
  await act(async()=>{await state.openJob(original() as ProductionJob);await state.loadProviders();await state.inspectExecution();await state.action('cancel');});
  expect(fetcher).not.toHaveBeenCalled();expect(state.selected).toBeUndefined();expect(state.canAction('execute')).toBe(false);
});

it.each(['read-mode','resume-mode','client','project','capsule'] as const)('retires the same mounted observer after %s A/B/A',async kind=>{
  const view=await hook(),source=props,read=state.openJob,receipt=state.downloadReceipt;
  if(kind==='read-mode')props={...props,resumeReadOnly:false};
  if(kind==='resume-mode')props={...props,resumeOnly:false};
  if(kind==='client')props={...props,client:studioProductionClient(native.project,{sessionToken:''})};
  if(kind==='project')props={...props,externalJob:{...props.externalJob!,novel_id:'other-project'}};
  if(kind==='capsule')props={...props,canvasNodeTask:{...props.canvasNodeTask!,binding:{...props.canvasNodeTask!.binding,node_id:'other-node'}}};
  view.rerender(<Hook/>);props=source;view.rerender(<Hook/>);
  await act(async()=>{await read(original() as ProductionJob);receipt();});
  expect(fetcher).not.toHaveBeenCalled();expect(state.canAction('cancel')).toBe(false);
});

it.each(['version','owner','project','command'] as const)('does not adopt a same-URL response with changed %s',async kind=>{
  await hook();const changed=structuredClone(native.job);
  if(kind==='version')changed.version=native.job.version-1;
  if(kind==='owner')changed.owner='video';
  if(kind==='project')changed.novel_id='other-project';
  if(kind==='command')changed.command.canvas_image_node.node_id='other-node';
  server(url=>url.endsWith(`/jobs/image/${native.job.id}`)?json(changed):undefined);
  await act(async()=>state.openJob(original() as ProductionJob));
  expect(state.selected?.version).toBe(native.job.version);expect(state.selected?.novel_id).toBe(native.project);
  expect(state.error).not.toBe('');expect(fetcher.mock.calls).toHaveLength(1);onlyMetadata();
});

it.each(['status','error','receipt'] as const)('rejects software-projected same-version %s metadata changes',async kind=>{
  props={...observeProps(),externalJob:{...original(),status:'RUNNING'} as ProductionJob};render(<Hook/>);
  await waitFor(()=>expect(state.selected?.status).toBe('RUNNING'));
  const changed={...native.job,status:kind==='status'?'UNKNOWN':'RUNNING',error_code:kind==='error'?'SOFTWARE_SAME_VERSION_CHANGE':null,
    receipt_digest:kind==='receipt'?'a'.repeat(64):null};
  server(url=>url.endsWith(`/jobs/image/${native.job.id}`)?json(changed):undefined);
  await act(async()=>state.openJob({...original(),status:'RUNNING'} as ProductionJob));
  expect(state.selected?.status).toBe('RUNNING');expect(state.selected?.error_code).toBeNull();expect(state.selected?.receipt_digest).toBeNull();
  expect(state.error).not.toBe('');onlyMetadata();
});

it('keeps the adopted read-only public record separate from later parent prop mutation',async()=>{
  await hook();props.externalJob!.command!.prompt='mutated parent input';
  expect(state.selected?.command?.prompt).toBe(native.node.prompt);
  await act(async()=>state.openJob(original() as ProductionJob));expect(fetcher).not.toHaveBeenCalled();
});

it('blocks a deferred exact GET at actual send after read-mode A/B/A',async()=>{
  const view=await hook(),source=props;let release!:()=>void;
  props={...props,read:async work=>{await new Promise<void>(resolve=>{release=resolve;});return work();}};view.rerender(<Hook/>);
  let pending!:Promise<void>;act(()=>{pending=state.openJob(original() as ProductionJob);});
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  props={...source,resumeReadOnly:false};view.rerender(<Hook/>);props=source;view.rerender(<Hook/>);
  await act(async()=>{release();await pending;});expect(fetcher).not.toHaveBeenCalled();
});

it('discards a late exact response on unmount and never starts another read or action',async()=>{
  const view=await hook();let release!:(value:Response)=>void;
  server(url=>url.endsWith(`/jobs/image/${native.job.id}`)?new Promise<Response>(resolve=>{release=resolve;}):undefined);
  let pending!:Promise<void>;act(()=>{pending=state.openJob(original() as ProductionJob);});
  await waitFor(()=>expect(release).toBeTypeOf('function'));view.unmount();
  await act(async()=>{release(json({...native.job,version:native.job.version+1}));await pending;});
  expect(fetcher.mock.calls).toHaveLength(1);onlyMetadata();
});

it('revokes existing read controls after authoritative production READ denial',async()=>{
  await hook();server(url=>url.endsWith(`/jobs/image/${native.job.id}`)?json({code:'READ_REVOKED',message:'read revoked'},403):undefined);
  const read=state.openJob;await act(async()=>read(original() as ProductionJob));
  expect(props.onUnavailable).toHaveBeenCalledOnce();expect(state.selected).toBeUndefined();
  await act(async()=>{await read(original() as ProductionJob);state.downloadReceipt();});expect(fetcher.mock.calls).toHaveLength(1);
});
