import { describe, expect, it } from 'vitest';
import { clipBoundaryNavigation } from './clipBoundaryNavigation';

const source={kind:'ASSET',id:'audio',asset_kind:'audio',version:1,digest:'a'.repeat(64)};
function fixture(){return {schema_version:3,media_kind:'AUDIO',duration_ms:5000,tracks:[
 {id:'one',kind:'AUDIO',order:0,muted:false,gain_db:0,clips:[{id:'a',source_snapshot:source,start_ms:100,in_ms:100,out_ms:700,speed_num:3,speed_den:2}]},
 {id:'two',kind:'AUDIO',order:1,muted:true,locked:true,gain_db:0,clips:[{id:'b',source_snapshot:source,start_ms:500,in_ms:0,out_ms:1500,speed_num:1,speed_den:1}]},
]};}
it('uses the original retimed source duration, merges equal cross-track edges, and does not add unrelated endpoints',()=>{
 const input=fixture(),before=structuredClone(input);const result=clipBoundaryNavigation(input,450);
 expect(result).toMatchObject({ok:true,pointsMs:[100,500,2000],previousMs:100,nextMs:500});expect(input).toEqual(before);
 expect(clipBoundaryNavigation(input,500)).toMatchObject({ok:true,previousMs:100,nextMs:2000});
 expect(clipBoundaryNavigation(input,0)).toMatchObject({ok:true,previousMs:null,nextMs:100});
 expect(clipBoundaryNavigation(input,5000)).toMatchObject({ok:true,previousMs:2000,nextMs:null});
});
it.each([-1,0.5,5001,NaN,Infinity,'500',null])('refuses invalid playhead %s without rounding or clamping',ms=>{
 expect(clipBoundaryNavigation(fixture(),ms).ok).toBe(false);
});
it.each(['malformed','fractional','over-limit','unknown-content'] as const)('keeps the original timeline refusal: %s',fault=>{
 const input=fixture();
 if(fault==='fractional')input.tracks[0].clips[0].out_ms=701;
 if(fault==='over-limit')input.tracks[0].clips=Array.from({length:31},(_,i)=>({...input.tracks[0].clips[0],id:'a'+i}));
 expect(clipBoundaryNavigation(fault==='malformed'?{}:fault==='unknown-content'?{...input,execute:'external'}:input,0).ok).toBe(false);
});
it('uses actual video transition overlap edges and source speed rather than an invented cut midpoint',()=>{
 const result=clipBoundaryNavigation({schema_version:2,duration_ms:3000,width:64,height:64,fps:25,captions:[],tracks:[
 {id:'video',kind:'VIDEO',order:0,muted:false,gain_db:0,clips:[
  {id:'left',source_snapshot:{...source,asset_kind:'video'},start_ms:0,in_ms:100,out_ms:3100,speed_num:3,speed_den:2,x:0,y:0,width:64,height:64,transition_out:{kind:'CROSS_DISSOLVE',to_clip_id:'right',duration_ms:500}},
  {id:'right',source_snapshot:{...source,id:'other',asset_kind:'video'},start_ms:1500,in_ms:0,out_ms:1500,x:0,y:0,width:64,height:64},
 ]}]},1600);
 expect(result).toMatchObject({ok:true,pointsMs:[0,1500,2000,3000],previousMs:1500,nextMs:2000});
});
