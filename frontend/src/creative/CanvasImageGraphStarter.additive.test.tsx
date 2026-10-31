// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {buildCanvasImageGraphStarter,type CanvasImageGraphRequest} from './canvasImageGraphStarter';
import {blankGraph,connectionIssue} from './graphDraft';
import {checkedStudioGraphDraft} from './studioGraphClient';
import {checkedLocalGraphDefinition} from './studioGraphLocalDraft';
import {imageGraphCatalog} from './studioImageGraph.testFixtures';
import {modelCatalog} from './studioGraphModel.testFixtures';
import {useStudioGraphEditorController,type StudioGraphEditorController,type StudioGraphEditorProps} from './useStudioGraphEditorController';
import {MediaCanvasViewPanel} from './MediaCanvasViewPanel';
import {useStudioGraphEditor} from './useStudioGraphEditor';
import type {CanvasDefinition} from './studioCanvasViewClient';

afterEach(cleanup);
const request=():CanvasImageGraphRequest=>({prompt:'保留人物服装和雨后街道的作者输入',sources:[{cardId:'Card_A',reference:{asset_id:'image-a',version:2,digest:'a'.repeat(64),kind:'image'},weight:.75,purpose:'character'},{cardId:'Card_B',reference:{asset_id:'image-b',version:3,digest:'b'.repeat(64),kind:'image'},weight:.5,purpose:'environment'}]});
const empty=()=>({...blankGraph(),schema_version:4 as const});
it('uses original seven nodes/six ports, fixed source versions and blank local route without mutating inputs',()=>{
 const target=empty(),input=request(),before=structuredClone({target,input});let id=0;const plan=buildCanvasImageGraphStarter(target,imageGraphCatalog(),input,prefix=>`${prefix}_${++id}`);
 expect({target,input}).toEqual(before);expect(plan.definition.nodes).toHaveLength(7);expect(plan.definition.edges).toHaveLength(6);
 for(const edge of plan.definition.edges)expect(connectionIssue({...plan.definition,edges:plan.definition.edges.filter(row=>row!==edge)},imageGraphCatalog().definitions,edge)).toBeUndefined();
 expect(plan.definition.nodes.find(row=>row.definition_id==='text_input')?.parameters.text).toBe(input.prompt);
 expect(plan.definition.nodes.find(row=>row.definition_id==='image_generate')?.parameters).toMatchObject({operation_id:'m5.image.reference',provider_id:'',model_id:'',allow_cloud:false});
 expect(plan.definition.nodes.find(row=>row.definition_id==='image_reference')?.parameters.bindings).toEqual([{port:'source_1',weight:.75,purpose:'character'},{port:'source_2',weight:.5,purpose:'environment'}]);
 expect(plan.sources.map(row=>plan.definition.nodes.find(node=>node.id===row.nodeId)?.parameters)).toEqual(input.sources.map(row=>row.reference));
 expect(()=>checkedStudioGraphDraft(plan.definition)).toThrow();const configured=structuredClone(plan.definition);const generator=configured.nodes.find(row=>row.definition_id==='image_generate')!;generator.parameters.provider_id='fixture-provider';generator.parameters.model_id='fixture-model';expect(checkedStudioGraphDraft(configured).edges).toHaveLength(6);
});
it('refuses unbounded choices, duplicates, invalid references, nonempty targets and full-definition capacity before mutation',()=>{
 const target=empty(),catalog=imageGraphCatalog(),before=structuredClone(target);
 const cases=[{...request(),sources:request().sources.slice(0,1)},{...request(),sources:[request().sources[0],request().sources[0]]},{...request(),prompt:' '},{...request(),sources:request().sources.map(row=>({...row,weight:0}))}];
 for(const input of cases)expect(()=>buildCanvasImageGraphStarter(target,catalog,input)).toThrow();
 const malformed=request();malformed.sources[0].reference.digest='invalid';expect(()=>buildCanvasImageGraphStarter(target,catalog,malformed)).toThrow();
 expect(()=>buildCanvasImageGraphStarter({...target,schema_version:3},catalog,request())).toThrow();
 expect(()=>buildCanvasImageGraphStarter({...target,nodes:[{id:'Text',definition_id:'text_input',definition_version:1,enabled:true,position:{x:0,y:0},parameters:{text:'keep'}}]},catalog,request())).toThrow();
 const nearCapacity={...target,presentation:{notes:Array.from({length:900},(_,i)=>({id:`Note_${i}`,text:'字'.repeat(13),position:{x:0,y:0}}))}};
 expect(()=>checkedLocalGraphDefinition(nearCapacity)).not.toThrow();expect(()=>buildCanvasImageGraphStarter(nearCapacity,catalog,request())).not.toThrow();
 expect(()=>buildCanvasImageGraphStarter(nearCapacity,catalog,{...request(),prompt:'字'.repeat(8000)})).toThrow();
 expect(()=>buildCanvasImageGraphStarter(target,catalog,request(),()=> 'same')).toThrow();expect(target).toEqual(before);
});

