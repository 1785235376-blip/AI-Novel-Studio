import { segment, type ExperimentalClient } from './api';
import type { CaptionTrack } from './voiceSubtitleClient';
export type BurnCatalog = { adapters:{adapter_id:string;version:string;local:true;verification:'CONTRACT_VERIFIED';operations:string[]}[] };
export type BurnTask = { id:string;version:number;status:string;caption_id:string;caption_version:number;adapter_id:string;operation:'BURN_IN';verification:'CONTRACT_VERIFIED';asset_snapshot:{version:number;digest:string};preview_digest?:string;recovery_required?:boolean;result?:{bytes:number;sha256:string;media_type:string} };
const object=(value:unknown):value is Record<string,any>=>!!value&&typeof value==='object'&&!Array.isArray(value);
const id=(value:unknown,max=240):value is string=>typeof value==='string'&&value.length>0&&value.length<=max;
const integer=(value:unknown):value is number=>Number.isSafeInteger(value)&&Number(value)>0;
const hash=(value:unknown):value is string=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const invalid=():never=>{throw new Error('字幕压制回执无效，请重新读取原任务。');};
export function burnCatalog(value:unknown):BurnCatalog {
  if(!object(value)||value.schema!=='ai-novel-subtitle-processing/1'||value.owner!=='subtitle_timeline_v2'||value.privacy!=='LOCAL_ONLY'||!Array.isArray(value.adapters)||value.adapters.length>200)return invalid();
  const adapters=value.adapters.filter((row:any)=>object(row)&&row.local===true&&row.verification==='CONTRACT_VERIFIED'&&Array.isArray(row.operations)&&row.operations.includes('BURN_IN'));
  if(adapters.some((row:any)=>!id(row.adapter_id,160)||!id(row.version,160))||new Set(adapters.map((row:any)=>row.adapter_id)).size!==adapters.length)return invalid();
  return {adapters:adapters.map((row:any)=>({adapter_id:row.adapter_id,version:row.version,local:true,verification:'CONTRACT_VERIFIED',operations:['BURN_IN']}))};
}
export function burnTask(value:unknown,row:CaptionTrack):BurnTask {
  if(!object(value)||!id(value.id)||!integer(value.version)||!['QUEUED','RUNNING','NEEDS_REVIEW','APPROVED','REJECTED','FAILED','CANCELLED','INTERRUPTED','NOT_CONFIGURED'].includes(value.status)||value.stale||value.content_withheld||value.operation!=='BURN_IN'||value.verification!=='CONTRACT_VERIFIED'||value.caption_id!==row.id||value.caption_version!==row.version||!id(value.adapter_id,160)||!object(value.asset_snapshot)||value.asset_snapshot.version!==row.asset_snapshot?.version||value.asset_snapshot.digest!==row.asset_snapshot?.digest||!hash(value.asset_snapshot.digest))return invalid();
  if(value.preview_digest!==undefined&&value.preview_digest!==null&&!hash(value.preview_digest))return invalid();
  let result:BurnTask['result'];
  if(value.result){const r=value.result;if(!object(r)||!integer(r.bytes)||r.bytes>8388608||!hash(r.sha256)||!['video/mp4','video/webm'].includes(r.media_type))return invalid();result={bytes:r.bytes,sha256:r.sha256,media_type:r.media_type};}
  if(['NEEDS_REVIEW','APPROVED'].includes(value.status)&&(!result||!hash(value.preview_digest)))return invalid();
  return {id:value.id,version:value.version,status:value.status,caption_id:row.id,caption_version:row.version,adapter_id:value.adapter_id,operation:'BURN_IN',verification:'CONTRACT_VERIFIED',asset_snapshot:{version:value.asset_snapshot.version,digest:value.asset_snapshot.digest},...(hash(value.preview_digest)?{preview_digest:value.preview_digest}:{}),recovery_required:value.recovery_required===true,...(result?{result}:{})};
}
export function burnTasks(value:unknown,row:CaptionTrack):BurnTask[]{if(!object(value)||!Array.isArray(value.items)||value.items.length>200)return invalid();const rows=value.items.filter((task:any)=>object(task)&&task.caption_id===row.id&&task.caption_version===row.version&&!task.stale&&!task.content_withheld&&task.operation==='BURN_IN'&&task.verification==='CONTRACT_VERIFIED').map((task:any)=>burnTask(task,row));if(new Set(rows.map((task:BurnTask)=>task.id)).size!==rows.length)return invalid();return rows;}
export const captionBurnInClient=(client:ExperimentalClient)=>({
  catalog:async()=>burnCatalog(await client.get('/subtitle-timeline/processing/catalog')),
  tasks:async(row:CaptionTrack)=>burnTasks(await client.get('/subtitle-timeline/processing/tasks'),row),
  queue:async(row:CaptionTrack,adapter:string)=>{if(!row.cues.length)return invalid();const task=burnTask(await client.post('/subtitle-timeline/processing/tasks',{caption_id:row.id,expected_caption_version:row.version,adapter_id:adapter,operation:'BURN_IN',transcript:''}),row);if(task.adapter_id!==adapter||!['QUEUED','NOT_CONFIGURED'].includes(task.status))return invalid();return task;},
  action:async(row:CaptionTrack,task:BurnTask,action:string)=>{const next=burnTask(await client.post(`/subtitle-timeline/processing/tasks/${segment(task.id)}/${action}`,{expected_version:task.version,...(['approve','reject'].includes(action)?{preview_digest:task.preview_digest}:{})}),row);const states:Record<string,string[]>={execute:['NEEDS_REVIEW','FAILED','CANCELLED'],cancel:['CANCELLED'],recover:['INTERRUPTED'],resume:['QUEUED'],approve:['APPROVED'],reject:['REJECTED']};if(next.id!==task.id||next.adapter_id!==task.adapter_id||next.version<=task.version||!states[action]?.includes(next.status))return invalid();return next;},
  download:async(task:BurnTask)=>{if(task.status!=='APPROVED'||!task.result)return invalid();const blob=await client.blob(`/subtitle-timeline/processing/tasks/${segment(task.id)}/file?expected_version=${task.version}`);if(!task.result||blob.size!==task.result.bytes||blob.type.split(';')[0]!==task.result.media_type)return invalid();const bytes=await blob.arrayBuffer();const sum=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),byte=>byte.toString(16).padStart(2,'0')).join('');if(sum!==task.result.sha256)return invalid();return blob;},
});
