// @vitest-environment jsdom
// Original task panel/controller + strict SDK. Synthetic receipts and real bounded PNG bytes; no processor/model call.
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {createHash,webcrypto} from 'node:crypto';
import {Blob as NodeBlob} from 'node:buffer';
import native from './fixtures/cpuCutout.mounted.json';
import {CanvasImageTaskReturn} from './CanvasImageTaskReturn';
import {studioClient} from './studioClient';
import type {CanvasViewRecord} from './studioCanvasViewClient';
import {StudioCanvasImageTaskPanel} from './StudioCanvasImageTaskPanel';
import {ExecutionImpactPanel} from '../experimental/executionImpact/ExecutionImpactPanel';
import {useStudioMediaExecution,type StudioMediaExecutionController,type StudioMediaExecutionProps} from './useStudioMediaExecution';
import {studioProductionClient,type MediaCommand,type ProductionJob} from './studioProductionClient';
import {checkedCanvasReturnBinding} from './studioCanvasReturnBinding';
import {cutoutAssets,cutoutBytes,cutoutHash,cutoutJob,cutoutPreview,cutoutProject,cutoutRecipe} from './studioCpuCutout.testFixtures';
import type {CanvasImageTaskSession} from './canvasImageTask';
import type {StudioAsset} from './studioClient';
const clone=<T,>(v:T):T=>structuredClone(v);
const canonical=(v:unknown)=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const hash=(v:unknown)=>createHash('sha256').update(canonical(v)).digest('hex');
const json=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
const deferred=<T,>()=>{let resolve!:(v:T)=>void;const promise=new Promise<T>(yes=>{resolve=yes;});return{promise,resolve};};
let state:StudioMediaExecutionController,props:StudioMediaExecutionProps,task:CanvasImageTaskSession,fetcher:ReturnType<typeof vi.fn>,saved:MediaCommand|undefined,job:ProductionJob|undefined;
let sourceCurrent=true,requestId='mask-entry-request',candidateBytes:Uint8Array;
const binding=()=>checkedCanvasReturnBinding({contract:'studio-canvas-return/1',project_id:cutoutProject,scope:{mode:'local',novel_id:cutoutProject},incarnation:'file:12345678-1234-1234-1234-123456789abc',canvas_id:'original-canvas',canvas_version:3,canvas_digest:'e'.repeat(64),card_id:'original-card',source:{kind:'ASSET',asset_kind:'image',id:'source',version:2,digest:'a'.repeat(64)}});
function receipt(kind:'preview'|'queued'|'executed'|'approved',command:MediaCommand){
 const v:any={...clone(native[kind]),...(kind==='preview'?cutoutPreview(command):cutoutJob(kind==='queued'?'QUEUED':kind==='executed'?'AWAITING_REVIEW':'APPROVED',kind==='queued'?1:kind==='executed'?3:4,command))};
 v.novel_id=cutoutProject;v.request_id=command.request_id;v.command=clone(command);v.command.source_snapshots=v.command.source_snapshots.map((s:any)=>({...s,reference_only:true}));v.request_digest=hash(command);
 v.execution_recipe={...cutoutRecipe(),parameters:clone(command.parameters),recipe_digest:hash(['recipe',command.parameters])};
 if(kind==='preview'){v.preview_digest=hash(['preview',command]);v.sources=command.source_snapshots.map(snapshot=>({snapshot:clone(snapshot),measured:{media_type:'image/png',extension:'png',width:64,height:64,validation:'DECODED'}}));}
 else {v.id='cutout-job';v.sources=clone(command.source_snapshots);}
 return v;
}
function HookHarness(){state=useStudioMediaExecution(props);return state.impact?<ExecutionImpactPanel input={state.impact.input} owner={state.impact} current={state.impact.current()} canConfirm={props.canMutate} busy={state.locked} isCurrent={state.impact.current} onConfirm={proof=>void state.confirmImpact(state.impact!,proof)}/>:null;}
function TaskHarness(){return <StudioCanvasImageTaskPanel key={task.id} {...props} task={task} taskAssets={props.assets}/>;}
beforeEach(()=>{
 sourceCurrent=true;requestId='mask-entry-request';saved=undefined;job=undefined;candidateBytes=cutoutBytes;
 vi.stubGlobal('crypto',{subtle:webcrypto.subtle,randomUUID:()=>requestId});
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=>'blob:private-mask-entry')});Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
 const assets=cutoutAssets(),returnBinding=binding();
 props={client:studioProductionClient(cutoutProject,{sessionToken:''}),assets,canMutate:true,canReview:true,busy:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),onDirtyChange:vi.fn(),onUnavailable:vi.fn(),onApproved:vi.fn(),canvasImageTask:{source:returnBinding.source,returnBinding,isCurrent:()=>sourceCurrent}};
 task={id:'task-a',origin:{projectId:cutoutProject,canvasId:returnBinding.canvas_id,canvasVersion:returnBinding.canvas_version,canvasDigest:returnBinding.canvas_digest,cardId:returnBinding.card_id,source:{asset_id:'source',kind:'image',version:2,digest:'a'.repeat(64)},binding:returnBinding},asset:assets[0],isOriginCurrent:()=>sourceCurrent};
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/providers'))return json({items:[],automatic_runtime_start:false,health_probed:false,credentials_read:false});
  if(url.endsWith('/preview'))return json(receipt('preview',body));
  if(url.endsWith('/jobs')&&init.method==='POST'){saved=clone(body.command);job=receipt('queued',saved!);return json(job);}
  if(url.endsWith('/jobs'))return json({items:job?[job]:[],product_acceptance:'LOCAL_REQUIRED'});
  if(url.endsWith('/execute')){job=receipt('executed',saved!);return json(job);}
  if(url.endsWith('/review')){job=receipt('approved',saved!);return json(job);}
  if(url.endsWith('/candidate'))return {ok:true,status:200,headers:new Headers({'Content-Type':'image/png'}),blob:async()=>new NodeBlob([candidateBytes],{type:'image/png'})} as unknown as Response;
  if(url.endsWith('/jobs/image/cutout-job'))return json(job);
  throw new Error('Unexpected original SDK fixture request '+url);
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const posts=(suffix:string)=>fetcher.mock.calls.filter(([u,i])=>u.endsWith(suffix)&&i.method==='POST');
const click=(name:string)=>fireEvent.click(screen.getByRole('button',{name}));
async function hook(){const view=render(<HookHarness/>);await waitFor(()=>expect(state.providerLoading).toBe(false));act(()=>{state.changeOperation('m5.image.cutout');state.selectMask('mask');});expect(state.inputError).toBe('');return view;}
async function confirm(kind:'CREATE'|'EXECUTE'){
 expect(state.impact?.input.boundary.kind).toBe(kind);const consent=screen.getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((consent as HTMLInputElement).disabled).toBe(false));fireEvent.click(consent);click('确认本次输入核对');await waitFor(()=>expect(kind==='CREATE'?state.canCreate:state.canAction('execute')).toBe(true));
}
async function preview(){await act(async()=>state.inspect());expect(state.error).toBe('');expect(state.preview).toBeTruthy();act(()=>state.confirmPreview(true));}
async function queued(){await preview();await confirm('CREATE');await act(async()=>state.create());expect(state.error).toBe('');expect(state.selected?.status).toBe('QUEUED');}
async function executionReady(){await act(async()=>state.inspectExecution());expect(state.error).toBe('');await confirm('EXECUTE');}
async function taskImpact(kind:'CREATE'|'EXECUTE'='CREATE'){const input=screen.getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((input as HTMLInputElement).disabled).toBe(false));fireEvent.click(input);click('确认本次输入核对');await waitFor(()=>expect((screen.getByRole('button',{name:kind==='CREATE'?'仅创建任务并入队':'明确执行当前入队任务'}) as HTMLButtonElement).disabled).toBe(false));}
it('actual saved-card panel uses fixed source, an explicit user mask, both proof gates, original Job re-preview and private PNG review',async()=>{
 render(<TaskHarness/>);const operation=screen.getByLabelText('操作');await waitFor(()=>expect((operation as HTMLSelectElement).disabled).toBe(false));expect([...operation.querySelectorAll('option')].map(x=>x.value)).toEqual(['m5.image.i2i','m5.image.cutout','m5.image.composite']);
 fireEvent.change(operation,{target:{value:'m5.image.cutout'}});expect((screen.getByLabelText('source.png · v2') as HTMLInputElement).disabled).toBe(true);expect((screen.getByLabelText('source.png · v2') as HTMLInputElement).checked).toBe(true);
 expect(screen.queryByLabelText('服务商与模型')).toBeNull();expect(screen.queryByLabelText('本次提示词')).toBeNull();expect(posts('/preview')).toHaveLength(0);
 fireEvent.change(screen.getByLabelText('绑定当前来源版本的遮罩'),{target:{value:'mask'}});click('读取制作预览');await screen.findByRole('region',{name:'制作预览确认'});
 expect(posts('/jobs')).toHaveLength(0);expect(posts('/execute')).toHaveLength(0);expect((screen.getByRole('button',{name:'仅创建任务并入队'}) as HTMLButtonElement).disabled).toBe(true);
 const command=JSON.parse(String(posts('/preview')[0][1].body));expect(command.source_snapshots.every((s:any)=>!Object.hasOwn(s,'reference_only'))).toBe(true);expect(command.canvas_return).toEqual(binding());
 fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));expect((screen.getByRole('button',{name:'仅创建任务并入队'}) as HTMLButtonElement).disabled).toBe(true);await taskImpact();click('仅创建任务并入队');
 await screen.findByText('任务已保存入队。执行仍需单独点击。');expect(job!.command!.source_snapshots.every(s=>s.reference_only===true)).toBe(true);expect(posts('/execute')).toHaveLength(0);
 click('读取原入队任务预览');await screen.findByText('已核对原入队任务预览；仍需单独确认本次执行输入，没有派发。');const repeated=JSON.parse(String(posts('/preview').at(-1)![1].body));expect(repeated.source_snapshots).toEqual(saved!.source_snapshots);expect(repeated.source_snapshots.every((s:any)=>!Object.hasOwn(s,'reference_only'))).toBe(true);
 await taskImpact('EXECUTE');await waitFor(()=>expect((screen.getByRole('button',{name:'明确执行当前入队任务'}) as HTMLButtonElement).disabled).toBe(false));click('明确执行当前入队任务');await waitFor(()=>expect((screen.getByRole('button',{name:'读取并核对候选媒体'}) as HTMLButtonElement).disabled).toBe(false));
 expect(posts('/review')).toHaveLength(0);expect(URL.createObjectURL).not.toHaveBeenCalled();click('读取并核对候选媒体');await screen.findByAltText('本任务经摘要核对的图片候选');expect((screen.getByRole('button',{name:'明确审核并入素材库'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));click('明确审核并入素材库');await waitFor(()=>expect(props.onApproved).toHaveBeenCalledTimes(1));expect(job!.status).toBe('APPROVED');expect(posts('/execute')).toHaveLength(1);expect(posts('/review')).toHaveLength(1);expect(job!.output_candidate!.digest).toBe(cutoutHash);
});
it('original CREATE and EXECUTE APIs reject bypasses and consume separate single-use confirmations for duplicate clicks',async()=>{
 await hook();await preview();await act(async()=>state.create());expect(posts('/jobs')).toHaveLength(0);await confirm('CREATE');await act(async()=>Promise.all([state.create(),state.create()]));expect(posts('/jobs')).toHaveLength(1);
 await act(async()=>state.action('execute'));expect(posts('/execute')).toHaveLength(0);await executionReady();await act(async()=>Promise.all([state.action('execute'),state.action('execute')]));expect(posts('/execute')).toHaveLength(1);
});
it.each(['mask change','output profile'] as const)('retires CREATE proof after %s and does not revive across parameter ABA',async mode=>{
 const second=clone(props.assets[1]);second.id='mask-b';second.provenance=Object.assign({},second.provenance!,{id:'mask-b'});props={...props,assets:[...props.assets,second]};await hook();await preview();await confirm('CREATE');const gate=state.impact!,create=state.create;
 act(()=>mode==='mask change'?state.selectMask('mask-b'):state.changeParameter('cutout_output','WEBP_LOSSLESS_V1'));act(()=>mode==='mask change'?state.selectMask('mask'):state.changeParameter('cutout_output',''));await act(async()=>create());expect(gate.current()).toBe(false);expect(state.preview).toBeUndefined();expect(posts('/jobs')).toHaveLength(0);
});
it.each(['source','mask'] as const)('refuses stale %s pin at queued execution',async which=>{
 const view=await hook();await queued();await executionReady();const execute=state.action;props={...props,assets:props.assets.map(row=>row.id===which?{...row,version:row.version+1}:row)};view.rerender(<HookHarness/>);await act(async()=>execute('execute'));expect(posts('/execute')).toHaveLength(0);expect(state.canAction('execute')).toBe(false);
});
it.each(['client','task'] as const)('retires confirmed proof across %s A/B/A and rejects retained execution',async which=>{
 const view=await hook();await queued();await executionReady();const gate=state.impact!,execute=state.action,original=props;
 props=which==='client'?{...original,client:studioProductionClient('other-project',{sessionToken:''})}:{...original,canvasImageTask:{...original.canvasImageTask!,returnBinding:{...original.canvasImageTask!.returnBinding!,card_id:'other-card'}}};view.rerender(<HookHarness/>);props=original;view.rerender(<HookHarness/>);await act(async()=>execute('execute'));expect(gate.current()).toBe(false);expect(posts('/execute')).toHaveLength(0);
});
it.each(['preview','execute'] as const)('drops late %s receipt across client A/B/A',async phase=>{
 const view=await hook();if(phase==='execute'){await queued();await executionReady();}const wait=deferred<Response>(),prior=fetcher.getMockImplementation()!;fetcher.mockImplementation((url,init)=>url.endsWith('/'+phase)?wait.promise:prior(url,init));
 let pending!:Promise<void>;act(()=>{pending=phase==='preview'?state.inspect():state.action('execute');});await waitFor(()=>expect(posts('/'+phase)).toHaveLength(1));const original=props.client;props={...props,client:studioProductionClient('other-project',{sessionToken:''})};view.rerender(<HookHarness/>);props={...props,client:original};view.rerender(<HookHarness/>);
 const command=phase==='preview'?JSON.parse(String(posts('/preview').at(-1)![1].body)):saved!;await act(async()=>{wait.resolve(json(receipt(phase==='preview'?'preview':'executed',command)));await pending;});expect(state.preview).toBeUndefined();expect(state.selected).toBeUndefined();expect(URL.createObjectURL).not.toHaveBeenCalled();expect(posts('/review')).toHaveLength(0);
});
it('the task keyed entry retires a late preview when task A/B/A remounts',async()=>{
 const view=render(<TaskHarness/>);await waitFor(()=>expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));fireEvent.change(screen.getByLabelText('操作'),{target:{value:'m5.image.cutout'}});fireEvent.change(screen.getByLabelText('绑定当前来源版本的遮罩'),{target:{value:'mask'}});
 const wait=deferred<Response>(),prior=fetcher.getMockImplementation()!;fetcher.mockImplementation((url,init)=>url.endsWith('/preview')?wait.promise:prior(url,init));click('读取制作预览');await waitFor(()=>expect(posts('/preview')).toHaveLength(1));const old=task;task={...old,id:'task-b'};view.rerender(<TaskHarness/>);task=old;view.rerender(<TaskHarness/>);await act(async()=>wait.resolve(json(receipt('preview',JSON.parse(String(posts('/preview')[0][1].body))))));expect(screen.queryByRole('region',{name:'制作预览确认'})).toBeNull();expect(posts('/jobs')).toHaveLength(0);
});
it('UNKNOWN never redispatches the original cutout, even through retained action callbacks',async()=>{
 await hook();await queued();const unknown={...job!,status:'UNKNOWN',version:2} as ProductionJob;job=unknown;await act(async()=>state.openJob(unknown));const execute=state.action;await act(async()=>{await state.inspectExecution();await execute('execute');await execute('execute');});expect(state.selected?.status).toBe('UNKNOWN');expect(state.canAction('execute')).toBe(false);expect(posts('/execute')).toHaveLength(0);expect(posts('/jobs')).toHaveLength(1);
});
it.each(['size','sha256'] as const)('refuses candidate %s mismatch before allowing explicit review',async mode=>{
 await hook();await queued();await executionReady();await act(async()=>state.action('execute'));candidateBytes=mode==='size'?cutoutBytes.slice(0,-1):new Uint8Array(cutoutBytes);if(mode==='sha256')candidateBytes[candidateBytes.length-1]^=1;await act(async()=>state.loadCandidate());expect(state.candidate).toBeUndefined();expect(state.canAction('review')).toBe(false);expect(URL.createObjectURL).not.toHaveBeenCalled();expect(posts('/review')).toHaveLength(0);
});
it('revalidates the one-use proof inside the local dispatch lease after source changes while waiting',async()=>{
 const lease=deferred<void>();props.cutoutExecution={execute:vi.fn(async(job:ProductionJob,authorize?:()=>void)=>{await lease.promise;authorize?.();return props.client.execute(job);}),control:vi.fn()};await hook();await queued();await executionReady();let sending!:Promise<void>;act(()=>{sending=state.action('execute');});await waitFor(()=>expect(props.cutoutExecution!.execute).toHaveBeenCalledTimes(1));props.assets[0].version++;
 await act(async()=>{lease.resolve();await sending;});expect(posts('/execute')).toHaveLength(0);expect(state.candidate).toBeUndefined();
});
it('consumes a live EXECUTE proof exactly once at the original local dispatch boundary',async()=>{
 let authorizeSaved:(()=>void)|undefined;props.cutoutExecution={execute:vi.fn(async(job:ProductionJob,authorize?:()=>void)=>{authorizeSaved=authorize;authorize?.();return props.client.execute(job);}),control:vi.fn()};await hook();await queued();await executionReady();await act(async()=>state.action('execute'));expect(posts('/execute')).toHaveLength(1);expect(authorizeSaved).toBeTypeOf('function');expect(()=>authorizeSaved!()).toThrow();expect(posts('/execute')).toHaveLength(1);
});

