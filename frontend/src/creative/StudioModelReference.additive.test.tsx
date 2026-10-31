// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { StudioModelReferencePanel } from './StudioModelReferencePanel';
import { checkedModelReferenceInspection } from './studioModelReferenceContract';
import { studioClient } from './studioClient';
import { modelAsset, modelGlbBytes, modelInspection } from './studioModelReference.testFixtures';
beforeEach(()=>vi.stubGlobal('crypto',webcrypto));afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function props(){return {scope:{},assets:[modelAsset()],blocked:false,canImport:true,isCurrent:()=>true,onImport:vi.fn(async(_input:{filename:string;content_base64:string})=>modelAsset()),onInspect:vi.fn(async()=>modelInspection())};}
function file(){const bytes=modelGlbBytes(),value=new File([bytes],'triangle.glb');Object.defineProperty(value,'arrayBuffer',{value:async()=>bytes.buffer});return value;}
it('validates the exact asset version/hash and refuses fabricated viewport or transformed bounds claims',()=>{
 const asset=modelAsset(),receipt=modelInspection();expect(checkedModelReferenceInspection(receipt,asset)).toEqual(receipt);
 const changed=structuredClone(receipt);changed.asset_snapshot.version++;expect(()=>checkedModelReferenceInspection(changed,asset)).toThrow();
 const flags=structuredClone(receipt) as any;flags.inspection.preview_available=true;expect(()=>checkedModelReferenceInspection(flags,asset)).toThrow();
});
it('reads selected file locally and uploads only on explicit action without auto-inspection',async()=>{
 const p=props();render(<StudioModelReferencePanel {...p}/>);expect(p.onImport).not.toHaveBeenCalled();expect(p.onInspect).not.toHaveBeenCalled();fireEvent.change(screen.getByLabelText('选择静态 GLB 文件'),{target:{files:[file()]}});
 const save=await screen.findByRole('button',{name:'明确导入并保存 GLB 参考素材'});expect(p.onImport).not.toHaveBeenCalled();fireEvent.click(save);await waitFor(()=>expect(p.onImport).toHaveBeenCalledTimes(1));expect(p.onInspect).not.toHaveBeenCalled();expect(p.onImport.mock.calls[0][0]).toMatchObject({filename:'triangle.glb'});
});
it('keeps a failed import for explicit same-body retry and never retries automatically',async()=>{
 const p=props();p.onImport.mockRejectedValueOnce(new Error('Unknown transport'));render(<StudioModelReferencePanel {...p}/>);fireEvent.change(screen.getByLabelText('选择静态 GLB 文件'),{target:{files:[file()]}});fireEvent.click(await screen.findByRole('button',{name:'明确导入并保存 GLB 参考素材'}));
 fireEvent.click(await screen.findByRole('button',{name:'使用同一请求重试 GLB 导入'}));await waitFor(()=>expect(p.onImport).toHaveBeenCalledTimes(2));expect(p.onImport.mock.calls[0]).toEqual(p.onImport.mock.calls[1]);
});
it('reads exact metadata only after selection and hides late old-scope results',async()=>{
 let resolve!:(value:ReturnType<typeof modelInspection>)=>void;const p=props();p.onInspect.mockImplementation(()=>new Promise(done=>{resolve=done;}));const view=render(<StudioModelReferencePanel {...p}/>);fireEvent.change(screen.getByLabelText('已保存 GLB 参考'),{target:{value:modelAsset().id}});fireEvent.click(screen.getByRole('button',{name:'读取当前 GLB 几何检查'}));view.rerender(<StudioModelReferencePanel {...p} scope={{}}/>);await act(async()=>resolve(modelInspection()));expect(screen.queryByLabelText('GLB 原素材几何回执')).toBeNull();
});
it('retains captured original transport authority, verifies uploaded bytes and uses the separate endpoint',async()=>{
 const origin={sessionToken:'fixture-session'},asset=modelAsset();const fetch=vi.fn(async(url:string,init:RequestInit)=>new Response(JSON.stringify(url.endsWith('/model-reference')&&init.method==='GET'?modelInspection():asset),{status:200}));vi.stubGlobal('fetch',fetch);
 const client=studioClient('project',origin);origin.sessionToken='changed';const bytes=modelGlbBytes(),body={contract:'studio-static-glb-import/1' as const,filename:'triangle.glb',content_base64:btoa(String.fromCharCode(...bytes)),idempotency_key:'one-original-request'};
 await client.importModelReference(body);await client.inspectModelReference(asset);
 expect(fetch.mock.calls[0][0]).toBe('/api/projects/project/studio/assets/model-reference');expect(fetch.mock.calls[0][1].headers).toMatchObject({'X-Session-Token':'fixture-session','Idempotency-Key':'one-original-request'});expect(fetch.mock.calls[1][1].method).toBe('GET');
 asset.sha256='b'.repeat(64);await expect(client.importModelReference(body)).rejects.toThrow(/文件字节不一致/);
});
