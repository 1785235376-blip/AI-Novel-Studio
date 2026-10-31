// @vitest-environment jsdom
import {webcrypto} from 'node:crypto';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import wire from './modelClaySaveWire.testFixture.json';
import {checkedClayAssetResult} from './studioModelClaySaveContract';
import type {ModelClayExport} from './studioModelClayContract';
import {StudioModelDepthExport} from './StudioModelDepthExport';
import {studioClient,type StudioAsset} from './studioClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
const source=wire.source as StudioAsset,review=wire.review as ModelClayExport,camera={yaw:review.clay_export.yaw,pitch:review.clay_export.pitch};
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('URL',class extends URL{static createObjectURL=vi.fn(()=> 'blob:synthetic-preview');static revokeObjectURL=vi.fn();});vi.clearAllMocks();});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('decodes genuine persisted original Asset receipt and rejects false source or generation claims',()=>{
 expect(checkedClayAssetResult(wire.result,source,review)).toEqual(wire.result);
 for(const change of [(v:typeof wire.result)=>{v.asset.model_reference.yaw++;},(v:typeof wire.result)=>{v.receipt.source_version++;},(v:typeof wire.result)=>{v.receipt.model_called=true;},(v:typeof wire.result)=>{v.receipt.replayed=true;},(v:typeof wire.result)=>{v.asset.provenance.parents[0].digest='0'.repeat(64);},(v:typeof wire.result)=>{v.asset.novel_id='wrong-project';}]){const result=structuredClone(wire.result);change(result);expect(()=>checkedClayAssetResult(result,source,review)).toThrow();}
});
it('sends only source-pinned reviewed hash with explicit confirmation and stable caller key',async()=>{
 const fetch=vi.fn(async(_url:unknown,_init?:RequestInit)=>new Response(JSON.stringify(wire.result),{status:201}));vi.stubGlobal('fetch',fetch);
 const client=studioClient(source.novel_id,{sessionToken:'synthetic-session'});
 expect(await client.saveModelClay(source,review,'same-request')).toEqual(wire.result);
 expect(fetch.mock.calls[0][0]).toContain(`/assets/${source.id}/model-reference/clay-save`);
 expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({contract:'studio-static-glb-clay-asset/1',source_version:source.version,source_sha256:source.sha256,...camera,reviewed_png_sha256:review.clay_export.png_sha256,confirm_reference:true,idempotency_key:'same-request'});
 const broken=structuredClone(review);broken.clay_export.png_sha256='0'.repeat(64);await expect(client.saveModelClay(source,broken,'same-request')).rejects.toThrow();expect(fetch).toHaveBeenCalledTimes(1);
});
it('requires actual PNG preview, explicit checkbox and current write permission before save',async()=>{
 const onSave=vi.fn(async(_asset:StudioAsset,_review:ModelClayExport)=>{}),request=vi.fn(async()=>review);
 const props={scope:{},asset:source,...camera,disabled:false,canExport:true,isCurrent:()=>true,request,onSave};
 const view=render(<StudioModelDepthExport {...props} kind="clay"/>);
 expect(screen.queryByText('保存这张灰模参考到素材库')).toBeNull();
 fireEvent.click(screen.getByText('预览当前视角灰模 PNG'));await screen.findByRole('img',{name:'已校验的灰模参考 PNG'});
 fireEvent.click(screen.getByLabelText('已查看灰模 PNG，确认保存为诊断参考素材'));fireEvent.click(screen.getByText('保存这张灰模参考到素材库'));expect(onSave).not.toHaveBeenCalled();
 view.rerender(<StudioModelDepthExport {...props} kind="clay" canSave/>);
 expect(screen.queryByText('保存这张灰模参考到素材库')).toBeNull();
 fireEvent.click(screen.getByText('预览当前视角灰模 PNG'));await screen.findByRole('img',{name:'已校验的灰模参考 PNG'});
 fireEvent.click(screen.getByText('保存这张灰模参考到素材库'));expect(onSave).not.toHaveBeenCalled();
 fireEvent.click(screen.getByLabelText('已查看灰模 PNG，确认保存为诊断参考素材'));
 await act(async()=>{fireEvent.click(screen.getByText('保存这张灰模参考到素材库'));});
 expect(onSave).toHaveBeenCalledTimes(1);expect(onSave).toHaveBeenCalledWith(source,review);
});
it('retires the reviewed PNG when camera or permission changes',async()=>{
 const onSave=vi.fn(async()=>{}),props={scope:{},asset:source,...camera,disabled:false,canExport:true,canSave:true,isCurrent:()=>true,request:async()=>review,onSave};
 const view=render(<StudioModelDepthExport {...props} kind="clay"/>);fireEvent.click(screen.getByText('预览当前视角灰模 PNG'));await screen.findByRole('img',{name:'已校验的灰模参考 PNG'});fireEvent.click(screen.getByLabelText('已查看灰模 PNG，确认保存为诊断参考素材'));
 view.rerender(<StudioModelDepthExport {...props} kind="clay" yaw={camera.yaw+1}/>);expect(screen.queryByText('保存这张灰模参考到素材库')).toBeNull();expect(onSave).not.toHaveBeenCalled();expect(URL.revokeObjectURL).toHaveBeenCalled();
});
