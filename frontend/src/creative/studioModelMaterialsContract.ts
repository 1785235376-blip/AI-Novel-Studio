import {ApiError} from '../api';
import type {StudioAsset} from './studioClient';
import {checkedModelReferenceInspection,type ModelReferenceInspection} from './studioModelReferenceContract';
export type ModelMaterial={index:number;name:string;base_color_factor:number[];metallic_factor:number;roughness_factor:number;emissive_factor:number[];alpha_mode:'OPAQUE'|'MASK'|'BLEND';alpha_cutoff:number;double_sided:boolean;declared_texture_slots:string[]};
export type ModelMaterials=ModelReferenceInspection&{material_inspection:{contract:'studio-static-glb-material-inspection/1';materials:ModelMaterial[];primitive_bindings:{mesh_index:number;primitive_index:number;material_index:number|null}[];default_factors_applied:true;color_space:'LINEAR_FACTORS';textures_decoded:false;texture_resources_validated:false;materials_rendered:false;external_resources_loaded:false;model_called:false}};
function invalid():never{throw new ApiError({status:200,code:'STUDIO_RESPONSE_INVALID',message:'材质检查回执与原素材不一致，请重新读取。'});}
function exact(value:unknown,keys:string[]):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))invalid();const r=value as Record<string,unknown>;if(Object.keys(r).length!==keys.length||keys.some(k=>!Object.hasOwn(r,k)))invalid();return r;}
function number(value:unknown,max=1){if(typeof value!=='number'||!Number.isFinite(value)||value<0||value>max)invalid();return value;}
function integer(value:unknown,max:number){const n=number(value,max);if(!Number.isSafeInteger(n))invalid();return n;}
function vector(value:unknown,length:number){if(!Array.isArray(value)||value.length!==length)invalid();value.forEach(n=>number(n));}
const slots=['baseColorTexture','metallicRoughnessTexture','normalTexture','occlusionTexture','emissiveTexture'];
export function checkedModelMaterials(value:unknown,asset:StudioAsset):ModelMaterials{
 const root=exact(value,['asset_snapshot','inspection','material_inspection']);const base=checkedModelReferenceInspection({asset_snapshot:root.asset_snapshot,inspection:root.inspection},asset);
 const flags=['textures_decoded','texture_resources_validated','materials_rendered','external_resources_loaded','model_called'];
 const raw=exact(root.material_inspection,['contract','materials','primitive_bindings','default_factors_applied','color_space',...flags]);
 if(raw.contract!=='studio-static-glb-material-inspection/1'||raw.default_factors_applied!==true||raw.color_space!=='LINEAR_FACTORS'||flags.some(k=>raw[k]!==false)||!Array.isArray(raw.materials)||raw.materials.length>128||!Array.isArray(raw.primitive_bindings)||raw.primitive_bindings.length!==base.inspection.primitive_count)invalid();
 raw.materials.forEach((value,i)=>{const m=exact(value,['index','name','base_color_factor','metallic_factor','roughness_factor','emissive_factor','alpha_mode','alpha_cutoff','double_sided','declared_texture_slots']);if(m.index!==i||typeof m.name!=='string'||m.name.length>200||/[\u0000-\u001f]/.test(m.name)||!['OPAQUE','MASK','BLEND'].includes(String(m.alpha_mode))||typeof m.double_sided!=='boolean')invalid();vector(m.base_color_factor,4);vector(m.emissive_factor,3);number(m.metallic_factor);number(m.roughness_factor);number(m.alpha_cutoff,1000000);if(!Array.isArray(m.declared_texture_slots)||m.declared_texture_slots.some(v=>typeof v!=='string'||!slots.includes(v))||JSON.stringify(m.declared_texture_slots)!==JSON.stringify(slots.filter(k=>(m.declared_texture_slots as string[]).includes(k))))invalid();});
 let mesh=0,primitive=0;
 raw.primitive_bindings.forEach((value,i)=>{const b=exact(value,['mesh_index','primitive_index','material_index']);integer(b.mesh_index,base.inspection.mesh_count-1);integer(b.primitive_index,127);if(i&&b.mesh_index===mesh+1){mesh++;primitive=0;}if(b.mesh_index!==mesh||b.primitive_index!==primitive++)invalid();if(b.material_index!==null)integer(b.material_index,(raw.materials as unknown[]).length-1);});
 if(mesh+1!==base.inspection.mesh_count)invalid();return structuredClone(value) as ModelMaterials;
}
