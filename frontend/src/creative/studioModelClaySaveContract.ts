import {ApiError} from '../api';
import type {StudioAsset} from './studioClient';
import type {ModelClayExport} from './studioModelClayContract';
export const CLAY_ASSET_CONTRACT='studio-static-glb-clay-asset/1' as const;
export type ClayAssetOrigin={contract:typeof CLAY_ASSET_CONTRACT;diagnostic_only:true;source_asset_id:string;source_version:number;source_sha256:string;width:256;height:192;yaw:number;pitch:number;png_sha256:string;scene_index:number};
export type ClayAssetResult={asset:StudioAsset;receipt:{contract:typeof CLAY_ASSET_CONTRACT;source_asset_id:string;source_version:number;source_sha256:string;png_sha256:string;replayed:boolean;model_called:false;diagnostic_only:true;asset_created:boolean}};
function invalid():never{throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'灰模素材保存回执未确认，请核对原素材库后使用同一请求重试。'});}
function object(value:unknown):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))invalid();return value as Record<string,unknown>;}
function exact(value:unknown,keys:string[]){const row=object(value);if(Object.keys(row).length!==keys.length||keys.some(k=>!Object.hasOwn(row,k)))invalid();return row;}
export function checkedClayAssetResult(value:unknown,source:StudioAsset,review:ModelClayExport):ClayAssetResult{
 const detached=structuredClone(value),root=exact(detached,['asset','receipt']),asset=object(root.asset),p=review.clay_export;
 const origin=exact(asset.model_reference,['contract','diagnostic_only','source_asset_id','source_version','source_sha256','width','height','yaw','pitch','png_sha256','scene_index']);
 const receipt=exact(root.receipt,['contract','source_asset_id','source_version','source_sha256','png_sha256','replayed','model_called','diagnostic_only','asset_created']);
 for(const row of [origin,receipt])if(row.contract!==CLAY_ASSET_CONTRACT||row.diagnostic_only!==true||row.source_asset_id!==source.id||row.source_version!==source.version||row.source_sha256!==source.sha256||row.png_sha256!==p.png_sha256)invalid();
 if(origin.width!==256||origin.height!==192||origin.yaw!==p.yaw||origin.pitch!==p.pitch||origin.scene_index!==p.scene_index||receipt.model_called!==false||typeof receipt.replayed!=='boolean'||typeof receipt.asset_created!=='boolean'||receipt.replayed===receipt.asset_created)invalid();
 if(typeof asset.id!=='string'||!asset.id||asset.id===source.id||!Number.isSafeInteger(asset.version)||(asset.version as number)<1||asset.novel_id!==source.novel_id||(asset.branch_id??null)!==(source.branch_id??null)||asset.kind!=='image'||asset.media_type!=='image/png'||asset.sha256!==p.png_sha256||asset.deleted_at||asset.source_job_id!=null||asset.provider_id!=null||asset.model_id!=null||asset.approved_at!=null)invalid();
 if(!Array.isArray(asset.source_asset_ids)||asset.source_asset_ids.length!==1||asset.source_asset_ids[0]!==source.id)invalid();
 const provenance=object(asset.provenance);if(provenance.origin!=='MANUAL_EDIT'||provenance.integrity!=='VERIFIED')invalid();
 if(!Array.isArray(provenance.parents)||provenance.parents.length!==1)invalid();const parent=object(provenance.parents[0]);if(parent.id!==source.id||parent.version!==source.version||parent.digest!==source.sha256||parent.state!=='CURRENT')invalid();
 if(JSON.stringify(detached).includes('"_model_reference_origin"'))invalid();return detached as ClayAssetResult;
}
