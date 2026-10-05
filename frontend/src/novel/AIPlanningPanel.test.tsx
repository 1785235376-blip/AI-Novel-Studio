// @vitest-environment jsdom
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {AIPlanningPanel} from './AIPlanningPanel';
import {api,planningApi,type PlanningRun} from '../api';
vi.mock('../api',()=>({api:{textModels:vi.fn()},planningApi:{list:vi.fn(),create:vi.fn(),save:vi.fn(),cancel:vi.fn()},apiErrorView:(error:Error)=>({message:error.message})}));
const chapter={id:'n:1',novel_id:'n',version:5,title:'第一章',content:'正文',number:1,word_count:2,status:'DRAFT',document:{}};
const run:PlanningRun={id:'run',novel_id:'n',version:4,status:'READY',request:{kind:'ABILITY',mode:'LOCAL_EXPLICIT',candidate_count:2},sources:[{chapter_id:'n:1',chapter_version:5,content_sha256:'hash',truncated:false,excerpt_characters:2}],candidates:[{id:'c',record:{kind:'ABILITY',title:'规则',description:'需要代价',rules:['需要代价']},evidence:[{chapter_id:'n:1',chapter_version:5,content_sha256:'hash',start:0,end:2,quote:'正文'}],record_id:null,status:'DRAFT',analysis_source:'LOCAL_EXPLICIT'}],findings:[],created_at:'2026-10-05',usage_status:'NOT_APPLICABLE',execution_mode:'local_explicit'};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(planningApi.list).mockResolvedValue({items:[]});vi.mocked(api.textModels).mockResolvedValue([{provider_id:'local',model_id:'a:b',display_name:'本地模型',available:true}])});
afterEach(cleanup);
describe('structured planning review',()=>{
 it('submits source version with local extraction by default and guards double click',async()=>{
  let resolve!:Function;vi.mocked(planningApi.create).mockImplementation(()=>new Promise(r=>{resolve=r}));
  render(<AIPlanningPanel novelId="n" chapter={chapter} onSaved={vi.fn()}/>);
  await screen.findByText('暂无规划任务');
  fireEvent.click(screen.getByRole('button',{name:'提取明确标记'}));
  fireEvent.click(screen.getByRole('button',{name:'正在提交…'}));
  expect(planningApi.create).toHaveBeenCalledTimes(1);
  expect(planningApi.create).toHaveBeenCalledWith('n',{kind:'ABILITY',mode:'LOCAL_EXPLICIT',sources:[{chapter_id:'n:1',expected_version:5}],candidate_count:2},undefined);
  resolve(run);await screen.findByText('任务已保存，可关闭后重新打开查看。');
 });
 it('selects a model without an allow-cloud or target bypass and preserves failures',async()=>{
  vi.mocked(planningApi.create).mockRejectedValue(new Error('隐私未审核'));
  render(<AIPlanningPanel novelId="n" chapter={chapter} onSaved={vi.fn()}/>);
  await screen.findByText('暂无规划任务');
  fireEvent.change(screen.getByLabelText('规划方式'),{target:{value:'MODEL'}});
  fireEvent.change(screen.getByLabelText('规划文本模型'),{target:{value:JSON.stringify(['local','a:b'])}});
  fireEvent.click(screen.getByRole('button',{name:'生成待审建议'}));
  await screen.findByText(/隐私未审核/);
  expect(planningApi.create).toHaveBeenCalledWith('n',expect.objectContaining({provider_id:'local',model_id:'a:b',mode:'MODEL'}),undefined);
  expect(vi.mocked(planningApi.create).mock.calls[0][1]).not.toHaveProperty('allow_cloud_excerpt');
  expect((screen.getByLabelText('规划文本模型') as HTMLSelectElement).value).toBe(JSON.stringify(['local','a:b']));
 });
 it('reopens evidence and explicitly saves only as Draft with optimistic version',async()=>{
  const onSaved=vi.fn();vi.mocked(planningApi.list).mockResolvedValue({items:[run]});
  const saved={...run,candidates:[{...run.candidates[0],record_id:'record'}],version:5};
  vi.mocked(planningApi.save).mockResolvedValue({run:saved,record:{id:'record',status:'DRAFT'} as any});
  render(<AIPlanningPanel novelId="n" chapter={chapter} onSaved={onSaved}/>);
  fireEvent.click(await screen.findByRole('button',{name:'保存此候选为草稿'}));
  await screen.findByRole('button',{name:'已保存为草稿'});
  expect(planningApi.save).toHaveBeenCalledWith('n','run','c',4,undefined);
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({status:'DRAFT'}));
  expect(screen.getByText(/字符 0–2：正文/)).toBeTruthy();
 });
 it('cancels pending task and prevents active duplicate submissions',async()=>{
  vi.mocked(planningApi.list).mockResolvedValue({items:[{...run,status:'WORKING',candidates:[],execution_mode:null}]});
  vi.mocked(planningApi.cancel).mockResolvedValue({...run,status:'CANCELLED',candidates:[],execution_mode:null});
  render(<AIPlanningPanel novelId="n" chapter={chapter} onSaved={vi.fn()}/>);
  fireEvent.click(await screen.findByRole('button',{name:'取消规划任务'}));
  await waitFor(()=>expect(planningApi.cancel).toHaveBeenCalledWith('n','run',4,undefined));
  await screen.findByText('已取消');
 });
 it('late requests from old project cannot populate new project',async()=>{
  let resolve!:Function;vi.mocked(planningApi.list).mockImplementationOnce(()=>new Promise(r=>{resolve=r}));
  const view=render(<AIPlanningPanel novelId="old" chapter={chapter} onSaved={vi.fn()}/>);
  view.rerender(<AIPlanningPanel novelId="new" chapter={chapter} onSaved={vi.fn()}/>);
  await screen.findByText('暂无规划任务');resolve({items:[run]});
  await new Promise(r=>setTimeout(r,0));expect(screen.queryByText('规则')).toBeNull();
 });
 it('incomplete marker findings keep empty results honest',async()=>{
  vi.mocked(planningApi.list).mockResolvedValue({items:[{...run,candidates:[],findings:[{code:'PLOT_MARKERS_INCOMPLETE',chapter_id:'n:1',missing_fields:['ending'],duplicate_fields:[],fields:{act1:'开始'},evidence:[]}]}]});
  render(<AIPlanningPanel novelId="n" chapter={chapter} onSaved={vi.fn()}/>);
  await screen.findByText('未发现完整明确结构');
  expect(screen.queryByRole('button',{name:'保存此候选为草稿'})).toBeNull();
 });
});
