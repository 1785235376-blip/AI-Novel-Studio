// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {ApiError} from '../api';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
import {StudioModelCameraInspection} from './StudioModelCameraInspection';
import type {ModelCameras,ModelCameraExport,ModelCameraSelection} from './studioModelCameraContract';
import type {StudioAsset} from './studioClient';
import {cameraAsset,cameraReview,cameraExport} from './studioModelCamera.testFixtures';

vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.clearAllMocks();});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const readButton=()=>screen.getByRole('button',{name:'明确读取 GLB 源相机'});
const exportButton=()=>screen.getByRole('button',{name:'导出所选源相机 glTF'});
const selector=()=>screen.getByLabelText('选择源相机实例') as HTMLSelectElement;
async function choose(node='0') {fireEvent.click(readButton());await screen.findByLabelText('选择源相机实例');fireEvent.change(selector(),{target:{value:node}});}
function basic() {return {scope:{},asset:cameraAsset,disabled:false,canExport:true,isCurrent:()=>true,read:vi.fn(async()=>cameraReview()),request:vi.fn(async(_asset:StudioAsset,selection:ModelCameraSelection)=>cameraExport(selection))};}

it('requires separate explicit read, node selection and verified download with accurate boundaries',async()=>{
  const props=basic();render(<StudioModelCameraInspection {...props}/>);
  expect(props.read).not.toHaveBeenCalled();expect(props.request).not.toHaveBeenCalled();
  fireEvent.click(readButton());await screen.findByLabelText('选择源相机实例');expect(selector().value).toBe('');
  expect((exportButton() as HTMLButtonElement).disabled).toBe(true);expect(props.request).not.toHaveBeenCalled();
  fireEvent.change(selector(),{target:{value:'0'}});expect(screen.getByText(/源文件未指定，取决于目标视口/)).toBeTruthy();expect(screen.getByText(/未指定，保留无限远/)).toBeTruthy();
  fireEvent.click(exportButton());await screen.findByText('源相机 glTF 校验通过，已发起下载；目标软件导入尚未验收。');
  expect(props.request).toHaveBeenCalledTimes(1);expect(downloadPortableBlob).toHaveBeenCalledTimes(1);
  const [blob,name]=vi.mocked(downloadPortableBlob).mock.calls[0];expect(blob.type).toBe('model/gltf+json');expect(name).toBe(`source-camera-${cameraAsset.id}-node-0.gltf`);
  expect(screen.getByText(/Blender 与 Unreal 的目标导入验收均未运行/)).toBeTruthy();expect(screen.queryByRole('img')).toBeNull();
  fireEvent.change(selector(),{target:{value:'1'}});expect(screen.getByText(/水平半宽 3 米/)).toBeTruthy();expect(screen.queryByText(/已发起下载/)).toBeNull();
  fireEvent.click(readButton());await screen.findByLabelText('选择源相机实例');expect(selector().value).toBe('');
});
it('shows zero-camera state without inventing a selection or export',async()=>{
  const review=cameraReview();review.camera_inspection.instances=[];review.camera_inspection.camera_definition_count=0;
  const props={...basic(),read:vi.fn(async()=>review)};render(<StudioModelCameraInspection {...props}/>);fireEvent.click(readButton());
  await screen.findByText(/当前场景没有源相机实例/);expect(screen.queryByLabelText('选择源相机实例')).toBeNull();expect(screen.queryByRole('button',{name:'导出所选源相机 glTF'})).toBeNull();expect(props.request).not.toHaveBeenCalled();
});
it.each([undefined,false])('allows read but never exports without explicit export authority (%s)',async canExport=>{
  const props={...basic(),canExport};render(<StudioModelCameraInspection {...props}/>);await choose();fireEvent.click(exportButton());expect(props.read).toHaveBeenCalledTimes(1);expect(props.request).not.toHaveBeenCalled();expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it('keeps unsupported rigid-transform error visible and permits only an explicit retry',async()=>{
  const props={...basic(),read:vi.fn(async()=>{throw new ApiError({status:422,code:'MODEL_REFERENCE_GLB_CAMERA_NONRIGID_UNSUPPORTED',message:'Unsupported'});})};render(<StudioModelCameraInspection {...props}/>);fireEvent.click(readButton());await screen.findByText(/源相机或祖先节点含缩放/);expect(props.read).toHaveBeenCalledTimes(1);expect(props.request).not.toHaveBeenCalled();
});
it('refuses export response with damaged bytes',async()=>{
  const props={...basic(),request:vi.fn(async()=>({...cameraExport(),content_base64:'AAAA'}))};render(<StudioModelCameraInspection {...props}/>);await choose();fireEvent.click(exportButton());await screen.findByText('相机回执、原素材或 glTF 文件校验不一致，未下载。');expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it('aborts pending export when selected camera changes, including selection ABA',async()=>{
  let finish!:(value:ModelCameraExport)=>void;
  const request=vi.fn((_asset:StudioAsset,_choice:ModelCameraSelection,_signal:AbortSignal)=>new Promise<ModelCameraExport>(resolve=>{finish=resolve;}));
  render(<StudioModelCameraInspection {...basic()} request={request}/>);await choose();fireEvent.click(exportButton());const signal=request.mock.calls[0][2];
  fireEvent.change(selector(),{target:{value:'1'}});fireEvent.change(selector(),{target:{value:'0'}});expect(signal.aborted).toBe(true);
  await act(async()=>finish(cameraExport()));expect(downloadPortableBlob).not.toHaveBeenCalled();expect(screen.queryByText(/已发起下载/)).toBeNull();
});
it.each(['source','scope','authority','disabled','identity'] as const)('aborts a pending camera read on %s ABA and drops old receipts',async change=>{
  let finish!:(value:ModelCameras)=>void;
  const read=vi.fn((_asset:StudioAsset,_signal:AbortSignal)=>new Promise<ModelCameras>(resolve=>{finish=resolve;}));
  const props={...basic(),read},view=render(<StudioModelCameraInspection {...props}/>);fireEvent.click(readButton());
  const changed=change==='source'?{asset:{...cameraAsset,version:2}}:change==='scope'?{scope:{}}:change==='authority'?{canExport:false}:change==='disabled'?{disabled:true}:{isCurrent:()=>false};
  view.rerender(<StudioModelCameraInspection {...props} {...changed}/>);view.rerender(<StudioModelCameraInspection {...props}/>);
  expect(read.mock.calls[0][1].aborted).toBe(true);await act(async()=>finish(cameraReview()));expect(screen.queryByLabelText('选择源相机实例')).toBeNull();expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it.each(['source','scope','authority','disabled','identity'] as const)('aborts a pending export on %s ABA and clears selection',async change=>{
  let finish!:(value:ModelCameraExport)=>void;
  const request=vi.fn((_asset:StudioAsset,_choice:ModelCameraSelection,_signal:AbortSignal)=>new Promise<ModelCameraExport>(resolve=>{finish=resolve;}));
  const props={...basic(),request},view=render(<StudioModelCameraInspection {...props}/>);await choose();fireEvent.click(exportButton());
  const changed=change==='source'?{asset:{...cameraAsset,sha256:'f'.repeat(64)}}:change==='scope'?{scope:{}}:change==='authority'?{canExport:false}:change==='disabled'?{disabled:true}:{isCurrent:()=>false};
  view.rerender(<StudioModelCameraInspection {...props} {...changed}/>);view.rerender(<StudioModelCameraInspection {...props}/>);
  expect(request.mock.calls[0][2].aborted).toBe(true);await act(async()=>finish(cameraExport()));expect(downloadPortableBlob).not.toHaveBeenCalled();expect(screen.queryByLabelText('选择源相机实例')).toBeNull();
});
it('checks live identity again even without a rerender',async()=>{
  let finish!:(value:ModelCameraExport)=>void,current=true;
  const request=vi.fn(()=>new Promise<ModelCameraExport>(resolve=>{finish=resolve;}));
  render(<StudioModelCameraInspection {...basic()} isCurrent={()=>current} request={request}/>);await choose();fireEvent.click(exportButton());current=false;await act(async()=>finish(cameraExport()));expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it.each(['read','export'] as const)('aborts %s on unmount and never downloads',async operation=>{
  let finish!:()=>void;let signal!:AbortSignal;
  const props=basic();
  const read=operation==='read'?vi.fn((_a:StudioAsset,s:AbortSignal)=>{signal=s;return new Promise<ModelCameras>(resolve=>{finish=()=>resolve(cameraReview());});}):props.read;
  const request=vi.fn((_a:StudioAsset,_c:ModelCameraSelection,s:AbortSignal)=>{signal=s;return new Promise<ModelCameraExport>(resolve=>{finish=()=>resolve(cameraExport());});});
  const view=render(<StudioModelCameraInspection {...props} read={read} request={request}/>);
  if(operation==='read')fireEvent.click(readButton());else{await choose();fireEvent.click(exportButton());}
  view.unmount();expect(signal.aborted).toBe(true);await act(async()=>finish());expect(downloadPortableBlob).not.toHaveBeenCalled();
});
