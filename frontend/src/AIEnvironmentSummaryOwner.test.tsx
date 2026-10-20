// @vitest-environment jsdom
import {StrictMode} from 'react';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {AIEnvironmentSummary} from './AIEnvironmentSummary';
import {setCollaborationContext} from './api';
import {bindLocalHostSession,clearLocalHostSession,useLocalHostSession} from './localHostSession';
import {useStudio} from './store';
import type {AIEnvironmentReport} from './localAiDiscoveryApi';
const report=(status:AIEnvironmentReport['status']='COMPLETED',cpu='Original CPU'):AIEnvironmentReport=>({schema_version:2,execution_scope:'BACKEND_HOST',inference_status:'NOT_RUN',windows_acceptance:'NOT_RUN',scan_id:'scan',status,started_at:null,finished_at:null,hardware:{platform:'Synthetic',architecture:'x86_64',cpu,logical_cpu_count:4,ram_bytes:4096,gpus:[],status:'NOT_VERIFIED',notes:[],cuda:{status:'NOT_RUN',source:'NOT_RUN',inference_verified:false},directml:{status:'NOT_RUN',source:'NOT_RUN',inference_verified:false}},services:[],model_files:[],roots:[],errors:[],notes:[],limits:{scan_budget_seconds:45,request_timeout_seconds:2,max_services:20,max_models_per_service:512,max_response_bytes:4194304,max_roots:32,max_entries:5000,max_files:2000,max_depth:3,max_metadata_bytes:262144}});
const reply=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
const deferred=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done;});return {promise,resolve};};
const fetchMock=vi.fn();const owner={context:{sessionToken:''},projectId:'project-1'};
beforeEach(()=>{setCollaborationContext({sessionToken:''});useStudio.setState({sessionToken:'',novelId:'project-1',scope:undefined,actor:undefined});useLocalHostSession.setState({token:'',actorId:'',epoch:0});bindLocalHostSession('original-local-host',{session_mode:'LOCAL_HOST',actor_id:'original'});fetchMock.mockReset();fetchMock.mockImplementation(async()=>reply(report()));vi.stubGlobal('fetch',fetchMock);});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.useRealTimers();setCollaborationContext({sessionToken:''});useStudio.setState({sessionToken:'',novelId:'',scope:undefined,actor:undefined});useLocalHostSession.setState({token:'',actorId:'',epoch:0});});
describe('V2 environment report original owner',()=>{
 it('reads the host report using the existing captured LOCAL_HOST token and never scans',async()=>{
  const open=vi.fn();render(<AIEnvironmentSummary enabled onboarding={owner} onOpenModels={open}/>);await screen.findByText('Original CPU');
  expect(fetchMock.mock.calls[0][0]).toBe('/api/model-center/local-ai/environment');expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('original-local-host');expect(fetchMock.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'打开模型中心'}));expect(open).toHaveBeenCalledOnce();expect(screen.getByText(/云端结果不代表你的电脑/)).toBeTruthy();
 });
 it('clears observations and disables retries after host authority is revoked',async()=>{
  render(<AIEnvironmentSummary enabled onboarding={owner} onOpenModels={vi.fn()}/>);await screen.findByText('Original CPU');fetchMock.mockImplementationOnce(async()=>reply({detail:{code:'SESSION_REQUIRED',message:'private path'}},401));fireEvent.click(screen.getByRole('button',{name:'重新读取'}));await screen.findByRole('alert');
  expect(screen.queryByText('Original CPU')).toBeNull();expect(screen.queryByText('private path')).toBeNull();const retry=screen.getByRole('button',{name:'重新读取'}) as HTMLButtonElement;expect(retry.disabled).toBe(true);fireEvent.click(retry);expect(fetchMock).toHaveBeenCalledTimes(2);
 });
 it('explains unavailable backend host authority without reporting measurements',async()=>{
  fetchMock.mockImplementationOnce(async()=>reply({detail:{code:'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE'}},403));render(<AIEnvironmentSummary enabled onboarding={owner} onOpenModels={vi.fn()}/>);await screen.findByText(/此后端未提供本地 AI 主机授权/);expect(screen.queryByText('Original CPU')).toBeNull();expect((screen.getByRole('button',{name:'重新读取'}) as HTMLButtonElement).disabled).toBe(true);
 });
 it('ignores a late read after same-token clear/rebind and adopts only the new epoch response',async()=>{
  const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);render(<AIEnvironmentSummary enabled onboarding={owner} onOpenModels={vi.fn()}/>);const signal=fetchMock.mock.calls[0][1].signal;
  fetchMock.mockImplementation(async()=>reply(report('COMPLETED','Current CPU')));act(()=>{clearLocalHostSession();bindLocalHostSession('original-local-host',{session_mode:'LOCAL_HOST',actor_id:'original'});});await screen.findByText('Current CPU');expect(signal.aborted).toBe(true);
  await act(async()=>{old.resolve(reply(report()));});expect(screen.queryByText('Original CPU')).toBeNull();expect(fetchMock.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
 });
 it('uses the new captured session only after an owner change and discards the previous response',async()=>{
  const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);const view=render(<AIEnvironmentSummary enabled onboarding={owner} onOpenModels={vi.fn()}/>);
  const next={context:{sessionToken:'next-session'},projectId:'project-2'};setCollaborationContext(next.context);fetchMock.mockImplementation(async()=>reply(report('NOT_SCANNED')));view.rerender(<AIEnvironmentSummary enabled onboarding={next} onOpenModels={vi.fn()}/>);await screen.findByText('尚未检测');
  await act(async()=>{old.resolve(reply(report()));});expect(screen.queryByText('Original CPU')).toBeNull();expect(fetchMock.mock.calls.at(-1)![1].headers['X-Session-Token']).toBe('next-session');
 });
 it('clears results on a project switch away and back without fetching with the old owner',async()=>{
  render(<AIEnvironmentSummary enabled onboarding={owner} onOpenModels={vi.fn()}/>);await screen.findByText('Original CPU');act(()=>{useStudio.setState({novelId:'away'});useStudio.setState({novelId:'project-1'});});await screen.findByText(/项目或会话已改变/);expect(screen.queryByText('Original CPU')).toBeNull();expect(fetchMock).toHaveBeenCalledTimes(1);
 });
 it('does no fetch when disabled and aborts an in-flight read on unmount',async()=>{
  const view=render(<AIEnvironmentSummary enabled={false} onboarding={owner} onOpenModels={vi.fn()}/>);expect(fetchMock).not.toHaveBeenCalled();const pending=deferred<Response>();fetchMock.mockImplementationOnce(()=>pending.promise);view.rerender(<AIEnvironmentSummary enabled onboarding={owner} onOpenModels={vi.fn()}/>);const signal=fetchMock.mock.calls[0][1].signal;view.unmount();expect(signal.aborted).toBe(true);await act(async()=>{pending.resolve(reply(report()));});expect(fetchMock).toHaveBeenCalledTimes(1);
 });
 it('works under StrictMode without triggering a scan',async()=>{
  render(<StrictMode><AIEnvironmentSummary enabled onboarding={owner} onOpenModels={vi.fn()}/></StrictMode>);await screen.findByText('Original CPU');expect(fetchMock.mock.calls.every(([url,init])=>url==='/api/model-center/local-ai/environment'&&init.method==='GET')).toBe(true);
 });
});
