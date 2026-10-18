// @vitest-environment jsdom
import { act,cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { afterEach,expect,it,vi } from 'vitest';
import { GraphNodeStateControl } from './GraphNodeStateControl';
import { graphNodeStateImpact } from './graphNodeStateImpact';
import { imageGraphCatalog,imageGraphRecord } from './studioImageGraph.testFixtures';
import { useStudioGraphEditorController,type StudioGraphEditorController,type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';
const retained=(element:HTMLElement)=>(element as any)[Object.keys(element).find(key=>key.startsWith('__reactProps$'))!].onClick;
afterEach(cleanup);
function fixture(){return{nodeId:'prompt',definition:imageGraphRecord().definition,definitions:imageGraphCatalog().definitions,owner:{},disabled:false,isCurrent:()=>true,onChange:vi.fn()};}
it('reports disable impact while preserving the original source and connections',()=>{
 const source=imageGraphRecord().definition,before=structuredClone(source),result=graphNodeStateImpact(source,'prompt',false,imageGraphCatalog().definitions);
 expect(result.affected).toEqual(['prompt','generate','review']);expect(result.newMissing).toContain('generate.prompt');expect(result.unaffected).toContain('asset');expect(result.definition.nodes.find(n=>n.id==='prompt')!.enabled).toBe(false);expect(result.definition.edges).toHaveLength(4);expect(source).toEqual(before);
});
it('requires preview and explicit consent, consuming even a retained callback once',()=>{
 const props=fixture();render(<GraphNodeStateControl {...props}/>);fireEvent.click(screen.getByLabelText('启用当前节点'));expect(props.onChange).not.toHaveBeenCalled();expect(screen.getByText('新增缺少的必需输入：generate.prompt。')).toBeTruthy();
 const button=screen.getByText('确认状态变更到本地草稿');expect((button as HTMLButtonElement).disabled).toBe(true);fireEvent.click(screen.getByLabelText('已核对影响，确认修改节点状态'));const callback=retained(button);act(()=>{callback();callback();});expect(props.onChange).toHaveBeenCalledTimes(1);expect(props.onChange.mock.calls[0][0].nodes.find((n:any)=>n.id==='prompt').enabled).toBe(false);
});
it.each(['draft','authority','permission','consent'])('rejects a retained confirmed state change after %s changes',mode=>{
 const props=fixture();const view=render(<GraphNodeStateControl {...props}/>);fireEvent.click(screen.getByLabelText('启用当前节点'));fireEvent.click(screen.getByLabelText('已核对影响，确认修改节点状态'));const callback=retained(screen.getByText('确认状态变更到本地草稿'));
 if(mode==='draft')view.rerender(<GraphNodeStateControl {...props} definition={{...props.definition,title:'Changed'}}/>);
 if(mode==='authority')view.rerender(<GraphNodeStateControl {...props} owner={{}}/>);
 if(mode==='permission'){view.rerender(<GraphNodeStateControl {...props} disabled/>);view.rerender(<GraphNodeStateControl {...props}/>);}
 if(mode==='consent')fireEvent.click(screen.getByLabelText('已核对影响，确认修改节点状态'));
 act(()=>callback());expect(props.onChange).not.toHaveBeenCalled();
});
it('applies through original Graph history and CAS without creating a run',async()=>{
 let controller!:StudioGraphEditorController;const original=imageGraphRecord();const save=vi.fn(async(_id:string,body:any)=>({...original,version:2,definition:body.definition})),createRun=vi.fn();
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'owner',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),client:{graphs:{catalog:vi.fn(async()=>imageGraphCatalog()),imageCatalog:vi.fn(async()=>imageGraphCatalog()),list:vi.fn(async()=>({items:[original]})),get:vi.fn(async()=>original),save,createRun}} as unknown as StudioClient};
 function Harness(){controller=useStudioGraphEditorController(props);return controller.catalog?<GraphNodeStateControl nodeId="prompt" definition={controller.draft} definitions={controller.catalog.definitions} owner={controller.insertionScope} disabled={!controller.editable} isCurrent={controller.current} onChange={controller.change}/>:null;}
 render(<Harness/>);await waitFor(()=>expect(controller.catalog).toBeTruthy());await act(async()=>controller.open(original.id));fireEvent.click(screen.getByLabelText('启用当前节点'));fireEvent.click(screen.getByLabelText('已核对影响，确认修改节点状态'));fireEvent.click(screen.getByText('确认状态变更到本地草稿'));expect(controller.draft.nodes.find(n=>n.id==='prompt')!.enabled).toBe(false);expect(save).not.toHaveBeenCalled();
 act(()=>controller.travel(false));expect(controller.draft.nodes.find(n=>n.id==='prompt')!.enabled).toBe(true);act(()=>controller.travel(true));expect(controller.draft.nodes.find(n=>n.id==='prompt')!.enabled).toBe(false);await act(async()=>controller.save());expect(save).toHaveBeenCalledTimes(1);expect(save.mock.calls[0][1].expected_version).toBe(1);expect(createRun).not.toHaveBeenCalled();
});
it('enabling an incomplete node reports its required inputs and does not manufacture an edge',()=>{
 const p=fixture();p.definition.edges=p.definition.edges.filter(edge=>edge.id!=='prompt_generate');p.definition.nodes.find(node=>node.id==='generate')!.enabled=false;
 const result=graphNodeStateImpact(p.definition,'generate',true,p.definitions);expect(result.newMissing).toContain('generate.prompt');expect(result.definition.edges).toEqual(p.definition.edges);
});
it('cancel leaves the checkbox and source state unchanged',()=>{const p=fixture();render(<GraphNodeStateControl {...p}/>);fireEvent.click(screen.getByLabelText('启用当前节点'));expect((screen.getByLabelText('启用当前节点') as HTMLInputElement).checked).toBe(true);fireEvent.click(screen.getByText('保持原状态'));expect(p.onChange).not.toHaveBeenCalled();expect(screen.queryByLabelText('节点状态影响预览')).toBeNull();});
it('rejects an unknown node and an incomplete catalog instead of guessing',()=>{const p=fixture();expect(()=>graphNodeStateImpact(p.definition,'absent',false,p.definitions)).toThrow();expect(()=>graphNodeStateImpact(p.definition,'prompt',false,[])).toThrow();});
