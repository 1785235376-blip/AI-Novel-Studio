import {useEffect,useRef,useState} from 'react';
import {Activity,FileText,Play,RefreshCw,Settings2,ShieldAlert,Square,X} from 'lucide-react';
import {ApiError,api,getCollaborationContext,type ModelCenterModel,type ModelCenterPipeline,type ModelCenterRuntime,type ModelCenterEditableRuntimeConfiguration,type ModelCenterWhisperRuntimeConfiguration,type RuntimeCapabilitySnapshot,type RuntimeDiagnostics} from '../api';
import {Badge,Button,EmptyState,Panel,StatusMessage} from './primitives';
import './ModelCenter.css';
import {LocalAiDiscovery, type LocalAiOnboardingOwner} from './LocalAiDiscovery';
import {useLocalAiDiscoveryOwner,useLocalAiOwnerKey} from '../localAiDiscoveryOwner';
import {useLocalHostSession} from '../localHostSession';
import {fixedWhisperConfiguration,runtimePresentation} from './modelCenterRuntimePresentation';
import {VideoModelObservationSummary} from '../AIEnvironmentSummary';
import type {VideoObservationReport} from '../localAiDiscoveryApi';

const authCodes=['SESSION_REQUIRED','INVALID_SESSION'];

function mutationPayload(configuration:ModelCenterEditableRuntimeConfiguration):Record<string,unknown>{
 if(configuration.runtime_type==='COMFYUI'){
  return {
   runtime_type:'COMFYUI',
   management:'EXTERNAL',
   executable:configuration.executable||'',
   installation_path:configuration.installation_path||'',
   base_url:configuration.base_url,
   bind_address:configuration.bind_address,
   port:configuration.port,
   health_endpoint:configuration.health_endpoint,
  };
 }
 if(configuration.runtime_type!=='LLAMA_CPP')throw new Error('MODEL_CENTER_CONFIGURATION_READ_ONLY');
 return {
  runtime_type:'LLAMA_CPP',
  management:configuration.management,
  executable:configuration.executable,
  working_directory:configuration.working_directory,
  base_url:configuration.base_url,
  bind_address:configuration.bind_address,
  port:configuration.port,
  health_endpoint:configuration.health_endpoint,
  model_path:configuration.model_path||'',
  context_size:configuration.context_size,
  gpu_layers:configuration.gpu_layers,
  threads:configuration.threads,
  batch_size:configuration.batch_size,
  extra_arguments:configuration.extra_arguments??[],
 };
}

function logArrays(payload:{stdout?:string[]|null;stderr?:string[]|null}|null|undefined){
 return {stdout:Array.isArray(payload?.stdout)?payload.stdout:[],stderr:Array.isArray(payload?.stderr)?payload.stderr:[]};
}

function operationError(caught:unknown,fallback:string){
 return caught instanceof ApiError&&/^[A-Z][A-Z0-9_:-]{0,159}$/.test(caught.problem.code)?caught.problem.code:fallback;
}

