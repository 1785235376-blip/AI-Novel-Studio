import { useLayoutEffect,useRef,useState } from 'react';
import { Button,StatusMessage } from '../ui/primitives';
import { graphNodeStateImpact } from './graphNodeStateImpact';
import type { StudioGraphCatalogDefinition,StudioGraphDefinition } from './studioGraphTypes';
type Props={nodeId:string;definition:StudioGraphDefinition;definitions:readonly StudioGraphCatalogDefinition[];owner:object;disabled:boolean;isCurrent:()=>boolean;onChange:(definition:StudioGraphDefinition)=>void};
type Candidate=ReturnType<typeof graphNodeStateImpact>&{token:object};
export function GraphNodeStateControl(props:Props){
 const [candidate,setCandidate]=useState<Candidate>(),[confirmed,setConfirmed]=useState(false),[error,setError]=useState('');
 const alive=useRef(true),live=useRef(props),candidateLive=useRef(candidate),consent=useRef(confirmed);live.current=props;candidateLive.current=candidate;consent.current=confirmed;
 const values=[props.definition,props.nodeId,props.owner,props.disabled,JSON.stringify(props.definitions)],fence=useRef({values,token:{}});
 if(values.some((value,index)=>!Object.is(value,fence.current.values[index])))fence.current={values,token:{}};
 const token=fence.current.token,current=()=>alive.current&&fence.current.token===token&&!live.current.disabled&&live.current.isCurrent();
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 useLayoutEffect(()=>{setCandidate(undefined);setConfirmed(false);setError('');},[token]);
 const visible=candidate?.token===token?candidate:undefined;
 function inspect(enabled:boolean){if(!current())return;candidateLive.current=undefined;consent.current=false;setConfirmed(false);setError('');try{setCandidate({...graphNodeStateImpact(props.definition,props.nodeId,enabled,props.definitions),token});}catch{setCandidate(undefined);setError('节点或目录已变化，请重新读取原图。');}}
 function apply(){if(!current()||!visible||candidateLive.current!==visible||!confirmed||!consent.current)return;candidateLive.current=undefined;consent.current=false;setCandidate(undefined);setConfirmed(false);props.onChange(visible.definition);}
 const node=props.definition.nodes.find(value=>value.id===props.nodeId);
 if(!node)return null;
 return <section aria-label="节点启停影响检查"><label><input type="checkbox" checked={node.enabled} disabled={props.disabled} onChange={event=>inspect(event.target.checked)}/>启用当前节点</label>
  {visible&&<section aria-label="节点状态影响预览"><h4>{visible.enabled?'启用':'停用'} {visible.nodeId} 的结构影响</h4>
   <p>当前节点及可达下游：{visible.affected.join('、')||'无'}。</p><p>新增缺少的必需输入：{visible.newMissing.join('、')||'无'}。</p><p>变更后仍缺少的必需输入：{visible.remainingMissing.join('、')||'无'}。</p>
   <p>只修改本地草稿中的启用状态，保留节点参数、连接、资产和历史。保存后仍须按原流程预览与审核，不会启动或停止已有任务。这里不判断模型语义或费用。</p>
   <label><input type="checkbox" checked={confirmed} disabled={props.disabled} onChange={event=>{if(current()&&candidateLive.current===visible){consent.current=event.target.checked;setConfirmed(event.target.checked);}}}/>已核对影响，确认修改节点状态</label>
   <Button disabled={props.disabled||!confirmed} onClick={apply}>确认状态变更到本地草稿</Button><Button onClick={()=>{if(current()){candidateLive.current=undefined;consent.current=false;setCandidate(undefined);setConfirmed(false);}}}>保持原状态</Button>
  </section>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}
 </section>;
}
