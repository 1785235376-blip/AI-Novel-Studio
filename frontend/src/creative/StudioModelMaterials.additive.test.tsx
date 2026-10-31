// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import wire from './modelMaterialsWire.testFixture.json';
import {checkedModelMaterials,type ModelMaterials} from './studioModelMaterialsContract';
import {StudioModelMaterialInspection} from './StudioModelMaterialInspection';
import {studioClient,type StudioAsset} from './studioClient';
const asset=wire.asset as StudioAsset,result=wire.result as ModelMaterials;
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('checks genuine File material receipt and rejects stale source, invalid factors and mappings',()=>{
 expect(checkedModelMaterials(result,asset)).toEqual(result);
 for(const mutate of [(r:ModelMaterials)=>{r.asset_snapshot.version++;},(r:ModelMaterials)=>{r.material_inspection.materials[0].roughness_factor=2;},(r:ModelMaterials)=>{r.material_inspection.materials[0].base_color_factor[0]=NaN;},(r:ModelMaterials)=>{r.material_inspection.primitive_bindings[0].material_index=2;},(r:ModelMaterials)=>{r.material_inspection.materials[0].declared_texture_slots=['normalTexture','normalTexture'];},(r:ModelMaterials)=>{r.material_inspection.primitive_bindings[0].primitive_index=1;}]){const value=structuredClone(result);mutate(value);expect(()=>checkedModelMaterials(value,asset)).toThrow();}
});
it('requires explicit read, displays factors and never renders texture resources',async()=>{
 const read=vi.fn(async()=>result);render(<StudioModelMaterialInspection scope={{}} asset={asset} disabled={false} isCurrent={()=>true} read={read}/>);expect(read).not.toHaveBeenCalled();fireEvent.click(screen.getByText('明确读取 GLB 材质数值'));await screen.findByText('材质 0 · Paint');expect(screen.getByText(/金属度：0.2/)).toBeTruthy();expect(screen.queryByRole('img')).toBeNull();expect(read).toHaveBeenCalledTimes(1);
});
it('drops a retained response across source ABA and aborts original read',async()=>{
 let finish!:(r:ModelMaterials)=>void;const read=vi.fn((_a:StudioAsset,_s:AbortSignal)=>new Promise<ModelMaterials>(r=>{finish=r;}));const props={scope:{},asset,disabled:false,isCurrent:()=>true,read};const view=render(<StudioModelMaterialInspection {...props}/>);fireEvent.click(screen.getByText('明确读取 GLB 材质数值'));view.rerender(<StudioModelMaterialInspection {...props} asset={{...asset,version:2}}/>);view.rerender(<StudioModelMaterialInspection {...props}/>);expect(read.mock.calls[0][1].aborted).toBe(true);await act(async()=>finish(result));expect(screen.queryByText('材质 0 · Paint')).toBeNull();
});
it('uses the captured original asset GET transport and validates source receipt',async()=>{
 const fetch=vi.fn(async()=>new Response(JSON.stringify(result),{status:200}));vi.stubGlobal('fetch',fetch);expect(await studioClient(asset.novel_id,{sessionToken:'fixture-session'}).inspectModelMaterials(asset)).toEqual(result);const [url,init]=fetch.mock.calls[0] as unknown as [string,RequestInit];expect(url).toContain(`/assets/${asset.id}/model-reference/materials`);expect(init.method).toBe('GET');expect(fetch).toHaveBeenCalledTimes(1);
});
