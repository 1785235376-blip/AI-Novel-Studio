import {useEffect,useRef,useState} from 'react';
import {api} from '../api';
import {Button,Panel} from '../ui/primitives';
import {FOCUS_FAILED_TASKS_EVENT,publishTaskSummary} from '../ui/taskSummary';
import type {ImageInspection} from './ImageTaskInspector';

type ImageProvider={provider_id:string;default_model:string;configured:boolean;registered:boolean};
type ImageTask={id:string;status:'QUEUED'|'RUNNING'|'SUCCEEDED'|'FAILED';prompt:string;provider_id:string;model_id:string;asset_uri?:string;error?:string};

export function ImageGenerationPanel({novelId,characterId,sceneId,onInspect}:{novelId?:string;characterId?:string;sceneId?:string;onInspect?:(inspection?:ImageInspection)=>void}){
  const [prompt,setPrompt]=useState('生成适合小说设定的角色或场景概念图。');
  const [uri,setUri]=useState(''),[history,setHistory]=useState<any[]>([]),[loading,setLoading]=useState(false),[error,setError]=useState(''),[imported,setImported]=useState(false);
  const [providers,setProviders]=useState<ImageProvider[]>([]),[providerId,setProviderId]=useState(''),[modelId,setModelId]=useState(''),[task,setTask]=useState<ImageTask|null>(null);
  const generateButton=useRef<HTMLButtonElement>(null);
  useEffect(()=>{if(novelId)api.imageGenerations(novelId,characterId,sceneId).then(data=>setHistory(data.items||[])).catch(()=>setHistory([]));},[novelId,characterId,sceneId]);
  useEffect(()=>{let active=true;api.assetProviders().then(data=>{if(!active)return;const items=data.items||[];setProviders(items);const preferred=items.find(item=>item.configured&&item.registered);if(preferred){setProviderId(preferred.provider_id);setModelId(preferred.default_model)}}).catch(()=>{if(active)setProviders([])});return()=>{active=false}},[]);
  useEffect(()=>{publishTaskSummary('image',task?[task]:[])},[task]);
  useEffect(()=>{onInspect?.(task?{id:task.id,status:task.status,providerId:task.provider_id,modelId:task.model_id,assetUri:task.asset_uri,error:task.error,imported}:undefined)},[task,imported,onInspect]);
  useEffect(()=>{const listener=(event:Event)=>{const detail=(event as CustomEvent).detail;if(detail?.source==='image'&&(!detail.taskId||String(detail.taskId)===String(task?.id||'image-task')))requestAnimationFrame(()=>generateButton.current?.focus())};window.addEventListener(FOCUS_FAILED_TASKS_EVENT,listener);return()=>window.removeEventListener(FOCUS_FAILED_TASKS_EVENT,listener)},[task]);
  async function generate(){
    const requestPrompt=prompt.trim(),requestProvider=providerId,requestModel=modelId.trim();if(!requestPrompt||!requestProvider||!requestModel)return;
    setLoading(true);setError('');setUri('');setImported(false);setTask({id:'image-task',status:'QUEUED',prompt:requestPrompt,provider_id:requestProvider,model_id:requestModel});
    try{setTask(current=>current?{...current,status:'RUNNING'}:current);const result=await api.imageGenerate({provider_id:requestProvider,model_id:requestModel,prompt:requestPrompt,novel_id:novelId,character_id:characterId,scene_id:sceneId});setUri(result.asset_uri);setTask(current=>current?{...current,status:'SUCCEEDED',asset_uri:result.asset_uri}:current)}
    catch{const message='图片生成失败，请检查 Provider 配置。';setError(message);setTask(current=>current?{...current,status:'FAILED',error:message}:current)}finally{setLoading(false)}
  }
  const available=providers.some(item=>item.configured&&item.registered);
  return <Panel title="图片生成">
    <label>图片 Provider<select aria-label="图片 Provider" value={providerId} onChange={event=>{const next=providers.find(item=>item.provider_id===event.target.value);setProviderId(event.target.value);setModelId(next?.default_model||'')}}><option value="">选择已配置 Provider</option>{providers.map(item=><option key={item.provider_id} value={item.provider_id} disabled={!item.configured||!item.registered}>{item.provider_id}{item.configured&&item.registered?'':'（不可用）'}</option>)}</select></label>
    <label>模型<input aria-label="图片模型" value={modelId} onChange={event=>setModelId(event.target.value)}/></label>
    <label>生成描述<textarea rows={5} value={prompt} onChange={event=>setPrompt(event.target.value)}/></label>
    <Button ref={generateButton} disabled={loading||!prompt.trim()||!providerId||!modelId.trim()} onClick={generate}>{loading?'生成中…':'生成图片'}</Button>
    {!available&&<p className="novel-help">请先在主控中配置并连接图片 Provider。</p>}
    {task&&<p className="novel-help" aria-live="polite">任务状态：{task.status==='QUEUED'?'已提交，等待执行':task.status==='RUNNING'?'执行中':task.status==='SUCCEEDED'?'已完成':'失败'}{task.error?` · ${task.error}`:''}</p>}
    {error&&<p role="alert">{error}</p>}
    {uri&&<div><img src={uri} alt="生成结果" style={{maxWidth:'100%',maxHeight:360}}/><p className="novel-help">结果地址：{uri}</p>{novelId&&<Button variant="ghost" onClick={async()=>{await api.importGeneratedImage(novelId,{asset_uri:uri,character_id:characterId,scene_id:sceneId});setImported(true)}}>{imported?'已导入资产库':'导入资产库'}</Button>}</div>}
    {history.length>0&&<details><summary>生成历史（{history.length}）</summary>{history.map((item:any,index:number)=><p key={`${item.created_at}-${index}`} className="novel-help">{item.created_at} · {item.prompt} · <Button variant="ghost" onClick={()=>{setUri(item.asset_uri);setPrompt(item.prompt||prompt);setImported(false);setTask({id:String(item.id||`history-${index+1}`),status:'SUCCEEDED',prompt:item.prompt||'',provider_id:item.provider_id||providerId,model_id:item.model_id||modelId,asset_uri:item.asset_uri})}}>预览</Button></p>)}</details>}
  </Panel>;
}
