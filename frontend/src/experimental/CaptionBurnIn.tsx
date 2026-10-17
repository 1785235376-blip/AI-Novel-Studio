import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { ErrorMessage } from './shared';
import type { ExperimentalClient } from './api';
import { downloadCaption, type CaptionTrack } from './voiceSubtitleClient';
import { captionBurnInClient, type BurnCatalog, type BurnTask } from './captionBurnInClient';
type Props={client:ExperimentalClient;row:CaptionTrack;binding:string;disabled:boolean};
const actionLabel={execute:'执行本地字幕压制',cancel:'取消此压制任务',recover:'恢复中断任务状态',resume:'重新排队此任务',approve:'批准此渲染产物',reject:'拒绝此渲染产物'};
export function CaptionBurnIn(props:Props){
  const api=useMemo(()=>captionBurnInClient(props.client),[props.client]);
  const live=useRef(props);live.current=props;const alive=useRef(true),lock=useRef(false);
  const values=[props.client,props.binding,props.disabled];const owner=useRef({values,token:{}});
  if(values.some((value,index)=>value!==owner.current.values[index]))owner.current={values,token:{}};
  const token=owner.current.token;const current=()=>alive.current&&!live.current.disabled&&owner.current.token===token;
  const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(),[adapter,setAdapter]=useState('');
  const [snapshot,setSnapshot]=useState<{owner:object;catalog:BurnCatalog;tasks:BurnTask[]}>();
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
  const ready=()=>current()&&!lock.current&&snapshotRef.current===visible&&!!visible;
  const updateTask=(task:BurnTask)=>{if(!current())return;setSnapshot(old=>old?.owner===token?{...old,tasks:[task,...old.tasks.filter(row=>row.id!==task.id)]}:old);};
  async function queue(){if(!props.row.cues.length||!ready()||createUnknown.current||uncertainRef.current||!visible?.catalog.adapters.some(row=>row.adapter_id===adapter)||consentRef.current!==`queue:${adapter}`)return;
    await run(async()=>{resetConsent();createUnknown.current=true;setUnknownCreate(true);const task=await api.queue(props.row,adapter);if(!current())return;updateTask(task);createUnknown.current=false;setUnknownCreate(false);});}
  async function action(task:BurnTask,kind:keyof typeof actionLabel){const key=`${task.id}:${task.version}:${kind}`;
    if(!ready()||uncertainRef.current||consentRef.current!==key||!visible?.tasks.includes(task))return;
    await run(async()=>{resetConsent();const pending={id:task.id,version:task.version};uncertainRef.current=pending;setUncertain(pending);const next=await api.action(props.row,task,kind);if(!current())return;updateTask(next);uncertainRef.current=undefined;setUncertain(undefined);});}
  function confirm(key:string,checked:boolean){if(!ready())return;consentRef.current=checked?key:'';setConsent(consentRef.current);}
  const controls=(task:BurnTask):Array<keyof typeof actionLabel>=>task.status==='QUEUED'?['execute','cancel']:task.status==='RUNNING'?task.recovery_required?['recover','cancel']:['cancel']:task.status==='NEEDS_REVIEW'?['approve','reject','cancel']:['FAILED','CANCELLED','INTERRUPTED','NOT_CONFIGURED'].includes(task.status)?['resume']:[];
  return <section aria-label="本地字幕压制"><h4>本地字幕压制任务</h4><p>只使用此字幕已保存 v{props.row.version} 与原视频。读取不会启动任务；排队、执行、审核和下载分别确认。无配置时不安装、不调用云端。</p>
    <Button disabled={props.disabled||busy} onClick={load}>读取字幕压制能力与任务</Button>
    {busy&&<StatusMessage>正在与原字幕处理服务核对…</StatusMessage>}{!!error&&<ErrorMessage error={error}/>}
    {unknownCreate&&<StatusMessage tone="warning">创建结果尚未核实，禁止重复创建。请读取原任务目录核对；读取到已有任务不能证明本次请求未执行。关闭前请记录此状态。</StatusMessage>}
    {uncertain&&<StatusMessage tone="warning">任务操作回执尚未核实，请先读取当前任务状态，不自动重发。</StatusMessage>}
    {!props.row.cues.length&&<p>先填写并保存字幕，才能创建压制任务。</p>}
    {visible&&<>{!visible.catalog.adapters.length?<p>当前未配置可用的正式本地字幕压制器；合成测试适配器不作为生产能力。</p>:<>
      <label>字幕压制器<select value={adapter} disabled={busy||unknownCreate||!!uncertain} onChange={event=>{resetConsent();setAdapter(event.target.value);}}><option value="">明确选择已配置适配器</option>{visible.catalog.adapters.map(row=><option key={row.adapter_id} value={row.adapter_id}>{row.adapter_id} · {row.version}</option>)}</select></label>
      <label><input type="checkbox" checked={consent===`queue:${adapter}`} disabled={!props.row.cues.length||!adapter||busy||unknownCreate||!!uncertain} onChange={event=>confirm(`queue:${adapter}`,event.target.checked)}/>确认只创建此已保存字幕的压制任务</label>
      <Button disabled={!props.row.cues.length||!adapter||busy||unknownCreate||!!uncertain||consent!==`queue:${adapter}`} onClick={()=>void queue()}>创建字幕压制任务（不执行）</Button></>}
      <p>仅显示当前字幕版本的正式压制任务；旧版本和来源失效任务不会在这里重新启用。字体效果与观感仍需人工查看导出文件。</p>
      {visible.tasks.map(task=><article key={task.id} aria-label={`压制任务 ${task.id}`}><p>{task.id} · v{task.version} · {task.status}</p>
        {task.result&&<p>产物 {task.result.bytes} 字节 · {task.result.media_type} · SHA-256 {task.result.sha256}</p>}
        {uncertain?.id===task.id&&task.version>uncertain.version&&<Button disabled={busy} onClick={()=>{if(!ready()||uncertainRef.current?.id!==task.id||task.version<=uncertainRef.current.version)return;uncertainRef.current=undefined;setUncertain(undefined);resetConsent();}}>采用已更新的原任务状态</Button>}
        {controls(task).map(kind=>{const key=`${task.id}:${task.version}:${kind}`;return <div key={kind}><label><input type="checkbox" checked={consent===key} disabled={busy||!!uncertain} onChange={event=>confirm(key,event.target.checked)}/>确认{actionLabel[kind]}</label><Button disabled={busy||!!uncertain||consent!==key} onClick={()=>void action(task,kind)}>{actionLabel[kind]}</Button></div>;})}
        {task.status==='APPROVED'&&<Button disabled={busy||!!uncertain} onClick={()=>{if(!ready())return;void run(async()=>{const blob=await api.download(task);if(current())downloadCaption(blob,`captions-${task.id}.${task.result?.media_type==='video/webm'?'webm':'mp4'}`);});}}>下载已批准字幕视频</Button>}
      </article>)}
    </>}
  </section>;
}
