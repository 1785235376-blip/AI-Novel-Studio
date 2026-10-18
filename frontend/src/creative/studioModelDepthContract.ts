import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';
import { checkedModelReferenceAsset } from './studioModelReferenceContract';
import { maskSha256 } from './studioManualMaskContract';
export type ModelDepthCamera={yaw:number;pitch:number};
export type ModelDepthExport={asset_snapshot:{id:string;kind:'ASSET';asset_kind:'model';version:number;digest:string};content_base64:string;depth_export:{contract:'studio-static-glb-depth-export/1';width:256;height:192;yaw:number;pitch:number;projection:'ORTHOGRAPHIC_DIAGNOSTIC';depth_encoding:'BACKGROUND_0_FAR_1_NEAR_255';metric_depth:false;covered_pixels:number;pixel_tests:number;png_sha256:string;scene_index:number;scene_selection:'DECLARED_DEFAULT'|'SOLE_SCENE';scene_transforms_applied:true;materials_rendered:false;animation_applied:false;model_called:false;asset_created:false}};
function invalid():never{throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'深度图回执、来源或 PNG 校验不一致，未下载。'});}
function exact(value:unknown,keys:string[]):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))invalid();const row=value as Record<string,unknown>;if(Object.keys(row).length!==keys.length||keys.some(k=>!Object.hasOwn(row,k)))invalid();return row;}
function integer(value:unknown,min:number,max:number){if(typeof value!=='number'||!Number.isSafeInteger(value)||value<min||value>max)invalid();return value;}
export function checkedDepthCamera(camera:ModelDepthCamera):ModelDepthCamera{if(!camera||typeof camera.yaw!=='number'||!Number.isFinite(camera.yaw)||Math.abs(camera.yaw)>180||typeof camera.pitch!=='number'||!Number.isFinite(camera.pitch)||Math.abs(camera.pitch)>89)invalid();return {yaw:camera.yaw,pitch:camera.pitch};}
export async function checkedModelDepth(value:unknown,asset:StudioAsset,camera:ModelDepthCamera):Promise<ModelDepthExport>{
 checkedModelReferenceAsset(asset);checkedDepthCamera(camera);
 // Detach before hashing: asynchronous verification must not admit later mutation.
 const detached=structuredClone(value),root=exact(detached,['asset_snapshot','content_base64','depth_export']),pin=exact(root.asset_snapshot,['id','kind','asset_kind','version','digest']);
 if(pin.id!==asset.id||pin.kind!=='ASSET'||pin.asset_kind!=='model'||pin.version!==asset.version||pin.digest!==asset.sha256)invalid();
 const flags=['metric_depth','materials_rendered','animation_applied','model_called','asset_created'];
 const p=exact(root.depth_export,['contract','width','height','yaw','pitch','projection','depth_encoding','covered_pixels','pixel_tests','png_sha256','scene_index','scene_selection','scene_transforms_applied',...flags]);
 if(p.contract!=='studio-static-glb-depth-export/1'||p.width!==256||p.height!==192||p.yaw!==camera.yaw||p.pitch!==camera.pitch||p.projection!=='ORTHOGRAPHIC_DIAGNOSTIC'||p.depth_encoding!=='BACKGROUND_0_FAR_1_NEAR_255'||p.scene_transforms_applied!==true||flags.some(k=>p[k]!==false)||!['DECLARED_DEFAULT','SOLE_SCENE'].includes(String(p.scene_selection)))invalid();
 integer(p.covered_pixels,1,256*192);integer(p.pixel_tests,p.covered_pixels as number,2000000);integer(p.scene_index,0,63);if(p.scene_selection==='SOLE_SCENE'&&p.scene_index!==0)invalid();
 await checkedDiagnosticPng(root.content_base64,p.png_sha256);return detached as ModelDepthExport;
}
/** Shared bounded grayscale PNG byte verification; semantic receipts stay separate. */
export async function checkedDiagnosticPng(content:unknown,digest:unknown):Promise<void>{
 if(typeof digest!=='string'||!/^[a-f0-9]{64}$/.test(digest)||typeof content!=='string'||content.length>87384)invalid();
 let binary:string;try{binary=atob(content);}catch{invalid();}if(binary.length<45||binary.length>65536||btoa(binary)!==content)invalid();
 const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0)),view=new DataView(bytes.buffer);
 if([137,80,78,71,13,10,26,10].some((n,i)=>bytes[i]!==n)||view.getUint32(8)!==13||String.fromCharCode(...bytes.slice(12,16))!=='IHDR'||view.getUint32(16)!==256||view.getUint32(20)!==192||bytes[24]!==8||bytes[25]!==0||bytes[26]!==0||bytes[27]!==0||bytes[28]!==0)invalid();
 if(await maskSha256(bytes)!==digest)invalid();
}
export function modelDepthBlob(value:{content_base64:string}){return new Blob([Uint8Array.from(atob(value.content_base64),c=>c.charCodeAt(0))],{type:'image/png'});}
