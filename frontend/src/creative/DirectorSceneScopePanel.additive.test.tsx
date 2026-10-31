// @vitest-environment jsdom
import { act,cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { afterEach,expect,it,vi } from 'vitest';
import { DirectorSceneScopePanel } from './DirectorSceneScopePanel';
import { checkedDirectorSceneScopeResult,directorSceneScopeBody } from './directorSceneScope';
import { newDocument,type CreativeDocument } from './types';
const source:CreativeDocument={...newDocument('DIRECTOR'),id:'parent',version:1,title:'Parent',status:'DRAFT',actor_id:'author',created_at:'',updated_at:'',source_evidence:{},source_independent:true,
 scenes:[{id:'a',sequence:1,heading:'Scene A',source_chapter_id:null,time:'',location:'',characters:[],action:'A',dialogue:[],emotion:'',director_notes:[]},{id:'b',sequence:2,heading:'Scene B',source_chapter_id:null,time:'',location:'',characters:[],action:'B',dialogue:[],emotion:'',director_notes:[]} ]};
const snapshot={id:'parent',version:1,digest:'a'.repeat(64)};
const result=()=>({...source,id:'child',title:'Opening',source_independent:false,scenes:source.scenes.slice(0,1),source_documents:{parent:{version:1,digest:snapshot.digest}},provenance:{method:'STRUCTURED_DERIVATION',model_called:false,source_document_id:'parent',source_version:1,input_digest:snapshot.digest,parameters:{rule_version:'creative-director-scene-scope-v1',responsibility:'Opening',scene_ids:['a'],copied_approval:false,execution_authority:false}}});
const retained=(element:HTMLElement)=>(element as any)[Object.keys(element).find(key=>key.startsWith('__reactProps$'))!].onClick;
afterEach(cleanup);
function fixture(){return{source,snapshot,available:true,busy:false,isCurrent:()=>true,request:vi.fn(async()=>result()),mutate:async<T,>(work:()=>Promise<T>)=>work(),onPending:vi.fn(),onOpen:vi.fn()};}
function fill(){fireEvent.change(screen.getByLabelText('子导演职责'),{target:{value:'Opening'}});fireEvent.click(screen.getByRole('checkbox',{name:'1 · Scene A'}));fireEvent.click(screen.getByRole('checkbox',{name:'已核对职责与场景，同意创建一个新子导演草稿'}));}
it('uses explicit scene selection and consent, then opens the new original document only on request',async()=>{
 const props=fixture();render(<DirectorSceneScopePanel {...props}/>);fill();expect(props.request).not.toHaveBeenCalled();fireEvent.click(screen.getByText('创建所选场景子导演'));await screen.findByText(/已创建 Opening/);
 expect(props.request).toHaveBeenCalledWith(source,snapshot,'Opening',['a']);expect(props.onOpen).not.toHaveBeenCalled();fireEvent.click(screen.getByText('读取新子导演原文档'));expect(props.onOpen).toHaveBeenCalledWith('child');await waitFor(()=>expect(props.onPending).toHaveBeenLastCalledWith(false));
});
it('does not replay an uncertain create and preserves a pending intent',async()=>{
 const props=fixture();props.request.mockRejectedValue(new Error('lost response'));render(<DirectorSceneScopePanel {...props}/>);fill();const callback=retained(screen.getByText('创建所选场景子导演'));act(()=>{callback();callback();});await screen.findByText(/创建结果未确认/);act(()=>callback());expect(props.request).toHaveBeenCalledTimes(1);expect((screen.getByText('创建所选场景子导演') as HTMLButtonElement).disabled).toBe(true);
});
it('rejects an old confirmed form callback after the selected scene intent changes',()=>{
 const props=fixture();render(<DirectorSceneScopePanel {...props}/>);fill();const callback=retained(screen.getByText('创建所选场景子导演'));fireEvent.click(screen.getByRole('checkbox',{name:'2 · Scene B'}));act(()=>callback());expect(props.request).not.toHaveBeenCalled();
});
it('does not expose a late result after source authority changes',async()=>{
 const props=fixture();let finish!:(value:ReturnType<typeof result>)=>void;props.request.mockImplementation(()=>new Promise(resolve=>finish=resolve));const view=render(<DirectorSceneScopePanel {...props}/>);fill();fireEvent.click(screen.getByText('创建所选场景子导演'));
 view.rerender(<DirectorSceneScopePanel {...props} available={false}/>);await act(async()=>finish(result()));expect(screen.queryByText(/已创建 Opening/)).toBeNull();expect(props.onOpen).not.toHaveBeenCalled();
});
it('validates exact selected-scene result and rejects inherited approval or broadened content',()=>{
 expect(directorSceneScopeBody(source,snapshot,'Opening',['a']).director_scope.scene_ids).toEqual(['a']);expect(checkedDirectorSceneScopeResult(result(),source,snapshot,'Opening',['a']).id).toBe('child');
 for(const value of [{...result(),scenes:source.scenes},{...result(),status:'APPROVED'},{...result(),source_documents:{}},{...result(),provenance:{...result().provenance,parameters:{...result().provenance.parameters,copied_approval:true}}}])expect(()=>checkedDirectorSceneScopeResult(value,source,snapshot,'Opening',['a'])).toThrow();
});
it('accepts original HTTP JSON with reordered object keys while preserving exact selected values and array order',()=>{
 const reorder=(value:any):any=>Array.isArray(value)?value.map(reorder):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).reverse().map(key=>[key,reorder(value[key])])):value;
 expect(checkedDirectorSceneScopeResult(reorder(result()),source,snapshot,'Opening',['a']).id).toBe('child');
 const changed=reorder(result());changed.scenes[0].action='Changed';expect(()=>checkedDirectorSceneScopeResult(changed,source,snapshot,'Opening',['a'])).toThrow();
 const two={...result(),scenes:source.scenes,provenance:{...result().provenance,parameters:{...result().provenance.parameters,scene_ids:['a','b']}}};
 expect(checkedDirectorSceneScopeResult(reorder(two),source,snapshot,'Opening',['b','a']).scenes.map(scene=>scene.id)).toEqual(['a','b']);
 expect(()=>checkedDirectorSceneScopeResult({...two,scenes:[...two.scenes].reverse()},source,snapshot,'Opening',['a','b'])).toThrow();
});
it('uses the original captured Creative transport and validates the returned scope',async()=>{
 const {creativeClient}=await import('./client');const fetch=vi.fn(async()=>new Response(JSON.stringify(result()),{status:201}));vi.stubGlobal('fetch',fetch);
 try{const api=creativeClient('project',{sessionToken:'trusted-session'});expect((await api.deriveDirectorScope(source,snapshot,'Opening',['a'])).id).toBe('child');
  const [url,options]=fetch.mock.calls[0] as unknown as [string,RequestInit];expect(url).toBe('/api/novels/project/experimental/creative/documents/parent/derive');expect(options.method).toBe('POST');expect((options.headers as Record<string,string>)['X-Session-Token']).toBe('trusted-session');expect(JSON.parse(String(options.body)).director_scope).toEqual({source_digest:snapshot.digest,responsibility:'Opening',scene_ids:['a']});
 }finally{vi.unstubAllGlobals();}
});
it('mounted Director console keeps parent editing locked for child intent and reopens explicitly',async()=>{
 const {GraphDirectorConsole}=await import('./GraphDirectorConsole');
 const api={history:vi.fn(),derive:vi.fn(),list:vi.fn(async()=>({items:[source]})),capabilities:vi.fn(async()=>({enabled:true,can_mutate:true,modes:['DIRECTOR']})),create:vi.fn(),update:vi.fn(),deriveDirectorScope:vi.fn(async()=>result()),export:vi.fn(async(id:string)=>({document:id==='child'?result():source,document_digest:id==='child'?'c'.repeat(64):snapshot.digest,format:'creative-json/1',boundary:'original-owner'}))};
 const pending=vi.fn();render(<GraphDirectorConsole client={api as any} pin={snapshot} active canMutate busy={false} isCurrent={()=>true} read={work=>work()} mutate={work=>work()} onDirtyChange={pending}/>);
 fireEvent.click(screen.getByText('打开导演总控台'));await waitFor(()=>expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
 fireEvent.click(screen.getByText('读取选中导演节点原文档'));await screen.findByLabelText('子导演职责');fill();await waitFor(()=>expect(pending).toHaveBeenLastCalledWith(true));
 expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(true);expect((screen.getByText('创建所选场景子导演') as HTMLButtonElement).disabled).toBe(false);
 fireEvent.click(screen.getByText('创建所选场景子导演'));await screen.findByText(/已创建 Opening/);await waitFor(()=>expect(pending).toHaveBeenLastCalledWith(false));expect(api.export).not.toHaveBeenCalledWith('child');
 fireEvent.click(screen.getByText('读取新子导演原文档'));await waitFor(()=>expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Opening'));expect(api.export).toHaveBeenCalledWith('child');expect(api.create).not.toHaveBeenCalled();expect(api.update).not.toHaveBeenCalled();
});
