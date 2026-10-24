// @vitest-environment jsdom
/** Declared software HTTP projections through the real production client/panel.
 * No provider, binary candidate, File approval, inspection or accept is invoked. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createHash, webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type MediaCommand, type ProductionJob, type ProductionProvider } from './studioProductionClient';
import type { StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { CanvasImageNodeBinding } from './canvasImageNode';
const prompt='A single explicitly bound software node';
const sha=(v:string)=>createHash('sha256').update(v).digest('hex');
const target:CanvasImageNodeBinding={contract:'studio-canvas-image-node/1',project_id:'node-project',scope:{mode:'local',novel_id:'node-project'},
 incarnation:'file:12345678-1234-1234-1234-123456789abc',canvas_id:'original-canvas',canvas_version:1,canvas_digest:'a'.repeat(64),
 node_id:'image_node',title:'Bound node',position:{x:40,y:80},prompt_digest:sha(prompt)};
const provider:ProductionProvider={operation_id:'m5.image.t2i',provider_id:'software-local-image',model_id:'software-model',local:true,route_digest:'b'.repeat(64),
 capability:'TEXT_TO_IMAGE',supported_parameters:['steps','seed'],readiness:'CONFIGURED_NOT_VERIFIED'};
const json=(v:unknown)=>new Response(JSON.stringify(v),{headers:{'Content-Type':'application/json'}});
let props:StudioMediaExecutionProps,fetcher:ReturnType<typeof vi.fn>,latest:MediaCommand|undefined;
const recipe=(command:MediaCommand)=>({contract:'studio-execution-recipe/1',operation_id:command.operation_id,adapter:'AUTOMATIC1111_IMAGE',
 parameters:command.parameters,automatic_fallback:false,recipe_digest:sha('software-recipe:'+JSON.stringify(command.parameters))});
function queued(command:MediaCommand):ProductionJob{return {contract:'studio-production-job/1',owner:'image',id:'original-software-job',novel_id:target.project_id,branch_id:null,
 version:1,status:'QUEUED',operation_id:command.operation_id,request_id:command.request_id,request_digest:sha(JSON.stringify(command)),receipt_digest:null,output_candidate:null,timeline_snapshot:null,sources:[],
 command,provider:{provider_id:provider.provider_id,model_id:provider.model_id,local:true,route_digest:provider.route_digest},execution_recipe:recipe(command),
 approved_asset_version:null,created_at:'2026-10-24T00:00:00Z',updated_at:'2026-10-24T00:00:00Z',product_acceptance:'LOCAL_REQUIRED',automatic_replay:false,remote_compute_may_continue:false} as ProductionJob;}
const count=(suffix:string)=>fetcher.mock.calls.filter(([url,init])=>url.endsWith(suffix)&&init?.method==='POST').length;
function retained(button:HTMLElement){const key=Object.keys(button).find(k=>k.startsWith('__reactProps$'))!;return (button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}
beforeEach(()=>{
 vi.stubGlobal('crypto',webcrypto);latest=undefined;
 props={client:studioProductionClient(target.project_id,{sessionToken:''}),assets:[],canvasNodeTask:{binding:structuredClone(target),initialPrompt:prompt,isCurrent:()=>true},
 canMutate:true,canReview:true,busy:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),onDirtyChange:vi.fn(),onUnavailable:vi.fn()};
 fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const body=init.body?JSON.parse(String(init.body)):undefined;
  if(url.endsWith('/providers'))return json({items:[provider,{...provider,provider_id:'software-cloud-image',local:false}],health_probed:false,credentials_read:false});
  if(url.endsWith('/preview')){latest=body;return json({contract:'studio-production-preview/1',novel_id:target.project_id,branch_id:null,operation_id:body.operation_id,
   request_id:body.request_id,request_digest:sha(JSON.stringify(body)),preview_digest:sha('preview:'+JSON.stringify(body)),command:body,
   provider:{provider_id:provider.provider_id,model_id:provider.model_id,local:true,route_digest:provider.route_digest},sources:[],execution_recipe:recipe(body),
   product_acceptance:'LOCAL_REQUIRED',execution_available:true,automatic_dispatch:false,output_policy:'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW'});}
  if(url.endsWith('/jobs')&&init.method==='POST'){latest=body.command;return json(queued(body.command));}
  if(url.endsWith('/jobs/image/original-software-job')&&latest)return json(queued(latest));
  throw new Error('Unexpected software request; execution/review/media are forbidden in this fixture');
 });vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
async function draft(){
 const view=render(<StudioMediaExecutionPanel {...props}/>);const picker=screen.getByLabelText('服务商与模型') as HTMLSelectElement;
 await waitFor(()=>expect(picker.options.length).toBe(2));expect(picker.textContent).not.toContain('software-cloud-image');
 fireEvent.change(picker,{target:{value:picker.options[1].value}});fireEvent.change(screen.getByLabelText('采样步数（1–150）'),{target:{value:'31'}});
 fireEvent.change(screen.getByLabelText('种子（0–2147483647）'),{target:{value:'71'}});return view;
}
async function preview(){fireEvent.click(screen.getByRole('button',{name:'读取制作预览'}));await screen.findByRole('region',{name:'制作预览确认'});
 fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));}
async function impact(){const check=screen.getByLabelText('已核对本次输入变化与影响范围') as HTMLInputElement;
 await waitFor(()=>expect(check.disabled).toBe(false));fireEvent.click(check);fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));
 await waitFor(()=>expect((screen.getByRole('button',{name:'仅创建任务并入队'}) as HTMLButtonElement).disabled).toBe(false));}

it('uses actual panel/client for locked node prompt, editable parameters, explicit preview+impact+queue and no automatic execution/review',async()=>{
 await draft();expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).disabled).toBe(true);expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe(prompt);
 expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(true);expect(screen.queryByLabelText('制作路线')).toBeNull();expect(count('/jobs')).toBe(0);
 await preview();const create=screen.getByRole('button',{name:'仅创建任务并入队'});expect((create as HTMLButtonElement).disabled).toBe(true);act(()=>retained(create)());expect(count('/jobs')).toBe(0);
 await impact();fireEvent.click(create);await screen.findByRole('button',{name:'明确执行当前入队任务'});await waitFor(()=>expect(count('/jobs')).toBe(1));
 const posted=JSON.parse(String(fetcher.mock.calls.find(([url,init])=>url.endsWith('/jobs')&&init.method==='POST')![1].body));
 expect(posted.command).toMatchObject({operation_id:'m5.image.t2i',prompt,parameters:{steps:31,seed:71},allow_cloud:false,source_snapshots:[],canvas_image_node:target});
 expect(posted.command.canvas_return).toBeUndefined();expect(count('/execute')).toBe(0);expect(count('/review')).toBe(0);
 expect((screen.getByRole('button',{name:'明确执行当前入队任务'}) as HTMLButtonElement).disabled).toBe(true);
});
it('retires a real-panel queue confirmation after parameter A/B/A without another POST',async()=>{
 await draft();await preview();await impact();const old=retained(screen.getByRole('button',{name:'仅创建任务并入队'}));
 fireEvent.change(screen.getByLabelText('采样步数（1–150）'),{target:{value:'32'}});fireEvent.change(screen.getByLabelText('采样步数（1–150）'),{target:{value:'31'}});
 await act(async()=>old());expect(count('/jobs')).toBe(0);expect(count('/execute')).toBe(0);expect(count('/review')).toBe(0);
});
it('refuses dispatch when a parsed node-bound Job is opened in the unbound original global panel',async()=>{
 latest={operation_id:'m5.image.t2i',request_id:'software-only-reopen',provider_id:provider.provider_id,model_id:provider.model_id,prompt,parameters:{steps:31,seed:71},source_snapshots:[],allow_cloud:false,license_note:'',canvas_image_node:target};
 const job=await props.client.get('image','original-software-job');props={...props,canvasNodeTask:undefined,externalJob:job};render(<StudioMediaExecutionPanel {...props}/>);
 const execute=await screen.findByRole('button',{name:'明确执行当前入队任务'});expect((execute as HTMLButtonElement).disabled).toBe(true);await act(async()=>retained(execute)());
 expect(count('/jobs')).toBe(0);expect(count('/execute')).toBe(0);expect(count('/review')).toBe(0);
});
