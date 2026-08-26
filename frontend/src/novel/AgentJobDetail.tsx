import {useQuery} from '@tanstack/react-query';
import {api} from '../api';
import {Badge,EmptyState,Panel} from '../ui/primitives';

export function AgentJobDetail({jobId}:{jobId?:string}){
  const query=useQuery({queryKey:['agent-job-detail',jobId],queryFn:()=>api.agentJob(jobId!),enabled:!!jobId,retry:false});
  if(!jobId)return <EmptyState title="未选择任务" detail="从历史列表选择一个 Agent Job。"/>;
  if(query.isLoading)return <Panel title="任务详情"><p role="status">正在加载任务详情…</p></Panel>;
  if(query.error)return <Panel title="任务详情"><p className="novel-error" role="alert">无法加载任务详情</p></Panel>;
  const job=query.data;
  const executionLabel=job.execution_mode==='deterministic'?'契约校验，未调用模型':'真实模型执行';
  return <Panel title="Agent Job 详情"><article className="novel-draft-review"><header><strong>{job.agent_name}</strong><Badge>{job.status}</Badge></header><p>任务说明：{job.instruction||'未填写说明'}</p><p className="novel-help">执行模式：{job.execution_mode} · {executionLabel} · 目标：{job.target}</p><p className="novel-help">Provider / 模型：{job.provider||'未指定'} / {job.model||'未指定'}</p><p className="novel-help">上下文哈希：{job.context_hash}</p><p className="novel-help">输出契约：{job.output_schema}</p>{job.error_code&&<p className="novel-error">错误：{job.error_code} · {job.error}</p>}{job.result?.structured_output&&<><h4>结构化输出</h4><pre>{JSON.stringify(job.result.structured_output,null,2)}</pre></>}{job.review&&<><h4>审核记录</h4><p>{job.review.decision} · {job.review.reviewed_by} · {job.review.note||'无备注'}</p></>}{job.application&&<><h4>应用快照</h4><pre>{JSON.stringify(job.application,null,2)}</pre></>}</article></Panel>;
}
