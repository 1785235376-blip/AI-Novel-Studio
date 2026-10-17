import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import { graphDraftChecklist } from './graphDraftChecklist';
import type { StudioGraphCatalogDefinition, StudioGraphDefinition } from './studioGraphTypes';
type Props={draft:StudioGraphDefinition;catalog:readonly StudioGraphCatalogDefinition[];scope:object;disabled:boolean;onSelect:(ids:string[])=>void};
export function GraphDraftChecklist(props:Props){
 const result=useMemo(()=>graphDraftChecklist(props.draft,props.catalog),[props.draft,props.catalog]);
 const [page,setPage]=useState(0),alive=useRef(true);
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const values=[props.draft,props.catalog,props.scope,props.disabled];
 const owner=useRef({values,token:{}});if(values.some((value,index)=>value!==owner.current.values[index]))owner.current={values,token:{}};
 const token=owner.current.token,live=useRef(props);live.current=props;
 const current=()=>alive.current&&!live.current.disabled&&owner.current.token===token;
 useLayoutEffect(()=>setPage(0),[props.draft,props.catalog,props.scope]);
 const pages=Math.max(1,Math.ceil(result.hints.length/20)),activePage=Math.min(page,pages-1);
 return <details aria-label="创作图本地配置清单"><summary>配置清单 · {result.hints.length} 项提示</summary>
  <StatusMessage tone={result.contractValid?'info':'warning'}>{result.contractValid?'原客户端格式检查通过。':'当前草稿尚未通过原客户端格式检查；请先补齐参数、来源或连接。'}</StatusMessage>
  <p>这里只检查当前本地草稿。来源权限、版本、预算、模型可用性和实际执行仍由原服务核对；没有发送请求或运行任务。</p>
  {result.hints.length===0&&<p>未发现已覆盖的配置提示；这不代表可以执行或已完成验收。</p>}
  <ul>{result.hints.slice(activePage*20,activePage*20+20).map(hint=>{
   const node=props.draft.nodes.find(row=>row.id===hint.nodeId);
   return <li key={hint.key}>{hint.kind==='execution'?'运行准备':hint.kind==='connection'?'连接':'参数'} · {node?GRAPH_NODE_LABELS[node.definition_id]:'图'}：{hint.message}{node&&<Button disabled={props.disabled} onClick={()=>{if(current()&&live.current.draft.nodes.some(row=>row.id===node.id))props.onSelect([node.id]);}}>定位节点 {node.id}</Button>}</li>;
  })}</ul>
  {pages>1&&<div><Button disabled={props.disabled||activePage===0} onClick={()=>{if(current())setPage(activePage-1);}}>上一页配置提示</Button><span>{activePage+1} / {pages}</span><Button disabled={props.disabled||activePage===pages-1} onClick={()=>{if(current())setPage(activePage+1);}}>下一页配置提示</Button></div>}
 </details>;
}
