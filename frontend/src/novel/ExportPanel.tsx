import {useState} from 'react';
import {Download,FileArchive,FileText,LoaderCircle,PackageCheck} from 'lucide-react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {api,apiErrorView,ExportJob} from '../api';
import {Badge,Button,EmptyState,Panel} from '../ui/primitives';
import './export.css';

const formats=[
  {id:'txt',label:'TXT 小说',detail:'纯文本，适合备份与快速分享',available:true,icon:FileText},
  {id:'markdown',label:'Markdown',detail:'保留章节结构与标题层级',available:true,icon:FileText},
  {id:'json',label:'项目 JSON',detail:'完整项目数据交换格式',available:true,icon:PackageCheck},
  {id:'docx',label:'Word 文档',detail:'基础 OOXML 文稿；模板与目录增强待接入',available:true,icon:FileText},
  {id:'pdf',label:'PDF 文档',detail:'预留：分页、字体嵌入与打印版式',available:false,icon:FileText},
  {id:'epub',label:'EPUB 电子书',detail:'基础 EPUB 3 导航与章节；封面资源待接入',available:true,icon:FileArchive},
  {id:'screenplay',label:'影视剧本预览',detail:'确定性 Markdown 预览；标准排版仍待接入',available:true,icon:FileText},
  {id:'shot-list',label:'镜头表 CSV',detail:'确定性镜头字段导出；对白扩展待接入',available:true,icon:FileArchive},
  {id:'storyboard',label:'分镜预览',detail:'确定性 Markdown 预览；图片资源待接入',available:true,icon:FileArchive},
] as const;

export function ExportPanel({novelId}:{novelId?:string}){
  const [jobId,setJobId]=useState('');
  const client=useQueryClient();
  const selected=useQuery({queryKey:['export-job',jobId],queryFn:()=>api.exportJob(jobId),enabled:!!jobId,refetchInterval:(q)=>['queued','running'].includes(q.state.data?.status||'')?700:false});
  const start=useMutation({mutationFn:(format:string)=>api.createExport(novelId!,format),onSuccess:(job)=>setJobId(job.id)});
  const cancel=useMutation({mutationFn:(id:string)=>api.cancelExport(id),onSuccess:(next)=>client.setQueryData(['export-job',next.id],next)});
  const retry=useMutation({mutationFn:(id:string)=>api.retryExport(id),onSuccess:(job)=>setJobId(job.id)});
  const downloadJob=useMutation({mutationFn:(target:{id:string;filename:string})=>api.exportDownload(target.id).then(blob=>({blob,filename:target.filename}))});
  const job=selected.data as ExportJob|undefined;
  function download(){if(!job?.result?.filename)return;downloadJob.mutate({id:job.id,filename:job.result.filename},{onSuccess:({blob,filename})=>{const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),0)}})}
  const label=job?({queued:'排队中',running:'处理中',succeeded:'已完成',failed:'失败',cancelled:'已取消'} as Record<string,string>)[job.status]||'未知状态':'选择格式';
  const busy= start.isPending||cancel.isPending||retry.isPending;
  return <Panel title="导出中心" actions={<Badge tone={job?.status==='succeeded'?'success':job?.status==='failed'?'error':job?.status==='cancelled'?'warning':'info'}>{label}</Badge>}>
    <p className="novel-help">导出读取任务执行时的项目内容。任务状态会保存，可在桌面端关闭后恢复查询。</p>
    {!novelId&&<EmptyState title="尚未选择项目" detail="打开一个小说项目后即可导出。"/>}
    <div className="export-format-grid" aria-label="可用导出格式">{formats.map(({id,label:formatLabel,detail,available,icon:Icon})=><button type="button" key={id} className="export-format" aria-label={`${formatLabel}${available?'':'（后端待接入）'}`} title={available?detail:`${detail}。此窗口会在后端能力完成后启用。`} disabled={!novelId||!available||busy} onClick={()=>start.mutate(id)}><Icon aria-hidden="true"/><span><strong>{formatLabel}</strong><small>{detail}</small></span>{available?<span className="export-format__state">可用</span>:<Badge>后端待接入</Badge>}</button>)}</div>
    {start.error&&<ExportError error={start.error} fallback="导出任务创建失败，请重试。"/>}
    {(cancel.error||retry.error)&&<ExportError error={cancel.error||retry.error} fallback="导出任务操作失败，请重试。"/>}
    {selected.error&&<div className="export-error" role="alert"><ExportError error={selected.error} fallback="无法读取导出任务状态。"/><Button type="button" variant="ghost" disabled={selected.isFetching} onClick={()=>void selected.refetch()}>{selected.isFetching?'正在刷新…':'刷新任务状态'}</Button></div>}
    {job&&<section className="export-job" aria-live="polite" aria-busy={selected.isFetching||busy}><header><strong>任务 {job.id.slice(0,8)} · 第 {job.attempt||1} 次</strong>{['queued','running'].includes(job.status)&&<LoaderCircle className="export-spin" aria-label="处理中"/>}</header>{['queued','running'].includes(job.status)&&<><div className="export-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress||0} aria-valuetext={`${job.progress||0}% · ${job.progress_message||'处理中'}`}><span style={{width:`${Math.max(0,Math.min(100,job.progress||0))}%`}}/></div><p className="novel-help">{job.progress_message||'处理中'} · {job.progress||0}%</p></>}{job.status==='failed'&&<ExportError error={job.error||new Error('导出失败')} fallback="导出失败。"/>}{job.status==='cancelled'&&<p className="novel-help">任务已取消，可重新尝试。</p>}{downloadJob.error&&<ExportError error={downloadJob.error} fallback="下载失败，请重试。"/>}{job.status==='succeeded'&&!job.result?.filename&&<p className="novel-error" role="alert">任务已完成，但下载文件信息缺失，请重新导出。</p>}<footer className="export-job__actions">{['queued','running'].includes(job.status)&&<Button type="button" variant="ghost" disabled={busy} onClick={()=>cancel.mutate(job.id)}>取消任务</Button>}{['failed','cancelled'].includes(job.status)&&<Button type="button" variant="secondary" disabled={busy} onClick={()=>retry.mutate(job.id)}>重新尝试</Button>}{job.status==='succeeded'&&<Button type="button" variant="primary" disabled={downloadJob.isPending||!job.result?.filename} onClick={download}><Download aria-hidden="true"/>{downloadJob.isPending?'准备下载…':`下载 ${job.result?.filename||'导出文件'}`}</Button>}</footer></section>}
  </Panel>
}

function ExportError({error,fallback}:{error:unknown;fallback:string}){
  const view=apiErrorView(error,fallback);
  return <div className="export-error" role="alert"><p className="novel-error">{view.message}</p><p className="export-error__meta">{view.code&&<span>代码：<code>{view.code}</code></span>}{view.requestId&&<span>请求 ID：<code>{view.requestId}</code></span>}{view.details&&<span>详情：<code>{view.details}</code></span>}</p></div>;
}