async function controllerFixture(){
 let c!:StudioGraphEditorController;const create=vi.fn(),createRun=vi.fn();let busy=false;
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'dual:owner',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,isBusy:()=>busy,read:f=>f(),mutate:f=>f(),client:{graphs:{catalog:async()=>modelCatalog(),imageCatalog:async()=>imageGraphCatalog(),list:async()=>({items:[]}),create,createRun}} as any};
 function Mounted(){c=useStudioGraphEditorController(props);return null;}const view=render(<Mounted/>);await waitFor(()=>expect(c.editable).toBe(true));
 await act(async()=>{await c.loadImageCatalog();});act(()=>c.confirmImageSchema(true));act(()=>c.upgradeImageSchema());expect(c.draft.schema_version).toBe(4);
 return {get c(){return c;},create,createRun,props,render:()=>view.rerender(<Mounted/>),setBusy:(value:boolean)=>{busy=value;}};
}
it('applies only the sealed plan once through original history and reverses/redoes the entire graph in one step',async()=>{
 const f=await controllerFixture(),h=f.c.canvasImageGraphStarter,old=structuredClone(f.c.draft),past=f.c.past.length,plan=h.preview(request(),h.scope);expect(f.c.draft).toEqual(old);
 act(()=>{expect(h.apply(plan,h.scope,()=>true)).toBe(true);expect(h.apply(plan,h.scope,()=>true)).toBe(false);});
 const next=structuredClone(f.c.draft);expect(f.c.past).toHaveLength(past+1);expect(next.nodes).toHaveLength(7);expect(f.c.selected).toEqual([plan.generatorNodeId]);
 act(()=>f.c.travel(false));expect(f.c.draft).toEqual(old);act(()=>f.c.travel(true));expect(f.c.draft).toEqual(next);expect(f.create).not.toHaveBeenCalled();expect(f.createRun).not.toHaveBeenCalled();
});
it.each(['target ABA','source ABA','busy','permission ABA','mutated plan'])('rejects retained confirmation after %s without import history',async mode=>{
 const f=await controllerFixture(),h=f.c.canvasImageGraphStarter,plan=h.preview(request(),h.scope),original=f.c.draft,past=f.c.past.length;
 if(mode==='target ABA')act(()=>{f.c.change({...original,title:'Intervening'});f.c.change(original);expect(h.apply(plan,h.scope,()=>true)).toBe(false);});
 if(mode==='source ABA')act(()=>expect(h.apply(plan,h.scope,()=>false)).toBe(false));
 if(mode==='busy'){f.setBusy(true);act(()=>expect(h.apply(plan,h.scope,()=>true)).toBe(false));}
 if(mode==='permission ABA'){f.props.canMutate=false;f.render();f.props.canMutate=true;f.render();act(()=>expect(h.apply(plan,h.scope,()=>true)).toBe(false));}
 if(mode==='mutated plan'){plan.definition.title='tampered';act(()=>expect(h.apply(plan,h.scope,()=>true)).toBe(false));}
 expect(f.c.draft.nodes).toHaveLength(0);expect(f.c.past).toHaveLength(past+(mode==='target ABA'?2:0));expect(f.create).not.toHaveBeenCalled();expect(f.createRun).not.toHaveBeenCalled();
});

