import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { canonicalImageNode } from './canvasImageNode';
import { readCanvasImageNodeTarget, type CanvasImageNodeTargetObservation, type CanvasImageNodeTargetObservationInput, type CanvasImageNodeTargetSource } from './canvasImageNodeTargetObservation';
import { CanvasImageNodeTargetViewPanel } from './CanvasImageNodeTargetViewPanel';
import type { CanvasImageNodeTargetViewInput, CanvasImageNodeTargetViewPin } from './canvasImageNodeTargetView';

export type CanvasImageNodeTargetPanelProps = Omit<CanvasImageNodeTargetObservationInput,'signal'|'client'> & {
  client: CanvasImageNodeTargetViewInput['client'];
  onUnavailable: () => void;
  onClose: () => void;
};
type TargetViewSession = { id: number; controller: AbortController; source: CanvasImageNodeTargetSource; pin: CanvasImageNodeTargetViewPin };
function signature(props: CanvasImageNodeTargetPanelProps): string {
  try { return canonicalImageNode({projectId:props.projectId,branchId:props.branchId,key:props.source.key,job:props.source.job}); }
  catch { return ''; }
}
function sourceCurrent(props: CanvasImageNodeTargetPanelProps): boolean {
  try { return props.source.isCurrent()===true; } catch { return false; }
}

