import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field } from './shared';
import { voiceSubtitleClient, type CaptionCue, type CaptionTrack, type CaptionHistoryPage, type CaptionHistoryPreview } from './voiceSubtitleClient';

class HistoryResponseError extends Error {}
const invalid=()=>{throw new HistoryResponseError('历史响应与当前字幕或来源不匹配，请重新读取历史。');};
const object=(value:any)=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const integer=(value:any,min:number,max=Number.MAX_SAFE_INTEGER)=>Number.isSafeInteger(value)&&value>=min&&value<=max;
const text=(value:any,min:number,max:number)=>typeof value==='string'&&Array.from(value).length>=min&&Array.from(value).length<=max;
const cueFields=(cue:CaptionCue):CaptionCue=>({id:cue.id,start_tick:cue.start_tick,end_tick:cue.end_tick,text:cue.text,segment_id:cue.segment_id,overlap_reason:cue.overlap_reason});
function pageResponse(value:CaptionHistoryPage,row:CaptionTrack,before?:number) {
 if(!object(value)||value.record_id!==row.id||value.expected_version!==row.version||!Array.isArray(value.items)||value.items.length>20||typeof value.has_more!=='boolean')return invalid();
 let previous=before??row.version;
 for(const item of value.items){
  if(!object(item)||!integer(item.version,1)||item.version>=previous||!text(item.updated_at,1,100)||!['DRAFT','APPROVED'].includes(item.status)||!['MANUAL','SYNTHETIC_FIXTURE','MFA_WORD_INTERVALS','MODEL_SEGMENT_TIMESTAMPS','ADAPTER_CUE_ALIGNMENT'].includes(item.timing_origin)||!integer(item.cue_count,0,2000))return invalid();
  previous=item.version;
 }
 if(value.has_more?(!value.items.length||value.next_before_version!==previous):value.next_before_version!==null)return invalid();
 return value;
}
function previewResponse(value:CaptionHistoryPreview,row:CaptionTrack,version:number) {
 if(!object(value)||value.record_id!==row.id||value.expected_version!==row.version||value.history_version!==version||value.asset_id!==row.asset_id||!object(value.asset_snapshot)||value.asset_snapshot.version!==row.asset_snapshot?.version||value.asset_snapshot.digest!==row.asset_snapshot?.digest||!text(value.asset_snapshot.digest,1,240)||!integer(value.asset_snapshot.version,1)||!object(value.timebase)||value.timebase.numerator!==row.timebase.numerator||value.timebase.denominator!==row.timebase.denominator||!integer(value.timebase.numerator,1,192000)||!integer(value.timebase.denominator,1,1001)||value.plan_id!==(row.plan_id??null)||typeof value.source_binding_digest!=='string'||!/^[a-f0-9]{64}$/.test(value.source_binding_digest)||!Array.isArray(value.cues)||value.cues.length>2000||!Array.isArray(value.warnings)||value.warnings.length>value.cues.length*2)return invalid();
 const ids=new Set<string>();let previous=-1,previousEnd=-1;
 for(const cue of value.cues){
  if(!object(cue)||!text(cue.id,1,240)||ids.has(cue.id)||!integer(cue.start_tick,0)||!integer(cue.end_tick,1)||cue.end_tick<=cue.start_tick||cue.start_tick<previous||!text(cue.text,1,10000)||!cue.text.trim()||/[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(cue.text)||/\n\s*\n/.test(cue.text)||!(cue.segment_id===null||text(cue.segment_id,0,240))||!text(cue.overlap_reason,0,500)||(cue.start_tick<previousEnd&&!cue.overlap_reason.trim()))return invalid();
  ids.add(cue.id);previous=cue.start_tick;previousEnd=Math.max(previousEnd,cue.end_tick);
 }
 for(const warning of value.warnings){
  if(!object(warning)||!ids.has(warning.cue_id)||!['READING_SPEED_HEURISTIC','LONG_LINE_HEURISTIC'].includes(warning.code)||('boundary' in warning&&!text(warning.boundary,1,240)))return invalid();
 }
 // Only original cue fields cross the local replacement boundary.
 return {...value,cues:value.cues.map(cueFields),warnings:value.warnings.map(w=>({cue_id:w.cue_id,code:w.code}))};
}

type Props={client:ExperimentalClient;row:CaptionTrack;cues:CaptionCue[];binding:string;disabled:boolean;dirty:boolean;draftEpoch:{current:number};admissionEpoch:{current:number};replace:(cues:CaptionCue[],version:number)=>void};
export function CaptionHistory({client,row,cues,binding,disabled,dirty,draftEpoch,admissionEpoch,replace}:Props) {
 const api=useMemo(()=>voiceSubtitleClient(client),[client]);
 const alive=useRef(true),owner=useRef({binding,client}),selection=useRef(0),requestEpoch=useRef(0),pending=useRef<object|null>(null);
 const [busyTicket,setBusyTicket]=useState<object|null>(null),[error,setError]=useState<unknown>(),[selected,setSelected]=useState('');
 const [page,setPage]=useState<{owner:object;value:CaptionHistoryPage}|null>(null),[preview,setPreview]=useState<{owner:object;selection:number;value:CaptionHistoryPreview}|null>(null);
 if(owner.current.binding!==binding||owner.current.client!==client){owner.current={binding,client};pending.current=null;}
 const capturedOwner=owner.current,capturedSelection=selection.current,capturedDraft=draftEpoch.current,capturedAdmission=admissionEpoch.current,capturedRequest=requestEpoch.current;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;pending.current=null;};},[]);
 const scopeActive=()=>alive.current&&!disabled&&owner.current===capturedOwner&&selection.current===capturedSelection&&draftEpoch.current===capturedDraft&&admissionEpoch.current===capturedAdmission;
 const active=()=>scopeActive()&&requestEpoch.current===capturedRequest;
 const busy=busyTicket!==null&&pending.current===busyTicket;
 const validPage=page?.owner===capturedOwner&&!disabled?page.value:null;
 const validPreview=preview?.owner===capturedOwner&&preview.selection===capturedSelection&&!disabled?preview.value:null;
 const equal=!!validPreview&&JSON.stringify(validPreview.cues)===JSON.stringify(cues.map(cueFields));
 const load=async(before?:number)=>{
  if(!active()||pending.current)return;
  const request=++requestEpoch.current,ticket={};pending.current=ticket;setBusyTicket(ticket);setError(undefined);setPreview(null);setPage(null);setSelected('');
  const current=()=>scopeActive()&&requestEpoch.current===request&&pending.current===ticket;
  try{const value=await api.captionHistory(row,before);if(current())setPage({owner:capturedOwner,value:pageResponse(value,row,before)});}
  catch(value){if(current())setError(value);}
  finally{if(pending.current===ticket){pending.current=null;if(alive.current)setBusyTicket(null);}}
 };
 const read=async()=>{
  if(!active()||pending.current||!validPage||!validPage.items.some(item=>String(item.version)===selected))return;
  const request=++requestEpoch.current,ticket={};pending.current=ticket;setBusyTicket(ticket);setError(undefined);setPreview(null);
  const current=()=>scopeActive()&&requestEpoch.current===request&&pending.current===ticket;
  try{const version=Number(selected),value=await api.historyPreview(row,version);if(current())setPreview({owner:capturedOwner,selection:capturedSelection,value:previewResponse(value,row,version)});}
  catch(value){if(current())setError(value);}
  finally{if(pending.current===ticket){pending.current=null;if(alive.current)setBusyTicket(null);}}
 };
 return <section aria-label="字幕历史恢复"><h4>字幕历史</h4><p>只读预览旧字幕；确认后仅替换本地输入，再使用原保存操作创建新版本。不会恢复历史审批或处理任务权限。</p>
 <Button disabled={disabled||busy} onClick={()=>void load()}>读取字幕历史</Button>
 {busy&&<p role="status">正在读取字幕历史…</p>}
 {!!error&&(error instanceof HistoryResponseError?<StatusMessage tone="error">{error.message}</StatusMessage>:<ErrorMessage error={error}/>)}
 {(page||preview)&&!validPage&&<StatusMessage tone="warning">字幕输入、版本或来源已变化，旧历史列表和预览已失效；本地输入仍保留。</StatusMessage>}
 {validPage&&<><p>当前字幕 {row.id} · v{row.version}</p>
 {!validPage.items.length?<EmptyState title="暂无旧字幕版本" detail="当前字幕没有可供预览的历史记录。"/>:<Field label="字幕历史版本"><select disabled={disabled} value={selected} onChange={event=>{if(!active())return;selection.current++;pending.current=null;setBusyTicket(null);setSelected(event.target.value);setPreview(null);setError(undefined);}}><option value="">选择旧版本</option>{validPage.items.map(item=><option key={item.version} value={item.version}>v{item.version} · {item.cue_count} 条 · {item.status} · {item.timing_origin} · {item.updated_at}</option>)}</select></Field>}
 <Button disabled={disabled||busy||!selected} onClick={()=>void read()}>预览所选历史字幕</Button>
 {validPage.has_more&&<Button disabled={disabled||busy} onClick={()=>void load(validPage.next_before_version!)}>读取更早字幕历史</Button>}
 </>}
 {validPreview&&<section aria-label="字幕历史只读预览"><p>历史 v{validPreview.history_version} · {validPreview.cues.length} 条字幕 · 目标 v{row.version}</p>
 <ol aria-label="历史字幕预览行">{validPreview.cues.map(cue=><li key={cue.id}>{cue.start_tick} → {cue.end_tick} tick · {cue.text}</li>)}</ol>
 {!validPreview.cues.length&&<p>此历史版本没有字幕行；替换将清空本地字幕。</p>}
 {!!validPreview.warnings.length&&<Details label="历史字幕读速 / 行长提示" value={validPreview.warnings}/>}
 {equal?<StatusMessage>历史字幕与本地字幕一致，无需替换；现有来源标记和拆分输入保持不变。</StatusMessage>:<><StatusMessage tone="warning">{dirty?'将替换全部本地字幕，包括尚未保存的修改及拆分输入。':'将替换全部本地字幕。'}确认后尚未保存，请核对后使用“保存字幕版本”创建新版本。</StatusMessage>
 <Button disabled={disabled||busy} onClick={()=>{if(!active()||!validPreview||equal||preview?.owner!==owner.current||preview.selection!==selection.current)return;selection.current++;pending.current=null;setPreview(null);setError(undefined);replace(validPreview.cues.map(cueFields),validPreview.history_version);}}>确认用历史替换本地字幕（尚未保存）</Button></>}
 </section>}
 </section>;
}
