// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { blankGraph, connectionIssue } from './graphDraft';
import { checkedStudioGraphDraft } from './studioGraphClient';
import { checkedStoryboardReceipt } from './studioStoryboardContract';
import { buildStoryboardVideoBranches } from './graphStoryboardStarter';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import type { StudioClient } from './studioClient';
import { GraphStoryboardStarter } from './GraphStoryboardStarter';
import type { StudioGraphCatalog } from './studioGraphTypes';
import catalogJson from './fixtures/phase5.capture.video-catalog.json';
import receiptJson from './fixtures/phase5.capture.storyboard-video-approved.json';
const catalog=catalogJson as unknown as StudioGraphCatalog;
const {video_result: _video, ...shotTemplate}=receiptJson.shots[0];
const receipt=checkedStoryboardReceipt({...receiptJson,shots:Array.from({length:5},(_,i)=>({...shotTemplate,shot_id:`shot-${i+1}`,shot:{...receiptJson.shots[0].shot,id:`shot-${i+1}`,number:i+1,continuity:{characters:"",outfit:"",environment:"",camera:""}}}))});
const empty=()=>({...blankGraph(),schema_version:5 as const});
const ids=receipt.shots.map(row=>row.shot_id);
const button=()=>screen.getByRole('button',{name:'应用分镜视频链到本地空图'});
const handler=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
function select(values:string[]){const input=screen.getByLabelText('起步分镜镜头') as HTMLSelectElement;for(const option of input.options)option.selected=values.includes(option.value);fireEvent.change(input);}
afterEach(cleanup);
it.each([1,2,4])('assembles %i explicit ordered branches with exact pins and unchanged input',count=>{
 const draft=empty(),before=structuredClone(draft),source=structuredClone(receipt);let sequence=0;
 const next=buildStoryboardVideoBranches(draft,catalog,receipt,ids.slice(0,count).reverse(),prefix=>`${prefix}-${++sequence}`);
 expect(next.nodes).toHaveLength(1+3*count);expect(next.edges).toHaveLength(3*count);
 expect(new Set([...next.nodes,...next.edges].map(row=>row.id)).size).toBe(1+6*count);
 expect(next.nodes[0].parameters.document_snapshot).toEqual(receipt.document_snapshot);
 expect(next.nodes.filter(row=>row.definition_id==='storyboard_shot').map(row=>row.parameters)).toEqual(receipt.shots.slice(0,count).map(({shot_id,shot_version,shot_digest})=>({shot_id,shot_version,shot_digest})));
 for(const node of next.nodes.filter(row=>row.definition_id==='video_generate'))expect(node.parameters).toMatchObject({provider_id:'',model_id:'',allow_cloud:false,bind_shot:true});
 for(const edge of next.edges)expect(connectionIssue({...next,edges:next.edges.filter(row=>row!==edge)},catalog.definitions,edge)).toBeUndefined();
 expect(next.nodes.filter(row=>row.definition_id==='media_review')).toHaveLength(count);
 expect(()=>checkedStudioGraphDraft(next)).toThrow();
 const configured=structuredClone(next);for(const node of configured.nodes.filter(row=>row.definition_id==='video_generate'))Object.assign(node.parameters,{provider_id:'fixture-provider',model_id:'fixture-model'});
 expect(checkedStudioGraphDraft(configured).nodes).toHaveLength(1+3*count);
 expect(draft).toEqual(before);expect(receipt).toEqual(source);
});
it.each([[],['shot-1','shot-1'],['missing'],ids].map(selection=>({selection})))('rejects invalid selections without mutation: $selection',({selection})=>{
 const draft=empty(),before=structuredClone(draft);expect(()=>buildStoryboardVideoBranches(draft,catalog,receipt,selection)).toThrow();expect(draft).toEqual(before);
});
it('rejects edge ID collisions as well as node collisions',()=>{
 let i=0;expect(()=>buildStoryboardVideoBranches(empty(),catalog,receipt,ids.slice(0,2),prefix=>prefix==='edge'?'edge':`${prefix}-${++i}`)).toThrow(/标识重复/);
 i=0;expect(()=>buildStoryboardVideoBranches(empty(),catalog,receipt,ids.slice(0,2),prefix=>prefix==='edge'?'storyboard-1':`${prefix}-${++i}`)).toThrow(/标识重复/);
});
async function setup(){
 const props={scope:{},disabled:false,loading:false,documents:[{...receipt.document_snapshot,title:'Original',mode:'STORYBOARD' as const}],onLoad:vi.fn(async()=>{}),onRead:vi.fn(async()=>receipt),onApply:vi.fn(()=>true)};
 const view=render(<GraphStoryboardStarter {...props}/>);
 fireEvent.change(screen.getByLabelText('起步来源分镜'),{target:{value:receipt.document_snapshot.id}});fireEvent.click(screen.getByRole('button',{name:'核对起步分镜镜头与审核'}));await screen.findByLabelText('起步分镜精确来源');return {props,view};
}
it('previews four exact pins and configuration warning, refuses five without truncating, and consumes once',async()=>{
 const {props}=await setup();select(ids.slice(0,4));const preview=screen.getByLabelText('分镜视频链应用预览');expect(preview.textContent).toContain('13 个节点 · 12 条连线 · 4 个视频生成器');expect(preview.textContent).toContain('仍需配置服务商和模型');expect(within(preview).getAllByRole('listitem')).toHaveLength(4);for(const shot of receipt.shots.slice(0,4))expect(preview.textContent).toContain(shot.shot_digest);
 const old=handler(button());select(ids);expect((button() as HTMLButtonElement).disabled).toBe(true);expect(screen.getByText(/超过 4 个镜头/)).toBeTruthy();act(()=>old());expect(props.onApply).not.toHaveBeenCalled();
 select(ids.slice(0,4));act(()=>old());expect(props.onApply).not.toHaveBeenCalled();const apply=handler(button());act(()=>{apply();apply();});expect(props.onApply).toHaveBeenCalledTimes(1);expect(props.onApply).toHaveBeenCalledWith(receipt,ids.slice(0,4),props.scope);expect(props.onRead).toHaveBeenCalledTimes(1);expect(props.onLoad).not.toHaveBeenCalled();
});
it.each(['scope','documents','disabled','loading'] as const)('rejects multishot authority ABA for %s',async key=>{
 const {props,view}=await setup();select(ids.slice(0,4));const apply=handler(button());view.rerender(<GraphStoryboardStarter {...props} {...(key==='scope'?{scope:{}}:key==='documents'?{documents:[...props.documents]}:key==='disabled'?{disabled:true}:{loading:true})}/>);view.rerender(<GraphStoryboardStarter {...props}/>);act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();expect(screen.queryByLabelText('分镜视频链应用预览')).toBeNull();
});
it('rejects retained multishot apply after unmount',async()=>{const {props,view}=await setup();select(ids.slice(0,4));const apply=handler(button());view.unmount();act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();});

