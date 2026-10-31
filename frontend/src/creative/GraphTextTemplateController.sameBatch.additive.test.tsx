// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {useStudioGraphEditorController,type StudioGraphEditorController,type StudioGraphEditorProps} from './useStudioGraphEditorController';
import {studioGraphEditorView} from './studioGraphEditorView';
import {blankGraph} from './graphDraft';
import {modelCatalog} from './studioGraphModel.testFixtures';
import {exportTextGraphTemplate} from './graphTextTemplates';
afterEach(cleanup);
it.each(['intervening title','draft ABA'])('production template wiring rejects a retained confirmation after same-batch %s',async mode=>{
 let control!:StudioGraphEditorController;const save=vi.fn(),run=vi.fn();const props:StudioGraphEditorProps={active:true,denied:false,identity:'same-batch:actor',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),client:{graphs:{catalog:async()=>modelCatalog(),list:async()=>({items:[]}),create:save,createRun:run}} as any};
 function Mounted(){const c=useStudioGraphEditorController(props);control=c;const view=studioGraphEditorView(c,props);return <>{view.content}{view.inspector}</>}
 render(<Mounted/>);await waitFor(()=>expect(control.editable).toBe(true));const source={...blankGraph(),nodes:[{id:'Input',definition_id:'text_input' as const,definition_version:1 as const,enabled:true,parameters:{text:'author'},position:{x:0,y:0}}]},raw=exportTextGraphTemplate(source);
 fireEvent.change(screen.getByLabelText('导入文字图模板 JSON'),{target:{files:[{size:new TextEncoder().encode(raw).length,text:async()=>raw}]}});await screen.findByText(/将新增 1 个节点/);fireEvent.click(screen.getByLabelText('确认仅把模板追加到当前本地草稿'));
 const button=screen.getByText('明确追加模板节点'),action=(button as any)[Object.keys(button).find(key=>key.startsWith('__reactProps$'))!].onClick,original=control.draft;
 act(()=>{control.change({...original,title:'Intervening author edit'});if(mode==='draft ABA')control.change(original);action();});
 expect(control.draft.title).toBe(mode==='draft ABA'?original.title:'Intervening author edit');expect(control.draft.nodes).toHaveLength(0);expect(control.past).toHaveLength(mode==='draft ABA'?2:1);expect(control.future).toHaveLength(0);expect(save).not.toHaveBeenCalled();expect(run).not.toHaveBeenCalled();
 act(action);expect(control.draft.nodes).toHaveLength(0);expect(control.past).toHaveLength(mode==='draft ABA'?2:1);expect(control.selected).toEqual([]);
 act(()=>control.travel(false));expect(control.draft.title).toBe(mode==='draft ABA'?'Intervening author edit':original.title);expect(control.draft.nodes).toHaveLength(0);
});
it('drops a late file read after same-batch target ABA without adding history',async()=>{
 let control!:StudioGraphEditorController;const save=vi.fn(),run=vi.fn();const props:StudioGraphEditorProps={active:true,denied:false,identity:'late-aba:actor',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),client:{graphs:{catalog:async()=>modelCatalog(),list:async()=>({items:[]}),create:save,createRun:run}} as any};
 function Mounted(){const c=useStudioGraphEditorController(props);control=c;const view=studioGraphEditorView(c,props);return <>{view.content}{view.inspector}</>}
 render(<Mounted/>);await waitFor(()=>expect(control.editable).toBe(true));const original=control.draft;let resolve!:(value:string)=>void;
 const raw=exportTextGraphTemplate({...blankGraph(),nodes:[{id:'Input',definition_id:'text_input',definition_version:1,enabled:true,parameters:{text:'author'},position:{x:0,y:0}}]});
 fireEvent.change(screen.getByLabelText('导入文字图模板 JSON'),{target:{files:[{size:new TextEncoder().encode(raw).length,text:()=>new Promise<string>(done=>{resolve=done})}]}});
 await act(async()=>{control.change({...original,title:'Intervening'});control.change(original);resolve(raw);await Promise.resolve();});
 expect(screen.queryByText('明确追加模板节点')).toBeNull();expect(control.draft).toBe(original);expect(control.past).toHaveLength(2);expect(control.future).toHaveLength(0);expect(save).not.toHaveBeenCalled();expect(run).not.toHaveBeenCalled();
});
