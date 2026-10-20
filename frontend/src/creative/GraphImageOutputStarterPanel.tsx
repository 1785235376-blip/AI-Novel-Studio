import {useLayoutEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import {IMAGE_OUTPUT_COUNTS,type ImageOutputCount,type ImageOutputHandoff,type ImageOutputPlan} from './graphImageOutputStarter';

type Props={owner:object;disabled:boolean;isCurrent:()=>boolean;handoff:ImageOutputHandoff};
type Proof={token:object;revision:number;scope:object;plan:ImageOutputPlan;handoff:ImageOutputHandoff};
export function GraphImageOutputStarterPanel(props:Props){
 const [prompt,setPrompt]=useState(''),[count,setCount]=useState<ImageOutputCount>(2),[supplements,setSupplements]=useState(['','','','']),[proof,setProof]=useState<Proof>(),[checked,setChecked]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [,renderRevision]=useState(0),alive=useRef(true),revision=useRef(0),composing=useRef(false),proofRef=useRef<Proof>(),consent=useRef<Proof>(),input=useRef<HTMLTextAreaElement>(null),countInput=useRef<HTMLSelectElement>(null),extraInputs=useRef<(HTMLTextAreaElement|null)[]>([]),live=useRef(props);live.current=props;
 const values=[props.owner,props.handoff.scope,props.disabled,props.handoff.available],fence=useRef({values,token:{},epoch:0});if(values.some((value,index)=>!Object.is(value,fence.current.values[index])))fence.current={values,token:{},epoch:fence.current.epoch+1};
 const token=fence.current.token,captured=revision.current;
 function retire(){const old=proofRef.current;if(old)old.handoff.cancel(old.plan,old.scope);proofRef.current=undefined;consent.current=undefined;}
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;retire();};},[]);
 useLayoutEffect(()=>{retire();composing.current=false;setProof(undefined);setChecked(false);setError('');},[token]);
 const current=()=>alive.current&&fence.current.token===token&&revision.current===captured&&!live.current.disabled&&live.current.isCurrent()&&live.current.handoff.scope===props.handoff.scope&&live.current.handoff.isCurrent();
 const fieldsMatch=()=>!composing.current&&input.current?.value===prompt&&countInput.current?.value===String(count)&&supplements.slice(0,count).every((text,index)=>extraInputs.current[index]?.value===text);
 function invalidate(){retire();revision.current++;renderRevision(value=>value+1);setProof(undefined);setChecked(false);setError('');setNotice('');}
 const visible=proof?.token===token&&proof.revision===revision.current&&!props.disabled?proof:undefined,disabled=props.disabled||!props.handoff.available;
 return <details><summary>文字起步：2–4个图片产物</summary><section className="studio-graph-inspector" aria-label="文字到多图片产物草稿">
  <p>来源为本地作者文字。每份生成一个原候选，分别通过原Job与人工Review；数量不代表三视图、一致性或不同画面的保证。保存后由原Graph版本固定作者输入。</p>
  <p>当前原图图片生成／处理节点：{props.handoff.existingGenerators}。下方是尚未应用的起步预算；仅用于空白图片图v4。</p>
  <fieldset key={fence.current.epoch} disabled={disabled}><legend>作者输入与数量预算</legend>
   <label>图片产物作者 Prompt<textarea aria-label="图片产物作者 Prompt" ref={input} rows={4} cols={80} maxLength={16000} value={prompt} onChange={event=>{if(current()){invalidate();setPrompt(event.target.value);}}} onCompositionStart={()=>{if(current()){composing.current=true;invalidate();}}} onCompositionEnd={event=>{if(current()){composing.current=false;invalidate();setPrompt(event.currentTarget.value);}}}/></label>
   <label>图片产物数量<select aria-label="图片产物数量" ref={countInput} value={count} onChange={event=>{const value=Number(event.target.value);if(current()&&(value===2||value===3||value===4)){invalidate();setCount(value);}}}>{IMAGE_OUTPUT_COUNTS.map(value=><option key={value} value={value}>{value}张 · {value}个生成节点</option>)}</select></label>
   {supplements.slice(0,count).map((text,index)=><label key={index}>产物{index+1}补充说明（可空）<textarea aria-label={`产物${index+1}补充说明`} ref={element=>{extraInputs.current[index]=element;}} rows={2} cols={80} maxLength={4000} value={text} onChange={event=>{if(current()){invalidate();setSupplements(supplements.map((row,i)=>i===index?event.target.value:row));}}} onCompositionStart={()=>{if(current()){composing.current=true;invalidate();}}} onCompositionEnd={event=>{if(current()){composing.current=false;invalidate();setSupplements(supplements.map((row,i)=>i===index?event.currentTarget.value:row));}}}/></label>)}
  </fieldset>
  <p>拟建立{count}个原生成节点和{count}个审核节点，每轮完整运行至多{count}份原生成任务。原图总上限4个生成／处理节点；不自动派发、并行或重试。</p>
  <Button disabled={disabled||!prompt.trim()||Array.from(prompt).length>8000} onClick={()=>{if(!current()||!fieldsMatch())return;invalidate();try{const plan=props.handoff.preview({prompt,count,supplements:supplements.slice(0,count)},props.handoff.scope),next={token,revision:revision.current,scope:props.handoff.scope,plan,handoff:props.handoff};proofRef.current=next;setProof(next);}catch(reason){setError(reason instanceof Error?reason.message:'未建立产物草稿。');}}}>预览图片产物与数量预算</Button>
  {!props.handoff.available&&<p>请在原入口读取图片目录并明确采用空白图片图；其他未完成表单与已有图保持原样。</p>}
  {visible&&<section aria-label="图片产物数量确认"><p>{visible.plan.count}份产物 · {visible.plan.nodeCount}个原节点 · {visible.plan.edgeCount}条类型连接；provider/model留空，allow_cloud=false。</p><ol>{visible.plan.outputs.map(row=><li key={row.generatorNodeId}>产物{row.number}：<details><summary>核对完整Prompt与原节点</summary><p>{row.prompt}</p><p>{row.inputNodeId} → {row.generatorNodeId} → {row.reviewNodeId}</p></details></li>)}</ol>
   <p>还需在原Inspector配置本地模型、明确Save和预检。原运行先推进所需生成节点，每份分别预览／入队／执行，再按当前审核节点逐一Review；保存后空选区采用全图，后续改变选区请核对原预检范围。失败与UNKNOWN沿用原回执，先读取原运行核对；取消运行可阻止本地后续采用，远端计算可能继续。正式素材仍按原入口明确加入上层并保存。</p>
   <label><input type="checkbox" checked={checked} disabled={disabled} onChange={event=>{if(current()&&proofRef.current===visible){consent.current=event.target.checked?visible:undefined;setChecked(event.target.checked);}}}/>确认{visible.plan.count}份预算，仅建立本地图片产物草稿</label>
   <Button disabled={disabled||!checked} onClick={()=>{if(!current()||!fieldsMatch()||proofRef.current!==visible||consent.current!==visible)return;proofRef.current=undefined;consent.current=undefined;setProof(undefined);setChecked(false);if(props.handoff.apply(visible.plan,visible.scope,()=>current()&&fieldsMatch())){setNotice(`已加入${visible.plan.count}份原图片分支，可一次撤销；尚未保存、入队或执行。`);setPrompt('');setSupplements(['','','','']);}else{props.handoff.cancel(visible.plan,visible.scope);setError('原图、来源输入或权限已变化，未应用；请重新预览。');}}}>明确建立图片产物草稿</Button>
   <Button disabled={disabled} onClick={()=>{if(current()&&proofRef.current===visible){invalidate();setNotice('已取消本次产物预览，原图未改动。');}}}>取消本次产物预览</Button>
  </section>}
  {error&&<StatusMessage tone="warning">{error}</StatusMessage>}{notice&&<StatusMessage>{notice}</StatusMessage>}
 </section></details>;
}
