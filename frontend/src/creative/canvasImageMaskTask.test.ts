import {afterEach,expect,it,vi} from 'vitest';
import {assertCanvasImageTaskCommand,canvasImageTaskJobMatches,canvasImageTaskSource,captureCanvasImageTask,replaceCanvasImageTaskResult} from './canvasImageTask';
import {cutoutAssets,cutoutCommand,cutoutJob,cutoutHash,cutoutSources} from './studioCpuCutout.testFixtures';
import {CUTOUT_WEBP_OUTPUT,CUTOUT_WEBP_PROFILE} from './studioCutoutContract';
import pngFixture from './fixtures/cpuCutout.mounted.json';
import webpFixture from './fixtures/cpuCutoutWebp.actual.json';
import {studioProductionClient,type MediaCommand,type ProductionJob,type ProductionProvider} from './studioProductionClient';
import type {CanvasViewRecord} from './studioCanvasViewClient';
import type {StudioAsset} from './studioClient';
afterEach(()=>vi.unstubAllGlobals());
const incarnation='file:00000000-0000-4000-8000-000000000001';
function canvasFor(asset:StudioAsset):CanvasViewRecord{return{project_id:asset.novel_id,scope:{mode:'local',novel_id:asset.novel_id},id:'source-canvas',version:3,definition_digest:'c'.repeat(64),
 definition:{schema_version:1,title:'原作品',cards:[{id:'source-card',position:{x:41,y:63},asset:{asset_id:asset.id,version:asset.version,digest:asset.sha256,kind:'image'}},{id:'another-card',position:{x:200,y:300}}],groups:[{id:'original-group',name:'原组',card_ids:['source-card'],collapsed:false}],viewport:{x:17,y:23,zoom:1}},
 reference_states:[{card_id:'source-card',state:'CURRENT_METADATA'}]} as CanvasViewRecord;}
