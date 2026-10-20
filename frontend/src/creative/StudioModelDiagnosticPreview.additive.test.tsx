// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import wire from './modelDepthWire.testFixture.json';
import {type ModelDepthExport} from './studioModelDepthContract';
import {StudioModelDepthExport} from './StudioModelDepthExport';
import {type StudioAsset} from './studioClient';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
const asset=wire.asset as StudioAsset,result=wire.result as ModelDepthExport,camera={yaw:result.depth_export.yaw,pitch:result.depth_export.pitch};
const create=vi.fn((_blob:Blob)=> 'blob:verified-diagnostic'),revoke=vi.fn();
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.clearAllMocks();vi.stubGlobal('URL',Object.assign(class extends URL {},{createObjectURL:create,revokeObjectURL:revoke}));});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('previews real checked PNG bytes without download, then downloads the same reviewed blob without rerendering',async()=>{
 const request=vi.fn(async()=>result);const view=render(<StudioModelDepthExport scope={{}} asset={asset} {...camera} disabled={false} canExport isCurrent={()=>true} request={request}/>);
 expect(request).not.toHaveBeenCalled();fireEvent.click(screen.getByText('预览当前视角深度 PNG'));await screen.findByAltText('已校验的深度参考 PNG');
 expect(downloadPortableBlob).not.toHaveBeenCalled();expect(create.mock.calls[0][0]).toBeInstanceOf(Blob);
 fireEvent.click(screen.getByText('下载这张已校验的预览'));expect(request).toHaveBeenCalledTimes(1);expect(vi.mocked(downloadPortableBlob).mock.calls[0][0]).toBe(create.mock.calls[0][0]);
 fireEvent.click(screen.getByText('关闭 PNG 预览'));expect(screen.queryByAltText('已校验的深度参考 PNG')).toBeNull();expect(revoke).toHaveBeenCalledWith('blob:verified-diagnostic');view.unmount();
});
it.each(['view','source','scope','permission','disabled','unmount'])('removes and revokes the local preview on %s change',async change=>{
 const props={scope:{},asset,...camera,disabled:false,canExport:true,isCurrent:()=>true,request:vi.fn(async()=>result)};
 const view=render(<StudioModelDepthExport {...props}/>);fireEvent.click(screen.getByText('预览当前视角深度 PNG'));await screen.findByAltText('已校验的深度参考 PNG');
 if(change==='unmount')view.unmount();else view.rerender(<StudioModelDepthExport {...props} {...(change==='view'?{yaw:camera.yaw+1}:change==='source'?{asset:{...asset,version:asset.version+1}}:change==='scope'?{scope:{}}:change==='permission'?{canExport:false}:{disabled:true})}/>);
 await waitFor(()=>expect(revoke).toHaveBeenCalledWith('blob:verified-diagnostic'));expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it('rejects permission ABA during calculation and damaged PNG without creating an object URL',async()=>{
 let finish!:(v:ModelDepthExport)=>void;const request=vi.fn(()=>new Promise<ModelDepthExport>(r=>{finish=r;}));const props={scope:{},asset,...camera,disabled:false,canExport:true,isCurrent:()=>true,request};const view=render(<StudioModelDepthExport {...props}/>);
 fireEvent.click(screen.getByText('预览当前视角深度 PNG'));view.rerender(<StudioModelDepthExport {...props} canExport={false}/>);view.rerender(<StudioModelDepthExport {...props}/>);await act(async()=>finish(result));expect(create).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('预览当前视角深度 PNG'));await act(async()=>finish({...result,content_base64:'AAAA'}));await screen.findByText('深度图回执、来源或 PNG 校验不一致，未下载。');expect(create).not.toHaveBeenCalled();expect(downloadPortableBlob).not.toHaveBeenCalled();
});
