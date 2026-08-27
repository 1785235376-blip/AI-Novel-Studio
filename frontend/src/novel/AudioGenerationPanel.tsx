import {useEffect,useMemo,useState} from 'react';
import {api,apiErrorView} from '../api';
import {Badge,Button,Panel,StatusMessage} from '../ui/primitives';

type Capability='TEXT_TO_AUDIO'|'AUDIO_EDIT'|'VIDEO_TO_AUDIO'|'SFX'|'FOLEY'|'MUSIC';
type Provider={provider_id:string;display_name:string;endpoint:string;default_model:string;local:boolean;requires_credential:boolean;capabilities:string[]};
const options:[Capability,string][]=[['SFX','音效'],['FOLEY','拟音 / Foley'],['MUSIC','音乐'],['TEXT_TO_AUDIO','文本生成音频'],['AUDIO_EDIT','音频编辑'],['VIDEO_TO_AUDIO','视频同步音频']];

export function AudioGenerationPanel({novelId}:{novelId:string}){
  const [capability,setCapability]=useState<Capability>('SFX');
  const [providers,setProviders]=useState<Provider[]>([]),[providerId,setProviderId]=useState('auto'),[modelId,setModelId]=useState('');
  const [prompt,setPrompt]=useState('为当前场景制作有空间层次、不过度抢对白的环境音。'),[sourceUri,setSourceUri]=useState(''),[duration,setDuration]=useState(8);
  const [loading,setLoading]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<{provider_id:string;model_id:string;audio_uri:string;status:string;remote_task_id?:string}>();
  useEffect(()=>{api.audioProviders().then(data=>setProviders(data.items||[])).catch(()=>setError('音频 Provider 目录读取失败，请检查本地服务。'))},[]);
  const supported=useMemo(()=>providers.filter(item=>item.capabilities.includes(capability)),[providers,capability]);
  useEffect(()=>{if(providerId!=='auto'&&!supported.some(item=>item.provider_id===providerId)){setProviderId('auto');setModelId('')}},[capability,providerId,supported]);
  const needsAudio=capability==='AUDIO_EDIT',needsVideo=capability==='VIDEO_TO_AUDIO';
  const sourceValid=!needsAudio&&!needsVideo||/^https?:\/\//i.test(sourceUri)||/^data:(audio|video)\//i.test(sourceUri);
  async function generate(){setLoading(true);setError('');setResult(undefined);try{const data=await api.audioGenerate({provider_id:providerId,model_id:modelId.trim()||undefined,capability,prompt:prompt.trim(),source_audio_uri:needsAudio?sourceUri.trim()||undefined:undefined,source_video_uri:needsVideo?sourceUri.trim()||undefined:undefined,duration_seconds:duration,novel_id:novelId});setResult(data)}catch(reason){setError(apiErrorView(reason,'音频任务提交失败，请检查对应 Provider 是否已部署或配置。').message)}finally{setLoading(false)}}
  return <Panel title="音频制作" actions={<Badge tone="info">本地优先</Badge>}>
    <label>制作类型<select aria-label="音频制作类型" value={capability} onChange={event=>setCapability(event.target.value as Capability)}>{options.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    <label>Provider<select aria-label="音频制作 Provider" value={providerId} onChange={event=>{const id=event.target.value;setProviderId(id);setModelId(supported.find(item=>item.provider_id===id)?.default_model||'')}}><option value="auto">自动选择（本地优先）</option>{supported.map(item=><option key={item.provider_id} value={item.provider_id}>{item.display_name}{item.local?' · 本地':''}</option>)}</select></label>
    <label>模型（留空使用 Provider 默认）<input value={modelId} onChange={event=>setModelId(event.target.value)} placeholder={providerId==='auto'?'自动选择':'模型 ID'}/></label>
    <label>制作描述<textarea rows={5} value={prompt} onChange={event=>setPrompt(event.target.value)}/></label>
    {(needsAudio||needsVideo)&&<label>{needsAudio?'源音频地址':'源视频地址'}<input aria-label={needsAudio?'源音频地址':'源视频地址'} value={sourceUri} onChange={event=>setSourceUri(event.target.value)} placeholder="https://... 或 data:..."/></label>}
    <label>目标时长（秒）<input aria-label="音频目标时长" type="number" min="1" max="600" value={duration} onChange={event=>setDuration(Math.max(1,Math.min(600,Number(event.target.value)||1)))}/></label>
    {!sourceValid&&<StatusMessage tone="error">来源必须使用 http(s)、data:audio 或 data:video 地址。</StatusMessage>}
    <Button loading={loading} disabled={loading||!prompt.trim()||!sourceValid} onClick={generate}>{result?.status==='FAILED'?'重新提交':'生成音频'}</Button>
    {!supported.length&&<p className="novel-help">当前目录没有支持此制作类型的 Provider。请在本机部署对应模型，或配置支持该能力的云端服务。</p>}
    {error&&<StatusMessage tone="error">{error}</StatusMessage>}
    {result&&<section aria-live="polite"><p className="novel-help">{result.provider_id} · {result.model_id} · {result.status}</p>{result.audio_uri?<audio controls src={result.audio_uri} aria-label="音频制作结果" style={{width:'100%'}}/>:<p className="novel-help">任务已提交{result.remote_task_id?` · ${result.remote_task_id}`:''}，等待 Provider 返回音频。</p>}</section>}
  </Panel>;
}
