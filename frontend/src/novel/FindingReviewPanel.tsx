import {useMemo, useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {ApiError, type Chapter, type CollaborationContext} from '../api';
import {useStudio} from '../store';
import {Badge, Button, EmptyState, StatusMessage} from '../ui/primitives';
import {experimentalFeatures} from '../experimental/api';
import {useReviewAction} from '../experimental/styleReviewClient';
import {findingReviewClient, type FindingEvidence, type FindingKind, type ReviewedFinding} from './findingReviewClient';

let instance=0;
export function FindingReviewPanel({projectId,chapter}:{projectId:string;chapter?:Chapter}) {
  const sessionToken=useStudio(s=>s.sessionToken),scope=useStudio(s=>s.scope),actor=useStudio(s=>s.actor);
  const context=useMemo(()=>({sessionToken,scope,actor}),[sessionToken,scope,actor]);
  const key=useMemo(()=>++instance,[projectId,context,chapter?.id]);
  return <FindingReviewBody key={key} projectId={projectId} chapter={chapter} context={context} namespace={key}/>;
}
function FindingReviewBody({projectId,chapter,context,namespace}:{projectId:string;chapter?:Chapter;context:CollaborationContext;namespace:number}) {
  const client=useMemo(()=>findingReviewClient(projectId,context),[projectId,context]);
  const flags=useQuery({queryKey:['finding-review-flags',namespace],queryFn:({signal})=>experimentalFeatures(signal,context),retry:false});
  const enabled=flags.data?.features['experimental.finding_review_v1']===true;
  const [kind,setKind]=useState<FindingKind>('continuity');
  const rows=useQuery({queryKey:['finding-review',namespace,kind],queryFn:({signal})=>client.list(kind,signal),enabled,retry:false});
  const [selected,setSelected]=useState<ReviewedFinding>();const [reason,setReason]=useState('');
  const [decision,setDecision]=useState('intentional');const [confirmed,setConfirmed]=useState(false);
  const [facts,setFacts]=useState('');const [evidence,setEvidence]=useState<FindingEvidence>();
  const [operation,setOperation]=useState('');const action=useReviewAction();
  const error=action.error||rows.error||flags.error;
  const problem=error instanceof ApiError?error.problem:undefined;
  const withheld=!!problem&&[401,403,404].includes(problem.status);
  const blocked=action.busy||rows.isLoading||!!rows.error||withheld;
  function select(row:ReviewedFinding){setSelected(row);setReason('');setConfirmed(false);setEvidence(undefined);setOperation(crypto.randomUUID());}
  async function run(){await action.run(async current=>{
    const parsed=facts.trim()?JSON.parse(facts):{};
    if(!parsed||typeof parsed!=='object'||Array.isArray(parsed))throw new Error('事实需要 JSON 对象');
    await client.check(kind,{chapter_id:chapter!.id,expected_source_version:chapter!.version,facts:parsed});
    if(current()){await rows.refetch();setSelected(undefined);setConfirmed(false);}
  },'检查已保存。相同证据的有意设置会保留。');}
  return <section aria-label="来源绑定的问题审阅">
    <h3>来源绑定的问题审阅</h3>
    {flags.isLoading&&<StatusMessage>正在读取审阅功能状态…</StatusMessage>}
    {!flags.isLoading&&!flags.error&&!enabled&&<StatusMessage>此工作区未启用版本化问题审阅。</StatusMessage>}
    {error&&<StatusMessage tone="error">{problem?.message||(error instanceof SyntaxError?'事实 JSON 格式错误':'请求未完成，请重试。')}{problem?.code?` (${problem.code})`:''}</StatusMessage>}
    {enabled&&!flags.error&&<>
      <p className="novel-help">人工确认仅作用于这次来源版本和问题指纹。正文或事实改变后必须重新审阅。规则校验未调用模型。</p>
      <label>问题来源 <select aria-label="问题来源" value={kind} disabled={action.busy} onChange={e=>{setKind(e.target.value as FindingKind);setSelected(undefined);setEvidence(undefined);setConfirmed(false);}}><option value="continuity">连续性</option><option value="narrative">叙事与伏笔</option></select></label>
      <details><summary>检查使用的事实</summary><p className="novel-help">本地可留空读取已存连续性资料或叙事期望；分支需要明确事实。手动叙事事实需要 current_chapter 和 expectations。资料缺失会保持未配置，不会借用主线正文。</p><textarea aria-label="审阅事实 JSON" rows={6} value={facts} maxLength={200000} disabled={action.busy} onChange={e=>setFacts(e.target.value)}/></details>
      {!chapter&&<EmptyState title="选择来源章节" detail="需要已保存的确切章节版本才能检查。"/>}
      <div className="novel-actions"><Button disabled={!chapter||blocked} loading={action.busy} onClick={()=>void run()}>检查并保存可审阅问题</Button><Button disabled={action.busy} onClick={()=>void action.run(async current=>{const result=await rows.refetch();if(current()&&selected){const latest=result.data?.items.find(row=>row.id===selected.id);setSelected(latest);setEvidence(undefined);setConfirmed(false);setOperation(crypto.randomUUID());}})}>刷新审阅问题</Button></div>
      {rows.isLoading&&<StatusMessage>正在读取问题与审阅历史…</StatusMessage>}
      {action.notice&&<StatusMessage tone="success">{action.notice}</StatusMessage>}
      {!rows.isLoading&&!rows.error&&!rows.data?.items.length&&<EmptyState title="没有来源绑定的问题" detail="运行检查后会在这里出现；旧版未绑定来源的问题仍显示在原清单。"/>}
      {!rows.error&&!withheld&&rows.data?.items.map(row=><article className="experimental-record" key={row.id}>
        <p>{row.description}</p><Badge tone={row.stale_source?'warning':'info'}>{row.effective_status} · v{row.review_version}</Badge>
        <p className="novel-help">{row.finding_type} · 来源章节 v{row.source.version} · {row.provenance}</p>
        {row.stale_source&&<StatusMessage tone="warning">来源已改变，原有意设置不再生效。重新检查后才能处理新问题。</StatusMessage>}
        <Button disabled={blocked} onClick={()=>select(row)}>审阅此问题</Button>
        <Button disabled={blocked} onClick={()=>void action.run(async current=>{const result=await client.evidence(kind,row.id);if(current()){setEvidence(result);setSelected(undefined);}},'已打开准确来源版本。')}>打开确切来源 v{row.source.version}</Button>
        <details><summary>审阅历史（{row.review_history.length}）</summary>{row.review_history.length?row.review_history.map((entry,index)=><p key={index}>{entry.action} · {entry.actor_id} · v{entry.version} · {entry.reason}</p>):<p>尚无人审阅</p>}</details>
      </article>)}
      {!rows.error&&!withheld&&evidence&&<section aria-label="确切来源版本"><h4>来源 {evidence.navigation.chapter_id} · v{evidence.chapter.version}</h4><p>{evidence.stale_source?'历史快照，当前正文已经改变':'当前来源版本'}</p><textarea readOnly aria-label="来源正文快照" rows={8} value={evidence.chapter.content}/><p>证据：{evidence.evidence_ids.join('、')||'章节级规则证据；无定位片段'}</p><Button onClick={()=>setEvidence(undefined)}>关闭来源</Button></section>}
      {!rows.error&&!withheld&&selected&&<section aria-label="人工审阅决定"><h4>人工审阅：{selected.description}</h4>
        <label>决定 <select aria-label="审阅决定" value={decision} disabled={action.busy} onChange={e=>{setDecision(e.target.value);setConfirmed(false);setOperation(crypto.randomUUID());}}><option value="intentional" disabled={selected.stale_source}>这是有意设置</option><option value="resolve" disabled={selected.stale_source}>标记处理完成</option><option value="reopen">撤销处理，重新打开</option><option value="feedback">只记录反馈</option></select></label>
        <label>审阅理由 <textarea aria-label="审阅理由" value={reason} maxLength={2000} disabled={action.busy} onChange={e=>{setReason(e.target.value);setConfirmed(false);setOperation(crypto.randomUUID());}}/></label>
        <label><input type="checkbox" checked={confirmed} disabled={action.busy} onChange={e=>setConfirmed(e.target.checked)}/>已核对来源版本和证据</label>
        <div className="novel-actions"><Button disabled={blocked||!confirmed||!reason.trim()||!selected.allowed_actions.includes(decision)} onClick={()=>void action.run(async current=>{await client.review(kind,selected.id,{expected_version:selected.review_version,source_digest:selected.source_digest,finding_fingerprint:selected.finding_fingerprint,action:decision,reason,operation_id:operation,confirmed:true});if(current()){setSelected(undefined);setConfirmed(false);await rows.refetch();}},'审阅决定已保存。')}>确认保存审阅</Button><Button disabled={action.busy} onClick={()=>{setSelected(undefined);setConfirmed(false);setReason('');}}>取消审阅</Button></div>
        {problem?.status===409&&<p className="novel-help">理由保留在此。请刷新后重新选择最新问题，重新确认；不会自动覆盖他人的决定。</p>}
      </section>}
    </>}
  </section>;
}
