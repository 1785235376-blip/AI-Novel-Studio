import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { canonicalImageNode } from './canvasImageNode';
import { readCanvasImageNodeJobObservation, type CanvasImageNodeJobObservation } from './canvasImageNodeJobObservation';
import { CANVAS_IMAGE_NODE_JOB_DISCARD_NOT_SENT, canDiscardCanvasImageNodeJob, discardCanvasImageNodeJob,
  type CanvasImageNodeJobDiscardInput } from './canvasImageNodeJobDiscard';
import type { StudioImageNodeJobDiscard } from './studioProductionClient';

export type CanvasImageNodeJobDiscardPanelProps = Omit<CanvasImageNodeJobDiscardInput,'observation'|'isCurrent'|'confirmed'|'signal'> & {
  read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
  canMutate: boolean;
  onConfirmed: (receipt: StudioImageNodeJobDiscard) => void;
  onUnavailable: () => void;
  onClose: () => void;
};
type Phase = 'IDLE' | 'SENDING' | 'UNKNOWN' | 'CONFIRMED';
type Approval = { value: CanvasImageNodeJobObservation; snapshot: number; nonce: number };
function signature(props: CanvasImageNodeJobDiscardPanelProps): string {
  try { return canonicalImageNode({projectId:props.projectId,branchId:props.branchId,key:props.source.key,job:props.source.job}); }
  catch { return ''; }
}
function sourceCurrent(props: CanvasImageNodeJobDiscardPanelProps): boolean {
  try { return props.source.isCurrent()===true; } catch { return false; }
}

