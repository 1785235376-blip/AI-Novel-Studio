import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { replaceCanvasImageTaskResult, type CanvasImageTaskSession } from './canvasImageTask';
import type { StudioClient, StudioAsset } from './studioClient';
import type { CanvasViewRecord } from './studioCanvasViewClient';
import type { ProductionJob, StudioProductionClient } from './studioProductionClient';
import { sameCanvasReturnScope } from './studioCanvasReturnBinding';
type Proof={token:object;canvas:CanvasViewRecord;job:ProductionJob;asset:StudioAsset};
export function CanvasImageTaskReturn(props:{task:CanvasImageTaskSession;approved:ProductionJob;client:StudioClient;production:StudioProductionClient;
  disabled:boolean;canMutate:boolean;isCurrent:()=>boolean;read:<T>(f:()=>Promise<T>)=>Promise<T>;mutate:<T>(f:()=>Promise<T>)=>Promise<T>;
  onAdopt:(row:CanvasViewRecord)=>void;onUncertain:()=>void;onComplete:()=>void}) {
  const [proof,setProof]=useState<Proof>(),[consent,setConsent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false);
  const alive=useRef(true),running=useRef(false),live=useRef(props),proofRef=useRef(proof),approvedRef=useRef<Proof>();live.current=props;proofRef.current=proof;
  const values=[props.task,props.approved,props.client,props.production,props.canMutate],fence=useRef({values,token:{}});
  if(values.some((v,i)=>!Object.is(v,fence.current.values[i])))fence.current={values,token:{}};
  const token=fence.current.token,current=()=>alive.current&&token===fence.current.token&&live.current.canMutate&&live.current.isCurrent()&&live.current.task.isOriginCurrent();
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const visible=proof?.token===token?proof:undefined;
  async function inspect(){
    if(!current()||running.current||props.disabled||uncertain)return;running.current=true;setBusy(true);setError('');proofRef.current=undefined;approvedRef.current=undefined;setProof(undefined);setConsent(false);
    try{
      const value=await props.read(async()=>{
        const job=await props.production.get('image',props.approved.id);
        if(!current())throw new Error('原审核任务读取已退役。');
        if(job.request_digest!==props.approved.request_digest||job.version!==props.approved.version||!job.output_candidate)throw new Error('原审核任务版本已改变。');
        const asset=await props.client.asset(job.output_candidate.id);if(!current())throw new Error('正式素材读取已退役。');
        const canvas=await props.client.graphs.canvasViews!.get(props.task.origin.canvasId);if(!current())throw new Error('原位置读取已退役。');
        const binding=props.task.origin.binding;
        if(binding){const history=await props.client.graphs.canvasViews!.history(binding.canvas_id);
          if(!sameCanvasReturnScope(binding,canvas.project_id,canvas.scope,history.incarnation)||history.current_version!==canvas.version||history.current_definition_digest!==canvas.definition_digest)throw new Error('原项目代次、范围或画布版本已改变，不能采用。');}
        replaceCanvasImageTaskResult(props.task.origin,canvas,job,asset);return {token,canvas,job,asset};
      });
      if(current())setProof(value);
    }catch(reason){if(current())setError(reason instanceof Error?reason.message:'原位置或正式结果未通过核验。');}
    finally{running.current=false;if(alive.current)setBusy(false);}
  }
  async function apply(){
    if(!current()||running.current||props.disabled||uncertain||!visible||proofRef.current!==visible||approvedRef.current!==visible||!consent)return;
    running.current=true;setBusy(true);proofRef.current=undefined;approvedRef.current=undefined;setProof(undefined);setConsent(false);
    try{
      const definition=replaceCanvasImageTaskResult(props.task.origin,visible.canvas,visible.job,visible.asset);
      const binding=props.task.origin.binding;
      const row=await props.mutate(()=>props.client.graphs.canvasViews!.save(visible.canvas.id,visible.canvas.version,definition,binding?{expected_incarnation:binding.incarnation,expected_definition_digest:binding.canvas_digest,expected_card:{card_id:binding.card_id,source:props.task.origin.source}}:undefined));
      if(current()){props.onAdopt(row);props.onComplete();}
      else if(alive.current){setUncertain(true);props.onUncertain();setError('原位置或权限在回填期间改变，保存结果待核对。请重新读取原画布，不会重试。');}
    }catch(reason){setUncertain(true);props.onUncertain();if(alive.current)setError('回填结果待核对，请重新读取原画布；不会自动重试。'+(reason instanceof Error?reason.message:''));}
    finally{running.current=false;if(alive.current)setBusy(false);}
  }
  return <section aria-label="审核结果回到原作品位置"><h4>采用到原卡片</h4>
    <p>审核已入库。目标固定为画布 <code>{props.task.origin.canvasId}</code> · v{props.task.origin.canvasVersion}，卡片 <code>{props.task.origin.cardId}</code>；不会采用到当前选中的其他卡片。</p>
    <Button disabled={props.disabled||busy||uncertain||!props.canMutate||!props.task.isOriginCurrent()} onClick={()=>void inspect()}>核验原位置与正式审核结果</Button>
    {visible&&<><p>仅替换这 1 张卡片：{props.task.origin.source.asset_id} → {visible.asset.id} · v{visible.asset.version}；坐标、分组、其他卡片和原素材文件保留。保存为新画布版本。</p>
      <label><input type="checkbox" checked={consent} disabled={busy||props.disabled} onChange={e=>{if(current()&&proofRef.current===visible){approvedRef.current=e.target.checked?visible:undefined;setConsent(e.target.checked);}}}/>确认只采用到上述原卡片</label>
      <Button disabled={!consent||props.disabled||busy} onClick={()=>void apply()}>确认采用并回填原卡片</Button></>}
    {error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  </section>;
}
