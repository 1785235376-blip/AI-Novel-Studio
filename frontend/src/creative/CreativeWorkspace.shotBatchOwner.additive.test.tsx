// @vitest-environment jsdom
import type {ComponentProps} from 'react';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {CreativeWorkspace,type CreativeWorkspaceProps} from './CreativeWorkspace';
import {prepareStoryboardEditor,storyboardEditorRequest} from './storyboardEditorHandoff';
import {newDocument,newScene,newShot,type CreativeDocument} from './types';
import type {CreativeCanvas} from './CreativeCanvas';
import type {StoryboardProductionPanel} from './StoryboardProductionPanel';
import {useLocalHostSession} from '../localHostSession';

// Retain callbacks at the real author boundary; keep its Canvas and batch tools mounted.
const captured=vi.hoisted(()=>({canvas:undefined as ComponentProps<typeof CreativeCanvas>|undefined,production:undefined as ComponentProps<typeof StoryboardProductionPanel>|undefined}));
vi.mock('./CreativeCanvas',async()=>{
 const original=await vi.importActual<typeof import('./CreativeCanvas')>('./CreativeCanvas');
 return {...original,CreativeCanvas:(props:ComponentProps<typeof CreativeCanvas>)=>{captured.canvas=props;return <original.CreativeCanvas {...props}/>;}};
});
vi.mock('./StoryboardProductionPanel',async()=>{
 const original=await vi.importActual<typeof import('./StoryboardProductionPanel')>('./StoryboardProductionPanel');
 return {...original,StoryboardProductionPanel:(props:ComponentProps<typeof StoryboardProductionPanel>)=>{captured.production=props;return <original.StoryboardProductionPanel {...props}/>;}};
});
const response=(body:unknown)=>({ok:true,status:200,json:async()=>body});
const pin={id:'source-director',version:4,digest:'a'.repeat(64)};
let fetchMock:ReturnType<typeof vi.fn>;
beforeEach(()=>{
 fetchMock=vi.fn(async(url:string,init:RequestInit)=>{
  if(init.method==='PUT')return response({...board(),...JSON.parse(String(init.body)),version:9});
  if(url.endsWith('/creation-reference-data'))return response({characters:[],locations:[],story_routes:[]});
  if(url.endsWith('/assets'))return response([]);
  throw new Error(`Unexpected request ${url}`);
 });vi.stubGlobal('fetch',fetchMock);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();captured.canvas=undefined;captured.production=undefined;});
