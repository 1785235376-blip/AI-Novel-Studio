// @vitest-environment jsdom
import {StrictMode} from 'react';
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext, type CollaborationContext} from '../api';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {localAiDiscoveryApi, type LocalAiScanScope} from '../localAiDiscoveryApi';
import {LocalAiDiscovery} from './LocalAiDiscovery';
const digest='a'.repeat(64), newerDigest='b'.repeat(64);
const preview=(common=false, scopeDigest=digest):LocalAiScanScope=>({schema_version:1,execution_scope:'BACKEND_HOST',scope_digest:scopeDigest,include_common_model_dirs:common,
 services:[{id:'ollama',name:'Ollama',type:'OLLAMA',endpoint:'http://127.0.0.1:11434',management:'EXTERNAL',probe_paths:['/api/tags']}],
 roots:[{path:'/private/configured-models',source:'CONFIGURED'},...(common?[{path:'/private/common-models',source:'COMMON' as const}]:[])],
 metadata_inspections:[{kind:'CONFIGURED_GGUF',path:'/private/configured.gguf',max_entries:1,max_bytes:262144}],hardware_categories:['CPU','RAM','GPU','CUDA','DIRECTML'],
 limits:{scan_budget_seconds:45,max_services:20,max_depth:3,max_metadata_bytes:262144},inference_status:'NOT_RUN',requires_confirmation:true,
 side_effects:{launches:false,loads_weights:false,registers:false,enables:false,cloud_calls:false,persists_settings:false,may_disable_stale_registrations:true,persists_registration_safety_updates:true}});
const snapshot=()=>({scan:null,registrations:[],settings:{scan_roots:[],runtimes:[],include_common_model_dirs:true},hardware:{status:'NOT_VERIFIED',gpus:[]}});
const scan=(status='COMPLETED')=>({id:'scan-1',status,runtimes:[],candidates:[],errors:[]});
const reply=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
const deferred=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done;});return {promise,resolve};};
const fetchMock=vi.fn();
const calls=(path:string)=>fetchMock.mock.calls.filter(([url])=>String(url).includes(path));
const confirms=()=>fetchMock.mock.calls.filter(([url])=>String(url).endsWith('/onboarding/scan'));
const button=(name:string)=>screen.getByRole('button',{name}) as HTMLButtonElement;
const click=(name:string)=>fireEvent.click(button(name));
const context:CollaborationContext={sessionToken:'original-host'};
async function mount(ctx=context,canMutate=true){const view=render(<LocalAiDiscovery canMutate={canMutate} onboarding={{context:ctx,projectId:'project-1'}}/>);await screen.findByText('尚未开始扫描');return view;}
async function openPreview(){click('预览 AI 检测范围');await screen.findByText('将检查的服务（1）');}
beforeEach(()=>{useLocalHostSession.setState({token:'',actorId:'',epoch:0});useStudio.setState({novelId:'project-1',sessionToken:'original-host',scope:undefined,actor:undefined});setCollaborationContext(context);fetchMock.mockReset();fetchMock.mockImplementation(async(url:string)=>url.includes('/onboarding/scan-scope')?reply(preview(url.endsWith('true'),url.endsWith('true')?newerDigest:digest)):url.endsWith('/onboarding/scan')?reply(scan()):reply(snapshot()));vi.stubGlobal('fetch',fetchMock);});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();vi.useRealTimers();setCollaborationContext({sessionToken:''});useLocalHostSession.setState({token:'',actorId:'',epoch:0});useStudio.setState({novelId:'',sessionToken:'',scope:undefined,actor:undefined});});

