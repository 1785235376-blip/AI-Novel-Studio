// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {api,ApiError} from '../api';
import {bindLocalHostSession,clearLocalHostSession,useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {LocalHostSessionPanel} from './LocalHostSessionPanel';
import {AgentTeamPanel,AgentJobHistory} from './AgentTeamPanel';
import {AgentJobDetail} from './AgentJobDetail';
const receipt={session_mode:'LOCAL_HOST',actor_id:'verified-author'} as const;
const clients:QueryClient[]=[];
function mount(component:React.ReactNode){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);return render(<QueryClientProvider client={client}>{component}</QueryClientProvider>)}
beforeEach(()=>{useStudio.getState().setCollaboration('');clearLocalHostSession();useStudio.getState().setNovel('local-work');useStudio.getState().setChapter('local-work:1');localStorage.clear()});
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());clearLocalHostSession();delete window.__AI_NOVEL_PACKAGED_HOST__;vi.restoreAllMocks()});
it('requires an explicit password input and click, validates once, then preserves the selected local manuscript',async()=>{
 let finish!:(value:typeof receipt)=>void;const validate=vi.spyOn(api,'validateLocalHostSession').mockImplementation(()=>new Promise(resolve=>{finish=resolve}));mount(<LocalHostSessionPanel/>);
 expect(validate).not.toHaveBeenCalled();const input=screen.getByLabelText('本机访问凭证') as HTMLInputElement;expect(input.type).toBe('password');expect((screen.getByRole('button',{name:'验证并绑定本机会话'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(input,{target:{value:' synthetic-host '}});fireEvent.click(screen.getByRole('button',{name:'验证并绑定本机会话'}));fireEvent.click(screen.getByRole('button',{name:'验证并绑定本机会话'}));expect(validate).toHaveBeenCalledTimes(1);expect(validate).toHaveBeenCalledWith('synthetic-host');finish(receipt);
 await screen.findByText('已验证本机身份：verified-author');expect(useStudio.getState().novelId).toBe('local-work');expect(useStudio.getState().chapterId).toBe('local-work:1');expect(useStudio.getState().sessionToken).toBe('');expect(localStorage.getItem('studio.session')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'解绑本机可信会话'}));expect(useLocalHostSession.getState().token).toBe('');expect((screen.getByLabelText('本机访问凭证') as HTMLInputElement).value).toBe('');
});
it('shows unauthorized failures without echoing opaque credentials or committing an identity',async()=>{
 vi.spyOn(api,'validateLocalHostSession').mockRejectedValue(new ApiError({status:401,code:'INVALID_SESSION',message:'secret-value'}));mount(<LocalHostSessionPanel/>);fireEvent.change(screen.getByLabelText('本机访问凭证'),{target:{value:'secret-value'}});fireEvent.click(screen.getByRole('button',{name:'验证并绑定本机会话'}));expect((await screen.findByRole('alert')).textContent).toContain('凭证无效');expect(screen.queryByText('secret-value')).toBeNull();expect(useLocalHostSession.getState().token).toBe('');
});
it('does not bind a delayed validation after team navigation or unmount',async()=>{
 let finish!:(value:typeof receipt)=>void;vi.spyOn(api,'validateLocalHostSession').mockImplementation(()=>new Promise(resolve=>{finish=resolve}));const view=mount(<LocalHostSessionPanel/>);fireEvent.change(screen.getByLabelText('本机访问凭证'),{target:{value:'synthetic-host'}});fireEvent.click(screen.getByRole('button',{name:'验证并绑定本机会话'}));useStudio.getState().setCollaboration('team-token',undefined,{workspaceId:'w',projectId:'p',storylineId:'s',branchId:'b'});view.unmount();finish(receipt);await waitFor(()=>expect(useLocalHostSession.getState().token).toBe(''));
});
it('keeps the development Host input absent in packaged and team contexts',()=>{
 useStudio.getState().setCollaboration('team-token');const view=mount(<LocalHostSessionPanel/>);expect(screen.queryByLabelText('本机访问凭证')).toBeNull();view.unmount();useStudio.getState().setCollaboration('');window.__AI_NOVEL_PACKAGED_HOST__=true;mount(<LocalHostSessionPanel/>);expect(screen.queryByLabelText('本机访问凭证')).toBeNull();
});
it('exposes the real API failure on Agent start and keeps the instruction for retry',async()=>{
 vi.spyOn(api,'agents').mockResolvedValue({catalog_version:'1',agents:[{id:'reviewer',name:'审核 Agent',description:'Review',tools:[],prompt_role:'review',output_schema:'review',requires_approval:false}]});vi.spyOn(api,'textModels').mockResolvedValue([]);vi.spyOn(api,'createAgentJob').mockRejectedValue(new ApiError({status:401,code:'SESSION_REQUIRED',message:'需要有效的本机可信会话'}));mount(<AgentTeamPanel chapter={{id:'n:1',novel_id:'n',number:1} as any}/>);fireEvent.change(await screen.findByLabelText('任务说明'),{target:{value:'保留核对要求'}});fireEvent.click(screen.getByRole('button',{name:'启动任务'}));expect((await screen.findByRole('alert')).textContent).toContain('需要有效的本机可信会话');expect((screen.getByLabelText('任务说明') as HTMLTextAreaElement).value).toBe('保留核对要求');
});
it('never continues Agent start under another identity after an in-flight create loses its Host session',async()=>{
 bindLocalHostSession('original-host',receipt);vi.spyOn(api,'agents').mockResolvedValue({catalog_version:'1',agents:[{id:'reviewer',name:'审核 Agent',description:'Review',tools:[],prompt_role:'review',output_schema:'review',requires_approval:false}]});vi.spyOn(api,'textModels').mockResolvedValue([]);let finish!:(value:any)=>void;vi.spyOn(api,'createAgentJob').mockImplementation(()=>new Promise(resolve=>{finish=resolve}));const start=vi.spyOn(api,'startAgentJob');mount(<AgentTeamPanel chapter={{id:'n:1',novel_id:'n',number:1} as any}/>);fireEvent.click(await screen.findByRole('button',{name:'启动任务'}));await waitFor(()=>expect(typeof finish).toBe('function'));fireEvent.click(screen.getByRole('button',{name:'解绑本机可信会话'}));finish({id:'original-job',status:'QUEUED'});await waitFor(()=>expect(start).not.toHaveBeenCalled());expect(screen.queryByText('original-job')).toBeNull();
});
it.each(['actor-change','unbind'])('isolates protected cached history and detail immediately on %s',async change=>{
 bindLocalHostSession('actor-a-credential',{session_mode:'LOCAL_HOST',actor_id:'actor-a'});
 vi.spyOn(api,'agents').mockResolvedValue({catalog_version:'1',agents:[]});
 const jobs=vi.spyOn(api,'agentJobs').mockResolvedValue({items:[{id:'private-a-job',agent_name:'Private Actor A',instruction:'Actor A private instruction',status:'COMPLETED'}],total:1,has_more:false} as any);
 const detail=vi.spyOn(api,'agentJob').mockResolvedValue({id:'private-a-job',agent_name:'Actor A private detail',instruction:'Actor A private instruction',status:'COMPLETED',result:{}});
 mount(<><AgentJobHistory novelId="local-work"/><AgentJobDetail jobId="private-a-job"/></>);
 await screen.findByText('Private Actor A');await screen.findByText('Actor A private detail');
 jobs.mockImplementation(()=>new Promise(()=>{}));detail.mockImplementation(()=>new Promise(()=>{}));
 act(()=>{if(change==='unbind')clearLocalHostSession();else bindLocalHostSession('actor-b-credential',{session_mode:'LOCAL_HOST',actor_id:'actor-b'})});
 expect(screen.queryByText('Private Actor A')).toBeNull();expect(screen.queryByText('Actor A private detail')).toBeNull();
 expect(screen.queryByText(/Actor A private instruction/)).toBeNull();
 const keys=JSON.stringify(clients.at(-1)!.getQueryCache().getAll().map(query=>query.queryKey));expect(keys).not.toContain('actor-a-credential');expect(keys).not.toContain('actor-b-credential');
});
it('does not adopt a mismatched session-mode receipt',async()=>{
 vi.spyOn(api,'validateLocalHostSession').mockResolvedValue({session_mode:'TEAM',actor_id:'team-actor'} as any);mount(<LocalHostSessionPanel/>);fireEvent.change(screen.getByLabelText('本机访问凭证'),{target:{value:'candidate-host'}});fireEvent.click(screen.getByRole('button',{name:'验证并绑定本机会话'}));expect((await screen.findByRole('alert')).textContent).toContain('验证未通过');expect(useLocalHostSession.getState().token).toBe('');
});
