import {ApiError} from '../api';
import type {StudioAsset} from './studioClient';
import {maskSha256} from './studioManualMaskContract';
import {checkedModelReferenceAsset, checkedModelReferenceInspection, type ModelReferenceInspection} from './studioModelReferenceContract';

export const MODEL_CAMERA_CONTRACT = 'studio-static-glb-cameras/1';
export const MODEL_CAMERA_EXPORT_CONTRACT = 'studio-static-glb-camera-export/1';
export type ModelCameraProjection =
  | {type:'perspective';yfov:number;znear:number;aspectRatio:number|null;zfar:number|null}
  | {type:'orthographic';xmag:number;ymag:number;znear:number;zfar:number};
export type ModelCameraInstance = {node_index:number;camera_index:number;node_name:string;camera_name:string;world_matrix:number[];projection:ModelCameraProjection};
type SceneSelection = 'DECLARED_DEFAULT'|'SOLE_SCENE';
export type ModelCameras = ModelReferenceInspection & {camera_inspection:{
  contract:typeof MODEL_CAMERA_CONTRACT;space:'SCENE_WORLD_STATIC';coordinate_system:'GLTF_RH_Y_UP_METERS';matrix_layout:'COLUMN_MAJOR';
  scene_index:number;scene_selection:SceneSelection;camera_definition_count:number;instances:ModelCameraInstance[];
  rigid_transforms_only:true;animation_applied:false;model_called:false;
}};
export type ModelCameraSelection = {scene_index:number;scene_selection:SceneSelection;camera:ModelCameraInstance};
export type ModelCameraExport = {asset_snapshot:ModelReferenceInspection['asset_snapshot'];content_base64:string;camera_export:ModelCameraSelection & {
  contract:typeof MODEL_CAMERA_EXPORT_CONTRACT;profile:'GLTF_2_CAMERA_ONLY';coordinate_system:'GLTF_RH_Y_UP_METERS';matrix_layout:'COLUMN_MAJOR';
  byte_count:number;sha256:string;animation_applied:false;model_called:false;asset_created:false;
  blender_import_acceptance:'NOT_RUN';unreal_import_acceptance:'NOT_RUN';
}};

