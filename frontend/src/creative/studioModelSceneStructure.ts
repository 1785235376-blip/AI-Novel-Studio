import { projectModelMesh } from './modelMeshProjection';
import type { ModelScenePreview } from './studioModelReferenceContract';

type ScenePrimitive = ModelScenePreview['scene_preview']['primitives'][number];
export type ModelSceneStructureEntry = {
 key:string;
 label:string;
 nodeIndices:number[];
 meshIndices:number[];
 primitiveCount:number;
 positionCount:number;
 triangleCount:number;
 bounds:{min:number[];max:number[]};
 primitives:{nodeIndex:number;meshIndex:number;primitiveIndex:number;positionCount:number;triangleCount:number}[];
};

function entry(key:string,label:string,primitives:ScenePrimitive[]):ModelSceneStructureEntry {
 const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
 for(const primitive of primitives)for(const point of primitive.positions)point.forEach((value,index)=>{min[index]=Math.min(min[index],value);max[index]=Math.max(max[index],value);});
 return {key,label,nodeIndices:[...new Set(primitives.map(p=>p.node_index))],meshIndices:[...new Set(primitives.map(p=>p.mesh_index))],primitiveCount:primitives.length,
  positionCount:primitives.reduce((sum,p)=>sum+p.positions.length,0),triangleCount:primitives.reduce((sum,p)=>sum+p.triangles.length,0),bounds:{min,max},
  primitives:primitives.map(p=>({nodeIndex:p.node_index,meshIndex:p.mesh_index,primitiveIndex:p.primitive_index,positionCount:p.positions.length,triangleCount:p.triangles.length})),
 };
}

/** Pure, bounded view of an already checked scene receipt. Never reads raw GLB metadata. */
export function modelSceneStructure(receipt:ModelScenePreview) {
 const primitives=receipt.scene_preview.primitives;
 const nodeIndices=[...new Set(primitives.map(p=>p.node_index))].sort((a,b)=>a-b);
 const meshIndices=[...new Set(primitives.map(p=>p.mesh_index))].sort((a,b)=>a-b);
 return {
  all:entry('all','完整场景',primitives),
  instances:nodeIndices.map(index=>{const rows=primitives.filter(p=>p.node_index===index);return entry(`node:${index}`,`节点 #${index} · 网格 #${rows[0].mesh_index}`,rows);}),
  meshes:meshIndices.map(index=>entry(`mesh:${index}`,`网格 #${index}（所有实例）`,primitives.filter(p=>p.mesh_index===index))),
 };
}

/** Render an inspection overlay in the full scene's coordinate frame, without mutating its receipt. */
export function modelSceneHighlightFaces(receipt:ModelScenePreview,selection:ModelSceneStructureEntry|undefined,yaw:number,pitch:number) {
 if(!selection||selection.key==='all')return [];
 const nodes=new Set(selection.nodeIndices);
 const primitives=receipt.scene_preview.primitives.filter(p=>nodes.has(p.node_index));
 // This is a local rendering view only; the original checked receipt remains the export source.
 return projectModelMesh({...receipt,scene_preview:{...receipt.scene_preview,primitives}},yaw,pitch);
}