describe('V2 Local AI scan consent',()=>{
 it('never scans on mount; previews actual backend scope then confirms once without registration or inference',async()=>{
  const legacy=vi.spyOn(localAiDiscoveryApi,'scan');await mount();expect(calls('/onboarding/')).toHaveLength(0);expect(screen.getByText(/未配置或未发现可用模型时/)).toBeTruthy();await openPreview();
  expect(calls('/onboarding/scan-scope')[0][0]).toBe('/api/model-center/local-ai/onboarding/scan-scope?include_common_model_dirs=false');expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
  expect(screen.getByText(/http:\/\/127.0.0.1:11434/)).toBeTruthy();expect(screen.getByText('CPU · RAM · GPU · CUDA · DIRECTML')).toBeTruthy();expect(screen.getByText(/可能停用旧注册及路由/)).toBeTruthy();
  const detail=screen.getByText('高级：查看具体路径与文件检查').parentElement as HTMLDetailsElement;expect(detail.open).toBe(false);expect(detail.textContent).toContain('/private/configured.gguf');expect(confirms()).toHaveLength(0);
  click('确认此范围并检测');await screen.findByText('尚未发现模型');expect(JSON.parse(confirms()[0][1].body)).toEqual({scope_digest:digest,confirmed:true});expect(confirms()[0][1].headers['X-Session-Token']).toBe('original-host');
  expect(legacy).not.toHaveBeenCalled();expect(fetchMock.mock.calls.some(([url])=>/\/validate|\/register|\/enable|\/generate|\/start/.test(url))).toBe(false);
  click('重新预览检测范围');await screen.findByText('将检查的服务（1）');expect(calls('/onboarding/scan-scope')).toHaveLength(2);expect(confirms()).toHaveLength(1);
 });
 it('requires new scope after common-directory opt-in without persisting settings',async()=>{
  await mount();await openPreview();const pending=deferred<Response>();fetchMock.mockImplementationOnce(()=>pending.promise);fireEvent.click(screen.getByRole('checkbox'));expect(button('确认此范围并检测').disabled).toBe(true);expect(calls('/onboarding/scan-scope')[1][0]).toContain('include_common_model_dirs=true');
  await act(async()=>{pending.resolve(reply(preview(true,newerDigest)));});expect(button('确认此范围并检测').disabled).toBe(false);click('确认此范围并检测');await screen.findByText('尚未发现模型');expect(JSON.parse(confirms()[0][1].body).scope_digest).toBe(newerDigest);expect(fetchMock.mock.calls.some(([,init])=>init.method==='PUT')).toBe(false);
 });
 it('drops late preview after Cancel and reopening; no old digest is submitted',async()=>{
  await mount();const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);click('预览 AI 检测范围');click('取消预览');expect(calls('/onboarding/scan-scope')[0][1].signal.aborted).toBe(true);fetchMock.mockImplementationOnce(async()=>reply(preview(false,newerDigest)));await openPreview();await act(async()=>{old.resolve(reply(preview()));});click('确认此范围并检测');await screen.findByText('尚未发现模型');expect(JSON.parse(confirms()[0][1].body).scope_digest).toBe(newerDigest);
 });
 it('ignores late opt-in scope after changing it back',async()=>{
  await mount();await openPreview();const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByRole('checkbox'));await screen.findByText('将检查的服务（1）');await act(async()=>{old.resolve(reply(preview(true,newerDigest)));});expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);click('确认此范围并检测');await screen.findByText('尚未发现模型');expect(JSON.parse(confirms()[0][1].body).scope_digest).toBe(digest);
 });
 it.each(['STALE','EXPIRED','CONSUMED','CONFLICT','REQUIRED'])('fails closed on scope %s without automatic retry',async code=>{
  await mount();await openPreview();fetchMock.mockImplementationOnce(async()=>reply({detail:{code:`LOCAL_AI_SCOPE_${code}`,message:'/private/raw-error'}},409));click('确认此范围并检测');await screen.findByText(/请重新预览并确认/);expect(screen.queryByRole('button',{name:'确认此范围并检测'})).toBeNull();expect(screen.queryByText('/private/raw-error')).toBeNull();expect(confirms()).toHaveLength(1);expect(calls('/onboarding/scan-scope')).toHaveLength(1);expect(button('预览 AI 检测范围').disabled).toBe(false);
 });
 it('guards repeated preview and confirmation clicks synchronously',async()=>{
  await mount();const pending=deferred<Response>();fetchMock.mockImplementationOnce(()=>pending.promise);const start=button('预览 AI 检测范围');act(()=>{start.click();start.click();});expect(calls('/onboarding/scan-scope')).toHaveLength(1);await act(async()=>{pending.resolve(reply(preview()));});const confirmed=deferred<Response>();fetchMock.mockImplementationOnce(()=>confirmed.promise);const confirm=button('确认此范围并检测');act(()=>{confirm.click();confirm.click();});expect(confirms()).toHaveLength(1);await act(async()=>{confirmed.resolve(reply(scan()));});
 });
 it('invalidates consent when advanced configuration opens',async()=>{
  await mount();await openPreview();click('高级：配置扫描目录');expect(screen.queryByRole('button',{name:'确认此范围并检测'})).toBeNull();expect(screen.getByRole('textbox',{name:'模型目录（每行一个完整路径）'})).toBeTruthy();expect(confirms()).toHaveLength(0);
 });
 it('does not reopen a collapsed panel after a late preview',async()=>{
  await mount();const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);click('预览 AI 检测范围');click('跳过 / 收起');await act(async()=>{old.resolve(reply(preview()));});expect(screen.queryByText('确认本次检测范围')).toBeNull();click('展开本地 AI');expect(screen.queryByText('确认本次检测范围')).toBeNull();expect(calls('/onboarding/scan-scope')).toHaveLength(1);
 });
 it('clears private scope and ignores pending confirmation after permission revoke',async()=>{
  const view=await mount();await openPreview();const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);click('确认此范围并检测');view.rerender(<LocalAiDiscovery canMutate={false} onboarding={{context,projectId:'project-1'}}/>);await screen.findByText(/后端主机权限已撤回/);await act(async()=>{old.resolve(reply(scan()));});expect(screen.queryByText('COMPLETED')).toBeNull();expect(screen.queryByText('/private/configured.gguf')).toBeNull();expect(button('预览 AI 检测范围').disabled).toBe(true);
 });
 it('does not scan without mutation authorization',async()=>{await mount(context,false);expect(button('预览 AI 检测范围').disabled).toBe(true);click('预览 AI 检测范围');expect(calls('/onboarding/')).toHaveLength(0);});
 it('explains host-authority refusal without claiming local hardware or requiring paths',async()=>{
  fetchMock.mockImplementation(async()=>reply({detail:{code:'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE',message:'private host data'}},403));render(<LocalAiDiscovery canMutate onboarding={{context,projectId:'project-1'}}/>);await screen.findByText(/此后端未提供本地 AI 主机授权/);expect(screen.queryByText('private host data')).toBeNull();expect(screen.queryByText('正在读取本地 AI 状态…')).toBeNull();expect(button('预览 AI 检测范围').disabled).toBe(true);expect(calls('/onboarding/')).toHaveLength(0);
 });
 it('rejects older session previews when the owner changes',async()=>{
  const view=await mount();const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);click('预览 AI 检测范围');const next={sessionToken:'next-host'};setCollaborationContext(next);view.rerender(<LocalAiDiscovery canMutate onboarding={{context:next,projectId:'project-2'}}/>);await screen.findByText('尚未开始扫描');await act(async()=>{old.resolve(reply(preview()));});expect(screen.queryByText('确认本次检测范围')).toBeNull();await openPreview();expect(calls('/onboarding/scan-scope').at(-1)![1].headers['X-Session-Token']).toBe('next-host');
 });
 it('invalidates same-token LOCAL_HOST rebind by epoch and keeps original request credentials',async()=>{
  setCollaborationContext({sessionToken:''});useStudio.setState({sessionToken:''});bindLocalHostSession('local-host',{session_mode:'LOCAL_HOST',actor_id:'host'});await mount({sessionToken:''});const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);click('预览 AI 检测范围');expect(calls('/onboarding/scan-scope')[0][1].headers['X-Session-Token']).toBe('local-host');act(()=>{clearLocalHostSession();bindLocalHostSession('local-host',{session_mode:'LOCAL_HOST',actor_id:'host'});});await screen.findByText('尚未开始扫描');await act(async()=>{old.resolve(reply(preview()));});expect(screen.queryByText('确认本次检测范围')).toBeNull();expect(calls('/onboarding/scan-scope')).toHaveLength(1);
 });
 it('does not revive consent after a project switch away and back',async()=>{
  await mount();const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);click('预览 AI 检测范围');act(()=>{useStudio.setState({novelId:'another-project'});useStudio.setState({novelId:'project-1'});});await act(async()=>{old.resolve(reply(preview()));});expect(screen.queryByRole('button',{name:'确认此范围并检测'})).toBeNull();expect(screen.getByText(/项目或会话已改变/)).toBeTruthy();expect(confirms()).toHaveLength(0);
 });
 it('works under the existing StrictMode mount cycle',async()=>{render(<StrictMode><LocalAiDiscovery canMutate onboarding={{context,projectId:'project-1'}}/></StrictMode>);await screen.findByText('尚未开始扫描');await openPreview();expect(button('确认此范围并检测').disabled).toBe(false);expect(calls('/onboarding/scan-scope')).toHaveLength(1);});
 it('aborts pending scope on unmount and never scans',async()=>{const view=await mount();const old=deferred<Response>();fetchMock.mockImplementationOnce(()=>old.promise);click('预览 AI 检测范围');const signal=calls('/onboarding/scan-scope')[0][1].signal;view.unmount();expect(signal.aborted).toBe(true);await act(async()=>{old.resolve(reply(preview()));});expect(calls('/onboarding/scan-scope')).toHaveLength(1);expect(confirms()).toHaveLength(0);});
});

