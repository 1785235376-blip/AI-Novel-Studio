import {expect,test,request as independentRequest,type APIRequestContext,type APIResponse,type Page} from '@playwright/test';
import type {LocalAiScanScope,LocalDiscoveryScan,AIEnvironmentReport} from '../../src/localAiDiscoveryApi';
const TOKEN='synthetic-m3-browser-existing-host';
const headers={'X-Session-Token':TOKEN};
const root='/api/model-center/local-ai';
const owned=new WeakMap<APIRequestContext,Set<string>>();
const pages=new WeakMap<APIRequestContext,Page>();
type FixtureReceipt={fixture:string;synthetic:boolean;probe_calls:{endpoint:string;path:string;method:string;body:null}[];hardware_calls:number;launch_attempts:number;blocked_attempts:string[];registrations:number;enabled_registrations:number;scan_id:string|null;scan_status:string|null;inference_status:'NOT_RUN';windows_acceptance:'NOT_RUN';model_weights_loaded:false};
async function body<T>(response:Pick<APIResponse,'ok'|'status'|'text'|'json'>):Promise<T>{expect(response.ok(),`HTTP ${response.status()}: ${await response.text()}`).toBe(true);return response.json() as Promise<T>;}
async function receipt(request:APIRequestContext){return body<FixtureReceipt>(await request.get('/api/__tests__/v2-discovery-fixture',{headers}));}
async function openModels(page:Page,request:APIRequestContext){
 await page.goto('/');await page.getByLabel('小说名称',{exact:true}).fill('M3 合成主机检测验收');
 const creating=page.waitForResponse(value=>new URL(value.url()).pathname==='/api/novels'&&value.request().method()==='POST');
 await page.getByRole('button',{name:'创建小说',exact:true}).click();const created=await creating;
 if(created.status()===201){const value=await created.json();if(typeof value.id==='string'&&value.id)owned.get(request)!.add(value.id);}
 expect(created.status()).toBe(201);expect(owned.get(request)!.size).toBe(1);
 // Exercise the product's existing credential validation UI and in-memory owner.
 // This is a fixed synthetic test identity already registered by the owned host.
 await page.getByRole('button',{name:'打开功能导航',exact:true}).click();
 const navigation=page.getByRole('navigation',{name:'功能面板导航',exact:true});
 const group=navigation.locator('.feature-group__header').filter({hasText:'协作'});
 if(await group.getAttribute('aria-expanded')!=='true')await group.click();
 await navigation.getByRole('button',{name:'Agent 团队',exact:true}).click();await page.keyboard.press('Escape');
 await page.getByLabel('本机访问凭证',{exact:true}).fill(TOKEN);
 const validation=page.waitForResponse(value=>new URL(value.url()).pathname==='/api/local-session');
 await page.getByRole('button',{name:'验证并绑定本机会话',exact:true}).click();
 expect(await body(await validation)).toEqual({session_mode:'LOCAL_HOST',actor_id:'synthetic-m3-browser-author'});
 await expect(page.getByText('已验证本机身份：synthetic-m3-browser-author',{exact:true})).toBeVisible();
 await page.getByRole('tablist',{name:'创作模块',exact:true}).getByRole('tab',{name:'主控',exact:true}).click();
 await page.getByRole('tablist',{name:'主控设置',exact:true}).getByRole('tab',{name:'模型中心',exact:true}).click();
}
test.beforeEach(async({request,page})=>{owned.set(request,new Set());pages.set(request,page);expect(await body(await request.get('/api/novels'))).toEqual([]);const state=await receipt(request);expect(state.fixture).toBe('ORIGINAL_FILE_HTTP_UI_WITH_SYNTHETIC_DISCOVERY_ADAPTER');expect(state.synthetic).toBe(true);expect(state.probe_calls).toEqual([]);expect(state.scan_id).toBeNull();});
test.afterEach(async({request},info)=>{
 const page=pages.get(request);
 try {if(page&&!page.isClosed())await page.close();}
 finally {
  // The fixture request context can already be disposed after a test timeout.
  // A separate bounded cleanup owner preserves the primary failure and deletes
  // only IDs returned by this test's successful create responses.
  const cleanupRequest=await independentRequest.newContext({baseURL:String(info.project.use.baseURL),timeout:10000});
  try {
   for(const id of owned.get(request)||[]){const removed=await cleanupRequest.delete(`/api/novels/${encodeURIComponent(id)}`);expect(removed.status()).toBe(204);}
   expect(await body(await cleanupRequest.get('/api/novels'))).toEqual([]);
  } finally {await cleanupRequest.dispose();}
 }
});

