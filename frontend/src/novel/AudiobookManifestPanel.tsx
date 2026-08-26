import {useEffect,useState} from 'react';
import {api} from '../api';
import {Button,Panel} from '../ui/primitives';
import {FOCUS_FAILED_TASKS_EVENT,publishTaskSummary} from '../ui/taskSummary';
import type {AudioInspection} from './AudioTaskInspector';

export function AudiobookManifestPanel({novelId,onInspect}:{novelId?:string;onInspect?:(inspection:AudioInspection)=>void}){
  const [data,setData]=useState<any>(),[jobs,setJobs]=useState<any[]>([]),[mix,setMix]=useState<any>(),[loading,setLoading]=useState(false);
  const refresh=async()=>{if(!novelId)return;setLoading(true);try{const [manifest,queue,plan]=await Promise.all([api.audiobookManifest(novelId),api.audiobookJobs(novelId),api.audiobookMixPlan(novelId)]);setData(manifest);setJobs(queue.items||[]);setMix(plan)}finally{setLoading(false)}};
  useEffect(()=>{refresh()},[novelId]);
  useEffect(()=>{publishTaskSummary('audiobook',jobs);},[jobs]);
  useEffect(()=>{const listener=(event:Event)=>{const detail=(event as CustomEvent).detail;if(detail?.source!=='audiobook')return;const job=jobs.find(item=>String(item.id)===String(detail.taskId));onInspect?.(job?{kind:'audiobook',id:String(job.id),status:job.status,chapterId:job.chapter_id,providerId:job.provider_id,modelId:job.model_id,voice:job.voice,audioUri:job.audio_uri||job.result?.audio_uri,error:job.error}:{kind:'audiobook',id:String(detail.taskId||'audiobook-job'),status:'FAILED',pendingRefresh:true});};window.addEventListener(FOCUS_FAILED_TASKS_EVENT,listener);return()=>window.removeEventListener(FOCUS_FAILED_TASKS_EVENT,listener)},[jobs,onInspect]);
  return <Panel title="有声小说编排">
    <Button variant="ghost" onClick={refresh}>{loading?'加载中…':'刷新编排'}</Button>
    {jobs.length>0&&<p className="novel-help">合成队列：{jobs.length} 项 · 待执行 {jobs.filter(job=>job.status==='QUEUED').length} 项 · 失败 {jobs.filter(job=>job.status==='FAILED').length} 项 {jobs.map(job=><Button key={`inspect-${job.id}`} variant="ghost" onClick={()=>onInspect?.({kind:'audiobook',id:String(job.id),status:job.status,chapterId:job.chapter_id,providerId:job.provider_id,modelId:job.model_id,voice:job.voice,audioUri:job.audio_uri||job.result?.audio_uri,error:job.error})}>检查 {job.chapter_id}</Button>)} {jobs.filter(job=>job.status==='QUEUED').map(job=><Button key={job.id} variant="ghost" onClick={()=>novelId&&api.executeAudiobookJob(novelId,job.id).then(refresh)}>执行 {job.chapter_id}</Button>)} {jobs.filter(job=>job.status==='FAILED').map(job=><Button key={`retry-${job.id}`} variant="ghost" onClick={()=>novelId&&api.retryAudiobookJob(novelId,job.id).then(refresh)}>重试 {job.chapter_id}</Button>)}</p>}
    {mix&&<details><summary>混音计划：{mix.tracks?.length||0} 条轨道 · {mix.mix_status}</summary>{(mix.tracks||[]).map((track:any)=><p key={track.track_id} className="novel-help">轨道 {track.track_id} · {track.clips?.length||0} 个片段 {track.clips?.map((clip:any,index:number)=><span key={`${clip.created_at}-${index}`}> · {clip.voice}/{clip.emotion}</span>)}</p>)}</details>}
    {data&&<><p className="novel-help">已准备 {data.ready_chapters}/{data.total_chapters} 个章节</p>{data.chapters.map((chapter:any)=><article key={chapter.chapter_id}><strong>{chapter.title||chapter.chapter_id}</strong><p>文本 {chapter.text_length} 字 · 音频 {chapter.audio_count} 条</p>{chapter.audio.map((audio:any,index:number)=><audio key={`${audio.created_at}-${index}`} controls src={audio.audio_uri} style={{width:'100%'}}/>)}{chapter.audio_count===0&&<Button variant="ghost" onClick={()=>novelId&&api.queueAudiobookChapter(novelId,chapter.chapter_id).then(refresh)}>加入合成队列</Button>}</article>)}</>}
  </Panel>;
}
