import type { CanvasAssetReference, CanvasDefinition, CanvasViewRecord } from './studioCanvasViewClient';
import type { MediaCommand, ProductionJob, ProductionProvider, ProductionSource } from './studioProductionClient';
import type { StudioAsset } from './studioClient';

/** Session-only return intent over original CanvasView/Job/Asset owners. */
export type CanvasImageTaskOrigin = { projectId: string; canvasId: string; canvasVersion: number; canvasDigest: string; cardId: string; source: CanvasAssetReference };
export type CanvasImageTaskBinding = { source: ProductionSource; isCurrent: () => boolean };
export type CanvasImageTaskSession = { id: string; origin: CanvasImageTaskOrigin; asset: StudioAsset; isOriginCurrent: () => boolean };
const same = (a: unknown,b: unknown) => JSON.stringify(a)===JSON.stringify(b);
export function canvasImageTaskSource(reference: CanvasAssetReference): ProductionSource {
  if(reference.kind!=='image')throw new Error('本片仅接受已保存的图片卡片。');
  return { id:reference.asset_id, kind:'ASSET', version:reference.version, digest:reference.digest, asset_kind:'image' };
}
export function captureCanvasImageTask(canvas: CanvasViewRecord, cardId: string, asset: StudioAsset): CanvasImageTaskOrigin {
  const card=canvas.definition.cards.find(row=>row.id===cardId), state=canvas.reference_states.find(row=>row.card_id===cardId);
  if(!card?.asset||state?.state!=='CURRENT_METADATA'||card.asset.kind!=='image'||asset.kind!=='image'||asset.deleted_at||asset.manual_mask
    ||asset.id!==card.asset.asset_id||asset.version!==card.asset.version||asset.sha256!==card.asset.digest)throw new Error('原卡片图片版本不可用，请重新读取。');
  return {projectId:canvas.project_id,canvasId:canvas.id,canvasVersion:canvas.version,canvasDigest:canvas.definition_digest,cardId,source:{...card.asset}};
}
export function assertCanvasImageTaskTarget(origin: CanvasImageTaskOrigin, canvas: CanvasViewRecord) {
  if(canvas.project_id!==origin.projectId||canvas.id!==origin.canvasId||canvas.version!==origin.canvasVersion||canvas.definition_digest!==origin.canvasDigest
    ||canvas.reference_states.find(row=>row.card_id===origin.cardId)?.state!=='CURRENT_METADATA'
    ||!same(canvas.definition.cards.find(row=>row.id===origin.cardId)?.asset,origin.source))throw new Error('原画布、卡片或素材版本已改变；不会回填当前选中的其他位置。');
}
const exactSource=(sources: readonly {id:string;kind:string;version:number;digest:string;asset_kind?:string}[], source:ProductionSource)=>sources.length===1
  && sources[0].id===source.id&&sources[0].kind==='ASSET'&&sources[0].version===source.version&&sources[0].digest===source.digest&&sources[0].asset_kind==='image';
export function assertCanvasImageTaskCommand(task: CanvasImageTaskBinding, command: MediaCommand, provider?: ProductionProvider) {
  if(!task.isCurrent())throw new Error('原作品位置已改变，请返回创作画布重新建立任务。');
  if(command.operation_id!=='m5.image.i2i'||command.allow_cloud||!provider?.local||provider.image_capabilities?.recipe_id!=='comfy-sd-checkpoint-v1'
    ||!exactSource(command.source_snapshots,task.source)||command.image_references?.length||command.mask_source)throw new Error('此卡片任务仅支持单张原图片的本地 Comfy SD 图生图，不会降级、增加参考或发送云端。');
}
export function canvasImageTaskJobMatches(task: CanvasImageTaskBinding, job: ProductionJob) {
  return job.owner==='image'&&job.operation_id==='m5.image.i2i'&&job.provider?.local===true&&job.command?.allow_cloud===false
    &&job.execution_recipe.adapter==='COMFYUI_BUILTIN_IMAGE'&&job.execution_recipe.image_recipe_id==='comfy-sd-checkpoint-v1'
    &&exactSource(job.sources,task.source)&&exactSource(job.command.source_snapshots,task.source);
}
export function replaceCanvasImageTaskResult(origin: CanvasImageTaskOrigin, canvas: CanvasViewRecord, job: ProductionJob, asset: StudioAsset): CanvasDefinition {
  assertCanvasImageTaskTarget(origin,canvas);
  if(job.novel_id!==origin.projectId||job.status!=='APPROVED'||!canvasImageTaskJobMatches({source:canvasImageTaskSource(origin.source),isCurrent:()=>true},job)
    ||!job.output_candidate||asset.id!==job.output_candidate.id||asset.version!==job.approved_asset_version||asset.sha256!==job.output_candidate.digest
    ||asset.kind!=='image'||asset.deleted_at)throw new Error('正式审核结果、原任务来源或素材版本未通过核验，未改变作品位置。');
  return {...canvas.definition,cards:canvas.definition.cards.map(card=>card.id===origin.cardId
    ? {...card,asset:{asset_id:asset.id,version:asset.version,digest:asset.sha256,kind:'image' as const}}:card)};
}
