import {useMemo,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {ApiError,type CollaborationContext} from '../api';
import {useStudio} from '../store';
import {experimentalFeatures} from '../experimental/api';
import {useReviewAction} from '../experimental/styleReviewClient';
import {Badge,Button,EmptyState,StatusMessage} from '../ui/primitives';
import {pendingCanonReviewClient,type CanonReview} from './pendingCanonReviewClient';

let sequence=0;
export function PendingCanonReviewPanel({projectId,chapterId}:{projectId:string;chapterId?:string}){
  const token=useStudio(s=>s.sessionToken),scope=useStudio(s=>s.scope),actor=useStudio(s=>s.actor);
  const context=useMemo(()=>({sessionToken:token,scope,actor}),[token,scope,actor]);
  const key=useMemo(()=>++sequence,[projectId,context,chapterId]);
  return <CanonBody key={key} projectId={projectId} chapterId={chapterId} context={context} namespace={key}/>;
}
function CanonBody({projectId,chapterId,context,namespace}:{projectId:string;chapterId?:string;context:CollaborationContext;namespace:number}){
  const client=useMemo(()=>pendingCanonReviewClient(projectId,context),[projectId,context]);
  const flags=useQuery({queryKey:['canon-review-flags',namespace],queryFn:({signal})=>experimentalFeatures(signal,context),retry:false});
  const enabled=flags.data?.features['experimental.finding_review_v1']===true;
  const rows=useQuery({queryKey:['pending-canon-review',namespace],queryFn:({signal})=>client.list(signal),enabled,retry:false});
  const [selected,setSelected]=useState<CanonReview>();const [previewDirty,setPreviewDirty]=useState(false);const [sourceId,setSourceId]=useState(chapterId||'');
  const [reason,setReason]=useState('');const [confirmed,setConfirmed]=useState(false);const [operation,setOperation]=useState('');
  const action=useReviewAction();const error=action.error||rows.error||flags.error;
  const safeError=error instanceof ApiError?error.problem.message:'请求未完成，请刷新后重试。';
  const withheld=error instanceof ApiError&&[401,403,404].includes(error.problem.status);
  const blocked=action.busy||rows.isLoading||!!rows.error||withheld;
  function edit(row:CanonReview){setSelected(row);setPreviewDirty(false);if(row.source)setSourceId(row.source.chapter_id);setConfirmed(false);setOperation(crypto.randomUUID());}
  async function preview(row:CanonReview,explicitSource=false){await action.run(async current=>{const fresh=await client.preview(row.id,explicitSource?(sourceId.trim()||undefined):undefined);if(current())edit(fresh);});}
  return <section aria-label="原始 Canon 候选审阅"><h3>原始 Canon 候选审阅</h3>
    {flags.isLoading&&<StatusMessage>正在读取 Canon 审阅状态…</StatusMessage>}
    {!flags.isLoading&&!flags.error&&!enabled&&<StatusMessage>版本化 Canon 审阅未启用。</StatusMessage>}
    {error&&<StatusMessage tone="error">{safeError}</StatusMessage>}
    {enabled&&!flags.error&&<>
      <p className="novel-help">此处操作原有项目级 Canon 候选。批准会写入原 Canon；不会生成第二套资料。旧候选没有历史来源版本时，必须明确核对当前来源。</p>
      <Button disabled={action.busy} onClick={()=>void action.run(async()=>{await rows.refetch();setSelected(undefined);setConfirmed(false);})}>刷新 Canon 审阅</Button>
      {rows.isLoading&&<StatusMessage>正在读取候选与历史…</StatusMessage>}
      {!rows.isLoading&&!rows.error&&!rows.data?.items.length&&<EmptyState title="没有 Canon 候选" detail="生成结果提出的事实仍需作者批准才能成为 Canon。"/>}
      {action.notice&&<StatusMessage tone="success">{action.notice}</StatusMessage>}
      {!rows.error&&!withheld&&rows.data?.items.map(row=><article className="experimental-record" key={row.id}><strong>Canon {row.id}</strong><Badge>{row.status} · v{row.version}</Badge><Button disabled={blocked} onClick={()=>void preview(row)}>查看 Canon 候选与历史</Button>
        {row.recovery_required&&<><StatusMessage tone="warning">检测到中断记录。先恢复已经提交的凭据；尚未写入的操作可取消后重新审阅。</StatusMessage><Button disabled={blocked} onClick={()=>void action.run(async current=>{const value=await client.recover(row.id,row.version);if(current()){edit(value);await rows.refetch();}},'已恢复提交凭据，没有重复写入事实。')}>恢复 Canon 提交凭据</Button><Button disabled={blocked} onClick={()=>void action.run(async current=>{await client.cancelRecovery(row.id,row.version);if(current()){setSelected(undefined);await rows.refetch();}},'已取消未提交操作；可以重新预览。')}>取消尚未提交的 Canon 操作</Button></>}
      </article>)}
      {!rows.error&&!withheld&&selected&&<section aria-label="Canon 人工确认"><h4>候选 v{selected.version} · {selected.status}</h4>
        <ul>{selected.proposals.map((proposal,index)=><li key={index}>{JSON.stringify(proposal)}</li>)}</ul>
        <p>来源状态：{selected.source_state} · {selected.lineage}</p>
        {selected.source&&<p>已核对来源 {selected.source.chapter_id} · v{selected.source.version}</p>}
        {selected.source_evidence&&<textarea readOnly aria-label="Canon 来源正文快照" rows={6} value={selected.source_evidence.content}/>}
        {selected.stale_source&&<StatusMessage tone="warning">审阅后的来源已改变或不可用。保留历史凭据，不会重复批准。</StatusMessage>}
        {selected.status==='PENDING'&&!selected.recovery_required&&<><label>明确来源章节 ID<input aria-label="Canon 来源章节 ID" value={sourceId} disabled={action.busy} onChange={e=>{setSourceId(e.target.value);setPreviewDirty(true);setConfirmed(false);}}/></label><Button disabled={blocked} onClick={()=>void preview(selected,true)}>重新预览 Canon 来源</Button>
          <label>审阅理由<textarea aria-label="Canon 审阅理由" value={reason} maxLength={2000} disabled={action.busy} onChange={e=>{setReason(e.target.value);setConfirmed(false);setOperation(crypto.randomUUID());}}/></label>
          <label><input type="checkbox" checked={confirmed} disabled={action.busy} onChange={e=>setConfirmed(e.target.checked)}/>已核对全部候选事实与来源</label>
          <div className="novel-actions">{(['approve','reject'] as const).map(decision=><Button key={decision} disabled={blocked||previewDirty||!confirmed||!reason.trim()||!selected.allowed_actions.includes(decision)} onClick={()=>void action.run(async current=>{const result=await client.review(selected.id,{expected_version:selected.version,preview_digest:selected.preview_digest,chapter_id:selected.source?.chapter_id||null,action:decision,reason,operation_id:operation,confirmed:true});if(current()){edit(result);await rows.refetch();}},decision==='approve'?'已写入原 Canon。':'已驳回候选，正文和 Canon 未改变。')}>{decision==='approve'?'确认批准 Canon':'确认驳回 Canon'}</Button>)}</div></>}
        <details><summary>Canon 审阅历史（{selected.history.length}）</summary>{selected.history.map((entry,index)=><p key={index}>{entry.action} · v{entry.version} · {entry.actor_id} · {entry.reason}</p>)}</details>
        <Button disabled={action.busy} onClick={()=>{setSelected(undefined);setConfirmed(false);}}>关闭 Canon 审阅</Button>
      </section>}
    </>}
  </section>;
}