function fixture(bound=true){
 const asset=cutoutAssets()[0],canvas=canvasFor(asset),origin=captureCanvasImageTask(canvas,'source-card',asset,bound?incarnation:undefined),sources=cutoutSources();
 const task={source:structuredClone(sources[0]),isCurrent:()=>true,...(origin.binding?{returnBinding:origin.binding}:{})};
 const command=cutoutCommand();if(origin.binding)command.canvas_return=structuredClone(origin.binding);
 const job=cutoutJob('APPROVED',5,command);job.sources=structuredClone(command.source_snapshots);
 const result={...asset,id:'candidate',version:2,sha256:cutoutHash,filename:'approved.png'};
 return{asset,canvas,origin,task,command,job,result};
}
it.each([false,true])('admits only explicit local CPU cutout with original source then a structural mask pin (bound=%s)',bound=>{
 const f=fixture(bound);expect(()=>assertCanvasImageTaskCommand(f.task,f.command)).not.toThrow();expect(canvasImageTaskJobMatches(f.task,f.job)).toBe(true);
});
it('does not claim the structural mask pin is a verified mask or an AI segmentation capability',()=>{
 const f=fixture(false);f.command.source_snapshots[1]={...f.command.source_snapshots[1],id:'another-structurally-pinned-mask'};
 expect(()=>assertCanvasImageTaskCommand(f.task,f.command)).not.toThrow();
 // Original assets/owner must validate authored-mask provenance, dimensions and access.
});
it('retains local Comfy i2i and its original return binding unchanged',()=>{
 const f=fixture(),command:MediaCommand={...f.command,operation_id:'m5.image.i2i',provider_id:'local',model_id:'sd',prompt:'original author prompt',parameters:{denoising_strength:0.5},source_snapshots:[f.task.source],image_source:f.task.source};
 const provider={operation_id:'m5.image.i2i',provider_id:'local',model_id:'sd',local:true,image_capabilities:{recipe_id:'comfy-sd-checkpoint-v1'}} as ProductionProvider;
 expect(()=>assertCanvasImageTaskCommand(f.task,command,provider)).not.toThrow();const job={...f.job,operation_id:'m5.image.i2i',provider:{provider_id:'local',model_id:'sd',local:true,route_digest:'a'.repeat(64)},command,sources:[f.task.source],execution_recipe:{contract:'studio-execution-recipe/1',operation_id:'m5.image.i2i',adapter:'COMFYUI_BUILTIN_IMAGE',image_recipe_id:'comfy-sd-checkpoint-v1',automatic_fallback:false,recipe_digest:'a'.repeat(64)}} as ProductionJob;
 expect(canvasImageTaskJobMatches(f.task,job)).toBe(true);provider.local=false;expect(()=>assertCanvasImageTaskCommand(f.task,command,provider)).toThrow();
});
it.each(['provider','model','prompt','cloud','wrong operation','missing source','extra source','source swap','changed source','same mask','bad mask kind','bad mask version','bad mask digest','mask extra','request reference marker','image_source','image_references','mask_source','video_frames','storyboard_shot','derived_from','template_ref','unknown field','bad parameter','bad profile','retired target'] as const)('rejects CPU command substitution or implicit capability: %s',kind=>{
 const f=fixture(false),c=f.command as any;
 if(kind==='provider')c.provider_id='local';if(kind==='model')c.model_id='model';if(kind==='prompt')c.prompt='infer mask';if(kind==='cloud')c.allow_cloud=true;if(kind==='wrong operation')c.operation_id='m5.image.t2i';
 if(kind==='missing source')c.source_snapshots.pop();if(kind==='extra source')c.source_snapshots.push({...c.source_snapshots[1],id:'third'});if(kind==='source swap')c.source_snapshots.reverse();if(kind==='changed source')c.source_snapshots[0].version++;
 if(kind==='same mask')c.source_snapshots[1]={...c.source_snapshots[0]};if(kind==='bad mask kind')c.source_snapshots[1].asset_kind='audio';if(kind==='bad mask version')c.source_snapshots[1].version=1.5;if(kind==='bad mask digest')c.source_snapshots[1].digest='unknown';if(kind==='mask extra')c.source_snapshots[1].secret='do-not-read';if(kind==='request reference marker')c.source_snapshots=c.source_snapshots.map((source:unknown)=>({...source as object,reference_only:true}));
 if(['image_source','image_references','mask_source','video_frames','storyboard_shot','derived_from','template_ref'].includes(kind))c[kind]=undefined;
 if(kind==='unknown field')c.provider_url='https://invalid.example';if(kind==='bad parameter')c.parameters={seed:5};if(kind==='bad profile')c.parameters={cutout_output:'PNG'};if(kind==='retired target')f.task.isCurrent=()=>false;
 expect(()=>assertCanvasImageTaskCommand(f.task,c)).toThrow();
});
it('rejects a provider picker object for CPU without silently reusing its route',()=>{const f=fixture(false);expect(()=>assertCanvasImageTaskCommand(f.task,f.command,{local:true} as ProductionProvider)).toThrow();});
it.each(['job source swap','command source swap','both swaps','job source pin','command mask pin','mask proof mismatch','job provider','command provider','job operation','command operation','request','adapter','output profile','mask policy','recipe parameters','fallback','automatic replay','remote compute','recipe contract','recipe digest','proof missing','proof null','proof source','proof mask','proof output','proof dimensions','proof bytes','candidate kind','advanced command'] as const)('does not match a substituted CPU job: %s',kind=>{
 const f=fixture(false),j=f.job as any;
 if(kind==='job source swap')j.sources.reverse();if(kind==='command source swap')j.command.source_snapshots.reverse();if(kind==='both swaps'){j.sources.reverse();j.command.source_snapshots.reverse();}if(kind==='job source pin')j.sources[0].version++;
 if(kind==='command mask pin')j.command.source_snapshots[1].version++;if(kind==='mask proof mismatch'){j.sources[1].digest='e'.repeat(64);j.command.source_snapshots[1].digest='e'.repeat(64);}
 if(kind==='job provider')j.provider={local:true};if(kind==='command provider')j.command.provider_id='local';if(kind==='job operation')j.operation_id='m7.video.i2v';if(kind==='command operation')j.command.operation_id='m5.image.i2i';if(kind==='request')j.request_id='different-request';
 if(kind==='adapter')j.execution_recipe.adapter='COMFYUI_BUILTIN_IMAGE';if(kind==='output profile')j.execution_recipe.output_profile='JPEG';if(kind==='mask policy')j.execution_recipe.mask_policy='INFER_MASK';if(kind==='recipe parameters')j.execution_recipe.parameters={cutout_output:CUTOUT_WEBP_PROFILE};if(kind==='fallback')j.execution_recipe.automatic_fallback=true;if(kind==='automatic replay')j.automatic_replay=true;if(kind==='remote compute')j.remote_compute_may_continue=true;if(kind==='recipe contract')j.execution_recipe.contract='unknown';if(kind==='recipe digest')j.execution_recipe.recipe_digest='unknown';
 if(kind==='proof missing')delete j.processing_proof;if(kind==='proof null')j.processing_proof=null;if(kind==='proof source')j.processing_proof.source_sha256='e'.repeat(64);if(kind==='proof mask')j.processing_proof.mask_sha256='e'.repeat(64);if(kind==='proof output')j.processing_proof.output_sha256='e'.repeat(64);if(kind==='proof dimensions')j.processing_proof.width=1;if(kind==='proof bytes')j.processing_proof.output_bytes=1;
 if(kind==='candidate kind')j.output_candidate.kind='audio';if(kind==='advanced command')j.command.image_source=undefined;
 expect(canvasImageTaskJobMatches(f.task,j)).toBe(false);
});
it.each([undefined,null,{},[],{operation_id:'m5.image.cutout'},{operation_id:'m5.image.cutout',owner:'image',provider:null,command:{}}])('returns false for unknown damaged Job instead of throwing: %j',job=>{expect(()=>canvasImageTaskJobMatches(fixture(false).task,job as ProductionJob)).not.toThrow();expect(canvasImageTaskJobMatches(fixture(false).task,job as ProductionJob)).toBe(false);});
it('returns only the APPROVED CPU result to the original card, preserving group/layout/other cards',()=>{
 const f=fixture(),before=structuredClone(f.canvas),next=replaceCanvasImageTaskResult(f.origin,f.canvas,f.job,f.result);expect(next.cards[0].asset).toEqual({asset_id:f.result.id,version:2,digest:cutoutHash,kind:'image'});expect(next.cards[0].position).toEqual(before.definition.cards[0].position);expect(next.cards[1]).toBe(f.canvas.definition.cards[1]);expect(next.groups).toBe(f.canvas.definition.groups);expect(next.viewport).toBe(f.canvas.definition.viewport);expect(f.canvas).toEqual(before);
});
it.each(['unreviewed','canvas CAS','canvas digest','deleted card','replaced source','scope','incarnation','result digest','result version','result deleted','wrong project'] as const)('refuses CPU adoption when original target or formal review changed: %s',kind=>{
 const f=fixture();if(kind==='unreviewed')f.job.status='AWAITING_REVIEW';if(kind==='canvas CAS')f.canvas.version++;if(kind==='canvas digest')f.canvas.definition_digest='f'.repeat(64);if(kind==='deleted card')f.canvas.definition.cards=[];if(kind==='replaced source')f.canvas.definition.cards[0].asset!.version++;if(kind==='scope')f.canvas.scope={mode:'local',novel_id:'foreign'};if(kind==='incarnation')f.job.command!.canvas_return!.incarnation='file:11111111-1111-4111-8111-111111111111';if(kind==='result digest')f.result.sha256='f'.repeat(64);if(kind==='result version')f.result.version=1;if(kind==='result deleted')f.result.deleted_at='deleted';if(kind==='wrong project')f.job.novel_id='foreign';expect(()=>replaceCanvasImageTaskResult(f.origin,f.canvas,f.job,f.result)).toThrow();
});
it.each([['PNG',pngFixture],['WEBP',webpFixture]] as const)('accepts original captured %s preview and Jobs with a precise card binding through the real SDK',async(_profile,native)=>{
 const source=structuredClone(native.source) as StudioAsset,canvas=canvasFor(source),origin=captureCanvasImageTask(canvas,'source-card',source,incarnation),command={...structuredClone(native.command),canvas_return:origin.binding} as MediaCommand,task={source:canvasImageTaskSource({asset_id:source.id,kind:'image',version:source.version,digest:source.sha256}),returnBinding:origin.binding,isCurrent:()=>true};
 const reply=(value:unknown)=>vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>structuredClone(value)})));
 const client=studioProductionClient(source.novel_id,{sessionToken:''});const preview=structuredClone(native.preview) as any;preview.command.canvas_return=origin.binding;reply(preview);expect(await client.preview(command)).toEqual(preview);
 for(const actual of [native.queued,native.executed,native.approved]){const row=structuredClone(actual) as unknown as ProductionJob;row.command!.canvas_return=origin.binding;reply(row);const decoded=await client.get('image',row.id);expect(canvasImageTaskJobMatches(task,decoded)).toBe(true);}
});

it.each([0,1])('rejects a sparse recorded source array missing slot %s instead of skipping the source',index=>{
 const f=fixture(false);delete f.job.sources[index];expect(f.job.sources.length).toBe(2);expect(canvasImageTaskJobMatches(f.task,f.job)).toBe(false);
});
