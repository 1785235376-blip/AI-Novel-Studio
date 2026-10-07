// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {api,setCollaborationContext} from './api';
import {bindLocalHostSession,clearLocalHostSession,useLocalHostSession} from './localHostSession';
const receipt={session_mode:'LOCAL_HOST',actor_id:'verified-author'} as const;
beforeEach(()=>{localStorage.clear();clearLocalHostSession();setCollaborationContext({sessionToken:''});vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[]}))))});
afterEach(()=>{clearLocalHostSession();delete window.__AI_NOVEL_PACKAGED_HOST__;vi.unstubAllGlobals()});
it('keeps the explicit Host credential in memory and leaves team identity and current project unchanged',async()=>{
 const {useStudio}=await import('./store');useStudio.getState().setCollaboration('');useStudio.getState().setNovel('local-manuscript');
 const set=vi.spyOn(Storage.prototype,'setItem');bindLocalHostSession('synthetic-local',receipt);
 expect(set).not.toHaveBeenCalled();expect(useStudio.getState().sessionToken).toBe('');expect(useStudio.getState().novelId).toBe('local-manuscript');
 await api.novels();expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).get('X-Session-Token')).toBe('synthetic-local');set.mockRestore();
});
it('does not authorize anonymous local calls or calls after an explicit unlink',async()=>{
 await api.novels();expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).has('X-Session-Token')).toBe(false);
 bindLocalHostSession('synthetic-local',receipt);clearLocalHostSession();await api.novels();expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).has('X-Session-Token')).toBe(false);
});
it('never borrows the local credential for team scopes, actor metadata or packaged hosts',async()=>{
 bindLocalHostSession('synthetic-local',receipt);
 for(const context of [{sessionToken:'',scope:{workspaceId:'w',projectId:'p',storylineId:'s',branchId:'b'}},{sessionToken:'',actor:{id:'team',displayName:'Team',workspaceId:'w'}}]){
  await api.chapter('p:1',context);expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).has('X-Session-Token')).toBe(false);
 }
 await api.adminWorkspaces();expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).has('X-Session-Token')).toBe(false);
 window.__AI_NOVEL_PACKAGED_HOST__=true;await api.novels();expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).has('X-Session-Token')).toBe(false);
});
it('clears the local credential on team connection and uses only the original team token',async()=>{
 bindLocalHostSession('synthetic-local',receipt);setCollaborationContext({sessionToken:'synthetic-team'});
 expect(useLocalHostSession.getState().token).toBe('');await api.novels();expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).get('X-Session-Token')).toBe('synthetic-team');
});
it('keeps a captured Agent request on its original verified token and honors explicit empty identity',async()=>{
 bindLocalHostSession('new-identity',receipt);await api.startAgentJob('owner-job',{sessionToken:'',localHostToken:'original-identity'});
 expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).get('X-Session-Token')).toBe('original-identity');
 await api.startAgentJob('anonymous-job',{sessionToken:'',localHostToken:''});expect(new Headers(vi.mocked(fetch).mock.calls.at(-1)![1]?.headers).has('X-Session-Token')).toBe(false);
});
it('validates via the original request header without placing a credential in URL or body',async()=>{
 await api.validateLocalHostSession('candidate-token');expect(vi.mocked(fetch).mock.calls[0][0]).toBe('/api/local-session');expect(vi.mocked(fetch).mock.calls[0][1]?.body).toBeUndefined();expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).get('X-Session-Token')).toBe('candidate-token');
});
