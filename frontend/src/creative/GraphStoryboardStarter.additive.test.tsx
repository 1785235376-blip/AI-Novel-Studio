// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { blankGraph, connectionIssue } from './graphDraft';
import { checkedStudioGraphDraft } from './studioGraphClient';
import { checkedStoryboardReceipt } from './studioStoryboardContract';
import { buildStoryboardVideoStarter } from './graphStoryboardStarterHelpers';
import { GraphStoryboardStarter } from './GraphStoryboardStarter';
import type { StudioGraphCatalog } from './studioGraphTypes';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import type { StudioClient } from './studioClient';
import type { PlanningDocument } from './studioProductionGraphContract';
import catalogJson from './fixtures/phase5.capture.video-catalog.json';
import receiptJson from './fixtures/phase5.capture.storyboard-video-approved.json';
const catalog=catalogJson as unknown as StudioGraphCatalog;
const receipt=checkedStoryboardReceipt(receiptJson);
const empty=()=>({...blankGraph(),schema_version:5 as const});
const documents:PlanningDocument[]=[{...receipt.document_snapshot,title:'Original storyboard',mode:'STORYBOARD'}];
const button=(name:string)=>screen.getByRole('button',{name});
const handler=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
afterEach(()=>cleanup());
it('pins the approved original shot and uses original typed edges without choosing a provider',()=>{
 const draft={...empty(),title:'My video'},before=structuredClone(draft);
 const next=buildStoryboardVideoStarter(draft,catalog,receipt,receipt.shots[0].shot_id);
 expect(next.nodes.map(row=>row.definition_id)).toEqual(['storyboard_plan','storyboard_shot','video_generate','media_review']);
 expect(next.nodes[0].parameters.document_snapshot).toEqual(receipt.document_snapshot);
 expect(next.nodes[1].parameters).toEqual({shot_id:receipt.shots[0].shot_id,shot_version:receipt.shots[0].shot_version,shot_digest:receipt.shots[0].shot_digest});
 expect(next.nodes[2].parameters).toMatchObject({bind_shot:true,allow_cloud:false,provider_id:'',model_id:''});
 expect(draft).toEqual(before);expect(next.title).toBe('My video');
 for(const edge of next.edges)expect(connectionIssue({...next,edges:next.edges.filter(row=>row!==edge)},catalog.definitions,edge)).toBeUndefined();
 expect(()=>checkedStudioGraphDraft(next)).toThrow();
 const configured=structuredClone(next);configured.nodes[2].parameters.provider_id='fixture-provider';configured.nodes[2].parameters.model_id='fixture-model';
 expect(checkedStudioGraphDraft(configured).edges).toHaveLength(3);
});
it('refuses unreviewed, missing-shot, nonempty, wrong-schema and colliding drafts',()=>{
 const shot=receipt.shots[0].shot_id;
 expect(()=>buildStoryboardVideoStarter(empty(),catalog,{...receipt,approved:false},shot)).toThrow();
 expect(()=>buildStoryboardVideoStarter(empty(),catalog,receipt,'missing')).toThrow();
 expect(()=>buildStoryboardVideoStarter(blankGraph(),catalog,receipt,shot)).toThrow();
 expect(()=>buildStoryboardVideoStarter(empty(),catalog,receipt,shot,()=> 'same')).toThrow();
 const full=buildStoryboardVideoStarter(empty(),catalog,receipt,shot);
 expect(()=>buildStoryboardVideoStarter(full,catalog,receipt,shot)).toThrow();
});
function setup(onRead=vi.fn(async()=>receipt)){
 const props={scope:{},disabled:false,loading:false,documents,onLoad:vi.fn(async()=>{}),onRead,onApply:vi.fn(()=>true)};
 const view=render(<GraphStoryboardStarter {...props}/>);return {props,view};
}
async function inspect(){fireEvent.change(screen.getByLabelText('起步来源分镜'),{target:{value:receipt.document_snapshot.id}});fireEvent.click(button('核对起步分镜镜头与审核'));await screen.findByLabelText('起步分镜精确来源');fireEvent.change(screen.getByLabelText('起步分镜镜头'),{target:{value:receipt.shots[0].shot_id}});}
it('requires explicit inspection and shot choice and applies exactly once without background reads',async()=>{
 const {props}=setup();expect(props.onRead).not.toHaveBeenCalled();expect(props.onLoad).not.toHaveBeenCalled();await inspect();expect(props.onApply).not.toHaveBeenCalled();
 const apply=handler(button('应用分镜视频链到本地空图'));act(()=>{apply();apply();});
 expect(props.onApply).toHaveBeenCalledTimes(1);expect(props.onApply).toHaveBeenCalledWith(receipt,receipt.shots[0].shot_id,props.scope);
});
it.each(['scope','documents','disabled'] as const)('rejects retained apply after %s changes',async(key)=>{
 const {props,view}=setup();await inspect();const apply=handler(button('应用分镜视频链到本地空图'));
 view.rerender(<GraphStoryboardStarter {...props} {...(key==='scope'?{scope:{}}:key==='documents'?{documents:[...documents]}:{disabled:true})}/>);
 act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();
});
it('invalidates retained shot choice after selection changes away and back',async()=>{
 const {props}=setup();await inspect();const apply=handler(button('应用分镜视频链到本地空图'));
 fireEvent.change(screen.getByLabelText('起步分镜镜头'),{target:{value:receipt.shots[1].shot_id}});
 fireEvent.change(screen.getByLabelText('起步分镜镜头'),{target:{value:receipt.shots[0].shot_id}});
 act(()=>apply());expect(props.onApply).not.toHaveBeenCalled();fireEvent.click(button('应用分镜视频链到本地空图'));expect(props.onApply).toHaveBeenCalledTimes(1);
});
it('discards a late inspection after owner changes',async()=>{
 let resolve!:(value:typeof receipt)=>void;const {props,view}=setup(vi.fn(()=>new Promise<typeof receipt>(done=>{resolve=done;})));
 fireEvent.change(screen.getByLabelText('起步来源分镜'),{target:{value:receipt.document_snapshot.id}});fireEvent.click(button('核对起步分镜镜头与审核'));
 view.rerender(<GraphStoryboardStarter {...props} scope={{}}/>);await act(async()=>resolve(receipt));
 expect(screen.queryByLabelText('起步分镜精确来源')).toBeNull();expect(props.onApply).not.toHaveBeenCalled();
});

