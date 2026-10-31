// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import wire from './modelDepthWire.testFixture.json';
import {checkedModelDepth,type ModelDepthExport} from './studioModelDepthContract';
import {StudioModelDepthExport} from './StudioModelDepthExport';
import {studioClient,type StudioAsset} from './studioClient';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
const asset=wire.asset as StudioAsset,result=wire.result as ModelDepthExport,camera={yaw:result.depth_export.yaw,pitch:result.depth_export.pitch};
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.clearAllMocks();});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('accepts genuine File owner PNG bytes and rejects tampered pin, view, proof and bytes',async()=>{
 expect(await checkedModelDepth(result,asset,camera)).toEqual(result);
 for(const mutate of [(v:ModelDepthExport)=>{v.asset_snapshot.version++;},(v:ModelDepthExport)=>{v.depth_export.yaw++;},(v:ModelDepthExport)=>{v.depth_export.png_sha256='0'.repeat(64);},(v:ModelDepthExport)=>{v.content_base64=v.content_base64.slice(0,-4)+'AAAA';},(v:ModelDepthExport)=>{v.depth_export.width=255 as 256;}]){const value=structuredClone(result);mutate(value);await expect(checkedModelDepth(value,asset,camera)).rejects.toThrow();}
});
it('requests only on explicit export and checks bytes before downloading',async()=>{
 const request=vi.fn(async()=>result);render(<StudioModelDepthExport scope={{}} asset={asset} {...camera} disabled={false} canExport isCurrent={()=>true} request={request}/>);
 expect(request).not.toHaveBeenCalled();fireEvent.click(screen.getByText('导出当前视角深度参考 PNG'));await screen.findByText('PNG 校验通过，已发起下载。');expect(request).toHaveBeenCalledTimes(1);expect(downloadPortableBlob).toHaveBeenCalledTimes(1);expect(vi.mocked(downloadPortableBlob).mock.calls[0][0].type).toBe('image/png');
});
it('denies missing export authority and discards a late response after camera replacement',async()=>{
 let finish!:(v:ModelDepthExport)=>void;const request=vi.fn((_a:StudioAsset,_c:unknown,_s:AbortSignal)=>new Promise<ModelDepthExport>(resolve=>{finish=resolve;}));const props={scope:{},asset,...camera,disabled:false,isCurrent:()=>true,request};const view=render(<StudioModelDepthExport {...props}/>);
 fireEvent.click(screen.getByText('导出当前视角深度参考 PNG'));expect(request).not.toHaveBeenCalled();view.rerender(<StudioModelDepthExport {...props} canExport/>);fireEvent.click(screen.getByText('导出当前视角深度参考 PNG'));const signal=request.mock.calls[0][2];view.rerender(<StudioModelDepthExport {...props} yaw={camera.yaw+1} canExport/>);expect(signal.aborted).toBe(true);await act(async()=>finish(result));expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it('rechecks export authority after a pending response and refuses damaged bytes',async()=>{
 let finish!:(v:ModelDepthExport)=>void;const request=vi.fn(()=>new Promise<ModelDepthExport>(resolve=>{finish=resolve;}));const props={scope:{},asset,...camera,disabled:false,isCurrent:()=>true,request};const view=render(<StudioModelDepthExport {...props} canExport/>);fireEvent.click(screen.getByText('导出当前视角深度参考 PNG'));view.rerender(<StudioModelDepthExport {...props} canExport={false}/>);await act(async()=>finish(result));expect(downloadPortableBlob).not.toHaveBeenCalled();
 view.rerender(<StudioModelDepthExport {...props} canExport/>);fireEvent.click(screen.getByText('导出当前视角深度参考 PNG'));await act(async()=>finish({...result,content_base64:'AAAA'}));await screen.findByText('深度图回执、来源或 PNG 校验不一致，未下载。');expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it('uses original asset POST with exact source and camera, never a model endpoint',async()=>{
 const fetch=vi.fn(async()=>new Response(JSON.stringify(result),{status:200}));vi.stubGlobal('fetch',fetch);const client=studioClient(asset.novel_id,{sessionToken:'fixture-session'});
 expect(await client.exportModelDepth(asset,camera)).toEqual(result);expect(fetch).toHaveBeenCalledTimes(1);const [url,options]=fetch.mock.calls[0] as unknown as [string,RequestInit];expect(url).toContain(`/assets/${asset.id}/model-reference/depth-export`);expect(options.method).toBe('POST');expect(JSON.parse(String(options.body))).toEqual({contract:'studio-static-glb-depth-export/1',source_version:asset.version,source_sha256:asset.sha256,...camera});
 await expect(client.exportModelDepth(asset,{yaw:Infinity,pitch:0})).rejects.toThrow();expect(fetch).toHaveBeenCalledTimes(1);
});

it('discards old source bytes on source ABA or unmount',async()=>{
 let finish!:(v:ModelDepthExport)=>void;const request=vi.fn(()=>new Promise<ModelDepthExport>(resolve=>{finish=resolve;}));const props={scope:{},asset,...camera,disabled:false,canExport:true,isCurrent:()=>true,request};const view=render(<StudioModelDepthExport {...props}/>);fireEvent.click(screen.getByText('导出当前视角深度参考 PNG'));view.rerender(<StudioModelDepthExport {...props} asset={{...asset,version:asset.version+1}}/>);view.rerender(<StudioModelDepthExport {...props}/>);await act(async()=>finish(result));expect(downloadPortableBlob).not.toHaveBeenCalled();fireEvent.click(screen.getByText('导出当前视角深度参考 PNG'));view.unmount();await act(async()=>finish(result));expect(downloadPortableBlob).not.toHaveBeenCalled();
});
