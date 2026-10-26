import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { canonicalImageNode } from './canvasImageNode';
import { readCanvasImageNodeTargetView, type CanvasImageNodeTargetView, type CanvasImageNodeTargetViewInput } from './canvasImageNodeTargetView';

export type CanvasImageNodeTargetViewPanelProps = CanvasImageNodeTargetViewInput & {
  onUnavailable: () => void;
  onClose: () => void;
};
function signature(props: CanvasImageNodeTargetViewPanelProps): string {
  try { return canonicalImageNode({projectId:props.projectId,branchId:props.branchId,key:props.source.key,job:props.source.job,pin:props.pin}); }
  catch { return ''; }
}
function sourceCurrent(props: CanvasImageNodeTargetViewPanelProps): boolean {
  try { return !props.signal?.aborted&&props.source.isCurrent()===true; } catch { return false; }
}
const referenceLabels = {CURRENT_METADATA:'当前元数据可用',STALE:'引用元数据已变化',UNAVAILABLE:'来源不可用，响应未提供原 pin'};

/** One explicitly requested, pinned public Canvas record. This is never an editor or a media preview. */
export function CanvasImageNodeTargetViewPanel(props: CanvasImageNodeTargetViewPanelProps) {
  const latest=useRef(props);latest.current=props;
  const stamp=signature(props),anchor=useRef({stamp,client:props.client,method:props.client.readImageNodeTargetView,read:props.read,signal:props.signal,retired:false});
  if(!stamp||stamp!==anchor.current.stamp||props.client!==anchor.current.client
    ||props.client.readImageNodeTargetView!==anchor.current.method||props.read!==anchor.current.read
    ||props.signal!==anchor.current.signal||!sourceCurrent(props))anchor.current.retired=true;
  const alive=useRef(true),serial=useRef(0),flight=useRef<{id:number;controller:AbortController}>();
  const [state,setState]=useState<{pending:boolean;value?:CanvasImageNodeTargetView;snapshotAt?:string;error?:string}>({pending:false});
  const current=()=>{
    if(!alive.current||anchor.current.retired)return false;
    const value=latest.current;
    if(signature(value)!==anchor.current.stamp||value.client!==anchor.current.client
      ||value.client.readImageNodeTargetView!==anchor.current.method||value.read!==anchor.current.read
      ||value.signal!==anchor.current.signal||!sourceCurrent(value)){
      anchor.current.retired=true;flight.current?.controller.abort();return false;
    }
    return true;
  };
  const ours=(id:number)=>current()&&flight.current?.id===id&&!flight.current.controller.signal.aborted;
  async function load() {
    if(!current()||flight.current)return;
    const id=++serial.current,controller=new AbortController();flight.current={id,controller};setState({pending:true});
    try {
      const value=latest.current;
      const result=await readCanvasImageNodeTargetView({projectId:value.projectId,branchId:value.branchId,client:value.client,
        source:{job:structuredClone(value.source.job),key:value.source.key,isCurrent:current},pin:structuredClone(value.pin),
        read:value.read,signal:controller.signal});
      if(ours(id))setState({pending:false,value:result,snapshotAt:new Date().toISOString()});
    }catch(error){
      if(!ours(id)||error instanceof Error&&error.name==='AbortError')return;
      const status=error instanceof ApiError?error.status:undefined;
      const message=status===409?'刚核对的画布版本已变化，未改用最新记录。请关闭记录并重新核对保存状态。'
        :status===404?'记录不存在或当前不可读取；本次未确认是否删除。'
        :status===422?'关联画布记录未通过本次只读核验，没有显示替代版本。'
        :status===401||status===403?'当前身份或读取权限已变化，关联画布记录未显示。'
        :apiErrorView(error,'关联画布只读记录尚未确认，请关闭后重新明确核对。').message;
      setState({pending:false,error:message});
      if(status===401||status===403){try{latest.current.onUnavailable();}catch{/* No other source is read. */}}
    }finally{
      if(flight.current?.id===id){flight.current=undefined;if(alive.current)setState(old=>old.pending?{...old,pending:false}:old);}
    }
  }
  function close() {
    if(!current())return;
    anchor.current.retired=true;flight.current?.controller.abort();flight.current=undefined;serial.current++;setState({pending:false});
    try{latest.current.onClose();}catch{/* A closed record never sends another request. */}
  }
  useLayoutEffect(()=>{
    alive.current=true;
    const abort=()=>{anchor.current.retired=true;flight.current?.controller.abort();};
    props.signal?.addEventListener('abort',abort,{once:true});if(props.signal?.aborted)abort();
    return()=>{alive.current=false;props.signal?.removeEventListener('abort',abort);flight.current?.controller.abort();flight.current=undefined;serial.current++;};
  },[]);
  useLayoutEffect(()=>{if(anchor.current.retired){flight.current?.controller.abort();flight.current=undefined;}});
  // Mounting this keyed child is the explicit request. No refresh, polling or fallback follows.
  useEffect(()=>{void load();},[]);
  const owns=!anchor.current.retired&&sourceCurrent(props),value=owns?state.value:undefined;
  const canvas=value?.canvas,requestedCard=canvas?.definition.cards.find(card=>card.id===value?.target.node_id);
  const origin=canvas?.definition.image_node_origin;
  const matchedOrigin=!!value&&!!requestedCard?.asset&&!!origin
    &&origin.job_id===value.job.id&&origin.job_version===value.job.version&&origin.job_request_digest===value.job.request_digest
    &&canonicalImageNode(origin.target)===canonicalImageNode(value.target)&&canonicalImageNode(origin.asset)===canonicalImageNode(requestedCard.asset);
  const states=new Map(canvas?.reference_states.map(row=>[row.card_id,row])??[]);
  return <Panel title="关联画布只读记录" aria-label="原目标关联画布只读记录">
    <p>这里显示刚核对版本的服务端记录，仅供查看；没有进入编辑器、恢复画布、读取媒体内容或保存任何修改。</p>
    {!owns&&<StatusMessage tone="warning">原任务选择或核对快照已失效，旧关联记录已隐藏。请返回原保存状态核对。</StatusMessage>}
    {owns&&state.pending&&<StatusMessage>正在读取此版本关联画布记录…</StatusMessage>}
    {owns&&state.error&&<StatusMessage tone="error">{state.error}</StatusMessage>}
    {value&&canvas&&<>
      <p>本次读取完成时间（本浏览器）：<time dateTime={state.snapshotAt}>{state.snapshotAt}</time>。这不是实时画布状态。</p>
      <dl>
        <dt>保存画布 ID</dt><dd>{canvas.id}</dd><dt>保存标题</dt><dd>{canvas.definition.title}</dd>
        <dt>读取版本</dt><dd>v{canvas.version}</dd><dt>读取摘要</dt><dd><code>{canvas.definition_digest}</code></dd>
        <dt>项目代次</dt><dd>{value.incarnation}</dd><dt>保存视口</dt><dd>x {canvas.definition.viewport.x}，y {canvas.definition.viewport.y}，缩放 {canvas.definition.viewport.zoom}</dd>
        <dt>记录创建时间</dt><dd>{canvas.created_at}</dd><dt>记录更新时间</dt><dd>{canvas.updated_at}</dd>
        <dt>原任务请求节点 ID</dt><dd>{value.target.node_id}</dd><dt>原任务请求位置</dt><dd>x {value.target.position.x}，y {value.target.position.y}</dd>
        <dt>真实保存卡片数量</dt><dd>{canvas.definition.cards.length}</dd>
      </dl>
      {!requestedCard?<StatusMessage>此保存版本没有原请求节点 ID 对应的卡片；任务中的节点与坐标仅是请求记录。</StatusMessage>
        :!matchedOrigin?<StatusMessage tone="warning">存在同 ID 卡片，但没有匹配的原任务来源关联；不能认定生成节点已保存。</StatusMessage>
        :<p>此记录含有匹配原任务与精确引用的来源关联元数据；它不证明媒体内容、生成质量或本次验收。</p>}
      {origin&&<details><summary>服务端记录的来源关联元数据</summary><p>记录任务 {origin.job_id} · v{origin.job_version}</p>
        <p>记录请求摘要：<code>{origin.job_request_digest}</code></p><p>记录目标节点 {origin.target.node_id}</p></details>}
      {canvas.definition.cards.length===0?<p>这是已保存的空白作品位置，没有可显示的节点卡片。</p>:<ul aria-label="真实保存卡片元数据">{canvas.definition.cards.map(card=>{
        const reference=states.get(card.id);
        return <li key={card.id}><h4>卡片 {card.id}</h4><p>实际保存坐标：x {card.position.x}，y {card.position.y}</p>
          <p>引用状态：{reference?referenceLabels[reference.state]:'响应未提供引用状态'}</p>
          {card.asset?<dl><dt>资产 ID</dt><dd>{card.asset.asset_id}</dd><dt>资产类型</dt><dd>{card.asset.kind}</dd>
            <dt>引用版本</dt><dd>v{card.asset.version}</dd><dt>引用摘要</dt><dd><code>{card.asset.digest}</code></dd>
            {reference?.filename&&<><dt>元数据文件名</dt><dd>{reference.filename}</dd></>}</dl>:<p>响应未提供资产引用；没有从任务或其他记录补写 pin。</p>}</li>;
      })}</ul>}
      <p>来源状态仅描述元数据，不验证二进制内容；此处不提供预览、定位、采用、保存或恢复操作。</p>
    </>}
    <Button disabled={!owns} onClick={close}>关闭关联画布记录</Button>
  </Panel>;
}
