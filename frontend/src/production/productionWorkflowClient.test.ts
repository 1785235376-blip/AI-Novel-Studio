import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type CollaborationContext } from '../api';
import { studioTransport } from '../creative/studioClient';
import { createProductionWorkflowClient } from './productionWorkflowClient';
import { PRODUCTION_WORKFLOW_MODULES } from './productionWorkflowTypes';

/** Protocol fixtures only; they prove the client seam, not runtime acceptance. */
function projection(projectId = 'studio-project', scope: Record<string, unknown> = { mode: 'local', novel_id: projectId }) {
  return {
    schema_version: 1, contract: 'studio-production-workflow/1', project_id: projectId, scope,
    advisory_only: true, execution_authority: false, generated_at: '2026-10-14T09:41:59+00:00',
    project_start: {
      state: 'NOT_STARTED', entry_kind: 'NEUTRAL_STUDIO', incarnation: null, has_creative_documents: false,
      start_action: { method: 'POST', path: '/api/experimental/projects', requires_original_host_session: true },
    },
    creative_intent: { version: 0, preset: 'BLANK', values: [], editable: true, history_retained: true },
    modules: PRODUCTION_WORKFLOW_MODULES.map((id, index) => ({
      id, label: `模块${index}`, status: 'NOT_STARTED', document_count: 0, asset_count: 0, job_count: 0,
      blocked_reasons: [], owner: `Owner${index}`, next_action: null,
    })),
    asset_overview: { total: 0, by_kind: { image: 0, audio: 0, video: 0, text: 0, other: 0 }, private_pending_review: 0, reviewed: 0 },
    dashboard: { stages_total: 7, stages_started: 0, stages_reviewed: 0, open_reviews: 0, blocked_stages: [] },
  };
}
const intent = () => ({
  version: 1, preset: 'IMAGE', editable: true, history_retained: true,
  values: [{ intent_id: 'image_design', label: '图片设计', selected: true, custom: false }],
});
const draft = () => ({ expected_version: 0, values: [{ intent_id: 'image_design', label: '图片设计', selected: true }] });
const base = '/api/projects/studio-project/studio/production/workflow';
async function refusalOf(work: Promise<unknown>): Promise<ApiError> {
  try { await work; } catch (reason) { return reason as ApiError; }
  throw new Error('expected this call to be refused');
}