function invalid():never {throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'相机回执、原素材或 glTF 文件校验不一致，未下载。'});}
function exact(value:unknown, keys:string[]):Record<string,unknown> {
  if(!value || typeof value!=='object' || Array.isArray(value)) invalid();
  const row=value as Record<string,unknown>;
  if(Object.keys(row).length!==keys.length || keys.some(key=>!Object.hasOwn(row,key))) invalid();
  return row;
}
function number(value:unknown,min:number,max=1e9):number {
  if(typeof value!=='number' || !Number.isFinite(value) || value<min || value>max) invalid();
  return value;
}
function integer(value:unknown,min:number,max:number):number {
  const result=number(value,min,max);if(!Number.isSafeInteger(result)) invalid();return result;
}
function positive(value:unknown):number {const result=number(value,0);if(result===0) invalid();return result;}
function label(value:unknown) {if(typeof value!=='string' || [...value].length>240 || /[\u0000-\u001f\u007f]/.test(value)) invalid();}
function scene(index:unknown, selection:unknown) {
  integer(index,0,63);
  if(selection!=='DECLARED_DEFAULT' && selection!=='SOLE_SCENE' || selection==='SOLE_SCENE' && index!==0) invalid();
}
function checkedInstance(value:unknown, nodeCount=256, cameraCount=64):ModelCameraInstance {
  const row=exact(value,['node_index','camera_index','node_name','camera_name','world_matrix','projection']);
  integer(row.node_index,0,nodeCount-1);integer(row.camera_index,0,cameraCount-1);label(row.node_name);label(row.camera_name);
  if(!Array.isArray(row.world_matrix) || row.world_matrix.length!==16) invalid();
  const matrix=Array.from(row.world_matrix,value=>number(value,-1e9));
  if(matrix[3]!==0 || matrix[7]!==0 || matrix[11]!==0 || matrix[15]!==1) invalid();
  // Column-major rigid camera pose, with no normalization or recentering.
  for(let a=0;a<3;a++) for(let b=a;b<3;b++) {
    const dot=matrix[a*4]*matrix[b*4]+matrix[a*4+1]*matrix[b*4+1]+matrix[a*4+2]*matrix[b*4+2];
    if(Math.abs(dot-(a===b?1:0))>1e-5) invalid();
  }
  const determinant=matrix[0]*(matrix[5]*matrix[10]-matrix[9]*matrix[6])-matrix[4]*(matrix[1]*matrix[10]-matrix[9]*matrix[2])+matrix[8]*(matrix[1]*matrix[6]-matrix[5]*matrix[2]);
  if(Math.abs(determinant-1)>1e-5) invalid();
  const projection=row.projection as Record<string,unknown>|null;
  if(projection?.type==='perspective') {
    const p=exact(projection,['type','yfov','znear','aspectRatio','zfar']);
    if(positive(p.yfov)>=Math.PI) invalid();
    const near=positive(p.znear);if(p.aspectRatio!==null) positive(p.aspectRatio);
    if(p.zfar!==null && positive(p.zfar)<=near) invalid();
  } else if(projection?.type==='orthographic') {
    const p=exact(projection,['type','xmag','ymag','znear','zfar']);positive(p.xmag);positive(p.ymag);
    if(positive(p.zfar)<=number(p.znear,0)) invalid();
  } else invalid();
  return structuredClone(value) as ModelCameraInstance;
}
/** Structural equality is key-order independent and rejects extra artifact fields. */
function same(actual:unknown, expected:unknown):boolean {
  if(actual===expected) return true;
  if(Array.isArray(expected)) return Array.isArray(actual) && actual.length===expected.length && expected.every((value,index)=>same(actual[index],value));
  if(!expected || typeof expected!=='object' || !actual || typeof actual!=='object' || Array.isArray(actual)) return false;
  const keys=Object.keys(expected),row=actual as Record<string,unknown>;
  return Object.keys(row).length===keys.length && keys.every(key=>Object.hasOwn(row,key) && same(row[key],(expected as Record<string,unknown>)[key]));
}
export function checkedModelCameras(value:unknown, asset:StudioAsset):ModelCameras {
  const root=exact(value,['asset_snapshot','inspection','camera_inspection']);
  const base=checkedModelReferenceInspection({asset_snapshot:root.asset_snapshot,inspection:root.inspection},asset);
  const cameras=exact(root.camera_inspection,['contract','space','coordinate_system','matrix_layout','scene_index','scene_selection','camera_definition_count','instances','rigid_transforms_only','animation_applied','model_called']);
  if(cameras.contract!==MODEL_CAMERA_CONTRACT || cameras.space!=='SCENE_WORLD_STATIC' || cameras.coordinate_system!=='GLTF_RH_Y_UP_METERS' || cameras.matrix_layout!=='COLUMN_MAJOR' || cameras.rigid_transforms_only!==true || cameras.animation_applied!==false || cameras.model_called!==false) invalid();
  scene(cameras.scene_index,cameras.scene_selection);const count=integer(cameras.camera_definition_count,0,64);
  if(!Array.isArray(cameras.instances) || cameras.instances.length>64) invalid();
  const nodes=new Set<number>();
  for(const value of cameras.instances) {
    const camera=checkedInstance(value,base.inspection.node_count,count);
    if(nodes.has(camera.node_index)) invalid();nodes.add(camera.node_index);
  }
  return structuredClone(value) as ModelCameras;
}
export function checkedModelCameraSelection(value:unknown):ModelCameraSelection {
  const row=exact(value,['scene_index','scene_selection','camera']);scene(row.scene_index,row.scene_selection);checkedInstance(row.camera);
  return structuredClone(value) as ModelCameraSelection;
}
export function modelCameraSelection(review:ModelCameras, asset:StudioAsset, nodeIndex:number):ModelCameraSelection {
  const cameras=checkedModelCameras(review,asset).camera_inspection;
  const camera=cameras.instances.find(row=>row.node_index===nodeIndex);if(!camera) invalid();
  return {scene_index:cameras.scene_index,scene_selection:cameras.scene_selection,camera};
}
function expectedDocument(asset:StudioAsset, selection:ModelCameraSelection) {
  const {camera,scene_index,scene_selection}=selection,p=camera.projection;
  const projection=p.type==='perspective'
    ? {type:p.type,name:camera.camera_name,perspective:{yfov:p.yfov,znear:p.znear,...(p.aspectRatio===null?{}:{aspectRatio:p.aspectRatio}),...(p.zfar===null?{}:{zfar:p.zfar})}}
    : {type:p.type,name:camera.camera_name,orthographic:{xmag:p.xmag,ymag:p.ymag,znear:p.znear,zfar:p.zfar}};
  return {asset:{version:'2.0',generator:'Studio static camera exchange/1'},scene:0,scenes:[{nodes:[0]}],nodes:[{camera:0,matrix:camera.world_matrix,name:camera.node_name}],cameras:[projection],extras:{studio_camera_source:{contract:'studio-static-glb-camera-source/1',asset_id:asset.id,version:asset.version,sha256:asset.sha256,scene_index,scene_selection,node_index:camera.node_index,camera_index:camera.camera_index}}};
}
function parseDocument(bytes:Uint8Array):unknown {
  const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
  const stack:({kind:'object';keys:Set<string>}|{kind:'array'})[]=[];
  // JSON.parse discards duplicate keys. Check the raw bounded artifact first,
  // including escaped-equivalent names, so the downloaded bytes cannot conceal
  // a different interpretation for another glTF reader. Syntax is checked below.
  for(let offset=0;offset<text.length;offset++) {
    const char=text[offset];
    if(char==='{' || char==='[') {
      stack.push(char==='{'?{kind:'object',keys:new Set()}:{kind:'array'});
      if(stack.length>16) invalid();
    } else if(char==='}' || char===']') {
      const frame=stack.pop();if(!frame || frame.kind!==(char==='}'?'object':'array')) invalid();
    } else if(char==='"') {
      const start=offset++;
      for(;offset<text.length;offset++) {
        if(text[offset]==='\\') offset++;
        else if(text[offset]==='"') break;
      }
      if(offset>=text.length) invalid();
      const value=JSON.parse(text.slice(start,offset+1)) as string;
      let next=offset+1;while(next<text.length && /[\t\n\r ]/.test(text[next])) next++;
      if(text[next]===':') {
        const frame=stack[stack.length-1];if(frame?.kind!=='object' || frame.keys.has(value)) invalid();
        frame.keys.add(value);
      }
    }
  }
  if(stack.length) invalid();
  return JSON.parse(text);
}
export async function checkedModelCameraExport(value:unknown, asset:StudioAsset, selection:ModelCameraSelection):Promise<ModelCameraExport> {
  // Detach all inputs before the asynchronous byte hash to prevent later mutation.
  const source=structuredClone(checkedModelReferenceAsset(asset)),choice=checkedModelCameraSelection(selection),detached=structuredClone(value);
  const root=exact(detached,['asset_snapshot','camera_export','content_base64']);
  if(!same(root.asset_snapshot,{id:source.id,kind:'ASSET',asset_kind:'model',version:source.version,digest:source.sha256})) invalid();
  const receipt=exact(root.camera_export,['contract','profile','scene_index','scene_selection','camera','coordinate_system','matrix_layout','byte_count','sha256','animation_applied','model_called','asset_created','blender_import_acceptance','unreal_import_acceptance']);
  if(receipt.contract!==MODEL_CAMERA_EXPORT_CONTRACT || receipt.profile!=='GLTF_2_CAMERA_ONLY' || receipt.coordinate_system!=='GLTF_RH_Y_UP_METERS' || receipt.matrix_layout!=='COLUMN_MAJOR' || receipt.animation_applied!==false || receipt.model_called!==false || receipt.asset_created!==false || receipt.blender_import_acceptance!=='NOT_RUN' || receipt.unreal_import_acceptance!=='NOT_RUN' || receipt.scene_index!==choice.scene_index || receipt.scene_selection!==choice.scene_selection || !same(receipt.camera,choice.camera)) invalid();
  const size=integer(receipt.byte_count,1,65536);
  if(typeof receipt.sha256!=='string' || !/^[a-f0-9]{64}$/.test(receipt.sha256) || typeof root.content_base64!=='string' || root.content_base64.length>87384) invalid();
  let binary:string;try {binary=atob(root.content_base64);} catch {invalid();}
  if(binary.length!==size || btoa(binary)!==root.content_base64) invalid();
  const bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));let document:unknown;
  try {document=parseDocument(bytes);} catch {invalid();}
  if(!same(document,expectedDocument(source,choice)) || await maskSha256(bytes)!==receipt.sha256) invalid();
  return detached as ModelCameraExport;
}
export function modelCameraBlob(value:ModelCameraExport):Blob {
  return new Blob([Uint8Array.from(atob(value.content_base64),char=>char.charCodeAt(0))],{type:'model/gltf+json'});
}
