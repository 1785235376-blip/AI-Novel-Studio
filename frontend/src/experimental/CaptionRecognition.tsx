import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { ErrorMessage } from './shared';
import type { ExperimentalClient } from './api';
import type { CaptionTrack } from './voiceSubtitleClient';
import { captionRecognitionClient, type RecognitionCatalog, type RecognitionTask, type RecognitionOperation } from './captionRecognitionClient';
type Props={client:ExperimentalClient;row:CaptionTrack;binding:string;disabled:boolean;onApplied:()=>void};
const actionLabel={execute:'执行本地转录或对齐',cancel:'取消此识别任务',recover:'恢复识别中断状态',resume:'重新排队识别任务',approve:'批准并替换已保存字幕',reject:'拒绝此识别结果'};
export function CaptionRecognition(props:Props){
  const api=useMemo(()=>captionRecognitionClient(props.client),[props.client]);
  const live=useRef(props);live.current=props;const alive=useRef(true),lock=useRef(false);
  const values=[props.client,props.binding,props.disabled];const owner=useRef({values,token:{}});
  if(values.some((value,index)=>value!==owner.current.values[index]))owner.current={values,token:{}};
  const token=owner.current.token;const current=()=>alive.current&&!live.current.disabled&&owner.current.token===token;
  const [operation,setOperation]=useState<RecognitionOperation>('ASR'),[transcript,setTranscript]=useState('');
  const transcriptInput=useRef<HTMLTextAreaElement>(null),composing=useRef(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(),[adapter,setAdapter]=useState('');
  const [snapshot,setSnapshot]=useState<{owner:object;catalog:RecognitionCatalog;tasks:RecognitionTask[]}>();
  const snapshotRef=useRef(snapshot);snapshotRef.current=snapshot;
  const [unknownCreate,setUnknownCreate]=useState(false),createUnknown=useRef(false);
  const [uncertain,setUncertain]=useState<{id:string;version:number}>();
  const uncertainRef=useRef(uncertain);uncertainRef.current=uncertain;
  const [consent,setConsent]=useState('');const consentRef=useRef('');
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const visible=snapshot?.owner===token&&!props.disabled?snapshot:undefined;
  const resetConsent=()=>{consentRef.current='';setConsent('');};
  async function run(work:()=>Promise<void>){if(!current()||lock.current)return;lock.current=true;setBusy(true);setError(undefined);try{await work();}catch(reason){if(current()){setError(reason);setSnapshot(undefined);}}finally{lock.current=false;if(alive.current)setBusy(false);}}
  const load=()=>void run(async()=>{resetConsent();const [catalog,tasks]=await Promise.all([api.catalog(),api.tasks(props.row)]);if(!current())return;setSnapshot({owner:token,catalog,tasks});setAdapter('');});
  const alignmentValid=!!transcript.trim()&&Array.from(transcript).length<=100000;
  const ready=()=>current()&&!lock.current&&snapshotRef.current===visible&&!!visible;
  const updateTask=(task:RecognitionTask)=>{if(!current())return;setSnapshot(old=>old?.owner===token?{...old,tasks:[task,...old.tasks.filter(row=>row.id!==task.id)]}:old);};
  async function queue(){if(composing.current||operation==='FORCED_ALIGNMENT'&&(!alignmentValid||transcriptInput.current?.value!==transcript)||!ready()||createUnknown.current||uncertainRef.current||!visible?.catalog.adapters.some(row=>row.adapter_id===adapter&&row.operations.includes(operation))||consentRef.current!==`queue:${operation}:${adapter}`)return;
    await run(async()=>{resetConsent();createUnknown.current=true;setUnknownCreate(true);const task=await api.queue(props.row,adapter,operation,operation==='FORCED_ALIGNMENT'?transcript:'');if(!current())return;updateTask(task);createUnknown.current=false;setUnknownCreate(false);});}
  async function action(task:RecognitionTask,kind:keyof typeof actionLabel){const key=`${task.id}:${task.version}:${kind}`;
    if(!ready()||uncertainRef.current||consentRef.current!==key||!visible?.tasks.includes(task))return;
    await run(async()=>{resetConsent();const pending={id:task.id,version:task.version};uncertainRef.current=pending;setUncertain(pending);const next=await api.action(props.row,task,kind);if(!current())return;updateTask(next);uncertainRef.current=undefined;setUncertain(undefined);if(kind==='approve')props.onApplied();});}
  function confirm(key:string,checked:boolean){if(!ready())return;consentRef.current=checked?key:'';setConsent(consentRef.current);}
  const controls=(task:RecognitionTask):Array<keyof typeof actionLabel>=>task.status==='QUEUED'?['execute','cancel']:task.status==='RUNNING'?task.recovery_required?['recover','cancel']:['cancel']:task.status==='NEEDS_REVIEW'?['approve','reject','cancel']:['FAILED','CANCELLED','INTERRUPTED','NOT_CONFIGURED'].includes(task.status)?['resume']:[];
  return <section aria-label="本地转录与对齐"><h4>本地语音转录与人工原文对齐</h4><p>使用已保存字幕 v{props.row.version} 的原媒体。转录由已注册本地 ASR 路线执行；对齐使用你提供的原文。结果先预览，明确批准后才替换已保存字幕并新增版本，不改原音视频。模型质量未经本次验收。</p>
    <Button disabled={props.disabled||busy} onClick={load}>读取本地转录与对齐能力</Button>
    {busy&&<StatusMessage>正在与原字幕处理服务核对…</StatusMessage>}{!!error&&<ErrorMessage error={error}/>}
    {unknownCreate&&<StatusMessage tone="warning">创建结果尚未核实，禁止重复创建。请读取原任务目录核对；读取到已有任务不能证明本次请求未执行。关闭前请记录此状态。</StatusMessage>}
    {uncertain&&<StatusMessage tone="warning">任务操作回执尚未核实，请先读取当前任务状态，不自动重发。</StatusMessage>}

    {visible&&<>{!visible.catalog.adapters.length?<p>当前未配置可用的正式本地转录或对齐路线；需要在原模型中心配置，不会安装模型或使用云端回退。</p>:<>
      <label>识别操作<select value={operation} disabled={busy||unknownCreate||!!uncertain} onChange={event=>{if(!ready())return;resetConsent();setOperation(event.target.value as RecognitionOperation);setAdapter('');}}><option value="ASR">从原媒体转录语音</option><option value="FORCED_ALIGNMENT">将人工原文对齐原媒体</option></select></label>
      {operation==='FORCED_ALIGNMENT'&&<label>人工对齐原文<textarea ref={transcriptInput} value={transcript} maxLength={200000} disabled={busy||unknownCreate||!!uncertain} onChange={event=>{if(!ready())return;resetConsent();setTranscript(event.target.value);}} onCompositionStart={()=>{composing.current=true;resetConsent();}} onCompositionEnd={event=>{composing.current=false;resetConsent();setTranscript(event.currentTarget.value);}}/></label>}
      <label>本地识别适配器<select value={adapter} disabled={busy||unknownCreate||!!uncertain} onChange={event=>{resetConsent();setAdapter(event.target.value);}}><option value="">明确选择已配置适配器</option>{visible.catalog.adapters.filter(row=>row.operations.includes(operation)).map(row=><option key={row.adapter_id} value={row.adapter_id}>{row.adapter_id} · {row.version}</option>)}</select></label>
      <label><input type="checkbox" checked={consent===`queue:${operation}:${adapter}`} disabled={operation==='FORCED_ALIGNMENT'&&!alignmentValid||!adapter||busy||unknownCreate||!!uncertain} onChange={event=>confirm(`queue:${operation}:${adapter}`,event.target.checked)}/>确认只创建此已保存来源的识别任务</label>
      <Button disabled={operation==='FORCED_ALIGNMENT'&&!alignmentValid||!adapter||busy||unknownCreate||!!uncertain||consent!==`queue:${operation}:${adapter}`} onClick={()=>void queue()}>创建识别任务（不执行）</Button></>}
      <p>仅显示当前字幕来源版本的正式任务；批准后的新字幕仍可通过原历史入口核对。阅读结果、刷新目录不会执行模型或自动批准。</p>
      {visible.tasks.map(task=><article key={task.id} aria-label={`识别任务 ${task.id}`}><p>{task.id} · v{task.version} · {task.status} · 来源字幕 v{task.caption_version}</p>
        {task.result&&<RecognitionResult task={task}/>}
        {task.applied_caption_version&&<p>已通过原字幕服务保存为 v{task.applied_caption_version}；请载入当前字幕查看，不自动覆盖本地输入。</p>}
        {uncertain?.id===task.id&&task.version>uncertain.version&&<Button disabled={busy} onClick={()=>{if(!ready()||uncertainRef.current?.id!==task.id||task.version<=uncertainRef.current.version)return;uncertainRef.current=undefined;setUncertain(undefined);resetConsent();}}>采用已更新的原任务状态</Button>}
        {controls(task).map(kind=>{const key=`${task.id}:${task.version}:${kind}`;return <div key={kind}><label><input type="checkbox" checked={consent===key} disabled={busy||!!uncertain} onChange={event=>confirm(key,event.target.checked)}/>确认{actionLabel[kind]}</label><Button disabled={busy||!!uncertain||consent!==key} onClick={()=>void action(task,kind)}>{actionLabel[kind]}</Button></div>;})}

      </article>)}
    </>}
  </section>;
}

function RecognitionResult({task}:{task:RecognitionTask}){const [page,setPage]=useState(0);const cues=task.result?.cues||[];return <section aria-label={`识别结果 ${task.id}`}><p>{cues.length} 条字幕 · {task.result?.timing_origin} · 质量待人工复核；时间单位为当前字幕 tick。</p><ol>{cues.slice(page*20,(page+1)*20).map(cue=><li key={cue.id}>{cue.start_tick} → {cue.end_tick}：{cue.text}</li>)}</ol>{cues.length>20&&<><Button disabled={!page} onClick={()=>setPage(value=>value-1)}>上一页识别字幕</Button><Button disabled={(page+1)*20>=cues.length} onClick={()=>setPage(value=>value+1)}>下一页识别字幕</Button></>}</section>;}
