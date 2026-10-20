// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ApiError} from '../api';
import {GraphDirectorRunOverview} from './GraphDirectorRunOverview';
import {directorRunBranch,projectDirectorRun} from './directorRunOverview';
import {imageGraphRecord,imageGraphRun} from './studioImageGraph.testFixtures';
import {useStudioGraphEditorController,type StudioGraphEditorProps} from './useStudioGraphEditorController';
import {studioGraphEditorView} from './studioGraphEditorView';
import type {StudioClient} from './studioClient';
import type {StudioGraphRun} from './studioGraphTypes';
import productionCatalog from './fixtures/productionGraph.catalog.json';
const execute=async<T,>(work:()=>Promise<T>)=>work();
function setup(){
 const graph=imageGraphRecord();graph.definition.nodes=[
  {id:'director',definition_id:'director_plan',definition_version:1,enabled:true,position:{x:0,y:0},parameters:{document_snapshot:{id:'source',version:1,digest:'a'.repeat(64)}}},
  {id:'board',definition_id:'storyboard_plan',definition_version:1,enabled:true,position:{x:300,y:0},parameters:{document_snapshot:{id:'storyboard',version:1,digest:'b'.repeat(64)}}},
  {id:'unrelated',definition_id:'text_input',definition_version:1,enabled:true,position:{x:600,y:0},parameters:{text:'unrelated author text'}},
 ];graph.definition.edges=[{id:'direction',source_node_id:'director',source_port:'direction',target_node_id:'board',target_port:'direction'}];graph.reference_states=[];
 const run:StudioGraphRun={...imageGraphRun(),id:'run1',graph_id:graph.id,graph_version:graph.version,status:'FAILED',current_node_id:'board',node_states:{director:{status:'SUCCEEDED',output:{text:'PRIVATE OUTPUT MUST NOT BE SHOWN'},error:null},board:{status:'FAILED',output:null,error:{code:'SYNTHETIC'}},unrelated:{status:'SUCCEEDED',output:{text:'UNRELATED PRIVATE OUTPUT'},error:null}}};
 const api={runs:vi.fn(async(_graphId:string,_signal?:AbortSignal)=>({items:[structuredClone(run)]})),getRun:vi.fn(async(id:string,_signal?:AbortSignal)=>({...structuredClone(run),id})),save:vi.fn(),create:vi.fn(),createRun:vi.fn(),action:vi.fn(),readDirectorWorkspace:vi.fn()};
 const props={client:api,definition:graph.definition,base:graph,nodeId:'director',identity:'owner',active:true,busy:false,isCurrent:()=>true,read:execute,onLocate:vi.fn(()=>true)};
 return{graph,run,api,props};
}
const click=(name:string)=>fireEvent.click(screen.getByRole('button',{name}));
const retained=(name:string)=>{const element=screen.getByRole('button',{name});return(element as any)[Object.keys(element).find(key=>key.startsWith('__reactProps$'))!].onClick as()=>void;};
async function choose(id='run1'){click('读取导演分支运行目录');await screen.findByRole('option',{name:new RegExp(id)});fireEvent.change(screen.getByLabelText('导演分支运行记录 director'),{target:{value:id}});}
async function inspect(){click('读取／刷新所选导演分支运行');await screen.findByText(/本分支返回状态/);}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(yes=>resolve=yes);return{promise,resolve};}
afterEach(cleanup);
it('projects only structural descendants and status metadata, preserving missing statuses and rejecting foreign scope',()=>{
 const f=setup();const run={...f.run,node_states:{director:f.run.node_states.director}};const result=projectDirectorRun(run,f.graph,'director');
 expect(directorRunBranch(f.graph.definition,'director').map(row=>row.id)).toEqual(['director','board']);expect(result.rows[1].status).toBeUndefined();expect(JSON.stringify(result)).not.toContain('PRIVATE');expect(JSON.stringify(result)).not.toContain('output');
 expect(()=>projectDirectorRun({...run,scope:{mode:'local',novel_id:'foreign'}},f.graph,'director')).toThrow();expect(()=>projectDirectorRun({...run,graph_version:2},f.graph,'director')).toThrow();
});
it('explicitly reads original runs then the selected receipt and locates only branch nodes without writing',async()=>{
 const f=setup();render(<GraphDirectorRunOverview {...f.props}/>);expect(f.api.runs).not.toHaveBeenCalled();await choose();expect(f.api.getRun).not.toHaveBeenCalled();await inspect();
 expect(f.api.runs).toHaveBeenCalledWith(f.graph.id,expect.any(AbortSignal));expect(f.api.getRun).toHaveBeenCalledWith('run1',expect.any(AbortSignal));expect(screen.getByText(/成功 1，失败 1/)).toBeTruthy();
 expect(screen.queryByText(/PRIVATE OUTPUT/)).toBeNull();expect(screen.queryByRole('button',{name:'定位导演分支节点 unrelated'})).toBeNull();click('定位导演分支节点 board');expect(f.props.onLocate).toHaveBeenCalledWith('board',f.graph);
 for(const method of [f.api.save,f.api.create,f.api.createRun,f.api.action])expect(method).not.toHaveBeenCalled();
});
it('filters old graph versions in the directory and refuses a mismatched fresh receipt',async()=>{
 const f=setup();f.api.runs.mockResolvedValue({items:[f.run,{...f.run,id:'old-version',graph_version:0},{...f.run,id:'other-project',project_id:'other'}]});render(<GraphDirectorRunOverview {...f.props}/>);await choose();expect(screen.queryByRole('option',{name:/old-version|other-project/})).toBeNull();
 f.api.getRun.mockResolvedValue({...f.run,graph_id:'foreign'});click('读取／刷新所选导演分支运行');await screen.findByText(/运行不属于当前已保存图版本/);expect(screen.queryByRole('button',{name:'定位导演分支节点 board'})).toBeNull();
});
it.each(['busy','graph','authority'] as const)('retires prior status and retained Locate through %s ABA',async kind=>{
 const f=setup();const view=render(<GraphDirectorRunOverview {...f.props}/>);await choose();await inspect();const locate=retained('定位导演分支节点 board');
 const changed=kind==='busy'?{busy:true}:kind==='graph'?{base:{...f.graph,id:'other-graph'}}:{isCurrent:()=>false};
 view.rerender(<GraphDirectorRunOverview {...f.props} {...changed}/>);view.rerender(<GraphDirectorRunOverview {...f.props}/>);act(()=>locate());expect(f.props.onLocate).not.toHaveBeenCalled();expect(screen.queryByText(/本分支返回状态/)).toBeNull();
});
it('retires old Read and Locate callbacks synchronously when the explicit run choice changes',async()=>{
 const f=setup();f.api.runs.mockResolvedValue({items:[f.run,{...f.run,id:'run2'}]});render(<GraphDirectorRunOverview {...f.props}/>);await choose();const read=retained('读取／刷新所选导演分支运行');
 act(()=>{fireEvent.change(screen.getByLabelText('导演分支运行记录 director'),{target:{value:'run2'}});read();});expect(f.api.getRun).not.toHaveBeenCalled();await inspect();const locate=retained('定位导演分支节点 board');
 act(()=>{fireEvent.change(screen.getByLabelText('导演分支运行记录 director'),{target:{value:'run1'}});locate();});expect(f.props.onLocate).not.toHaveBeenCalled();
});
it('aborts late reads and prevents an old finally from clearing a newer pending directory read',async()=>{
 const f=setup(),old=deferred<{items:StudioGraphRun[]}>(),fresh=deferred<{items:StudioGraphRun[]}>();f.api.runs.mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);const view=render(<GraphDirectorRunOverview {...f.props}/>);
 click('读取导演分支运行目录');const signal=f.api.runs.mock.calls[0][1] as AbortSignal;view.rerender(<GraphDirectorRunOverview {...f.props} busy/>);view.rerender(<GraphDirectorRunOverview {...f.props}/>);expect(signal.aborted).toBe(true);click('读取导演分支运行目录');
 await act(async()=>old.resolve({items:[f.run]}));expect((screen.getByRole('button',{name:'读取导演分支运行目录'}) as HTMLButtonElement).disabled).toBe(true);expect(screen.queryByRole('option',{name:/run1/})).toBeNull();
 await act(async()=>fresh.resolve({items:[{...f.run,id:'fresh'}]}));await screen.findByRole('option',{name:/fresh/});expect(screen.queryByRole('option',{name:/run1/})).toBeNull();
});
it('closes private status on original-owner denial and cannot replay the retained read',async()=>{
 const f=setup();render(<GraphDirectorRunOverview {...f.props}/>);await choose();await inspect();const read=retained('读取／刷新所选导演分支运行');f.api.getRun.mockRejectedValue(new ApiError({status:403,code:'DENIED',message:'Denied'}));click('读取／刷新所选导演分支运行');await screen.findByText(/先前状态已关闭/);expect(screen.queryByText(/本分支返回状态/)).toBeNull();act(()=>read());expect(f.api.getRun).toHaveBeenCalledTimes(2);
});
it('ignores an aborted late run receipt after the saved graph version changes',async()=>{
 const f=setup(),late=deferred<StudioGraphRun>();const view=render(<GraphDirectorRunOverview {...f.props}/>);await choose();f.api.getRun.mockReturnValueOnce(late.promise);click('读取／刷新所选导演分支运行');
 const signal=f.api.getRun.mock.calls[0][1] as AbortSignal;view.rerender(<GraphDirectorRunOverview {...f.props} base={{...f.graph,version:2}}/>);expect(signal.aborted).toBe(true);
 await act(async()=>late.resolve(f.run));expect(screen.queryByText(/本分支返回状态/)).toBeNull();expect(f.props.onLocate).not.toHaveBeenCalled();
});
it('wires the real graph view and original controller locator without changing graph/history or saving',async()=>{
 const f=setup(),graphs={...f.api,catalog:vi.fn(async()=>productionCatalog),productionCatalog:vi.fn(async()=>productionCatalog),list:vi.fn(async()=>({items:[f.graph]})),get:vi.fn(async()=>f.graph)};
 const props:StudioGraphEditorProps={active:true,denied:false,identity:'mounted-owner',client:{graphs} as unknown as StudioClient,canMutate:true,canReview:true,busy:false,externalDirty:false,isCurrent:()=>true,read:execute,mutate:execute};let controller!:ReturnType<typeof useStudioGraphEditorController>;
 function Mounted(){controller=useStudioGraphEditorController(props);return studioGraphEditorView(controller,props).content;}render(<Mounted/>);await screen.findByRole('option',{name:/Independent image graph/});
 fireEvent.change(screen.getByLabelText('已保存创作图'),{target:{value:f.graph.id}});await screen.findByRole('checkbox',{name:/对照 director/});fireEvent.click(screen.getByRole('checkbox',{name:/对照 director/}));
 await choose();await inspect();const before=structuredClone(controller.draft);click('定位导演分支节点 board');await waitFor(()=>expect(controller.selected).toEqual(['board']));expect(controller.draft).toEqual(before);expect(controller.past).toEqual([]);expect(graphs.save).not.toHaveBeenCalled();expect(graphs.createRun).not.toHaveBeenCalled();
});
