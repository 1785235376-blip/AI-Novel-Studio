import type { CanvasAssetReference, CanvasDefinition, CanvasViewRecord } from './studioCanvasViewClient';
import type { MediaCommand, ProductionJob, ProductionProvider, ProductionSource } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
import { checkedCanvasReturnBinding, sameCanvasReturn, type CanvasReturnBinding } from './studioCanvasReturnBinding';
import { checkedCutoutProof, CUTOUT_WEBP_OUTPUT, CUTOUT_WEBP_PROFILE, validCutoutParameters } from './studioCutoutContract';

/** Session presentation over an optional immutable return binding in the original Job. */
export type CanvasImageTaskOrigin = { projectId: string; canvasId: string; canvasVersion: number; canvasDigest: string; cardId: string; source: CanvasAssetReference; binding?:CanvasReturnBinding };
export type CanvasImageTaskBinding = { source: ProductionSource; returnBinding?:CanvasReturnBinding; isCurrent: () => boolean };
export type CanvasImageTaskSession = { id: string; origin: CanvasImageTaskOrigin; asset: StudioAsset; isOriginCurrent: () => boolean; resumeJob?:ProductionJob };
const same = (a: unknown,b: unknown) => JSON.stringify(a,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x)===JSON.stringify(b,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
export function canvasImageTaskSource(reference: CanvasAssetReference): ProductionSource {
  if(reference.kind!=='image')throw new Error('本片仅接受已保存的图片卡片。');
  return { id:reference.asset_id, kind:'ASSET', version:reference.version, digest:reference.digest, asset_kind:'image' };
}
export function captureCanvasImageTask(canvas: CanvasViewRecord, cardId: string, asset: StudioAsset, incarnation?:string): CanvasImageTaskOrigin {
  const card=canvas.definition.cards.find(row=>row.id===cardId), state=canvas.reference_states.find(row=>row.card_id===cardId);
  if(!card?.asset||state?.state!=='CURRENT_METADATA'||card.asset.kind!=='image'||asset.kind!=='image'||asset.deleted_at||asset.manual_mask
    ||asset.id!==card.asset.asset_id||asset.version!==card.asset.version||asset.sha256!==card.asset.digest)throw new Error('原卡片图片版本不可用，请重新读取。');
  const binding=incarnation===undefined?undefined:checkedCanvasReturnBinding({contract:'studio-canvas-return/1',project_id:canvas.project_id,scope:canvas.scope,incarnation,
    canvas_id:canvas.id,canvas_version:canvas.version,canvas_digest:canvas.definition_digest,card_id:cardId,source:canvasImageTaskSource(card.asset)});
  return {projectId:canvas.project_id,canvasId:canvas.id,canvasVersion:canvas.version,canvasDigest:canvas.definition_digest,cardId,source:{...card.asset},...(binding?{binding}:{})};
}
export function assertCanvasImageTaskTarget(origin: CanvasImageTaskOrigin, canvas: CanvasViewRecord) {
  if(canvas.project_id!==origin.projectId||canvas.id!==origin.canvasId||canvas.version!==origin.canvasVersion||canvas.definition_digest!==origin.canvasDigest||origin.binding&&!same(canvas.scope,origin.binding.scope)
    ||canvas.reference_states.find(row=>row.card_id===origin.cardId)?.state!=='CURRENT_METADATA'
    ||!same(canvas.definition.cards.find(row=>row.id===origin.cardId)?.asset,origin.source))throw new Error('原画布、卡片或素材版本已改变；不会回填当前选中的其他位置。');
}
const record=(value:unknown):value is Record<string,unknown>=>!!value&&typeof value==='object'&&!Array.isArray(value);
const exactSource=(sources: readonly {id:string;kind:string;version:number;digest:string;asset_kind?:string}[], source:ProductionSource)=>Array.isArray(sources)&&sources.length===1
  &&record(sources[0])&&sources[0].id===source.id&&sources[0].kind==='ASSET'&&sources[0].version===source.version&&sources[0].digest===source.digest&&sources[0].asset_kind==='image';
const pinFields=['id','kind','version','digest','asset_kind'] as const;
function imagePin(value:unknown):value is ProductionSource {
  return record(value)&&Object.keys(value).every(key=>[...pinFields,'reference_only'].includes(key as never))
    &&typeof value.id==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value.id)&&value.kind==='ASSET'&&value.asset_kind==='image'
    &&Number.isSafeInteger(value.version)&&(value.version as number)>0&&typeof value.digest==='string'&&/^[a-f0-9]{64}$/.test(value.digest)
    &&(!Object.hasOwn(value,'reference_only')||value.reference_only===true);
}
const sameImagePin=(left:unknown,right:unknown)=>imagePin(left)&&imagePin(right)&&pinFields.every(key=>left[key]===right[key]);
function cutoutCommandMatches(task:CanvasImageTaskBinding, command:MediaCommand, recorded=false):boolean {
  const allowed=['operation_id','request_id','provider_id','model_id','prompt','parameters','source_snapshots','allow_cloud','license_note','canvas_return'];
  const sources=command.source_snapshots;
  return Object.keys(command).every(key=>allowed.includes(key))&&command.operation_id==='m5.image.cutout'&&command.provider_id===null&&command.model_id===null
    &&command.prompt===''&&command.allow_cloud===false&&typeof command.request_id==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(command.request_id)
    &&typeof command.license_note==='string'&&command.license_note.length<=2000&&validCutoutParameters(command.parameters)
    &&Array.isArray(sources)&&sources.length===2&&sameImagePin(sources[0],task.source)&&imagePin(sources[1])&&sources[0].id!==sources[1].id
    &&(recorded||sources.every(source=>record(source)&&source.reference_only===undefined))
    &&(!Object.hasOwn(command,'canvas_return')||sameCanvasReturn(command,command))
    &&(!task.returnBinding||sameCanvasReturn({...command,canvas_return:task.returnBinding},command));
}
export function assertCanvasImageTaskCommand(task: CanvasImageTaskBinding, command: MediaCommand, provider?: ProductionProvider) {
  if(!task.isCurrent())throw new Error('原作品位置已改变，请返回创作画布重新建立任务。');
  if(command.operation_id==='m5.image.cutout'){
    if(provider!=null||!cutoutCommandMatches(task,command))throw new Error('此卡片抠图仅支持原图与明确选择的蒙版进行本地 CPU 处理，不会调用模型或发送云端。');
    return;
  }
  if(command.operation_id!=='m5.image.i2i'||command.allow_cloud||!provider?.local||provider.image_capabilities?.recipe_id!=='comfy-sd-checkpoint-v1'
    ||!exactSource(command.source_snapshots,task.source)||command.image_references?.length||command.mask_source
    ||task.returnBinding&&!sameCanvasReturn({...command,canvas_return:task.returnBinding},command))throw new Error('此卡片任务仅支持单张原图片的本地 Comfy SD 图生图，不会降级、增加参考或发送云端。');
}
export function canvasImageTaskJobMatches(task: CanvasImageTaskBinding, job: ProductionJob) {
  try{
    if(job.operation_id==='m5.image.cutout'){
      const command=job.command,recipe=job.execution_recipe;
      if(job.owner!=='image'||job.provider!==null||!command||!cutoutCommandMatches(task,command,true)||job.request_id!==command.request_id
        ||job.automatic_replay!==false||job.remote_compute_may_continue!==false
        ||!Array.isArray(job.sources)||job.sources.length!==2||!job.sources.every((source,index)=>sameImagePin(source,command.source_snapshots[index]))
        ||recipe.contract!=='studio-execution-recipe/1'||typeof recipe.recipe_digest!=='string'||!/^[a-f0-9]{64}$/.test(recipe.recipe_digest)
        ||recipe.operation_id!=='m5.image.cutout'||recipe.adapter!=='LOCAL_CPU_MASK'||recipe.automatic_fallback!==false
        ||recipe.output_profile!==(command.parameters.cutout_output===CUTOUT_WEBP_PROFILE?CUTOUT_WEBP_OUTPUT:'PNG_RGBA8_STORED_DEFLATE')
        ||recipe.mask_policy!=='WHITE_KEEP_BLACK_TRANSPARENT_ZERO'||!same(recipe.parameters,command.parameters)
        ||job.output_candidate!==null&&job.output_candidate?.kind!=='image')return false;
      checkedCutoutProof(job.processing_proof,command.source_snapshots,job.output_candidate,command.parameters.cutout_output);
      return true;
    }
    return job.owner==='image'&&job.operation_id==='m5.image.i2i'&&job.provider?.local===true&&job.command?.allow_cloud===false
      &&job.execution_recipe.adapter==='COMFYUI_BUILTIN_IMAGE'&&job.execution_recipe.image_recipe_id==='comfy-sd-checkpoint-v1'
      &&exactSource(job.sources,task.source)&&exactSource(job.command.source_snapshots,task.source)
      &&(!task.returnBinding||sameCanvasReturn({...job.command,canvas_return:task.returnBinding},job.command));
  }catch{return false;}
}
export function replaceCanvasImageTaskResult(origin: CanvasImageTaskOrigin, canvas: CanvasViewRecord, job: ProductionJob, asset: StudioAsset): CanvasDefinition {
  assertCanvasImageTaskTarget(origin,canvas);
  if(job.novel_id!==origin.projectId||job.status!=='APPROVED'||!canvasImageTaskJobMatches({source:canvasImageTaskSource(origin.source),returnBinding:origin.binding,isCurrent:()=>true},job)
    ||!job.output_candidate||asset.id!==job.output_candidate.id||asset.version!==job.approved_asset_version||asset.sha256!==job.output_candidate.digest
    ||asset.kind!=='image'||asset.deleted_at)throw new Error('正式审核结果、原任务来源或素材版本未通过核验，未改变作品位置。');
  return {...canvas.definition,cards:canvas.definition.cards.map(card=>card.id===origin.cardId
    ? {...card,asset:{asset_id:asset.id,version:asset.version,digest:asset.sha256,kind:'image' as const}}:card)};
}
