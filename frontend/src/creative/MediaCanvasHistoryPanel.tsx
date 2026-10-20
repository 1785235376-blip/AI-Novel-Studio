import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { CanvasViewClient, CanvasViewHistory, CanvasViewRecord } from './studioCanvasViewClient';
type Receipt={token:object;history:CanvasViewHistory};
export function MediaCanvasHistoryPanel(props:{base:CanvasViewRecord;client:CanvasViewClient;owner:object;incarnation?:string;canMutate:boolean;externalDirty:boolean;busy:boolean;isBusy?:()=>boolean;
  isCurrent:()=>boolean;read:<T>(f:()=>Promise<T>)=>Promise<T>;mutate:<T>(f:()=>Promise<T>)=>Promise<T>;onAdopt:(row:CanvasViewRecord)=>void;onUncertain:()=>void}){
  const [receipt,setReceipt]=useState<Receipt>(),[version,setVersion]=useState(0),[consent,setConsent]=useState(false),[pending,setPending]=useState(false),[uncertain,setUncertain]=useState(false),[error,setError]=useState('');
  const alive=useRef(true),running=useRef(false),live=useRef(props),receiptRef=useRef(receipt),approval=useRef<{receipt:Receipt;version:number}>();live.current=props;receiptRef.current=receipt;
  const values=[props.owner,props.client,props.base.id,props.base.version,props.base.definition_digest,JSON.stringify(props.base.scope),props.incarnation,props.canMutate,props.externalDirty];
  const fence=useRef({values,token:{}});if(values.some((v,i)=>!Object.is(v,fence.current.values[i])))fence.current={values,token:{}};
  const token=fence.current.token,current=()=>alive.current&&fence.current.token===token&&live.current.isCurrent()&&!live.current.externalDirty;
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const visible=receipt?.token===token?receipt:undefined,target=visible?.history.items.find(row=>row.version===version);
  const busy=pending||props.busy||!!props.isBusy?.(),canRestore=current()&&props.canMutate&&!busy&&!uncertain&&!!props.incarnation&&visible?.history.incarnation===props.incarnation&&target?.can_restore===true;
  async function load(){
    if(!current()||running.current||props.busy||props.isBusy?.())return;running.current=true;setPending(true);setError('');setReceipt(undefined);receiptRef.current=undefined;approval.current=undefined;setConsent(false);setVersion(0);
    try{const value=await props.read(()=>props.client.history(props.base.id));
      if(!current())return;
      if(value.project_id!==props.base.project_id||JSON.stringify(value.scope)!==JSON.stringify(props.base.scope)||value.id!==props.base.id||value.current_version!==props.base.version||value.current_definition_digest!==props.base.definition_digest
        ||props.incarnation&&value.incarnation!==props.incarnation)throw new Error('画布版本、范围或项目代次已改变，请重新读取当前画布。');
      setReceipt({token,history:structuredClone(value)});
    }catch(reason){if(current())setError(reason instanceof Error?reason.message:'历史读取失败。');}
    finally{running.current=false;if(alive.current)setPending(false);}
  }
  async function restore(){
    const proof=visible,chosen=target,approved=approval.current;
    if(!current()||!canRestore||running.current||!proof||receiptRef.current!==proof||!chosen||!consent||approved?.receipt!==proof||approved.version!==chosen.version||live.current.incarnation!==proof.history.incarnation)return;
    const captured=structuredClone(proof.history),capturedIncarnation=proof.history.incarnation;running.current=true;setPending(true);approval.current=undefined;receiptRef.current=undefined;setReceipt(undefined);setConsent(false);
    try{const row=await props.mutate(()=>props.client.restore(captured,chosen.version));
      if(current()&&live.current.incarnation===capturedIncarnation){props.onAdopt(row);}
      else if(alive.current){setUncertain(true);props.onUncertain();setError('恢复期间原范围或代次改变，结果待核对；不会重试。');}
    }catch(reason){if(alive.current){setUncertain(true);props.onUncertain();setError('恢复结果待核对，请重新读取当前画布。'+(reason instanceof Error?reason.message:''));}}
    finally{running.current=false;if(alive.current)setPending(false);}
  }
  return <details><summary>画布版本历史与恢复</summary><section aria-label="持久画布版本历史">
    <p>读取原画布 row 的版本历史。恢复会创建新当前版本，保留原历史与素材 pin；不会回滚或读取历史二进制，也不会自动换成最新素材。</p>
    <Button disabled={busy||props.externalDirty} onClick={()=>void load()}>读取画布版本历史</Button>
    {visible&&<><p>当前 v{visible.history.current_version} · 历史 {visible.history.items.length} 项。</p>
      <label>待恢复画布版本<select aria-label="待恢复画布版本" value={version||''} disabled={busy} onChange={e=>{if(current()){approval.current=undefined;setConsent(false);setVersion(Number(e.target.value));}}}>
        <option value="">明确选择历史版本</option>{visible.history.items.map(row=><option key={row.version} value={row.version} disabled={!row.can_restore}>v{row.version} · {row.definition.cards.length} 卡片 · {row.can_restore?'可核对恢复':row.version===visible.history.current_version?'当前版本':'来源过期或不可用'}</option>)}
      </select></label>
      {target&&<><p>将 v{target.version} 的布局与原资产引用保存成新 v{visible.history.current_version+1}。仅此画布；原任务不重发，旧选择、预览与回流意图退役。</p>
        <label><input type="checkbox" disabled={!canRestore} checked={consent} onChange={e=>{if(current()&&visible===receiptRef.current){approval.current=e.target.checked?{receipt:visible,version:target.version}:undefined;setConsent(e.target.checked);}}}/>确认创建新的当前版本并退役旧预览</label>
        <Button disabled={!canRestore||!consent} onClick={()=>void restore()}>恢复此画布版本为新版本</Button></>}
    </>}
    {!props.incarnation&&<p>当前上下文未提供项目代次，历史仅供查看；请先从原项目入口重新核对，不能猜测恢复代次。</p>}
    {error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  </section></details>;
}