/** A metadata-only snapshot, mounted by an explicit original-task row action. */
export function CanvasImageNodeTargetPanel(props: CanvasImageNodeTargetPanelProps) {
  const latest=useRef(props);latest.current=props;
  const stamp=signature(props),anchor=useRef({stamp,client:props.client,method:props.client.observeImageNodeTarget,viewMethod:props.client.readImageNodeTargetView,read:props.read,retired:false});
  if(!stamp||stamp!==anchor.current.stamp||props.client!==anchor.current.client
    ||props.client.observeImageNodeTarget!==anchor.current.method||props.client.readImageNodeTargetView!==anchor.current.viewMethod
    ||props.read!==anchor.current.read||!sourceCurrent(props))anchor.current.retired=true;
  const alive=useRef(true),serial=useRef(0),flight=useRef<{id:number;controller:AbortController}>();
  const [state,setState]=useState<{pending:boolean;value?:CanvasImageNodeTargetObservation;snapshotAt?:string;error?:string}>({pending:false});
  const valueRef=useRef<CanvasImageNodeTargetObservation>(),viewSerial=useRef(0),viewRef=useRef<TargetViewSession>();
  const [view,setView]=useState<TargetViewSession>();
  function retireView(publish=true) {
    const previous=viewRef.current;viewSerial.current++;viewRef.current=undefined;previous?.controller.abort();
    if(publish)setView(undefined);
  }
  if(anchor.current.retired){valueRef.current=undefined;retireView(false);}
  const current=(publish=true)=>{
    if(!alive.current||anchor.current.retired){
      if(publish&&alive.current)setState(old=>old.pending||old.value||old.error?{pending:false}:old);
      return false;
    }
    const value=latest.current;
    if(signature(value)!==anchor.current.stamp||value.client!==anchor.current.client
      ||value.client.observeImageNodeTarget!==anchor.current.method||value.client.readImageNodeTargetView!==anchor.current.viewMethod
      ||value.read!==anchor.current.read||!sourceCurrent(value)){
      anchor.current.retired=true;valueRef.current=undefined;retireView(false);flight.current?.controller.abort();
      if(publish)setState({pending:false});return false;
    }
    return true;
  };
  const ours=(id:number)=>current()&&flight.current?.id===id&&!flight.current.controller.signal.aborted;
  async function refresh(expectedSerial?:number,expectedViewSerial?:number) {
    if(expectedSerial!==undefined&&(serial.current!==expectedSerial||viewSerial.current!==expectedViewSerial))return;
    if(!current()||flight.current)return;
    retireView();valueRef.current=undefined;
    const id=++serial.current,controller=new AbortController();flight.current={id,controller};
    setState({pending:true});
    try {
      const value=latest.current;
      const result=await readCanvasImageNodeTarget({projectId:value.projectId,branchId:value.branchId,client:value.client,
        source:{job:structuredClone(value.source.job),key:value.source.key,isCurrent:current},
        read:value.read,signal:controller.signal});
      if(ours(id)){valueRef.current=result;setState({pending:false,value:result,snapshotAt:new Date().toISOString()});}
    }catch(error){
      if(!ours(id))return;
      if(error instanceof Error&&error.name==='AbortError')return;
      const unavailable=error instanceof ApiError&&[401,403,404].includes(error.status);
      setState({pending:false,error:unavailable?'记录不存在或当前不可读取；本次未确认是否删除。':apiErrorView(error,'原作品保存状态尚未确认，请显式重新核对。').message});
      if(error instanceof ApiError&&[401,403].includes(error.status)){
        try{latest.current.onUnavailable();}catch{/* The safe read failure remains visible. */}
      }
    }finally{
      if(flight.current?.id===id){flight.current=undefined;if(alive.current)setState(old=>old.pending?{...old,pending:false}:old);}
    }
  }
  function close(expectedSerial:number,expectedViewSerial:number) {
    if(serial.current!==expectedSerial||viewSerial.current!==expectedViewSerial)return;
    if(!current())return;
    retireView();valueRef.current=undefined;anchor.current.retired=true;setState({pending:false});
    flight.current?.controller.abort();flight.current=undefined;serial.current++;
    try{latest.current.onClose();}catch{/* A closed observation cannot send another request. */}
  }
  function openView(observed:CanvasImageNodeTargetObservation,expectedSerial:number,expectedViewSerial:number) {
    if(serial.current!==expectedSerial||viewSerial.current!==expectedViewSerial||!current()||flight.current||viewRef.current
      ||valueRef.current!==observed||!latest.current.client.readImageNodeTargetView)return;
    const id=++viewSerial.current,observationSerial=serial.current,controller=new AbortController();
    const pin={incarnation:observed.incarnation,version:observed.canvas.version,definition_digest:observed.canvas.definition_digest};
    const source={job:structuredClone(latest.current.source.job),key:`${latest.current.source.key}:canvas:${id}`,
      isCurrent:()=>current(false)&&!controller.signal.aborted&&viewSerial.current===id&&viewRef.current?.id===id
        &&viewRef.current.controller===controller&&serial.current===observationSerial&&valueRef.current===observed};
    const next={id,controller,source,pin};viewRef.current=next;setView(next);
  }
  function closeView(selected:TargetViewSession) {
    if(viewRef.current!==selected||viewSerial.current!==selected.id)return;
    retireView();
  }
  useLayoutEffect(()=>{
    alive.current=true;
    return()=>{alive.current=false;retireView(false);valueRef.current=undefined;flight.current?.controller.abort();flight.current=undefined;serial.current++;};
  },[]);
  useLayoutEffect(()=>{if(anchor.current.retired){retireView(false);if(view)setView(undefined);flight.current?.controller.abort();flight.current=undefined;}});
  // Opening this keyed panel is the user's request. A refresh is always explicit; no polling follows.
  useEffect(()=>{void refresh();},[]);
  const owns=!anchor.current.retired&&sourceCurrent(props),value=owns?state.value:undefined;
  const renderedSerial=serial.current,renderedViewSerial=viewSerial.current;
  return <Panel title="核对原作品保存状态" aria-label="原图片节点作品保存状态">
    <p>只读取原任务及作品保存元数据，不读取素材内容，也不执行、审核、保存或恢复。本面板不会解锁其他任务操作。</p>
    {!owns&&<StatusMessage tone="warning">原任务选择、项目或读取入口已变化，本次核对已退役。请从任务列表重新明确选择。</StatusMessage>}
    {owns&&state.pending&&<StatusMessage>正在核对原作品保存状态…</StatusMessage>}
    {owns&&state.error&&<StatusMessage tone="error">{state.error}</StatusMessage>}
    {value&&<>
      <StatusMessage>{value.comparison==='CURRENT_MATCH'?'当前保存版本与原请求时的空白作品一致。':'原请求时的空白作品历史已匹配；当前保存版本已变化。'}</StatusMessage>
      <p>这是本次读取的元数据快照，不是实时状态。读取完成时间（本浏览器）：<time dateTime={state.snapshotAt}>{state.snapshotAt}</time>。</p>
      <dl>
        <dt>原任务 ID</dt><dd>{value.job.id}</dd>
        <dt>作品画布 ID</dt><dd>{value.target.canvas_id}</dd>
        <dt>原请求节点 ID</dt><dd>{value.target.node_id}</dd>
        <dt>原请求节点标题</dt><dd>{value.target.title}</dd>
        <dt>原请求节点位置</dt><dd>x {value.target.position.x}，y {value.target.position.y}</dd>
        <dt>原请求捕获版本</dt><dd>v{value.target.canvas_version}</dd>
        <dt>原请求捕获摘要</dt><dd><code>{value.target.canvas_digest}</code></dd>
        <dt>当前保存版本</dt><dd>v{value.canvas.version}</dd>
        <dt>当前保存摘要</dt><dd><code>{value.canvas.definition_digest}</code></dd>
        <dt>当前作品标题</dt><dd>{value.canvas.title}</dd>
        <dt>当前卡片数量</dt><dd>{value.canvas.card_count}</dd>
        <dt>匹配的原历史版本</dt><dd>v{value.history.target_version} · 原历史为空白作品，未含节点采用来源</dd>
        <dt>匹配的原历史摘要</dt><dd><code>{value.history.target_definition_digest}</code></dd>
      </dl>
      <p>节点 ID、标题和坐标来自历史请求，不证明该节点卡片现在存在，也不证明生成结果已保存到原位置。历史匹配不授予恢复或执行权限。</p>
      <Button disabled={!owns||state.pending||!!view||!props.client.readImageNodeTargetView} onClick={()=>openView(value,renderedSerial,renderedViewSerial)}>查看此版本关联画布</Button>
      {!props.client.readImageNodeTargetView&&<p>当前服务尚不支持固定版本的完整只读记录，不能使用其他读取入口替代。</p>}
    </>}
    <Button disabled={!owns||state.pending} loading={owns&&state.pending} onClick={()=>void refresh(renderedSerial,renderedViewSerial)}>重新核对保存状态</Button>
    <Button disabled={!owns} onClick={()=>close(renderedSerial,renderedViewSerial)}>关闭保存状态核对</Button>
    {owns&&view&&<CanvasImageNodeTargetViewPanel key={view.source.key} projectId={props.projectId} branchId={props.branchId}
      client={props.client} source={view.source} pin={view.pin} read={props.read} signal={view.controller.signal}
      onUnavailable={()=>{if(viewRef.current===view&&view.source.isCurrent())latest.current.onUnavailable();}}
      onClose={()=>closeView(view)} />}
  </Panel>;
}
