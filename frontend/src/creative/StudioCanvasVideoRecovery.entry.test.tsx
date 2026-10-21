// @vitest-environment jsdom
// Actual video controller + strict SDK, synthetic responses only. Native CPU is separate.
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {createHash,webcrypto} from 'node:crypto';
import native from './fixtures/canvasVideoTrim.native.json';
import {ExecutionImpactPanel} from '../experimental/executionImpact/ExecutionImpactPanel';
import {useStudioCanvasVideoTask,type StudioCanvasVideoTaskProps,type StudioCanvasVideoTaskController} from './useStudioCanvasVideoTask';
import {compileCanvasVideoTimeline,type CanvasVideoTaskCommand} from './canvasVideoTrimTask';
import {deriveFailedCanvasVideoDraft} from './videoTaskRecovery';
import {studioProductionClient,type ProductionJob} from './studioProductionClient';
const clone=<T,>(v:T):T=>structuredClone(v);
const canonical=(v:unknown)=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const hash=(v:unknown)=>createHash('sha256').update(canonical(v)).digest('hex');
const json=(v:unknown)=>new Response(JSON.stringify(v),{headers:{'Content-Type':'application/json'}});
let props:StudioCanvasVideoTaskProps,state:StudioCanvasVideoTaskController,fetcher:ReturnType<typeof vi.fn>,parent:ProductionJob;
let saved:CanvasVideoTaskCommand|undefined,timelines:Map<string,typeof native.timeline>,requestIndex=0;
function recipe(command:CanvasVideoTaskCommand){const r={...clone(native.preview.execution_recipe),timeline:compileCanvasVideoTimeline(command.source_snapshots[0],command.parameters)};r.recipe_digest=hash({...r,recipe_digest:undefined});return r;}
function receipt(kind:'preview'|'queued'|'executed',command:CanvasVideoTaskCommand){
 const row:any=clone(native[kind]);row.request_digest=hash(command);row.execution_recipe=recipe(command);
 if(kind==='preview'){row.command=clone(command);row.preview_digest=hash(['preview',command]);}
 else{row.request_id=command.request_id;row.id='job-'+command.request_id;row.canvas_video=clone(command);row.timeline_snapshot=clone(command.timeline_snapshot);row.sources=clone(command.source_snapshots);}
 return row;
}
function binding(){return {source:props.task.origin.binding!.source,returnBinding:props.task.origin.binding,isCurrent:props.task.isOriginCurrent};}
function Harness(){state=useStudioCanvasVideoTask(props);const gate=state.impact;return gate?<ExecutionImpactPanel input={gate.input} owner={gate} current={gate.current()} canConfirm={props.canMutate&&state.previewConfirmed} busy={state.locked} isCurrent={gate.current} onConfirm={proof=>void state.confirmImpact(gate,proof)}/>:null;}
beforeEach(()=>{
 saved=undefined;requestIndex=0;timelines=new Map([[native.timeline.id,clone(native.timeline)]]);
 parent={...clone(native.queued),status:'FAILED',version:3,output_candidate:null,media_measurement:null,receipt_digest:null,error_code:'TEST_CPU_RENDER_FAILED'} as unknown as ProductionJob;
 vi.stubGlobal('crypto',{subtle:webcrypto.subtle,randomUUID:()=>`video-derived-${++requestIndex}`});
 const b=clone(native.command.canvas_return);
 props={client:studioProductionClient(native.canvas.project_id,{sessionToken:''}),task:{id:'task',asset:clone(native.source_asset),origin:{projectId:b.project_id,canvasId:b.canvas_id,canvasVersion:b.canvas_version,canvasDigest:b.canvas_digest,cardId:b.card_id,source:{...clone(native.canvas.definition.cards[0].asset),kind:'video'},binding:b as any},resumeJob:parent,isOriginCurrent:()=>true},canMutate:true,canReview:true,busy:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),onDirtyChange:vi.fn(),onUnavailable:vi.fn()};
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/timelines')&&init.method==='POST'){const row={...clone(native.timeline),id:'child-timeline',timeline:body.timeline,version:1,timeline_digest:hash(body.timeline)};timelines.set(row.id,row);return json(row);}
  if(url.includes('/timelines/')&&init.method==='PUT'){const id=url.split('/').at(-1)!;const old=timelines.get(id)!;const row={...old,timeline:body.timeline,version:old.version+1,timeline_digest:hash(body.timeline)};timelines.set(id,row);return json(row);}
  if(url.includes('/timelines/'))return json(timelines.get(url.split('/').at(-1)!));
  if(url.endsWith('/canvas-video/preview'))return json(receipt('preview',body));
  if(url.endsWith('/canvas-video/queue')){saved=clone(body.command);return json(receipt('queued',saved!));}
  if(url.endsWith('/execute'))return json(receipt('executed',saved!));
  if(url.includes('/jobs/timeline/'))return json(saved?receipt('queued',saved):parent);
  throw new Error('Unexpected original-owner request '+url);
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const calls=(suffix:string)=>fetcher.mock.calls.filter(([u,i])=>u.endsWith(suffix)&&i.method==='POST');
async function inspect(){await act(async()=>state.inspect());expect(state.preview,state.error+'; posted previews='+calls('/canvas-video/preview').length+'; '+JSON.stringify(calls('/canvas-video/preview').at(-1)?.[1].body)).toBeTruthy();act(()=>state.confirmPreview(true));}
async function confirm(kind:'CREATE'|'EXECUTE'){expect(state.impact?.input.boundary.kind).toBe(kind);const check=screen.getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));fireEvent.click(check);fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));await waitFor(()=>expect(kind==='CREATE'?state.canCreate:state.canExecute).toBe(true));}
function derive(){const draft=deriveFailedCanvasVideoDraft(state.selected!,binding(),'explicit-child');act(()=>state.prepareFailedVideo(draft));return draft;}
it.each(['omitted','false','true'] as const)('derives %s audio policy without writing parent and uses independent Apply plus both original single-use gates',async choice=>{
 if(choice!=='omitted'){parent.canvas_video!.parameters.include_audio=choice==='true';parent.execution_recipe=recipe(parent.canvas_video!) as any;}
 const before=clone(parent);render(<Harness/>);const draft=derive();expect(state.selected).toBeUndefined();expect(state.timeline).toBeUndefined();expect(fetcher).not.toHaveBeenCalled();expect(state.derivedFrom?.job_id).toBe(parent.id);
 if(choice==='omitted')expect(Object.hasOwn(draft.parameters,'include_audio')).toBe(false);else expect(draft.parameters.include_audio).toBe(choice==='true');
 await act(async()=>state.apply());expect(state.timeline?.id,state.error).toBe('child-timeline');expect(calls('/timelines')[0][1].body&&JSON.parse(String(calls('/timelines')[0][1].body)).expected_version).toBe(0);
 expect(timelines.get(native.timeline.id)).toEqual(native.timeline);await inspect();await act(async()=>state.create());expect(calls('/canvas-video/queue')).toHaveLength(0);
 await confirm('CREATE');await act(async()=>Promise.all([state.create(),state.create()]));expect(state.selected?.status,state.error).toBe('QUEUED');expect(calls('/canvas-video/queue')).toHaveLength(1);expect(saved!.derived_from).toEqual(draft.derived_from);expect(saved!.request_id).not.toBe(parent.request_id);expect(saved!.timeline_snapshot.id).not.toBe(parent.timeline_snapshot!.id);
 await act(async()=>state.execute());expect(calls('/execute')).toHaveLength(0);await inspect();await confirm('EXECUTE');await act(async()=>Promise.all([state.execute(),state.execute()]));expect(calls('/execute')).toHaveLength(1);expect(state.selected?.status,state.error).toBe('SUCCEEDED');expect(parent).toEqual(before);
});
it('reopens the child queued identity and origin, requiring a fresh execution preview/proof without another queue',async()=>{
 const view=render(<Harness/>);derive();await act(async()=>state.apply());await inspect();await confirm('CREATE');await act(async()=>state.create());const child=clone(state.selected!);view.unmount();props={...props,task:{...props.task,resumeJob:child}};render(<Harness/>);expect(state.impact).toBeUndefined();expect(calls('/execute')).toHaveLength(0);
 await act(async()=>state.readJob());expect(state.derivedFrom).toEqual(child.canvas_video!.derived_from);expect(state.timeline?.id).toBe(child.timeline_snapshot!.id);await inspect();await confirm('EXECUTE');await act(async()=>state.execute());expect(calls('/canvas-video/queue')).toHaveLength(1);expect(calls('/execute')).toHaveLength(1);
});
it('retires a derived CREATE proof after observed parameter ABA and permits a new explicit confirmation',async()=>{
 render(<Harness/>);derive();await act(async()=>state.apply());await inspect();await confirm('CREATE');const gate=state.impact!,create=state.create;act(()=>state.changeParameter('out_ms','1640'));act(()=>state.changeParameter('out_ms','1600'));await act(async()=>create());expect(gate.current()).toBe(false);expect(calls('/canvas-video/queue')).toHaveLength(0);
 await act(async()=>state.apply());await inspect();await confirm('CREATE');await act(async()=>state.create());expect(calls('/canvas-video/queue')).toHaveLength(1);expect(saved!.derived_from?.job_id).toBe(parent.id);
});
it('never derives UNKNOWN or accepts a captured FAILED draft after source/current ownership is lost',()=>{
 render(<Harness/>);const draft=deriveFailedCanvasVideoDraft(state.selected!,binding(),'explicit-child');const derive=state.prepareFailedVideo;parent.status='UNKNOWN';props.task.resumeJob=parent;props.task.isOriginCurrent=()=>false;act(()=>derive(draft));expect(state.selected?.id).toBe(parent.id);expect(fetcher).not.toHaveBeenCalled();
 expect(()=>deriveFailedCanvasVideoDraft(parent,binding(),'other-child')).toThrow();
});
