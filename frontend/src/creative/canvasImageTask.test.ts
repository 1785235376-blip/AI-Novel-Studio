import { expect, it } from 'vitest';
import { assertCanvasImageTaskCommand, captureCanvasImageTask, replaceCanvasImageTaskResult } from './canvasImageTask';
import type { CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioAsset } from './studioClient';
import type { MediaCommand, ProductionJob, ProductionProvider } from './studioProductionClient';
const digest='a'.repeat(64),outputDigest='b'.repeat(64);
function fixture(){
  const source={asset_id:'original-image',version:2,digest,kind:'image' as const},asset={id:source.asset_id,version:2,sha256:digest,kind:'image',deleted_at:null,manual_mask:null} as StudioAsset;
  const canvas={project_id:'project',id:'canvas',version:3,definition_digest:'c'.repeat(64),definition:{schema_version:1,title:'Original work',cards:[{id:'target',position:{x:41,y:63},asset:source},{id:'other',position:{x:500,y:200},asset:source}],groups:[{id:'group',name:'Work group',card_ids:['target'],collapsed:false}],viewport:{x:17,y:23,zoom:1}},reference_states:[{card_id:'target',state:'CURRENT_METADATA'},{card_id:'other',state:'CURRENT_METADATA'}]} as CanvasViewRecord;
  const command={operation_id:'m5.image.i2i',allow_cloud:false,source_snapshots:[{id:source.asset_id,version:2,digest,kind:'ASSET',asset_kind:'image'}]} as MediaCommand;
  const provider={local:true,image_capabilities:{recipe_id:'comfy-sd-checkpoint-v1'}} as ProductionProvider;
  const job={novel_id:'project',owner:'image',operation_id:'m5.image.i2i',status:'APPROVED',provider:{local:true},command,sources:command.source_snapshots,execution_recipe:{adapter:'COMFYUI_BUILTIN_IMAGE',image_recipe_id:'comfy-sd-checkpoint-v1'},output_candidate:{id:'formal-result',version:1,digest:outputDigest,kind:'image'},approved_asset_version:2} as ProductionJob;
  const result={id:'formal-result',version:2,sha256:outputDigest,kind:'image',deleted_at:null} as StudioAsset;
  const origin=captureCanvasImageTask(canvas,'target',asset),binding={source:command.source_snapshots[0],isCurrent:()=>true};
  return {source,asset,canvas,command,provider,job,result,origin,binding};
}
it('adopts only the captured card even when a different card is selected, preserving original positions/groups/asset data',()=>{
  const f=fixture(),before=structuredClone(f.canvas),next=replaceCanvasImageTaskResult(f.origin,f.canvas,f.job,f.result);
  expect(next.cards[0]).toEqual({...before.definition.cards[0],asset:{asset_id:'formal-result',version:2,digest:outputDigest,kind:'image'}});
  expect(next.cards[1]).toBe(f.canvas.definition.cards[1]);expect(next.groups).toBe(f.canvas.definition.groups);expect(f.canvas).toEqual(before);
});
it.each(['canvas version','canvas digest','source pin','missing target','metadata stale','wrong project','unreviewed','wrong source','wrong result digest','wrong result version'] as const)('rejects unsafe return: %s',kind=>{
  const f=fixture();
  if(kind==='canvas version')f.canvas.version++;
  if(kind==='canvas digest')f.canvas.definition_digest='d'.repeat(64);
  if(kind==='source pin')f.canvas.definition.cards[0].asset!.version++;
  if(kind==='missing target')f.canvas.definition.cards=f.canvas.definition.cards.slice(1);
  if(kind==='metadata stale')f.canvas.reference_states[0].state='STALE';
  if(kind==='wrong project')f.job.novel_id='other-project';
  if(kind==='unreviewed')f.job.status='AWAITING_REVIEW';
  if(kind==='wrong source')f.job.sources=[{...f.job.sources[0],id:'other-image'}];
  if(kind==='wrong result digest')f.result.sha256='e'.repeat(64);
  if(kind==='wrong result version')f.result.version=1;
  expect(()=>replaceCanvasImageTaskResult(f.origin,f.canvas,f.job,f.result)).toThrow();
});
it.each(['retired target','cloud','unknown adapter','other operation','extra input'] as const)('refuses out-of-scope cost before original dispatch: %s',kind=>{
  const f=fixture();
  if(kind==='retired target')f.binding.isCurrent=()=>false;
  if(kind==='cloud')f.provider.local=false;
  if(kind==='unknown adapter')f.provider.image_capabilities!.recipe_id='opaque';
  if(kind==='other operation')f.command.operation_id='m7.video.i2v';
  if(kind==='extra input')f.command.source_snapshots.push({...f.command.source_snapshots[0],id:'extra'});
  expect(()=>assertCanvasImageTaskCommand(f.binding,f.command,f.provider)).toThrow();
});
