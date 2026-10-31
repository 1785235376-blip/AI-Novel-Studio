// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {AIPlanningPanel} from './AIPlanningPanel';
import {api,planningApi,type PlanningRun} from '../api';

vi.mock('../api',()=>({api:{textModels:vi.fn()},planningApi:{list:vi.fn(),create:vi.fn(),save:vi.fn(),cancel:vi.fn(),apply:vi.fn()},apiErrorView:(reason:Error)=>({message:reason.message})}));
const premise='一个失忆者在废弃城市寻找过去身份，最终发现自己曾经毁灭城市。';
function projectRun(kind='WORLD'):PlanningRun {
 const record=kind==='WORLD'?{kind,title:'废城世界',description:'毁灭后的城市',world_summary:'记忆驱动机器的废城',world_rules:[{statement:'力量会消耗记忆',forbidden_terms:['无需代价']}],locations:[{name:'钟塔',description:'主角醒来处',rules:'进入要付出记忆',atmosphere:'寂静'}]}
 :kind==='CHARACTERS'?{kind,title:'失忆者',description:'寻找过去身份',characters:[{name:'旅人',role:'主角',personality:'谨慎',goal:'寻找身份',age:27,status:'ALIVE'}]}
 :{kind,title:'身份悬疑',description:'三幕剧情',outline:{theme:'身份与赎罪',premise,structure:'THREE_ACT',beginning:'在钟塔醒来',middle:'寻找过去',ending:'发现自己毁城',main_conflict:'害怕真相',climax:'打开记忆核心'}};
 return {id:'project-run',novel_id:'n',version:4,status:'READY',request:{kind,mode:'MODEL',premise,provider_id:'local',model_id:'actual:model',candidate_count:1},sources:[],candidates:[{id:'candidate',record,evidence:[],record_id:null,status:'DRAFT',analysis_source:'MODEL'}],findings:[],execution_mode:'real',created_at:'2026-10-07',usage_status:'REPORTED'};
}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done});return {promise,resolve};}
beforeEach(()=>{vi.clearAllMocks();vi.mocked(planningApi.list).mockResolvedValue({items:[]});vi.mocked(api.textModels).mockResolvedValue([{provider_id:'local',model_id:'actual:model',display_name:'真实本地模型',available:true}])});
afterEach(cleanup);
async function prepare(kind='WORLD'){
 await screen.findByText('暂无规划任务');
 fireEvent.change(screen.getByLabelText('规划方式'),{target:{value:'MODEL'}});
 fireEvent.change(screen.getByLabelText('候选类型'),{target:{value:kind}});
 fireEvent.change(screen.getByLabelText('规划文本模型'),{target:{value:JSON.stringify(['local','actual:model'])}});
 fireEvent.change(screen.getByLabelText('故事创意与规划要求'),{target:{value:premise}});
}
it.each(['WORLD','CHARACTERS','OUTLINE'])('creates a %s proposal from a premise without requiring a chapter or applying it',async kind=>{
 const row=projectRun(kind);vi.mocked(planningApi.create).mockResolvedValue(row);
 render(<AIPlanningPanel novelId="n" onSaved={vi.fn()}/>);await prepare(kind);
 fireEvent.change(screen.getByLabelText('比较候选数'),{target:{value:'1'}});
 fireEvent.click(screen.getByRole('button',{name:'生成待审建议'}));
 await screen.findByRole('button',{name:'审阅并采用项目方案'});
 expect(planningApi.create).toHaveBeenCalledWith('n',{kind,mode:'MODEL',premise,sources:[],candidate_count:1,provider_id:'local',model_id:'actual:model'},undefined);
 expect(planningApi.apply).not.toHaveBeenCalled();expect(planningApi.save).not.toHaveBeenCalled();
 if(kind==='WORLD'){expect(screen.getByText(/记忆驱动机器的废城/)).toBeTruthy();expect(screen.getByText(/力量会消耗记忆/)).toBeTruthy();expect(screen.getByRole('region',{name:'地点候选 钟塔'})).toBeTruthy();}
 else if(kind==='CHARACTERS'){expect(screen.getByText('目标：寻找身份')).toBeTruthy();expect(screen.getByText('状态：ALIVE')).toBeTruthy();}
 else {expect(screen.getByText('结局：发现自己毁城')).toBeTruthy();expect(screen.getByText('高潮：打开记忆核心')).toBeTruthy();}
});
it('requires review and explicit confirmation, then sends exact run CAS only once',async()=>{
 const row=projectRun(),pending=deferred<any>(),onApplied=vi.fn();
 vi.mocked(planningApi.list).mockResolvedValue({items:[row]});vi.mocked(planningApi.apply).mockReturnValue(pending.promise);
 render(<AIPlanningPanel novelId="n" onSaved={vi.fn()} onApplied={onApplied}/>);
 fireEvent.click(await screen.findByRole('button',{name:'审阅并采用项目方案'}));
 expect(planningApi.apply).not.toHaveBeenCalled();
 const confirm=screen.getByRole('button',{name:'确认采用到故事资料库'});fireEvent.click(confirm);fireEvent.click(confirm);
 expect(planningApi.apply).toHaveBeenCalledTimes(1);expect(planningApi.apply).toHaveBeenCalledWith('n','project-run','candidate',4,undefined);
 const applied={world_summary:'记忆驱动机器的废城',location_ids:['tower'],world_rule_ids:['rule']};
 await act(async()=>pending.resolve({run:{...row,version:5,candidates:[{...row.candidates[0],status:'APPLIED',applied}]},applied}));
 expect(onApplied).toHaveBeenCalledTimes(1);expect(onApplied).toHaveBeenCalledWith(applied);
 expect(screen.getByText('此方案已采用，已写入故事资料库。')).toBeTruthy();
 expect(screen.queryByRole('button',{name:'确认采用到故事资料库'})).toBeNull();
});
it('canceling review never writes a candidate',async()=>{
 vi.mocked(planningApi.list).mockResolvedValue({items:[projectRun()]});render(<AIPlanningPanel novelId="n" onSaved={vi.fn()}/>);
 fireEvent.click(await screen.findByRole('button',{name:'审阅并采用项目方案'}));
 fireEvent.click(screen.getByRole('button',{name:'取消采用'}));
 expect(planningApi.apply).not.toHaveBeenCalled();expect(screen.queryByRole('group',{name:'确认采用项目方案'})).toBeNull();
});
it('retains the proposal and author input when a newer project digest rejects apply',async()=>{
 vi.mocked(planningApi.list).mockResolvedValue({items:[projectRun()]});vi.mocked(planningApi.apply).mockRejectedValue(new Error('作品上下文已有变化，请重新生成'));
 const onApplied=vi.fn();render(<AIPlanningPanel novelId="n" onSaved={vi.fn()} onApplied={onApplied}/>);
 fireEvent.click(await screen.findByRole('button',{name:'复用配置'}));
 fireEvent.click(screen.getByRole('button',{name:'审阅并采用项目方案'}));fireEvent.click(screen.getByRole('button',{name:'确认采用到故事资料库'}));
 await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('作品上下文已有变化');
 expect((screen.getByLabelText('故事创意与规划要求') as HTMLTextAreaElement).value).toBe(premise);
 expect(screen.getByText(/世界观概要：记忆驱动机器的废城/)).toBeTruthy();expect(onApplied).not.toHaveBeenCalled();
});
it('never offers applying simulated output as product data',async()=>{
 vi.mocked(planningApi.list).mockResolvedValue({items:[{...projectRun(),execution_mode:'mock_standin'}]});render(<AIPlanningPanel novelId="n" onSaved={vi.fn()}/>);
 const apply=await screen.findByRole('button',{name:'审阅并采用项目方案'});expect((apply as HTMLButtonElement).disabled).toBe(true);
 expect(screen.getByText(/模拟输出不能采用为作品资料/)).toBeTruthy();fireEvent.click(apply);expect(planningApi.apply).not.toHaveBeenCalled();
});
it('fails closed for a collaboration branch without the project-domain write owner',async()=>{
 vi.mocked(planningApi.list).mockResolvedValue({items:[projectRun()]});
 render(<AIPlanningPanel novelId="n" context={{sessionToken:'private',scope:{workspaceId:'w',projectId:'n',storylineId:'s',branchId:'b'}}} onSaved={vi.fn()}/>);
 fireEvent.click(await screen.findByRole('button',{name:'复用配置'}));
 expect((screen.getByRole('button',{name:'生成待审建议'}) as HTMLButtonElement).disabled).toBe(true);
 expect((screen.getByRole('button',{name:'审阅并采用项目方案'}) as HTMLButtonElement).disabled).toBe(true);
 expect(screen.getByText(/此项目方案流程仅支持本地作品/)).toBeTruthy();
});
it.each(['project','actor','unmount'])('ignores late apply after %s navigation',async change=>{
 const row=projectRun(),pending=deferred<any>(),onApplied=vi.fn();vi.mocked(planningApi.list).mockResolvedValueOnce({items:[row]}).mockResolvedValue({items:[]});vi.mocked(planningApi.apply).mockReturnValue(pending.promise);
 const view=render(<AIPlanningPanel novelId="n" context={{sessionToken:'',actor:{id:'a',workspaceId:'w',displayName:'A'}}} onSaved={vi.fn()} onApplied={onApplied}/>);
 fireEvent.click(await screen.findByRole('button',{name:'审阅并采用项目方案'}));fireEvent.click(screen.getByRole('button',{name:'确认采用到故事资料库'}));
 if(change==='unmount')view.unmount();else view.rerender(<AIPlanningPanel novelId={change==='project'?'other':'n'} context={{sessionToken:'',actor:{id:change==='actor'?'b':'a',workspaceId:'w',displayName:'B'}}} onSaved={vi.fn()} onApplied={onApplied}/>);
 await act(async()=>pending.resolve({run:{...row,version:5},applied:{world_summary:'OLD PRIVATE WORLD'}}));
 expect(onApplied).not.toHaveBeenCalled();expect(screen.queryByText('OLD PRIVATE WORLD')).toBeNull();expect(screen.queryByText(/项目方案已明确采用/)).toBeNull();
});
