import { captionCommand } from '../nle/timelineOps';
import { checkedTimelineDraft, cloneTimeline, type StudioTimelineDraft } from './studioTimelineTypes';
/** Use the original caption mapper and original complete timeline validator. */
export function applyNleCaptionCommand(draft:StudioTimelineDraft, kind:string, payload:unknown):StudioTimelineDraft {
  if(!['caption.insert','caption.update','caption.remove'].includes(kind)||!payload||typeof payload!=='object'||Array.isArray(payload))throw new Error('字幕编辑指令无效。');
  const body=payload as Record<string,unknown>, allowed=kind==='caption.insert'?['op','caption']:kind==='caption.update'?['op','index','caption']:['op','index'];
  if(body.op!==kind||Object.keys(body).length!==allowed.length||Object.keys(body).some(key=>!allowed.includes(key)))throw new Error('字幕编辑包含原契约之外的字段。');
  const plan=captionCommand(kind.replace('.','-'),{timeline:draft.timeline,...(kind!=='caption.insert'?{index:body.index}:{}),...(kind!=='caption.remove'?{caption:body.caption}:{})});
  if(!plan.ok)throw new Error(plan.message);
  const next=cloneTimeline(draft), operation=plan.payload;
  if(operation.op==='caption.insert')next.timeline.captions.push(cloneTimeline(operation.caption));
  else if(operation.op==='caption.update')next.timeline.captions[operation.index]=cloneTimeline(operation.caption);
  else if(operation.op==='caption.remove')next.timeline.captions.splice(operation.index,1);
  else throw new Error('字幕编辑类型不匹配。');
  return checkedTimelineDraft(next);
}
