import {useEffect,useState} from 'react';
import {api} from '../api';
import {Button,Panel} from '../ui/primitives';
import {CloudPromptConsent,useScopedRequestConsent,cloudPromptReviewMessage} from '../useScopedRequestConsent';

export function VisionAnalysisPanel({novelId,characterId,sceneId}:{novelId?:string;characterId?:string;sceneId?:string}){
  const [imageUrl,setImageUrl]=useState(''),[prompt,setPrompt]=useState('分析图片中的人物、场景、服装、情绪和可用于小说创作的视觉细节。'),[result,setResult]=useState(''),[memories,setMemories]=useState<any[]>([]),[loading,setLoading]=useState(false),[error,setError]=useState('');
  const consent=useScopedRequestConsent([novelId,characterId,sceneId,'openai','gpt-4o-mini',prompt,imageUrl]);
  useEffect(()=>{setResult('');setError('');setLoading(false);},[consent.requestKey]);
  useEffect(()=>{let active=true;setMemories([]);if(novelId)api.visualMemories(novelId,characterId,sceneId).then(data=>{if(active)setMemories(data.items||[])}).catch(()=>{if(active)setMemories([])});return()=>{active=false};},[consent.scopeKey,novelId,characterId,sceneId,result]);
  async function analyze(){if(loading)return;const current=consent.begin();setLoading(true);setError('');try{const data=await api.visionAnalyze({provider_id:'openai',model_id:'gpt-4o-mini',prompt,image_url:imageUrl,novel_id:novelId,character_id:characterId,scene_id:sceneId,allow_cloud_prompt:consent.allowed});if(current())setResult(data.text)}catch(reason){if(current())setError(cloudPromptReviewMessage(reason,'图片分析失败，请检查云端发送授权、Provider 凭据和图片地址。'))}finally{if(current())setLoading(false)}}
  return <Panel title="图片理解"><label>图片 URL<input value={imageUrl} onChange={e=>setImageUrl(e.target.value)}/></label><label>分析要求<textarea rows={4} value={prompt} onChange={e=>setPrompt(e.target.value)}/></label><CloudPromptConsent target="OpenAI / gpt-4o-mini" checked={consent.allowed} onChange={consent.setAllowed}/><Button disabled={loading||!imageUrl||!prompt} onClick={analyze}>{loading?'分析中…':'分析图片'}</Button>{error&&<p role="alert">{error}</p>}{result&&<textarea readOnly rows={10} value={result}/>} {memories.length>0&&<details><summary>视觉记忆（{memories.length}）</summary>{memories.map((item:any,index:number)=><p key={`${item.created_at}-${index}`} className="novel-help">{item.created_at} · {item.text}</p>)}</details>}</Panel>;
}
