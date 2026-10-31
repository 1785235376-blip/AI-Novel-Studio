import {useLayoutEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import {verifyCanvasGraphAsset} from './mediaCanvasGraphHandoffHelpers';
import {IMAGE_REFERENCE_PURPOSES,IMAGE_REFERENCE_PURPOSE_LABELS,type ImageReferencePurpose} from './studioImageRuntimeContract';
import type {CanvasAssetReference} from './studioCanvasViewClient';
import type {StudioClient} from './studioClient';
import type {CanvasImageGraphHandoff,CanvasImageGraphPlan,CanvasImageGraphRequest} from './canvasImageGraphStarter';
type Source={cardId:string;reference:CanvasAssetReference};
type Props={sources:Source[];owner:object;disabled:boolean;isCurrent:()=>boolean;client:Pick<StudioClient,'asset'>;read:<T>(work:()=>Promise<T>)=>Promise<T>;handoff:CanvasImageGraphHandoff};
type Proof={token:object;revision:number;scope:object;plan:CanvasImageGraphPlan};
export function MediaCanvasImageGraphStarter(props:Props){
 const [text,setText]=useState(''),[settings,setSettings]=useState<Record<string,{weight:string;purpose:ImageReferencePurpose}>>({}),[proof,setProof]=useState<Proof>(),[checked,setChecked]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [,renderRevision]=useState(0),alive=useRef(true),running=useRef(false),ticket=useRef(0),revision=useRef(0),composing=useRef(false),consent=useRef<Proof>(),proofRef=useRef(proof),input=useRef<HTMLTextAreaElement>(null);
 proofRef.current=proof;const fields=useRef(new Map<string,{weight:HTMLInputElement|null;purpose:HTMLSelectElement|null}>()),live=useRef(props);live.current=props;
 const values=[props.owner,props.handoff.scope,props.disabled,JSON.stringify(props.sources)],fence=useRef({values,token:{},epoch:0});if(values.some((value,index)=>!Object.is(value,fence.current.values[index])))fence.current={values,token:{},epoch:fence.current.epoch+1};
 const token=fence.current.token,renderedRevision=revision.current;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;ticket.current++;consent.current=undefined;};},[]);
 useLayoutEffect(()=>{ticket.current++;composing.current=false;consent.current=undefined;proofRef.current=undefined;setProof(undefined);setChecked(false);setError('');},[token]);
 const current=()=>alive.current&&fence.current.token===token&&!live.current.disabled&&live.current.isCurrent()&&live.current.handoff.isCurrent()&&revision.current===renderedRevision;
 const setting=(id:string)=>settings[id]||{weight:'1',purpose:'composition' as const};
 const fieldsMatch=()=>!composing.current&&input.current?.value===text&&props.sources.every(row=>{const dom=fields.current.get(row.cardId),value=setting(row.cardId);return dom?.weight?.value===value.weight&&dom.purpose?.value===value.purpose;});
 function invalidate(){revision.current++;renderRevision(value=>value+1);ticket.current++;consent.current=undefined;proofRef.current=undefined;setProof(undefined);setChecked(false);setError('');}
 async function inspect(){
  if(!current()||running.current||!fieldsMatch()||props.sources.length!==2||!props.handoff.available)return;invalidate();const request=++ticket.current,scope=props.handoff.scope;running.current=true;setLoading(true);setNotice('');
  const captured:CanvasImageGraphRequest={prompt:text,sources:props.sources.map(row=>({...structuredClone(row),weight:Number(setting(row.cardId).weight),purpose:setting(row.cardId).purpose}))};
  try{const assets=await props.read(()=>Promise.all(captured.sources.map(row=>props.client.asset(row.reference.asset_id))));
   if(!alive.current||fence.current.token!==token||ticket.current!==request||!live.current.isCurrent()||!live.current.handoff.isCurrent())return;
   captured.sources.forEach((row,index)=>verifyCanvasGraphAsset(assets[index],row.reference));
   const plan=props.handoff.preview(captured,scope);const next={token,revision:revision.current,scope,plan};proofRef.current=next;setProof(next);
  }catch(reason){if(alive.current&&fence.current.token===token&&ticket.current===request)setError(reason instanceof Error?reason.message:'引用或目标核对失败。');}
  finally{running.current=false;if(alive.current)setLoading(false);}
 }
 const visible=proof?.token===token&&proof.revision===revision.current&&!props.disabled?proof:undefined;
 const disabled=props.disabled||loading||!props.handoff.available;
 return <section className="studio-graph-inspector" aria-label="双参考图与Prompt交接"><h4>两张参考图＋作者 Prompt</h4>
  <p>先保存上层画布并明确选择两张图片，在下方原图进入空白图片图 v4。这里只建立原图节点，不保存或执行生成。</p>
  {props.sources.map((row,index)=><div key={row.cardId}><p>参考 {index+1}：{row.cardId} · {row.reference.asset_id} · v{row.reference.version}</p>
   <label>参考 {index+1} 用途<select aria-label={`参考 ${index+1} 用途`} disabled={disabled} value={setting(row.cardId).purpose} ref={element=>{const item=fields.current.get(row.cardId)||{weight:null,purpose:null};item.purpose=element;fields.current.set(row.cardId,item);}} onChange={event=>{if(!current())return;invalidate();setSettings({...settings,[row.cardId]:{...setting(row.cardId),purpose:event.target.value as ImageReferencePurpose}});}}>{IMAGE_REFERENCE_PURPOSES.map(purpose=><option key={purpose} value={purpose}>{IMAGE_REFERENCE_PURPOSE_LABELS[purpose]}</option>)}</select></label>
   <label>参考 {index+1} 权重（大于0且不超过1）<input aria-label={`参考 ${index+1} 权重`} type="number" min="0" max="1" step="0.05" disabled={disabled} value={setting(row.cardId).weight} ref={element=>{const item=fields.current.get(row.cardId)||{weight:null,purpose:null};item.weight=element;fields.current.set(row.cardId,item);}} onChange={event=>{if(!current())return;invalidate();setSettings({...settings,[row.cardId]:{...setting(row.cardId),weight:event.target.value}});}}/></label>
  </div>)}
  <label>双参考图作者 Prompt<textarea aria-label="双参考图作者 Prompt" key={fence.current.epoch} ref={input} disabled={disabled} maxLength={16000} rows={4} cols={80} value={text} onChange={event=>{if(current()){invalidate();setText(event.target.value);}}} onCompositionStart={()=>{if(current()){composing.current=true;invalidate();}}} onCompositionEnd={event=>{if(current()){composing.current=false;invalidate();setText(event.currentTarget.value);}}}/></label>
  <p>{Array.from(text).length} / 8000 字符。输入确认后只写入原图的 text_input；未应用的输入不属于已保存图。用途是作者标签，元数据核对不代表已验证像素、模型可运行或一致性效果。</p>
  <Button disabled={disabled||props.sources.length!==2||!text.trim()||Array.from(text).length>8000} onClick={()=>void inspect()}>核对两张图片并预览原图</Button>
  {!props.handoff.available&&<p>请使用原图入口读取图片目录并明确进入空白图片图；已有节点或其他未完成表单不会被覆盖。</p>}
  {loading&&<StatusMessage>正在核对两份原素材元数据…</StatusMessage>}
  {visible&&<section aria-label="双参考图起步预览"><p>{visible.plan.nodeCount} 个原节点、{visible.plan.edgeCount} 条类型连线；生成一个候选，保留原人工审核节点。</p><p>作者 Prompt：{visible.plan.prompt}</p>
   <ol>{visible.plan.sources.map(row=><li key={row.cardId}>{row.cardId} → {row.nodeId} · {row.reference.asset_id} · v{row.reference.version} · {IMAGE_REFERENCE_PURPOSE_LABELS[row.purpose]} · 权重 {row.weight}<details><summary>固定版本摘要</summary><code>{row.reference.digest}</code></details></li>)}</ol>
   <p>服务商和模型保持未配置，allow_cloud=false。配置后才能原保存、预检、明确运行及审核；来源版本仍由原流程复核。</p>
   <label><input type="checkbox" checked={checked} disabled={disabled} onChange={event=>{if(current()&&proofRef.current===visible){consent.current=event.target.checked?visible:undefined;setChecked(event.target.checked);}}}/>确认仅将预览加入下方本地图片图</label>
   <Button disabled={disabled||!checked} onClick={()=>{if(!current()||!fieldsMatch()||proofRef.current!==visible||consent.current!==visible)return;consent.current=undefined;proofRef.current=undefined;setProof(undefined);setChecked(false);ticket.current++;if(props.handoff.apply(visible.plan,visible.scope,()=>current()&&fieldsMatch())){setText('');setNotice('已加入同一原图草稿，可一次撤销。尚未保存或执行。');}else setError('来源、图或权限已变化，未应用；请重新核对。');}}>明确建立双参考图片图草稿</Button>
  </section>}
  {error&&<StatusMessage tone="warning">{error}</StatusMessage>}{notice&&<StatusMessage>{notice}</StatusMessage>}
  {!!props.handoff.graph.prompts.length&&<section aria-label="原图片图输入与来源"><p>原图：{props.handoff.graph.title} · {props.handoff.graph.id?`${props.handoff.graph.id} · v${props.handoff.graph.version}`:'尚未保存'}</p>
   {props.handoff.graph.prompts.map(row=><details key={row.nodeId}><summary>原 Prompt 节点 {row.nodeId}</summary><p>{row.text}</p><Button disabled={props.disabled||!props.handoff.isCurrent()} onClick={()=>props.handoff.focusPrompt(row.nodeId,props.handoff.scope)}>定位此原图文字节点</Button></details>)}
   <details><summary>原图固定版本图片来源</summary>{props.handoff.graph.references.map(row=><p key={row.nodeId}>{row.nodeId} · {row.reference.asset_id} · v{row.reference.version}<code>{row.reference.digest}</code></p>)}</details>
   <p>生成候选须先走原 Job/Review，成为正式素材后再用上方“读取可用素材／加入引用卡片”明确接回，分别保存两层；不自动回接或重复发送任务。</p>
  </section>}
 </section>;
}
