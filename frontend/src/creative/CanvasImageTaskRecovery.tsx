import { captureCanvasVideoTrimTask, canvasVideoTaskJobMatches, checkedCanvasVideoReturnBinding } from './canvasVideoTrimTask';
import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { captureCanvasAudioTrimTask, canvasAudioTrimTaskJobMatches } from './canvasAudioTrimTask';
import { captureCanvasImageTask, canvasImageTaskJobMatches, type CanvasImageTaskOrigin } from './canvasImageTask';
import { canvasReturnInJob, sameCanvasReturn, sameCanvasReturnJob, sameCanvasReturnScope } from './studioCanvasReturnBinding';
import type { StudioClient, StudioAsset } from './studioClient';
import type { CanvasViewRecord } from './studioCanvasViewClient';
import type { ProductionJob, StudioProductionClient } from './studioProductionClient';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';

type Props={client:StudioClient;production:StudioProductionClient;owner?:StudioGraphDraftOwner;ownerToken:object;disabled:boolean;canMutate:boolean;
  isCurrent:()=>boolean;read:<T>(f:()=>Promise<T>)=>Promise<T>;onResume:(canvas:CanvasViewRecord,asset:StudioAsset,job:ProductionJob,origin:CanvasImageTaskOrigin)=>void};
const resumable=(job:ProductionJob)=>job.owner==='audio'&&job.operation_id==='m8.audio.trim'&&job.provider===null
  &&job.execution_recipe.adapter==='LOCAL_FFMPEG'&&job.execution_recipe.output_profile==='PCM_S16LE_WAV_48000_STEREO'
  &&['QUEUED','FAILED','UNKNOWN'].includes(job.status)?(job.status!=='FAILED'||job.output_candidate===null):job.canvas_video!==undefined?['QUEUED','SUCCEEDED','APPROVED','AWAITING_REVIEW'].includes(job.status)&&(job.status==='QUEUED'||!!job.output_candidate):['APPROVED','AWAITING_REVIEW'].includes(job.status)&&!!job.output_candidate;
/** Reads the original Job's immutable command. No local storage or inferred target. */
export function CanvasImageTaskRecovery(props:Props){
  const [rows,setRows]=useState<{token:object;jobs:ProductionJob[]}>(),[pending,setPending]=useState(false),[error,setError]=useState('');
  const alive=useRef(true),running=useRef(false),live=useRef(props);live.current=props;
  const values=[props.client,props.production,props.ownerToken,JSON.stringify(props.owner),props.canMutate],fence=useRef({values,token:{}});
  if(values.some((v,i)=>!Object.is(v,fence.current.values[i])))fence.current={values,token:{}};
  const token=fence.current.token,current=()=>alive.current&&fence.current.token===token&&live.current.isCurrent();
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  async function load(){
    if(!current()||live.current.disabled||running.current||!props.owner)return;running.current=true;setPending(true);setRows(undefined);setError('');
    try{const jobs=await props.read(()=>props.production.list());if(!current())return;
      const owner=props.owner;setRows({token,jobs:jobs.filter(j=>{const origin=canvasReturnInJob(j);return (j.owner==='image'||j.owner==='audio'||j.canvas_video!==undefined)&&resumable(j)&&origin?.project_id===owner.projectId&&origin.incarnation===owner.incarnation;})});
    }catch(e){if(current())setError(e instanceof Error?e.message:'原任务读取失败。');}finally{running.current=false;if(alive.current)setPending(false);}
  }
  async function resume(requested:ProductionJob){
    if(!current()||live.current.disabled||running.current||!props.canMutate||!props.owner)return;running.current=true;setPending(true);setError('');
    try{const value=await props.read(async()=>{
      const job=await props.production.get(requested.owner,requested.id),binding=canvasReturnInJob(job);
      if(!current())throw new Error('原任务读取已退役。');
      if(!binding||!resumable(job)||job.request_digest!==requested.request_digest||!sameCanvasReturnJob(job,requested))throw new Error('原任务或持久回流来源已改变，请重新读取任务记录。');
      const client=props.client.graphs.canvasViews!;
      const history=await client.history(binding.canvas_id);if(!current())throw new Error('原代次读取已退役。');
      const canvas=await client.get(binding.canvas_id);if(!current())throw new Error('原画布读取已退役。');
      if(!sameCanvasReturnScope(binding,canvas.project_id,canvas.scope,props.owner!.incarnation)||history.incarnation!==binding.incarnation
        ||history.current_version!==canvas.version||history.current_definition_digest!==canvas.definition_digest)throw new Error('原项目范围、代次或画布版本已改变；候选保留，不会换绑位置。');
      const asset=await props.client.asset(binding.source.id),origin=(binding.source.asset_kind==='video'?captureCanvasVideoTrimTask:binding.source.asset_kind==='audio'?captureCanvasAudioTrimTask:captureCanvasImageTask)(canvas,binding.card_id,asset,binding.incarnation);
      if(!current())throw new Error('原素材读取已退役。');
      const video=binding.source.asset_kind==='video';
      const matches=video?canvasVideoTaskJobMatches({source:binding.source,returnBinding:checkedCanvasVideoReturnBinding(origin.binding),isCurrent:()=>true},job)
        :sameCanvasReturn(job.command,{...job.command!,canvas_return:origin.binding})&&(binding.source.asset_kind==='audio'?canvasAudioTrimTaskJobMatches:canvasImageTaskJobMatches)({source:binding.source,returnBinding:binding,isCurrent:()=>true},job);
      if(!matches)throw new Error('原卡片、画布版本或源 pin 已改变；候选保留，不会回填其他位置。');
      return {canvas,asset,job,origin};
    });if(current())props.onResume(value.canvas,value.asset,value.job,value.origin);
    }catch(e){if(current())setError(e instanceof Error?e.message:'恢复原任务失败，未采用或重新执行。');}finally{running.current=false;if(alive.current)setPending(false);}
  }
  return <details><summary>重开后恢复尚未采用的卡片结果</summary><section aria-label="持久卡片回流任务">
    <p>支持已绑定原位置的图像、音频截取和视频截取任务。只读取原 Job 中的版本化目标。旧任务没有绑定时不能猜测位置；读取和打开不会执行或自动采用。原位置冲突时保留候选。</p>
    <p>本地音频截取也可重新核对原入队、失败或 UNKNOWN 记录。打开只读取；失败后须明确派生新身份草稿，UNKNOWN 只查询核对，绝不自动重发。</p>
    <Button disabled={props.disabled||pending||!props.owner} onClick={()=>void load()}>读取有原位置绑定的卡片结果</Button>
    {rows?.token===token&&<>{!rows.jobs.length&&<p>没有可恢复的待审核或已审核结果。其他状态及旧任务仍可从原任务记录核对，不会重发。</p>}<ul>{rows.jobs.map(job=><li key={job.id}><Button disabled={pending||props.disabled||!props.canMutate} onClick={()=>void resume(job)}>核验并恢复原卡片任务 · {job.id} · {job.status}</Button></li>)}</ul></>}
    {!props.owner&&<p>尚未取得当前项目代次，不能恢复精确回流意图。</p>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  </section></details>;
}
