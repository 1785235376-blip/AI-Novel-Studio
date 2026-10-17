import { checkedTimelineWaveform, type TimelineWaveform } from './studioTimelineWaveformTypes';
import type { StudioTimelineDraft, StudioTimelineRow, StudioTimelineSource } from './studioTimelineTypes';
export type TimelineMeasuredBound={snapshot:StudioTimelineSource;frames:number;sampleRate:number};
export const measuredBoundKey=(pin:StudioTimelineSource)=>JSON.stringify([pin.id,pin.asset_kind,pin.version,pin.digest]);
export function measuredBoundFromWaveform(value:TimelineWaveform,source:StudioTimelineRow):TimelineMeasuredBound{
 const checked=checkedTimelineWaveform(value,source,value.clip_id);
 return {snapshot:{...checked.source_snapshot},frames:checked.frame_count,sampleRate:checked.sample_rate};
}
/** Only changed/new media ranges are checked. Unknown sources and existing
 * untouched author input are never silently clamped, repaired or declared valid. */
export function changedRangeBeyondMeasurement(previous:StudioTimelineDraft,next:StudioTimelineDraft,bounds:readonly TimelineMeasuredBound[]):string|undefined{
 const known=new Map(bounds.map(bound=>[measuredBoundKey(bound.snapshot),bound]));
 const before=new Map(previous.timeline.tracks.flatMap(track=>track.clips.map(clip=>[clip.id,clip] as const)));
 for(const track of next.timeline.tracks)for(const clip of track.clips){
  if(clip.source_snapshot.asset_kind==='image')continue;
  const old=before.get(clip.id),key=measuredBoundKey(clip.source_snapshot);
  if(old&&measuredBoundKey(old.source_snapshot)===key&&old.in_ms===clip.in_ms&&old.out_ms===clip.out_ms)continue;
  const bound=known.get(key);if(!bound||!Number.isSafeInteger(clip.out_ms))continue;
  if(clip.out_ms*bound.sampleRate>bound.frames*1000)return clip.id;
 }
 return undefined;
}