it.each([2,4])('assembles %i branches through the original controller in one undo/redo without automatic writes',async count=>{
 const documents=[{...receipt.document_snapshot,title:'Original storyboard',mode:'STORYBOARD' as const}];
 const button=(name:string)=>screen.getByRole('button',{name});
 const transport=vi.fn(),create=vi.fn(async(body:{definition:unknown})=>{checkedStudioGraphDraft(body.definition);return transport(body);}),createRun=vi.fn(),videoStoryboard=vi.fn(async()=>receipt);
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'starter-project',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),client:{graphs:{catalog:vi.fn(async()=>catalog),list:vi.fn(async()=>({items:[]})),videoCatalog:vi.fn(async()=>catalog),planningDocuments:vi.fn(async()=>({documents})),videoStoryboard,create,createRun}} as unknown as StudioClient};
 function Harness(){const controller=useStudioGraphEditorController(props);return studioGraphEditorView(controller,props).content;}
 render(<Harness/>);await screen.findByLabelText('确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务');
 fireEvent.click(button('明确读取视频图节点目录'));
 await act(async()=>{});
 fireEvent.click(screen.getByLabelText('确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务'));
 fireEvent.click(button('明确采用视频图 v5'));
 await screen.findByLabelText('分镜到视频起步方案');fireEvent.click(button('读取起步分镜目录'));
 await within(screen.getByLabelText('起步来源分镜')).findByRole('option',{name:'Original storyboard · v5'});fireEvent.change(screen.getByLabelText('起步来源分镜'),{target:{value:receipt.document_snapshot.id}});fireEvent.click(button('核对起步分镜镜头与审核'));await screen.findByLabelText('起步分镜精确来源');select(ids.slice(0,count));
 fireEvent.click(button('应用分镜视频链到本地空图'));
 expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(1+3*count);
 expect(create).not.toHaveBeenCalled();expect(createRun).not.toHaveBeenCalled();
 fireEvent.click(button('撤销图编辑'));expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);
 fireEvent.click(button('重做图编辑'));expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(1+3*count);
 fireEvent.click(button('保存创作图'));await act(async()=>{});expect(create).toHaveBeenCalledTimes(1);expect(transport).not.toHaveBeenCalled();
 expect(createRun).not.toHaveBeenCalled();expect(videoStoryboard).toHaveBeenCalledTimes(1);
});
it('rejects DOM selection drift before React receives a change event',async()=>{
 const {props}=await setup();select(ids.slice(0,4));const apply=handler(button());const input=screen.getByLabelText('起步分镜镜头') as HTMLSelectElement;input.options[4].selected=true;act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();
});
it('requires an explicit subset from a larger board; no initial selection or silent truncation',async()=>{
 const {props}=await setup();const input=screen.getByLabelText('起步分镜镜头') as HTMLSelectElement;expect(input.options).toHaveLength(5);expect(input.selectedOptions).toHaveLength(0);expect((button() as HTMLButtonElement).disabled).toBe(true);expect(screen.queryByLabelText('分镜视频链应用预览')).toBeNull();select([ids[4],ids[1]]);fireEvent.click(button());expect(props.onApply).toHaveBeenCalledWith(receipt,[ids[1],ids[4]],props.scope);
});
