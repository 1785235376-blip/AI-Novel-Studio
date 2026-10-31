// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import wire from './modelClayWire.testFixture.json';
import {checkedModelClay,type ModelClayExport} from './studioModelClayContract';
import {StudioModelDepthExport} from './StudioModelDepthExport';
import {studioClient,type StudioAsset} from './studioClient';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
const asset=wire.asset as StudioAsset,result=wire.result as ModelClayExport,camera={yaw:result.clay_export.yaw,pitch:result.clay_export.pitch};
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.clearAllMocks();});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('checks genuine original File clay PNG without accepting depth/material/physical-lighting claims',async()=>{
 expect(await checkedModelClay(result,asset,camera)).toEqual(result);
 for(const mutate of [(v:ModelClayExport)=>{v.asset_snapshot.version++;},(v:ModelClayExport)=>{v.clay_export.physical_lighting=true as false;},(v:ModelClayExport)=>{v.clay_export.png_sha256='0'.repeat(64);},(v:ModelClayExport)=>{v.clay_export.yaw++;}]){const value=structuredClone(result);mutate(value);await expect(checkedModelClay(value,asset,camera)).rejects.toThrow();}
});
it('reuses explicit export authority and only downloads a verified clay PNG on click',async()=>{
 const request=vi.fn(async()=>result);const props={scope:{},asset,...camera,disabled:false,isCurrent:()=>true,request};const view=render(<StudioModelDepthExport {...props} kind="clay"/>);fireEvent.click(screen.getByText('导出当前视角灰模参考 PNG'));expect(request).not.toHaveBeenCalled();view.rerender(<StudioModelDepthExport {...props} kind="clay" canExport/>);fireEvent.click(screen.getByText('导出当前视角灰模参考 PNG'));await screen.findByText('PNG 校验通过，已发起下载。');expect(downloadPortableBlob).toHaveBeenCalledTimes(1);expect(vi.mocked(downloadPortableBlob).mock.calls[0][1]).toBe(`scene-clay-${asset.id}.png`);
});
it('discards a late clay response when the same exporter switches to depth mode',async()=>{
 let finish!:(v:ModelClayExport)=>void;const request=vi.fn((_a:StudioAsset,_c:unknown,_s:AbortSignal)=>new Promise<ModelClayExport>(r=>{finish=r;}));const props={scope:{},asset,...camera,disabled:false,canExport:true,isCurrent:()=>true};const view=render(<StudioModelDepthExport {...props} kind="clay" request={request}/>);fireEvent.click(screen.getByText('导出当前视角灰模参考 PNG'));view.rerender(<StudioModelDepthExport {...props} request={vi.fn()}/>);expect(request.mock.calls[0][2].aborted).toBe(true);await act(async()=>finish(result));expect(downloadPortableBlob).not.toHaveBeenCalled();
});
it('uses original asset read POST with exact clay contract and source/camera',async()=>{
 const fetch=vi.fn(async()=>new Response(JSON.stringify(result),{status:200}));vi.stubGlobal('fetch',fetch);expect(await studioClient(asset.novel_id,{sessionToken:'fixture-session'}).exportModelClay(asset,camera)).toEqual(result);const [url,init]=fetch.mock.calls[0] as unknown as [string,RequestInit];expect(url).toContain(`/assets/${asset.id}/model-reference/clay-export`);expect(init.method).toBe('POST');expect(JSON.parse(String(init.body))).toEqual({contract:'studio-static-glb-clay-export/1',source_version:asset.version,source_sha256:asset.sha256,...camera});
});
