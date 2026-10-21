import {afterEach,expect,it,vi} from 'vitest';
import native from './fixtures/canvasAudioTrim.native.json';
import {studioProductionClient,type MediaCommand,type ProductionJob,type ProductionRecipe} from './studioProductionClient';
import {canvasReturnInCommand,sameCanvasReturn} from './studioCanvasReturnBinding';
import {canvasAudioTrimTaskJobMatches} from './canvasAudioTrimTask';
import {buildStudioExecutionRecipeView as studioExecutionRecipeView} from './studioExecutionRecipeView';

const json=(v:unknown)=>new Response(JSON.stringify(v),{headers:{'Content-Type':'application/json'}});
const fresh=():MediaCommand=>({...structuredClone(native.command),parameters:{in_ms:550,out_ms:850},source_snapshots:native.command.source_snapshots.map(s=>({...s}))} as MediaCommand);
afterEach(()=>vi.unstubAllGlobals());
it('decodes the actual native AudioJob preview/create/get/execute/review and its immutable origin',async()=>{
 const client=studioProductionClient(native.canvas.project_id,{sessionToken:''});
 vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit={})=>json(url.endsWith('/preview')?native.preview:url.endsWith('/execute')?native.executed:url.endsWith('/review')?native.approved:init.method==='POST'?native.queued:native.approved)));
 const preview=await client.preview(fresh());expect(sameCanvasReturn(preview.command,fresh())).toBe(true);
 const queued=await client.create(fresh(),preview.preview_digest),executed=await client.execute(queued),approved=await client.review(executed);
 const loaded=await client.get('audio',approved.id);expect(loaded.status).toBe('APPROVED');
 const binding=canvasReturnInCommand(loaded.command)!;
 expect(canvasAudioTrimTaskJobMatches({source:binding.source,returnBinding:binding,isCurrent:()=>true},loaded)).toBe(true);
 expect(executed.media_measurement).toMatchObject({duration_ms:300,sample_rate:48000,channels:2,container:'wav'});
});
it.each(['card_id','canvas_digest','incarnation'])('rejects swapped native audio %s in preview and action receipts',async field=>{
 const client=studioProductionClient(native.canvas.project_id,{sessionToken:''});
 const changed=(value:unknown)=>{const v:any=structuredClone(value);v.command.canvas_return[field]=field==='canvas_digest'?'a'.repeat(64):field==='incarnation'?'file:00000000-0000-0000-0000-000000000001':'other-card';return v;};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>json(changed(url.endsWith('/preview')?native.preview:native.executed))));
 await expect(client.preview(fresh())).rejects.toBeDefined();await expect(client.execute(native.queued as unknown as ProductionJob)).rejects.toBeDefined();
});
it.each(['sample-rate','format','model','cloud','source','project','unknown-null'])('blocks unsupported fresh audio %s before transport',async mode=>{
 const c:any=fresh();if(mode==='sample-rate')c.parameters.sample_rate=48000;if(mode==='format')c.parameters.output_format='WAV';if(mode==='model')c.model_id='model';
 if(mode==='cloud')c.allow_cloud=true;if(mode==='source')c.source_snapshots[0].digest='b'.repeat(64);if(mode==='project')c.canvas_return.project_id='other';if(mode==='unknown-null')c.parameters.unrecognised=null;
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);await expect(studioProductionClient(native.canvas.project_id,{sessionToken:''}).preview(c)).rejects.toBeDefined();expect(fetcher).not.toHaveBeenCalled();
});
it('explains only the known original local WAV mapping, retaining unknown/stale boundaries',()=>{
 const recipe=native.executed.execution_recipe as ProductionRecipe;
 const view=studioExecutionRecipeView({recipe,operationId:'m8.audio.trim',current:true});
 expect(view.visibility).toBe('visible');expect(view.steps[0].inputs.map(i=>i.recordedValue)).toEqual([550,850]);expect(view.notes.join(' ')).toContain('不是可编辑节点图');
 expect(studioExecutionRecipeView({recipe,operationId:'m8.audio.trim',current:false}).state).toBe('stale');
 expect(studioExecutionRecipeView({recipe:{...recipe,adapter:'UNKNOWN'},current:true}).visibility).toBe('hidden');
});

it('keeps projection-only source markers out of fresh audio requests',async()=>{
 const command={...fresh(),source_snapshots:structuredClone(native.queued.command.source_snapshots)} as MediaCommand;
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);await expect(studioProductionClient(native.canvas.project_id,{sessionToken:''}).preview(command)).rejects.toBeDefined();expect(fetcher).not.toHaveBeenCalled();
});

it('explains the recorded original gain/fade mapping without claiming execution',()=>{
 const recipe={...native.executed.execution_recipe,parameters:{in_ms:550,out_ms:850,gain_db:-6,fade_in_ms:100,fade_out_ms:100}} as ProductionRecipe;
 const view=studioExecutionRecipeView({recipe,operationId:'m8.audio.trim',current:true});
 expect(view.visibility).toBe('visible');expect(view.steps[0].inputs.map(i=>[i.name,i.recordedValue])).toEqual([['in_ms',550],['out_ms',850],['gain_db',-6],['fade_in_ms',100],['fade_out_ms',100]]);
 expect(view.message).toContain('执行未验证');
});
