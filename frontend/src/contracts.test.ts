import './i18n'; // [HERMIA-FE-20261025 P1-ERR] 友好错误文案由 i18n 注册（应用启动时总会加载）
import {afterEach,describe,expect,it,vi} from 'vitest';import {api,ApiError,setCollaborationContext} from './api';import {conflicts,drafts} from './drafts';
afterEach(()=>{vi.unstubAllGlobals();if(typeof localStorage!=='undefined')localStorage.clear();setCollaborationContext({sessionToken:''});drafts.remove('c');conflicts.remove('c')});
describe('collaboration frontend contracts',()=>{
 it('uses nested scope routes, item envelopes, and trusted headers',async()=>{const fetch=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>({items:[]})});vi.stubGlobal('fetch',fetch);const scope={workspaceId:'w',projectId:'p',storylineId:'s',branchId:'b'};setCollaborationContext({sessionToken:'opaque',scope});expect(await api.members(scope)).toEqual([]);expect(fetch.mock.calls[0][0]).toBe('/api/collaboration/workspaces/w/projects/p/storylines/s/branches/b/members');expect(fetch.mock.calls[0][1].headers).toMatchObject({'X-Session-Token':'opaque','X-Branch-Id':'b'})});
 it('persists local drafts and conflicts without server overwrite',()=>{drafts.save({chapterId:'c',content:'local',baseVersion:2,updatedAt:'now'});const local=drafts.load('c')!;conflicts.save({chapterId:'c',local,server:{content:'remote',version:3},detectedAt:'now'});expect(conflicts.load('c')?.local.content).toBe('local');expect(conflicts.load('c')?.server.content).toBe('remote')});
 it('namespaces identical chapter ids by collaboration scope',()=>{drafts.save({chapterId:'c',content:'branch-a',baseVersion:1,updatedAt:'now'},'scope-a');drafts.save({chapterId:'c',content:'branch-b',baseVersion:2,updatedAt:'now'},'scope-b');expect(drafts.load('c','scope-a')?.content).toBe('branch-a');expect(drafts.load('c','scope-b')?.content).toBe('branch-b')});
 it('keeps the File-mode legacy history endpoint',async()=>{const fetch=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>[]});vi.stubGlobal('fetch',fetch);expect(await api.legacyHistory('novel:1')).toEqual([]);expect(fetch.mock.calls[0][0]).toBe('/api/chapters/novel%3A1/history')});
 it.each([
  // [HERMIA-FE-20261025 VERA-620963bf 规格变更] 白名单裁定：FORBIDDEN / VALIDATION_ERROR 不在 LITERAL_MESSAGE_CODES（后端不带字面文案），message 改为按状态码友好文案；
  // 白名单 code 的服务端文案仍原样保留（第三行）。status/code 断言不变。
  [403,'application/json',JSON.stringify({detail:{code:'FORBIDDEN',message:'没有权限'}}),'FORBIDDEN','没有权限执行此操作'],
  [422,'application/json',JSON.stringify({detail:{code:'VALIDATION_ERROR',message:'输入无效'}}),'VALIDATION_ERROR','提交的内容未通过校验，请检查后重试'],
  [409,'application/json',JSON.stringify({detail:{code:'PLANNING_VERSION_CONFLICT',message:'任务已更新，请刷新后重试。'}}),'PLANNING_VERSION_CONFLICT','任务已更新，请刷新后重试。'],
  // [HERMIA-FE-20261025 P1-ERR] 规格变更：非 JSON 正文不再作为 message 原样展示，改为按状态码的友好文案；原文移至 problem.raw_text（仅专业模式技术详情），见 apiErrorView.test.ts
  [500,'text/plain','服务暂时不可用','HTTP_ERROR','服务暂时出错，请稍后重试'],
 ])('parses an error response body once and preserves status/code/message',async(status,contentType,body,code,message)=>{const response=new Response(body,{status,headers:{'content-type':contentType}});const text=vi.spyOn(response,'text');vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response));await expect(api.adminWorkspaces()).rejects.toMatchObject({problem:{status,code,message}} satisfies Partial<ApiError>);expect(text).toHaveBeenCalledTimes(1);expect(response.bodyUsed).toBe(true)});
 it('keeps a non-JSON error body only as raw_text, never as message ([HERMIA-FE-20261025 P1-ERR])',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('服务暂时不可用',{status:500,headers:{'content-type':'text/plain'}})));await expect(api.adminWorkspaces()).rejects.toMatchObject({problem:{status:500,code:'HTTP_ERROR',message:'服务暂时出错，请稍后重试',message_source:'fallback',raw_text:'服务暂时不可用'}})});
});
