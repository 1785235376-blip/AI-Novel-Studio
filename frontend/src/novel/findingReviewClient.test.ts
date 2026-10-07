import {afterEach,expect,it,vi} from 'vitest';
import {findingReviewClient} from './findingReviewClient';
import {pendingCanonReviewClient} from './pendingCanonReviewClient';
afterEach(()=>vi.unstubAllGlobals());
const context={sessionToken:'trusted-synthetic-session',scope:{workspaceId:'w',projectId:'p',storylineId:'s',branchId:'b'}};
it('captures branch finding authority but sends only project credentials for Canon',async()=>{
 const fetcher=vi.fn().mockResolvedValue({ok:true,json:async()=>({items:[]})});vi.stubGlobal('fetch',fetcher);
 const finding=findingReviewClient('project/encoded',context);const canon=pendingCanonReviewClient('project/encoded',context);
 await finding.list('narrative');await canon.list();
 expect(fetcher.mock.calls[0][0]).toBe('/api/projects/project%2Fencoded/narrative/review-findings');
 expect(fetcher.mock.calls[0][1].headers).toEqual({'Content-Type':'application/json','X-Session-Token':'trusted-synthetic-session','X-Branch-Id':'b'});
 expect(fetcher.mock.calls[1][1].headers).toEqual({'Content-Type':'application/json','X-Session-Token':'trusted-synthetic-session'});
});
it('keeps raw server/source text out of permission error messages',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:403,json:async()=>({detail:{code:'FORBIDDEN',message:'SYNTHETIC_PRIVATE_SERVER_TEXT'}})}));
 await expect(findingReviewClient('p',context).list('continuity')).rejects.toMatchObject({problem:{status:403,message:'当前身份无权读取或审阅此范围。'}});
 await expect(pendingCanonReviewClient('p',context).list()).rejects.toMatchObject({problem:{status:403,message:'需要项目级 Canon 审阅权限；分支角色不能操作主线 Canon。'}});
});
