import { segment, type ExperimentalClient } from './api';
import type { CaptionCue, CaptionTrack } from './voiceSubtitleClient';
import { previewCaptionTimingOffset } from './captionTimingOffset';
export type RecognitionOperation='ASR'|'FORCED_ALIGNMENT';
export type RecognitionCatalog={adapters:{adapter_id:string;version:string;operations:RecognitionOperation[]}[]};
export type RecognitionTask={id:string;version:number;status:string;caption_id:string;caption_version:number;operation:RecognitionOperation;adapter_id:string;preview_digest?:string;recovery_required:boolean;applied_caption_version?:number;result?:{cues:CaptionCue[];timing_origin:string}};
const object=(value:unknown):value is Record<string,any>=>!!value&&typeof value==='object'&&!Array.isArray(value);
const id=(value:unknown,max=240):value is string=>typeof value==='string'&&value.length>0&&value.length<=max;
const integer=(value:unknown):value is number=>Number.isSafeInteger(value)&&Number(value)>0;
const hash=(value:unknown):value is string=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const invalid=():never=>{throw new Error('字幕识别回执与原来源不一致，请重新核对。');};
export function recognitionCatalog(value:unknown):RecognitionCatalog{
 if(!object(value)||value.schema!=='ai-novel-subtitle-processing/1'||value.owner!=='subtitle_timeline_v2'||value.privacy!=='LOCAL_ONLY'||!Array.isArray(value.adapters)||value.adapters.length>200||!Array.isArray(value.operations))return invalid();
 const available=new Set(value.operations.filter((row:any)=>object(row)&&row.status==='CONTRACT_VERIFIED').map((row:any)=>row.operation));
 const adapters=value.adapters.filter((row:any)=>object(row)&&row.local===true&&row.verification==='CONTRACT_VERIFIED'&&id(row.adapter_id,160)&&id(row.version,160)&&Array.isArray(row.operations)).map((row:any)=>({adapter_id:row.adapter_id,version:row.version,operations:row.operations.filter((op:any)=>(op==='ASR'||op==='FORCED_ALIGNMENT')&&available.has(op))})).filter((row:any)=>row.operations.length);
 if(new Set(adapters.map((row:any)=>row.adapter_id)).size!==adapters.length)return invalid();return {adapters};
}
export function recognitionTask(value:unknown,row:CaptionTrack,allowAppliedNext=false):RecognitionTask{
 if(!object(value)||!id(value.id)||!integer(value.version)||!integer(value.caption_version)||!['QUEUED','RUNNING','NEEDS_REVIEW','APPROVED','REJECTED','FAILED','CANCELLED','INTERRUPTED','NOT_CONFIGURED'].includes(value.status)||value.stale||value.content_withheld||!['ASR','FORCED_ALIGNMENT'].includes(value.operation)||value.verification!=='CONTRACT_VERIFIED'||value.caption_id!==row.id||!id(value.adapter_id,160)||!object(value.asset_snapshot)||value.asset_snapshot.version!==row.asset_snapshot?.version||value.asset_snapshot.digest!==row.asset_snapshot?.digest||!hash(value.asset_snapshot.digest))return invalid();
 const applied=value.applied_caption_version;
 if(applied!==undefined&&(!integer(applied)||value.status!=='APPROVED'||applied!==value.caption_version+1))return invalid();
 const effective=applied??value.caption_version;
 if(effective!==row.version&&!(allowAppliedNext&&value.status==='APPROVED'&&value.caption_version===row.version&&applied===row.version+1))return invalid();
 if(value.preview_digest!=null&&!hash(value.preview_digest))return invalid();
 let result:RecognitionTask['result'];
 if(value.result){const r=value.result;if(!object(r)||!Array.isArray(r.cues)||!r.cues.length||r.cues.length>2000||r.cues.some((cue:any)=>!object(cue)||cue.segment_id!==null||typeof cue.text!=='string')||r.cues.reduce((sum:number,cue:any)=>sum+cue.text.length,0)>200000||r.cues.reduce((sum:number,cue:any)=>sum+Array.from(cue.text).length,0)>100000||r.alignment_quality!=='NOT_RUN'||r.timing_origin!==(value.operation==='ASR'?'MODEL_SEGMENT_TIMESTAMPS':'MFA_WORD_INTERVALS'))return invalid();
  result={cues:previewCaptionTimingOffset(row,r.cues,'all','0').cues.map(cue=>({id:cue.id,start_tick:cue.start_tick,end_tick:cue.end_tick,text:cue.text,segment_id:null,overlap_reason:cue.overlap_reason})),timing_origin:r.timing_origin};}
 if(['NEEDS_REVIEW','APPROVED'].includes(value.status)&&(!result||!hash(value.preview_digest)))return invalid();
 if(value.status==='APPROVED'&&applied===undefined)return invalid();
 return {id:value.id,version:value.version,status:value.status,caption_id:value.caption_id,caption_version:value.caption_version,adapter_id:value.adapter_id,operation:value.operation,recovery_required:value.recovery_required===true,...(hash(value.preview_digest)?{preview_digest:value.preview_digest}:{}),...(applied?{applied_caption_version:applied}:{}),...(result?{result}:{})};
}
export const captionRecognitionClient=(client:ExperimentalClient)=>({
 catalog:async()=>recognitionCatalog(await client.get('/subtitle-timeline/processing/catalog')),
 tasks:async(row:CaptionTrack)=>{const value=await client.get('/subtitle-timeline/processing/tasks');if(!object(value)||!Array.isArray(value.items)||value.items.length>200)return invalid();const tasks=value.items.filter((task:any)=>object(task)&&task.caption_id===row.id&&(task.applied_caption_version??task.caption_version)===row.version&&!task.stale&&!task.content_withheld&&['ASR','FORCED_ALIGNMENT'].includes(task.operation)&&task.verification==='CONTRACT_VERIFIED').map((task:any)=>recognitionTask(task,row));if(new Set(tasks.map((task:RecognitionTask)=>task.id)).size!==tasks.length)return invalid();return tasks;},
 queue:async(row:CaptionTrack,adapter:string,operation:RecognitionOperation,transcript:string)=>{if(operation==='ASR'&&transcript||operation==='FORCED_ALIGNMENT'&&(!transcript.trim()||Array.from(transcript).length>100000))return invalid();const task=recognitionTask(await client.post('/subtitle-timeline/processing/tasks',{caption_id:row.id,expected_caption_version:row.version,adapter_id:adapter,operation,transcript}),row);if(task.adapter_id!==adapter||task.operation!==operation||!['QUEUED','NOT_CONFIGURED'].includes(task.status))return invalid();return task;},
 action:async(row:CaptionTrack,task:RecognitionTask,action:string)=>{const next=recognitionTask(await client.post(`/subtitle-timeline/processing/tasks/${segment(task.id)}/${action}`,{expected_version:task.version,...(['approve','reject'].includes(action)?{preview_digest:task.preview_digest}:{})}),row,action==='approve');const states:Record<string,string[]>={execute:['NEEDS_REVIEW','FAILED','CANCELLED'],cancel:['CANCELLED'],recover:['INTERRUPTED'],resume:['QUEUED'],approve:['APPROVED'],reject:['REJECTED']};if(next.id!==task.id||next.adapter_id!==task.adapter_id||next.operation!==task.operation||next.version<=task.version||!states[action]?.includes(next.status))return invalid();return next;},
});
