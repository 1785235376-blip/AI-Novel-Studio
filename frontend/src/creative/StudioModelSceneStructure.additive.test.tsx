// @vitest-environment jsdom
// Synthetic, contract-checked scene responses. No backend, renderer, or model service is invoked.
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {StudioModelMeshPreview} from './StudioModelMeshPreview';
import {checkedModelScenePreview,type ModelScenePreview} from './studioModelReferenceContract';
import {modelAsset,modelInspection} from './studioModelReference.testFixtures';
import {modelSceneHighlightFaces,modelSceneStructure} from './studioModelSceneStructure';
import {meshFacePoints,projectModelMesh} from './modelMeshProjection';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
afterEach(()=>{cleanup();vi.clearAllMocks();});

function scene():ModelScenePreview {
 const base=modelInspection();base.inspection.node_count=3;
 return {...base,scene_preview:{contract:'studio-static-glb-scene-preview/1',space:'SCENE_WORLD_STATIC',scene_index:0,selection:'DECLARED_DEFAULT',traversed_nodes:3,mesh_instances:2,position_count:6,triangle_count:2,
  primitives:[{node_index:0,mesh_index:0,primitive_index:0,positions:[[-1,0,0],[1,0,0],[0,2,0]],triangles:[[0,1,2]]},{node_index:2,mesh_index:0,primitive_index:0,positions:[[99,0,0],[101,0,0],[100,2,0]],triangles:[[0,1,2]]}],
  bounds:{min:[-1,0,0],max:[101,2,0]},scene_transforms_applied:true,materials_rendered:false,animation_applied:false,decimated:false,model_called:false}};
}
function props(){return {scope:{},asset:modelAsset(),disabled:false,canExport:true,isCurrent:()=>true,read:vi.fn(),readScene:vi.fn(async()=>scene())};}
async function readScene(){fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'scene'}});fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));return screen.findByRole('region',{name:'静态场景结构检查'});}
function select(key:string){fireEvent.change(screen.getByLabelText('结构高亮'),{target:{value:key}});}
function highlight(){return screen.getByRole('img').querySelector('g');}

it('builds instance and shared-mesh inventories only from checked world geometry, without mutating the receipt',()=>{
 const receipt=checkedModelScenePreview(scene(),modelAsset()),before=structuredClone(receipt),structure=modelSceneStructure(receipt);
 expect(structure.instances.map(value=>[value.key,value.meshIndices,value.bounds])).toEqual([
  ['node:0',[0],{min:[-1,0,0],max:[1,2,0]}],['node:2',[0],{min:[99,0,0],max:[101,2,0]}],
 ]);
 expect(structure.all).toMatchObject({nodeIndices:[0,2],primitiveCount:2,positionCount:6,triangleCount:2,bounds:receipt.scene_preview.bounds});
 expect(structure.meshes).toHaveLength(1);expect(structure.meshes[0].nodeIndices).toEqual([0,2]);
 const faces=projectModelMesh(receipt,35,25),highlighted=modelSceneHighlightFaces(receipt,structure.instances[1],35,25);
 expect(highlighted).toHaveLength(1);expect(faces.map(meshFacePoints)).toContain(meshFacePoints(highlighted[0]));
 expect(modelSceneHighlightFaces(receipt,structure.meshes[0],35,25)).toEqual(faces);
 expect(modelSceneHighlightFaces(receipt,structure.all,35,25)).toEqual([]);expect(receipt).toEqual(before);
});

it('groups multiple primitives and meshes with deterministic node order and bounded counts',()=>{
 const value=scene();value.inspection.mesh_count=2;value.inspection.primitive_count=3;
 const second=value.scene_preview.primitives[1];second.mesh_index=1;
 value.scene_preview.primitives.push({...structuredClone(value.scene_preview.primitives[0]),primitive_index:1});
 value.scene_preview.position_count=9;value.scene_preview.triangle_count=3;
 const structure=modelSceneStructure(checkedModelScenePreview(value,modelAsset()));
 expect(structure.instances.map(item=>item.key)).toEqual(['node:0','node:2']);
 expect(structure.instances[0]).toMatchObject({primitiveCount:2,positionCount:6,triangleCount:2});
 expect(structure.instances[0].primitives.map(p=>p.primitiveIndex)).toEqual([0,1]);
 expect(structure.meshes.map(item=>item.nodeIndices)).toEqual([[0],[2]]);
});

