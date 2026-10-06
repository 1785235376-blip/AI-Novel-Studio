import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {Download,FileArchive,FileText,LoaderCircle,PackageCheck} from 'lucide-react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {api,apiErrorView,CollaborationContext,ExportJob,getCollaborationContext,Scope} from '../api';
import {Badge,Button,EmptyState,Panel} from '../ui/primitives';
import './export.css';

const formats=[
  {id:'txt',label:'TXT 小说',detail:'纯文本，适合备份与快速分享',available:true,icon:FileText},
  {id:'markdown',label:'Markdown',detail:'保留章节结构与标题层级',available:true,icon:FileText},
  {id:'json',label:'项目 JSON',detail:'完整项目数据交换格式',available:true,icon:PackageCheck},
  {id:'docx',label:'Word 文档',detail:'基础 OOXML 文稿；模板与目录增强待接入',available:true,icon:FileText},
  {id:'pdf',label:'PDF 文档',detail:'本地确定性分页与中文字体回退；正式发行可配置嵌入字体',available:true,icon:FileText},
  {id:'epub',label:'EPUB 电子书',detail:'基础 EPUB 3 导航与章节；封面资源待接入',available:true,icon:FileArchive},
  {id:'screenplay',label:'影视剧本预览',detail:'确定性 Markdown 预览；标准排版仍待接入',available:true,icon:FileText},
  {id:'screenplay-fountain',label:'Fountain 剧本',detail:'行业通用纯文本剧本格式，保留场景、动作与对白',available:true,icon:FileText},
  {id:'screenplay-docx',label:'Word 剧本',detail:'独立剧本 OOXML 文档，保留场景、动作与对白',available:true,icon:FileText},
  {id:'screenplay-package',label:'剧本资源包 ZIP',detail:'Fountain、Word 与创建时冻结的资源；缺少资源时明确失败',available:true,icon:FileArchive},
  {id:'shot-list-package',label:'镜头资源包 ZIP',detail:'扩展镜头表、版本清单与摘要校验后的资源',available:true,icon:FileArchive},
  {id:'storyboard-package',label:'分镜资源包 ZIP',detail:'离线分镜 HTML、资源与来源清单',available:true,icon:FileArchive},
  {id:'shot-list',label:'镜头表 CSV',detail:'确定性镜头字段导出；对白扩展待接入',available:true,icon:FileArchive},
  {id:'storyboard',label:'分镜预览',detail:'确定性 Markdown 预览；图片资源待接入',available:true,icon:FileArchive},
] as const;

export function ExportPanel({novelId,scope,sessionToken,requestedTaskId}:{novelId?:string;scope?:Scope|null;sessionToken?:string;requestedTaskId?:string}){
  const context=getCollaborationContext();
  const activeScope=scope===undefined?context.scope:scope;
  const scopeKey=JSON.stringify([novelId||'',activeScope?.workspaceId||'',activeScope?.projectId||'',activeScope?.storylineId||'',activeScope?.branchId||'']);
  // Remount the job observer and mutations on every project, branch or session change.
  // Session credentials are used only for React identity, never in query cache keys.
  return <ScopedExportPanel key={JSON.stringify([scopeKey,sessionToken??context.sessionToken])} novelId={novelId} requestedTaskId={requestedTaskId} scopeKey={scopeKey} requestContext={{sessionToken:sessionToken??context.sessionToken,scope:activeScope??undefined,actor:context.actor}}/>;
}

