import { validCutoutParameters } from './studioCutoutContract';
import { checkedCanvasAudioTaskEnvelope } from './canvasAudioTaskEnvelope';
import { checkedCanvasVideoTaskJob } from './canvasVideoTrimTask';
import type { ProductionJob } from './studioProductionClient';
import { ApiError } from '../api';
import type { StudioGraphScope } from './studioGraphTypes';
import type { ProductionSource } from './studioProductionClient';

export type CanvasReturnBinding={contract:'studio-canvas-return/1';project_id:string;scope:StudioGraphScope;incarnation:string;
  canvas_id:string;canvas_version:number;canvas_digest:string;card_id:string;source:ProductionSource};
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const id=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(v);
const hex=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const canonical=(v:unknown):string=>JSON.stringify(v,(_k,x)=>object(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
function invalid():never{throw new ApiError({status:422,code:'STUDIO_CANVAS_RETURN_INVALID',message:'原卡片回流来源不完整或已改变；不会猜测其他作品位置。'});}
export function checkedCanvasReturnBinding(value:unknown):CanvasReturnBinding{
  if(!object(value)||Object.keys(value).length!==9||!['contract','project_id','scope','incarnation','canvas_id','canvas_version','canvas_digest','card_id','source'].every(k=>Object.hasOwn(value,k))
    ||value.contract!=='studio-canvas-return/1'||![value.project_id,value.canvas_id,value.card_id].every(id)||!Number.isSafeInteger(value.canvas_version)||(value.canvas_version as number)<1||!hex(value.canvas_digest)
    ||typeof value.incarnation!=='string'||!/^(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value.incarnation))invalid();
  const scope=value.scope,source=value.source;
  if(!object(scope)||Object.keys(scope).some(k=>!['mode','novel_id','workspace_id','project_id','storyline_id','branch_id'].includes(k))||scope.novel_id!==value.project_id
    ||!['local','collaboration'].includes(String(scope.mode))||Object.values(scope).some(v=>v!==null&&(typeof v!=='string'||!v.length||v.length>240))
    ||scope.mode==='collaboration'&&!['workspace_id','storyline_id','branch_id'].every(k=>id(scope[k]))
    ||!object(source)||Object.keys(source).some(k=>!['id','kind','version','digest','asset_kind','reference_only'].includes(k))||!id(source.id)||source.kind!=='ASSET'||!['image','audio'].includes(String(source.asset_kind))||source.asset_kind==='audio'&&source.reference_only!==undefined
    ||!Number.isSafeInteger(source.version)||(source.version as number)<1||!hex(source.digest)||source.reference_only!==undefined&&source.reference_only!==true)invalid();
  return {...structuredClone(value),source:{id:source.id,kind:'ASSET',version:source.version,digest:source.digest,asset_kind:source.asset_kind}} as CanvasReturnBinding;
}
export function canvasReturnInCommand(command:unknown):CanvasReturnBinding|undefined{
  if(!object(command)||!Object.hasOwn(command,'canvas_return'))return;
  const binding=checkedCanvasReturnBinding(command.canvas_return),sources=command.source_snapshots;
  const pin=(v:unknown)=>object(v)&&['id','kind','version','digest','asset_kind'].every(k=>v[k]===(binding.source as unknown as Record<string,unknown>)[k]);
  if(binding.source.asset_kind==='audio'){
    const parameters=checkedCanvasAudioTaskEnvelope(command.parameters,true);
    if(command.operation_id!=='m8.audio.trim'||command.allow_cloud!==false||command.provider_id!=null||command.model_id!=null||command.prompt!==''
      ||!Array.isArray(sources)||sources.length!==1||!pin(sources[0])||!parameters
      ||['image_source','image_references','mask_source','video_reference','video_frames','storyboard_shot','storyboard_speech','audio_profile','image_layers'].some(k=>Object.hasOwn(command,k)))invalid();
  }else if(command.operation_id==='m5.image.cutout'){
    if(command.allow_cloud!==false||command.provider_id!==null||command.model_id!==null||command.prompt!==''||!validCutoutParameters(command.parameters)
      ||!Array.isArray(sources)||sources.length!==2||!pin(sources[0])||!object(sources[1])||sources[1].kind!=='ASSET'||sources[1].asset_kind!=='image'
      ||!id(sources[1].id)||sources[1].id===binding.source.id||!Number.isSafeInteger(sources[1].version)||(sources[1].version as number)<1||!hex(sources[1].digest)
      ||sources.some(s=>!object(s)||Object.keys(s).some(k=>!['id','kind','version','digest','asset_kind'].includes(k)))
      ||['image_source','image_references','mask_source','video_reference','video_frames','storyboard_shot','storyboard_speech','audio_profile','image_layers','derived_from','template_ref'].some(k=>Object.hasOwn(command,k)))invalid();
  }else if(command.operation_id!=='m5.image.i2i'||command.allow_cloud!==false||!Array.isArray(sources)||sources.length!==1||!pin(sources[0])||!pin(command.image_source)
    ||command.mask_source!==undefined||command.image_references!==undefined&&(!Array.isArray(command.image_references)||command.image_references.length))invalid();
  return binding;
}
export const sameCanvasReturn=(a:unknown,b:unknown)=>{
  const left=canvasReturnInCommand(a),right=canvasReturnInCommand(b);return left===undefined&&right===undefined||!!left&&!!right&&canonical(left)===canonical(right);
};
export const sameCanvasReturnScope=(binding:CanvasReturnBinding,projectId:string,scope:StudioGraphScope,incarnation:string|undefined)=>
  binding.project_id===projectId&&binding.incarnation===incarnation&&canonical(binding.scope)===canonical(scope);

/** New Timeline capsule remains distinct from the legacy MediaCommand contract. */
export function canvasReturnInJob(job: ProductionJob): CanvasReturnBinding | undefined {
  return Object.hasOwn(job, 'canvas_video') ? checkedCanvasVideoTaskJob(job).canvas_video.canvas_return : canvasReturnInCommand(job.command);
}
export function sameCanvasReturnJob(left: ProductionJob, right: ProductionJob): boolean {
  if (left.canvas_video !== undefined || right.canvas_video !== undefined) {
    return !!left.canvas_video && !!right.canvas_video && canonical(checkedCanvasVideoTaskJob(left).canvas_video) === canonical(checkedCanvasVideoTaskJob(right).canvas_video);
  }
  return sameCanvasReturn(left.command, right.command);
}
