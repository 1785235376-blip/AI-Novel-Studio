import { afterEach, expect, it, vi } from 'vitest';
import { creativeClient } from './client';
import captured from './directorModelActionWire.testFixture.json';
afterEach(()=>vi.unstubAllGlobals());

it('lazily reuses original captured credentials and scope without construction-time requests',async()=>{
  const project=captured.preview.project_id;
  const context={sessionToken:'original-token',scope:{workspaceId:'w',projectId:project,storylineId:'s',branchId:'original-branch'}};
  const wire={...captured.preview,scope:{mode:'collaboration',novel_id:project,workspace_id:'w',storyline_id:'s',branch_id:'original-branch'}};
  const fetch=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>wire});vi.stubGlobal('fetch',fetch);
  const client=creativeClient(project,context);
  context.sessionToken='later-token';context.scope.branchId='later-branch';
  const model=client.independentDirector();expect(fetch).not.toHaveBeenCalled();
  const p=captured.preview.receipt,signal=new AbortController().signal;
  const receipt=await model.readPreview(p.proposal_id,{id:p.source_document_id,version:p.source_version,digest:p.source_digest},signal);
  expect(receipt).toEqual(p);expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1]).toMatchObject({method:'GET',signal,headers:{'X-Session-Token':'original-token','X-Branch-Id':'original-branch'}});
  expect(fetch.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
});

it('does not alter legacy client construction when an unrelated scope is temporarily present',()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  const client=creativeClient('p',{sessionToken:'token',scope:{workspaceId:'w',projectId:'different',storylineId:'s',branchId:'b'}});
  expect(typeof client.list).toBe('function');expect(fetch).not.toHaveBeenCalled();
  expect(()=>client.independentDirector()).toThrow();expect(fetch).not.toHaveBeenCalled();
});
