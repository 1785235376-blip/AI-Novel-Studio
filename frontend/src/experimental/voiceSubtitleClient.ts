import type { ExperimentalClient, Row } from './api';
import { segment } from './api';
export type Direction = { reviewed_text: string; text_reviewed: boolean; voice_authorized: boolean; emotion: string; speech_rate: number; pause_ms: number; pronunciation_rules: {term: string; pronunciation: string}[] };
export type AudioSegment = Row & {kind: 'NARRATION'|'DIALOGUE';text: string;character_id?:string;profile_id?:string;attribution_status:string;direction?:Direction;locked?:boolean;audio_asset_id?:string;start_ms?:number;end_ms?:number};
export type AudioPlan = Row & {title:string;segments?:AudioSegment[];needs_review_count:number};
export type VoiceCatalog = {plans:AudioPlan[];mixes?:Row[];mixer?:string;profiles:Row[];characters:{id:string;name:string}[];tts:Record<string,unknown>};
export type CaptionCue = {id:string;start_tick:number;end_tick:number;text:string;segment_id:string|null;overlap_reason:string};
export type CaptionTrack = Row & {title?:string;asset_id:string;timebase:{numerator:number;denominator:number};cues:CaptionCue[];media:{duration_seconds:{numerator:number;denominator:number};waveform:{status:string;peaks?:number[]}};warnings:{cue_id:string;code:string}[];speakers:Record<string,{name:string}>};
export function voiceSubtitleClient(client:ExperimentalClient) {
  return {
    voice: (signal?:AbortSignal)=>client.get<VoiceCatalog>('/voice-direction/catalog',signal),
    jobs: (signal?:AbortSignal)=>client.get<{items:Row[]}>('/voice-direction/jobs',signal),
    edit: (plan:AudioPlan,item:AudioSegment,body:Direction&{kind:string;character_id:string|null;profile_id:string|null;attribution_reviewed:boolean})=>client.put<AudioPlan>(`/voice-direction/plans/${segment(plan.id)}/segments/${segment(item.id)}`,{expected_version:plan.version,...body}),
    lock: (plan:AudioPlan,item:AudioSegment)=>client.post<AudioPlan>(`/voice-direction/plans/${segment(plan.id)}/segments/${segment(item.id)}/lock`,{expected_version:plan.version,locked:!item.locked}),
    reorder:(plan:AudioPlan,ids:string[])=>client.post<AudioPlan>(`/voice-direction/plans/${segment(plan.id)}/reorder`,{expected_version:plan.version,segment_ids:ids}),
    queue:(plan:AudioPlan,ids:string[])=>client.post(`/voice-direction/plans/${segment(plan.id)}/queue`,{expected_version:plan.version,segment_ids:ids,approve_selected:true,local_only:true,max_cost:0}),
    jobAction:(job:Row,action:'execute'|'cancel'|'retry'|'approve')=>client.post(`/voice-direction/jobs/${segment(job.id)}/${action}`,action==='approve'?{expected_asset_version:job.asset_version}:{}),
    audio:(job:Row)=>client.blob(`/voice-direction/jobs/${segment(job.id)}/audio`),
    mix:(plan:AudioPlan)=>client.post<Row>(`/voice-direction/plans/${segment(plan.id)}/mix`,{expected_version:plan.version}),
    mixAudio:(mix:Row)=>client.blob(`/voice-direction/mixes/${segment(mix.id)}/audio?expected_version=${mix.version}`),
    reviewMix:(mix:Row,action:'approve'|'reject')=>client.post<Row>(`/audiobook/mixes/${segment(mix.id)}/${action}`,{expected_version:mix.version}),
    captionCatalog:(signal?:AbortSignal)=>client.get<{assets:Row[];plans:AudioPlan[]}>('/subtitle-timeline/catalog',signal),
    tracks:(signal?:AbortSignal)=>client.get<{items:CaptionTrack[]}>('/subtitle-timeline/records',signal),
    createTrack:(body:unknown)=>client.post<CaptionTrack>('/subtitle-timeline/records',body),
    saveCues:(row:CaptionTrack,cues:CaptionCue[])=>client.put<CaptionTrack>(`/subtitle-timeline/records/${segment(row.id)}`,{expected_version:row.version,cues}),
    split:(row:CaptionTrack,cue:CaptionCue,tick:number,left:string,right:string)=>client.post<CaptionTrack>(`/subtitle-timeline/records/${segment(row.id)}/cues/${segment(cue.id)}/split`,{expected_version:row.version,split_tick:tick,left_text:left,right_text:right}),
    merge:(row:CaptionTrack,cue:CaptionCue,next:CaptionCue)=>client.post<CaptionTrack>(`/subtitle-timeline/records/${segment(row.id)}/cues/${segment(cue.id)}/merge`,{expected_version:row.version,next_cue_id:next.id}),
    download:(row:CaptionTrack,format:'srt'|'vtt')=>client.blob(`/subtitle-timeline/records/${segment(row.id)}/file.${format}?expected_version=${row.version}`),
  };
}
export function downloadCaption(blob:Blob,name:string) { const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),0); }
