import {afterEach,expect,it,vi} from 'vitest';
import {api,setCollaborationContext} from './api';
afterEach(()=>{vi.unstubAllGlobals();setCollaborationContext({sessionToken:''})});
it('explicit source policy request context overrides a later global session and branch',async()=>{
 const fetcher=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>({})});vi.stubGlobal('fetch',fetcher);
 setCollaborationContext({sessionToken:'new-session',scope:{workspaceId:'other',projectId:'other',storylineId:'other',branchId:'new'}});
 const captured={sessionToken:'captured-session',scope:{workspaceId:'w',projectId:'n',storylineId:'s',branchId:'old'}};
 await api.sourcePrivacy('n','n:1',captured);
 expect(fetcher.mock.calls[0][1].headers['X-Session-Token']).toBe('captured-session');
 expect(fetcher.mock.calls[0][1].headers['X-Branch-Id']).toBe('old');
 expect(fetcher.mock.calls[0][0]).not.toContain('session');
});
