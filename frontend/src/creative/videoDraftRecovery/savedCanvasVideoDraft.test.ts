import {expect,it} from 'vitest';
import {savedDraftFixture} from './savedDraft.testFixtures';
import {savedCanvasVideoDraftView} from './savedCanvasVideoDraft';
it.each([undefined,false,true])('shows only original checked input metadata with audio %s',audio=>{
 const row=savedDraftFixture(undefined,audio),before=structuredClone(row),view=savedCanvasVideoDraftView(row);
 expect(view).toMatchObject({id:row.id,version:1,inMs:1000,outMs:1600,parentJobId:'original-failed-job',sourceId:'video-source',cardId:'original-card'});
 expect(view?.audio).toBe(audio===true?'包含首音轨':audio===false?'静音（明确关闭）':'静音（原请求未指定）');expect(row).toEqual(before);
});
it.each(['missing','digest','parent','self-version','self-id','self-digest','timeline','parameters','provider','proof','unsafe-version','unknown-origin'])('hides invalid or historical input %s',kind=>{
 const row=savedDraftFixture() as any;
 if(kind==='missing')delete row.canvas_video_draft;
 if(kind==='digest')row.canvas_video_draft_digest='unknown';
 if(kind==='parent')delete row.canvas_video_draft.derived_from;
 if(kind==='self-version')row.version++;
 if(kind==='self-id')row.id='another-timeline';
 if(kind==='self-digest')row.timeline_digest='c'.repeat(64);
 if(kind==='timeline')row.timeline.duration_ms+=40;
 if(kind==='parameters')row.canvas_video_draft.parameters.out_ms=1601;
 if(kind==='provider')row.canvas_video_draft.provider_id='cloud';
 if(kind==='proof')row.canvas_video_draft.proof={authorized:true};
 if(kind==='unsafe-version')row.canvas_video_draft.derived_from.job_version=2**53;
 if(kind==='unknown-origin')row.canvas_video_draft.derived_from.secret='never-display';
 expect(savedCanvasVideoDraftView(row)).toBeUndefined();
});
it('does not project arbitrary record metadata or caller secrets',()=>{
 const row=savedDraftFixture() as any;row.secret='NEVER_DISPLAY_ME';row.owner_credentials={api_key:'NEVER_DISPLAY_ME'};
 expect(JSON.stringify(savedCanvasVideoDraftView(row))).not.toContain('NEVER_DISPLAY_ME');
});
