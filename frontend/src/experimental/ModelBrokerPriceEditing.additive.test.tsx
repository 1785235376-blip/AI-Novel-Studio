// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import type {Chapter} from '../api';
import {experimentalClient} from './api';
import {ModelBrokerPanel} from './ModelBrokerPanel';

const context={sessionToken:'synthetic-config-session',scope:{workspaceId:'w',projectId:'price-project',storylineId:'s',branchId:'b'}};
const local={route_id:'local-fixture',provider_id:'local-fixture',model_id:'account-local-model',display_name:'本地配置夹具',capability:'TEXT',available:true,cloud:false,synthetic:false,fingerprint:'a'.repeat(64),reasons:[],context_window:null,verification:'ADAPTER_CONTRACT_ONLY',identity:{}};
const cloud={...local,route_id:'cloud-fixture',provider_id:'cloud-fixture',display_name:'云端配置夹具',cloud:true,fingerprint:'b'.repeat(64)};
const price={id:'price-local',version:7,route_id:local.route_id,route_fingerprint:local.fingerprint,currency:'USD',reserve_microusd:0,input_per_million_microusd:0,output_per_million_microusd:null,source:'用户核对的本地估计',as_of:'2026-10-01T00:00:00+00:00',expires_at:'2099-07-08T15:16:17.123456+05:30',applicability:'per_request'};
const cloudPrice={...price,id:'price-cloud',version:3,route_id:cloud.route_id,route_fingerprint:cloud.fingerprint,reserve_microusd:90,input_per_million_microusd:null,output_per_million_microusd:300,source:'用户提供的云端报价'};
const budget={version:1,limit_microusd:100,max_inflight:1,require_known_estimate:true,committed_microusd:0,inflight:0,unknown_count:0,overrun_count:0};
function setup(prices=[price,cloudPrice],conflict=false){
 let currentPrices=prices;
 const fetch=vi.fn(async(url:string,init?:RequestInit)=>{
  if(url.endsWith('/model-broker/status'))return new Response(JSON.stringify({candidates:[local,cloud],prices:currentPrices,budget,author_execution_available:false}));
  if(url.endsWith('/model-broker/history'))return new Response(JSON.stringify({decisions:[],ledger:[]}));
  if(url.endsWith('/model-broker/price'))return new Response(JSON.stringify(conflict?{detail:{code:'EXPERIMENTAL_VERSION_CONFLICT'}}:{...price,version:8}),{status:conflict?409:200});
  throw new Error(`Unexpected request ${init?.method} ${url}`);
 });
 vi.stubGlobal('fetch',fetch);
 render(<ModelBrokerPanel client={experimentalClient('price-project',context)} novelId="price-project" context={context} chapter={{id:'chapter',version:1,title:'配置夹具'} as Chapter}/>);
 return {fetch,replace:(value:typeof prices)=>{currentPrices=value;}};
}
const value=(label:string)=>(screen.getByLabelText(label) as HTMLInputElement).value;
const estimate='每请求保守预占（µUSD）',source='价格依据（来源或报价说明）',expiry='价格有效至',input='输入费率（每百万 Token 的 µUSD；可空）',output='输出费率（每百万 Token 的 µUSD；可空）';
async function choose(id=local.route_id){await screen.findByLabelText('价格适用路线');fireEvent.change(screen.getByLabelText('价格适用路线'),{target:{value:id}});}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