const retained=(element:HTMLElement)=>(element as any)[Object.keys(element).find(key=>key.startsWith('__reactProps$'))!].onClick as ()=>void;
async function boardFixture(){
 const sources=request().sources,definition:CanvasDefinition={schema_version:1,title:'Two saved cards',cards:sources.map((row,index)=>({id:row.cardId,asset:row.reference,position:{x:index*280,y:0}})),viewport:{x:0,y:0,zoom:1}};
 const record={id:'board',version:1,definition,reference_states:sources.map(row=>({card_id:row.cardId,state:'CURRENT_METADATA',filename:row.cardId+'.png'})),execution_authority:false};
 const apply=vi.fn(()=>true),scope={},handoff={scope,available:true,isCurrent:()=>true,preview:vi.fn((input:CanvasImageGraphRequest)=>buildCanvasImageGraphStarter(empty(),imageGraphCatalog(),input)),apply,graph:{title:'Empty',prompts:[],references:[]},focusPrompt:vi.fn()};
 const asset=vi.fn(async(id:string)=>{const ref=sources.find(row=>row.reference.asset_id===id)!.reference;return {id,version:ref.version,sha256:ref.digest,kind:'image'};});
 const props={active:true,denied:false,identity:'board:owner',canMutate:true,busy:false,externalDirty:false,isCurrent:()=>true,read:async<T,>(f:()=>Promise<T>)=>f(),mutate:async<T,>(f:()=>Promise<T>)=>f(),onDirtyChange:vi.fn(),imageGraphHandoff:handoff,client:{asset,graphs:{canvasViews:{list:async()=>({items:[{id:'board',title:'Two saved cards',version:1,card_count:2}]}),get:async()=>record,create:vi.fn(),save:vi.fn()}}} as any};
 const view=render(<MediaCanvasViewPanel {...props}/>);fireEvent.click(screen.getByText('读取已存画布'));await screen.findByText('Two saved cards · v1 · 2 张');fireEvent.click(screen.getByText('Two saved cards · v1 · 2 张'));await screen.findByText('已读取持久化版本');
 fireEvent.click(screen.getByLabelText('图片输入 Card_A'));fireEvent.click(screen.getByLabelText('图片输入 Card_B'));
 const preview=async()=>{fireEvent.change(screen.getByLabelText('双参考图作者 Prompt'),{target:{value:request().prompt}});fireEvent.click(screen.getByText('核对两张图片并预览原图'));await screen.findByLabelText('双参考图起步预览');fireEvent.click(screen.getByLabelText('确认仅将预览加入下方本地图片图'));return retained(screen.getByText('明确建立双参考图片图草稿'));};
 return {props,view,preview,apply,asset,definition};
}
it('keeps metadata selection usable with a dirty target graph, while original layout writes remain locked',async()=>{
 const f=await boardFixture();f.view.rerender(<MediaCanvasViewPanel {...f.props} externalDirty/>);
 expect((screen.getByLabelText('画布标题') as HTMLInputElement).disabled).toBe(true);expect((screen.getByLabelText('图片输入 Card_A') as HTMLInputElement).disabled).toBe(false);
 const apply=await f.preview();act(()=>{apply();apply();});expect(f.apply).toHaveBeenCalledTimes(1);expect(f.props.client.graphs.canvasViews.save).not.toHaveBeenCalled();
});
it('rejects a retained apply after same-batch card-selection ABA and preserves saved layout',async()=>{
 const f=await boardFixture(),apply=await f.preview(),checkbox=screen.getByLabelText('图片输入 Card_A'),handler=(checkbox as any)[Object.keys(checkbox).find(key=>key.startsWith('__reactProps$'))!].onChange;
 act(()=>{handler();handler();apply();});expect(f.apply).not.toHaveBeenCalled();expect(f.definition.cards.map(row=>row.position)).toEqual([{x:0,y:0},{x:280,y:0}]);expect(f.props.client.graphs.canvasViews.save).not.toHaveBeenCalled();
});
it('drops late metadata after source-selection change and requires a new explicit preview',async()=>{
 const f=await boardFixture();let resolve!:(row:any)=>void;const deferred=new Promise<any>(done=>{resolve=done;});f.asset.mockImplementationOnce(()=>deferred);
 fireEvent.change(screen.getByLabelText('双参考图作者 Prompt'),{target:{value:request().prompt}});fireEvent.click(screen.getByText('核对两张图片并预览原图'));fireEvent.click(screen.getByLabelText('图片输入 Card_A'));
 await act(async()=>{const ref=request().sources[0].reference;resolve({id:ref.asset_id,version:ref.version,sha256:ref.digest,kind:'image'});await deferred;});
 expect(screen.queryByLabelText('双参考图起步预览')).toBeNull();expect(f.apply).not.toHaveBeenCalled();
});
it('wires both actual canvases through the production hook without a dirty-target selection deadlock or automatic Save/run',async()=>{
 const sources=request().sources,definition:CanvasDefinition={schema_version:1,title:'Production hook board',cards:sources.map((row,index)=>({id:row.cardId,asset:row.reference,position:{x:index*280,y:0}})),viewport:{x:0,y:0,zoom:1}};
 const record={id:'board',version:1,definition,reference_states:sources.map(row=>({card_id:row.cardId,state:'CURRENT_METADATA',filename:row.cardId+'.png'})),execution_authority:false},save=vi.fn(),run=vi.fn();
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'production:hook',canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:f=>f(),mutate:f=>f(),client:{asset:async(id:string)=>{const ref=sources.find(row=>row.reference.asset_id===id)!.reference;return {id,version:ref.version,sha256:ref.digest,kind:'image'};},graphs:{catalog:async()=>modelCatalog(),imageCatalog:async()=>imageGraphCatalog(),list:async()=>({items:[]}),create:save,createRun:run,canvasViews:{list:async()=>({items:[{id:'board',title:definition.title,version:1,card_count:2}]}),get:async()=>record}}} as any};
 function Mounted(){const view=useStudioGraphEditor(props);return <>{view.content}{view.inspector}</>;}render(<Mounted/>);
 await screen.findByLabelText('起步作者输入');fireEvent.click(screen.getByText('读取已存画布'));await screen.findByText('Production hook board · v1 · 2 张');fireEvent.click(screen.getByText('Production hook board · v1 · 2 张'));await screen.findByText('已读取持久化版本');
 fireEvent.click(screen.getByText('明确读取图片节点目录'));await screen.findByLabelText('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核');fireEvent.click(screen.getByLabelText('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核'));fireEvent.click(screen.getByText('明确采用图片图 v4'));
 expect((screen.getByLabelText('画布标题') as HTMLInputElement).disabled).toBe(true);expect((screen.getByLabelText('图片输入 Card_A') as HTMLInputElement).disabled).toBe(false);
 fireEvent.click(screen.getByLabelText('图片输入 Card_A'));fireEvent.click(screen.getByLabelText('图片输入 Card_B'));fireEvent.change(screen.getByLabelText('双参考图作者 Prompt'),{target:{value:request().prompt}});fireEvent.click(screen.getByText('核对两张图片并预览原图'));await screen.findByLabelText('双参考图起步预览');fireEvent.click(screen.getByLabelText('确认仅将预览加入下方本地图片图'));fireEvent.click(screen.getByText('明确建立双参考图片图草稿'));
 expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(7);expect(screen.getByLabelText('原图片图输入与来源').textContent).toContain(request().prompt);expect(save).not.toHaveBeenCalled();expect(run).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('撤销图编辑'));expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);fireEvent.click(screen.getByText('重做图编辑'));expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(7);expect(save).not.toHaveBeenCalled();expect(run).not.toHaveBeenCalled();
});
