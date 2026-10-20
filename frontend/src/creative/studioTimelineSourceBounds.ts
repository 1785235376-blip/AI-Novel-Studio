import {ApiError} from '../api';
import {waveformSelectedClip,type TimelineWaveform} from './studioTimelineWaveformTypes';
import type {StudioTimelineRow} from './studioTimelineTypes';
export {timelineWaveformRequest as timelineSourceBoundsRequest} from './studioTimelineWaveformTypes';
export type TimelineSourceBounds=Pick<TimelineWaveform,'novel_id'|'branch_id'|'timeline_id'|'timeline_version'|'timeline_digest'|'clip_id'|'source_snapshot'|'byte_count'|'frame_count'|'sample_rate'|'channels'|'duration_seconds'|'clip'>&{contract:'studio-timeline-source-bounds/1';status:'MEASURED_PCM16_SOURCE_BOUNDS';scope:'SOURCE_DURATION_ONLY';maximum_out_ms:number;requested_start_frame:number;requested_end_frame:number;within_source:boolean};
function invalid():never{throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'源时长回执与当前片段不一致，请重新核对。'});}
function exact(value:unknown,keys:string[]){if(!value||typeof value!=='object'||Array.isArray(value))invalid();const row=value as Record<string,unknown>;if(Object.keys(row).length!==keys.length||keys.some(k=>!Object.hasOwn(row,k)))invalid();return row;}
function int(value:unknown,min:number,max:number){if(typeof value!=='number'||!Number.isSafeInteger(value)||value<min||value>max)invalid();return value;}
export function checkedTimelineSourceBounds(value:unknown,source:StudioTimelineRow,clipId:string,scope?:{novelId:string;branchId?:string|null}):TimelineSourceBounds{
 const clip=waveformSelectedClip(source,clipId),copy=structuredClone(value),row=exact(copy,['contract','novel_id','branch_id','timeline_id','timeline_version','timeline_digest','clip_id','source_snapshot','byte_count','status','scope','clip','frame_count','sample_rate','channels','duration_seconds','maximum_out_ms','requested_start_frame','requested_end_frame','within_source']);
 if(row.contract!=='studio-timeline-source-bounds/1'||row.status!=='MEASURED_PCM16_SOURCE_BOUNDS'||row.scope!=='SOURCE_DURATION_ONLY'||row.timeline_id!==source.id||row.timeline_version!==source.version||row.timeline_digest!==source.timeline_digest||row.clip_id!==clipId||typeof row.novel_id!=='string'||!row.novel_id||row.branch_id!==null&&typeof row.branch_id!=='string'||scope&&(row.novel_id!==scope.novelId||scope.branchId!==undefined&&row.branch_id!==scope.branchId))invalid();
 const pin=exact(row.source_snapshot,['id','kind','asset_kind','version','digest']);for(const [key,v] of Object.entries(clip.source_snapshot))if(pin[key]!==v)invalid();
 const mapping=exact(row.clip,['in_ms','out_ms','start_ms','speed_num','speed_den']);if(mapping.in_ms!==clip.in_ms||mapping.out_ms!==clip.out_ms||mapping.start_ms!==clip.start_ms||mapping.speed_num!==(clip.speed_num??1)||mapping.speed_den!==(clip.speed_den??1))invalid();
 const bytes=int(row.byte_count,1,8388608),rate=int(row.sample_rate,1,192000),channels=int(row.channels,1,2),frames=int(row.frame_count,1,4194304/channels);if(frames>rate*600||frames*channels*2>bytes)invalid();
 const duration=exact(row.duration_seconds,['num','den']);if(duration.num!==frames||duration.den!==rate)invalid();
 const start=Math.ceil(clip.in_ms*rate/1000),end=Math.ceil(clip.out_ms*rate/1000),within=0<=start&&start<end&&end<=frames;
 if(row.maximum_out_ms!==Math.floor(frames*1000/rate)||row.requested_start_frame!==start||row.requested_end_frame!==end||row.within_source!==within)invalid();
 return copy as TimelineSourceBounds;
}
