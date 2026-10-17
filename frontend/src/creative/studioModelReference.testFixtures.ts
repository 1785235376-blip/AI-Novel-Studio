import { createHash } from 'node:crypto';
import type { StudioAsset } from './studioClient';
import type { ModelReferenceInspection } from './studioModelReferenceContract';
// Synthetic response metadata paired with a genuine small GLB byte fixture.
export function modelGlbBytes(){
 const document={asset:{version:'2.0'},buffers:[{byteLength:36}],bufferViews:[{buffer:0,byteLength:36}],accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3'}],meshes:[{primitives:[{attributes:{POSITION:0}}]}]};
 let json=JSON.stringify(document);json+=' '.repeat((4-json.length%4)%4);const encoded=new TextEncoder().encode(json),bytes=new Uint8Array(12+8+encoded.length+8+36),view=new DataView(bytes.buffer);
 view.setUint32(0,0x46546c67,true);view.setUint32(4,2,true);view.setUint32(8,bytes.length,true);view.setUint32(12,encoded.length,true);view.setUint32(16,0x4e4f534a,true);bytes.set(encoded,20);const offset=20+encoded.length;view.setUint32(offset,36,true);view.setUint32(offset+4,0x004e4942,true);[-1,0,0,1,0,0,0,2,0].forEach((n,i)=>view.setFloat32(offset+8+i*4,n,true));return bytes;
}
export function modelAsset():StudioAsset{const bytes=modelGlbBytes();return {id:'model-reference',novel_id:'project',branch_id:null,filename:'triangle.glb',kind:'model',media_type:'model/gltf-binary',size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),version:1,created_at:'2026-10-17',updated_at:'2026-10-17',deleted_at:null};}
export function modelInspection(asset=modelAsset()):ModelReferenceInspection{return {asset_snapshot:{id:asset.id,kind:'ASSET',asset_kind:'model',version:asset.version,digest:asset.sha256},inspection:{contract:'studio-static-glb-inspection/1',format:'GLB_2_STATIC_TRIANGLE_GEOMETRY',byte_count:asset.size,sha256:asset.sha256,mesh_count:1,node_count:0,primitive_count:1,position_count_per_primitive:3,triangle_count_per_primitive:1,bounds:{space:'MESH_LOCAL_UNTRANSFORMED',min:[-1,0,0],max:[1,2,0]},scene_transforms_applied:false,materials_rendered:false,textures_decoded:false,full_gltf_conformance_verified:false,external_resources_loaded:false,model_called:false,preview_available:false,frame_export_available:false}};}
