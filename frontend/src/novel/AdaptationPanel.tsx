import {useRef,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {api,ApiError,getCollaborationContext} from '../api';
import {Badge,Button,EmptyState,Panel,StatusMessage} from '../ui/primitives';
import './adaptation.css';

const targets=[['COMMERCIAL','商业小说'],['LITERARY','文学小说'],['SCREEN','影视版本'],['CUSTOM','自定义风格']] as const;
function describe(error:unknown){
  if(error instanceof ApiError){
    if(error.status===409)return '版本、来源或写入结果存在冲突。草稿已保留，请读取最新状态后核对，不能自动重放。';
    if(error.status===401||error.status===403)return '当前身份无权操作，或权限已撤销。';
    if(error.status===404)return '功能已关闭，或当前来源已不可读。';
    if(error.status===428)return '需要当前方案版本，请刷新后重新操作。';
  }
  return '操作未完成。请保留草稿并读取最新状态，未知写入结果不能自动重试。';
}
function BlueprintEditor({item,novelId,branchId,onSaved,disabled}:{item:any;novelId:string;branchId?:string;onSaved:()=>Promise<void>;disabled:boolean}){
  const [draft,setDraft]=useState(()=>structuredClone(item.blueprint));const [revision,setRevision]=useState(item.revision);const saveLock=useRef(false);
  const save=useMutation({mutationFn:()=>api.updateAdaptationBlueprint(novelId,item.id,{...draft,expected_revision:revision},branchId),onSuccess:async row=>{setRevision(row.revision);setDraft(structuredClone(row.blueprint));await onSaved();},onSettled:()=>{saveLock.current=false;}});
  const busy=disabled||save.isPending;
  return <section className="novel-draft-review" aria-label="改编蓝图编辑">
    <p className="novel-help">方案版本 {revision} · 蓝图修订 v{item.blueprint_revision||1}</p>
    {save.isError&&<StatusMessage tone="error">{describe(save.error)}</StatusMessage>}
    {item.revision!==revision&&<StatusMessage tone="warning">服务器已有版本 {item.revision}。当前编辑内容未被替换。<Button disabled={busy} onClick={()=>{setDraft(structuredClone(item.blueprint));setRevision(item.revision);save.reset();}}>放弃本地编辑并加载最新蓝图</Button></StatusMessage>}
    <label>改编重点<textarea aria-label="改编重点" value={draft.focus} disabled={busy} onChange={event=>setDraft({...draft,focus:event.target.value})}/></label>
    <label>节奏策略<textarea aria-label="节奏策略" value={draft.pacing} disabled={busy} onChange={event=>setDraft({...draft,pacing:event.target.value})}/></label>
    <label>输出格式<input aria-label="输出格式" value={draft.format} disabled={busy} onChange={event=>setDraft({...draft,format:event.target.value})}/></label>
    <label>约束（每行一条）<textarea aria-label="约束（每行一条）" value={draft.constraints.join('\n')} disabled={busy} onChange={event=>setDraft({...draft,constraints:event.target.value.split('\n')})}/></label>
    <ol>{draft.chapter_map.map((mapping:any,index:number)=><li key={mapping.source_chapter_id}><strong>{mapping.source_title}</strong><label>目标单元<input aria-label="目标单元" value={mapping.unit} disabled={busy} onChange={event=>{const chapter_map=[...draft.chapter_map];chapter_map[index]={...mapping,unit:event.target.value};setDraft({...draft,chapter_map});}}/></label><label>改编动作<textarea aria-label="改编动作" value={mapping.action} disabled={busy} onChange={event=>{const chapter_map=[...draft.chapter_map];chapter_map[index]={...mapping,action:event.target.value};setDraft({...draft,chapter_map});}}/></label></li>)}</ol>
    <Button disabled={busy||item.revision!==revision} onClick={()=>{if(!saveLock.current){saveLock.current=true;save.mutate();}}}>{save.isPending?'正在保存…':'保存蓝图修订'}</Button>
  </section>;
}
function RevisionHistory({novelId,item,branchId}:{novelId:string;item:any;branchId?:string}){
  const [open,setOpen]=useState(false);
  const query=useQuery({queryKey:['adaptation-history',novelId,branchId,item.id,item.revision],queryFn:()=>api.adaptationHistory(novelId,item.id,branchId),enabled:open,retry:false});
  return <details onToggle={event=>setOpen(event.currentTarget.open)}><summary>查看方案修订与恢复记录</summary>
    {query.isLoading&&<StatusMessage>正在读取历史…</StatusMessage>}
    {query.isError&&<StatusMessage tone="error">{describe(query.error)}</StatusMessage>}
    {query.data&&!query.isError&&<><p>当前版本 {query.data.revision} · {query.data.materialization?.phase||'尚未创建工作副本'}</p><ol>{query.data.items.map((row:any)=><li key={row.revision}>v{row.revision} · {row.status} · {row.updated_at}</li>)}</ol></>}
  </details>;
}
type AdaptationProps={novelId?:string;branchId?:string;requestedProposalId?:string;requestedTaskId?:string;requestedRevision?:number};
export function AdaptationPanel(props:AdaptationProps){
  const context=getCollaborationContext();
  return <AdaptationBody key={[props.novelId,props.branchId,context.sessionToken,context.actor?.id].join('|')} {...props}/>;
}
function AdaptationBody({novelId,branchId,requestedProposalId,requestedTaskId,requestedRevision}:AdaptationProps){
  const qc=useQueryClient();const [target,setTarget]=useState('COMMERCIAL'),[title,setTitle]=useState(''),[instruction,setInstruction]=useState('');
  const [error,setError]=useState('');const commandLock=useRef(false);const verifiedRequest=useRef('');const context=getCollaborationContext();const identity=[novelId,branchId,context.sessionToken,context.actor?.id];
  const refresh=()=>qc.invalidateQueries({queryKey:['adaptation-proposals']});
  const catalog=useQuery({queryKey:['adaptation-catalog',...identity],queryFn:()=>api.adaptationCatalog(novelId!,branchId),enabled:!!novelId,retry:false});
  const proposals=useQuery({queryKey:['adaptation-proposals',...identity],queryFn:()=>api.adaptationProposals(novelId!,branchId),enabled:!!novelId&&catalog.isSuccess,retry:false});
  const mutation=useMutation({mutationFn:async(command:()=>Promise<unknown>)=>command(),onMutate:()=>setError(''),onSuccess:refresh,onError:reason=>{setError(describe(reason));refresh();},onSettled:()=>{commandLock.current=false;}});
  const execute=(command:()=>Promise<unknown>)=>{if(!commandLock.current){commandLock.current=true;mutation.mutate(command);}};
  const canWrite=Boolean(catalog.data?.can_write),canReview=Boolean(catalog.data?.can_review),lifecycle=Boolean(catalog.data?.enabled);
  const action=(item:any,value:'cancel'|'recover',taskId?:string)=>execute(()=>api.adaptationAction(novelId!,item.id,value,item.revision,branchId,taskId));
  const readError=catalog.error||proposals.error;
  const requested=Boolean(requestedProposalId||requestedTaskId);
  const requestKey=[requestedProposalId,requestedTaskId,requestedRevision].join('|');
  const requestedRow=(proposals.data||[]).find(item=>item.id===requestedProposalId&&Boolean(requestedTaskId)&&item.execution_manifest?.some((task:any)=>task.id===requestedTaskId));
  if(requestedRow&&requestedRow.revision===requestedRevision)verifiedRequest.current=requestKey;
  const visible=requested?(requestedRow&&verifiedRequest.current===requestKey?[requestedRow]:[]):(proposals.data||[]);
  return <Panel className="novel-adaptation-panel" title="智能改编" actions={novelId&&<Button disabled={catalog.isFetching||proposals.isFetching} onClick={()=>{void catalog.refetch();void proposals.refetch();}}>读取最新状态</Button>}>
    {!novelId?<EmptyState title="尚未打开小说" detail="打开一部小说后创建改编方案。"/>:catalog.isLoading||proposals.isLoading?<StatusMessage>正在读取改编方案…</StatusMessage>:readError?<StatusMessage tone="error">{describe(readError)}</StatusMessage>:<section className="novel-draft-review">
      {error&&<StatusMessage tone="error">{error}</StatusMessage>}
      {mutation.isPending&&<StatusMessage>正在处理，请勿重复提交…</StatusMessage>}
      {!lifecycle&&<StatusMessage tone="warning">扩展恢复操作已关闭（adaptation_lifecycle_v1）。现有改编仍保留版本与审阅保护。</StatusMessage>}
      {!canWrite&&<StatusMessage tone="warning">当前身份没有改编编辑权限。</StatusMessage>}
      <p className="novel-help">范围：{branchId?'当前协作分支正文':'项目主线正文'}。模型改写：NOT_CONFIGURED，需要原任务系统的准入和预算预检。本地准备稿不会宣称实质改写完成。</p>
      <label>改编目标<select aria-label="改编目标" value={target} disabled={!canWrite} onChange={event=>setTarget(event.target.value)}>{targets.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <label>方案名称<input aria-label="改编方案名称" value={title} maxLength={200} disabled={!canWrite} onChange={event=>setTitle(event.target.value)} placeholder="留空则自动命名"/></label>
      <label>改编要求<textarea aria-label="改编要求" value={instruction} disabled={!canWrite} onChange={event=>setInstruction(event.target.value)} placeholder="例如：压缩为六集，保留主要人物关系"/></label>
      <Button variant="primary" disabled={!canWrite||mutation.isPending} onClick={()=>execute(async()=>{const result=await api.createAdaptationProposal(novelId!,{target,title,instruction},branchId);setTitle('');setInstruction('');return result;})}>创建改编方案</Button>
      {!proposals.data?.length&&<EmptyState title="暂无改编方案" detail="原作章节不会因创建方案而被修改。"/>}
      {requested&&!visible.length&&<StatusMessage tone="error">请求的改编方案或原任务不存在、范围不符或已不可读。不会打开其他方案。</StatusMessage>}
      <ul className="novel-record-list">{visible.map(item=><li key={item.id}><article aria-label={`改编方案 ${item.title}`}>
        <header><strong>{item.title}</strong><Badge tone={item.status==='MATERIALIZED'?'success':'warning'}>{item.status}</Badge></header>
        <p className="novel-help">方案版本 {item.revision} · {targets.find(([value])=>value===item.target)?.[1]||item.target} · 锁定 {item.source_chapter_count} 章</p><p>{item.instruction||'未填写额外要求'}</p>
        {item.status==='DRAFT'&&item.blueprint?<details><summary>编辑改编蓝图</summary><BlueprintEditor item={item} novelId={novelId!} branchId={branchId} onSaved={refresh} disabled={!canWrite||mutation.isPending}/></details>:item.blueprint&&<details><summary>查看已冻结蓝图</summary><p><strong>重点：</strong>{item.blueprint.focus}</p><p><strong>节奏：</strong>{item.blueprint.pacing}</p><p><strong>格式：</strong>{item.blueprint.format}</p><ol>{item.blueprint.chapter_map.map((mapping:any)=><li key={mapping.source_chapter_id}>{mapping.unit} · {mapping.source_title}：{mapping.action}</li>)}</ol></details>}
        <details><summary>查看原作版本快照</summary><ul>{item.source_versions.map((source:{chapter_id:string;version:number})=><li key={source.chapter_id}>{source.chapter_id} · v{source.version}</li>)}</ul><p className="novel-help">来源摘要：{item.source_digest}</p></details>
        {lifecycle&&<RevisionHistory novelId={novelId!} item={item} branchId={branchId}/>}
        {item.execution_manifest&&<details open={requestedTaskId?true:undefined}><summary>查看改编执行清单</summary><p className="novel-help">当前状态：{item.execution_status}</p><ol>{item.execution_manifest.filter((task:any)=>!requestedTaskId||task.id===requestedTaskId).map((task:any)=><li key={task.id} aria-label={`改编任务 ${task.id}`}><strong>{task.unit}</strong> · {task.action} <Badge>{task.status}</Badge>
          <p className="novel-help">来源 {task.source_chapter_id} v{task.source_version} → 工作副本 {task.target_chapter_id}{task.target_version?` v${task.target_version}`:''}</p>
          {['PENDING_REWRITE','REJECTED','FAILED','NOT_CONFIGURED'].includes(task.status)&&<Button disabled={!canWrite||mutation.isPending} onClick={()=>execute(()=>api.generateAdaptationDraft(novelId!,item.id,task.id,{mode:'deterministic',expected_revision:item.revision},branchId))}>生成本地准备稿</Button>}
          {task.draft&&<details><summary>审阅草稿正文与来源绑定</summary><p>{task.draft.content}</p><p className="novel-help">来源摘要：{task.source_digest} · 工作副本摘要：{task.target_digest}</p><p>{task.draft.note||task.draft.verification}</p></details>}
          {task.status==='AWAITING_REVIEW'&&<><Button disabled={!canReview||mutation.isPending} onClick={()=>execute(()=>api.reviewAdaptationDraft(novelId!,item.id,task.id,'ACCEPTED',branchId,item.revision))}>接受草稿</Button><Button disabled={!canReview||mutation.isPending} onClick={()=>execute(()=>api.reviewAdaptationDraft(novelId!,item.id,task.id,'REJECTED',branchId,item.revision))}>驳回草稿</Button></>}
          {task.status==='ACCEPTED'&&<Button disabled={!canWrite||mutation.isPending} onClick={()=>execute(()=>api.applyAdaptationDraft(novelId!,item.id,task.id,branchId,item.revision))}>写入工作副本</Button>}
          {lifecycle&&!['APPLIED','CANCELLED'].includes(task.status)&&<Button disabled={!canWrite||mutation.isPending} onClick={()=>action(item,'cancel',task.id)}>取消此任务</Button>}
          {lifecycle&&['RUNNING','CANCELLED','FAILED','RECOVERY_REQUIRED','NOT_CONFIGURED'].includes(task.status)&&<Button disabled={!canWrite||mutation.isPending} onClick={()=>action(item,'recover',task.id)}>核对并恢复任务</Button>}
          {task.error&&<StatusMessage tone="error">{task.error_code}：{task.error}</StatusMessage>}
          {task.status==='RECOVERY_REQUIRED'&&<StatusMessage tone="warning">写入结果未确认。恢复只核对持久记录，不自动再次写入。</StatusMessage>}
        </li>)}</ol></details>}
        {item.status==='DRAFT'&&<Button disabled={!canReview||mutation.isPending} onClick={()=>execute(()=>api.approveAdaptationProposal(novelId!,item.id,branchId,item.revision))}>批准方案</Button>}
        {item.status==='APPROVED'&&<Button disabled={!canWrite||mutation.isPending} onClick={()=>execute(()=>api.materializeAdaptation(novelId!,item.id,branchId,item.revision))}>生成改编版本</Button>}
        {lifecycle&&!['MATERIALIZED','CANCELLED'].includes(item.status)&&<Button disabled={!canWrite||mutation.isPending} onClick={()=>action(item,'cancel')}>取消方案</Button>}
        {lifecycle&&['CANCELLED','MATERIALIZING','RECOVERY_REQUIRED'].includes(item.status)&&<><StatusMessage tone="warning">{item.materialization?.phase||item.status} · 中断的写入不会自动重放。</StatusMessage><Button disabled={!canWrite||mutation.isPending} onClick={()=>action(item,'recover')}>核对并恢复方案</Button></>}
        {item.status==='MATERIALIZED'&&<p className="novel-help">改编工作副本已创建：{item.adapted_novel_id}。章节等待改写，不代表已经完成改编。</p>}
      </article></li>)}</ul>
    </section>}
  </Panel>;
}
