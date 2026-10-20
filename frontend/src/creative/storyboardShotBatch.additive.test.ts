import {expect,it} from 'vitest';
import {newDocument,newScene,newShot,type CreativeInput} from './types';
import {previewStoryboardShotBatch,STORYBOARD_SHOT_BATCH_FIELDS} from './storyboardShotBatch';
const fixture=():CreativeInput=>({...newDocument('STORYBOARD'),title:'Batch',source_independent:true,source_chapter_ids:['source'],scenes:[{...newScene(1),id:'scene'},{...newScene(2),id:'other'}],shots:[{...newShot(1,'scene'),id:'one',frame_prompt:'keep frame',duration_seconds:7,director_note_ids:['original-note'],video_generation_hint:'keep hint',continuity:{characters:'A',outfit:'coat',environment:'room',camera:'left',next_shot_id:'two'}},{...newShot(2,'scene'),id:'two',sound:'keep sound'},{...newShot(3,'other'),id:'three'}]});
it.each(STORYBOARD_SHOT_BATCH_FIELDS)('updates only selected $key values and preserves all original identities and authored fields',({key})=>{
 const source=fixture(),before=structuredClone(source),planned=previewStoryboardShotBatch(source,'scene',['two','one'],key,'作者自定值 🐈');
 expect(planned.changedCount).toBe(2);expect(planned.rows.map(row=>row.id)).toEqual(['one','two']);
 expect(planned.draft).toEqual({...before,shots:[{...before.shots[0],[key]:'作者自定值 🐈'},{...before.shots[1],[key]:'作者自定值 🐈'},before.shots[2]]});expect(source).toEqual(before);
});
it.each(['wrong mode','unknown scene','duplicate scene','unknown target','cross scene','duplicate target','duplicate source','no target','empty value','blank value','long value','unsupported field','too many shots'])('refuses %s atomically',mode=>{
 const source=fixture();let scene='scene',selected=['one'],value='WIDE',field='shot_size';
 if(mode==='wrong mode')source.mode='DIRECTOR';if(mode==='unknown scene')scene='missing';if(mode==='duplicate scene')source.scenes.push({...source.scenes[0]});if(mode==='unknown target')selected=['missing'];if(mode==='cross scene')selected=['one','three'];if(mode==='duplicate target')selected=['one','one'];if(mode==='duplicate source')source.shots[1].id='one';if(mode==='no target')selected=[];if(mode==='empty value')value='';if(mode==='blank value')value=' \t\n';if(mode==='long value')value='🐈'.repeat(81);if(mode==='unsupported field')field='frame_prompt';if(mode==='too many shots')source.shots=Array.from({length:201},(_,i)=>({...newShot(i+1,'scene'),id:`shot${i}`}));
 const before=structuredClone(source);expect(()=>previewStoryboardShotBatch(source,scene,selected,field as any,value)).toThrow();expect(source).toEqual(before);
});
it('uses the original 80 Unicode-character boundary and preserves exact text instead of trimming it',()=>{const source=fixture(),value='🐈'.repeat(80);expect(previewStoryboardShotBatch(source,'scene',['one'],'camera_motion',value).draft.shots[0].camera_motion).toBe(value);expect(previewStoryboardShotBatch(source,'scene',['one'],'camera_motion',' PAN ').draft.shots[0].camera_motion).toBe(' PAN ');});
it('keeps no-op rows visible but does not manufacture a changed draft',()=>{const source=fixture(),plan=previewStoryboardShotBatch(source,'scene',['one','two'],'shot_size','MEDIUM');expect(plan.changedCount).toBe(0);expect(plan.rows).toHaveLength(2);expect(plan.draft).toBe(source);});
