import {useLayoutEffect,useRef,useState} from 'react';
import {Button,Panel,StatusMessage} from '../../ui/primitives';
import type {StudioTimelineRow} from '../studioTimelineTypes';
import {savedCanvasVideoDraftView,type SavedVideoDraftView} from './savedCanvasVideoDraft';

export type SavedCanvasVideoDraftPanelProps={owner:object;current:boolean;canMutate:boolean;busy:boolean;isCurrent:()=>boolean;
  onList:()=>Promise<StudioTimelineRow[]>;onResume:(row:StudioTimelineRow)=>void|Promise<void>};
const functionIds=new WeakMap<Function,number>();let nextFunctionId=0;
const stamp=(value:unknown)=>{try{return JSON.stringify(value,(_key,item)=>{
  if(typeof item==='function'){if(!functionIds.has(item))functionIds.set(item,++nextFunctionId);return `function:${functionIds.get(item)}`;}return item;
});}catch{return undefined;}};
type Listed={row:StudioTimelineRow;stamp:string;view:SavedVideoDraftView};
type Choice={entry:Listed;consent:boolean;used:boolean;retired:boolean};
type Batch={rows:Listed[];raw:StudioTimelineRow[];stamp:string;retired:boolean};
type Session={values:unknown[];retired:boolean;batch?:Batch;choice?:Choice;pending?:'LIST'|'RESUME';error:string;notice:string};
const sessionFor=(values:unknown[]):Session=>({values,retired:false,error:'',notice:''});