test('M3 enabled original File HTTP UI reviews synthetic host scope before explicit confirmation',async({page,request},info)=>{
 info.annotations.push({type:'verification',description:'Original File/HTTP/React and original discovery consent/worker; closed synthetic metadata adapter and synthetic hardware only. No app-route mocks, actual host inventory, real models, Windows acceptance, provider inference, paid API or downloads. Browser success requires hosted Chromium.'});
 const mutations:string[]=[],pageErrors:string[]=[];page.on('pageerror',value=>pageErrors.push(value.message));page.on('request',value=>{const path=new URL(value.url()).pathname;if(path.startsWith(root)&&!['GET','HEAD','OPTIONS'].includes(value.method()))mutations.push(`${value.method()} ${path}`);});
 await openModels(page,request);await expect(page.getByRole('button',{name:'预览 AI 检测范围',exact:true})).toBeEnabled();
 expect((await receipt(request)).hardware_calls).toBe(0);expect(mutations).toEqual([]);
 const firstRead=page.waitForResponse(value=>new URL(value.url()).pathname===`${root}/onboarding/scan-scope`);
 await page.getByRole('button',{name:'预览 AI 检测范围',exact:true}).click();const first=await body<LocalAiScanScope>(await firstRead);
 expect(first.include_common_model_dirs).toBe(false);expect(first.execution_scope).toBe('BACKEND_HOST');expect(first.roots).toEqual([]);expect(first.metadata_inspections).toEqual([]);
 const consent=page.getByRole('region',{name:'确认后端主机检测范围',exact:true});
 await expect(consent).toContainText('云端主机的结果不代表你的电脑');await expect(consent).toContainText('可能停用旧注册及路由');
 await expect(consent.getByRole('checkbox')).not.toBeChecked();await expect(consent.getByRole('button',{name:'确认此范围并检测',exact:true})).toBeEnabled();
 const unchanged=await receipt(request);expect(unchanged.probe_calls).toEqual([]);expect(unchanged.hardware_calls).toBe(0);expect(unchanged.scan_id).toBeNull();
 await consent.getByRole('button',{name:'取消预览',exact:true}).click();await expect(consent).toHaveCount(0);
 const secondRead=page.waitForResponse(value=>new URL(value.url()).pathname===`${root}/onboarding/scan-scope`);
 await page.getByRole('button',{name:'预览 AI 检测范围',exact:true}).click();const second=await body<LocalAiScanScope>(await secondRead);expect(second.scope_digest).not.toBe(first.scope_digest);
 const commonRead=page.waitForResponse(value=>new URL(value.url()).pathname===`${root}/onboarding/scan-scope`&&new URL(value.url()).searchParams.get('include_common_model_dirs')==='true');
 await consent.getByRole('checkbox').check();const withCommon=await body<LocalAiScanScope>(await commonRead);expect(withCommon.include_common_model_dirs).toBe(true);expect(withCommon.roots).toHaveLength(1);expect(withCommon.roots[0].source).toBe('COMMON');
 await expect(consent.locator('details')).not.toHaveAttribute('open','');expect((await receipt(request)).probe_calls).toEqual([]);
 const withoutCommon=page.waitForResponse(value=>new URL(value.url()).pathname===`${root}/onboarding/scan-scope`&&new URL(value.url()).searchParams.get('include_common_model_dirs')==='false');
 await consent.getByRole('checkbox').uncheck();const finalScope=await body<LocalAiScanScope>(await withoutCommon);expect(finalScope.roots).toEqual([]);
 const oldScan=await request.post(`${root}/scan`,{headers,data:{}});expect(oldScan.status()).toBe(409);expect(await oldScan.json()).toMatchObject({code:'LOCAL_AI_SCOPE_CONFIRMATION_REQUIRED'});expect((await receipt(request)).probe_calls).toEqual([]);
 for(const [width,height] of [[1366,768],[1440,900],[1920,1080]]){await page.setViewportSize({width,height});await page.evaluate(()=>document.fonts.ready);await consent.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:info.outputPath(`m3-scope-preview-${width}.png`)});}
 const confirmed=page.waitForResponse(value=>new URL(value.url()).pathname===`${root}/onboarding/scan`&&value.request().method()==='POST');
 const polled=page.waitForResponse(value=>new URL(value.url()).pathname.startsWith(`${root}/scan/`)&&value.request().method()==='GET');
 await consent.getByRole('button',{name:'确认此范围并检测',exact:true}).click();const confirmedResponse=await confirmed;expect(confirmedResponse.status()).toBe(202);expect(confirmedResponse.request().postDataJSON()).toEqual({scope_digest:finalScope.scope_digest,confirmed:true});
 const job=await confirmedResponse.json() as LocalDiscoveryScan&{consent:{scope_digest:string;execution_scope:string}};expect(job.consent.scope_digest).toBe(finalScope.scope_digest);expect(job.consent.execution_scope).toBe('BACKEND_HOST');expect((await polled).ok()).toBe(true);
 await expect(page.getByText('Synthetic consent fixture CPU',{exact:false})).toBeVisible();await expect(page.getByText('COMPLETED',{exact:true})).toBeVisible();
 const environment=await body<AIEnvironmentReport>(await request.get(`${root}/environment`,{headers}));expect(environment.status).toBe('COMPLETED');expect(environment.inference_status).toBe('NOT_RUN');expect(environment.windows_acceptance).toBe('NOT_RUN');expect(environment.roots).toEqual([]);expect(environment.model_files).toEqual([]);
 expect((await body<{settings:{include_common_model_dirs:boolean}}>(await request.get(root,{headers}))).settings.include_common_model_dirs).toBe(false);
 const terminal=await receipt(request);expect(terminal.hardware_calls).toBe(1);expect(terminal.probe_calls).toHaveLength(7);expect(terminal.registrations).toBe(0);expect(terminal.enabled_registrations).toBe(0);expect(terminal.launch_attempts).toBe(0);expect(terminal.blocked_attempts).toEqual([]);expect(terminal.model_weights_loaded).toBe(false);
 expect(mutations).toEqual([`POST ${root}/onboarding/scan`]);expect(pageErrors).toEqual([]);
 await page.screenshot({path:info.outputPath('m3-synthetic-confirmed-report.png'),fullPage:true});
 await info.attach('m3-original-file-http-ui-synthetic-adapter-receipt',{body:JSON.stringify({proof:'ORIGINAL_FILE_HTTP_UI_WITH_SYNTHETIC_DISCOVERY_ADAPTER',first_preview_digest:first.scope_digest,confirmed_preview_digest:finalScope.scope_digest,scan_id:job.id,environment,terminal,mutations,actual_host_inventory:'NOT_RUN',actual_model_inference:'NOT_RUN',windows_native:'NOT_RUN'},null,2),contentType:'application/json'});
});
for(const mode of ['default-off','acceptance-mode'] as const)test(`M3 ${mode} keeps original UI and rejects new onboarding routes without probes`,async({page,request},info)=>{
 await openModels(page,request);await expect(page.getByRole('button',{name:'检测本机 AI 环境',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'预览 AI 检测范围',exact:true})).toHaveCount(0);
 expect((await request.get(`${root}/onboarding/scan-scope?include_common_model_dirs=false`,{headers})).status()).toBe(404);
 expect((await request.post(`${root}/onboarding/scan`,{headers,data:{scope_digest:'a'.repeat(64),confirmed:true}})).status()).toBe(404);
 const state=await receipt(request);expect(state.probe_calls).toEqual([]);expect(state.hardware_calls).toBe(0);expect(state.scan_id).toBeNull();expect(state.registrations).toBe(0);expect(state.blocked_attempts).toEqual([]);
 await info.attach(`m3-${mode}-no-probes`,{body:JSON.stringify(state,null,2),contentType:'application/json'});
});
