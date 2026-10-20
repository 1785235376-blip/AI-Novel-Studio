// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {createHash,webcrypto} from 'node:crypto';
import fixture from '../../../tests/fixtures/studio_dual_canvas_loop.json';
import {executionImpactSnapshot,fingerprintExecutionImpact} from '../experimental/executionImpact/executionImpact';
import {ExecutionImpactPanel} from '../experimental/executionImpact/ExecutionImpactPanel';
import {mediaProviderKey,useStudioMediaExecution,type StudioMediaExecutionController,type StudioMediaExecutionProps} from './useStudioMediaExecution';
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
  canvasImageTask:{source:binding.source,returnBinding:binding,isCurrent:()=>true}};
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/providers'))return json(fixture.providers);
  if(url.endsWith('/preview'))return json(receipt('preview',body.request_id));
  if(url.endsWith('/jobs')&&init.method==='POST')return json(receipt('queued',body.command.request_id));
  if(url.endsWith('/execute'))return json(receipt('executed',lastRequest));
  throw new Error('Unexpected real owner request '+(init.method||'GET')+' '+url);
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const count=(suffix:string)=>fetcher.mock.calls.filter(([url,init])=>url.endsWith(suffix)&&init.method==='POST').length;
async function draft(){
 const view=render(<Harness/>);await waitFor(()=>expect(state.providers.length).toBeGreaterThan(0));
 const provider=state.providers.find(row=>row.operation_id==='m5.image.i2i')!;
 act(()=>{state.changeField('providerKey',mediaProviderKey(provider));state.changeField('prompt',fixture.command.prompt);
  state.changeField('licenseNote',fixture.command.license_note);state.changeParameter('steps','33');state.changeParameter('seed','100');state.changeParameter('denoising_strength','0.6');});
 return view;
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
it.each(['prompt','parameters','provider','pin','scope'])('retires a confirmed create after %s A/B/A and requires a new preview request',async mode=>{
 const view=await draft();await preview();await confirm('CREATE');const old=state.impact!,oldCreate=state.create;
 if(mode==='prompt'){act(()=>state.changeField('prompt','other'));act(()=>state.changeField('prompt',fixture.command.prompt));}
 if(mode==='parameters'){act(()=>state.changeParameter('steps','34'));act(()=>state.changeParameter('steps','33'));}
 if(mode==='provider'){const value=state.draft.providerKey;act(()=>state.changeField('providerKey',''));act(()=>state.changeField('providerKey',value));}
 if(mode==='pin'){const value=props.assets[0].version;props.assets[0].version++;await act(async()=>oldCreate());props.assets[0].version=value;}
 if(mode==='scope'){const value=props.canvasImageTask!.returnBinding!.incarnation;props.canvasImageTask!.returnBinding!.incarnation='file:00000000-0000-0000-0000-000000000001';await act(async()=>oldCreate());props.canvasImageTask!.returnBinding!.incarnation=value;}
 await act(async()=>oldCreate());expect(count('/jobs')).toBe(0);expect(old.current()).toBe(false);
 lastRequest='new-request-'+mode;view.rerender(<Harness/>);await preview();await confirm('CREATE');await act(async()=>state.create());expect(count('/jobs')).toBe(1);
 const body=JSON.parse(String(fetcher.mock.calls.find(([url,init])=>url.endsWith('/jobs')&&init.method==='POST')![1].body));expect(body.command.request_id).toBe(lastRequest);
});
it.each(['version','model','recipe','preview'])('retires execute after observed in-place %s A/B/A without rerender',async mode=>{
 await queued();await confirm('EXECUTE');const old=state.impact!,job=state.selected!,value=structuredClone(job),originalPreview=structuredClone(old.input.preview);
 if(mode==='version')job.version++;
 if(mode==='model')job.command!.model_id='other-model';
 if(mode==='recipe')job.execution_recipe.recipe_digest='e'.repeat(64);
 if(mode==='preview')old.input.preview.preview_digest='e'.repeat(64);
 await act(async()=>state.action('execute'));Object.assign(job,value);Object.assign(old.input.preview,originalPreview);
 await act(async()=>state.action('execute'));expect(count('/execute')).toBe(0);expect(old.current()).toBe(false);
});
it.each(['CREATE','EXECUTE'] as const)('rechecks and consumes %s inside the original delayed mutation callback after task removal',async kind=>{
 const view=kind==='CREATE'?await draft():await queued();if(kind==='CREATE')await preview();await confirm(kind);
 let reject!:(reason:unknown)=>void,invoke!:()=>Promise<unknown>;
 props.mutate=work=>new Promise<any>((_resolve,no)=>{reject=no;invoke=work;});view.rerender(<Harness/>);
 let pending!:Promise<void>;act(()=>{pending=kind==='CREATE'?state.create():state.action('execute');});await waitFor(()=>expect(invoke).toBeTypeOf('function'));
 props.canvasImageTask=undefined;view.rerender(<Harness/>);const before=count(kind==='CREATE'?'/jobs':'/execute');
 await act(async()=>{try{await Promise.resolve().then(invoke);throw new Error('Expected a retired boundary');}catch(reason){expect(reason).toMatchObject({problem:{code:'STUDIO_EXECUTION_IMPACT_RETIRED'}});reject(reason);}await pending;});
 expect(count(kind==='CREATE'?'/jobs':'/execute')).toBe(before);
});
it('retires a delayed confirmation and callback across client A/B/A and never dispatches through either client',async()=>{
 const view=await queued();await confirm('EXECUTE');const old=state.impact!,client=props.client;
 props.client=studioProductionClient(fixture.project,{sessionToken:''});view.rerender(<Harness/>);props.client=client;view.rerender(<Harness/>);
 await act(async()=>state.action('execute'));expect(old.current()).toBe(false);expect(count('/execute')).toBe(0);
});
it('keeps UNKNOWN non-dispatchable after an ambiguous send and never reuses consumed confirmation',async()=>{
 await queued();await confirm('EXECUTE');const execute=fetcher.getMockImplementation()!;
 fetcher.mockImplementation((url,init)=>url.endsWith('/execute')?Promise.reject(new TypeError('synthetic ambiguous transport')):execute(url,init));
 await act(async()=>state.action('execute'));expect(state.uncertain).toBe(true);expect(state.canAction('execute')).toBe(false);
 await act(async()=>state.action('execute'));expect(count('/execute')).toBe(1);expect(count('/jobs')).toBe(1);
});

it('rejects a forged proof with the correct SHA passed directly to the original confirmation owner',async()=>{
 await draft();await preview();const gate=state.impact!,inputFingerprint=await fingerprintExecutionImpact(executionImpactSnapshot(gate.input));
 await act(async()=>state.confirmImpact(gate,{contract:'studio-execution-impact-confirmation/1',scope:'TASK',inputFingerprint,isCurrent:()=>true}));
 await act(async()=>state.create());expect(state.canCreate).toBe(false);expect(count('/jobs')).toBe(0);expect(count('/execute')).toBe(0);
});
it('retires proof when an original client method is replaced in place, before invoking that method',async()=>{
 await queued();await confirm('EXECUTE');const original=props.client.execute,replacement=vi.fn(original);
 props.client.execute=replacement;await act(async()=>state.action('execute'));props.client.execute=original;await act(async()=>state.action('execute'));
 expect(replacement).not.toHaveBeenCalled();expect(count('/execute')).toBe(0);
});

it('re-reads an existing queued request preview explicitly without creating another Job, then requires execute confirmation',async()=>{
 props.externalJob=receipt('queued',lastRequest);render(<Harness/>);await waitFor(()=>expect(state.selected?.status).toBe('QUEUED'));
 expect(state.impact).toBeUndefined();await act(async()=>state.action('execute'));expect(count('/execute')).toBe(0);
 await act(async()=>state.inspectExecution());expect(count('/preview')).toBe(1);expect(count('/jobs')).toBe(0);expect(count('/execute')).toBe(0);
 await confirm('EXECUTE');await act(async()=>state.action('execute'));expect(count('/execute')).toBe(1);expect(count('/jobs')).toBe(0);
});
it('preserves the existing unbound media owner API and execute path',async()=>{
 props.canvasImageTask=undefined;props.externalJob=receipt('queued',lastRequest);delete props.externalJob!.command!.canvas_return;render(<Harness/>);await waitFor(()=>expect(state.selected?.status).toBe('QUEUED'));
 expect(state.impact).toBeUndefined();await act(async()=>state.action('execute'));expect(count('/execute')).toBe(1);expect(count('/preview')).toBe(0);
});

it('keeps a bound queued Job gated when its host task prop is removed instead of falling back to the unbound API',async()=>{
 const view=await queued();await confirm('EXECUTE');props.canvasImageTask=undefined;view.rerender(<Harness/>);
 await act(async()=>state.action('execute'));expect(count('/execute')).toBe(0);expect(state.canAction('execute')).toBe(false);
});

it('does not create or execute a replacement request while the bound original Job is UNKNOWN',async()=>{
 await draft();props.externalJob={...receipt('queued',lastRequest),status:'UNKNOWN'} as ProductionJob;
 // Receive through the original externalJob owner path, not an invented status flag.
 cleanup();render(<Harness/>);await waitFor(()=>expect(state.selected?.status).toBe('UNKNOWN'));await waitFor(()=>expect(state.providers.length).toBeGreaterThan(0));
 act(()=>{state.changeField('providerKey',mediaProviderKey(state.providers.find(row=>row.operation_id==='m5.image.i2i')!));state.changeField('prompt',fixture.command.prompt);
 state.changeField('licenseNote',fixture.command.license_note);state.changeParameter('steps','33');state.changeParameter('seed','100');state.changeParameter('denoising_strength','0.6');});
 lastRequest='new-request-while-unknown';await preview();await act(async()=>{await state.create();await state.action('execute');});
 expect(state.canCreate).toBe(false);expect(count('/jobs')).toBe(0);expect(count('/execute')).toBe(0);
});
