import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';
export const MODEL_REFERENCE_MAX_BYTES=8*1024*1024;
export type ModelReferenceImport={contract:'studio-static-glb-import/1';filename:string;content_base64:string;idempotency_key:string};
export type ModelReferenceInspection={asset_snapshot:{id:string;kind:'ASSET';asset_kind:'model';version:number;digest:string};inspection:{
 contract:'studio-static-glb-inspection/1';format:'GLB_2_STATIC_TRIANGLE_GEOMETRY';byte_count:number;sha256:string;mesh_count:number;node_count:number;primitive_count:number;position_count_per_primitive:number;triangle_count_per_primitive:number;
 bounds:{space:'MESH_LOCAL_UNTRANSFORMED';min:number[];max:number[]};scene_transforms_applied:false;materials_rendered:false;textures_decoded:false;full_gltf_conformance_verified:false;external_resources_loaded:false;model_called:false;preview_available:false;frame_export_available:false;
}};
function invalid():never{throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'GLB 检查回执与当前素材版本不一致，请重新读取。'});}
function exact(value:unknown,keys:string[]):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))invalid();const row=value as Record<string,unknown>;if(Object.keys(row).length!==keys.length||keys.some(key=>!Object.hasOwn(row,key)))invalid();return row;}
function integer(value:unknown,min:number,max:number){if(typeof value!=='number'||!Number.isSafeInteger(value)||value<min||value>max)invalid();return value;}
export function checkedModelReferenceAsset(asset:StudioAsset){
 if(!asset||asset.kind!=='model'||asset.media_type!=='model/gltf-binary'||typeof asset.id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(asset.id)||asset.deleted_at||typeof asset.sha256!=='string'||!/^[a-f0-9]{64}$/.test(asset.sha256))invalid();
 integer(asset.version,1,Number.MAX_SAFE_INTEGER);integer(asset.size,28,MODEL_REFERENCE_MAX_BYTES);return asset;
}
export function checkedModelReferenceInspection(value:unknown,expected:StudioAsset):ModelReferenceInspection{
 checkedModelReferenceAsset(expected);const root=exact(value,['asset_snapshot','inspection']),pin=exact(root.asset_snapshot,['id','kind','asset_kind','version','digest']);
 if(pin.id!==expected.id||pin.kind!=='ASSET'||pin.asset_kind!=='model'||pin.version!==expected.version||pin.digest!==expected.sha256)invalid();
 const flags=['scene_transforms_applied','materials_rendered','textures_decoded','full_gltf_conformance_verified','external_resources_loaded','model_called','preview_available','frame_export_available'];
 const item=exact(root.inspection,['contract','format','byte_count','sha256','mesh_count','node_count','primitive_count','position_count_per_primitive','triangle_count_per_primitive','bounds',...flags]);
 if(item.contract!=='studio-static-glb-inspection/1'||item.format!=='GLB_2_STATIC_TRIANGLE_GEOMETRY'||item.sha256!==expected.sha256||item.byte_count!==expected.size||flags.some(key=>item[key]!==false))invalid();
 integer(item.mesh_count,1,64);integer(item.node_count,0,256);integer(item.primitive_count,1,128);integer(item.position_count_per_primitive,1,100000);integer(item.triangle_count_per_primitive,1,100000);
 const bounds=exact(item.bounds,['space','min','max']);if(bounds.space!=='MESH_LOCAL_UNTRANSFORMED')invalid();
 for(const key of ['min','max'])if(!Array.isArray(bounds[key])||(bounds[key] as unknown[]).length!==3||(bounds[key] as unknown[]).some(n=>typeof n!=='number'||!Number.isFinite(n)||Math.abs(n)>1e9))invalid();
 if((bounds.min as number[]).some((n,i)=>n>(bounds.max as number[])[i]))invalid();return structuredClone(value) as ModelReferenceInspection;
}
