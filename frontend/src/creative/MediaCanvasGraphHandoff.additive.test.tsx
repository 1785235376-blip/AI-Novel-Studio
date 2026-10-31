// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MediaCanvasGraphHandoff } from './MediaCanvasGraphHandoff';
import { appendCanvasAssetNode, verifyCanvasGraphAsset } from './mediaCanvasGraphHandoffHelpers';
import { blankGraph } from './graphDraft';
import { imageGraphCatalog, imageGraphRecord } from './studioImageGraph.testFixtures';
import { useStudioGraphEditorController, type StudioGraphEditorProps, type StudioGraphEditorController } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';
const reference={asset_id:'selected-asset',version:2,digest:'a'.repeat(64),kind:'image' as const};
const asset={id:reference.asset_id,version:2,sha256:reference.digest,kind:'image',filename:'selected.png'} as any;
const click=(name:string)=>fireEvent.click(screen.getByRole('button',{name}));
const retained=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('adds only an original pinned input node, preserving graph content without edges or schema changes',()=>{
 const source=imageGraphRecord().definition,before=structuredClone(source);const next=appendCanvasAssetNode(source,imageGraphCatalog(),reference,()=> 'new-asset');
 expect(next.definition.nodes).toHaveLength(6);expect(next.definition.edges).toEqual(source.edges);expect(next.definition.nodes[5].parameters).toEqual(reference);expect(next.definition.schema_version).toBe(4);expect(source).toEqual(before);
});
it.each(['schema','kind','capacity','digest','duplicate'])('rejects incompatible %s without modifying the target',mode=>{
 const source=imageGraphRecord().definition,catalog=imageGraphCatalog(),ref={...reference};
 if(mode==='schema')source.schema_version=2;if(mode==='kind')ref.kind='video' as any;if(mode==='capacity')catalog.media_limits={...catalog.media_limits!,nodes:source.nodes.length} as any;if(mode==='digest')ref.digest='bad';
 expect(()=>appendCanvasAssetNode(source,catalog,ref,()=>mode==='duplicate'?'asset':'new-asset')).toThrow();
});
it.each([{version:3},{sha256:'b'.repeat(64)},{kind:'video'},{deleted_at:'now'}])('rejects stale or revoked asset metadata %j',change=>{expect(()=>verifyCanvasGraphAsset({...asset,...change},reference)).toThrow();});
function fixture(){const props={reference,owner:{},disabled:false,isCurrent:()=>true,client:{asset:vi.fn().mockResolvedValue(asset)},read:async<T,>(work:()=>Promise<T>)=>work(),handoff:{scope:{},available:true,isCurrent:()=>true,insert:vi.fn(()=>true)}};return props;}
it('requires current metadata and explicit consent, then consumes the action exactly once',async()=>{
 const props=fixture();render(<MediaCanvasGraphHandoff {...props}/>);expect(props.client.asset).not.toHaveBeenCalled();click('核对素材与目标图');
 await screen.findByText(/selected-asset · v2/);const button=screen.getByRole('button',{name:'加入素材引用节点'});expect((button as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox'));const callback=retained(button);act(()=>{callback();callback();});expect(props.handoff.insert).toHaveBeenCalledTimes(1);expect(props.handoff.insert).toHaveBeenCalledWith(reference,props.handoff.scope);
});
it.each(['source','target','permission'])('discards a late read after %s lifetime changes',async mode=>{
 const props=fixture();let resolve!:(value:any)=>void;props.client.asset.mockImplementation(()=>new Promise(r=>resolve=r));const view=render(<MediaCanvasGraphHandoff {...props}/>);click('核对素材与目标图');
 if(mode==='source')view.rerender(<MediaCanvasGraphHandoff {...props} owner={{}}/>);
 if(mode==='target')view.rerender(<MediaCanvasGraphHandoff {...props} handoff={{...props.handoff,scope:{}}}/>);
 if(mode==='permission'){view.rerender(<MediaCanvasGraphHandoff {...props} disabled/>);view.rerender(<MediaCanvasGraphHandoff {...props}/>);}
 await act(async()=>resolve(asset));expect(screen.queryByRole('button',{name:'加入素材引用节点'})).toBeNull();expect(props.handoff.insert).not.toHaveBeenCalled();
});
it('actual graph owner keeps history, rejects stale handoff scope and saves through original CAS',async()=>{
 let controller!:StudioGraphEditorController;const original=imageGraphRecord();
 const save=vi.fn(async(_id:string,body:any)=>({...original,version:2,definition:body.definition})),createRun=vi.fn();
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'owner',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),client:{asset:vi.fn(async()=>asset),graphs:{catalog:vi.fn(async()=>imageGraphCatalog()),imageCatalog:vi.fn(async()=>imageGraphCatalog()),list:vi.fn(async()=>({items:[original]})),get:vi.fn(async()=>original),save,createRun}} as unknown as StudioClient};
 function Harness(){controller=useStudioGraphEditorController(props);return <output>{controller.draft.nodes.length}</output>;}
 render(<Harness/>);await waitFor(()=>expect(controller.catalog).toBeTruthy());await act(async()=>controller.open(original.id));const old=controller.canvasAssetHandoff;
 await act(async()=>{expect(old.insert(reference,old.scope)).toBe(true);});expect(controller.draft.nodes).toHaveLength(6);expect(save).not.toHaveBeenCalled();
 act(()=>expect(old.insert(reference,old.scope)).toBe(false));act(()=>controller.travel(false));expect(controller.draft.nodes).toHaveLength(5);await act(async()=>controller.travel(true));expect(controller.draft.nodes).toHaveLength(6);
 await act(async()=>controller.save());expect(save).toHaveBeenCalledTimes(1);expect(save.mock.calls[0][1].expected_version).toBe(1);expect(createRun).not.toHaveBeenCalled();
});
