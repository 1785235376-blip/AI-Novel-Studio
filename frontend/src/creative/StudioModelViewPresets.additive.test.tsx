// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {StudioModelMeshPreview} from './StudioModelMeshPreview';
import {type ModelMeshPreview,type ModelScenePreview} from './studioModelReferenceContract';
import {modelAsset,modelInspection} from './studioModelReference.testFixtures';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));

const mesh=():ModelMeshPreview=>({...modelInspection(),mesh_preview:{contract:'studio-static-glb-mesh-preview/1',space:'MESH_LOCAL_UNTRANSFORMED',primitives:[{positions:[[-1,0,0],[1,0,0],[0,2,0]],triangles:[[0,1,2]]}],scene_transforms_applied:false,materials_rendered:false,decimated:false,model_called:false}});
const scene=():ModelScenePreview=>{const base=modelInspection();base.inspection.node_count=1;return {...base,scene_preview:{contract:'studio-static-glb-scene-preview/1',space:'SCENE_WORLD_STATIC',scene_index:0,selection:'DECLARED_DEFAULT',traversed_nodes:1,mesh_instances:1,position_count:3,triangle_count:1,primitives:[{node_index:0,mesh_index:0,primitive_index:0,positions:[[-1,0,0],[1,0,0],[0,2,0]],triangles:[[0,1,2]]}],bounds:{min:[-1,0,0],max:[1,2,0]},scene_transforms_applied:true,materials_rendered:false,animation_applied:false,decimated:false,model_called:false}};};
afterEach(()=>{cleanup();vi.clearAllMocks();});

it('offers repeatable axis views, marks slider edits and restores the original diagnostic view without another read or download',async()=>{
 const read=vi.fn(async()=>mesh());
 render(<StudioModelMeshPreview scope={{}} asset={modelAsset()} disabled={false} canExport isCurrent={()=>true} read={read}/>);
 expect(screen.queryByLabelText('诊断方向预设')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 网格诊断'}));
 const svg=await screen.findByRole('img'),original=svg.querySelector('polygon')!.getAttribute('points');
 const preset=screen.getByLabelText('诊断方向预设') as HTMLSelectElement;
 expect(preset.value).toBe('default');
 for(const [value,yaw] of [['positive-z','0'],['negative-z','180'],['negative-x','90'],['positive-x','-90']]){
  fireEvent.change(preset,{target:{value}});
  expect((screen.getByLabelText('诊断水平视角') as HTMLInputElement).value).toBe(yaw);
  expect((screen.getByLabelText('诊断俯仰视角') as HTMLInputElement).value).toBe('0');
 }
 fireEvent.change(preset,{target:{value:'positive-z'}});
 expect(svg.querySelector('polygon')!.getAttribute('points')).toBe('166.000,282.000 346.000,282.000 256.000,102.000');
 fireEvent.change(screen.getByLabelText('诊断水平视角'),{target:{value:'42'}});
 expect(preset.value).toBe('custom');
 expect(screen.getByText(/当前诊断视角：水平 42° · 俯仰 0°/)).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'复位诊断视角'}));
 expect(preset.value).toBe('default');
 expect(svg.querySelector('polygon')!.getAttribute('points')).toBe(original);
 expect(read).toHaveBeenCalledTimes(1);
 expect(downloadPortableBlob).not.toHaveBeenCalled();
});

it('uses the selected scene direction only when explicitly exporting and respects blocked controls',async()=>{
 const readScene=vi.fn(async()=>scene()),onDepth=vi.fn(()=>new Promise<never>(()=>{}));
 const props={scope:{},asset:modelAsset(),disabled:false,canExport:true,isCurrent:()=>true,read:vi.fn(),readScene,onDepth};
 const view=render(<StudioModelMeshPreview {...props}/>);
 fireEvent.change(screen.getByLabelText('诊断坐标空间'),{target:{value:'scene'}});
 fireEvent.click(screen.getByRole('button',{name:'明确读取 GLB 静态场景'}));
 await screen.findByRole('img');
 fireEvent.change(screen.getByLabelText('诊断方向预设'),{target:{value:'negative-x'}});
 expect(onDepth).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'导出当前视角深度参考 PNG'}));
 expect(onDepth).toHaveBeenCalledTimes(1);
 expect(onDepth.mock.calls[0]).toEqual([modelAsset(),{yaw:90,pitch:0},expect.any(AbortSignal)]);
 view.rerender(<StudioModelMeshPreview {...props} disabled/>);
 expect((screen.getByLabelText('诊断方向预设') as HTMLSelectElement).disabled).toBe(true);
 expect((screen.getByRole('button',{name:'复位诊断视角'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('诊断方向预设'),{target:{value:'positive-z'}});
 fireEvent.click(screen.getByRole('button',{name:'复位诊断视角'}));
 expect((screen.getByLabelText('诊断水平视角') as HTMLInputElement).value).toBe('90');
 expect(readScene).toHaveBeenCalledTimes(1);
});
