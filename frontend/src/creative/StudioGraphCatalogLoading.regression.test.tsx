// @vitest-environment jsdom
import {act,cleanup,renderHook,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {useStudioGraphEditorController,type StudioGraphEditorProps} from './useStudioGraphEditorController';
import type {StudioClient} from './studioClient';
import type {StudioGraphCatalog,StudioGraphRecord} from './studioGraphTypes';
import {modelCatalog} from './studioGraphModel.testFixtures';
import {imageGraphRecord} from './studioImageGraph.testFixtures';
import productionCatalog from './fixtures/productionGraph.catalog.json';
const record=()=>{const row=imageGraphRecord();row.definition.nodes=[{id:'director',definition_id:'director_plan',definition_version:1,enabled:true,position:{x:0,y:0},parameters:{document_snapshot:{id:'source',version:1,digest:'a'.repeat(64)}}}];row.definition.edges=[];row.reference_states=[];return row;};
function deferred<T>(){let resolve!:(value:T)=>void,reject!:(reason:unknown)=>void;const promise=new Promise<T>((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};}
afterEach(cleanup);
async function fixture(){
 let live=true;
 const graphs={catalog:vi.fn(async()=>modelCatalog()),list:vi.fn(async()=>({items:[record()]})),get:vi.fn(async(_id:string)=>record()),productionCatalog:vi.fn(async()=>structuredClone(productionCatalog) as unknown as StudioGraphCatalog),save:vi.fn(),create:vi.fn(),createRun:vi.fn()};
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'original-owner',client:{graphs} as unknown as StudioClient,canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>live,read:work=>work(),mutate:work=>work()};
 const hook=renderHook((input:StudioGraphEditorProps)=>useStudioGraphEditorController(input),{initialProps:props});
 await waitFor(()=>expect(hook.result.current.catalog).toBeTruthy());await waitFor(()=>expect(hook.result.current.loading).toBe(false));
 return{...hook,graphs,props,retire:()=>{live=false;}};
}
function refresh(f:Awaited<ReturnType<typeof fixture>>){const next=deferred<StudioGraphCatalog>();f.graphs.catalog.mockReturnValueOnce(next.promise);let work!:Promise<void>;act(()=>{work=f.result.current.load();});return{...next,work};}
async function adopt(f:Awaited<ReturnType<typeof fixture>>,mode:'manual'|'restore'){
 if(mode==='manual')await act(async()=>{await f.result.current.open('image-graph');});
 else{f.rerender({...f.props,requestedGraphId:'image-graph'});await waitFor(()=>expect(f.result.current.base?.id).toBe('image-graph'));}
}
it.each(['manual','restore'] as const)('%s adoption settles superseded directory loading before its old response arrives',async mode=>{
 const f=await fixture(),old=refresh(f);expect(f.result.current.loading).toBe(true);await adopt(f,mode);
 expect(f.result.current.loading).toBe(false);expect(f.result.current.base?.id).toBe('image-graph');expect(f.result.current.catalog?.capabilities.production_graph).toBe(true);
 await act(async()=>{old.resolve(modelCatalog());await old.work;});
 expect(f.result.current.loading).toBe(false);expect(f.result.current.catalog?.capabilities.production_graph).toBe(true);expect(f.result.current.draft).toEqual(record().definition);expect(f.result.current.error).toBe('');
 expect(f.graphs.save).not.toHaveBeenCalled();expect(f.graphs.create).not.toHaveBeenCalled();expect(f.graphs.createRun).not.toHaveBeenCalled();
});
it.each(['manual','restore'] as const)('%s adoption does not let a retired refresh clear a newer request or publish its late error',async mode=>{
 const f=await fixture(),old=refresh(f);await adopt(f,mode);const newer=refresh(f);
 await act(async()=>{old.reject(new Error('Retired directory failure'));await old.work;});
 expect(f.result.current.loading).toBe(true);expect(f.result.current.error).toBe('');expect(f.result.current.catalog?.capabilities.production_graph).toBe(true);
 await act(async()=>{newer.resolve(modelCatalog());await newer.work;});expect(f.result.current.loading).toBe(false);
});
it('keeps loading while a newer overlapping directory request is still pending',async()=>{
 const f=await fixture(),first=refresh(f),second=refresh(f);
 await act(async()=>{first.resolve(modelCatalog());await first.work;});expect(f.result.current.loading).toBe(true);
 await act(async()=>{second.resolve(modelCatalog());await second.work;});expect(f.result.current.loading).toBe(false);
});
it.each(['manual','restore'] as const)('%s obsolete adoption cannot clear loading after a newer target has taken over',async mode=>{
 const f=await fixture(),olderRefresh=refresh(f),olderGraph=deferred<StudioGraphRecord>();f.graphs.get.mockReturnValueOnce(olderGraph.promise);let opening:Promise<void>|undefined;
 if(mode==='manual')act(()=>{opening=f.result.current.open('image-graph');});else f.rerender({...f.props,requestedGraphId:'image-graph'});
 await waitFor(()=>expect(f.graphs.get).toHaveBeenCalledTimes(1));
 f.graphs.get.mockImplementation(async id=>({...record(),id}));await act(async()=>{await f.result.current.open('newer-graph');
   // Match the host's onSelectionChange: its requested route follows the explicit newer choice.
   if(mode==='restore')f.rerender({...f.props,requestedGraphId:'newer-graph'});
 });
 const newerRefresh=refresh(f);
 await act(async()=>{olderGraph.resolve(record());await opening;olderRefresh.resolve(modelCatalog());await olderRefresh.work;});
 expect(f.result.current.loading).toBe(true);expect(f.result.current.base?.id).toBe('newer-graph');expect(f.result.current.catalog?.capabilities.production_graph).toBe(true);
 await act(async()=>{newerRefresh.resolve(modelCatalog());await newerRefresh.work;});expect(f.result.current.loading).toBe(false);
});
it.each(['manual','restore'] as const)('%s late adoption cannot publish catalog or graph after owner revocation',async mode=>{
 const f=await fixture(),get=deferred<StudioGraphRecord>();f.graphs.get.mockReturnValueOnce(get.promise);let opening:Promise<void>|undefined;
 if(mode==='manual')act(()=>{opening=f.result.current.open('image-graph');});else f.rerender({...f.props,requestedGraphId:'image-graph'});
 await waitFor(()=>expect(f.graphs.get).toHaveBeenCalledTimes(1));f.retire();f.rerender({...f.props,denied:true});
 await act(async()=>{get.resolve(record());await opening;});expect(f.result.current.retired).toBe(true);expect(f.result.current.base).toBeUndefined();expect(f.result.current.catalog).toBeUndefined();expect(f.graphs.save).not.toHaveBeenCalled();
});
it.each(['manual','restore'] as const)('%s old controller completion cannot settle a new mounted owner request',async mode=>{
 const old=await fixture(),get=deferred<StudioGraphRecord>();old.graphs.get.mockReturnValueOnce(get.promise);let opening:Promise<void>|undefined;
 if(mode==='manual')act(()=>{opening=old.result.current.open('image-graph');});else old.rerender({...old.props,requestedGraphId:'image-graph'});
 await waitFor(()=>expect(old.graphs.get).toHaveBeenCalledTimes(1));old.unmount();const newer=await fixture(),request=refresh(newer);
 await act(async()=>{get.resolve(record());await opening;});expect(newer.result.current.loading).toBe(true);expect(newer.result.current.base).toBeUndefined();
 await act(async()=>{request.resolve(modelCatalog());await request.work;});expect(newer.result.current.loading).toBe(false);
});
it('keeps previous canvas authority retired through target and permission ABA',async()=>{
 const f=await fixture();await adopt(f,'manual');const target=f.result.current.reviewedDirectorHandoff;
 f.graphs.get.mockImplementation(async id=>({...record(),id}));await act(async()=>{await f.result.current.open('other-graph');});await adopt(f,'manual');expect(target.isVerificationCurrent()).toBe(false);
 const permission=f.result.current.reviewedDirectorHandoff;f.rerender({...f.props,canMutate:false});f.rerender(f.props);expect(permission.isVerificationCurrent()).toBe(false);
 const before=structuredClone(f.result.current.draft);expect(target.insert({id:'source',version:1,digest:'a'.repeat(64)},target.scope)).toBe(false);expect(permission.insert({id:'source',version:1,digest:'a'.repeat(64)},permission.scope)).toBe(false);expect(f.result.current.draft).toEqual(before);
});
