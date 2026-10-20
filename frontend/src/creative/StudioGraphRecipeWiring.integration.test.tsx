// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {StudioGraphMediaExecutionPanel} from './StudioGraphMediaExecutionPanel';
import {imageGraphRecord,imageGraphRun} from './studioImageGraph.testFixtures';
import type {StudioGraphMediaExecutionProps} from './useStudioGraphMediaExecution';
afterEach(cleanup);
function recipe(name='recorded-model.safetensors'){return {contract:'studio-execution-recipe/1',operation_id:'m5.image.reference',adapter:'COMFYUI_BUILTIN_IMAGE',recipe_digest:'a'.repeat(64),automatic_fallback:false,workflow:{'1':{class_type:'CheckpointLoaderSimple',inputs:{ckpt_name:name}}}};}
function mediaNode(id='generate',name='recorded-model.safetensors'){return {node_id:id,status:'PREVIEWED',execution:null,preview:{preview_digest:'c'.repeat(64),command:{operation_id:'m5.image.reference',prompt:'Saved author prompt',source_snapshots:[]},production_preview:{operation_id:'m5.image.reference',request_digest:'d'.repeat(64),execution_recipe:recipe(name),execution_available:true,provider:{provider_id:'saved-provider',model_id:'saved-model',local:true,route_digest:'e'.repeat(64)}}}};}
function fixture(){const graph=imageGraphRecord(),run={...imageGraphRun(),media_runtime:{nodes:[mediaNode()]}};const client={previewMedia:vi.fn(),dispatchMedia:vi.fn(),executeMedia:vi.fn(),refreshMedia:vi.fn(),reconcileMedia:vi.fn(),reviewMedia:vi.fn()},perform=vi.fn();
 const props:StudioGraphMediaExecutionProps={client:client as any,graph,run:run as any,locked:false,canMutate:true,canReview:true,uncertain:false,isCurrent:()=>true,read:f=>f(),perform,onUnavailable:vi.fn()};return {props,client,perform,graph,run};}
it('passes the original current preview recipe without a request or synthetic provider/model claims',()=>{const f=fixture();render(<StudioGraphMediaExecutionPanel {...f.props}/>);expect(screen.getByLabelText('执行配方说明').textContent).toContain('recorded-model.safetensors');expect(screen.getByLabelText('执行配方说明').textContent).toContain('执行未验证');expect(screen.getByLabelText('执行配方说明').textContent).not.toContain('saved-provider');expect(f.perform).not.toHaveBeenCalled();for(const fn of Object.values(f.client))expect(fn).not.toHaveBeenCalled();});
it.each(['scope','graph version','run stale','locked','uncertain','operation mismatch'])('hides structured and raw recipe when original %s is no longer current',mode=>{
 const f=fixture(),view=render(<StudioGraphMediaExecutionPanel {...f.props}/>);expect(screen.getByLabelText('执行配方说明')).toBeTruthy();
 const next={...f.props};if(mode==='scope')next.isCurrent=()=>false;if(mode==='graph version')next.graph={...f.graph,version:f.graph.version+1};if(mode==='run stale')next.run={...f.props.run!,stale:true};if(mode==='locked')next.locked=true;if(mode==='uncertain')next.uncertain=true;if(mode==='operation mismatch'){next.graph=structuredClone(f.graph);next.graph.definition.nodes.find(row=>row.id==='generate')!.parameters.operation_id='m5.image.t2i';}
 view.rerender(<StudioGraphMediaExecutionPanel {...next}/>);expect(screen.queryByLabelText('执行配方说明')).toBeNull();expect(screen.queryByText('核对执行接口和工作流')).toBeNull();expect(document.body.textContent).not.toContain('recorded-model.safetensors');expect(f.perform).not.toHaveBeenCalled();
});
it('changes explanation with the original selected media node and removes the previous node recipe',()=>{
 const f=fixture(),graph=structuredClone(f.graph);graph.definition.nodes.push({...structuredClone(graph.definition.nodes.find(row=>row.id==='generate')!),id:'second'});const run={...f.run,media_runtime:{nodes:[mediaNode(),mediaNode('second','second-model.safetensors')]}};
 render(<StudioGraphMediaExecutionPanel {...f.props} graph={graph} run={run as any}/>);fireEvent.change(screen.getByLabelText('媒体节点'),{target:{value:'second'}});expect(screen.getByLabelText('执行配方说明').textContent).toContain('second-model.safetensors');expect(document.body.textContent).not.toContain('recorded-model.safetensors');expect(f.perform).not.toHaveBeenCalled();
});
it('keeps the original preview explanation after dispatch without inventing a recipe on the narrow Graph Job projection',()=>{
 const f=fixture(),node=mediaNode();node.execution={owner:'image',status:'QUEUED',job_id:'original-job',receipt_state:'RECORDED',send_reserved:false,job:{id:'original-job',version:1,status:'QUEUED',request_digest:'f'.repeat(64)}} as any;
 const view=render(<StudioGraphMediaExecutionPanel {...f.props} run={{...f.run,media_runtime:{nodes:[node]}} as any}/>);expect(screen.getByLabelText('执行配方说明').textContent).toContain('recorded-model.safetensors');
 view.rerender(<StudioGraphMediaExecutionPanel {...f.props} run={{...f.run,media_runtime:{nodes:[{...node,preview:null}]}} as any}/>);expect(screen.getByLabelText('执行配方说明').textContent).toContain('执行配方不可用');expect(document.body.textContent).not.toContain('recorded-model.safetensors');expect(f.perform).not.toHaveBeenCalled();for(const fn of Object.values(f.client))expect(fn).not.toHaveBeenCalled();
});
