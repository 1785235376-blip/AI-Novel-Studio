import {afterEach,expect,it,vi} from 'vitest';
import {planningApi,setCollaborationContext} from './api';
afterEach(()=>{vi.unstubAllGlobals();setCollaborationContext({sessionToken:''})});
it('uses the existing planning owner and captured authorization for explicit candidate adoption',async()=>{
 const fetcher=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>({run:{version:8},applied:{character_ids:['hero']}})});vi.stubGlobal('fetch',fetcher);
 setCollaborationContext({sessionToken:'later-session',scope:{workspaceId:'other',projectId:'other',storylineId:'other',branchId:'other'}});
 const result=await planningApi.apply('作品/1','run/a','candidate:b',7,{sessionToken:'captured-session'});
 expect(fetcher).toHaveBeenCalledTimes(1);
 const [url,request]=fetcher.mock.calls[0];
 expect(url).toBe('/api/novels/%E4%BD%9C%E5%93%81%2F1/planning-runs/run%2Fa/candidates/candidate%3Ab/apply');
 expect(request.method).toBe('POST');expect(JSON.parse(request.body)).toEqual({expected_version:7});
 expect(request.headers['X-Session-Token']).toBe('captured-session');expect(request.headers['X-Branch-Id']).toBeUndefined();
 expect(result.applied.character_ids).toEqual(['hero']);
});