/** A separate explicit command over one untouched QUEUED Job, never a media or remote-stop operation. */
export function CanvasImageNodeJobDiscardPanel(props: CanvasImageNodeJobDiscardPanelProps) {
  const latest=useRef(props);latest.current=props;
  const stamp=signature(props),anchor=useRef({stamp,client:props.client,observe:props.client.observeImageNodeJob,
    discard:props.client.discardImageNodeJob,read:props.read,mutate:props.mutate,claim:props.claim,canMutate:props.canMutate,retired:false});
  const alive=useRef(true),snapshot=useRef(0),operation=useRef(0),consent=useRef(0),phase=useRef<Phase>('IDLE');
  const accepted=useRef<CanvasImageNodeJobObservation>(),approval=useRef<Approval>();
  const flight=useRef<{id:number;kind:'READ'|'ACTION';controller:AbortController}>();
  const [state,setState]=useState<{pending:boolean;phase:Phase;value?:CanvasImageNodeJobObservation;receipt?:StudioImageNodeJobDiscard;error?:string;blocked?:boolean}>({pending:false,phase:'IDLE'});
  const [checked,setChecked]=useState(false);
  function clearConsent(publish=true) { consent.current++;approval.current=undefined;if(publish)setChecked(false); }
  function retire(publish=false) {
    anchor.current.retired=true;accepted.current=undefined;clearConsent(publish);snapshot.current++;
    if(phase.current==='SENDING')phase.current='UNKNOWN';flight.current?.controller.abort();
    if(publish)setState({pending:false,phase:phase.current});
  }
  const changed=(value:CanvasImageNodeJobDiscardPanelProps)=>!stamp||signature(value)!==anchor.current.stamp
    ||value.client!==anchor.current.client||value.client.observeImageNodeJob!==anchor.current.observe
    ||value.client.discardImageNodeJob!==anchor.current.discard||value.read!==anchor.current.read||value.mutate!==anchor.current.mutate
    ||value.claim!==anchor.current.claim||value.canMutate!==anchor.current.canMutate||!sourceCurrent(value);
  if(changed(props)&&!anchor.current.retired)retire();
  const current=()=>{
    if(!alive.current||anchor.current.retired)return false;
    if(changed(latest.current)){retire(true);return false;}
    return true;
  };
  const ours=(id:number)=>current()&&flight.current?.id===id&&!flight.current.controller.signal.aborted;
  async function refresh(expectedSnapshot?:number,expectedConsent?:number) {
    if(expectedSnapshot!==undefined&&(snapshot.current!==expectedSnapshot||consent.current!==expectedConsent))return;
    if(!current()||flight.current||phase.current!=='IDLE')return;
    snapshot.current++;accepted.current=undefined;clearConsent();
    const id=++operation.current,controller=new AbortController();flight.current={id,kind:'READ',controller};
    setState({pending:true,phase:'IDLE'});
    try {
      const value=latest.current;
      const result=await readCanvasImageNodeJobObservation({projectId:value.projectId,branchId:value.branchId,client:value.client,
        source:{job:structuredClone(value.source.job),key:value.source.key,isCurrent:current},read:value.read,signal:controller.signal});
      if(ours(id)){accepted.current=result;setState({pending:false,phase:'IDLE',value:result});}
    }catch(error){
      if(!ours(id)||error instanceof Error&&error.name==='AbortError')return;
      setState({pending:false,phase:'IDLE',error:apiErrorView(error,'原排队任务尚未核对，请明确重新读取。').message});
      if(error instanceof ApiError&&[401,403].includes(error.status)&&ours(id)){
        retire(true);try{latest.current.onUnavailable();}catch{/* The current read remains rejected. */}
      }
    }finally{if(flight.current?.id===id){flight.current=undefined;if(alive.current)setState(old=>old.pending?{...old,pending:false}:old);}}
  }
  function changeConsent(value:boolean,expectedSnapshot:number,expectedConsent:number) {
    if(snapshot.current!==expectedSnapshot||consent.current!==expectedConsent||!current()||flight.current||phase.current!=='IDLE'
      ||!latest.current.canMutate||!canDiscardCanvasImageNodeJob(accepted.current))return;
    const observed=accepted.current!;clearConsent(false);
    if(value)approval.current={value:observed,snapshot:snapshot.current,nonce:consent.current};
    setChecked(value);
  }
  async function submit(expectedSnapshot:number,expectedConsent:number,confirmed:Approval|undefined) {
    if(snapshot.current!==expectedSnapshot||consent.current!==expectedConsent||!current()||flight.current||phase.current!=='IDLE'
      ||!latest.current.canMutate||!confirmed||approval.current!==confirmed||accepted.current!==confirmed.value
      ||confirmed.snapshot!==snapshot.current||confirmed.nonce!==consent.current||!canDiscardCanvasImageNodeJob(confirmed.value))return;
    const value=latest.current,observed=confirmed.value,id=++operation.current,controller=new AbortController(),claim=value.claim;
    const stillConfirmed=()=>approval.current===confirmed&&accepted.current===observed&&snapshot.current===confirmed.snapshot&&consent.current===confirmed.nonce;
    phase.current='SENDING';flight.current={id,kind:'ACTION',controller};setState({pending:true,phase:'SENDING',value:observed});
    try {
      const result=await discardCanvasImageNodeJob({projectId:value.projectId,branchId:value.branchId,client:value.client,source:value.source,
        observation:observed,mutate:value.mutate,isCurrent:()=>current()&&latest.current.canMutate&&stillConfirmed(),
        confirmed:stillConfirmed,claim,signal:controller.signal});
      if(result.state==='CONFIRMED'&&ours(id)&&stillConfirmed()){
        phase.current='CONFIRMED';clearConsent();setState({pending:false,phase:'CONFIRMED',value:observed,receipt:result.receipt});
        if(ours(id)){try{latest.current.onConfirmed(structuredClone(result.receipt));}catch{/* The valid owner acknowledgement remains displayed. */}}
      }else{
        phase.current='UNKNOWN';clearConsent();
        if(alive.current&&current())setState({pending:false,phase:'UNKNOWN',value:observed,
          blocked:result.state==='BLOCKED',error:result.state==='CONFIRMED'?'回执到达时原确认已失效，结果仍待核对。':result.message});
      }
    }catch(error){
      const knownNotSent=error instanceof ApiError&&error.problem.code===CANVAS_IMAGE_NODE_JOB_DISCARD_NOT_SENT;
      if(knownNotSent){
        if(ours(id)){phase.current='IDLE';accepted.current=undefined;clearConsent();setState({pending:false,phase:'IDLE',value:observed,
          error:'发送准备未通过；本次未进入发送阶段。请重新核对原任务后再确认。'});}
      }else{
        // An unexpected failure cannot authorize a replay. Reserve this original
        // snapshot even if its component or permission has since retired.
        try{claim();}catch{/* Remain unknown. */}phase.current='UNKNOWN';clearConsent();
        if(alive.current&&current())setState({pending:false,phase:'UNKNOWN',value:observed,error:'未取得可核对回执，结果仍待核对；不能再次发送此版本。'});
      }
    }finally{if(flight.current?.id===id){flight.current=undefined;controller.abort();if(alive.current)setState(old=>old.pending?{...old,pending:false}:old);}}
  }
  function close(expectedSnapshot:number,expectedConsent:number) {
    if(snapshot.current!==expectedSnapshot||consent.current!==expectedConsent||!current())return;
    retire(true);flight.current?.controller.abort();operation.current++;
    try{latest.current.onClose();}catch{/* Closing never replays a mutation. */}
  }
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;accepted.current=undefined;clearConsent(false);snapshot.current++;operation.current++;flight.current?.controller.abort();flight.current=undefined;};},[]);
  useLayoutEffect(()=>{if(anchor.current.retired){flight.current?.controller.abort();flight.current=undefined;}});
  useEffect(()=>{void refresh();},[]);
  const owns=!anchor.current.retired&&sourceCurrent(props),observed=owns?state.value:undefined,job=observed?.job;
  const eligible=canDiscardCanvasImageNodeJob(accepted.current),ready=owns&&props.canMutate&&phase.current==='IDLE'&&!state.pending&&eligible;
  const renderedSnapshot=snapshot.current,renderedConsent=consent.current,renderedApproval=approval.current;
  return <Panel title="放弃排队任务的本地采用" aria-label="原节点排队任务放弃采用确认">
    <p>这是独立操作。初次只读核对不会修改任务；只允许尚未执行、没有候选和回执的原排队任务。</p>
    <p>确认后只改变此任务的本地采用资格，保留原任务和证据；不生成、不审核、不删除媒体，也不确认远端计算停止。</p>
    {!owns&&<StatusMessage tone="warning">原来源、读取入口或写入能力已变化，此确认已永久退役。若操作已进入发送阶段，结果仍须从原任务列表核对。</StatusMessage>}
    {owns&&state.pending&&<StatusMessage>{state.phase==='SENDING'?'已进入原任务条件修改流程，结果待核对；不会自动重发。':'正在只读核对原排队任务…'}</StatusMessage>}
    {owns&&state.error&&<StatusMessage tone="warning">{state.error}</StatusMessage>}
    {observed&&job&&<>
      <p>{state.phase==='IDLE'?'已读取原任务元数据，尚未提交放弃采用。':'以下保留操作前读取的原任务元数据；它不代表本次操作结果。'} 以下为核对时的原任务快照，不是实时状态。</p>
      <dl><dt>项目 ID</dt><dd>{job.novel_id}</dd><dt>原任务 ID</dt><dd>{job.id}</dd><dt>核对时版本</dt><dd>v{job.version}</dd>
        <dt>核对时状态与执行次数</dt><dd>{job.status} · attempt {job.attempt}</dd><dt>原请求摘要</dt><dd><code>{job.request_digest}</code></dd>
        <dt>原请求 ID</dt><dd>{job.request_id}</dd><dt>原模型记录</dt><dd>{job.provider.provider_id} / {job.provider.model_id}</dd>
        <dt>请求目标（未核对画布）</dt><dd>{observed.target.canvas_id} / {observed.target.node_id} · 请求版本 v{observed.target.canvas_version}</dd>
      </dl><label>原排队任务提示词<textarea readOnly value={job.command.prompt} rows={4}/></label>
      <p>本次未读取画布，不证明目标存在或节点已经保存；服务商与模型仅为原任务记录，未读取配置。</p>
      {state.phase==='IDLE'&&!eligible&&<StatusMessage tone="warning">此回执不满足未执行、无候选的排队任务条件，不能从这里放弃采用。</StatusMessage>}
    </>}
    {owns&&state.phase==='IDLE'&&<>
      <label><input type="checkbox" checked={checked} disabled={!ready} onChange={event=>changeConsent(event.target.checked,renderedSnapshot,renderedConsent)}/>
        我确认只放弃此排队任务的本地采用资格</label>
      <Button variant="danger" disabled={!ready||!checked||!renderedApproval} onClick={()=>void submit(renderedSnapshot,renderedConsent,renderedApproval)}>确认放弃本地采用资格</Button>
    </>}
    {owns&&state.phase==='UNKNOWN'&&<StatusMessage tone="warning">{state.blocked?'此版本已有操作登记，当前结果待核对（UNKNOWN）；本次不会重发。':'原任务本地采用资格修改结果待核对（UNKNOWN）；不会再次发送此版本。'} 请关闭并在任务列表显式重新读取同一任务的新版本。</StatusMessage>}
    {owns&&state.receipt&&<section aria-label="原任务放弃采用回执"><StatusMessage>已收到原 owner 的 CANCELLED 回执，仅确认本地采用资格已放弃；不确认远端停止，也未删除媒体或执行审核。</StatusMessage>
      <p>原任务 {state.receipt.job.id} · 回执版本 v{state.receipt.job.version} · {state.receipt.job.status}</p></section>}
    <Button disabled={!owns||state.pending||state.phase!=='IDLE'} onClick={()=>void refresh(renderedSnapshot,renderedConsent)}>重新核对原排队任务</Button>
    <Button disabled={!owns} onClick={()=>close(renderedSnapshot,renderedConsent)}>关闭并返回任务列表</Button>
  </Panel>;
}
