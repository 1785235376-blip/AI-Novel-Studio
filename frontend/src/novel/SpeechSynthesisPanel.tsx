import {useEffect,useState} from 'react';
import {api} from '../api';
import {CloudPromptConsent,useScopedRequestConsent,cloudPromptReviewMessage} from '../useScopedRequestConsent';
import {Button,Panel,StatusMessage} from '../ui/primitives';
import {FOCUS_FAILED_TASKS_EVENT,publishTaskSummary} from '../ui/taskSummary';
import type {AudioInspection} from './AudioTaskInspector';
import './SpeechSynthesisPanel.css';

type SpeechTask={id:string;status:'QUEUED'|'RUNNING'|'SUCCEEDED'|'FAILED';audio_uri?:string;error?:string};

export function SpeechSynthesisPanel({novelId,characterId,onInspect}:{novelId?:string;characterId?:string;onInspect?:(inspection:AudioInspection)=>void}){
  const [text,setText]=useState('请输入需要朗读的小说片段。'),[providerId,setProviderId]=useState('auto'),[modelId,setModelId]=useState(''),[providers,setProviders]=useState<any[]>([]),[voice,setVoice]=useState('alloy'),[emotion,setEmotion]=useState('neutral'),[uri,setUri]=useState(''),[history,setHistory]=useState<any[]>([]),[loading,setLoading]=useState(false),[error,setError]=useState(''),[imported,setImported]=useState(false),[task,setTask]=useState<SpeechTask>();
  const consent=useScopedRequestConsent([novelId,characterId,providerId,modelId,text,voice,emotion]);
  useEffect(()=>{setUri('');setError('');setLoading(false);setTask(undefined);setImported(false)},[consent.requestKey]);
  useEffect(()=>{let active=true;setHistory([]);if(novelId)api.speechGenerations(novelId,characterId).then(data=>{if(active)setHistory(data.items||[])}).catch(()=>{if(active)setHistory([])});return()=>{active=false}},[consent.scopeKey,novelId,characterId,uri]);
  useEffect(()=>{let active=true;api.audioProviders().then(data=>{if(active)setProviders((data.items||[]).filter(item=>item.capabilities.includes('TTS')&&item.configured))}).catch(()=>{if(active)setProviders([])});return()=>{active=false}},[consent.scopeKey]);
  useEffect(()=>{publishTaskSummary('speech',task?[task]:[]);if(task)onInspect?.({kind:'speech',id:task.id,status:task.status,providerId,modelId,voice,emotion,audioUri:task.audio_uri,error:task.error,imported});},[task,providerId,modelId,voice,emotion,imported,onInspect]);
  useEffect(()=>{const listener=(event:Event)=>{const detail=(event as CustomEvent).detail;if(detail?.source==='speech'){onInspect?.(task?{kind:'speech',id:task.id,status:task.status,providerId,modelId,voice,emotion,audioUri:task.audio_uri,error:task.error,imported}:{kind:'speech',id:String(detail.taskId||'speech-task'),status:'FAILED',pendingRefresh:true});}};window.addEventListener(FOCUS_FAILED_TASKS_EVENT,listener);return()=>window.removeEventListener(FOCUS_FAILED_TASKS_EVENT,listener)},[task,providerId,modelId,voice,emotion,imported,onInspect]);
  async function synthesize(){if(loading)return;const current=consent.begin();const id=`speech-${Date.now()}`;setLoading(true);setError('');setImported(false);setUri('');setTask({id,status:'QUEUED'});try{setTask({id,status:'RUNNING'});const data=await api.speechSynthesize({provider_id:providerId,model_id:modelId,voice,emotion,text,novel_id:novelId,character_id:characterId,allow_cloud_prompt:providerId!=='auto'&&consent.allowed});if(!current())return;setUri(data.audio_uri);setTask({id,status:'SUCCEEDED',audio_uri:data.audio_uri})}catch(reason){if(!current())return;const message=cloudPromptReviewMessage(reason,'语音合成失败，请检查 Provider 地址、凭据和模型。');setError(message);setTask({id,status:'FAILED',error:message})}finally{if(current())setLoading(false)}}
  return <Panel title="声音合成" className="speech-production">
    <label>Provider<select aria-label="语音 Provider" value={providerId} onChange={event=>{const id=event.target.value;setProviderId(id);setModelId(providers.find(item=>item.provider_id===id)?.default_model||'')}}><option value="auto">自动选择（本地优先）</option>{providers.map(item=><option key={item.provider_id} value={item.provider_id}>{item.display_name||item.provider_id}{item.local?' · 本地':''}</option>)}</select></label>
    <label>模型<input value={modelId} onChange={event=>setModelId(event.target.value)} placeholder="gpt-4o-mini-tts"/></label>
    <label>朗读文本<textarea rows={8} value={text} onChange={event=>setText(event.target.value)}/></label>
    <label>音色<select value={voice} onChange={event=>setVoice(event.target.value)}><option value="alloy">Alloy</option><option value="echo">Echo</option><option value="fable">Fable</option><option value="onyx">Onyx</option><option value="nova">Nova</option><option value="shimmer">Shimmer</option></select></label>
    <label>情绪<select value={emotion} onChange={event=>setEmotion(event.target.value)}><option value="neutral">中性</option><option value="happy">愉快</option><option value="sad">悲伤</option><option value="angry">愤怒</option><option value="fearful">紧张</option></select></label>
    <CloudPromptConsent target={`${providerId} / ${modelId || '默认模型'}`} automatic={providerId==='auto'} checked={consent.allowed} onChange={consent.setAllowed}/>
    <Button loading={loading} disabled={loading||!text.trim()||!providerId.trim()||(providerId!=='auto'&&!modelId.trim())} onClick={synthesize}>{task?.status==='FAILED'?'重新生成':'生成语音'}</Button>
    {error&&<StatusMessage tone="error">{error}</StatusMessage>}
    {uri&&<><audio controls src={uri} aria-label="当前语音生成结果" style={{width:'100%'}}/><p className="novel-help">{providerId} · {modelId} · {voice} · {emotion}</p>{novelId&&<Button variant="ghost" disabled={imported} onClick={async()=>{const current=consent.begin();try{await api.importGeneratedSpeech(novelId,{audio_uri:uri,character_id:characterId});if(current())setImported(true)}catch{if(current())setError('语音校验或入库失败。')}}}>{imported?'已导入资产库':'导入资产库'}</Button>}</>}
    {history.length>0&&<details><summary>语音历史（{history.length}）</summary>{history.map((item:any,index:number)=><p key={`${item.created_at}-${index}`} className="novel-help">{item.created_at} · {item.provider_id}/{item.model_id} · {item.voice} · {item.emotion||'neutral'}</p>)}</details>}
  </Panel>;
}
