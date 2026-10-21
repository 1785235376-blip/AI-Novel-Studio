import {checkedCanvasVideoTaskCommand,compileCanvasVideoTimeline,type CanvasVideoTaskCommand} from '../canvasVideoTrimTask';
import {checkedTimelineRow,type StudioTimelineRow} from '../studioTimelineTypes';

export type SavedVideoDraftRow=StudioTimelineRow & {
  canvas_video_draft?:CanvasVideoTaskCommand;
  canvas_video_draft_digest?:string;
};
export type SavedVideoDraftView={id:string;title:string;version:number;requestId:string;parentJobId:string;parentJobVersion:number;
  sourceId:string;sourceVersion:number;canvasId:string;canvasVersion:number;cardId:string;inMs:number;outMs:number;audio:'包含首音轨'|'静音（明确关闭）'|'静音（原请求未指定）'};
const canonical=(value:unknown)=>JSON.stringify(value,(_key,item)=>item&&typeof item==='object'&&!Array.isArray(item)
  ?Object.fromEntries(Object.entries(item).sort(([a],[b])=>a.localeCompare(b))):item);

/** The original DTO parsers remain authoritative; historical/detached pins are never offered. */
export function savedCanvasVideoDraftView(value:StudioTimelineRow):SavedVideoDraftView|undefined{
  try{
    const row=value as SavedVideoDraftRow,base=checkedTimelineRow(value),command=checkedCanvasVideoTaskCommand(row.canvas_video_draft);
    if(!command.derived_from||typeof row.canvas_video_draft_digest!=='string'||!/^[a-f0-9]{64}$/.test(row.canvas_video_draft_digest)
      ||command.timeline_snapshot.id!==base.id||command.timeline_snapshot.version!==base.version
      ||command.timeline_snapshot.digest!==base.timeline_digest
      ||canonical(base.timeline)!==canonical(compileCanvasVideoTimeline(command.source_snapshots[0],command.parameters)))return;
    return {id:base.id,title:base.title,version:base.version,requestId:command.request_id,parentJobId:command.derived_from.job_id,
      parentJobVersion:command.derived_from.job_version,sourceId:command.source_snapshots[0].id,sourceVersion:command.source_snapshots[0].version,
      canvasId:command.canvas_return.canvas_id,canvasVersion:command.canvas_return.canvas_version,cardId:command.canvas_return.card_id,
      inMs:command.parameters.in_ms,outMs:command.parameters.out_ms,
      audio:command.parameters.include_audio===true?'包含首音轨':command.parameters.include_audio===false?'静音（明确关闭）':'静音（原请求未指定）'};
  }catch{return;}
}
