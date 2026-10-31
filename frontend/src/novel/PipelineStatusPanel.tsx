import {useEffect,useRef,useState} from 'react';
import {api,ApiError,getCollaborationContext} from '../api';
import {Button,EmptyState,StatusMessage} from '../ui/primitives';

export function PipelineStatusPanel(props:{novelId?:string;screenplayId?:string}){
  const context=getCollaborationContext();
  return <PipelineBody key={[props.novelId,props.screenplayId,context.sessionToken,context.scope?.branchId].join('|')} {...props}/>;
}
function PipelineBody({novelId,screenplayId}:{novelId?:string;screenplayId?:string}){
  const [data,setData]=useState<any>(),[message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
  const epoch=useRef(0),lock=useRef(false);
  const describe=(reason:unknown)=>reason instanceof ApiError&&(reason.status===401||reason.status===403)?'无权读取或推进当前剧本，权限可能已撤销。':reason instanceof ApiError&&reason.status===409?'剧本版本或阶段发生冲突，请读取最新状态。':reason instanceof ApiError&&reason.status===404?'剧本不存在、当前范围不符或功能已关闭。':'影视化状态读取失败，请重试；未确认的推进操作不会自动重放。';
  async function refresh(){
    if(!novelId||!screenplayId){setLoading(false);return;}
    const ticket=++epoch.current;setLoading(true);setError('');
    try{const result=await api.pipelineStatus(novelId,screenplayId);if(ticket===epoch.current)setData(result);}
    catch(reason){if(ticket===epoch.current){setData(undefined);setError(describe(reason));}}
    finally{if(ticket===epoch.current)setLoading(false);}
  }
  useEffect(()=>{void refresh();return()=>{++epoch.current;};},[novelId,screenplayId]);
  const names:Record<string,string>={screenplay:'剧本审批',shots:'镜头规划',storyboard:'分镜设计',transitions:'转场设计',motion:'视频生成',complete:'已完成'};
  async function advance(untilGate=false){
    if(!novelId||!screenplayId||lock.current)return;lock.current=true;setBusy(true);setError('');const ticket=epoch.current;
    try{
      const result=untilGate?await api.advancePipelineUntilGate(novelId,screenplayId):await api.advancePipeline(novelId,screenplayId);
      if(ticket!==epoch.current)return;
      setMessage(result.action==='MANUAL_APPROVAL_REQUIRED'?'需要先人工批准当前阶段。':untilGate?`批量推进：${(result.actions||[]).join(' → ')}`:`已执行：${result.action}`);
      await refresh();
    }catch(reason){if(ticket===epoch.current){setError(describe(reason));setData(undefined);}}
    finally{lock.current=false;setBusy(false);}
  }
  if(!novelId||!screenplayId)return <EmptyState title="尚未选择剧本" detail="选择剧本后查看人工审批与生产阶段。"/>;
  return <section className="novel-help" aria-label="影视化 Pipeline"><strong>影视化 Pipeline</strong>
    <Button variant="ghost" disabled={busy||loading} onClick={()=>void refresh()}>刷新</Button>
    {loading&&<StatusMessage>正在读取影视化阶段…</StatusMessage>}
    {error&&<StatusMessage tone="error">{error}</StatusMessage>}
    {message&&<StatusMessage>{message}</StatusMessage>}
    {data&&!error&&<><p>下一阶段：{names[data.next_stage]||data.next_stage}</p>
      <Button variant="ghost" disabled={busy||loading||data.next_stage==='complete'} onClick={()=>void advance()}>推进下一阶段</Button>
      <Button variant="ghost" disabled={busy||loading||data.next_stage==='complete'} onClick={()=>void advance(true)}>推进到审批点</Button>
      <ul>{data.stages.map((stage:any)=><li key={stage.id}>{stage.complete?'✓':'○'} {names[stage.id]||stage.id}</li>)}</ul><p>视频任务：{data.motion.completed}/{data.motion.total}</p>
      <p>审批仍在原剧本流程完成。外部视频模型质量取决于已配置并实际执行的 Provider。</p></>}
  </section>;
}