beforeEach(() => { vi.unstubAllGlobals(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('production workflow client seam', () => {
  it('exposes exactly one read and one intent replacement on the frozen routes', async () => {
    const json = vi.fn().mockResolvedValueOnce(projection()).mockResolvedValueOnce(intent());
    const client = createProductionWorkflowClient('studio-project', { json });
    const value = await client.read();
    expect(Object.keys(client)).toEqual(['read', 'updateIntent']);
    expect(json).toHaveBeenNthCalledWith(1, base, 'GET', undefined, undefined);
    expect(value.execution_authority).toBe(false);
    expect(value.modules.map(item => item.id)).toEqual([...PRODUCTION_WORKFLOW_MODULES]);
    const saved = await client.updateIntent({ ...draft(), preset: 'IMAGE' });
    expect(json).toHaveBeenNthCalledWith(2, `${base}/intent`, 'POST',
      { expected_version: 0, values: [{ intent_id: 'image_design', label: '图片设计', selected: true }], preset: 'IMAGE' }, undefined);
    expect(saved.version).toBe(1);
  });

  it('refuses an invalid local request before it reaches the original owner', async () => {
    const json = vi.fn().mockResolvedValue(intent());
    const client = createProductionWorkflowClient('studio-project', { json });
    const failures = [
      { expected_version: -1, values: [] },
      { expected_version: 0, values: [{ intent_id: 'custom', label: '', selected: true }] },
      { expected_version: 0, values: [{ intent_id: 'image_design', label: 'ok', selected: true, custom: true }] },
      { expected_version: 0, values: [], note: 'unknown to the owner' },
    ];
    for (const candidate of failures) {
      await expect(client.updateIntent(candidate)).rejects.toThrow(ApiError);
    }
    expect(json).not.toHaveBeenCalled();
  });

  it('maps the original owner error codes to bounded user text', async () => {
    const json = vi.fn();
    const client = createProductionWorkflowClient('studio-project', { json });
    const cases: [ApiError, string, string][] = [
      [new ApiError({ status: 409, code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', message: 'raw conflict' }), 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', '当前输入仍保留'],
      [new ApiError({ status: 422, code: 'PRODUCTION_WORKFLOW_INTENT_INVALID', message: 'raw invalid' }), 'PRODUCTION_WORKFLOW_INTENT_INVALID', '服务端未接受'],
      [new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_INVALID', message: 'raw denied' }), 'CREATIVE_AUTHORITY_INVALID', '无权修改创作意图'],
      [new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_CHANGED', message: 'raw changed' }), 'CREATIVE_AUTHORITY_CHANGED', '身份或项目范围已变化'],
      [new ApiError({ status: 507, code: 'CREATIVE_STORAGE_LOW_SPACE', message: 'raw space' }), 'CREATIVE_STORAGE_LOW_SPACE', '可用空间不足'],
      [new ApiError({ status: 507, code: 'CREATIVE_STORAGE_UNAVAILABLE', message: 'raw storage' }), 'CREATIVE_STORAGE_UNAVAILABLE', '存储状态'],
    ];
    for (const [failure, code, text] of cases) {
      json.mockRejectedValueOnce(failure);
      const caught = await refusalOf(client.updateIntent(draft()));
      expect(caught).toBeInstanceOf(ApiError);
      expect(caught.problem.code).toBe(code);
      expect(caught.problem.status).toBe(failure.status);
      expect(caught.message).toContain(text);
      expect(caught.message).not.toContain('raw');
    }
    json.mockRejectedValueOnce(new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }));
    expect((await refusalOf(client.updateIntent(draft()))).message).toBe('请求未完成。');
    json.mockRejectedValueOnce(new ApiError({ status: 507, code: 'SOMETHING_ELSE', message: 'raw capacity' }));
    expect((await refusalOf(client.updateIntent(draft()))).message).toContain('项目存储空间不足或不可用');
  });

  it('refuses a response that is not the frozen projection', async () => {
    const json = vi.fn().mockResolvedValue({ ...projection(), modules: projection().modules.slice(0, 6) });
    const client = createProductionWorkflowClient('studio-project', { json });
    const caught = await refusalOf(client.read());
    expect(caught.problem.code).toBe('PRODUCTION_WORKFLOW_RESPONSE_INVALID');
    json.mockResolvedValue({ ...intent(), editable: false });
    const rejected = await refusalOf(client.updateIntent(draft()));
    expect(rejected.problem.code).toBe('PRODUCTION_WORKFLOW_RESPONSE_INVALID');
  });

  it('captures the collaboration scope and rejects an unrelated captured project', async () => {
    const scope = { workspaceId: 'workspace', projectId: 'studio-project', storylineId: 'storyline', branchId: 'branch' };
    const json = vi.fn().mockResolvedValue(projection('studio-project',
      { mode: 'collaboration', novel_id: 'studio-project', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' }));
    const client = createProductionWorkflowClient('studio-project', { json }, scope);
    scope.branchId = 'changed-after-capture';
    expect((await client.read()).scope.branch_id).toBe('branch');
    const unrelatedTransport = vi.fn();
    const unrelated = createProductionWorkflowClient('studio-project', { json: unrelatedTransport }, { ...scope, projectId: 'other-project' });
    await expect(unrelated.read()).rejects.toThrow(ApiError);
    await expect(unrelated.updateIntent(draft())).rejects.toThrow(ApiError);
    expect(unrelatedTransport).not.toHaveBeenCalled();
    json.mockResolvedValue(projection());
    await expect(client.read()).rejects.toThrow(ApiError);
  });

  it('sends the original session, branch and idempotency headers through the Studio transport', async () => {
    const projectId = 'studio / project';
    const scope: CollaborationContext['scope'] = { workspaceId: 'w', projectId, storylineId: 's', branchId: 'branch' };
    const calls: [string, RequestInit][] = [];
    const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
      calls.push([url, init]);
      return { ok: true, status: 200, json: async () => url.endsWith('/intent') ? intent() : projection(projectId,
        { mode: 'collaboration', novel_id: projectId, workspace_id: 'w', storyline_id: 's', branch_id: 'branch' }) };
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = createProductionWorkflowClient(projectId, studioTransport({ sessionToken: 'session-original', scope }), scope);
    await client.read();
    await client.updateIntent({ ...draft(), preset: 'IMAGE' });
    expect(calls.map(([url]) => url)).toEqual([
      `/api/projects/${encodeURIComponent(projectId)}/studio/production/workflow`,
      `/api/projects/${encodeURIComponent(projectId)}/studio/production/workflow/intent`,
    ]);
    expect(calls[0][1].method).toBe('GET');
    expect(calls[1][1].method).toBe('POST');
    for (const [, init] of calls) {
      expect(init.headers).toMatchObject({ 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch', 'X-Request-ID': expect.any(String) });
    }
    expect((calls[0][1].headers as Record<string, string>)['Idempotency-Key']).toBeUndefined();
    expect((calls[1][1].headers as Record<string, string>)['Idempotency-Key']).toEqual(expect.any(String));
    expect(JSON.parse(String(calls[1][1].body))).toEqual({ expected_version: 0, values: [{ intent_id: 'image_design', label: '图片设计', selected: true }], preset: 'IMAGE' });
  });
});
