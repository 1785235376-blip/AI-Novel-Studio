import type { StudioAsset } from './studioClient';
import { timelineSourceState, type StudioTimeline, type StudioTimelineSource } from './studioTimelineTypes';
import type { TimelineSourceIntent } from './studioTimelineSourceEditContract';
const object=(value:unknown):value is Record<string,unknown>=>!!value&&typeof value==='object'&&!Array.isArray(value);
const keys=(value:Record<string,unknown>,allowed:string[])=>Object.keys(value).length===allowed.length&&Object.keys(value).every(key=>allowed.includes(key));
/** Translate the rail's descriptor into the existing source inspector's unsent intent. */
export function nleSourceReplacementIntent(timeline:StudioTimeline, selected:readonly string[], assets:StudioAsset[], payload:unknown):TimelineSourceIntent {
  if(!object(payload)||!keys(payload,['op','clip_id','changes'])||payload.op!=='clip.update'||typeof payload.clip_id!=='string'||!object(payload.changes)||!keys(payload.changes,['source_snapshot']))throw new Error('素材替换只接收原片段与确切素材快照。');
  const source=payload.changes.source_snapshot;
  if(!object(source)||!keys(source,['id','kind','asset_kind','version','digest'])||typeof source.id!=='string'||source.kind!=='ASSET'||!['image','video','audio'].includes(String(source.asset_kind))||!Number.isSafeInteger(source.version)||Number(source.version)<1||typeof source.digest!=='string'||!/^[a-f0-9]{64}$/.test(source.digest))throw new Error('素材快照字段无效，请重新选择当前正式素材。');
  const first=timeline.tracks.flatMap(track=>track.clips.map(clip=>({track,clip}))).find(row=>selected.includes(row.clip.id));
  if(!first||first.clip.id!==payload.clip_id||first.track.locked)throw new Error('请重新选择当前可编辑的原片段。');
  const pin=source as unknown as StudioTimelineSource;
  if(timelineSourceState(pin,assets)!=='CURRENT'||(first.track.kind==='AUDIO'?pin.asset_kind!=='audio':pin.asset_kind==='audio'||timeline.schema_version!==2&&pin.asset_kind==='image'))throw new Error('所填素材版本不可用、已变化或与轨道不兼容。');
  if((['id','kind','asset_kind','version','digest'] as const).every(key=>first.clip.source_snapshot[key]===pin[key]))throw new Error('来源没有变化，无需替换。');
  return {mode:'REPLACE',asset_id:pin.id,track_id:first.track.id,clip_id:first.clip.id,start_ms:first.clip.start_ms,
    in_ms:first.clip.in_ms,out_ms:first.clip.out_ms,include_audio:pin.asset_kind==='video'&&first.clip.include_audio===true};
}
