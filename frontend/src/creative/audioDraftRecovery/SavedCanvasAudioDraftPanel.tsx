import {useLayoutEffect,useRef,useState} from 'react';
import {Button,Panel,StatusMessage} from '../../ui/primitives';
import {audioDraftStamp,checkedAudioDraftSummary,type AudioDraftSummary} from './audioDraftSummary';
export type {AudioDraftSummary} from './audioDraftSummary';
export type SavedCanvasAudioDraftPanelProps = {
  owner: object; current: boolean; canMutate: boolean; busy: boolean; sessionInputKey: string; isCurrent: () => boolean;
  onList: () => Promise<AudioDraftSummary[]>; onResume: (summary: AudioDraftSummary) => void | Promise<void>;
};
type Entry = {raw: AudioDraftSummary; stamp: string; snapshot: Readonly<AudioDraftSummary>};
type Choice = {entry: Entry; consent: boolean; consumed: boolean; retired: boolean};
type Lease = {authority: unknown[]; retired: boolean; reset?: boolean; pending?: 'LIST'|'RESTORE'; raw?: AudioDraftSummary[]; stamp?: string; entries?: Entry[]; choice?: Choice; error?: string; notice?: string};
/** Input-only projection: no client, storage, proof, queue or execution capability. */
export function SavedCanvasAudioDraftPanel(props: SavedCanvasAudioDraftPanelProps) {
  const live=useRef(props);live.current=props;
  const alive=useRef(false),committed=useRef<Lease>(),[,paint]=useState(0);
  const authority=[props.owner,audioDraftStamp(props.owner),props.current,props.canMutate,props.busy,props.sessionInputKey,props.isCurrent,props.onList,props.onResume];
  const slot=useRef<Lease>({authority,retired:false});
  if(authority.some((v,i)=>!Object.is(v,slot.current.authority[i]))) { slot.current.retired=true; if(slot.current.choice)slot.current.choice.retired=true; slot.current={authority,retired:false,reset:true}; }
  const lease=slot.current;
  function retire(){lease.retired=true;if(lease.choice){lease.choice.retired=true;lease.choice.consent=false;}}
  function owns(){return alive.current&&committed.current===lease&&slot.current===lease;}
  function current(){
    if(!owns()||lease.retired)return false;
    const p=live.current,now=[p.owner,audioDraftStamp(p.owner),p.current,p.canMutate,p.busy,p.sessionInputKey,p.isCurrent,p.onList,p.onResume];
    if(!p.current||now[1]===undefined||now.some((v,i)=>!Object.is(v,authority[i]))){retire();return false;}
    try{if(!p.isCurrent()){retire();return false;}}catch{retire();return false;}
    return true;
  }
  function entriesCurrent(){
    if(!current()||!lease.raw||!lease.entries)return false;
    if(audioDraftStamp(lease.raw)!==lease.stamp||lease.entries.some(e=>audioDraftStamp(e.raw)!==e.stamp)){retire();return false;}
    return true;
  }
  function selectionCurrent(choice: Choice){return entriesCurrent()&&lease.choice===choice&&!choice.retired&&live.current.canMutate&&!live.current.busy;}
  useLayoutEffect(()=>{alive.current=true;committed.current=lease;return()=>{if(committed.current===lease)committed.current=undefined;};});
  useLayoutEffect(()=>()=>{alive.current=false;},[]);
  async function list(){
    if(!current()||live.current.busy||lease.pending)return;
    if(lease.choice)lease.choice.retired=true;lease.choice=undefined;lease.raw=undefined;lease.entries=undefined;lease.error='';lease.notice='';lease.pending='LIST';paint(n=>n+1);
    try{
      const raw=await props.onList();if(!current())return;
      if(!Array.isArray(raw)||raw.length>25)throw new Error();
      const entries=raw.map(row=>{const snapshot=checkedAudioDraftSummary(row),stamp=audioDraftStamp(row);if(stamp===undefined||audioDraftStamp(snapshot)!==stamp)throw new Error();return {raw:row,stamp,snapshot};});
      if(new Set(entries.map(e=>e.snapshot.id)).size!==entries.length)throw new Error();
      const stamp=audioDraftStamp(raw);if(stamp===undefined)throw new Error();lease.raw=raw;lease.stamp=stamp;lease.entries=entries;
    }catch{if(current())lease.error='音频草稿列表未能核对，请重新读取当前项目。';}
    finally{lease.pending=undefined;if(owns())paint(n=>n+1);}
  }
  async function restore(choice: Choice){
    if(!selectionCurrent(choice)){if(owns())paint(n=>n+1);return;}
    if(lease.pending||!choice.consent||choice.consumed)return;
    choice.consumed=true;choice.consent=false;lease.pending='RESTORE';lease.error='';lease.notice='';paint(n=>n+1);
    try{
      if(!selectionCurrent(choice))return;
      await props.onResume(choice.entry.snapshot);
      if(selectionCurrent(choice))lease.notice='已提交仅恢复输入的意图；原入口仍须重新校验、预览并明确确认，尚未派发或采用。';
    }catch{if(selectionCurrent(choice))lease.error='音频输入恢复未确认。原已保存草稿保留，请重新核对来源与版本。';}
    finally{lease.pending=undefined;if(owns())paint(n=>n+1);}
  }
  if(!props.current){retire();return null;}
  if(authority[1]===undefined||!props.owner||typeof props.owner!=='object'||Array.isArray(props.owner))retire();
  try{if(!props.isCurrent())retire();}catch{retire();}
  const valid=lease.entries?entriesCurrent():false;
  const choice=valid?lease.choice:undefined,row=choice?.entry.snapshot;
  const blocked=lease.retired||props.busy||!!lease.pending;
  return <Panel title="恢复已保存的音频输入" aria-label="未入队音频草稿恢复">
    <p>已保存草稿只含本次任务输入和来源，不含执行确认。尚未应用或保存的输入仍只在当前会话中；恢复会替换当前会话输入，保留原已保存版本。</p>
    <StatusMessage>不会修改共享模板或自动入队、执行、审核、采用。已入队及 UNKNOWN 请求须回到原任务核对；运行时间和费用尚未估算。</StatusMessage>
    <Button disabled={blocked} loading={lease.pending==='LIST'} onClick={()=>void list()}>读取已保存音频输入草稿</Button>
    {(lease.retired||lease.reset)&&<StatusMessage tone="warning">项目、客户端、输入或权限已改变，旧恢复确认已退役。请重新读取。</StatusMessage>}
    {lease.entries&&valid&&(!lease.entries.length?<p>没有可选择的已保存音频输入草稿。</p>:<label className="creative-field">已保存的音频输入草稿<select aria-label="已保存的音频输入草稿" disabled={blocked} value={row?.id??''} onChange={event=>{
      if(!entriesCurrent()||live.current.busy||lease.pending)return;
      if(lease.choice)lease.choice.retired=true;
      const entry=lease.entries?.find(e=>e.snapshot.id===event.target.value);lease.choice=entry?{entry,consent:false,consumed:false,retired:false}:undefined;lease.error='';lease.notice='';paint(n=>n+1);
    }}><option value="">选择一个已保存输入</option>{lease.entries.map(e=><option key={e.snapshot.id} value={e.snapshot.id}>{e.snapshot.title} · v{e.snapshot.version}</option>)}</select></label>)}
    {row&&choice&&<section aria-label="所选音频输入草稿">
      <p>已保存输入 <code>{row.id}</code> · v{row.version}；请求 <code>{row.requestId}</code>。</p>
      <p>来源音频 <code>{row.sourceId}</code> · v{row.sourceVersion}；画布 <code>{row.canvasId}</code> · v{row.canvasVersion}；原卡片 <code>{row.cardId}</code>。</p>
      <p>截取 {row.inMs}–{row.outMs} ms；增益 {row.gainDb===undefined?'未提供，沿原请求处理':`${row.gainDb} dB`}；淡入 {row.fadeInMs===undefined?'未提供':`${row.fadeInMs} ms`}；淡出 {row.fadeOutMs===undefined?'未提供':`${row.fadeOutMs} ms`}。</p>
      {row.templateGraphId?<p>来源模板 <code>{row.templateGraphId}</code> · v{row.templateVersion}；恢复任务局部覆盖，不修改该模板。</p>:<p>此摘要没有模板来源绑定；不能推断为共享模板。</p>}
      {row.parentJobId?<p>原失败来源 Job <code>{row.parentJobId}</code> · v{row.parentJobVersion}；恢复前须由原 owner 重新核对仍为 FAILED。</p>:<p>此摘要没有失败任务派生绑定。</p>}
      <details><summary>核对所选版本摘要</summary><p>时间线 <code>{row.timelineDigest}</code></p><p>输入草稿 <code>{row.draftDigest}</code></p><p>摘要只标识所选输入，面板不授予执行或来源访问权限。</p></details>
      <label><input type="checkbox" checked={choice.consent&&!choice.retired} disabled={blocked||!props.canMutate||choice.consumed||choice.retired} onChange={event=>{
        if(!selectionCurrent(choice)||lease.pending||choice.consumed)return;choice.consent=event.target.checked;paint(n=>n+1);
      }}/>我已核对所选版本与来源，同意用已保存草稿替换当前会话输入</label>
      <div className="creative-actions"><Button disabled={blocked||!props.canMutate||choice.consumed||choice.retired||!choice.consent} loading={lease.pending==='RESTORE'} onClick={()=>void restore(choice)}>明确仅恢复音频输入草稿</Button></div>
    </section>}
    {!props.canMutate&&<StatusMessage tone="warning">当前只能读取，没有恢复修改权限。</StatusMessage>}
    {lease.error&&<StatusMessage tone="error">{lease.error}</StatusMessage>}
    {lease.notice&&<StatusMessage>{lease.notice}</StatusMessage>}
  </Panel>;
}
