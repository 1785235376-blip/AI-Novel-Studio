// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {checkedModelScenePreview,type ModelScenePreview} from './studioModelReferenceContract';
import {modelAsset,modelInspection} from './studioModelReference.testFixtures';
import {StudioModelMeshPreview} from './StudioModelMeshPreview';
import {projectModelMesh,modelMeshSvg} from './modelMeshProjection';
import {studioClient} from './studioClient';
const scene=():ModelScenePreview=>{const base=modelInspection();base.inspection.node_count=2;return {...base,scene_preview:{contract:'studio-static-glb-scene-preview/1',space:'SCENE_WORLD_STATIC',scene_index:0,selection:'DECLARED_DEFAULT',traversed_nodes:2,mesh_instances:2,position_count:6,triangle_count:2,primitives:[{node_index:0,mesh_index:0,primitive_index:0,positions:[[-1,0,0],[1,0,0],[0,2,0]],triangles:[[0,1,2]]},{node_index:1,mesh_index:0,primitive_index:0,positions:[[99,0,0],[101,0,0],[100,2,0]],triangles:[[0,1,2]]}],bounds:{min:[-1,0,0],max:[101,2,0]},scene_transforms_applied:true,materials_rendered:false,animation_applied:false,decimated:false,model_called:false}};};
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('checks exact source, instance identifiers, topology and independently recomputed world bounds',()=>{
 expect(checkedModelScenePreview(scene(),modelAsset())).toEqual(scene());
 for(const mutate of [(r:ModelScenePreview)=>{r.scene_preview.bounds.max[0]=102;},(r:ModelScenePreview)=>{r.scene_preview.primitives[1].node_index=0;},(r:ModelScenePreview)=>{r.scene_preview.mesh_instances=1;},(r:ModelScenePreview)=>{r.scene_preview.primitives[1].triangles[0][0]=3;},(r:ModelScenePreview)=>{r.asset_snapshot.version++;}]){const value=scene();mutate(value);expect(()=>checkedModelScenePreview(value,modelAsset())).toThrow();}
 const faces=projectModelMesh(scene(),0,0);expect(faces).toHaveLength(2);expect(faces[0].points[0][0]).toBeLessThan(faces[1].points[0][0]);expect(modelMeshSvg(faces,true,true)).toContain('Static scene diagnostic');
});
it('uses explicit scene selection and read, then clears scene data when switching back',async()=>{
 const read=vi.fn(),readScene=vi.fn(async()=>scene());render(<StudioModelMeshPreview scope={{}} asset={modelAsset()} disabled={false} isCurrent={()=>true} read={read} readScene={readScene}/>);
 fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'scene'}});expect(readScene).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('明确读取 GLB 静态场景'));const svg=await screen.findByRole('img',{name:'实际 GLB 静态场景几何示意'});expect(svg.querySelectorAll('polygon')).toHaveLength(2);expect(read).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'mesh'}});expect(screen.queryByRole('img')).toBeNull();expect(read).not.toHaveBeenCalled();
});
it('aborts and discards a late scene response after coordinate-space replacement',async()=>{
 let resolve!:(value:ModelScenePreview)=>void;const readScene=vi.fn((_a:unknown,_s:AbortSignal)=>new Promise<ModelScenePreview>(done=>{resolve=done;}));render(<StudioModelMeshPreview scope={{}} asset={modelAsset()} disabled={false} isCurrent={()=>true} read={vi.fn()} readScene={readScene}/>);
 fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'scene'}});fireEvent.click(screen.getByText('明确读取 GLB 静态场景'));const signal=readScene.mock.calls[0][1];fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'mesh'}});expect(signal.aborted).toBe(true);await act(async()=>resolve(scene()));expect(screen.queryByRole('img')).toBeNull();
});
it('routes through the original captured asset client and exact scene endpoint',async()=>{
 const fetch=vi.fn(async()=>new Response(JSON.stringify(scene()),{status:200}));vi.stubGlobal('fetch',fetch);
 const client=studioClient('project',{sessionToken:'fixture-session'});expect(await client.inspectModelScene(modelAsset())).toEqual(scene());expect(fetch.mock.calls).toHaveLength(1);expect(String((fetch.mock.calls[0] as unknown[])[0])).toContain('/model-reference/scene-preview');
});
