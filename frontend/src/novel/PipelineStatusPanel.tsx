import {useEffect,useState} from 'react';
import {api} from '../api';
import {Button} from '../ui/primitives';

export function PipelineStatusPanel({novelId,screenplayId}:{novelId?:string;screenplayId?:string}){
  const [data,setData]=useState<any>(),[message,setMessage]=useState('');
  const refresh=()=>{if(novelId&&screenplayId)api.pipelineStatus(novelId,screenplayId).then(setData).catch(()=>setData(undefined));};
  useEffect(refresh,[novelId,screenplayId]);
  if(!data)return null;
  const names:Record<string,string>={screenplay:'剧本审批',shots:'镜头规划',storyboard:'分镜设计',transitions:'转场设计',motion:'视频生成',complete:'已完成'};
  async function advance(){if(!novelId||!screenplayId)return;const result=await api.advancePipeline(novelId,screenplayId);setMessage(result.action==='MANUAL_APPROVAL_REQUIRED'?'需要先人工批准当前阶段。':`已执行：${result.action}`);refresh();}
  async function advanceUntilGate(){if(!novelId||!screenplayId)return;const result=await api.advancePipelineUntilGate(novelId,screenplayId);setMessage(`批量推进：${(result.actions||[]).join(' → ')}`);setData(result.status);}
  return <section className="novel-help"><strong>影视化 Pipeline</strong><p>下一阶段：{names[data.next_stage]||data.next_stage}</p><Button variant="ghost" onClick={refresh}>刷新</Button> <Button variant="ghost" disabled={!novelId||!screenplayId||data.next_stage==='complete'} onClick={advance}>推进下一阶段</Button> <Button variant="ghost" disabled={!novelId||!screenplayId||data.next_stage==='complete'} onClick={advanceUntilGate}>推进到审批点</Button>{message&&<p>{message}</p>}<p>{data.stages.map((stage:any)=><span key={stage.id} style={{marginRight:12}}>{stage.complete?'✓':'○'} {names[stage.id]||stage.id}</span>)}</p><p>视频任务：{data.motion.completed}/{data.motion.total}</p></section>;
}
