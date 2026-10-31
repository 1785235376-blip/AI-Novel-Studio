import {ApiError} from '../api';
import type {StudioAsset} from './studioClient';
import {checkedModelReferenceAsset} from './studioModelReferenceContract';
import {checkedDepthCamera,checkedDiagnosticPng,type ModelDepthCamera,type ModelDepthExport} from './studioModelDepthContract';
export type ModelClayExport=Omit<ModelDepthExport,'depth_export'>&{clay_export:Omit<ModelDepthExport['depth_export'],'contract'|'metric_depth'|'depth_encoding'>&{contract:'studio-static-glb-clay-export/1';shading:'TWO_SIDED_FLAT_HEADLIGHT';background:255;physical_lighting:false}};
function invalid():never{throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'灰模图回执、来源或 PNG 校验不一致，未下载。'});}
function exact(value:unknown,keys:string[]):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))invalid();const row=value as Record<string,unknown>;if(Object.keys(row).length!==keys.length||keys.some(k=>!Object.hasOwn(row,k)))invalid();return row;}
function integer(value:unknown,min:number,max:number){if(typeof value!=='number'||!Number.isSafeInteger(value)||value<min||value>max)invalid();return value;}
export async function checkedModelClay(value:unknown,asset:StudioAsset,camera:ModelDepthCamera):Promise<ModelClayExport>{
 checkedModelReferenceAsset(asset);checkedDepthCamera(camera);const detached=structuredClone(value),root=exact(detached,['asset_snapshot','content_base64','clay_export']),pin=exact(root.asset_snapshot,['id','kind','asset_kind','version','digest']);
 if(pin.id!==asset.id||pin.kind!=='ASSET'||pin.asset_kind!=='model'||pin.version!==asset.version||pin.digest!==asset.sha256)invalid();
 const flags=['physical_lighting','materials_rendered','animation_applied','model_called','asset_created'];const p=exact(root.clay_export,['contract','width','height','yaw','pitch','projection','shading','background','covered_pixels','pixel_tests','png_sha256','scene_index','scene_selection','scene_transforms_applied',...flags]);
 if(p.contract!=='studio-static-glb-clay-export/1'||p.width!==256||p.height!==192||p.yaw!==camera.yaw||p.pitch!==camera.pitch||p.projection!=='ORTHOGRAPHIC_DIAGNOSTIC'||p.shading!=='TWO_SIDED_FLAT_HEADLIGHT'||p.background!==255||p.scene_transforms_applied!==true||flags.some(k=>p[k]!==false)||!['DECLARED_DEFAULT','SOLE_SCENE'].includes(String(p.scene_selection)))invalid();
 integer(p.covered_pixels,1,256*192);integer(p.pixel_tests,p.covered_pixels as number,2000000);integer(p.scene_index,0,63);if(p.scene_selection==='SOLE_SCENE'&&p.scene_index!==0)invalid();
 try{await checkedDiagnosticPng(root.content_base64,p.png_sha256);}catch{invalid();}return detached as ModelClayExport;
}
