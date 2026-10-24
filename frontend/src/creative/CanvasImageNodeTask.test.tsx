// @vitest-environment jsdom
/** Software owner projections only; no File approval, provider or media work. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { webcrypto } from 'node:crypto';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CanvasImageNodeTask, type CanvasImageNodeTaskProps } from './CanvasImageNodeTask';
import { assertSavedImageNode, checkedCanvasImageNodeBinding, imageNodePromptDigest, type CanvasImageNodeBinding } from './canvasImageNode';
import { checkedCanvasDefinition, type CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { ProductionJob } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
let panel:StudioMediaExecutionProps;
vi.mock('./StudioMediaExecutionPanel',()=>({StudioMediaExecutionPanel:(props:StudioMediaExecutionProps)=>{panel=props;return <p>Original production panel fixture</p>;}}));
const inc='file:12345678-1234-1234-1234-123456789abc', hash='a'.repeat(64), jobHash='b'.repeat(64), assetHash='c'.repeat(64);
const node={id:'image_node_1',title:'One node',prompt:'Bound prompt',x:40,y:80};
function retained(button:HTMLElement){const key=Object.keys(button).find(k=>k.startsWith('__reactProps$'))!;return (button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;}
function fixture(){
 const canvas={project_id:'p',scope:{mode:'local',novel_id:'p'},id:'canvas1',version:1,definition_digest:hash,
 definition:{schema_version:1,title:node.title,cards:[],viewport:{x:0,y:0,zoom:1}},reference_states:[],created_at:'now',updated_at:'now',
 execution_authority:false,binary_content_verified:false,capacity:{history_used:0,record_bytes:512}} as CanvasViewRecord;
 const owner={projectId:'p',incarnation:inc,actorId:'host',actorWorkspaceId:'',mode:'local',workspaceId:'',storylineId:'',branchId:''} as const;
 const views={create:vi.fn(async(..._args:unknown[])=>canvas),get:vi.fn(async()=>canvas),history:vi.fn(async()=>({incarnation:inc,current_version:1,current_definition_digest:hash})),imageNodeResult:vi.fn()};
 const production={get:vi.fn(),list:vi.fn(async():Promise<ProductionJob[]>=>[])};
 const asset={id:'asset1',novel_id:'p',branch_id:null,kind:'image',version:2,sha256:assetHash,filename:'formal-software-fixture.png'} as StudioAsset;
 const client={overview:vi.fn(async()=>({project:{id:'p',incarnation:inc},capabilities:{can_mutate:true}})),graphs:{canvasViews:views},asset:vi.fn(async()=>asset)};
 const props={projectId:'p',node,owner,client,production,canMutate:true,canReview:true,isCurrent:()=>true,read:async<T,>(f:()=>Promise<T>)=>f(),mutate:async<T,>(f:()=>Promise<T>)=>f()} as unknown as CanvasImageNodeTaskProps;
 return {props,canvas,views,production,client,asset};
}
function approved(binding:CanvasImageNodeBinding):ProductionJob{return {id:'job1',owner:'image',novel_id:'p',branch_id:null,version:4,status:'APPROVED',request_digest:jobHash,
 operation_id:'m5.image.t2i',sources:[],provider:{local:true},output_candidate:{id:'asset1',version:1,digest:assetHash,kind:'image'},approved_asset_version:2,
 command:{operation_id:'m5.image.t2i',prompt:node.prompt,source_snapshots:[],allow_cloud:false,canvas_image_node:binding}} as unknown as ProductionJob;}
function saved(e:ReturnType<typeof fixture>,binding:CanvasImageNodeBinding,job:ProductionJob):CanvasViewRecord{return {...e.canvas,version:2,definition_digest:'d'.repeat(64),
 definition:{...e.canvas.definition,cards:[{id:node.id,position:{x:node.x,y:node.y},asset:{asset_id:e.asset.id,version:e.asset.version,digest:e.asset.sha256,kind:'image'}}],
 image_node_origin:{contract:'studio-canvas-image-node-result/1',target:binding,job_id:job.id,job_version:job.version,job_request_digest:job.request_digest,asset:{asset_id:e.asset.id,version:e.asset.version,digest:e.asset.sha256,kind:'image'}}},
 reference_states:[{card_id:node.id,state:'CURRENT_METADATA',filename:e.asset.filename}]};}
async function prepare(e:ReturnType<typeof fixture>){fireEvent.click(screen.getByRole('button',{name:'为此节点保存正式空白位置'}));await waitFor(()=>expect(e.views.create).toHaveBeenCalledOnce());await screen.findByText('Original production panel fixture');return panel.canvasNodeTask!.binding;}
async function offerApproved(e:ReturnType<typeof fixture>,binding:CanvasImageNodeBinding){const job=approved(binding);e.production.get.mockResolvedValue(job);act(()=>panel.onJob?.(job));return job;}
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);});afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

describe('formal one-node software contract',()=>{
 it('allows explicit preparation after StrictMode setup replay without an automatic write',async()=>{
  const e=fixture();render(<StrictMode><CanvasImageNodeTask {...e.props}/></StrictMode>);expect(e.views.create).not.toHaveBeenCalled();await prepare(e);expect(e.views.create).toHaveBeenCalledOnce();
 });
 it('performs no write on mount and explicit prepare saves only an empty original view',async()=>{
  const e=fixture();render(<CanvasImageNodeTask {...e.props}/>);expect(e.views.create).not.toHaveBeenCalled();const old=retained(screen.getByRole('button',{name:'为此节点保存正式空白位置'}));
  const binding=await prepare(e);expect(binding.node_id).toBe(node.id);expect(binding.prompt_digest).toBe(await imageNodePromptDigest(node.prompt));expect((e.views.create.mock.calls[0][0] as {cards:unknown[]}).cards).toEqual([]);
  act(()=>old());await act(async()=>{});expect(e.views.create).toHaveBeenCalledOnce();expect(panel.canvasNodeTask?.initialPrompt).toBe(node.prompt);
 });
 it('separates original APPROVED projection, metadata inspection, explicit consent and one-node save',async()=>{
  const e=fixture();render(<CanvasImageNodeTask {...e.props}/>);const binding=await prepare(e),job=await offerApproved(e,binding);const result=saved(e,binding,job);e.views.imageNodeResult.mockResolvedValue(result);
  expect(e.views.imageNodeResult).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'核对正式结果与原节点位置'}));await screen.findByRole('checkbox',{name:'确认采用此正式资产到原节点位置'});
  expect(e.views.imageNodeResult).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByRole('button',{name:'确认采用并保存节点位置'}));await screen.findByLabelText('服务端节点资产关联');
  expect(e.views.imageNodeResult).toHaveBeenCalledOnce();expect(e.views.imageNodeResult.mock.calls[0].slice(1)).toEqual([inc,job,result.definition.image_node_origin!.asset]);
 });
 it('keeps an unknown adoption outcome read-only and retires retained apply callbacks',async()=>{
  const e=fixture();render(<CanvasImageNodeTask {...e.props}/>);const binding=await prepare(e);await offerApproved(e,binding);e.views.imageNodeResult.mockRejectedValue(new Error('ack lost'));
  fireEvent.click(screen.getByRole('button',{name:'核对正式结果与原节点位置'}));await screen.findByRole('checkbox');fireEvent.click(screen.getByRole('checkbox'));
  const old=retained(screen.getByRole('button',{name:'确认采用并保存节点位置'}));act(()=>old());await screen.findByText(/节点采用结果待核对/);act(()=>old());await act(async()=>{});
  expect(e.views.imageNodeResult).toHaveBeenCalledOnce();expect(screen.queryByLabelText('服务端节点资产关联')).toBeNull();
 });
 it('does not dispatch a deferred create after permission retirement',async()=>{
  const e=fixture();let deferred:(()=>Promise<unknown>)|undefined;e.props.mutate=vi.fn(async f=>{deferred=f;return new Promise<never>(()=>{});});const view=render(<CanvasImageNodeTask {...e.props}/>);
  fireEvent.click(screen.getByRole('button',{name:'为此节点保存正式空白位置'}));await waitFor(()=>expect(deferred).toBeDefined());view.rerender(<CanvasImageNodeTask {...e.props} canMutate={false}/>);
  expect(()=>deferred!()).toThrow();expect(e.views.create).not.toHaveBeenCalled();
 });
 it('does not revive retained preparation after node A/B/A',async()=>{
  const e=fixture(),view=render(<CanvasImageNodeTask {...e.props}/>);const old=retained(screen.getByRole('button',{name:'为此节点保存正式空白位置'}));view.rerender(<CanvasImageNodeTask {...e.props} node={{...node,prompt:'changed'}}/>);view.rerender(<CanvasImageNodeTask {...e.props}/>);
  act(()=>old());await act(async()=>{});expect(e.views.create).not.toHaveBeenCalled();
 });
 it('reads a saved moved card after cold remount, requires explicit record selection and sends no mutation',async()=>{
  const e=fixture();const target=checkedCanvasImageNodeBinding({contract:'studio-canvas-image-node/1',project_id:'p',scope:e.canvas.scope,incarnation:inc,canvas_id:e.canvas.id,canvas_version:1,canvas_digest:hash,
   node_id:node.id,title:node.title,position:{x:node.x,y:node.y},prompt_digest:await imageNodePromptDigest(node.prompt)}),job=approved(target),record=saved(e,target,job);
  record.definition.cards[0].position.x=200;e.production.list.mockResolvedValue([job]);e.production.get.mockResolvedValue(job);e.views.get.mockResolvedValue(record);e.views.history.mockResolvedValue({incarnation:inc,current_version:2,current_definition_digest:record.definition_digest});
  render(<CanvasImageNodeTask {...e.props}/>);fireEvent.click(screen.getByRole('button',{name:'读取此节点已保存位置与任务'}));await screen.findByRole('button',{name:/查看已保存节点位置/});expect(screen.queryByLabelText('服务端节点资产关联')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:/查看已保存节点位置/}));await screen.findByLabelText('服务端节点资产关联');expect(screen.getByText('{"x":200,"y":80}')).toBeTruthy();expect(e.views.create).not.toHaveBeenCalled();expect(e.views.imageNodeResult).not.toHaveBeenCalled();
 });
 it('rejects origin/card mismatches and distinguishes initial placement from later display moves',async()=>{
  const e=fixture();const target=checkedCanvasImageNodeBinding({contract:'studio-canvas-image-node/1',project_id:'p',scope:e.canvas.scope,incarnation:inc,canvas_id:e.canvas.id,canvas_version:1,canvas_digest:hash,
   node_id:node.id,title:node.title,position:{x:node.x,y:node.y},prompt_digest:await imageNodePromptDigest(node.prompt)}),record=saved(e,target,approved(target));
  expect(checkedCanvasDefinition(record.definition)).toEqual(record.definition);record.definition.cards[0].position.x=200;expect(()=>assertSavedImageNode(record,target)).not.toThrow();expect(()=>assertSavedImageNode(record,target,undefined,undefined,true)).toThrow();
  record.definition.cards[0].asset!.digest='f'.repeat(64);expect(()=>checkedCanvasDefinition(record.definition)).toThrow();
 });
});
