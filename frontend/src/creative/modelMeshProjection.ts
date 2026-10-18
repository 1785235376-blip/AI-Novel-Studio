import type { ModelMeshPreview, ModelScenePreview } from './studioModelReferenceContract';
export type MeshFace={points:number[][];depth:number;shade:number};
/** Orthographic mesh-local diagnostic. Painter order is approximate, no scene/material render. */
export function projectModelMesh(receipt:ModelMeshPreview|ModelScenePreview,yaw:number,pitch:number):MeshFace[]{
 if(!Number.isFinite(yaw)||!Number.isFinite(pitch)||Math.abs(yaw)>180||Math.abs(pitch)>89)throw new Error('诊断视角无效。');
 const geometry='scene_preview' in receipt?receipt.scene_preview:receipt.mesh_preview;
 const bounds='scene_preview' in receipt?receipt.scene_preview.bounds:receipt.inspection.bounds,center=bounds.min.map((n,i)=>(n+bounds.max[i])/2),extent=Math.max(...bounds.max.map((n,i)=>n-bounds.min[i]))||1;
 const y=yaw*Math.PI/180,p=pitch*Math.PI/180,cy=Math.cos(y),sy=Math.sin(y),cp=Math.cos(p),sp=Math.sin(p),scale=90;
 const faces:MeshFace[]=[];
 for(const primitive of geometry.primitives){const points=primitive.positions.map(point=>{const [x,a,z]=point.map((n,i)=>(n-center[i])*2/extent),rx=cy*x+sy*z,rz=-sy*x+cy*z;return [rx,cp*a-sp*rz,sp*a+cp*rz];});
  for(const ids of primitive.triangles){const [a,b,c]=ids.map(id=>points[id]),u=b.map((n,i)=>n-a[i]),v=c.map((n,i)=>n-a[i]);const normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],length=Math.hypot(...normal);
   faces.push({points:[a,b,c].map(point=>[256+point[0]*scale,192-point[1]*scale]),depth:(a[2]+b[2]+c[2])/3,shade:Math.round(80+140*(length?Math.abs(normal[2])/length:0))});
  }
 }
 return faces.sort((a,b)=>a.depth-b.depth);
}
export const meshFacePoints=(face:MeshFace)=>face.points.map(point=>point.map(n=>n.toFixed(3)).join(',')).join(' ');
export function modelMeshSvg(faces:MeshFace[],wireframe:boolean,scene=false){
 return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 384" width="512" height="384"><title>'+ (scene?'Static scene diagnostic; materials and animation are not applied':'Mesh-local diagnostic; scene transforms and materials are not applied') +'</title>'+faces.map(face=>`<polygon points="${meshFacePoints(face)}" fill="${wireframe?'none':`rgb(${face.shade},${face.shade},${face.shade})`}" stroke="#777" stroke-width="0.7"/>`).join('')+'</svg>';
}
