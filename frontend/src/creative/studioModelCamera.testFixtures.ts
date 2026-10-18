import {createHash} from 'node:crypto';
import {modelAsset,modelInspection} from './studioModelReference.testFixtures';
import type {ModelCameras,ModelCameraExport,ModelCameraSelection} from './studioModelCameraContract';
// Synthetic closed-wire fixtures for negative tests; owner-produced wire is tested separately.
export const cameraAsset=modelAsset(true);
export function cameraReview():ModelCameras {
  const base=modelInspection(cameraAsset,true);base.inspection.node_count=3;
  return {...base,camera_inspection:{contract:'studio-static-glb-cameras/1',space:'SCENE_WORLD_STATIC',coordinate_system:'GLTF_RH_Y_UP_METERS',matrix_layout:'COLUMN_MAJOR',scene_index:0,scene_selection:'DECLARED_DEFAULT',camera_definition_count:2,instances:[
    {node_index:0,camera_index:0,node_name:'Camera node',camera_name:'Source perspective',world_matrix:[1,0,0,0,0,1,0,0,0,0,1,0,120,10,-30,1],projection:{type:'perspective',yfov:0.75,znear:0.1,aspectRatio:null,zfar:null}},
    {node_index:1,camera_index:1,node_name:'Camera orthographic',camera_name:'Source orthographic',world_matrix:[0,0,-1,0,0,1,0,0,1,0,0,0,-20,0,0,1],projection:{type:'orthographic',xmag:3,ymag:2,znear:0,zfar:200}},
    {node_index:2,camera_index:0,node_name:'Shared camera',camera_name:'Source perspective',world_matrix:[1,0,0,0,0,1,0,0,0,0,1,0,20,0,30,1],projection:{type:'perspective',yfov:0.75,znear:0.1,aspectRatio:null,zfar:null}},
  ],rigid_transforms_only:true,animation_applied:false,model_called:false}};
}
export function cameraChoice(node=0):ModelCameraSelection {
  const {scene_index,scene_selection,instances}=cameraReview().camera_inspection;
  return {scene_index,scene_selection,camera:instances.find(camera=>camera.node_index===node)!};
}
export function cameraDocument(choice=cameraChoice()) {
  const {camera,scene_index,scene_selection}=choice,p=camera.projection;
  const projection=p.type==='perspective'?{yfov:p.yfov,znear:p.znear,...(p.aspectRatio===null?{}:{aspectRatio:p.aspectRatio}),...(p.zfar===null?{}:{zfar:p.zfar})}:{xmag:p.xmag,ymag:p.ymag,znear:p.znear,zfar:p.zfar};
  return {asset:{version:'2.0',generator:'Studio static camera exchange/1'},scene:0,scenes:[{nodes:[0]}],nodes:[{camera:0,matrix:camera.world_matrix,name:camera.node_name}],cameras:[{type:p.type,name:camera.camera_name,[p.type]:projection}],extras:{studio_camera_source:{contract:'studio-static-glb-camera-source/1',asset_id:cameraAsset.id,version:cameraAsset.version,sha256:cameraAsset.sha256,scene_index,scene_selection,node_index:camera.node_index,camera_index:camera.camera_index}}};
}
export function cameraExport(choice=cameraChoice()):ModelCameraExport {
  const bytes=Buffer.from(JSON.stringify(cameraDocument(choice))+'\n');
  return {asset_snapshot:cameraReview().asset_snapshot,content_base64:bytes.toString('base64'),camera_export:{contract:'studio-static-glb-camera-export/1',profile:'GLTF_2_CAMERA_ONLY',...structuredClone(choice),coordinate_system:'GLTF_RH_Y_UP_METERS',matrix_layout:'COLUMN_MAJOR',byte_count:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),animation_applied:false,model_called:false,asset_created:false,blender_import_acceptance:'NOT_RUN',unreal_import_acceptance:'NOT_RUN'}};
}
export function rewriteCameraDocument(value:ModelCameraExport, mutate:(document:ReturnType<typeof cameraDocument>)=>void) {
  const document=JSON.parse(Buffer.from(value.content_base64,'base64').toString('utf8'));mutate(document);
  const bytes=Buffer.from(JSON.stringify(document)+'\n');value.content_base64=bytes.toString('base64');value.camera_export.byte_count=bytes.length;value.camera_export.sha256=createHash('sha256').update(bytes).digest('hex');return value;
}
