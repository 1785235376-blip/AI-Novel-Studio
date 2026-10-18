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
 const messages:Record<string,string>={MODEL_REFERENCE_GLB_SCENE_SELECTION_REQUIRED:'GLB 有多个场景但未指定默认场景。请设置默认场景，或使用网格局部诊断。',MODEL_REFERENCE_GLB_SCENE_REQUIRED:'没有可用的静态场景；仍可尝试网格局部诊断。',MODEL_REFERENCE_GLB_SCENE_PREVIEW_LIMIT:'场景实例超出诊断预算，未自动简化；原文件保持不变。',MODEL_REFERENCE_GLB_SCENE_NOT_TREE:'节点层级含循环或多个父节点，不能作为静态场景读取。',MODEL_REFERENCE_GLB_TRANSFORM_INVALID:'节点变换格式不受支持，未返回部分场景。',MODEL_REFERENCE_GLB_PREVIEW_LIMIT:'网格超出诊断视图的 4096 个位置或 2048 个三角形上限；原文件保留，未自动简化。',MODEL_REFERENCE_GLB_URI_UNSUPPORTED:'GLB 含 URI 引用，当前不加载外部或内联 URI。请导出仅使用嵌入 BIN 数据的静态参考。',MODEL_REFERENCE_GLB_ANIMATION_OR_EXTENSION_UNSUPPORTED:'当前只支持静态未压缩网格，暂不支持动画、骨骼或扩展。',MODEL_REFERENCE_GLB_SIZE_INVALID:'GLB 文件为空、过小或超过 8 MiB 上限。',MODEL_REFERENCE_GLB_POSITION_UNSUPPORTED:'当前只支持 float32 VEC3 位置数据的三角网格。'};
 return Object.hasOwn(messages,code)?messages[code]:apiErrorView(reason,fallback).message;
}

export type ModelScenePreview=ModelReferenceInspection&{scene_preview:{
 contract:'studio-static-glb-scene-preview/1';space:'SCENE_WORLD_STATIC';scene_index:number;selection:'DECLARED_DEFAULT'|'SOLE_SCENE';traversed_nodes:number;mesh_instances:number;position_count:number;triangle_count:number;
 primitives:{node_index:number;mesh_index:number;primitive_index:number;positions:number[][];triangles:number[][]}[];bounds:{min:number[];max:number[]};scene_transforms_applied:true;materials_rendered:false;animation_applied:false;decimated:false;model_called:false;
}};
export function checkedModelScenePreview(value:unknown,expected:StudioAsset):ModelScenePreview{
 const root=exact(value,['asset_snapshot','inspection','scene_preview']);const base=checkedModelReferenceInspection({asset_snapshot:root.asset_snapshot,inspection:root.inspection},expected);
 const scene=exact(root.scene_preview,['contract','space','scene_index','selection','traversed_nodes','mesh_instances','position_count','triangle_count','primitives','bounds','scene_transforms_applied','materials_rendered','animation_applied','decimated','model_called']);
 if(scene.contract!=='studio-static-glb-scene-preview/1'||scene.space!=='SCENE_WORLD_STATIC'||scene.scene_transforms_applied!==true||['materials_rendered','animation_applied','decimated','model_called'].some(k=>scene[k]!==false)||(scene.selection!=='DECLARED_DEFAULT'&&scene.selection!=='SOLE_SCENE'))invalid();
 integer(scene.scene_index,0,63);if(scene.selection==='SOLE_SCENE'&&scene.scene_index!==0)invalid();
 const traversed=integer(scene.traversed_nodes,1,base.inspection.node_count),instances=integer(scene.mesh_instances,1,traversed);
 if(!Array.isArray(scene.primitives)||!scene.primitives.length||scene.primitives.length>128)invalid();
 const bounds=exact(scene.bounds,['min','max']),minimum=[Infinity,Infinity,Infinity],maximum=[-Infinity,-Infinity,-Infinity];let positions=0,triangles=0;
 const nodes=new Map<number,{mesh:number;next:number}>();
 for(const raw of scene.primitives){const p=exact(raw,['node_index','mesh_index','primitive_index','positions','triangles']);const node=integer(p.node_index,0,base.inspection.node_count-1),mesh=integer(p.mesh_index,0,base.inspection.mesh_count-1),primitive=integer(p.primitive_index,0,base.inspection.primitive_count-1);
  const prior=nodes.get(node);if(prior?(prior.mesh!==mesh||prior.next!==primitive):primitive!==0)invalid();nodes.set(node,{mesh,next:primitive+1});
  if(!Array.isArray(p.positions)||!p.positions.length||!Array.isArray(p.triangles)||!p.triangles.length)invalid();positions+=p.positions.length;triangles+=p.triangles.length;if(positions>4096||triangles>2048)invalid();
  for(const point of p.positions){if(!Array.isArray(point)||point.length!==3||point.some(n=>typeof n!=='number'||!Number.isFinite(n)||Math.abs(n)>1e9))invalid();point.forEach((n,i)=>{minimum[i]=Math.min(minimum[i],n);maximum[i]=Math.max(maximum[i],n);});}
  for(const tri of p.triangles){if(!Array.isArray(tri)||tri.length!==3)invalid();tri.forEach(i=>integer(i,0,(p.positions as unknown[]).length-1));}
 }
 if(nodes.size!==instances||positions!==integer(scene.position_count,1,4096)||triangles!==integer(scene.triangle_count,1,2048))invalid();
 if(!Array.isArray(bounds.min)||!Array.isArray(bounds.max)||bounds.min.length!==3||bounds.max.length!==3||minimum.some((n,i)=>n!==(bounds.min as number[])[i])||maximum.some((n,i)=>n!==(bounds.max as number[])[i]))invalid();
 return structuredClone(value) as ModelScenePreview;
}
