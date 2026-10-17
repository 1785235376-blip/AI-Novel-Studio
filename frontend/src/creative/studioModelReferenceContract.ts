import { ApiError, apiErrorView } from '../api';
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

export type ModelMeshPreview=ModelReferenceInspection&{mesh_preview:{contract:'studio-static-glb-mesh-preview/1';space:'MESH_LOCAL_UNTRANSFORMED';primitives:{positions:number[][];triangles:number[][]}[];scene_transforms_applied:false;materials_rendered:false;decimated:false;model_called:false}};
export function checkedModelMeshPreview(value:unknown,expected:StudioAsset):ModelMeshPreview{
 const root=exact(value,['asset_snapshot','inspection','mesh_preview']);
 const checked=checkedModelReferenceInspection({asset_snapshot:root.asset_snapshot,inspection:root.inspection},expected);
 const mesh=exact(root.mesh_preview,['contract','space','primitives','scene_transforms_applied','materials_rendered','decimated','model_called']);
 if(mesh.contract!=='studio-static-glb-mesh-preview/1'||mesh.space!=='MESH_LOCAL_UNTRANSFORMED'||['scene_transforms_applied','materials_rendered','decimated','model_called'].some(key=>mesh[key]!==false)||!Array.isArray(mesh.primitives)||mesh.primitives.length!==checked.inspection.primitive_count)invalid();
 let positions=0,triangles=0;const minimum=[Infinity,Infinity,Infinity],maximum=[-Infinity,-Infinity,-Infinity];
 for(const raw of mesh.primitives){const primitive=exact(raw,['positions','triangles']);if(!Array.isArray(primitive.positions)||!primitive.positions.length||!Array.isArray(primitive.triangles)||!primitive.triangles.length)invalid();
  positions+=primitive.positions.length;triangles+=primitive.triangles.length;if(positions>4096||triangles>2048)invalid();
  for(const point of primitive.positions){if(!Array.isArray(point)||point.length!==3||point.some(n=>typeof n!=='number'||!Number.isFinite(n)||Math.abs(n)>1e9))invalid();point.forEach((n,i)=>{minimum[i]=Math.min(minimum[i],n);maximum[i]=Math.max(maximum[i],n);});}
  for(const triangle of primitive.triangles){if(!Array.isArray(triangle)||triangle.length!==3)invalid();triangle.forEach(index=>integer(index,0,(primitive.positions as unknown[]).length-1));}
 }
 if(positions!==checked.inspection.position_count_per_primitive||triangles!==checked.inspection.triangle_count_per_primitive||minimum.some((n,i)=>n!==checked.inspection.bounds.min[i])||maximum.some((n,i)=>n!==checked.inspection.bounds.max[i]))invalid();
 return structuredClone(value) as ModelMeshPreview;
}

export function modelReferenceError(reason:unknown,fallback:string):string{
 const code=reason instanceof ApiError?reason.problem.code:'';
 const messages:Record<string,string>={MODEL_REFERENCE_GLB_PREVIEW_LIMIT:'网格超出诊断视图的 4096 个位置或 2048 个三角形上限；原文件保留，未自动简化。',MODEL_REFERENCE_GLB_URI_UNSUPPORTED:'GLB 含 URI 引用，当前不加载外部或内联 URI。请导出仅使用嵌入 BIN 数据的静态参考。',MODEL_REFERENCE_GLB_ANIMATION_OR_EXTENSION_UNSUPPORTED:'当前只支持静态未压缩网格，暂不支持动画、骨骼或扩展。',MODEL_REFERENCE_GLB_SIZE_INVALID:'GLB 文件为空、过小或超过 8 MiB 上限。',MODEL_REFERENCE_GLB_POSITION_UNSUPPORTED:'当前只支持 float32 VEC3 位置数据的三角网格。'};
 return Object.hasOwn(messages,code)?messages[code]:apiErrorView(reason,fallback).message;
}