it('assembles through the original controller with one undo and no automatic write or execution',async()=>{
 const transport=vi.fn(),create=vi.fn(async(body:{definition:unknown})=>{checkedStudioGraphDraft(body.definition);return transport(body);}),createRun=vi.fn(),videoStoryboard=vi.fn(async()=>receipt);
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'starter-project',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),client:{graphs:{catalog:vi.fn(async()=>catalog),list:vi.fn(async()=>({items:[]})),videoCatalog:vi.fn(async()=>catalog),planningDocuments:vi.fn(async()=>({documents})),videoStoryboard,create,createRun}} as unknown as StudioClient};
 function Harness(){const controller=useStudioGraphEditorController(props);return studioGraphEditorView(controller,props).content;}
 render(<Harness/>);await screen.findByLabelText('确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务');
 fireEvent.click(button('明确读取视频图节点目录'));
 await act(async()=>{});
 fireEvent.click(screen.getByLabelText('确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务'));
 fireEvent.click(button('明确采用视频图 v5'));
 await screen.findByLabelText('分镜到视频起步方案');fireEvent.click(button('读取起步分镜目录'));
 await within(screen.getByLabelText('起步来源分镜')).findByRole('option',{name:'Original storyboard · v5'});await inspect();
 fireEvent.click(button('应用分镜视频链到本地空图'));
 expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(4);
 expect(create).not.toHaveBeenCalled();expect(createRun).not.toHaveBeenCalled();
 fireEvent.click(button('撤销图编辑'));expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);
 fireEvent.click(button('重做图编辑'));expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(4);
 fireEvent.click(button('保存创作图'));await act(async()=>{});expect(create).toHaveBeenCalledTimes(1);expect(transport).not.toHaveBeenCalled();
 expect(createRun).not.toHaveBeenCalled();expect(videoStoryboard).toHaveBeenCalledTimes(1);
});
