import {useEffect,useRef,useState} from 'react';
import {api,apiErrorView,getCollaborationContext,type Asset} from '../api';
import {Button,StatusMessage} from '../ui/primitives';
import {AuthenticatedMedia} from './AuthenticatedMedia';

type Clip={asset_id:string;start_ms:number;end_ms:number|null};
export function VideoAssemblyPanel({novelId,screenplayId}:{novelId?:string;screenplayId?:string}){
 const [assets,setAssets]=useState<Asset[]>([]),[clips,setClips]=useState<Clip[]>([]),[jobs,setJobs]=useState<any[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const context=getCollaborationContext(),key=JSON.stringify([novelId,screenplayId,context.actor?.id,context.scope?.branchId,context.sessionToken]);const scope=useRef<string|null>(key),working=useRef(false);scope.current=key;
 const refresh=async()=>{if(!novelId||!screenplayId)return;try{const [library,result]=await Promise.all([api.assets(novelId,'video'),api.videoAssemblies(novelId,screenplayId)]);if(scope.current===key){setAssets(library);setJobs(result.items||[])}}catch(reason){if(scope.current===key)setError(apiErrorView(reason,'视频拼接数据加载失败').message)}};
 useEffect(()=>{scope.current=key;setAssets([]);setClips([]);setJobs([]);setError('');setBusy(false);working.current=false;void refresh();return()=>{scope.current=null}},[key]);
 const update=(index:number,patch:Partial<Clip>)=>setClips(rows=>rows.map((row,i)=>i===index?{...row,...patch}:row));
 const move=(index:number,offset:number)=>setClips(rows=>{const next=[...rows],target=index+offset;if(target<0||target>=rows.length)return rows;[next[index],next[target]]=[next[target],next[index]];return next});
 const assemble=async()=>{if(!novelId||!screenplayId||working.current||!clips.length)return;working.current=true;setBusy(true);setError('');try{const result=await api.createVideoAssembly(novelId,screenplayId,clips);if(scope.current!==key)return;if(result.status==='FAILED')setError('剪辑输出失败。原视频未改变，可检查裁剪范围后重试。');await refresh()}catch(reason){if(scope.current===key)setError(apiErrorView(reason,'视频拼接失败').message)}finally{if(scope.current===key){working.current=false;setBusy(false)}}};
 if(!novelId||!screenplayId)return null;
 return <section aria-label="本地视频剪辑输出"><details><summary>本地片段排序与裁剪</summary>
  <p className="novel-help">仅使用已校验的项目视频资产。输出为 640×360、24 fps 的无声审核片；原素材保留，音轨不会合入。单次最多 30 段、10 分钟。</p>
  {error&&<StatusMessage tone="error">{error}</StatusMessage>}
  <Button variant="ghost" disabled={busy||!assets.length||clips.length>=30} onClick={()=>setClips(rows=>[...rows,{asset_id:assets[0].id,start_ms:0,end_ms:null}])}>添加片段</Button>
  {!assets.length&&<p className="novel-help">请先下载视频生成结果并入库。</p>}
  {clips.map((clip,index)=><div key={index}><label>片段 {index+1}<select aria-label={`剪辑片段 ${index+1}`} value={clip.asset_id} disabled={busy} onChange={event=>update(index,{asset_id:event.target.value})}>{assets.map(asset=><option key={asset.id} value={asset.id}>{asset.filename}</option>)}</select></label><label>起点（毫秒）<input type="number" min={0} value={clip.start_ms} disabled={busy} onChange={event=>update(index,{start_ms:Number(event.target.value)})}/></label><label>终点（留空使用原时长）<input type="number" min={1} value={clip.end_ms??''} disabled={busy} onChange={event=>update(index,{end_ms:event.target.value?Number(event.target.value):null})}/></label><Button variant="ghost" disabled={busy||index===0} onClick={()=>move(index,-1)}>上移</Button><Button variant="ghost" disabled={busy||index===clips.length-1} onClick={()=>move(index,1)}>下移</Button><Button variant="ghost" disabled={busy} onClick={()=>setClips(rows=>rows.filter((_,i)=>i!==index))}>移除片段</Button></div>)}
  <Button disabled={busy||!clips.length} loading={busy} onClick={()=>void assemble()}>生成无声审核片</Button>
  {jobs.map(job=><article key={job.id}><p>{job.created_at} · {job.status} · {job.duration_ms?`${(job.duration_ms/1000).toFixed(2)} 秒`:''}</p>{(job.status==='FAILED'||job.recoverable)&&<Button variant="ghost" disabled={busy} onClick={()=>setClips((job.clips||[]).map((clip:Clip)=>({asset_id:clip.asset_id,start_ms:clip.start_ms,end_ms:clip.end_ms})))}>载入片段重试</Button>}{job.asset_id&&<><AuthenticatedMedia novelId={novelId} assetId={job.asset_id} kind="video" label="本地剪辑审核片"/><Button variant="ghost" onClick={async()=>{try{const blob=await api.assetDownload(job.asset_id,novelId);if(scope.current!==key)return;const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=`assembly-${job.id}.mp4`;anchor.click();URL.revokeObjectURL(url)}catch(reason){if(scope.current===key)setError(apiErrorView(reason,'下载失败').message)}}}>下载审核片</Button></>}</article>)}
 </details></section>;
}