function board():CreativeDocument{return {...newDocument('STORYBOARD'),id:'board',title:'Pinned board',version:8,status:'DRAFT',source_independent:true,actor_id:'author',created_at:'',updated_at:'',source_evidence:{},source_documents:{[pin.id]:{version:pin.version,digest:pin.digest}},scenes:[{...newScene(1),id:'scene'},{...newScene(2),id:'other'}],shots:[{...newShot(1,'scene'),id:'one',frame_prompt:'Keep frame',duration_seconds:7},{...newShot(2,'scene'),id:'two',video_generation_hint:'Keep hint'},{...newShot(3,'other'),id:'three'}]};}
function props():CreativeWorkspaceProps{
 const doc=board(),request=storyboardEditorRequest(doc,'b'.repeat(64),pin);
 return {enabled:true,novelId:'project',context:{sessionToken:'test'},scope:{workspace:'Local',project:'Project',storyline:'Story',branch:'Main'},actor:'Author',chapterCount:0,manuscriptReady:false,novelMain:null,novelSidebar:null,novelInspector:null,novelStatus:null,onExit:vi.fn(),onModuleChange:vi.fn(),storyboardHost:{module:'IMAGE',returnLabel:'返回独立创作图',prepared:prepareStoryboardEditor(request,{document:doc,document_digest:'b'.repeat(64)},{enabled:true,can_mutate:true,modes:['STORYBOARD']}),isCurrent:()=>true}};
}
const button=(name:string)=>screen.getByRole('button',{name});
function retained(element:HTMLElement){return (element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick as ()=>void;}
function stage(){fireEvent.click(screen.getByText('批量设置所选镜头语言'));fireEvent.click(screen.getByLabelText('批量选择镜头 1 · one'));fireEvent.change(screen.getByLabelText('批量镜头新值'),{target:{value:'WIDE'}});fireEvent.click(button('预览所选镜头语言'));}
const apply=()=>button('确认批量应用到分镜草稿（尚未保存）');
const undo=()=>button('撤销本次镜头语言批量编辑');
const writes=()=>fetchMock.mock.calls.filter(([,init])=>init.method!=='GET');

it.each(['edit','draft ABA'] as const)('rejects retained batch Apply after same-batch original author %s',kind=>{
 render(<CreativeWorkspace {...props()}/>);stage();const old=retained(apply()),owner=captured.canvas!,initial=owner.draft;
 act(()=>{owner.onChange({...initial,title:'Intervening author edit'});if(kind==='draft ABA')owner.onChange(initial);old();});
 expect(captured.canvas!.draft.title).toBe(kind==='edit'?'Intervening author edit':initial.title);
 expect(captured.canvas!.draft.shots).toEqual(initial.shots);expect(writes()).toHaveLength(0);
});
it.each(['edit','draft ABA'] as const)('rejects retained batch Undo after same-batch original author %s',kind=>{
 render(<CreativeWorkspace {...props()}/>);stage();fireEvent.click(apply());const old=retained(undo()),owner=captured.canvas!,applied=owner.draft;
 act(()=>{owner.onChange({...applied,title:'Later author edit'});if(kind==='draft ABA')owner.onChange(applied);old();});
 expect(captured.canvas!.draft.title).toBe(kind==='edit'?'Later author edit':applied.title);
 expect(captured.canvas!.draft.shots).toEqual(applied.shots);expect(writes()).toHaveLength(0);
});
it.each(['Apply','Undo'] as const)('rejects retained %s after same-batch scene ABA',kind=>{
 render(<CreativeWorkspace {...props()}/>);stage();if(kind==='Undo')fireEvent.click(apply());
 const old=retained(kind==='Apply'?apply():undo()),owner=captured.canvas!,initial=owner.draft;
 act(()=>{owner.onScene('other');owner.onScene('scene');old();});
 expect(captured.canvas!.draft).toBe(initial);expect(writes()).toHaveLength(0);
});
it.each(['Apply','Undo'] as const)('rejects retained %s after same-batch production dirty ABA',kind=>{
 render(<CreativeWorkspace {...props()}/>);stage();if(kind==='Undo')fireEvent.click(apply());
 const old=retained(kind==='Apply'?apply():undo()),initial=captured.canvas!.draft,owner=captured.production!;
 act(()=>{owner.onDirtyChange(true);owner.onDirtyChange(false);old();});
 expect(captured.canvas!.draft).toBe(initial);expect(writes()).toHaveLength(0);
 expect(screen.queryByRole('button',{name:'确认批量应用到分镜草稿（尚未保存）'})).toBeNull();
 expect((undo() as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByLabelText('批量选择镜头 1 · one'));fireEvent.change(screen.getByLabelText('批量镜头新值'),{target:{value:'CLOSE'}});fireEvent.click(button('预览所选镜头语言'));
 expect(apply()).toBeTruthy();expect(writes()).toHaveLength(0);
});
it('rejects an old Apply during and after original production busy work',async()=>{
 render(<CreativeWorkspace {...props()}/>);stage();const old=retained(apply()),initial=captured.canvas!.draft,owner=captured.production!;
 let resolve!:()=>void;const pending=new Promise<void>(done=>{resolve=done;});let work!:Promise<void>;
 act(()=>{work=owner.perform(()=>pending);old();});
 expect(captured.canvas!.draft).toBe(initial);expect(captured.canvas!.busy).toBe(true);
 await act(async()=>{resolve();await work;});act(old);
 expect(captured.canvas!.draft).toBe(initial);expect(captured.canvas!.busy).toBe(false);expect(writes()).toHaveLength(0);
});
it('rejects retained Apply after synchronous original host authority revocation and ABA',()=>{
 let allowed=true;const p=props();p.storyboardHost={...p.storyboardHost!,isCurrent:()=>allowed};
 render(<CreativeWorkspace {...p}/>);stage();const old=retained(apply());
 act(()=>{allowed=false;useLocalHostSession.setState({epoch:useLocalHostSession.getState().epoch+1});allowed=true;old();});
 expect(screen.queryByLabelText('文档标题')).toBeNull();expect(writes()).toHaveLength(0);
});
it('applies once, undoes exactly, and saves an explicit new preview with original expected_version',async()=>{
 render(<CreativeWorkspace {...props()}/>);stage();const initial=captured.canvas!.draft,old=retained(apply());act(()=>{old();old();});
 expect(captured.canvas!.draft).toEqual({...initial,shots:initial.shots.map(row=>row.id==='one'?{...row,shot_size:'WIDE'}:row)});expect(writes()).toHaveLength(0);
 const applied=captured.canvas!.draft,back=retained(undo());act(()=>{back();back();});expect(captured.canvas!.draft).toEqual(initial);expect(captured.canvas!.dirty).toBe(false);
 // The details remain open; restage without toggling their visibility.
 fireEvent.click(screen.getByLabelText('批量选择镜头 1 · one'));fireEvent.change(screen.getByLabelText('批量镜头新值'),{target:{value:'WIDE'}});fireEvent.click(button('预览所选镜头语言'));fireEvent.click(apply());
 expect(captured.canvas!.draft).toEqual(applied);expect(writes()).toHaveLength(0);fireEvent.click(button('保存草稿'));
 await screen.findByText('已保存“Pinned board” · v9');expect(writes()).toHaveLength(1);
 const [url,init]=writes()[0];expect(url).toContain('/documents/board');expect(JSON.parse(String(init.body))).toEqual({...applied,expected_version:8});expect(captured.canvas!.dirty).toBe(false);
});
