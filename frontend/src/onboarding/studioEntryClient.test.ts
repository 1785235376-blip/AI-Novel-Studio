import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type CollaborationContext } from '../api';
import { studioTransport } from '../creative/studioClient';
import { createStudioEntryClient, studioIntentFromPreferences, studioPreferencesFromIntent } from './studioEntryClient';
import { STUDIO_INTENT_IDS } from './studioEntryTypes';

/** Protocol fixtures only; they prove the client seam, not runtime acceptance. */
const preferences = (patch: Record<string, unknown> = {}) => ({
  version: 1, intents: ['NOVEL_WRITING', 'CUSTOM'], preset: 'TEXT', custom_intent: '我的长篇', ...patch,
});
const created = { id: 'novel-new', title: '新项目', studio_ready: true, requires_scope_selection: false };
async function refusalOf(work: Promise<unknown>): Promise<ApiError> {
  try { await work; } catch (reason) { return reason as ApiError; }
  throw new Error('expected this call to be refused');
}

beforeEach(() => { vi.unstubAllGlobals(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('studio entry client seam', () => {
  it('exposes exactly one list, one blank creation and one intent read/replacement on the frozen routes', async () => {
    const json = vi.fn()
      .mockResolvedValueOnce([{ id: 'novel-1', title: '第一个项目' }])
      .mockResolvedValueOnce(created)
      .mockResolvedValueOnce(preferences())
      .mockResolvedValueOnce(preferences({ version: 2, intents: ['IMAGE_DESIGN'], custom_intent: '' }));
    const client = createStudioEntryClient({ json });
    expect(Object.keys(client)).toEqual(['listProjects', 'createBlankProject', 'readIntent', 'saveIntent']);

    const rows = await client.listProjects();
    expect(json).toHaveBeenNthCalledWith(1, '/api/novels', 'GET', undefined, undefined);
    expect(rows).toEqual([{ id: 'novel-1', title: '第一个项目', updated_at: null, entry_kind: null, genre: null, status: null }]);

    const project = await client.createBlankProject({ title: '新项目' });
    expect(json).toHaveBeenNthCalledWith(2, '/api/experimental/projects', 'POST', { title: '新项目' }, undefined);
    expect(project).toEqual(created);

    const intent = await client.readIntent('novel-1');
    expect(json).toHaveBeenNthCalledWith(3, '/api/projects/novel-1/studio/preferences', 'GET', undefined, undefined);
    expect(intent.preset).toBe('TEXT');
    expect(intent.values.map(item => item.intent_id)).toEqual([...STUDIO_INTENT_IDS]);
    expect(intent.values.find(item => item.intent_id === 'novel_writing')?.selected).toBe(true);
    expect(intent.values.find(item => item.intent_id === 'custom')).toMatchObject({ label: '我的长篇', selected: true, custom: true });

    const saved = await client.saveIntent('novel-1', {
      expected_version: 1, preset: 'IMAGE', values: [{ intent_id: 'image_design', label: '图片设计', selected: true }],
    });
    // The owner's own literal vocabulary, no `custom` marker and no `note` field.
    expect(json).toHaveBeenNthCalledWith(4, '/api/projects/novel-1/studio/preferences', 'PUT', {
      expected_version: 1, intents: ['IMAGE_DESIGN'], custom_intent: '',
    }, undefined);
    expect(saved.version).toBe(2);
  });

  it('encodes a project id into the owner route and refuses an unrelated captured scope without calling the owner', async () => {
    const json = vi.fn().mockResolvedValue(preferences());
    const encoded = createStudioEntryClient({ json });
    await encoded.readIntent('novel.id_1');
    expect(json).toHaveBeenCalledWith('/api/projects/novel.id_1/studio/preferences', 'GET', undefined, undefined);

    const unrelated = vi.fn();
    const foreign = createStudioEntryClient({ json: unrelated }, 'other-project');
    for (const work of [foreign.readIntent('novel-1'), foreign.saveIntent('novel-1', { expected_version: 0, values: [] })]) {
      const failure = await refusalOf(work);
      expect(failure.problem.code).toBe('STUDIO_ENTRY_SCOPE_MISMATCH');
    }
    expect(unrelated).not.toHaveBeenCalled();
  });

  it('maps the original owner error codes to bounded user text', async () => {
    const json = vi.fn();
    const client = createStudioEntryClient({ json });
    const draft = { expected_version: 0, values: [{ intent_id: 'image_design', label: '图片设计', selected: true }] };
    const cases: [ApiError, string, string][] = [
      [new ApiError({ status: 409, code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', message: 'raw conflict' }), 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', '当前输入仍保留'],
      [new ApiError({ status: 422, code: 'PRODUCTION_WORKFLOW_INTENT_INVALID', message: 'raw invalid' }), 'PRODUCTION_WORKFLOW_INTENT_INVALID', '服务端未接受'],
      [new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_INVALID', message: 'raw denied' }), 'CREATIVE_AUTHORITY_INVALID', '无权修改创作意图'],
      [new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_CHANGED', message: 'raw changed' }), 'CREATIVE_AUTHORITY_CHANGED', '身份或项目范围已变化'],
      [new ApiError({ status: 404, code: 'STUDIO_REQUEST_FAILED', message: 'raw missing' }), 'STUDIO_ENTRY_PROJECT_MISSING', '不会自动创建一个替代项目'],
    ];
    for (const [failure, code, text] of cases) {
      json.mockRejectedValueOnce(failure);
      const caught = await refusalOf(client.saveIntent('novel-1', draft));
      expect(caught.problem.code).toBe(code);
      expect(caught.problem.status).toBe(failure.status);
      expect(caught.message).toContain(text);
      expect(caught.message).not.toContain('raw');
    }
    json.mockRejectedValueOnce(new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }));
    expect((await refusalOf(client.saveIntent('novel-1', draft))).message).toBe('请求未完成。');
  });

  it('reports a failed reopen of a saved id as invalid instead of a replacement', async () => {
    const json = vi.fn().mockRejectedValue(new ApiError({ status: 404, code: 'STUDIO_REQUEST_FAILED', message: '记录不可用。' }));
    const client = createStudioEntryClient({ json });
    const read = await refusalOf(client.readIntent('deleted-project'));
    expect(read.problem.code).toBe('STUDIO_ENTRY_PROJECT_MISSING');
    expect(read.message).toContain('已不可用');
    expect(json).toHaveBeenCalledTimes(1);
  });

  it('refuses a response that is not the saved preference projection', async () => {
    const json = vi.fn().mockResolvedValueOnce({ ...preferences(), extra: true });
    const client = createStudioEntryClient({ json });
    expect((await refusalOf(client.readIntent('novel-1'))).problem.code).toBe('STUDIO_ENTRY_RESPONSE_INVALID');
    json.mockResolvedValue({ id: 'novel-1', title: 'x' });
    expect((await refusalOf(client.listProjects())).problem.code).toBe('STUDIO_ENTRY_RESPONSE_INVALID');
    json.mockResolvedValue({ ...created, studio_ready: 'yes' });
    expect((await refusalOf(client.createBlankProject({ title: 'x' }))).problem.code).toBe('STUDIO_ENTRY_RESPONSE_INVALID');
  });

  it('gives a saved id to the owner untouched and rejects an impossible local blank request', async () => {
    const json = vi.fn().mockResolvedValue(created);
    const client = createStudioEntryClient({ json });
    await client.createBlankProject({ title: '  带空白的名称  ', id: 'novel-slug-1' });
    expect(json).toHaveBeenCalledWith('/api/experimental/projects', 'POST', { title: '带空白的名称', id: 'novel-slug-1' }, undefined);
    for (const bad of ['', '   ', 'x'.repeat(201), 'bad\u0000title']) {
      expect((await refusalOf(client.createBlankProject({ title: bad }))).problem.code).toBe('STUDIO_ENTRY_INTENT_LOCAL_INVALID');
    }
    expect((await refusalOf(client.createBlankProject({ title: 'ok', id: '../escape' }))).problem.code).toBe('STUDIO_ENTRY_INTENT_LOCAL_INVALID');
  });

  it('rebuilds the preference body explicitly and never sends the GET-only custom marker', () => {
    expect(studioPreferencesFromIntent({
      expected_version: 3,
      values: [
        { intent_id: 'custom', label: '我的短片', selected: true },
        { intent_id: 'image_design', label: '图片设计', selected: true },
        { intent_id: 'novel_writing', label: '小说创作', selected: false },
      ],
    })).toEqual({ expected_version: 3, intents: ['CUSTOM', 'IMAGE_DESIGN'], custom_intent: '我的短片' });
    // The GET-only marker and an unknown identifier are refused before the body exists.
    for (const values of [
      [{ intent_id: 'custom', label: '我的短片', selected: true, custom: true }],
      [{ intent_id: 'image_design', label: '图片设计', selected: true, note: 'no' }],
    ]) {
      expect(() => studioPreferencesFromIntent({ expected_version: 0, values })).toThrow(ApiError);
    }
  });

  it('sends the original session, branch and idempotency headers through the Studio transport', async () => {
    const projectId = 'studio-project';
    const scope: CollaborationContext['scope'] = { workspaceId: 'w', projectId, storylineId: 's', branchId: 'branch' };
    const calls: [string, RequestInit][] = [];
    const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
      calls.push([url, init]);
      if (url === '/api/novels') return { ok: true, status: 200, json: async () => [{ id: projectId, title: '项目' }] };
      if (url === '/api/experimental/projects') return { ok: true, status: 201, json: async () => ({ ...created, id: projectId }) };
      return { ok: true, status: 200, json: async () => preferences() };
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = createStudioEntryClient(studioTransport({ sessionToken: 'session-original', scope }), projectId);
    await client.listProjects();
    await client.createBlankProject({ title: '项目' });
    await client.readIntent(projectId);
    await client.saveIntent(projectId, { expected_version: 1, values: [{ intent_id: 'image_design', label: '图片设计', selected: true }] });
    expect(calls.map(([url]) => url)).toEqual([
      '/api/novels', '/api/experimental/projects',
      `/api/projects/${encodeURIComponent(projectId)}/studio/preferences`,
      `/api/projects/${encodeURIComponent(projectId)}/studio/preferences`,
    ]);
    expect(calls.map(([, init]) => init.method)).toEqual(['GET', 'POST', 'GET', 'PUT']);
    for (const [, init] of calls) {
      expect(init.headers).toMatchObject({ 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch', 'X-Request-ID': expect.any(String) });
    }
    expect((calls[0][1].headers as Record<string, string>)['Idempotency-Key']).toBeUndefined();
    expect((calls[1][1].headers as Record<string, string>)['Idempotency-Key']).toEqual(expect.any(String));
    expect(JSON.parse(String(calls[3][1].body))).toEqual({ expected_version: 1, intents: ['IMAGE_DESIGN'], custom_intent: '' });
  });

  it('keeps the catalog default label when the owner saved no custom text', () => {
    const state = studioIntentFromPreferences(preferences({ intents: ['CUSTOM'], custom_intent: '' }));
    expect(state.values.find(item => item.intent_id === 'custom')).toMatchObject({ label: '自定义', selected: true });
    const blank = studioIntentFromPreferences({ version: 0, intents: [], preset: 'BLANK', custom_intent: '' });
    expect(blank.values.every(item => !item.selected)).toBe(true);
    expect(blank.version).toBe(0);
  });
});