export function ModelCenter({onboarding}: {onboarding?: LocalAiOnboardingOwner} = {}){
 const identity=useLocalAiOwnerKey(onboarding);
 return <ModelCenterContent key={identity} onboarding={onboarding}/>;
}
function ModelCenterContent({onboarding}: {onboarding?: LocalAiOnboardingOwner}){
 const owner=useLocalAiDiscoveryOwner(onboarding);
 const [requestContext]=useState(()=>{const value=onboarding?.context??getCollaborationContext();return {...value,
  actor:value.actor&&{...value.actor},scope:value.scope&&{...value.scope},localHostToken:value.localHostToken??useLocalHostSession.getState().token};});
 const [discoveryRevision,setDiscoveryRevision]=useState(0);
 const [videoObservations,setVideoObservations]=useState<VideoObservationReport>();
 const [models,setModels]=useState<ModelCenterModel[]>([]),[runtimes,setRuntimes]=useState<ModelCenterRuntime[]>([]),[pipelines,setPipelines]=useState<ModelCenterPipeline[]>([]),[canMutate,setCanMutate]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[busy,setBusy]=useState('');
 const [selected,setSelected]=useState(''),[configuration,setConfiguration]=useState<ModelCenterEditableRuntimeConfiguration>(),[fixedConfiguration,setFixedConfiguration]=useState<ModelCenterWhisperRuntimeConfiguration>(),[diagnostics,setDiagnostics]=useState<RuntimeDiagnostics>(),[snapshot,setSnapshot]=useState<RuntimeCapabilitySnapshot>(),[logs,setLogs]=useState<{stdout:string[];stderr:string[]}>(),[editing,setEditing]=useState(false);
 const mounted=useRef(true),requestGeneration=useRef(0),videoObservationGeneration=useRef(0),operation=useRef(false),pollWindow=useRef<{ids:string;deadline:number}|null>(null);
 const current=()=>mounted.current&&owner.current();
 const retireVideoObservations=()=>{videoObservationGeneration.current++;setVideoObservations(undefined)};
 const clearPrivateDetails=()=>{setEditing(false);setConfiguration(undefined);setFixedConfiguration(undefined);setDiagnostics(undefined);setSnapshot(undefined);setLogs(undefined);retireVideoObservations()};
 const expire=()=>{setCanMutate(false);clearPrivateDetails();setError('受信任的桌面会话已失效，运行时控制已禁用。')};
 const refresh=async(background=false)=>{if(!current())return;const generation=++requestGeneration.current;if(!background){setError('');setLoading(true)}try{const [m,r,p,h]=await Promise.all([api.modelCenterModels(requestContext),api.modelCenterRuntimes(requestContext),api.modelCenterPipelines(requestContext),api.modelCenterHealth(requestContext)]);if(current()&&generation===requestGeneration.current){setModels(m.items);setRuntimes(r.items);setPipelines(p.items);setCanMutate(h.mutation_authorization.can_mutate===true);if(!h.mutation_authorization.can_mutate)clearPrivateDetails();setSelected(value=>r.items.some(item=>item.id===value)?value:r.items[0]?.id??'')}}catch(caught){if(current()&&generation===requestGeneration.current){if(caught instanceof ApiError&&authCodes.includes(caught.problem.code))expire();else setError('模型中心状态读取失败，请检查本地服务。')}}finally{if(current()&&generation===requestGeneration.current&&!background)setLoading(false)}};
 useEffect(()=>{mounted.current=true;void refresh();return()=>{mounted.current=false;requestGeneration.current++}},[]);
 useEffect(()=>{retireVideoObservations()},[discoveryRevision]);
 const action=async(id:string,kind:'validate'|'start'|'stop')=>{if(!canMutate||!current()||operation.current)return;const runtime=runtimes.find(item=>item.id===id);if(!runtime)return;const view=runtimePresentation(runtime);if(kind==='start'&&!view.canStart||kind==='stop'&&!view.canStop)return;operation.current=true;setBusy(`${id}:${kind}`);setError('');try{if(kind==='validate')await api.modelCenterValidateRuntime(id,requestContext);else if(kind==='start')await api.modelCenterStartRuntime(id,requestContext);else await api.modelCenterStopRuntime(id,requestContext);if(current())await refresh()}catch(caught){if(current()){if(caught instanceof ApiError&&authCodes.includes(caught.problem.code))expire();else setError(operationError(caught,'运行时操作结果未确认，请刷新状态后再操作。'))}}finally{operation.current=false;if(current())setBusy('')}};
 const openEdit=async(id:string)=>{if(!canMutate||!current()||operation.current)return;const runtime=runtimes.find(item=>item.id===id);if(!runtime)return;const view=runtimePresentation(runtime);if(!view.whisper&&!view.canConfigure)return;operation.current=true;setBusy(`${id}:edit`);setError('');try{const value=await api.modelCenterRuntimeConfiguration(id,requestContext);if(!current())return;if(view.whisper){setFixedConfiguration(fixedWhisperConfiguration(value,id));setEditing(false);setConfiguration(undefined)}else if(value.runtime_type===runtime.runtime_type&&(value.runtime_type==='LLAMA_CPP'||value.runtime_type==='COMFYUI')){setConfiguration(value);setFixedConfiguration(undefined);setEditing(true)}else setError('运行时配置身份已变化，请刷新。');setSelected(id)}catch(caught){if(current()){if(caught instanceof ApiError&&authCodes.includes(caught.problem.code))expire();else setError(operationError(caught,'运行时配置读取失败。'))}}finally{operation.current=false;if(current())setBusy('')}};
 const save=async(event:React.FormEvent)=>{event.preventDefault();if(!configuration||!canMutate||!current()||operation.current)return;operation.current=true;setBusy(`${configuration.id}:save`);try{await api.modelCenterUpdateRuntimeConfiguration(configuration.id,mutationPayload(configuration),requestContext);if(!current())return;if(onboarding)setDiscoveryRevision(value=>value+1);setEditing(false);await refresh()}catch(caught){if(current()){if(caught instanceof ApiError&&authCodes.includes(caught.problem.code))expire();else setError(operationError(caught,'运行时配置保存结果未确认，请刷新状态。'))}}finally{operation.current=false;if(current())setBusy('')}};
 const inspect=async(id:string)=>{if(!canMutate||!current()||operation.current)return;operation.current=true;setBusy(`${id}:inspect`);try{const [d,c,l]=await Promise.all([api.modelCenterRuntimeDiagnostics(id,requestContext),api.modelCenterRuntimeCapabilities(id,requestContext),api.modelCenterRuntimeLogs(id,requestContext)]);if(!current())return;setDiagnostics(d);setSnapshot(c);setLogs(logArrays(l));setSelected(id)}catch(caught){if(current()){if(caught instanceof ApiError&&authCodes.includes(caught.problem.code))expire();else setError('运行时诊断读取失败。')}}finally{operation.current=false;if(current())setBusy('')}};
 const readVideoObservations=async()=>{if(!onboarding||!canMutate||!current()||operation.current)return;operation.current=true;setBusy('video-observations');retireVideoObservations();const generation=videoObservationGeneration.current;try{const value=await owner.client.environment();if(current()&&generation===videoObservationGeneration.current)setVideoObservations(value.video_observations)}catch(caught){if(current()&&generation===videoObservationGeneration.current){if(caught instanceof ApiError&&([401,403].includes(caught.status)||authCodes.includes(caught.problem.code)))expire();else setError('视频模型观察读取失败，请核对原记录。')}}finally{operation.current=false;if(current())setBusy('')}};
 useEffect(()=>{const ids=runtimes.filter(item=>item.runtime_type==='WHISPER_CPP'&&item.instance?.state==='STARTING').map(item=>item.id).sort().join('|');if(!ids||!canMutate||!current()){pollWindow.current=null;return}if(pollWindow.current?.ids!==ids)pollWindow.current={ids,deadline:performance.now()+120000};const pollState=pollWindow.current;if(!pollState||busy||loading||performance.now()>=pollState.deadline)return;const timer=window.setTimeout(()=>{if(current()&&!operation.current)void refresh(true)},1500);return()=>window.clearTimeout(timer)},[runtimes,canMutate,busy,loading]);
 const field=(key:keyof ModelCenterEditableRuntimeConfiguration,label:string,type='text')=><label>{label}<input type={type} value={String(configuration?.[key]??'')} onChange={event=>setConfiguration(value=>value?{...value,[key]:type==='number'?Number(event.target.value):event.target.value}:value)}/></label>;
 return <div className="model-center">
  {error&&<StatusMessage tone="error">{error}</StatusMessage>}
  <LocalAiDiscovery onboarding={onboarding} scopeRevision={discoveryRevision} canMutate={canMutate} onRegistryChange={()=>{retireVideoObservations();void refresh()}}/>
  {onboarding&&<Panel title="视频模型观察"><Button disabled={!canMutate||loading||!!busy} onClick={()=>void readVideoObservations()}>读取已有视频模型观察</Button><VideoModelObservationSummary report={videoObservations}/><p>只读取原检测回执和启用状态；发现、验证、登记、启用仍由上方原流程处理。</p></Panel>}
  <Panel title="Model Center" actions={<Button variant="ghost" onClick={()=>void refresh()} disabled={loading||!!busy}><RefreshCw aria-hidden="true"/>刷新</Button>}>
   {loading?<div role="status">正在读取模型注册表…</div>:!models.length?<EmptyState title="暂无模型" detail="注册本地模型后会显示在这里。"/>:<div className="model-center__models">{models.map(model=>{
    const whisper=model.runtime_type==='WHISPER_CPP';
    const loaded=whisper&&runtimes.some(runtime=>runtime.runtime_type==='WHISPER_CPP'&&runtimePresentation(runtime).loadedModelId===model.id);
    return <article key={model.id}><header><div><strong>{model.display_name}</strong><small>{model.runtime_type}</small></div>
     <Badge tone={whisper?loaded?'info':'warning':model.status==='READY'?'success':model.status==='INCOMPATIBLE'?'error':'warning'}>{whisper?loaded?'模型已加载':'等待模型加载':model.status}</Badge></header>
     <div className="model-center__capabilities">{model.capabilities.filter(item=>!whisper||item==='AUDIO').map(item=><Badge key={item}>{item}</Badge>)}</div>
     <dl><div><dt>验证</dt><dd>{whisper?'真实字幕推理和完整流程仍待验收':model.verified?'Current Verified':model.historically_validated?'Historical Validation / Verified Baseline':'未完成推理验证'}</dd></div><div><dt>硬件</dt><dd>{model.hardware_profile_details[0]?.gpu_name||'未记录'}</dd></div></dl>
    </article>})}</div>}
  </Panel>
  <Panel title="Local Runtimes">{!loading&&!canMutate&&<StatusMessage tone="warning"><ShieldAlert aria-hidden="true"/>运行时控制需要受信任的桌面会话。Trusted desktop session required.</StatusMessage>}{!loading&&!runtimes.length?<EmptyState title="暂无运行时" detail="配置本地运行时后会显示在这里。"/>:<div className="model-center__runtimes">{runtimes.map(runtime=>{
   const view=runtimePresentation(runtime);return <article key={runtime.id} data-selected={selected===runtime.id}>
    <header><div><strong>{runtime.id}</strong><small>{runtime.runtime_type} · {runtime.management||(view.managed?'MANAGED':'EXTERNAL')}</small></div><Badge tone={view.tone}>{view.state}</Badge></header>
    <dl><div><dt>Endpoint</dt><dd>{runtime.base_url}</dd></div><div><dt>{view.whisper?'用途':'Context'}</dt><dd>{view.whisper?'本地字幕识别':runtime.context_size||'—'}</dd></div>
     <div><dt>{view.whisper?'模型状态':'Health'}</dt><dd>{view.whisper?view.loaded?'模型已加载，推理待验收':'尚无可信模型加载回执':runtime.instance?.http_reachable?'Reachable':'Not reachable'}</dd></div>
     {view.whisper&&<div><dt>配置</dt><dd>服务器固定配置</dd></div>}</dl>
    {view.whisper&&view.state==='STARTING'&&<StatusMessage>正在加载固定字幕模型，可停止加载。装载完成前不能执行字幕识别。</StatusMessage>}
    <div className="model-center__actions"><Button onClick={()=>void action(runtime.id,'validate')} disabled={!canMutate||!!busy||view.state==='STARTING'}>{view.whisper?'核对加载状态':'Validate'}</Button>
     <Button onClick={()=>void action(runtime.id,'start')} disabled={!canMutate||!!busy||!view.canStart}><Play aria-hidden="true"/>{view.whisper?'启动字幕模型':'Start'}</Button>
     <Button variant="ghost" onClick={()=>void action(runtime.id,'stop')} disabled={!canMutate||!!busy||!view.canStop}><Square aria-hidden="true"/>{view.whisper?'停止字幕模型':'Stop'}</Button>
     <Button variant="ghost" onClick={()=>void openEdit(runtime.id)} disabled={!canMutate||!!busy||!view.whisper&&!view.canConfigure}><Settings2 aria-hidden="true"/>{view.whisper?'查看固定配置':'Edit Configuration'}</Button>
     <Button variant="ghost" onClick={()=>void inspect(runtime.id)} disabled={!canMutate||!!busy}><Activity aria-hidden="true"/>View Diagnostics</Button></div>
   </article>})}</div>}</Panel>
  {fixedConfiguration&&<Panel title="Whisper 固定配置" actions={<Button variant="ghost" onClick={()=>setFixedConfiguration(undefined)} aria-label="关闭固定配置"><X aria-hidden="true"/></Button>}>
   <dl><div><dt>运行时</dt><dd>{fixedConfiguration.id}</dd></div><div><dt>Endpoint</dt><dd>{fixedConfiguration.base_url}</dd></div><div><dt>配置来源</dt><dd>服务器固定安装</dd></div><div><dt>用途</dt><dd>本地字幕识别</dd></div></dl>
   <StatusMessage>这里可启动、停止和核对模型加载状态。模型文件与安装配置由服务器管理；完整字幕推理仍需实际验收。</StatusMessage>
  </Panel>}
  {(diagnostics||snapshot||logs)&&<Panel title="Advanced Diagnostics" actions={<Button variant="ghost" onClick={()=>{setDiagnostics(undefined);setSnapshot(undefined);setLogs(undefined)}}><X aria-hidden="true"/></Button>}><div className="model-center__diagnostics">{diagnostics&&<dl><div><dt>State</dt><dd>{diagnostics.state}</dd></div><div><dt>Version</dt><dd>{diagnostics.version||'Unknown'}</dd></div><div><dt>Latency</dt><dd>{diagnostics.latency_ms??'—'} ms</dd></div><div><dt>Error</dt><dd>{diagnostics.safe_error_code||'None'}</dd></div></dl>}{snapshot&&<section><strong>Capabilities</strong><p>{snapshot.capabilities.join(', ')||'None detected'}</p><strong>Node classes</strong><p>{snapshot.node_classes.join(', ')||'None detected'}</p></section>}{logs&&<section><strong><FileText aria-hidden="true"/> Redacted logs</strong><pre>{[...(logs.stdout??[]),...(logs.stderr??[])].join('\n')||'No managed runtime logs.'}</pre></section>}</div></Panel>}
  {editing&&configuration&&<div className="model-center__dialog" role="dialog" aria-modal="true" aria-label="Edit runtime configuration"><form onSubmit={save}><header><h2>Edit Configuration</h2><Button type="button" variant="ghost" onClick={()=>setEditing(false)}><X aria-hidden="true"/></Button></header>{field('base_url','Base URL')}{field('bind_address','Host')}{field('port','Port','number')}{field('health_endpoint','Health endpoint')}{configuration.runtime_type==='LLAMA_CPP'&&<>{field('executable','Executable')}{field('working_directory','Working directory')}{field('model_path','Model path')}{field('context_size','Context','number')}{field('gpu_layers','GPU layers','number')}{field('threads','Threads','number')}{field('batch_size','Batch size','number')}<label>Extra safe flags<input value={(configuration.extra_arguments??[]).join(' ')} onChange={event=>setConfiguration({...configuration,extra_arguments:event.target.value.split(/\s+/).filter(Boolean)})}/></label></>}{configuration.runtime_type==='COMFYUI'&&field('installation_path','Installation path')}<footer><Button type="button" variant="ghost" onClick={()=>setEditing(false)}>Cancel</Button><Button type="submit" disabled={!!busy}>Save</Button></footer></form></div>}
  <Panel title="Pipelines">{pipelines.map(pipeline=><section className="model-center__pipeline" key={pipeline.id}><strong>{pipeline.id}</strong><ol>{pipeline.nodes.map(node=><li key={node.id}><span>{node.capability}</span><code>{node.model_id}</code></li>)}</ol></section>)}</Panel>
 </div>
}
