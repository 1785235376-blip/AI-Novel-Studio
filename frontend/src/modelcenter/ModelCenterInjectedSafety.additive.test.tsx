// @vitest-environment jsdom
import {cleanup,renderHook,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {useModelCenter} from './useModelCenter';
import {modelCenterCatalog,modelCenterStorage,modelCenterInjectedCatalog} from './modelCenterContract';
import type {StudioGraphTransport} from '../creative/studioGraphClient';
const storage=()=>modelCenterStorage({assets:{count:0,bytes:0},trash:{count:0,bytes:0},limits:{asset_bytes:1024,project_asset_bytes:4096,project_assets:10},model_storage:'EXTERNAL_READ_ONLY',cache_storage:'SEPARATE_OWNER',export_storage:'CLIENT_SELECTED_DOWNLOAD',physical_cleanup_available:false});
const catalog=()=>modelCenterCatalog({items:[]},{items:[]});
function props(c:unknown,s:unknown){return {projectId:'project',transport:{json:vi.fn(async()=>{throw new Error('Source unavailable');})} as unknown as StudioGraphTransport,identity:'fixture',active:true,denied:false,busy:false,isCurrent:()=>true,read:async<T,>(fn:()=>Promise<T>)=>fn(),mutate:async<T,>(fn:()=>Promise<T>)=>fn(),catalog:c,storage:s};}
afterEach(cleanup);
it('refuses incomplete injected catalog rather than exposing a renderer-crashing decoded value',async()=>{
 const {result}=renderHook(()=>useModelCenter(props({models:[],runtimes:[]},storage())));await waitFor(()=>expect(result.current.state).not.toBe('IDLE'));await waitFor(()=>expect(result.current.state).not.toBe('LOADING'));expect(result.current.catalog).toBeUndefined();expect(result.current.sources.catalog.state).toBe('FAILED');
});
it('refuses injected storage claiming physical cleanup authority',async()=>{
 const {result}=renderHook(()=>useModelCenter(props(catalog(),{...storage(),physical_cleanup_available:true})));await waitFor(()=>expect(result.current.state).not.toBe('IDLE'));await waitFor(()=>expect(result.current.state).not.toBe('LOADING'));expect(result.current.storage).toBeUndefined();expect(result.current.sources.storage.state).toBe('FAILED');
});

it('revalidates complete decoded profiles without losing declared hardware facts or sharing references',()=>{
 const original=modelCenterCatalog({items:[{id:'local',display_name:'Local',family:'QWEN',variant:'7B',version:'1',capabilities:['TEXT'],runtime_type:'LLAMA_CPP',model_format:'GGUF',metadata:{installed:true},hardware_profile_details:[{id:'profile',gpu_name:'Fixture GPU',profile_kind:'SMOKE',vram_required:8192,tested:false}]}]},{items:[]});
 const checked=modelCenterInjectedCatalog(original);expect(checked).toEqual(original);(original.models[0].metadata!).installed=false;expect(checked.models[0].metadata?.installed).toBe(true);expect(checked.models[0].hardware_profile?.vram_required_mib).toBe(8192);
});
it('rejects injected secret fields, observation aliases and malformed source markers',()=>{
 for(const value of [{...catalog(),api_key:'synthetic-not-a-key'},{...catalog(),sources:['STUDIO_STORAGE']},{...catalog(),hidden_by_authority:-1},{...catalog(),capability_snapshots:[{runtime_id:'unbound',capabilities:['TEXT']}]}])expect(()=>modelCenterInjectedCatalog(value)).toThrow();
 expect(modelCenterInjectedCatalog({models:{items:[]},runtimes:{items:[]}})).toEqual(catalog());
});

it('applies project scope checks before accepting even complete injected facts',async()=>{
 const p=props(catalog(),storage());const {result}=renderHook(()=>useModelCenter({...p,scope:{workspaceId:'w',projectId:'other',storylineId:'s',branchId:'b'}}));await waitFor(()=>expect(result.current.state).toBe('FAILED'));expect(result.current.catalog).toBeUndefined();expect(result.current.storage).toBeUndefined();expect(p.transport.json).not.toHaveBeenCalled();
});
it('rejects invalid project context even when both injected sources are otherwise valid',async()=>{
 const p=props(catalog(),storage());const {result}=renderHook(()=>useModelCenter({...p,projectId:''}));await waitFor(()=>expect(result.current.state).toBe('FAILED'));expect(result.current.catalog).toBeUndefined();expect(result.current.storage).toBeUndefined();expect(p.transport.json).not.toHaveBeenCalled();
});
