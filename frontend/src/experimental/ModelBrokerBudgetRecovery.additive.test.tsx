// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {experimentalClient} from './api';
import type {BrokerBudget} from './modelBrokerClient';
import {ModelBrokerPanel} from './ModelBrokerPanel';
const context={sessionToken:'synthetic-budget-session',scope:{workspaceId:'w',projectId:'budget-project',storylineId:'s',branchId:'b'}};
const initial:BrokerBudget={version:5,limit_microusd:null,max_inflight:1,require_known_estimate:true,committed_microusd:0,inflight:0,unknown_count:0,overrun_count:0};
const limitLabel='累计预占上限（µUSD；留空不设金额上限）',knownLabel='要求已配置费用估计；严格金额上限始终要求估计',loadLabel='载入已读取的项目预算（替换本地编辑）';
const field=(label:string)=>screen.getByLabelText(label) as HTMLInputElement;
const click=(name:string)=>fireEvent.click(screen.getByRole('button',{name}));
const retained=(name:string)=>{const button=screen.getByRole('button',{name});return (button as any)[Object.keys(button).find(key=>key.startsWith('__reactProps$'))!].onClick as ()=>void;};
function setup(conflict=false){
 let budget=structuredClone(initial),fail=conflict;
 const requests:{url:string;method:string;body?:Record<string,any>}[]=[];
 const fetch=vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method||'GET',body=init?.body?JSON.parse(String(init.body)):undefined;requests.push({url,method,body});
  if(url.endsWith('/model-broker/status'))return new Response(JSON.stringify({budget,candidates:[],prices:[],author_execution_available:false}));
  if(url.endsWith('/model-broker/history'))return new Response(JSON.stringify({decisions:[],ledger:[]}));
  if(url.endsWith('/model-broker/budget')){
   if(fail){fail=false;budget={...budget,version:6,limit_microusd:200,max_inflight:3,require_known_estimate:false};}
   if(body.expected_version!==budget.version)return new Response(JSON.stringify({detail:{code:'EXPERIMENTAL_VERSION_CONFLICT'}}),{status:409});
   budget={...budget,...body,version:budget.version+1};return new Response(JSON.stringify(budget));
  }
  throw new Error(`Unexpected request ${method} ${url}`);
 });
 vi.stubGlobal('fetch',fetch);
 const view=render(<ModelBrokerPanel client={experimentalClient('budget-project',context)} novelId="budget-project" context={context}/>);
 return {view,requests,replace:(value:BrokerBudget)=>{budget=structuredClone(value);},puts:()=>requests.filter(row=>row.method==='PUT')};
}
async function ready(){await screen.findByLabelText(limitLabel);await waitFor(()=>expect((screen.getByRole('button',{name:'保存版本化项目预算'}) as HTMLButtonElement).disabled).toBe(false));}
async function refresh(version:number){click('重新读取当前注册状态');await screen.findByRole('columnheader',{name:`已读取预算 v${version}`});}
function edit(limit='73'){fireEvent.change(field(limitLabel),{target:{value:limit}});fireEvent.change(field('最多并发任务'),{target:{value:'2'}});fireEvent.click(field(knownLabel));}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

it('compares an edit with the re-read budget after CAS conflict, then explicitly loads and saves the current revision',async()=>{
 const f=setup(true);await ready();edit('123');click('保存版本化项目预算');await screen.findByRole('alert');expect(field(limitLabel).value).toBe('123');
 await refresh(6);const compare=screen.getByRole('region',{name:'项目预算版本对照'});expect(within(compare).getByText('123 µUSD')).toBeTruthy();expect(within(compare).getByText('200 µUSD')).toBeTruthy();
 click(loadLabel);expect(field(limitLabel).value).toBe('200');expect(field('最多并发任务').value).toBe('3');expect(field(knownLabel).checked).toBe(false);expect(f.puts()).toHaveLength(1);
 fireEvent.change(field(limitLabel),{target:{value:'250'}});click('保存版本化项目预算');await waitFor(()=>expect(f.puts()).toHaveLength(2));expect(f.puts()[1].body).toMatchObject({expected_version:6,limit_microusd:250,max_inflight:3,require_known_estimate:false});
 expect(f.requests.every(row=>/model-broker\/(status|history|budget)$/.test(row.url))).toBe(true);
});

it('keeps the local edit when explicitly adopting the re-read revision instead of loading server values',async()=>{
 const f=setup();await ready();edit();f.replace({...initial,version:6,limit_microusd:90,max_inflight:3});await refresh(6);
 expect(field(limitLabel).value).toBe('73');click('已核对最新预算 v6，保留输入继续编辑');expect(field(limitLabel).value).toBe('73');expect(field('最多并发任务').value).toBe('2');expect(field(knownLabel).checked).toBe(false);expect(f.puts()).toHaveLength(0);
 click('保存版本化项目预算');await waitFor(()=>expect(f.puts()).toHaveLength(1));expect(f.puts()[0].body).toMatchObject({expected_version:6,limit_microusd:73,max_inflight:2,require_known_estimate:false});
});

it('restores null as an unset limit rather than zero without issuing a read or write',async()=>{
 const f=setup();await ready();edit('0');const before=f.requests.length;click(loadLabel);expect(field(limitLabel).value).toBe('');expect(field('最多并发任务').value).toBe('1');expect(field(knownLabel).checked).toBe(true);expect(f.requests).toHaveLength(before);expect(f.puts()).toHaveLength(0);
});

it('retires a retained Load when a newer snapshot and local edit replace its budget draft',async()=>{
 const f=setup();await ready();edit();const oldLoad=retained(loadLabel);f.replace({...initial,version:6,limit_microusd:200,max_inflight:3});await refresh(6);click(loadLabel);fireEvent.change(field(limitLabel),{target:{value:'88'}});act(()=>oldLoad());expect(field(limitLabel).value).toBe('88');click('保存版本化项目预算');await waitFor(()=>expect(f.puts()).toHaveLength(1));expect(f.puts()[0].body).toMatchObject({expected_version:6,limit_microusd:88});
});

it('retires a retained version acknowledgement after a later budget revision is adopted',async()=>{
 const f=setup();await ready();edit();f.replace({...initial,version:6,limit_microusd:200});await refresh(6);const oldAck=retained('已核对最新预算 v6，保留输入继续编辑');f.replace({...initial,version:7,limit_microusd:300});await refresh(7);click('已核对最新预算 v7，保留输入继续编辑');act(()=>oldAck());click('保存版本化项目预算');await waitFor(()=>expect(f.puts()).toHaveLength(1));expect(f.puts()[0].body?.expected_version).toBe(7);
});

it('does not send a retained budget Save after the editor unmounts',async()=>{
 const f=setup();await ready();edit();const oldSave=retained('保存版本化项目预算');f.view.unmount();await act(async()=>oldSave());expect(f.puts()).toHaveLength(0);
});
