import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { canonicalImageNode } from './canvasImageNode';
import { readCanvasImageNodeJobObservation, type CanvasImageNodeJobObservationInput } from './canvasImageNodeJobObservation';
import type { StudioImageNodeJobObservation } from './studioProductionClient';

export type CanvasImageNodeJobObservationPanelProps = Omit<CanvasImageNodeJobObservationInput,'signal'> & {
  onUnavailable: () => void;
  onClose: () => void;
};
function signature(props: CanvasImageNodeJobObservationPanelProps): string {
  try { return canonicalImageNode({projectId:props.projectId,branchId:props.branchId,key:props.source.key,job:props.source.job}); }
  catch { return ''; }
}
function sourceCurrent(props: CanvasImageNodeJobObservationPanelProps): boolean {
  try { return props.source.isCurrent()===true; } catch { return false; }
}
const statusLabels:Record<string,string>={QUEUED:'排队',RUNNING:'运行中',FAILED:'失败',UNKNOWN:'结果未知',
  AWAITING_REVIEW:'等待审核',REVIEWING:'审核中',APPROVED:'已记录审批状态',CANCELLED:'已取消'};

/** One original Job's public metadata. Canvas existence and media contents are not read here. */
export function CanvasImageNodeJobObservationPanel(props: CanvasImageNodeJobObservationPanelProps) {
  const latest=useRef(props);latest.current=props;
  const stamp=signature(props),anchor=useRef({stamp,client:props.client,method:props.client.observeImageNodeJob,read:props.read,retired:false});
  if(!stamp||stamp!==anchor.current.stamp||props.client!==anchor.current.client
    ||props.client.observeImageNodeJob!==anchor.current.method||props.read!==anchor.current.read||!sourceCurrent(props))anchor.current.retired=true;
  const alive=useRef(true),serial=useRef(0),flight=useRef<{id:number;controller:AbortController}>();
  const [state,setState]=useState<{pending:boolean;value?:StudioImageNodeJobObservation;snapshotAt?:string;error?:string}>({pending:false});
  const current=()=>{
    if(!alive.current||anchor.current.retired){
      if(alive.current)setState(old=>old.pending||old.value||old.error?{pending:false}:old);
      return false;
    }
    const value=latest.current;
    if(signature(value)!==anchor.current.stamp||value.client!==anchor.current.client
      ||value.client.observeImageNodeJob!==anchor.current.method||value.read!==anchor.current.read||!sourceCurrent(value)){
      anchor.current.retired=true;flight.current?.controller.abort();setState({pending:false});return false;
    }
    return true;
  };
  const ours=(id:number)=>current()&&flight.current?.id===id&&!flight.current.controller.signal.aborted;
  async function refresh(expectedSerial?:number) {
    if(expectedSerial!==undefined&&serial.current!==expectedSerial)return;
    if(!current()||flight.current)return;
    const id=++serial.current,controller=new AbortController();flight.current={id,controller};setState({pending:true});
    try {
      const value=latest.current;
      const result=await readCanvasImageNodeJobObservation({projectId:value.projectId,branchId:value.branchId,client:value.client,
        source:{job:structuredClone(value.source.job),key:value.source.key,isCurrent:current},read:value.read,signal:controller.signal});
      if(ours(id))setState({pending:false,value:result,snapshotAt:new Date().toISOString()});
    }catch(error){
      if(!ours(id)||error instanceof Error&&error.name==='AbortError')return;
      const status=error instanceof ApiError?error.status:undefined;
      const message=status===404?'原任务不存在或当前不可读取；本次未确认是否删除。'
        :status===409?'原任务回执版本已变化，未改读最新任务或版本。请从列表重新明确选择。'
        :status===422?'原任务元数据未通过本次核验，未显示替代回执。'
        :status===401||status===403?'当前身份或读取权限已变化，原任务元数据未显示。'
        :apiErrorView(error,'原任务元数据读取尚未确认，请明确重新读取。').message;
      setState({pending:false,error:message});
      if((status===401||status===403)&&ours(id)){
        anchor.current.retired=true;flight.current?.controller.abort();
        try{latest.current.onUnavailable();}catch{/* A rejected source never falls back to another owner. */}
      }
    }finally{
      if(flight.current?.id===id){flight.current=undefined;if(alive.current)setState(old=>old.pending?{...old,pending:false}:old);}
    }
  }
  function close(expectedSerial:number) {
    if(serial.current!==expectedSerial||!current())return;
    anchor.current.retired=true;flight.current?.controller.abort();flight.current=undefined;serial.current++;setState({pending:false});
    try{latest.current.onClose();}catch{/* A closed metadata view cannot read again. */}
  }
  useLayoutEffect(()=>{
    alive.current=true;
    return()=>{alive.current=false;flight.current?.controller.abort();flight.current=undefined;serial.current++;};
  },[]);
  useLayoutEffect(()=>{if(anchor.current.retired){flight.current?.controller.abort();flight.current=undefined;}});
  // The keyed row selection is the explicit initial request. There is no polling.
  useEffect(()=>{void refresh();},[]);
  const owns=!anchor.current.retired&&sourceCurrent(props),value=owns?state.value:undefined,job=value?.job;
  const renderedSerial=serial.current;
  return <Panel title="原节点任务只读详情" aria-label="原节点任务只读元数据">
    <p>只读取原任务 owner 已记录的状态、命令和回执元数据，不要求原空白画布仍存在。本次没有读取画布或素材内容，也不会执行、重排队、对账、取消、审核或采用。</p>
    {!owns&&<StatusMessage tone="warning">原任务选择、身份或读取入口已变化，旧任务元数据已隐藏。请从任务列表重新明确选择。</StatusMessage>}
    {owns&&state.pending&&<StatusMessage>正在读取原节点任务元数据…</StatusMessage>}
    {owns&&state.error&&<StatusMessage tone="error">{state.error}</StatusMessage>}
    {value&&job&&<>
      <p>这是本次读取的任务元数据快照，不是实时状态。读取完成时间（本浏览器）：<time dateTime={state.snapshotAt}>{state.snapshotAt}</time>。</p>
      <dl>
        <dt>原任务 ID</dt><dd>{job.id}</dd><dt>原任务版本</dt><dd>v{job.version}</dd>
        <dt>原 owner 状态</dt><dd>{statusLabels[job.status]??'原回执状态'} · {job.status}</dd>
        <dt>原错误码</dt><dd>{job.error_code??'未记录错误码；不据此推断成功'}</dd>
        <dt>原执行次数</dt><dd>{job.attempt}</dd><dt>原执行状态字段</dt><dd>{job.execution_state??'未记录'}</dd>
        <dt>原审核状态字段</dt><dd>{job.review_state??'未记录'}</dd><dt>原取消模式</dt><dd>{job.cancellation_mode??'未记录'}</dd>
        <dt>原对账标记</dt><dd>{job.needs_reconciliation===true?'是；本入口不执行对账':job.needs_reconciliation===false?'否':'未记录'}</dd>
        <dt>任务创建时间</dt><dd>{job.created_at}</dd><dt>任务更新时间</dt><dd>{job.updated_at}</dd>
        <dt>原操作</dt><dd>{job.operation_id}</dd><dt>原请求 ID</dt><dd>{job.request_id}</dd>
        <dt>原请求摘要</dt><dd><code>{job.request_digest}</code></dd>
        <dt>原回执摘要</dt><dd>{job.receipt_digest?<code>{job.receipt_digest}</code>:'尚未记录回执摘要'}</dd>
        <dt>回执中的审批资产版本字段</dt><dd>{job.approved_asset_version??'未记录'}</dd>
      </dl>
      {job.remote_compute_may_continue&&<StatusMessage tone="warning">原回执提示远端计算可能仍在继续；本页不判断它是否已经停止，也不发送任何任务操作。</StatusMessage>}
      {job.provider?<dl><dt>原请求服务商与模型</dt><dd>{job.provider.provider_id} / {job.provider.model_id}</dd>
        <dt>原路线类型</dt><dd>{job.provider.local?'记录为本地路线':'记录为云端路线'}</dd>
        <dt>原路线摘要</dt><dd><code>{job.provider.route_digest}</code></dd></dl>:<p>原回执没有服务路线投影。</p>}
      <p>上述路线来自原回执，不代表当前服务配置、模型加载情况或服务可用性；本页未读取服务配置。</p>
      {job.command&&<details><summary>原任务已记录的命令</summary>
        <label>原任务已记录的提示词<textarea readOnly rows={4} value={job.command.prompt}/></label>
        <h4>原命令参数</h4><pre>{JSON.stringify(job.command.parameters,null,2)}</pre>
        <p>原云端发送确认：{job.command.allow_cloud?'记录为允许':'记录为未允许'}。</p>
        {!!job.command.license_note&&<label>原来源与授权说明<textarea readOnly rows={2} value={job.command.license_note}/></label>}
      </details>}
      {job.output_candidate&&<section aria-label="原回执候选引用元数据"><h3>原回执记录的候选引用</h3><dl>
        <dt>候选 ID</dt><dd>{job.output_candidate.id}</dd><dt>候选类型</dt><dd>{job.output_candidate.kind}</dd>
        <dt>候选引用版本</dt><dd>v{job.output_candidate.version}</dd><dt>候选摘要</dt><dd><code>{job.output_candidate.digest}</code></dd>
      </dl><p>仅显示回执中的引用，不证明候选可读取、审批有效或当前资产版本；没有读取、预览或采用该候选。</p></section>}
      <section aria-label="原任务请求目标未核对"><h3>原请求目标（未读取画布）</h3><dl>
        <dt>请求画布 ID</dt><dd>{value.target.canvas_id}</dd><dt>请求捕获画布版本</dt><dd>v{value.target.canvas_version}</dd>
        <dt>请求捕获画布摘要</dt><dd><code>{value.target.canvas_digest}</code></dd><dt>原项目代次</dt><dd>{value.incarnation}</dd>
        <dt>请求节点 ID</dt><dd>{value.target.node_id}</dd><dt>请求节点标题</dt><dd>{value.target.title}</dd>
        <dt>请求节点坐标</dt><dd>x {value.target.position.x}，y {value.target.position.y}</dd>
      </dl><p>这些是原任务记录的请求目标，未核对画布是否存在、当前版本、节点卡片或保存位置；没有恢复任何作品。</p></section>
    </>}
    <Button disabled={!owns||state.pending} loading={owns&&state.pending} onClick={()=>void refresh(renderedSerial)}>重新读取原任务元数据</Button>
    <Button disabled={!owns} onClick={()=>close(renderedSerial)}>关闭原任务元数据</Button>
  </Panel>;
}
