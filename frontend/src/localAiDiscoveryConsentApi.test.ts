// @vitest-environment jsdom
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {setCollaborationContext} from './api';
import {localAiDiscoveryClient,type LocalAiScanScope} from './localAiDiscoveryApi';
import {useLocalHostSession} from './localHostSession';
import {isPackagedDesktopHost} from './packagedHost';
vi.mock('./packagedHost',()=>({isPackagedDesktopHost:vi.fn(()=>false)}));
const digest='a'.repeat(64);
const scope=():LocalAiScanScope=>({schema_version:1,execution_scope:'BACKEND_HOST',scope_digest:digest,include_common_model_dirs:false,services:[],roots:[],metadata_inspections:[],hardware_categories:['CPU'],limits:{max_services:20},inference_status:'NOT_RUN',requires_confirmation:true,side_effects:{launches:false,loads_weights:false,registers:false,enables:false,cloud_calls:false,persists_settings:false,may_disable_stale_registrations:true,persists_registration_safety_updates:true}});
const fetchMock=vi.fn();const reply=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
beforeEach(()=>{useLocalHostSession.setState({token:'host-at-capture',actorId:'host',epoch:1});fetchMock.mockReset();fetchMock.mockImplementation(async()=>reply(scope()));vi.stubGlobal('fetch',fetchMock);vi.mocked(isPackagedDesktopHost).mockReturnValue(false);});
afterEach(()=>{vi.unstubAllGlobals();setCollaborationContext({sessionToken:''});useLocalHostSession.setState({token:'',actorId:'',epoch:0});});
describe('captured V2 Local AI transport',()=>{
 it('captures local-host identity once for the entire existing discovery lifecycle',async()=>{
  const client=localAiDiscoveryClient({sessionToken:''});useLocalHostSession.setState({token:'later-host'});setCollaborationContext({sessionToken:'later-team'});
  await client.previewScope(false);await client.confirmScan(digest);await client.scanStatus('scan/1');await client.cancelScan('scan/1');await client.validate('candidate/1');await client.register('candidate/1');await client.enable('registered/1');
  expect(fetchMock.mock.calls.every(([,init])=>init.headers['X-Session-Token']==='host-at-capture')).toBe(true);expect(fetchMock.mock.calls[0][0]).toBe('/api/model-center/local-ai/onboarding/scan-scope?include_common_model_dirs=false');
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({scope_digest:digest,confirmed:true});expect(fetchMock.mock.calls[1][1].headers['Idempotency-Key']).toBeTruthy();expect(fetchMock.mock.calls[2][0]).toContain('/scan/scan%2F1');expect(fetchMock.mock.calls.some(([url])=>url==='/api/model-center/local-ai/scan')).toBe(false);
 });
 it('never borrows fallback for an explicitly empty credential, actor, collaboration scope or packaged host',async()=>{
  await localAiDiscoveryClient({sessionToken:'',localHostToken:''}).snapshot();await localAiDiscoveryClient({sessionToken:'',actor:{id:'actor',displayName:'Actor',workspaceId:'w'}}).snapshot();await localAiDiscoveryClient({sessionToken:'',scope:{workspaceId:'w',projectId:'p',storylineId:'s',branchId:'b'}}).snapshot();vi.mocked(isPackagedDesktopHost).mockReturnValue(true);await localAiDiscoveryClient({sessionToken:''}).snapshot();expect(fetchMock.mock.calls.every(([,init])=>!init.headers['X-Session-Token'])).toBe(true);
 });
 it('preserves the original explicit session and forwards AbortSignal',async()=>{
  const context={sessionToken:'original'},controller=new AbortController(),client=localAiDiscoveryClient(context);context.sessionToken='changed';await client.previewScope(false,controller.signal);expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('original');expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal);
 });
 it('prevents dispatch and rejects adoption after the owner is invalidated',async()=>{
  let current=false;const client=localAiDiscoveryClient({sessionToken:'original'},()=>current);await expect(client.confirmScan(digest)).rejects.toMatchObject({name:'AbortError'});expect(fetchMock).not.toHaveBeenCalled();current=true;let resolve!:(value:Response)=>void;fetchMock.mockImplementationOnce(()=>new Promise<Response>(done=>{resolve=done;}));const pending=client.previewScope(false);current=false;resolve(reply(scope()));await expect(pending).rejects.toMatchObject({name:'AbortError'});
 });
 it.each([
  ['schema',()=>({...scope(),schema_version:2})],['host',()=>({...scope(),execution_scope:'USER_COMPUTER'})],['digest',()=>({...scope(),scope_digest:'invalid'})],['opt-in',()=>({...scope(),include_common_model_dirs:true})],['common root',()=>({...scope(),roots:[{path:'/private/common',source:'COMMON'}]})],['inference',()=>({...scope(),inference_status:'VERIFIED'})],['confirmation',()=>({...scope(),requires_confirmation:false})],['side effects',()=>({...scope(),side_effects:{...scope().side_effects,loads_weights:true}})],['safety persistence',()=>({...scope(),side_effects:{...scope().side_effects,persists_registration_safety_updates:false}})],['unknown side effect',()=>({...scope(),side_effects:{...scope().side_effects,erases_files:true}})],['services',()=>({...scope(),services:[{}]})],['metadata',()=>({...scope(),metadata_inspections:[{kind:'GGUF',path:'/models/a.gguf',max_entries:1,max_bytes:-1}]})],['hardware',()=>({...scope(),hardware_categories:[42]})],['limits',()=>({...scope(),limits:{max_services:-1}})],
 ] as const)('rejects an unreviewable %s response before consent',async(_name,value)=>{fetchMock.mockImplementationOnce(async()=>reply(value()));await expect(localAiDiscoveryClient({sessionToken:'host'}).previewScope(false)).rejects.toMatchObject({problem:{code:'LOCAL_AI_SCOPE_INVALID'}});expect(fetchMock).toHaveBeenCalledTimes(1);});
 it('uses safe error codes without exposing returned private details',async()=>{fetchMock.mockImplementationOnce(async()=>reply({detail:{code:'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE',message:'/private/secret-path'}},403));await expect(localAiDiscoveryClient({sessionToken:'host'}).snapshot()).rejects.toMatchObject({problem:{code:'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE',message:'本地 AI 操作未完成。'}});});
});

it('captures the original collaboration branch without borrowing a later scope',async()=>{
 const context={sessionToken:'original',scope:{workspaceId:'w',projectId:'p',storylineId:'s',branchId:'original-branch'}};
 const client=localAiDiscoveryClient(context);context.scope.branchId='changed';await client.environment();expect(fetchMock.mock.calls[0][1].headers['X-Branch-Id']).toBe('original-branch');
});
