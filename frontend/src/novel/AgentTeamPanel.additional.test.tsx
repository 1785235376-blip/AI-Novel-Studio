// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {AgentTeamPanel,AgentJobHistory} from './AgentTeamPanel';
import {api,type CreativeAgent} from '../api';
import {useStudio} from '../store';
const reviewer:CreativeAgent={id:'reviewer',name:'审核 Agent',description:'审核已保存章节。',prompt_role:'continuity_reviewer',tools:['context.read','chapter.read'],output_schema:'continuity_findings',requires_approval:false};
const verifier:CreativeAgent={...reviewer,id:'verifier',name:'核验 Agent',description:'核验世界与人物。',prompt_role:'verifier',output_schema:'verification_findings'};
const planner:CreativeAgent={...reviewer,id:'planner',name:'策划 Agent',requires_approval:true};
const clients:QueryClient[]=[];
function mount(component:React.ReactNode){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}>{component}</QueryClientProvider>)}
beforeEach(()=>{vi.spyOn(api,'agents').mockResolvedValue({catalog_version:'1.0',agents:[planner],additional_agents:[reviewer,verifier]});vi.spyOn(api,'textModels').mockResolvedValue([]);useStudio.getState().setCollaboration('');useStudio.getState().setTextModel(null)});
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks()});
it.each([reviewer,verifier])('lets the author select and execute additional role $id',async agent=>{
 useStudio.getState().setTextModel({providerId:'local-runtime',modelId:'actual-model'});
 const create=vi.spyOn(api,'createAgentJob').mockResolvedValue({id:'additional-job',status:'QUEUED'}),start=vi.spyOn(api,'startAgentJob').mockResolvedValue({id:'additional-job',status:'COMPLETED',execution_mode:'model',agent_name:agent.name,result:{summary:'已核对',findings:[]}});
 mount(<AgentTeamPanel chapter={{id:'n:1',novel_id:'n',number:1,title:'第一章',version:2} as any}/>);
 const selection=await screen.findByLabelText('Agent 角色');fireEvent.change(selection,{target:{value:agent.id}});
 expect(screen.getByText(agent.description,{selector:'.novel-help'})).toBeTruthy();
 fireEvent.change(screen.getByLabelText('执行方式'),{target:{value:'model'}});fireEvent.change(screen.getByLabelText('任务说明'),{target:{value:'核对身份揭示'}});fireEvent.click(screen.getByRole('button',{name:'启动任务'}));
 await waitFor(()=>expect(create).toHaveBeenCalledWith(expect.objectContaining({agent_id:agent.id,chapter_id:'n:1',instruction:'核对身份揭示',execution_mode:'model',provider_id:'local-runtime',model_id:'actual-model'})));
 expect(start).toHaveBeenCalledWith('additional-job');
});
it('shows additional roles when there are no legacy roles and chooses a registered default',async()=>{
 vi.mocked(api.agents).mockResolvedValue({catalog_version:'1.0',agents:[],additional_agents:[verifier]});const create=vi.spyOn(api,'createAgentJob').mockResolvedValue({id:'job',status:'QUEUED'});vi.spyOn(api,'startAgentJob').mockResolvedValue({id:'job',status:'VALIDATED',execution_mode:'deterministic'});
 mount(<AgentTeamPanel chapter={{id:'n:1',novel_id:'n',number:1} as any}/>);
 await waitFor(()=>expect((screen.getByLabelText('Agent 角色') as HTMLSelectElement).value).toBe('verifier'));
 fireEvent.click(screen.getByRole('button',{name:'启动任务'}));await waitFor(()=>expect(create).toHaveBeenCalledWith(expect.objectContaining({agent_id:'verifier'})));
 expect(screen.queryByText('暂无 Agent')).toBeNull();
});
it('deduplicates role identity and preserves the original role definition',async()=>{
 vi.mocked(api.agents).mockResolvedValue({catalog_version:'1.0',agents:[planner,reviewer],additional_agents:[{...reviewer,name:'Duplicate reviewer'},verifier]});mount(<AgentTeamPanel/>);
 const select=await screen.findByLabelText('Agent 角色');expect(within(select).getAllByRole('option')).toHaveLength(3);expect(screen.queryByText('Duplicate reviewer')).toBeNull();
 expect(within(screen.getByRole('list',{name:'Creative Agent 角色'})).getAllByRole('listitem')).toHaveLength(3);
});
it('filters the original persisted job history by additional role identity',async()=>{
 const jobs=vi.spyOn(api,'agentJobs').mockResolvedValue({items:[],total:0,has_more:false} as any);mount(<AgentJobHistory novelId="n"/>);
 await screen.findByRole('option',{name:'核验 Agent'});fireEvent.change(screen.getByLabelText('历史 Agent 筛选'),{target:{value:'verifier'}});
 await waitFor(()=>expect(jobs).toHaveBeenLastCalledWith(expect.objectContaining({novelId:'n',agentId:'verifier'})));
});
