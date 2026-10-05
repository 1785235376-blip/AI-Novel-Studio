import {useEffect,useRef,useState} from 'react';
import {api,apiErrorView,type Chapter,type CollaborationContext,type SourcePrivacy} from '../api';
import {Button,StatusMessage} from '../ui/primitives';
export function SourcePrivacyControl({chapter,context}:{chapter:Chapter;context:CollaborationContext}){
 const [status,setStatus]=useState<SourcePrivacy>(),[choice,setChoice]=useState('LOCAL_ONLY'),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const active=useRef(true),flight=useRef(false),ticket=useRef(0);
 useEffect(()=>{active.current=true;return()=>{active.current=false;ticket.current++}},[]);
 async function load(){const request=++ticket.current;try{const value=await api.sourcePrivacy(chapter.novel_id,chapter.id,context);if(active.current&&request===ticket.current){setStatus(value);setChoice(value.privacy_level)}}catch(e){if(active.current&&request===ticket.current)setError(apiErrorView(e).message)}}
 useEffect(()=>{void load()},[chapter.id,chapter.version]);
 async function save(){if(!status||flight.current)return;flight.current=true;setBusy(true);setError('');try{const value=await api.reviewSourcePrivacy(chapter.novel_id,chapter.id,{privacy_level:choice,expected_version:status.chapter_version,content_sha256:status.content_sha256},context);if(active.current)setStatus(value)}catch(e){if(active.current)setError(apiErrorView(e).message)}finally{flight.current=false;if(active.current)setBusy(false)}}
 return <section className="panel" aria-label="正文外发策略"><details><summary>正文隐私：{status?.privacy_level==='CLOUD_ALLOWED'?'当前版本允许云端':'仅本地或尚未确认'}</summary><p className="novel-help">授权只绑定当前章节版本和分支。修改正文后需重新确认。改为仅本地会阻止尚未发送的请求；已经发送的内容无法撤回。</p>{status?.stale&&<p role="status">正文已改变，旧授权已失效。</p>}{error&&<StatusMessage tone="error">{error}</StatusMessage>}<label>当前章节正文与选区<select value={choice} disabled={busy||!status} onChange={e=>setChoice(e.target.value)}><option value="LOCAL_ONLY">仅本地</option><option value="CLOUD_ALLOWED">允许我选定的云模型接收此版本</option></select></label><Button disabled={busy||!status} onClick={()=>void save()}>{busy?'正在保存…':'保存正文隐私策略'}</Button><Button disabled={busy} onClick={()=>void load()}>重新读取当前版本</Button></details></section>
}