function ScopedExportPanel({novelId,scopeKey,requestContext,requestedTaskId}:{novelId?:string;scopeKey:string;requestContext:CollaborationContext;requestedTaskId?:string}){
  const active=useRef(true);
  useLayoutEffect(()=>{active.current=true;return()=>{active.current=false}},[]);
  const [jobId,setJobId]=useState(requestedTaskId || '');
  useEffect(()=>{if(requestedTaskId)setJobId(requestedTaskId)},[requestedTaskId]);
  // A per-mount opaque identity prevents cached history crossing user sessions.
  // Never place the session token in query keys or browser storage.
  const [observerId]=useState(()=>globalThis.crypto?.randomUUID?.()||Math.random().toString(36));
  const [statusFilter,setStatusFilter]=useState('');
  const [offset,setOffset]=useState(0);
  const historyKey=['export-history',scopeKey,observerId];
  const history=useQuery({queryKey:[...historyKey,statusFilter,offset],queryFn:()=>api.exportHistory(novelId!,statusFilter,offset,requestContext),enabled:!!novelId,refetchInterval:(q)=>q.state.data?.items?.some(item=>['queued','running'].includes(item.status))?2000:false});
  useEffect(()=>{if(active.current&&!jobId&&history.data?.items?.length)setJobId(history.data.items[0].id)},[history.data,jobId]);
  const client=useQueryClient();
  const selected=useQuery({queryKey:['export-job',scopeKey,observerId,jobId],queryFn:async()=>{const row=await api.exportJob(jobId,requestContext);if(row.novel_id!==novelId)throw new Error('EXPORT_PROJECT_CHANGED');return row},enabled:!!jobId,refetchInterval:(q)=>['queued','running'].includes(q.state.data?.status||'')?700:false});
  const start=useMutation({mutationFn:(format:string)=>api.createExport(novelId!,format,requestContext),onSuccess:(job)=>{if(active.current){setJobId(job.id);void client.invalidateQueries({queryKey:historyKey})}}});
  const cancel=useMutation({mutationFn:(id:string)=>api.cancelExport(id,requestContext),onSuccess:(next)=>{if(active.current){client.setQueryData(['export-job',scopeKey,observerId,next.id],next);void client.invalidateQueries({queryKey:historyKey})}}});
  const retry=useMutation({mutationFn:(id:string)=>api.retryExport(id,requestContext),onSuccess:(job)=>{if(active.current){setJobId(job.id);void client.invalidateQueries({queryKey:historyKey})}}});
  const downloadJob=useMutation({mutationFn:(target:{id:string;filename:string})=>api.exportDownload(target.id,requestContext).then(blob=>({blob,filename:target.filename}))});
  const job=selected.isError||history.isError?undefined:selected.data as ExportJob|undefined;
  function download(){if(!job?.result?.filename)return;downloadJob.mutate({id:job.id,filename:job.result.filename},{onSuccess:({blob,filename})=>{if(!active.current)return;const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),0)}})}
  const label=job?({queued:'排队中',running:'处理中',succeeded:'已完成',failed:'失败',cancelled:'已取消'} as Record<string,string>)[job.status]||'未知状态':'选择格式';
  const busy= start.isPending||cancel.isPending||retry.isPending;
  return <Panel title="导出中心" actions={<Badge tone={job?.status==='succeeded'?'success':job?.status==='failed'?'error':job?.status==='cancelled'?'warning':'info'}>{label}</Badge>}>
    <p className="novel-help">导出使用任务创建时保存的只读项目快照，后续编辑不会改变该任务的导出内容。任务状态会保存，可在桌面端关闭后恢复查询。</p>
    {!novelId&&<EmptyState title="尚未选择项目" detail="打开一个小说项目后即可导出。"/>}
    <div className="export-format-grid" aria-label="可用导出格式">{formats.map(({id,label:formatLabel,detail,available,icon:Icon})=><button type="button" key={id} className="export-format" aria-label={`${formatLabel}${available?'':'（后端待接入）'}`} title={available?detail:`${detail}。此窗口会在后端能力完成后启用。`} disabled={!novelId||!available||busy} onClick={()=>start.mutate(id)}><Icon aria-hidden="true"/><span><strong>{formatLabel}</strong><small>{detail}</small></span>{available?<span className="export-format__state">可用</span>:<Badge>后端待接入</Badge>}</button>)}</div>
    {!!novelId&&<section className="export-history" aria-label="导出任务历史">
      <header className="export-job__actions"><label>任务状态 <select aria-label="导出历史状态" value={statusFilter} onChange={event=>{setStatusFilter(event.target.value);setOffset(0)}}><option value="">全部状态</option>{Object.entries({queued:'排队中',running:'处理中',succeeded:'已完成',failed:'失败',cancelled:'已取消'}).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><Button type="button" variant="ghost" disabled={history.isFetching} onClick={()=>void history.refetch()}>{history.isFetching?'正在读取历史…':'刷新历史'}</Button></header>
      {history.isPending&&<p className="novel-help" role="status">正在读取导出历史…</p>}
      {history.error&&<ExportError error={history.error} fallback="无法读取导出历史，请刷新重试。"/>}
      {!history.isPending&&!history.error&&!history.data?.items?.length&&<EmptyState title="暂无导出记录" detail="此项目与当前分支下的任务会显示在这里，可关闭窗口后重新找到。"/>}
      {!history.error&&<div className="export-history__list">{history.data?.items?.map(item=><Button key={item.id} type="button" variant={item.id===jobId?'secondary':'ghost'} aria-pressed={item.id===jobId} onClick={()=>setJobId(item.id)}>{formats.find(format=>format.id===item.format)?.label||item.format} · {({queued:'排队中',running:'处理中',succeeded:'已完成',failed:'失败',cancelled:'已取消'})[item.status]} · {item.id.slice(0,8)}<small>{item.created_at?new Date(item.created_at).toLocaleString():''} · 快照 {item.snapshot_id?.slice(0,8)||'旧版未记录'}</small></Button>)}</div>}
      <footer className="export-job__actions">{offset>0&&<Button type="button" variant="ghost" disabled={history.isFetching} onClick={()=>setOffset(Math.max(0,offset-50))}>上一页</Button>}{history.data?.next_offset!=null&&<Button type="button" variant="ghost" disabled={history.isFetching} onClick={()=>setOffset(history.data!.next_offset!)}>下一页</Button>}</footer>
    </section>}
    {start.error&&<ExportError error={start.error} fallback="导出任务创建失败，请重试。"/>}
    {(cancel.error||retry.error)&&<ExportError error={cancel.error||retry.error} fallback="导出任务操作失败，请重试。"/>}
    {selected.error&&<div className="export-error" role="alert"><ExportError error={selected.error} fallback="无法读取导出任务状态。"/><Button type="button" variant="ghost" disabled={selected.isFetching} onClick={()=>void selected.refetch()}>{selected.isFetching?'正在刷新…':'刷新任务状态'}</Button></div>}
    {job&&<section className="export-job" aria-live="polite" aria-busy={selected.isFetching||busy}><header><strong>任务 {job.id.slice(0,8)} · 第 {job.attempt||1} 次</strong>{['queued','running'].includes(job.status)&&<LoaderCircle className="export-spin" aria-label="处理中"/>}</header>{['queued','running'].includes(job.status)&&<><div className="export-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress||0} aria-valuetext={`${job.progress||0}% · ${job.progress_message||'处理中'}`}><span style={{width:`${Math.max(0,Math.min(100,job.progress||0))}%`}}/></div><p className="novel-help">{job.progress_message||'处理中'} · {job.progress||0}%</p></>}<p className="novel-help">格式：{job.format} · 快照：{job.snapshot_id||'旧版任务未记录'}{job.recovery_count?` · 已恢复 ${job.recovery_count} 次`:''}</p>{!!job.missing_resources?.length&&<p className="novel-error">缺少 {job.missing_resources.length} 项资源，资源包不会生成不完整文件。</p>}{job.status==='failed'&&<ExportError error={job.error||new Error('导出失败')} fallback="导出失败。"/>}{job.status==='cancelled'&&<p className="novel-help">任务已取消，可重新尝试。</p>}{downloadJob.error&&<ExportError error={downloadJob.error} fallback="下载失败，请重试。"/>}{job.status==='succeeded'&&!job.result?.filename&&<p className="novel-error" role="alert">任务已完成，但下载文件信息缺失，请重新导出。</p>}<footer className="export-job__actions">{['queued','running'].includes(job.status)&&<Button type="button" variant="ghost" disabled={busy} onClick={()=>cancel.mutate(job.id)}>取消任务</Button>}{['failed','cancelled'].includes(job.status)&&<Button type="button" variant="secondary" disabled={busy} onClick={()=>retry.mutate(job.id)}>重新尝试</Button>}{job.status==='succeeded'&&<Button type="button" variant="primary" disabled={downloadJob.isPending||!job.result?.filename} onClick={download}><Download aria-hidden="true"/>{downloadJob.isPending?'准备下载…':`下载 ${job.result?.filename||'导出文件'}`}</Button>}</footer></section>}
  </Panel>
}

function ExportError({error,fallback}:{error:unknown;fallback:string}){
  const view=apiErrorView(error,fallback);
  return <div className="export-error" role="alert"><p className="novel-error">{view.message}</p><p className="export-error__meta">{view.code&&<span>代码：<code>{view.code}</code></span>}{view.requestId&&<span>请求 ID：<code>{view.requestId}</code></span>}{view.details&&<span>详情：<code>{view.details}</code></span>}</p></div>;
}
