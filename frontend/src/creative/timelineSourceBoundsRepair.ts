import {checkedTimelineSourceBounds,type TimelineSourceBounds} from './studioTimelineSourceBounds';
import {checkedTimelineDraft,cloneTimeline,type StudioTimelineDraft,type StudioTimelineRow} from './studioTimelineTypes';
/** Explicit local-only shortening; retain placements, source pin and all other tracks. */
export function previewSourceBoundsRepair(draft:StudioTimelineDraft,source:StudioTimelineRow,observation:TimelineSourceBounds){
 checkedTimelineDraft(draft);const proof=checkedTimelineSourceBounds(observation,source,observation.clip_id);
 if(JSON.stringify(draft.timeline)!==JSON.stringify(source.timeline))throw new Error('草稿已改变，请先保存并重新核对源时长。');
 if(proof.within_source)throw new Error('当前范围没有超出实测源长度，无需收短。');
 const next=cloneTimeline(draft),matches=next.timeline.tracks.flatMap(track=>track.clips.filter(clip=>clip.id===proof.clip_id).map(clip=>({track,clip})));
 if(matches.length!==1||matches[0].track.locked)throw new Error('片段或轨道状态已改变，锁定轨道不能修改。');
 const {clip}=matches[0],out=proof.maximum_out_ms;
 if(out<=clip.in_ms||out>=clip.out_ms)throw new Error('没有可保留的正长度范围，请手动调整素材入点。');
 const before=clip.out_ms;clip.out_ms=out;
 // Original speed, fade and transition constraints remain authoritative.
 checkedTimelineDraft(next);
 return {draft:next,clipId:clip.id,before,after:out};
}