it('retains the full checked geometry budget without truncating the inventory or highlighted mesh',()=>{
 const value=scene();value.inspection.node_count=128;value.scene_preview.traversed_nodes=128;value.scene_preview.mesh_instances=128;
 const original=value.scene_preview.primitives[0];
 value.scene_preview.primitives=Array.from({length:128},(_,node_index)=>({...original,node_index,
  positions:Array.from({length:32},(_,index)=>[...original.positions[index%3]]),triangles:Array.from({length:16},()=>[0,1,2]),
 }));
 value.scene_preview.position_count=4096;value.scene_preview.triangle_count=2048;value.scene_preview.bounds={min:[-1,0,0],max:[1,2,0]};
 const receipt=checkedModelScenePreview(value,modelAsset()),structure=modelSceneStructure(receipt);
 expect(structure.instances).toHaveLength(128);expect(structure.all).toMatchObject({primitiveCount:128,positionCount:4096,triangleCount:2048});
 expect(modelSceneHighlightFaces(receipt,structure.meshes[0],35,25)).toHaveLength(2048);
});

it('requires an explicit scene read and provides accessible instance and shared-mesh selection with no extra reads',async()=>{
 const source=props();render(<StudioModelMeshPreview {...source}/>);
 expect(screen.queryByRole('region',{name:'静态场景结构检查'})).toBeNull();expect(source.readScene).not.toHaveBeenCalled();
 const inspector=await readScene();expect(inspector.textContent).toContain('已遍历 3 个节点 · 2 个网格实例 · 1 个引用网格');
 expect(screen.getByLabelText<HTMLSelectElement>('结构高亮').value).toBe('all');expect(highlight()).toBeNull();
 select('node:2');expect(within(inspector).getByRole('status').textContent).toContain('节点 #2 · 网格 #0：1 个实例 · 1 个图元实例 · 3 个位置 · 1 个三角形');
 expect(inspector.textContent).toContain('最小 [99, 0, 0] · 最大 [101, 2, 0]');expect(highlight()?.querySelectorAll('polygon')).toHaveLength(1);
 expect(highlight()?.getAttribute('aria-label')).toBe('结构高亮：节点 #2 · 网格 #0');
 const oldPoints=highlight()?.querySelector('polygon')?.getAttribute('points');
 fireEvent.change(screen.getByLabelText('诊断水平视角'),{target:{value:'90'}});expect(highlight()?.querySelector('polygon')?.getAttribute('points')).not.toBe(oldPoints);
 select('mesh:0');expect(highlight()?.querySelectorAll('polygon')).toHaveLength(2);
 fireEvent.click(screen.getByRole('button',{name:'清除结构高亮'}));expect(highlight()).toBeNull();
 expect(source.readScene).toHaveBeenCalledTimes(1);expect(source.read).not.toHaveBeenCalled();expect(downloadPortableBlob).not.toHaveBeenCalled();
});

it('keeps full-scene exports independent of the inspection highlight and preserves export permission',async()=>{
 const source=props(),view=render(<StudioModelMeshPreview {...source}/>);await readScene();select('node:2');
 fireEvent.click(screen.getByRole('button',{name:'下载当前场景诊断 SVG'}));
 expect(downloadPortableBlob).toHaveBeenCalledTimes(1);
 const blob=vi.mocked(downloadPortableBlob).mock.calls[0][0];
 const text=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsText(blob);});
 expect((text.match(/<polygon/g)||[])).toHaveLength(2);expect(text).not.toContain('结构高亮');
 view.rerender(<StudioModelMeshPreview {...source} canExport={false}/>);
 fireEvent.click(screen.getByRole('button',{name:'下载当前场景诊断 SVG'}));expect(downloadPortableBlob).toHaveBeenCalledTimes(1);
});

