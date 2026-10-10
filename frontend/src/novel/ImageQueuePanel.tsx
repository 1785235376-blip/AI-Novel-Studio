import {useEffect,useRef,useState} from 'react';
import {api,apiErrorView,getCollaborationContext} from '../api';
import {Badge,Button,Panel,StatusMessage} from '../ui/primitives';
import {safeImagePreviewUri} from './ImageInfiniteCanvas';

type Draft={provider_id:string;model_id:string;prompt:string;novel_id?:string;character_id?:string;scene_id?:string;images?:string[]};
export function ImageQueuePanel({novelId,draft,local,requestedTaskId}:{novelId?:string;draft:Draft;local?:boolean;requestedTaskId?:string}){
 const targetFocused=useRef('');
 const [jobs,setJobs]=useState<any[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(''),[selected,setSelected]=useState<string[]>([]),[loaded,setLoaded]=useState(false);
 const [width,setWidth]=useState(1024),[height,setHeight]=useState(1024),[steps,setSteps]=useState(28),[seed,setSeed]=useState(1),[size,setSize]=useState('1024x1024'),[quality,setQuality]=useState('auto');
 const context=getCollaborationContext(),scopeKey=JSON.stringify([novelId,context.actor?.id,context.scope?.workspaceId,context.scope?.branchId,context.sessionToken]);
 const scope=useRef<string|null>(scopeKey);scope.current=scopeKey;const pending=useRef(new Set<string>());
 const refresh=async()=>{if(!novelId)return;const current=scopeKey;try{const result=await api.imageJobs(novelId);if(scope.current===current){setJobs(result.items||[]);setLoaded(true)}}catch(reason){if(scope.current===current)setError(apiErrorView(reason,'图片任务加载失败').message)}};
 useEffect(()=>{scope.current=scopeKey;setJobs([]);setSelected([]);setError('');setBusy('');pending.current.clear();void refresh();return()=>{scope.current=null}},[scopeKey]);
 const run=async(key:string,action:()=>Promise<unknown>)=>{if(pending.current.has(key))return;pending.current.add(key);setBusy(key);setError('');const current=scopeKey;try{await action();if(scope.current===current)await refresh()}catch(reason){if(scope.current===current)setError(apiErrorView(reason,'图片任务操作失败').message)}finally{pending.current.delete(key);if(scope.current===current)setBusy('')}};
 const toggle=(id:string)=>setSelected(current=>current.includes(id)?current.filter(item=>item!==id):[...current.slice(-1),id]);
 return <Panel title="持久生成队列" actions={<Button variant="ghost" onClick={()=>void refresh()}>刷新任务</Button>}>
   <p className="novel-help">任务和参数会保留。生成结果经检查后，明确接受才会进入资产库；取消后晚到结果不会入库，但不保证远端立即停止计算。</p>
   {error&&<StatusMessage tone="error">{error}</StatusMessage>}
   <details><summary>生成参数</summary>{local?<><label>宽度<input aria-label="队列图片宽度" type="number" min={64} max={2048} step={8} value={width} onChange={e=>setWidth(Number(e.target.value))}/></label><label>高度<input type="number" min={64} max={2048} step={8} value={height} onChange={e=>setHeight(Number(e.target.value))}/></label><label>采样步数<input type="number" min={1} max={150} value={steps} onChange={e=>setSteps(Number(e.target.value))}/></label><label>随机种子<input type="number" min={0} max={2147483647} value={seed} onChange={e=>setSeed(Number(e.target.value))}/></label></>:<><label>图片尺寸<select value={size} onChange={e=>setSize(e.target.value)}><option>1024x1024</option><option>1536x1024</option><option>1024x1536</option></select></label><label>质量<select value={quality} onChange={e=>setQuality(e.target.value)}><option value="auto">自动</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label></>}</details>
   <Button disabled={!novelId||!draft.provider_id||!draft.model_id||!draft.prompt.trim()||!!busy} loading={busy==='create'} onClick={()=>novelId&&void run('create',()=>api.createImageJob(novelId,{...draft,parameters:local?{width,height,steps,seed}:{size,quality},...(draft.images?.length?{size,quality,output_format:'png'}:{})}))}>保存到生成队列</Button>
   {!jobs.length&&<p className="novel-help">暂无持久任务。</p>}
   {requestedTaskId && loaded && !error && !jobs.some(job=>job.id===requestedTaskId) && <StatusMessage tone="warning">请求的原图片任务当前不可读或已移除。</StatusMessage>}
   {jobs.map(job=><article className="novel-record" key={job.id} aria-current={requestedTaskId===job.id?'true':undefined} tabIndex={requestedTaskId===job.id?0:undefined} ref={element=>{if(element&&requestedTaskId===job.id&&targetFocused.current!==requestedTaskId){targetFocused.current=String(requestedTaskId);element.focus();element.scrollIntoView?.({block:'nearest'})}}}><p>任务 ID：{job.id}</p><p>{job.prompt} <Badge>{job.status}</Badge> · {job.approval_status==='APPROVED'?'已接受':'待审核'}</p><small>{job.provider_id}/{job.model_id} · 尝试 {job.attempt} 次</small>{job.error&&<p role="alert">{job.error}</p>}<div>
    {job.status==='QUEUED'&&<Button disabled={!!busy} loading={busy===job.id} onClick={()=>novelId&&void run(job.id,()=>api.executeImageJob(novelId,job.id))}>执行任务</Button>}
    {['QUEUED','RUNNING'].includes(job.status)&&<Button variant="ghost" onClick={()=>novelId&&void run('cancel-'+job.id,()=>api.cancelImageJob(novelId,job.id))}>取消任务</Button>}
    {(['FAILED','CANCELLED'].includes(job.status)||job.recoverable)&&<Button variant="ghost" disabled={!!busy} onClick={()=>novelId&&void run(job.id,()=>api.retryImageJob(novelId,job.id))}>重新排队</Button>}
    {job.status==='SUCCEEDED'&&<><Button variant="ghost" aria-pressed={selected.includes(job.id)} onClick={()=>toggle(job.id)}>对比结果</Button><Button disabled={!!busy||job.approval_status==='APPROVED'} onClick={()=>novelId&&void run(job.id,()=>api.acceptImageJob(novelId,job.id))}>{job.approval_status==='APPROVED'?'已接受入库':'接受并入库'}</Button></>}
   </div></article>)}
   {selected.length>0&&<section aria-label="图片结果对比">{selected.map(id=>{const job=jobs.find(row=>row.id===id),uri=safeImagePreviewUri(job?.asset_uri||'');return uri?<figure key={id}><img src={uri} alt={`对比结果 ${id}`} referrerPolicy="no-referrer" style={{maxWidth:'100%',maxHeight:240}}/><figcaption>{job.provider_id}/{job.model_id}</figcaption></figure>:<p key={id}>结果地址不可预览。</p>})}</section>}
 </Panel>;
}
