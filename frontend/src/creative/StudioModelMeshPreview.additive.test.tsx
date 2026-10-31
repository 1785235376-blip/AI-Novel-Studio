// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StudioModelMeshPreview } from './StudioModelMeshPreview';
import { checkedModelMeshPreview, type ModelMeshPreview } from './studioModelReferenceContract';
import { projectModelMesh, modelMeshSvg } from './modelMeshProjection';
import { modelAsset, modelInspection } from './studioModelReference.testFixtures';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const receipt=():ModelMeshPreview=>({...modelInspection(),mesh_preview:{contract:'studio-static-glb-mesh-preview/1',space:'MESH_LOCAL_UNTRANSFORMED',primitives:[{positions:[[-1,0,0],[1,0,0],[0,2,0]],triangles:[[0,1,2]]}],scene_transforms_applied:false,materials_rendered:false,decimated:false,model_called:false}});
it('checks exact source and complete bounded topology rather than silently truncating',()=>{
 expect(checkedModelMeshPreview(receipt(),modelAsset())).toEqual(receipt());const changed=receipt();changed.mesh_preview.primitives[0].triangles[0][1]=99;expect(()=>checkedModelMeshPreview(changed,modelAsset())).toThrow();
 const fake=receipt();fake.inspection.bounds.max[1]=10;expect(()=>checkedModelMeshPreview(fake,modelAsset())).toThrow();const large=receipt();large.mesh_preview.primitives[0].triangles=Array.from({length:2049},()=>[0,1,2]);expect(()=>checkedModelMeshPreview(large,modelAsset())).toThrow();
});
it('projects actual mesh-local geometry deterministically without changing source data',()=>{
 const value=receipt(),before=structuredClone(value),faces=projectModelMesh(value,0,0);expect(faces).toHaveLength(1);expect(faces[0].points).toEqual([[166,282],[346,282],[256,102]]);expect(value).toEqual(before);expect(projectModelMesh(value,90,0)[0].points).not.toEqual(faces[0].points);expect(()=>projectModelMesh(value,NaN,0)).toThrow();
 const svg=modelMeshSvg(faces,false),parsed=new DOMParser().parseFromString(svg,'image/svg+xml');expect(parsed.querySelector('parsererror')).toBeNull();expect(parsed.querySelectorAll('polygon')).toHaveLength(1);expect(svg).not.toMatch(/script|href|onload|foreignObject/i);
});
it('requires explicit geometry read, offers local camera and explicit SVG download without saving',async()=>{
 const read=vi.fn(async()=>receipt());render(<StudioModelMeshPreview scope={{}} asset={modelAsset()} disabled={false} canExport={true} isCurrent={()=>true} read={read}/>);expect(read).not.toHaveBeenCalled();expect(screen.queryByRole('img')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 网格诊断'}));const svg=await screen.findByRole('img',{name:'实际 GLB 网格局部几何示意'});expect(svg.querySelectorAll('polygon')).toHaveLength(1);
 const original=svg.querySelector('polygon')!.getAttribute('points');fireEvent.change(screen.getByLabelText('诊断水平视角'),{target:{value:'90'}});expect(svg.querySelector('polygon')!.getAttribute('points')).not.toBe(original);fireEvent.click(screen.getByLabelText('线框显示（关闭后为灰阶示意）'));expect(svg.querySelector('polygon')!.getAttribute('fill')).toMatch(/^rgb/);
 expect(downloadPortableBlob).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'下载当前网格诊断 SVG'}));expect(downloadPortableBlob).toHaveBeenCalledTimes(1);expect(vi.mocked(downloadPortableBlob).mock.calls[0][0].type).toBe('image/svg+xml');expect(read).toHaveBeenCalledTimes(1);
});
it('aborts old-source reads and never shows late geometry after an asset version change',async()=>{
 let resolve!:(value:ModelMeshPreview)=>void;const read=vi.fn((_asset:unknown,_signal:AbortSignal)=>new Promise<ModelMeshPreview>(done=>{resolve=done;})),scope={};const view=render(<StudioModelMeshPreview scope={scope} asset={modelAsset()} disabled={false} isCurrent={()=>true} read={read}/>);fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 网格诊断'}));const signal=read.mock.calls[0][1];view.rerender(<StudioModelMeshPreview scope={scope} asset={{...modelAsset(),version:2}} disabled={false} isCurrent={()=>true} read={read}/>);expect(signal.aborted).toBe(true);await act(async()=>resolve(receipt()));expect(screen.queryByRole('img')).toBeNull();
});

it('does not infer file-export permission from readable geometry',async()=>{
 render(<StudioModelMeshPreview scope={{}} asset={modelAsset()} disabled={false} canExport={false} isCurrent={()=>true} read={async()=>receipt()}/>);fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 网格诊断'}));await screen.findByRole('img');fireEvent.click(screen.getByRole('button',{name:'下载当前网格诊断 SVG'}));expect(downloadPortableBlob).not.toHaveBeenCalled();
});