/** Explicit input-only recovery. It has no client, storage, dispatch or execution authority. */
export function SavedCanvasVideoDraftPanel(props:SavedCanvasVideoDraftPanelProps){
  const live=useRef(props);live.current=props;
  const alive=useRef(false),committed=useRef<Session>();const[,refresh]=useState(0);
  const values=[props.owner,props.current?stamp(props.owner):undefined,props.current,props.isCurrent,props.onList,props.onResume];
  const slot=useRef(sessionFor(values));
  if(values.some((value,index)=>!Object.is(value,slot.current.values[index]))){slot.current.retired=true;if(slot.current.choice)slot.current.choice.retired=true;slot.current=sessionFor(values);}
  const session=slot.current;
  const owns=()=>alive.current&&committed.current===session&&slot.current===session;
  function retire(){session.retired=true;if(session.choice){session.choice.retired=true;session.choice.consent=false;}}
  function current(){
    if(!owns()||session.retired)return false;
    const p=live.current;
    if(!p.current||p.owner!==values[0]||stamp(p.owner)!==values[1]||p.current!==values[2]||p.isCurrent!==values[3]||p.onList!==values[4]||p.onResume!==values[5]){retire();return false;}
    try{if(!p.isCurrent()){retire();return false;}}catch{retire();return false;}
    return true;
  }
  function batchCurrent(batch:Batch){
    if(session.batch!==batch||batch.retired)return false;
    if(stamp(batch.raw)!==batch.stamp||batch.rows.some(entry=>stamp(entry.row)!==entry.stamp||!savedCanvasVideoDraftView(entry.row))){
      batch.retired=true;if(session.choice){session.choice.retired=true;session.choice.consent=false;}return false;
    }
    return true;
  }
  function choiceCurrent(choice:Choice){
    if(live.current.busy||!live.current.canMutate){choice.retired=true;choice.consent=false;return false;}
    return current()&&!!session.batch&&batchCurrent(session.batch)&&session.choice===choice&&!choice.retired&&stamp(choice.entry.row)===choice.entry.stamp;
  }
  useLayoutEffect(()=>{alive.current=true;committed.current=session;return()=>{if(committed.current===session)committed.current=undefined;};});
  useLayoutEffect(()=>()=>{alive.current=false;},[]);
  async function list(){
    if(!current()||props.busy||session.pending)return;
    if(session.batch)session.batch.retired=true;if(session.choice)session.choice.retired=true;
    session.batch=undefined;session.choice=undefined;session.error='';session.notice='';session.pending='LIST';refresh(v=>v+1);
    try{
      const rows=await props.onList();if(!current())return;
      if(!Array.isArray(rows)||rows.length>25||new Set(rows.map(row=>row?.id)).size!==rows.length)throw new Error();
      const rawStamp=stamp(rows);if(rawStamp===undefined)throw new Error();const checked:Listed[]=[];
      for(const row of rows){const view=savedCanvasVideoDraftView(row),key=stamp(row);if(view&&key!==undefined)checked.push({row,view,stamp:key});}
      session.batch={rows:checked,raw:rows,stamp:rawStamp,retired:false};
    }catch{if(current())session.error='草稿列表读取未确认，请重新读取当前项目。';}
    finally{session.pending=undefined;if(owns())refresh(v=>v+1);}
  }
  async function resume(choice:Choice){
    if(!choiceCurrent(choice)||!live.current.canMutate||live.current.busy||session.pending||!choice.consent||choice.used)return;
    choice.used=true;session.pending='RESUME';session.error='';session.notice='';refresh(v=>v+1);
    try{
      if(!choiceCurrent(choice))return;await props.onResume(choice.entry.row);
      if(choiceCurrent(choice))session.notice='已提交输入草稿恢复请求；原入口仍须重新校验来源、预览并明确确认。没有派发或采用。';
    }catch{if(choiceCurrent(choice))session.error='草稿恢复未确认，原草稿保留。请重新读取并核对版本与权限。';}
    finally{session.pending=undefined;if(owns())refresh(v=>v+1);}
  }
  if(!props.current){retire();return null;}
  if(values[1]===undefined)retire();
  try{if(!props.isCurrent())retire();}catch{retire();}
  if((props.busy||!props.canMutate)&&session.choice){session.choice.retired=true;session.choice.consent=false;}
  const batch=session.batch;
  const validBatch=!!batch&&batchCurrent(batch);
  const selected=validBatch?session.choice:undefined;
  const blocked=session.retired||props.busy||!!session.pending;
  const canResume=!!selected&&!selected.retired&&!selected.used&&selected.consent&&props.canMutate&&!blocked;
  return <Panel title="恢复已保存的视频派生输入" aria-label="未入队视频派生草稿恢复">
    <p>只恢复本次任务的输入和来源，不修改共享工作流模板。保存的草稿不包含执行确认；恢复后必须重新校验原失败任务、来源与画布位置，再明确预览、入队和执行。</p>
    <StatusMessage>读取、选择和恢复均不会自动派发、审核或采用。已入队请求及 UNKNOWN 须从原任务记录核对。处理费用与运行时间未知。</StatusMessage>
    <div className="creative-actions"><Button disabled={blocked} loading={session.pending==='LIST'} onClick={()=>void list()}>读取已保存视频输入草稿</Button></div>
    {session.retired&&<StatusMessage tone="warning">当前项目、客户端或权限已改变，旧草稿确认已退役。</StatusMessage>}
    {batch&&validBatch&&<>
      {!batch.rows.length?<p>没有当前版本可恢复的未入队视频派生输入。</p>:<label className="creative-field">已保存的视频输入草稿<select aria-label="已保存的视频输入草稿" value={selected?.entry.view.id??''} disabled={blocked} onChange={event=>{
        if(!current()||!batchCurrent(batch)||session.pending||live.current.busy)return;
        if(session.choice)session.choice.retired=true;const entry=batch.rows.find(row=>row.view.id===event.target.value);
        session.choice=entry?{entry,consent:false,used:false,retired:false}:undefined;session.error='';session.notice='';refresh(v=>v+1);
      }}><option value="">选择一个输入草稿</option>{batch.rows.map(entry=><option key={entry.view.id} value={entry.view.id}>{entry.view.title} · v{entry.view.version}</option>)}</select></label>}
    </>}
    {batch&&!validBatch&&<StatusMessage tone="warning">列表中的原版本、参数或来源已改变，旧确认已退役。请重新读取。</StatusMessage>}
    {selected&&<section aria-label="所选视频输入草稿">
      <p>独立时间线 <code>{selected.entry.view.id}</code> · v{selected.entry.view.version} · 新请求 <code>{selected.entry.view.requestId}</code></p>
      <p>原失败 Job <code>{selected.entry.view.parentJobId}</code> · v{selected.entry.view.parentJobVersion}；原视频 <code>{selected.entry.view.sourceId}</code> · v{selected.entry.view.sourceVersion}</p>
      <p>原画布 <code>{selected.entry.view.canvasId}</code> · v{selected.entry.view.canvasVersion} · 卡片 <code>{selected.entry.view.cardId}</code>；范围 {selected.entry.view.inMs}–{selected.entry.view.outMs} 毫秒 · {selected.entry.view.audio}</p>
      <label><input type="checkbox" checked={selected.consent&&!selected.retired} disabled={blocked||!props.canMutate||selected.used||selected.retired} onChange={event=>{
        if(!choiceCurrent(selected)||!live.current.canMutate||live.current.busy||session.pending||selected.used)return;
        selected.consent=event.target.checked;refresh(v=>v+1);
      }}/>我已核对所选版本与来源，仅恢复输入草稿</label>
      <div className="creative-actions"><Button disabled={!canResume} loading={session.pending==='RESUME'} onClick={()=>void resume(selected)}>明确仅恢复输入草稿</Button></div>
    </section>}
    {!props.canMutate&&<StatusMessage tone="warning">当前只能读取草稿，没有恢复修改权限。</StatusMessage>}
    {session.error&&<StatusMessage tone="error">{session.error}</StatusMessage>}
    {session.notice&&<StatusMessage>{session.notice}</StatusMessage>}
  </Panel>;
}
