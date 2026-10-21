// @vitest-environment jsdom
// Original task/controller/strict SDK with native recorded envelopes and real captured PNG bytes.
// This suite does not invoke the CPU processor or a model; parent verifies actual pixel arithmetic separately.
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {createHash,webcrypto} from 'node:crypto';
import {CanvasImageTaskReturn} from './CanvasImageTaskReturn';
import {StudioCanvasImageTaskPanel} from './StudioCanvasImageTaskPanel';
import {ExecutionImpactPanel} from '../experimental/executionImpact/ExecutionImpactPanel';
import {useStudioMediaExecution,type StudioMediaExecutionController,type StudioMediaExecutionProps} from './useStudioMediaExecution';
import {studioProductionClient,type MediaCommand,type ProductionJob,type ProductionPreview} from './studioProductionClient';
import {checkedCanvasReturnBinding} from './studioCanvasReturnBinding';
import {studioClient,type StudioAsset} from './studioClient';
import type {CanvasImageTaskSession} from './canvasImageTask';
import type {CanvasViewRecord} from './studioCanvasViewClient';
import captured from './fixtures/image-composite.capture.json';
const actual=captured as unknown as {command:MediaCommand;preview:ProductionPreview;queued:ProductionJob;executed:ProductionJob;approved:ProductionJob;assets:StudioAsset[];output_base64:string};
const project=actual.preview.novel_id,first=actual.command.source_snapshots[0].id,second=actual.command.source_snapshots[1].id,bytes=Uint8Array.from(Buffer.from(actual.output_base64,'base64'));
const clone=<T,>(v:T):T=>structuredClone(v),canonical=(v:unknown)=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const hash=(v:unknown)=>createHash('sha256').update(canonical(v)).digest('hex');
const json=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
const deferred=<T,>()=>{let resolve!:(v:T)=>void;const promise=new Promise<T>(yes=>{resolve=yes;});return{promise,resolve};};
let state:StudioMediaExecutionController,props:StudioMediaExecutionProps,task:CanvasImageTaskSession,fetcher:ReturnType<typeof vi.fn>,saved:MediaCommand|undefined,job:ProductionJob|undefined,candidateBytes:Uint8Array;
let originCurrent=true;
const binding=()=>checkedCanvasReturnBinding({contract:'studio-canvas-return/1',project_id:project,scope:{mode:'local',novel_id:project},incarnation:'file:12345678-1234-1234-1234-123456789abc',canvas_id:'composite-canvas',canvas_version:1,canvas_digest:'e'.repeat(64),card_id:'original-card',source:clone(actual.command.source_snapshots[0])});
function recorded(command:MediaCommand){return{...clone(command),source_snapshots:command.source_snapshots.map(source=>({...clone(source),reference_only:true as const}))};}
function previewReceipt(command:MediaCommand):ProductionPreview{
 const row=clone(actual.preview);row.request_id=command.request_id;row.command=recorded(command);row.request_digest=hash(command);row.preview_digest=hash(['preview',command]);row.sources=command.source_snapshots.map(snapshot=>({snapshot:clone(snapshot),measured:{media_type:'image/png',extension:'png',width:64,height:64,validation:'DECODED'}}));row.execution_recipe={...row.execution_recipe,layers:clone(command.image_layers),recipe_digest:hash(['recipe',command.image_layers])};return row;
}
function jobReceipt(kind:'queued'|'executed'|'approved',command:MediaCommand):ProductionJob{
 const row=clone(actual[kind]);row.request_id=command.request_id;row.command=recorded(command);row.request_digest=hash(command);row.sources=clone(command.source_snapshots);row.execution_recipe={...row.execution_recipe,layers:clone(command.image_layers),recipe_digest:hash(['recipe',command.image_layers])};
 if(row.processing_proof?.contract==='cpu-two-layer-composite/1')row.processing_proof={...row.processing_proof,source_sha256:command.source_snapshots.map(source=>source.digest),layers_digest:hash(command.image_layers)};return row;
}
function HookHarness(){state=useStudioMediaExecution(props);return state.impact?<ExecutionImpactPanel input={state.impact.input} owner={state.impact} current={state.impact.current()} canConfirm={props.canMutate} busy={state.locked} isCurrent={state.impact.current} onConfirm={proof=>void state.confirmImpact(state.impact!,proof)}/>:null;}
function TaskHarness(){return <StudioCanvasImageTaskPanel key={task.id} {...props} task={task} taskAssets={props.assets}/>;}
beforeEach(()=>{
 originCurrent=true;saved=undefined;job=undefined;candidateBytes=bytes;vi.stubGlobal('crypto',{subtle:webcrypto.subtle,randomUUID:()=> 'card-composite-request'});
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=>'blob:private-card-composite')});Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
 const returnBinding=binding(),assets=clone(actual.assets);
 props={client:studioProductionClient(project,{sessionToken:''}),assets,canMutate:true,canReview:true,busy:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),onDirtyChange:vi.fn(),onUnavailable:vi.fn(),onApproved:vi.fn(),canvasImageTask:{source:returnBinding.source,returnBinding,isCurrent:()=>originCurrent}};
 task={id:'composite-task-a',origin:{projectId:project,canvasId:returnBinding.canvas_id,canvasVersion:1,canvasDigest:returnBinding.canvas_digest,cardId:returnBinding.card_id,source:{asset_id:first,kind:'image',version:assets[0].version,digest:assets[0].sha256},binding:returnBinding},asset:assets[0],isOriginCurrent:()=>originCurrent};
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/providers'))return json({items:[],automatic_runtime_start:false,health_probed:false,credentials_read:false});
  if(url.endsWith('/preview'))return json(previewReceipt(body));
  if(url.endsWith('/jobs')&&init.method==='POST'){saved=clone(body.command);job=jobReceipt('queued',saved!);return json(job);}
  if(url.endsWith('/jobs'))return json({items:job?[job]:[],product_acceptance:'LOCAL_REQUIRED'});
  if(url.endsWith('/execute')){job=jobReceipt('executed',saved!);return json(job);}
  if(url.endsWith('/review')){job=jobReceipt('approved',saved!);return json(job);}
  if(url.endsWith('/reconcile')){job={...job!,version:job!.version+1};return json(job);}
  if(url.endsWith('/candidate'))return new Response(new Uint8Array(candidateBytes).buffer,{headers:{'Content-Type':'image/png','X-Asset-Sha256':actual.executed.output_candidate!.digest}});
  if(url.endsWith('/jobs/image/'+actual.queued.id))return json(job);
  throw new Error('Unexpected strict composite fixture request '+url);
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const posts=(suffix:string)=>fetcher.mock.calls.filter(([url,init])=>url.endsWith(suffix)&&init.method==='POST');
const click=(name:string)=>fireEvent.click(screen.getByRole('button',{name}));
async function hook(){const view=render(<HookHarness/>);await waitFor(()=>expect(state.providerLoading).toBe(false));act(()=>{state.changeOperation('m5.image.composite');state.selectSource(second,true);state.changeLayer(second,'opacity','128');});expect(state.inputError).toBe('');return view;}
async function confirm(kind:'CREATE'|'EXECUTE'){
 expect(state.impact?.input.boundary.kind).toBe(kind);const check=screen.getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));fireEvent.click(check);click('确认本次输入核对');await waitFor(()=>expect(kind==='CREATE'?state.canCreate:state.canAction('execute')).toBe(true));
}
async function preview(){await act(async()=>state.inspect());expect(state.error).toBe('');expect(state.preview).toBeTruthy();act(()=>state.confirmPreview(true));}
async function queued(){await preview();await confirm('CREATE');await act(async()=>state.create());expect(state.error).toBe('');expect(state.selected?.status).toBe('QUEUED');}
async function ready(){await act(async()=>state.inspectExecution());expect(state.error).toBe('');await confirm('EXECUTE');}
async function taskConfirm(kind:'CREATE'|'EXECUTE'){
 const check=screen.getByLabelText('已核对本次输入变化与影响范围');await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));fireEvent.click(check);click('确认本次输入核对');await waitFor(()=>expect((screen.getByRole('button',{name:kind==='CREATE'?'仅创建任务并入队':'明确执行当前入队任务'}) as HTMLButtonElement).disabled).toBe(false));
}
it('actual saved-card panel binds two real layers, separately confirms the original Job and inspects private PNG before review',async()=>{
 render(<TaskHarness/>);const operation=screen.getByLabelText('操作');await waitFor(()=>expect((operation as HTMLSelectElement).disabled).toBe(false));expect([...operation.querySelectorAll('option')].map(option=>option.value)).toContain('m5.image.composite');fireEvent.change(operation,{target:{value:'m5.image.composite'}});
 const original=screen.getByLabelText(actual.assets[0].filename+' · v1') as HTMLInputElement,extra=screen.getByLabelText(actual.assets[1].filename+' · v1') as HTMLInputElement;expect(original.disabled).toBe(true);expect(original.checked).toBe(true);expect(extra.disabled).toBe(false);expect(extra.checked).toBe(false);expect(screen.queryByLabelText('服务商与模型')).toBeNull();expect(screen.queryByLabelText('本次提示词')).toBeNull();
 fireEvent.click(extra);fireEvent.change(screen.getByLabelText('第 2 层透明度（0–255）'),{target:{value:'128'}});click('读取制作预览');await screen.findByRole('region',{name:'制作预览确认'});expect(posts('/jobs')).toHaveLength(0);expect(posts('/execute')).toHaveLength(0);
 const command=JSON.parse(String(posts('/preview')[0][1].body)) as MediaCommand;expect(command.image_layers).toEqual(actual.command.image_layers);expect(command.canvas_return).toEqual(binding());expect(command.source_snapshots.every(source=>!Object.hasOwn(source,'reference_only'))).toBe(true);
 fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));expect((screen.getByRole('button',{name:'仅创建任务并入队'}) as HTMLButtonElement).disabled).toBe(true);await taskConfirm('CREATE');click('仅创建任务并入队');await screen.findByText('任务已保存入队。执行仍需单独点击。');expect(job!.command!.source_snapshots.every(source=>source.reference_only===true)).toBe(true);
 click('读取原入队任务预览');await screen.findByText('已核对原入队任务预览；仍需单独确认本次执行输入，没有派发。');const repeated=JSON.parse(String(posts('/preview').at(-1)![1].body)) as MediaCommand;expect(repeated.image_layers).toEqual(saved!.image_layers);expect(repeated.source_snapshots).toEqual(saved!.source_snapshots);expect(repeated.source_snapshots.every(source=>!Object.hasOwn(source,'reference_only'))).toBe(true);await taskConfirm('EXECUTE');click('明确执行当前入队任务');
 await waitFor(()=>expect((screen.getByRole('button',{name:'读取并核对候选媒体'}) as HTMLButtonElement).disabled).toBe(false));expect(posts('/review')).toHaveLength(0);expect(URL.createObjectURL).not.toHaveBeenCalled();click('读取并核对候选媒体');await screen.findByAltText('本任务经摘要核对的图片候选');expect((screen.getByRole('button',{name:'明确审核并入素材库'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));click('明确审核并入素材库');await waitFor(()=>expect(props.onApproved).toHaveBeenCalledTimes(1));expect(posts('/execute')).toHaveLength(1);expect(posts('/review')).toHaveLength(1);expect(job!.status).toBe('APPROVED');expect(job!.output_candidate!.digest).toBe(actual.executed.output_candidate!.digest);
});
it('swaps the original PNG to the top and preserves fixed target plus exact visible/opacity values through original queue and re-preview',async()=>{
 await hook();act(()=>{state.swapLayers();state.changeLayer(first,'visible',false);state.changeLayer(first,'opacity','73');});await queued();expect(saved!.source_snapshots.map(source=>source.id)).toEqual([second,first]);expect(saved!.image_layers!.map(layer=>[layer.source.id,layer.visible,layer.opacity])).toEqual([[second,true,128],[first,false,73]]);expect(saved!.canvas_return).toEqual(binding());await act(async()=>state.inspectExecution());expect(state.error).toBe('');const repeated=JSON.parse(String(posts('/preview').at(-1)![1].body)) as MediaCommand;expect(repeated.image_layers).toEqual(saved!.image_layers);expect(repeated.canvas_return!.source.id).toBe(first);expect(posts('/execute')).toHaveLength(0);
});
it('cannot replace or remove the original pin while the explicitly added second PNG can be removed',async()=>{
 await hook();const before=clone(state.draft.sources);act(()=>state.selectSource(first,false));expect(state.draft.sources).toEqual(before);act(()=>state.selectSource(second,false));expect(state.draft.sources.map(source=>source.id)).toEqual([first]);await act(async()=>state.inspect());expect(posts('/preview')).toHaveLength(0);expect(state.canInspect).toBe(false);
});
it.each(['swap','visibility','opacity','second source'] as const)('retires CREATE proof after %s A/B/A instead of reviving it',async mode=>{
 const third={...clone(actual.assets[1]),id:'third-png',filename:'third.png'};props={...props,assets:[...props.assets,third]};await hook();await preview();await confirm('CREATE');const gate=state.impact!,create=state.create;
 act(()=>{if(mode==='swap')state.swapLayers();if(mode==='visibility')state.changeLayer(second,'visible',false);if(mode==='opacity')state.changeLayer(second,'opacity','127');if(mode==='second source'){state.selectSource(second,false);state.selectSource(third.id,true);}});
 act(()=>{if(mode==='swap')state.swapLayers();if(mode==='visibility')state.changeLayer(second,'visible',true);if(mode==='opacity')state.changeLayer(second,'opacity','128');if(mode==='second source'){state.selectSource(third.id,false);state.selectSource(second,true);state.changeLayer(second,'opacity','128');}});
 await act(async()=>create());expect(gate.current()).toBe(false);expect(state.preview).toBeUndefined();expect(posts('/jobs')).toHaveLength(0);
});
it('rejects direct unconfirmed dispatch and duplicate creation/execution at the original APIs',async()=>{
 await hook();await preview();await act(async()=>state.create());expect(posts('/jobs')).toHaveLength(0);await confirm('CREATE');await act(async()=>Promise.all([state.create(),state.create()]));expect(posts('/jobs')).toHaveLength(1);await act(async()=>state.action('execute'));expect(posts('/execute')).toHaveLength(0);await ready();await act(async()=>Promise.all([state.action('execute'),state.action('execute')]));expect(posts('/execute')).toHaveLength(1);
});
it.each(['original','second'] as const)('refuses changed %s pin at original queued execution',async which=>{
 const view=await hook();await queued();await ready();const id=which==='original'?first:second,execute=state.action;props={...props,assets:props.assets.map(asset=>asset.id===id?{...asset,version:asset.version+1}:asset)};view.rerender(<HookHarness/>);await act(async()=>execute('execute'));expect(state.canAction('execute')).toBe(false);expect(posts('/execute')).toHaveLength(0);
});
it.each(['client','task'] as const)('retires EXECUTE proof across %s A/B/A',async which=>{
 const view=await hook();await queued();await ready();const original=props,execute=state.action,gate=state.impact!;props=which==='client'?{...original,client:studioProductionClient('other-project',{sessionToken:''})}:{...original,canvasImageTask:{...original.canvasImageTask!,returnBinding:{...original.canvasImageTask!.returnBinding!,card_id:'other-card'}}};view.rerender(<HookHarness/>);props=original;view.rerender(<HookHarness/>);await act(async()=>execute('execute'));expect(gate.current()).toBe(false);expect(posts('/execute')).toHaveLength(0);
});
it.each(['preview','execute'] as const)('ignores late %s across client A/B/A',async phase=>{
 const view=await hook();if(phase==='execute'){await queued();await ready();}const wait=deferred<Response>(),prior=fetcher.getMockImplementation()!;fetcher.mockImplementation((url,init)=>url.endsWith('/'+phase)?wait.promise:prior(url,init));let work!:Promise<void>;act(()=>{work=phase==='preview'?state.inspect():state.action('execute');});await waitFor(()=>expect(posts('/'+phase)).toHaveLength(1));const original=props.client;props={...props,client:studioProductionClient('other-project',{sessionToken:''})};view.rerender(<HookHarness/>);props={...props,client:original};view.rerender(<HookHarness/>);const command=phase==='preview'?JSON.parse(String(posts('/preview')[0][1].body)) as MediaCommand:saved!;await act(async()=>{wait.resolve(json(phase==='preview'?previewReceipt(command):jobReceipt('executed',command)));await work;});expect(state.preview).toBeUndefined();expect(state.selected).toBeUndefined();expect(URL.createObjectURL).not.toHaveBeenCalled();expect(posts('/review')).toHaveLength(0);
});
it('reopens private composite output in the original task panel with no replay or automatic adoption',async()=>{
 const view=await hook();await queued();await ready();await act(async()=>state.action('execute'));task={...task,resumeJob:clone(state.selected!)};view.unmount();const before=posts('/execute').length;render(<TaskHarness/>);await waitFor(()=>expect((screen.getByRole('button',{name:'读取并核对候选媒体'}) as HTMLButtonElement).disabled).toBe(false));expect(URL.createObjectURL).not.toHaveBeenCalled();click('读取并核对候选媒体');await screen.findByAltText('本任务经摘要核对的图片候选');expect(posts('/execute')).toHaveLength(before);expect(posts('/jobs')).toHaveLength(1);expect(posts('/review')).toHaveLength(0);expect((screen.getByRole('button',{name:'明确审核并入素材库'}) as HTMLButtonElement).disabled).toBe(true);
});
it('task keyed A/B/A drops a late execute and cannot acquire stale candidate review authority',async()=>{
 const view=await hook();await queued();task={...task,resumeJob:clone(state.selected!)};view.unmount();const mounted=render(<TaskHarness/>);await screen.findByRole('region',{name:'当前媒体任务'});click('读取原入队任务预览');await screen.findByText('已核对原入队任务预览；仍需单独确认本次执行输入，没有派发。');await taskConfirm('EXECUTE');const wait=deferred<Response>(),prior=fetcher.getMockImplementation()!;fetcher.mockImplementation((url,init)=>url.endsWith('/execute')?wait.promise:prior(url,init));click('明确执行当前入队任务');await waitFor(()=>expect(posts('/execute')).toHaveLength(1));const original=task;task={...task,id:'other-task',resumeJob:undefined};mounted.rerender(<TaskHarness/>);task=original;mounted.rerender(<TaskHarness/>);await act(async()=>wait.resolve(json(jobReceipt('executed',saved!))));expect(screen.queryByAltText('本任务经摘要核对的图片候选')).toBeNull();expect(screen.queryByRole('region',{name:'媒体候选预览与审核'})).toBeNull();expect(posts('/review')).toHaveLength(0);
});
it('UNKNOWN only permits explicit original read/reconcile without retrying composite dispatch',async()=>{
 await hook();await queued();job={...job!,version:2,status:'UNKNOWN'};await act(async()=>state.openJob(job!));await act(async()=>{await state.inspectExecution();await state.action('execute');await state.action('reconcile');await state.action('execute');});expect(state.selected?.status).toBe('UNKNOWN');expect(posts('/execute')).toHaveLength(0);expect(posts('/reconcile')).toHaveLength(1);expect(posts('/jobs')).toHaveLength(1);
});
it.each(['size','sha256'] as const)('refuses private PNG %s mismatch before review',async mode=>{
 await hook();await queued();await ready();await act(async()=>state.action('execute'));candidateBytes=mode==='size'?bytes.slice(0,-1):new Uint8Array(bytes);if(mode==='sha256')candidateBytes[candidateBytes.length-1]^=1;await act(async()=>state.loadCandidate());expect(state.candidate).toBeUndefined();expect(state.canAction('review')).toBe(false);expect(URL.createObjectURL).not.toHaveBeenCalled();expect(posts('/review')).toHaveLength(0);
});
it('consumes local EXECUTE proof inside the original dispatch lease and rejects a changed second pin while waiting',async()=>{
 const lease=deferred<void>();let authorizeSaved:(()=>void)|undefined;props.cutoutExecution={execute:vi.fn(async(row:ProductionJob,authorize:()=>void)=>{authorizeSaved=authorize;await lease.promise;authorize();return props.client.execute(row);}),control:vi.fn()};await hook();await queued();await ready();let sending!:Promise<void>;act(()=>{sending=state.action('execute');});await waitFor(()=>expect(props.cutoutExecution!.execute).toHaveBeenCalledTimes(1));props.assets[1].version++;await act(async()=>{lease.resolve();await sending;});expect(authorizeSaved).toBeTypeOf('function');expect(posts('/execute')).toHaveLength(0);expect(()=>authorizeSaved!()).toThrow();
});
function originalCanvas():CanvasViewRecord{return{project_id:project,scope:binding().scope,id:binding().canvas_id,version:1,definition_digest:binding().canvas_digest,created_at:'2026-10-21T00:00:00Z',updated_at:'2026-10-21T00:00:00Z',execution_authority:false,binary_content_verified:false,capacity:{history_used:0,record_bytes:1000},reference_states:[{card_id:'original-card',state:'CURRENT_METADATA',filename:'source.png'},{card_id:'other-card',state:'CURRENT_METADATA',filename:'source.png'}],definition:{schema_version:1,title:'Saved composite target',viewport:{x:12,y:24,zoom:1},cards:[{id:'original-card',position:{x:44,y:66},asset:clone(task.origin.source)},{id:'other-card',position:{x:400,y:100},asset:clone(task.origin.source)}],groups:[{id:'original-group',name:'Saved group',card_ids:['original-card'],collapsed:false}]}};}
async function returning(stale=false){
 const view=await hook();await queued();await ready();await act(async()=>state.action('execute'));await act(async()=>state.loadCandidate());act(()=>state.confirmReview(true));await act(async()=>state.action('review'));const approved=clone(state.selected!);expect(approved.status).toBe('APPROVED');view.unmount();const canvas=originalCanvas(),original=clone(canvas),adopt=vi.fn(),complete=vi.fn(),uncertain=vi.fn(),prior=fetcher.getMockImplementation()!,path=`/api/projects/${project}/studio/canvas-views/${canvas.id}`;
 const formal:StudioAsset={...props.assets[0],id:approved.output_candidate!.id,version:approved.approved_asset_version!,sha256:approved.output_candidate!.digest,size:bytes.length,filename:'approved-composite.png'};if(stale)canvas.version=2;
 fetcher.mockImplementation(async(url:string,init:RequestInit={})=>{
  if(url.endsWith('/assets/'+formal.id))return json(formal);
  if(url===path+'/history')return json({project_id:project,scope:canvas.scope,id:canvas.id,incarnation:binding().incarnation,current_version:canvas.version,current_definition_digest:canvas.definition_digest,items:Array.from({length:canvas.version},(_,i)=>({version:i+1,definition_digest:canvas.definition_digest,definition:canvas.definition,created_at:canvas.created_at,updated_at:canvas.updated_at,reference_states:canvas.reference_states,can_restore:i+1<canvas.version})),restore_policy:'CURRENT_METADATA_ONLY',execution_authority:false,binary_content_verified:false});
  if(url===path&&init.method==='PUT'){const body=JSON.parse(String(init.body));expect(body.expected_version).toBe(1);expect(body.expected_incarnation).toBe(binding().incarnation);expect(body.expected_definition_digest).toBe(binding().canvas_digest);expect(body.expected_card).toEqual({card_id:'original-card',source:task.origin.source});Object.assign(canvas,{version:2,definition:body.definition,definition_digest:'f'.repeat(64)});return json(canvas);}
  if(url===path)return json(canvas);return prior(url,init);
 });
 render(<CanvasImageTaskReturn task={task} approved={approved} client={studioClient(project,{sessionToken:''})} production={props.client} disabled={false} canMutate isCurrent={()=>true} read={f=>f()} mutate={f=>f()} onAdopt={adopt} onComplete={complete} onUncertain={uncertain}/>);return{canvas,original,adopt,complete,uncertain,path};
}
it('original Return component explicitly adopts reviewed composite with captured CAS and retains original coordinates/groups/other cards',async()=>{
 const v=await returning();expect(v.adopt).not.toHaveBeenCalled();click('核验原位置与正式审核结果');fireEvent.click(await screen.findByLabelText('确认只采用到上述原卡片'));click('确认采用并回填原卡片');await waitFor(()=>expect(v.complete).toHaveBeenCalledTimes(1));expect(v.adopt).toHaveBeenCalledTimes(1);expect(v.uncertain).not.toHaveBeenCalled();expect(v.canvas.version).toBe(2);expect(v.canvas.definition.cards[0].asset).toEqual({asset_id:job!.output_candidate!.id,version:job!.approved_asset_version,digest:job!.output_candidate!.digest,kind:'image'});expect(v.canvas.definition.cards[0].position).toEqual(v.original.definition.cards[0].position);expect(v.canvas.definition.cards[1]).toEqual(v.original.definition.cards[1]);expect(v.canvas.definition.groups).toEqual(v.original.definition.groups);expect(fetcher.mock.calls.filter(([url,init])=>url===v.path&&init.method==='PUT')).toHaveLength(1);
});
it('original Return refuses changed canvas versions and preserves formal output without writing a guessed target',async()=>{
 const v=await returning(true);click('核验原位置与正式审核结果');await screen.findByText('原画布、卡片或素材版本已改变；不会回填当前选中的其他位置。');expect(screen.queryByLabelText('确认只采用到上述原卡片')).toBeNull();expect(v.adopt).not.toHaveBeenCalled();expect(fetcher.mock.calls.filter(([url,init])=>url===v.path&&init.method==='PUT')).toHaveLength(0);expect(job!.status).toBe('APPROVED');
});