it('retires selection as soon as a reread starts and never revives it for an identical receipt',async()=>{
 let resolve!:(value:ModelScenePreview)=>void;const source=props();render(<StudioModelMeshPreview {...source}/>);await readScene();select('node:2');
 source.readScene.mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
 fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));
 expect(screen.queryByLabelText('结构高亮')).toBeNull();expect(screen.queryByRole('img')).toBeNull();
 await act(async()=>resolve(scene()));expect(screen.getByLabelText<HTMLSelectElement>('结构高亮').value).toBe('all');expect(highlight()).toBeNull();
});

it('discards structure on a failed or malformed reread instead of reusing the earlier successful selection',async()=>{
 const source=props();render(<StudioModelMeshPreview {...source}/>);await readScene();select('node:2');
 source.readScene.mockRejectedValueOnce(new Error('blocked'));
 fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));await screen.findByText('blocked');expect(screen.queryByLabelText('结构高亮')).toBeNull();
 const malformed=scene();malformed.scene_preview.bounds.max[0]=999;source.readScene.mockResolvedValueOnce(malformed);
 fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));await screen.findByText('GLB 检查回执与当前素材版本不一致，请重新读取。');expect(screen.queryByLabelText('结构高亮')).toBeNull();
});

it('never displays unchecked names, altered source snapshots or forged instance identifiers',async()=>{
 for(const corrupt of [(v:ModelScenePreview)=>{Object.assign(v.scene_preview.primitives[0],{node_name:'untrusted name'});},(v:ModelScenePreview)=>{v.asset_snapshot.version++;},(v:ModelScenePreview)=>{v.scene_preview.primitives[1].node_index=0;}]){
  const source=props(),value=scene();corrupt(value);source.readScene.mockResolvedValue(value);const view=render(<StudioModelMeshPreview {...source}/>);
  fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'scene'}});fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));
  await screen.findByText('GLB 检查回执与当前素材版本不一致，请重新读取。');expect(screen.queryByLabelText('结构高亮')).toBeNull();expect(screen.queryByText('untrusted name')).toBeNull();view.unmount();
 }
});

it('retires structure across asset, scope and coordinate-space ABA changes',async()=>{
 const source=props(),view=render(<StudioModelMeshPreview {...source}/>);await readScene();select('node:2');
 view.rerender(<StudioModelMeshPreview {...source} asset={{...source.asset,version:2}}/>);view.rerender(<StudioModelMeshPreview {...source}/>);
 expect(screen.queryByLabelText('结构高亮')).toBeNull();await readScene();expect(screen.getByLabelText<HTMLSelectElement>('结构高亮').value).toBe('all');select('node:2');
 view.rerender(<StudioModelMeshPreview {...source} scope={{}}/>);view.rerender(<StudioModelMeshPreview {...source}/>);expect(screen.queryByLabelText('结构高亮')).toBeNull();
 await readScene();select('node:2');fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'mesh'}});await readScene();expect(screen.getByLabelText<HTMLSelectElement>('结构高亮').value).toBe('all');
});

it('blocks disabled or stale-owner selection and retires a selection after authorization visibility is lost',async()=>{
 const source=props(),view=render(<StudioModelMeshPreview {...source}/>);await readScene();select('node:2');
 view.rerender(<StudioModelMeshPreview {...source} disabled/>);select('mesh:0');expect(screen.getByLabelText<HTMLSelectElement>('结构高亮').value).toBe('node:2');
 view.rerender(<StudioModelMeshPreview {...source} isCurrent={()=>false}/>);expect(screen.queryByRole('img')).toBeNull();
 view.rerender(<StudioModelMeshPreview {...source}/>);expect(screen.getByLabelText<HTMLSelectElement>('结构高亮').value).toBe('all');expect(highlight()).toBeNull();
});

it('aborts a pending old scene across a scope ABA and rejects its late response',async()=>{
 let resolve!:(value:ModelScenePreview)=>void;const source=props();source.readScene.mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
 const view=render(<StudioModelMeshPreview {...source}/>);fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'scene'}});fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));
 const signal=(source.readScene.mock.calls[0] as unknown as [unknown,AbortSignal])[1];
 view.rerender(<StudioModelMeshPreview {...source} scope={{}}/>);view.rerender(<StudioModelMeshPreview {...source}/>);expect(signal.aborted).toBe(true);
 await act(async()=>resolve(scene()));expect(screen.queryByLabelText('结构高亮')).toBeNull();expect(screen.queryByRole('img')).toBeNull();
});
