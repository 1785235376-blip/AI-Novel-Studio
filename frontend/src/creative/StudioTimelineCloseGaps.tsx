import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { previewTimelineCloseGaps } from './timelineCloseGaps';
import type { StudioTimelineDraft } from './studioTimelineTypes';
type Props={draft:StudioTimelineDraft;scope:object;disabled:boolean;isCurrent:()=>boolean;getRevision:()=>string;onApply:(draft:StudioTimelineDraft)=>boolean};
type Preview={value:ReturnType<typeof previewTimelineCloseGaps>;token:object;revision:string;edit:number};
export function StudioTimelineCloseGaps(props:Props){
 const [track,setTrack]=useState(''),[leading,setLeading]=useState(false),[preview,setPreview]=useState<Preview>(),[confirmed,setConfirmed]=useState(false),[error,setError]=useState('');
 const live=useRef(props);live.current=props;const alive=useRef(true),edit=useRef(0),consent=useRef<Preview>(),proof=useRef(preview);proof.current=preview;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;consent.current=undefined;};},[]);
 const values=[props.draft,props.scope,props.disabled,props.getRevision()];const owner=useRef({values,token:{}});if(values.some((value,index)=>value!==owner.current.values[index]))owner.current={values,token:{}};const token=owner.current.token;
 const current=()=>alive.current&&!live.current.disabled&&live.current.isCurrent()&&owner.current.token===token;
 const visible=preview&&preview.token===token&&preview.edit===edit.current&&preview.revision===props.getRevision()?preview:undefined;
 function reset(){edit.current++;consent.current=undefined;proof.current=undefined;setConfirmed(false);setPreview(undefined);setError('');}
 return <details aria-label="关闭单轨空隙"><summary>关闭单轨空隙</summary><p>只前移所选轨道的片段，保留片段内部裁剪、速度和交叉溶解。其他轨道、字幕和总长保持原位，可能改变声画同步；先核对预览。</p>
  <label>整理空隙的轨道<select value={track} disabled={props.disabled} onChange={event=>{if(current()){reset();setTrack(event.target.value);}}}><option value="">明确选择一条轨道</option>{props.draft.timeline.tracks.map((row,index)=><option key={row.id} value={row.id} disabled={!!row.locked}>{index+1} · {row.kind} · {row.id}{row.locked?' · 已锁定':''}</option>)}</select></label>
  <label><input type="checkbox" checked={leading} disabled={props.disabled} onChange={event=>{if(current()){reset();setLeading(event.target.checked);}}}/>同时关闭本轨开头空隙</label>
  <Button disabled={props.disabled||!track} onClick={()=>{if(!current())return;reset();try{const value=previewTimelineCloseGaps(props.draft,track,leading);const next={value,token,revision:props.getRevision(),edit:edit.current};proof.current=next;setPreview(next);}catch(reason){setError(reason instanceof Error?reason.message:'无法整理当前轨道。');}}}>预览本轨空隙整理</Button>
  {error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  {visible&&<section aria-label="单轨空隙整理预览"><p>关闭 {visible.value.gaps.length} 段空隙，共 {visible.value.removedMs} 毫秒，前移 {visible.value.shifts.length} 个片段。未修改草稿。</p>
   <ul>{visible.value.shifts.map(row=><li key={row.clipId}>{row.clipId}：{row.before} → {row.after} 毫秒</li>)}</ul>
   <label><input type="checkbox" checked={confirmed} disabled={props.disabled||!visible.value.shifts.length} onChange={event=>{if(current()){consent.current=event.target.checked?visible:undefined;setConfirmed(event.target.checked);}}}/>确认仅移动本轨片段，其他轨道与字幕不跟随</label>
   <Button disabled={props.disabled||!confirmed||!visible.value.shifts.length} onClick={()=>{if(!current()||proof.current!==visible||consent.current!==visible||visible.edit!==edit.current||visible.revision!==live.current.getRevision())return;reset();if(!props.onApply(visible.value.draft))setError('当前输入或权限已变化，未应用；请重新预览。');}}>应用空隙整理到本地草稿</Button>
  </section>}
 </details>;
}
