import {expect,it} from 'vitest';
import native from './canvasVideoTrimTask.testFixtures';
import {buildStudioExecutionRecipeView} from './studioExecutionRecipeView';
import type {ProductionRecipe} from './studioProductionClient';
const view=(recipe:ProductionRecipe)=>buildStudioExecutionRecipeView({recipe,operationId:'m9.timeline.multitrack',current:true});
it('explains only the actual single-clip Timeline mapping and preserves execution uncertainty',()=>{
 const input=structuredClone(native.preview.execution_recipe),before=JSON.stringify(input),result=view(input as ProductionRecipe);
 expect(result.visibility).toBe('visible');expect(result.steps).toHaveLength(1);expect(result.steps[0].inputs).toEqual([
  {name:'in_ms',type:'INT',source:null,component:null,recordedValue:1000},{name:'out_ms',type:'INT',source:null,component:null,recordedValue:1600},
  {name:'width',type:'INT',source:null,component:null,recordedValue:640},{name:'height',type:'INT',source:null,component:null,recordedValue:360},
  {name:'fps',type:'INT',source:null,component:null,recordedValue:25},{name:'include_audio',type:'BOOLEAN',source:null,component:null,recordedValue:false},
  {name:'video_bitrate_kbps',type:'INT',source:null,component:null,recordedValue:400},{name:'audio_bitrate_kbps',type:'INT',source:null,component:null,recordedValue:96},
  {name:'crf',type:'INT',source:null,component:null,recordedValue:23}]);
 expect(result.steps[0].outputs).toEqual(['VIDEO_H264_MP4']);expect(result.notes.join(' ')).toContain('配方不含逐步骤执行回执');
 expect(result.notes.join(' ')).toContain('不保留源音轨');expect(JSON.stringify(input)).toBe(before);
});
it.each(['include_audio','extra clip','different size','different profile','string range','invalid pin'])('does not explain unsupported video mapping: %s',mode=>{
 const recipe:any=structuredClone(native.preview.execution_recipe),clip=recipe.timeline.tracks[0].clips[0];
 if(mode==='include_audio')clip.include_audio=true;if(mode==='extra clip')recipe.timeline.tracks[0].clips.push(structuredClone(clip));
 if(mode==='different size')recipe.timeline.width=1280;if(mode==='different profile')recipe.export_profile.preset='DELIVERY_MP4';
 if(mode==='string range')clip.in_ms='1000';if(mode==='invalid pin')clip.source_snapshot.digest='invalid';
 expect(view(recipe)).toMatchObject({visibility:'hidden',steps:[]});
});