it('explicitly loads existing price fields without a request, then saves the loaded revision and exact source expiry through the original price API',async()=>{
 const {fetch}=setup();await choose();
 fireEvent.click(screen.getByRole('button',{name:'载入此路线已有价格依据'}));
 expect(value(estimate)).toBe('0');expect(value(source)).toBe(price.source);expect(value(input)).toBe('0');expect(value(output)).toBe('');
 expect(value(expiry)).not.toBe('');expect(fetch.mock.calls.every(([,init])=>init?.method==='GET')).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'保存路线价格依据'}));
 await waitFor(()=>expect(fetch.mock.calls.some(([url])=>url.endsWith('/model-broker/price'))).toBe(true));
 const sent=JSON.parse(String(fetch.mock.calls.find(([url])=>url.endsWith('/model-broker/price'))![1]?.body));
 expect(sent).toMatchObject({route_id:local.route_id,route_fingerprint:local.fingerprint,expected_version:7,reserve_microusd:0,input_per_million_microusd:0,output_per_million_microusd:null,source:price.source,expires_at:price.expires_at});
 expect(fetch.mock.calls.every(([url])=>!/preview|generate|credential/.test(url))).toBe(true);
});

it('clears the prior route draft when switching local/cloud and loads only the explicitly chosen route without changing privacy',async()=>{
 const {fetch}=setup();await choose();
 for(const label of [estimate,source,expiry,input,output])fireEvent.change(screen.getByLabelText(label),{target:{value:label===source?'上一条路线草稿':label===expiry?'2099-01-01T12:00':'25'}});
 await choose(cloud.route_id);
 for(const label of [estimate,source,expiry,input,output])expect(value(label)).toBe('');
 expect((screen.getByRole('button',{name:'保存路线价格依据'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'载入此路线已有价格依据'}));
 expect(value(estimate)).toBe('90');expect(value(source)).toBe(cloudPrice.source);expect(value(input)).toBe('');expect(value(output)).toBe('300');
 expect(value('调度策略')).toBe('LOCAL_FIRST');expect(value('创作隐私模式')).toBe('LOCAL_ONLY');
 expect(fetch.mock.calls.every(([,init])=>init?.method==='GET')).toBe(true);
});

it('keeps edits on status refresh and adopts a newer price revision only on explicit load',async()=>{
 const {fetch,replace}=setup();await choose();fireEvent.change(screen.getByLabelText(source),{target:{value:'保留我的草稿'}});
 replace([{...price,version:8,source:'新版本来源'},cloudPrice]);fireEvent.click(screen.getByRole('button',{name:'重新读取当前注册状态'}));
 await waitFor(()=>expect(fetch.mock.calls.filter(([url])=>url.endsWith('/model-broker/status'))).toHaveLength(2));
 await waitFor(()=>expect((screen.getByRole('button',{name:'载入此路线已有价格依据'}) as HTMLButtonElement).disabled).toBe(false));
 expect(value(source)).toBe('保留我的草稿');fireEvent.click(screen.getByRole('button',{name:'载入此路线已有价格依据'}));expect(value(source)).toBe('新版本来源');
 fireEvent.click(screen.getByRole('button',{name:'保存路线价格依据'}));await waitFor(()=>expect(fetch.mock.calls.some(([url])=>url.endsWith('/model-broker/price'))).toBe(true));
 expect(JSON.parse(String(fetch.mock.calls.find(([url])=>url.endsWith('/model-broker/price'))![1]?.body)).expected_version).toBe(8);
});

it('does not load an old-fingerprint estimate as current-route configuration',async()=>{
 setup([{...price,route_fingerprint:'c'.repeat(64)}]);await choose();
 expect((screen.getByRole('button',{name:'载入此路线已有价格依据'}) as HTMLButtonElement).disabled).toBe(true);
 expect(value(source)).toBe('');expect(value(estimate)).toBe('');
 expect(screen.getByText(/已有价格记录与当前路线指纹不一致/)).toBeTruthy();
});

it('preserves the loaded local edit on a price revision conflict',async()=>{
 setup([price,cloudPrice],true);await choose();fireEvent.click(screen.getByRole('button',{name:'载入此路线已有价格依据'}));
 fireEvent.change(screen.getByLabelText(source),{target:{value:'我的更新依据'}});fireEvent.click(screen.getByRole('button',{name:'保存路线价格依据'}));
 await screen.findByRole('alert');expect(value(source)).toBe('我的更新依据');expect(value(estimate)).toBe('0');
});
