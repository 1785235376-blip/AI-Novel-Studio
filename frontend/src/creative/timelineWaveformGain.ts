import { checkedTimelineWaveform, waveformTimelineCoordinate, type TimelineWaveform } from './studioTimelineWaveformTypes';
import { checkedTimelineRow, timelineClipDuration, type StudioTimelineRow } from './studioTimelineTypes';
/** Display estimate only, never rendered PCM or a bound on resampled/mixed output. */
export function projectWaveformGain(value:TimelineWaveform,source:StudioTimelineRow){
 const row=checkedTimelineRow(source),wave=checkedTimelineWaveform(value,row,value.clip_id);
 const track=row.timeline.tracks.find(item=>item.clips.some(clip=>clip.id===wave.clip_id))!;
 const clip=track.clips.find(item=>item.id===wave.clip_id)!;
 const duration=timelineClipDuration(clip),extended=row.timeline.schema_version===2;
 const gainDb=track.gain_db+(extended?(clip.gain_db??0):0),muted=track.muted||(extended&&!!clip.muted);
 const fadeIn=extended?(clip.fade_in_ms??0):0,fadeOut=extended?(clip.fade_out_ms??0):0;
 const amplitude=muted?0:10**(gainDb/20);
 const coordinate=(frame:number)=>{const time=waveformTimelineCoordinate(wave,frame);return Math.max(0,Math.min(duration,time.num/time.den-clip.start_ms));};
 const envelope=(time:number)=>Math.min(1,fadeIn?time/fadeIn:1)*Math.min(1,fadeOut?(duration-time)/fadeOut:1);
 const peaks=wave.peaks.map((peak,index)=>{
  const start=wave.start_frame+index*wave.samples_per_bucket,end=Math.min(wave.end_frame,start+wave.samples_per_bucket);
  const a=coordinate(start),b=coordinate(end);
  // Peak sample positions inside a bucket are unknown. Use the maximum linear
  // envelope within that bucket, rather than claiming a measured post-fade peak.
  const points=[a,b,fadeIn,duration-fadeOut].filter(time=>time>=a&&time<=b);
  return peak*amplitude*Math.max(...points.map(envelope));
 });
 return {peaks,gainDb,muted,fadeIn,fadeOut,aboveUnity:peaks.filter(peak=>peak>1).length,
  method:'SOURCE_BUCKET_PEAK_TIMES_MAX_LINEAR_ENVELOPE' as const};
}
