import { useLayoutEffect,useRef,useState } from 'react';
import { Button,StatusMessage } from '../ui/primitives';
import { graphDisconnectImpact } from './graphDisconnectImpact';
import type { StudioGraphCatalogDefinition,StudioGraphDefinition } from './studioGraphTypes';
type Props={definition:StudioGraphDefinition;definitions:readonly StudioGraphCatalogDefinition[];owner:object;disabled:boolean;isCurrent:()=>boolean;onChange:(definition:StudioGraphDefinition)=>void};
type Candidate=ReturnType<typeof graphDisconnectImpact>&{token:object};
export function GraphConnectionList(props:Props){
 const [candidate,setCandidate]=useState<Candidate>(),[confirmed,setConfirmed]=useState(false),[error,setError]=useState('');
 const alive=useRef(true),live=useRef(props),candidateLive=useRef(candidate),consent=useRef(confirmed);live.current=props;candidateLive.current=candidate;consent.current=confirmed;
 const values=[props.definition,props.owner,props.disabled,JSON.stringify(props.definitions)],fence=useRef({values,token:{}});
 if(values.some((value,index)=>!Object.is(value,fence.current.values[index])))fence.current={values,token:{}};
 const token=fence.current.token,current=()=>alive.current&&fence.current.token===token&&!live.current.disabled&&live.current.isCurrent();
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 useLayoutEffect(()=>{setCandidate(undefined);setConfirmed(false);setError('');},[token]);
 const visible=candidate?.token===token?candidate:undefined;
 function inspect(id:string){if(!current())return;candidateLive.current=undefined;consent.current=false;setConfirmed(false);setError('');try{setCandidate({...graphDisconnectImpact(props.definition,id,props.definitions),token});}catch{setCandidate(undefined);setError('连接或节点目录已变化，请重新读取原图。');}}
 function apply(){if(!current()||!visible||candidateLive.current!==visible||!confirmed||!consent.current)return;candidateLive.current=undefined;consent.current=false;setCandidate(undefined);setConfirmed(false);props.onChange(visible.definition);}
 return <section aria-label="图连接列表"><h3>已保存到草稿的连接</h3>{!props.definition.edges.length&&<p>暂无连接；不相连节点可以独立保存。</p>}<ul>{props.definition.edges.map(edge=><li key={edge.id}>{edge.source_node_id}.{edge.source_port} → {edge.target_node_id}.{edge.target_port}<Button disabled={props.disabled} onClick={()=>inspect(edge.id)}>移除连接 {edge.id}</Button></li>)}</ul>
  {visible&&<section aria-label="断开连接影响预览"><h4>断开 {visible.edge.id} 的结构影响</h4><p>目标及可达下游：{visible.affected.join('、')||'无'}。</p><p>新增缺少的必需输入：{visible.newMissing.join('、')||'无'}。</p><p>不在该下游路径中的节点：{visible.unaffected.join('、')||'无'}。</p><p>仅从本地草稿移除这一条连接，不删除任何节点、原素材、文档或运行历史。可一次撤销；保存和再次运行仍走原流程。这里不判断模型语义或费用。</p>
   <label><input type="checkbox" checked={confirmed} disabled={props.disabled} onChange={event=>{if(current()&&candidateLive.current===visible){consent.current=event.target.checked;setConfirmed(event.target.checked);}}}/>已核对下游影响，确认只断开此连接</label>
   <Button disabled={props.disabled||!confirmed} onClick={apply}>确认断开到本地草稿</Button><Button onClick={()=>{if(current()){candidateLive.current=undefined;consent.current=false;setCandidate(undefined);setConfirmed(false);}}}>保留原连接</Button>
  </section>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}
 </section>;
}