it('reopens a saved private cutout candidate in the original task panel without dispatch or automatic review',async()=>{
 const view=await hook();await queued();await executionReady();await act(async()=>state.action('execute'));task={...task,resumeJob:clone(state.selected!)};view.unmount();const before={create:posts('/jobs').length,execute:posts('/execute').length,review:posts('/review').length};render(<TaskHarness/>);
 await waitFor(()=>expect((screen.getByRole('button',{name:'读取并核对候选媒体'}) as HTMLButtonElement).disabled).toBe(false));expect(screen.queryByRole('region',{name:'制作预览确认'})).toBeNull();expect(URL.createObjectURL).not.toHaveBeenCalled();click('读取并核对候选媒体');await screen.findByAltText('本任务经摘要核对的图片候选');expect(posts('/jobs')).toHaveLength(before.create);expect(posts('/execute')).toHaveLength(before.execute);expect(posts('/review')).toHaveLength(before.review);expect((screen.getByRole('button',{name:'明确审核并入素材库'}) as HTMLButtonElement).disabled).toBe(true);
});
it('task keyed A/B/A drops late execution and exposes no stale candidate or review authority',async()=>{
 const view=await hook();await queued();task={...task,resumeJob:clone(state.selected!)};view.unmount();const panel=render(<TaskHarness/>);await screen.findByRole('region',{name:'当前媒体任务'});click('读取原入队任务预览');await screen.findByText('已核对原入队任务预览；仍需单独确认本次执行输入，没有派发。');await taskImpact('EXECUTE');
 const wait=deferred<Response>(),prior=fetcher.getMockImplementation()!;fetcher.mockImplementation((url,init)=>url.endsWith('/execute')?wait.promise:prior(url,init));click('明确执行当前入队任务');await waitFor(()=>expect(posts('/execute')).toHaveLength(1));const original=task;task={...task,id:'other-task',resumeJob:undefined};panel.rerender(<TaskHarness/>);task=original;panel.rerender(<TaskHarness/>);await act(async()=>wait.resolve(json(receipt('executed',saved!))));expect(screen.queryByAltText('本任务经摘要核对的图片候选')).toBeNull();expect(screen.queryByRole('region',{name:'媒体候选预览与审核'})).toBeNull();expect(posts('/review')).toHaveLength(0);
});
function originalCanvas():CanvasViewRecord{return{project_id:cutoutProject,scope:binding().scope,id:binding().canvas_id,version:3,definition_digest:binding().canvas_digest,created_at:'2026-10-21T00:00:00Z',updated_at:'2026-10-21T00:00:00Z',execution_authority:false,binary_content_verified:false,capacity:{history_used:0,record_bytes:1000},reference_states:[{card_id:'original-card',state:'CURRENT_METADATA',filename:'source.png'},{card_id:'other-card',state:'CURRENT_METADATA',filename:'source.png'}],definition:{schema_version:1,title:'Original canvas',viewport:{x:12,y:24,zoom:1},cards:[{id:'original-card',position:{x:44,y:66},asset:clone(task.origin.source)},{id:'other-card',position:{x:400,y:100},asset:clone(task.origin.source)}],groups:[{id:'original-group',name:'Saved group',card_ids:['original-card'],collapsed:false}]}};}
async function approvedReturn(stale=false){
 const view=await hook();await queued();await executionReady();await act(async()=>state.action('execute'));await act(async()=>state.loadCandidate());act(()=>state.confirmReview(true));await act(async()=>state.action('review'));expect(state.selected?.status).toBe('APPROVED');const approved=clone(state.selected!),canvas=originalCanvas(),original=clone(canvas),prior=fetcher.getMockImplementation()!,adopt=vi.fn(),complete=vi.fn(),uncertain=vi.fn();view.unmount();
 const formal:StudioAsset={...props.assets[0],id:approved.output_candidate!.id,version:approved.approved_asset_version!,sha256:approved.output_candidate!.digest,size:cutoutBytes.length,filename:'approved-cutout.png'};
 const path=`/api/projects/${cutoutProject}/studio/canvas-views/${canvas.id}`;if(stale)canvas.version=4;
 fetcher.mockImplementation(async(url:string,init:RequestInit={})=>{
  if(url.endsWith('/assets/'+formal.id))return json(formal);
  if(url===path+'/history')return json({project_id:cutoutProject,scope:canvas.scope,id:canvas.id,incarnation:binding().incarnation,current_version:canvas.version,current_definition_digest:canvas.definition_digest,items:Array.from({length:canvas.version},(_,i)=>({version:i+1,definition_digest:canvas.definition_digest,definition:canvas.definition,created_at:canvas.created_at,updated_at:canvas.updated_at,reference_states:canvas.reference_states,can_restore:i+1<canvas.version})),restore_policy:'CURRENT_METADATA_ONLY',execution_authority:false,binary_content_verified:false});
  if(url===path&&init.method==='PUT'){const body=JSON.parse(String(init.body));expect(body.expected_version).toBe(3);expect(body.expected_incarnation).toBe(binding().incarnation);expect(body.expected_definition_digest).toBe(binding().canvas_digest);expect(body.expected_card).toEqual({card_id:'original-card',source:task.origin.source});Object.assign(canvas,{version:4,definition:body.definition,definition_digest:'f'.repeat(64)});return json(canvas);}
  if(url===path)return json(canvas);
  return prior(url,init);
 });
 render(<CanvasImageTaskReturn task={task} approved={approved} client={studioClient(cutoutProject,{sessionToken:''})} production={props.client} disabled={false} canMutate isCurrent={()=>true} read={f=>f()} mutate={f=>f()} onAdopt={adopt} onComplete={complete} onUncertain={uncertain}/>);
 return{adopt,complete,uncertain,canvas,original,path};
}
it('original return component adopts an explicitly reviewed cutout only to the captured card with original CAS and preserves layout',async()=>{
 const result=await approvedReturn();expect(result.adopt).not.toHaveBeenCalled();click('核验原位置与正式审核结果');fireEvent.click(await screen.findByLabelText('确认只采用到上述原卡片'));click('确认采用并回填原卡片');await waitFor(()=>expect(result.complete).toHaveBeenCalledTimes(1));expect(result.adopt).toHaveBeenCalledTimes(1);expect(result.uncertain).not.toHaveBeenCalled();expect(result.canvas.version).toBe(4);expect(result.canvas.definition.cards[0].asset).toEqual({asset_id:job!.output_candidate!.id,version:job!.approved_asset_version,digest:cutoutHash,kind:'image'});expect(result.canvas.definition.cards[0].position).toEqual(result.original.definition.cards[0].position);expect(result.canvas.definition.cards[1]).toEqual(result.original.definition.cards[1]);expect(result.canvas.definition.groups).toEqual(result.original.definition.groups);expect(fetcher.mock.calls.filter(([u,i])=>u===result.path&&i.method==='PUT')).toHaveLength(1);expect(posts('/execute')).toHaveLength(1);expect(posts('/review')).toHaveLength(1);
});
it('original return component blocks a stale canvas version and keeps the approved candidate instead of guessing another card',async()=>{
 const result=await approvedReturn(true);click('核验原位置与正式审核结果');await screen.findByText('原画布、卡片或素材版本已改变；不会回填当前选中的其他位置。');expect(screen.queryByLabelText('确认只采用到上述原卡片')).toBeNull();expect(result.adopt).not.toHaveBeenCalled();expect(fetcher.mock.calls.filter(([u,i])=>u===result.path&&i.method==='PUT')).toHaveLength(0);expect(job!.status).toBe('APPROVED');
});
