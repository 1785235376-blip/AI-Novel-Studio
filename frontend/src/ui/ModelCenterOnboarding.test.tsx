// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {api,setCollaborationContext} from '../api';
import {bindLocalHostSession,clearLocalHostSession,useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {ModelCenter} from './ModelCenter';
const snapshot=()=>({scan:null,registrations:[],settings:{scan_roots:[],runtimes:[]},hardware:{status:'NOT_VERIFIED',gpus:[]}});
const fetchMock=vi.fn();const owner={context:{sessionToken:''},projectId:'project'};
beforeEach(()=>{setCollaborationContext({sessionToken:''});useStudio.setState({sessionToken:'',novelId:'project',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:'',epoch:0});bindLocalHostSession('original-host',{session_mode:'LOCAL_HOST',actor_id:'host'});vi.spyOn(api,'modelCenterModels').mockResolvedValue({items:[]});vi.spyOn(api,'modelCenterRuntimes').mockResolvedValue({items:[]});vi.spyOn(api,'modelCenterPipelines').mockResolvedValue({items:[]});vi.spyOn(api,'modelCenterHealth').mockResolvedValue({status:'READY',mutation_authorization:{can_mutate:true,mutation_auth_mode:'TRUSTED_SESSION'}});fetchMock.mockReset();fetchMock.mockImplementation(async()=>new Response(JSON.stringify(snapshot())));vi.stubGlobal('fetch',fetchMock);});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();setCollaborationContext({sessionToken:''});useStudio.setState({sessionToken:'',novelId:'',actor:undefined,scope:undefined});useLocalHostSession.setState({token:'',actorId:'',epoch:0});});
describe('existing Model Center V2 onboarding integration',()=>{
 it('gates its discovery consumer without adding a direct scan trigger',async()=>{
  render(<ModelCenter onboarding={owner}/>);await screen.findByText('暂无模型');const start=screen.getByRole('button',{name:'预览 AI 检测范围'}) as HTMLButtonElement;expect(start.disabled).toBe(false);expect(screen.queryByRole('button',{name:'检测本机 AI 环境'})).toBeNull();expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('original-host');expect(fetchMock.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
 });
 it('remounts health and discovery ownership after an existing LOCAL_HOST epoch changes',async()=>{
  render(<ModelCenter onboarding={owner}/>);await screen.findByText('暂无模型');expect(api.modelCenterHealth).toHaveBeenCalledTimes(1);
  act(()=>{clearLocalHostSession();bindLocalHostSession('next-host',{session_mode:'LOCAL_HOST',actor_id:'next'});});await screen.findByText('暂无模型');expect(api.modelCenterHealth).toHaveBeenCalledTimes(2);expect(fetchMock.mock.calls.at(-1)![1].headers['X-Session-Token']).toBe('next-host');expect(fetchMock.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
 });
 it('propagates a revoked shared health permission while keeping manual use available',async()=>{
  render(<ModelCenter onboarding={owner}/>);await screen.findByText('暂无模型');vi.mocked(api.modelCenterHealth).mockResolvedValue({status:'READY',mutation_authorization:{can_mutate:false,mutation_auth_mode:'TRUSTED_SESSION_REQUIRED'}});fireEvent.click(screen.getByRole('button',{name:'刷新'}));await screen.findByText(/后端主机权限已撤回/);expect((screen.getByRole('button',{name:'预览 AI 检测范围'}) as HTMLButtonElement).disabled).toBe(true);expect(screen.getByText(/未配置模型或跳过检测时，仍可手动创作/)).toBeTruthy();
 });
});
