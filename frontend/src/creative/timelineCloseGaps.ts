import { checkedTimelineDraft, cloneTimeline, timelineClipDuration, type StudioTimelineDraft } from './studioTimelineTypes';
/** Close only uncovered intervals on one original track. Overlap windows stay intact. */
export function previewTimelineCloseGaps(value:StudioTimelineDraft,trackId:string,includeLeading:boolean){
 checkedTimelineDraft(value);
 const draft=cloneTimeline(value);
 const track=draft.timeline.tracks.find(row=>row.id===trackId);
 if(!track||track.locked)throw new Error('请选择当前未锁定的原轨道。');
 if(typeof includeLeading!=='boolean')throw new Error('请明确选择是否关闭开头空隙。');
 const ordered=[...track.clips].sort((a,b)=>a.start_ms-b.start_ms||a.id.localeCompare(b.id));
 const shifts:{clipId:string;before:number;after:number}[]=[],gaps:{start:number;end:number}[]=[];
 let coveredEnd=includeLeading?0:(ordered[0]?.start_ms??0),removed=0;
 for(const clip of ordered){
  const originalStart=clip.start_ms,originalEnd=originalStart+timelineClipDuration(clip);
  if(originalStart>coveredEnd){gaps.push({start:coveredEnd,end:originalStart});removed+=originalStart-coveredEnd;}
  if(removed){clip.start_ms=originalStart-removed;shifts.push({clipId:clip.id,before:originalStart,after:clip.start_ms});}
  coveredEnd=Math.max(coveredEnd,originalEnd);
 }
 // Preserve the authored array order, sources, all other tracks/captions and project duration.
 checkedTimelineDraft(draft);
 return {draft,trackId,removedMs:removed,shifts,gaps};
}
