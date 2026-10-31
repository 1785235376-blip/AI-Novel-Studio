// [HERMIA-FE-20261025 DUI P0-3] Repro: chapter list queries must never resolve undefined (React Query rejects it with a raw English error).
import {describe,it,expect,vi,afterEach} from 'vitest';
import {api} from './api';
const scope={workspaceId:'w',projectId:'p',storylineId:'s',branchId:'b'} as any;
const reply=(b:unknown)=>vi.stubGlobal('fetch',vi.fn(()=>Promise.resolve(new Response(JSON.stringify(b),{status:200,headers:{'Content-Type':'application/json'}}))));
afterEach(()=>vi.unstubAllGlobals());
describe('chapter list normalisation',()=>{
  it('scoped chapters accepts {items}',async()=>{reply({items:[{id:'c1'}]});expect(await api.scopedChapters(scope)).toEqual([{id:'c1'}]);});
  it('scoped chapters accepts a bare array instead of resolving undefined',async()=>{reply([{id:'c1'}]);expect(await api.scopedChapters(scope)).toEqual([{id:'c1'}]);});
  it('local chapters accepts {items}',async()=>{reply({items:[{id:'c2'}]});expect(await api.chapters('n1')).toEqual([{id:'c2'}]);});
  it('unrecognised shape rejects with human Chinese text, never undefined',async()=>{reply({unexpected:true});await expect(api.scopedChapters(scope)).rejects.toThrow('章节列表格式无法识别');});
});