it('invalidates consent after parent runtime configuration changes',async()=>{
 const view=await mount();await openPreview();view.rerender(<LocalAiDiscovery canMutate scopeRevision={1} onboarding={{context,projectId:'project-1'}}/>);
 expect(screen.queryByRole('button',{name:'确认此范围并检测'})).toBeNull();expect(confirms()).toHaveLength(0);
});
it('discloses all registered-model safety inspections without truncating the backend scope',async()=>{
 await mount();const value=preview();value.metadata_inspections=Array.from({length:2048},(_,index)=>({kind:'REGISTERED_GGUF_HEADER',path:`/private/registered-${index}.gguf`,max_entries:1,max_bytes:262144}));value.limits.max_registration_metadata_inspections=2048;
 fetchMock.mockImplementationOnce(async()=>reply(value));await openPreview();const detail=screen.getByText('高级：查看具体路径与文件检查').parentElement as HTMLDetailsElement;
 expect(detail.open).toBe(false);expect(detail.textContent).toContain('已注册 GGUF 安全复查：/private/registered-2047.gguf');expect(detail.querySelectorAll('li')).toHaveLength(2049);expect(confirms()).toHaveLength(0);
});
it('keeps current cancellation and new scan ownership when an old V2 status read resolves late',async()=>{
 await mount();await openPreview();vi.useFakeTimers();const old=deferred<Response>();
 fetchMock.mockImplementation(async(url:string)=>url.endsWith('/onboarding/scan')?reply(scan('RUNNING')):url.endsWith('/scan/scan-1/cancel')?reply(scan('CANCELLED')):url.endsWith('/scan/scan-1')?old.promise:url.includes('/onboarding/scan-scope')?reply(preview()):reply(snapshot()));
 await act(async()=>{click('确认此范围并检测');});await act(async()=>{await vi.advanceTimersByTimeAsync(1000);});
 const poll=calls('/scan/scan-1')[0];await act(async()=>{click('取消扫描');});expect(poll[1].signal.aborted).toBe(true);expect(screen.getByText('扫描已取消，保留已发现结果。')).toBeTruthy();
 await act(async()=>{click('重新预览检测范围');});expect(confirms()).toHaveLength(1);
 await act(async()=>{old.resolve(reply(scan('RUNNING')));});expect(screen.getByText('CANCELLED')).toBeTruthy();expect(screen.queryByText('RUNNING')).toBeNull();expect(button('确认此范围并检测').disabled).toBe(false);
});
