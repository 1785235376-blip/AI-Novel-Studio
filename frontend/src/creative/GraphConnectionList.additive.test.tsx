// @vitest-environment jsdom
import { act,cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { afterEach,expect,it,vi } from 'vitest';
import { GraphConnectionList } from './GraphConnectionList';
import { graphDisconnectImpact } from './graphDisconnectImpact';
import { imageGraphCatalog,imageGraphRecord } from './studioImageGraph.testFixtures';
import { useStudioGraphEditorController,type StudioGraphEditorController,type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';
const retained=(element:HTMLElement)=>(element as any)[Object.keys(element).find(key=>key.startsWith('__reactProps$'))!].onClick;
afterEach(cleanup);
function fixture(){return{definition:imageGraphRecord().definition,definitions:imageGraphCatalog().definitions,owner:{},disabled:false,isCurrent:()=>true,onChange:vi.fn()};}
it('reports structural downstream and newly missing required ports without changing source or nodes',()=>{
 const source=imageGraphRecord().definition,before=structuredClone(source),result=graphDisconnectImpact(source,'prompt_generate',imageGraphCatalog().definitions);
 expect(result.affected).toEqual(['generate','review']);expect(result.newMissing).toContain('generate.prompt');expect(result.unaffected).toContain('asset');expect(result.definition.nodes).toEqual(source.nodes);expect(result.definition.edges).toHaveLength(3);expect(source).toEqual(before);
});
it('requires preview and explicit consent, consuming even a retained callback once',()=>{
 const props=fixture();render(<GraphConnectionList {...props}/>);fireEvent.click(screen.getByText('移除连接 prompt_generate'));expect(props.onChange).not.toHaveBeenCalled();expect(screen.getByText('新增缺少的必需输入：generate.prompt。')).toBeTruthy();
 const button=screen.getByText('确认断开到本地草稿');expect((button as HTMLButtonElement).disabled).toBe(true);fireEvent.click(screen.getByRole('checkbox'));const callback=retained(button);act(()=>{callback();callback();});expect(props.onChange).toHaveBeenCalledTimes(1);expect(props.onChange.mock.calls[0][0].edges).toHaveLength(3);
});
it.each(['draft','authority','permission','consent'])('rejects a retained confirmed removal after %s changes',mode=>{
 const props=fixture();const view=render(<GraphConnectionList {...props}/>);fireEvent.click(screen.getByText('移除连接 prompt_generate'));fireEvent.click(screen.getByRole('checkbox'));const callback=retained(screen.getByText('确认断开到本地草稿'));
 if(mode==='draft')view.rerender(<GraphConnectionList {...props} definition={{...props.definition,title:'Changed'}}/>);
 if(mode==='authority')view.rerender(<GraphConnectionList {...props} owner={{}}/>);
 if(mode==='permission'){view.rerender(<GraphConnectionList {...props} disabled/>);view.rerender(<GraphConnectionList {...props}/>);}
 if(mode==='consent')fireEvent.click(screen.getByRole('checkbox'));
 act(()=>callback());expect(props.onChange).not.toHaveBeenCalled();
});
it('applies through original Graph history and CAS without creating a run',async()=>{
 let controller!:StudioGraphEditorController;const original=imageGraphRecord();const save=vi.fn(async(_id:string,body:any)=>({...original,version:2,definition:body.definition})),createRun=vi.fn();
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'owner',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:work=>work(),mutate:work=>work(),client:{graphs:{catalog:vi.fn(async()=>imageGraphCatalog()),imageCatalog:vi.fn(async()=>imageGraphCatalog()),list:vi.fn(async()=>({items:[original]})),get:vi.fn(async()=>original),save,createRun}} as unknown as StudioClient};
 function Harness(){controller=useStudioGraphEditorController(props);return controller.catalog?<GraphConnectionList definition={controller.draft} definitions={controller.catalog.definitions} owner={controller.insertionScope} disabled={!controller.editable} isCurrent={controller.current} onChange={controller.change}/>:null;}
 render(<Harness/>);await waitFor(()=>expect(controller.catalog).toBeTruthy());await act(async()=>controller.open(original.id));fireEvent.click(screen.getByText('移除连接 prompt_generate'));fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByText('确认断开到本地草稿'));expect(controller.draft.edges).toHaveLength(3);expect(save).not.toHaveBeenCalled();
 act(()=>controller.travel(false));expect(controller.draft.edges).toHaveLength(4);act(()=>controller.travel(true));expect(controller.draft.edges).toHaveLength(3);await act(async()=>controller.save());expect(save).toHaveBeenCalledTimes(1);expect(save.mock.calls[0][1].expected_version).toBe(1);expect(createRun).not.toHaveBeenCalled();
});
