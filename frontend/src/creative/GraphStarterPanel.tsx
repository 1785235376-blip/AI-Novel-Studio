import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { GRAPH_STARTERS, buildGraphStarter, graphStarterAvailable, type GraphStarterKind } from './graphStarter';
import type { StudioGraphCatalog, StudioGraphDefinition } from './studioGraphTypes';
type Props={draft:StudioGraphDefinition;catalog:StudioGraphCatalog;scope:object;disabled:boolean;onApply:(kind:GraphStarterKind,text:string,scope:object)=>boolean};
export function GraphStarterPanel(props:Props){
 const [kind,setKind]=useState<GraphStarterKind>('manual-text'),[text,setText]=useState(''),[error,setError]=useState('');
 const [preview,setPreview]=useState<{scope:object;revision:number;draft:StudioGraphDefinition}>();
 const live=useRef(props);live.current=props;const alive=useRef(true),revision=useRef(0),composing=useRef(false),input=useRef<HTMLTextAreaElement>(null),consumed=useRef<object>();
 const [,renderRevision]=useState(0);const captured=revision.current;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const active=()=>alive.current&&!live.current.disabled&&live.current.scope===props.scope&&live.current.draft===props.draft&&revision.current===captured;
 const invalidate=()=>{revision.current++;renderRevision(revision.current);setPreview(undefined);setError('');};
 const visible=preview&&preview.scope===props.scope&&preview.revision===revision.current&&!props.disabled?preview:undefined;
 return <section aria-label="空图起步方案"><h3>先搭好连接，再逐步配置</h3><p>仅用于空图。方案生成普通节点和连接，可按原方式编辑、撤销和保存；不会启动模型、选择服务商或给予云端授权。</p>
  <label>画布起步方案<select value={kind} disabled={props.disabled} onChange={event=>{if(active()){invalidate();setKind(event.target.value as GraphStarterKind);}}}>{GRAPH_STARTERS.map(row=><option key={row.id} value={row.id} disabled={!graphStarterAvailable(row.id,props.draft,props.catalog)}>{row.label}</option>)}</select></label>
  <label>起步作者输入<textarea ref={input} value={text} maxLength={16000} disabled={props.disabled} onChange={event=>{if(active()){invalidate();setText(event.target.value);}}} onCompositionStart={()=>{composing.current=true;invalidate();}} onCompositionEnd={event=>{composing.current=false;invalidate();setText(event.currentTarget.value);}}/></label>
  <Button disabled={props.disabled||!text.trim()||!graphStarterAvailable(kind,props.draft,props.catalog)} onClick={()=>{if(!active()||composing.current||input.current?.value!==text)return;invalidate();try{setPreview({scope:props.scope,revision:revision.current,draft:buildGraphStarter(props.draft,props.catalog,kind,text)});}catch(reason){setError(reason instanceof Error?reason.message:'无法准备起步方案。');}}}>预览起步节点与连接</Button>
  {error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  {visible&&<section aria-label="起步方案预览"><p>{visible.draft.nodes.map(row=>row.definition_id).join(' → ')}；{visible.draft.edges.length} 条已核对类型的连接。</p><p>模型方案仍需使用原设置明确选择模型并核对来源、预算和运行；文生图的服务商和模型留空，配置完整后才能保存，人工审核节点保留。</p><Button disabled={props.disabled} onClick={()=>{if(!active()||composing.current||input.current?.value!==text||consumed.current===visible)return;consumed.current=visible;invalidate();if(!props.onApply(kind,text,props.scope))setError('当前图或权限已变化，未应用；请重新预览。');}}>应用起步方案到本地空图</Button></section>}
 </section>;
}
