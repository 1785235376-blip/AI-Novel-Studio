/** Local module fixture only: synthetic Graph responses, no job/API/CPU/model execution. */
import {useCallback,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {AppShell} from '../../ui/AppShell';
import {CanvasAudioWorkflowTemplatePanel} from './CanvasAudioWorkflowTemplatePanel';
import {AudioTemplateParametersComparison} from './CanvasAudioTemplateParameterComparison';
import {templateGraph,templateOwner} from './canvasAudioWorkflowTemplate.testFixtures';
import type {CanvasAudioTemplateParameters,CanvasAudioWorkflowTemplateRef} from './canvasAudioWorkflowTemplate';
import '../../ui/ui.css';import '../../ui/fixture.css';import '../../ui/desktop-craft.css';import '../creative.css';
const graph=templateGraph();
Object.assign(graph.definition.nodes[1].parameters.parameters!,{gain_db:-6,fade_in_ms:100,fade_out_ms:200});
const original=JSON.stringify(graph),ownerToken={},isCurrent=()=>true;
const data={calls:{list:0,read:0,apply:0},copied:undefined as CanvasAudioWorkflowTemplateRef|undefined,frozen:false,originalUnchanged:true};
const list=async()=>{data.calls.list++;return [graph];};
const read=async()=>{data.calls.read++;return graph;};
function Fixture(){
 const[current,setCurrent]=useState<CanvasAudioTemplateParameters>({in_ms:0,out_ms:1000,gain_db:-3,fade_in_ms:50,fade_out_ms:50});
 const[applied,setApplied]=useState<CanvasAudioTemplateParameters>();
 const onApply=useCallback((ref:CanvasAudioWorkflowTemplateRef)=>{data.calls.apply++;data.copied=ref;data.frozen=Object.isFrozen(ref)&&Object.isFrozen(ref.parameters);data.originalUnchanged=JSON.stringify(graph)===original;setCurrent(value=>({...value,...ref.parameters}));setApplied(ref.parameters);},[]);
 return <AppShell module="AUDIO" onModuleChange={()=>{}} actor="本地模块检查" scope={{workspace:'创作工作区',project:'音频模板效果',storyline:'主线',branch:'合成模块夹具'}}
 sidebar={<p>仅检查原模板选择组件与只读参数对照。Graph 回执为合成数据。</p>}
 main={<div style={{height:'100%',overflow:'auto',minWidth:0}}>
  <CanvasAudioWorkflowTemplatePanel owner={templateOwner} ownerToken={ownerToken} current busy={false} canApply isCurrent={isCurrent} list={list} read={read} onApply={onApply} currentParameters={current}/>
  {applied&&<section aria-label="应用后的本次参数"><h4>源模板与本次局部参数</h4><p>这里只读展示；本夹具不创建、排队或执行任务。</p>
   <label>夹具本次增益<input aria-label="夹具本次增益" type="number" value={current.gain_db??''} onChange={event=>setCurrent(value=>({...value,gain_db:Number(event.target.value)}))}/></label>
   <AudioTemplateParametersComparison templateParameters={applied} currentParameters={current}/></section>}
 </div>}
 inspector={<p>版本固定 · 只复制源明确提供的参数 · 本次覆盖不修改共享模板。</p>} status="模块合成检查；真实 CPU 在父线验证"/>;
}
export function mount(){(window as any).__audioTemplate=data;const host=document.createElement('div');document.body.replaceChildren(host);createRoot(host).render(<Fixture/>);}
