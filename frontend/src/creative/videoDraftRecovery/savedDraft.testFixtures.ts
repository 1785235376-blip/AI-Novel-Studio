import {compileCanvasVideoTimeline,type CanvasVideoTaskCommand} from '../canvasVideoTrimTask';
import {recoveryFixture,hash} from '../videoTaskRecovery/recovery.testFixtures';
import type {SavedVideoDraftRow} from './savedCanvasVideoDraft';
export function savedDraftFixture(id='saved-video-draft',includeAudio?:boolean):SavedVideoDraftRow{
 const {job}=recoveryFixture(includeAudio),source=job.canvas_video;
 const command:CanvasVideoTaskCommand={...structuredClone(source),request_id:'new-request-'+id,
  timeline_snapshot:{id,version:1,digest:hash('b')},derived_from:{owner:'timeline',job_id:job.id,job_version:job.version,
    request_id:job.request_id,request_digest:job.request_digest,receipt_digest:job.receipt_digest}};
 return {id,title:'本次失败视频派生输入',version:1,timeline_digest:hash('b'),created_at:'',updated_at:'',
  timeline:compileCanvasVideoTimeline(command.source_snapshots[0],command.parameters),canvas_video_draft:command,canvas_video_draft_digest:hash('a')};
}
