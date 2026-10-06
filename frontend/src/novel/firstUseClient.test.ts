import { afterEach, describe, expect, it, vi } from 'vitest';
import { firstUseClient } from './firstUseClient';
import { setCollaborationContext } from '../api';
afterEach(() => vi.unstubAllGlobals());
describe('firstUseClient', () => {
  it('captures session and workspace without putting credentials in a URL', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ item: null, model_calls: 0 }) }); vi.stubGlobal('fetch', fetch);
    const context = { sessionToken: 'old-token', scope: { workspaceId: 'old/workspace' } } as any;
    const client = firstUseClient(context); context.sessionToken = 'new-token'; context.scope.workspaceId = 'new-workspace'; setCollaborationContext(context);
    await client.start(); await client.read(); await client.recover();
    expect(fetch.mock.calls[0][1].headers['X-Session-Token']).toBe('old-token'); expect(fetch.mock.calls[0][1].body).toBe('{"workspace_id":"old/workspace"}');
    expect(fetch.mock.calls[1][0]).toBe('/api/experimental/first-use/sample?workspace_id=old%2Fworkspace'); expect(fetch.mock.calls[2][0]).toBe('/api/experimental/first-use/sample/recover');
    expect(fetch.mock.calls.every(call => !call[0].includes('token'))).toBe(true);
  });
  it('does not retry uncertain creation or expose arbitrary failure bodies', async () => {
    const fetch = vi.fn().mockRejectedValue(new Error('synthetic transport')); vi.stubGlobal('fetch', fetch);
    await expect(firstUseClient({ sessionToken: '' }).start()).rejects.toThrow(); expect(fetch).toHaveBeenCalledOnce();
    fetch.mockResolvedValue({ ok: false, status: 403, json: async () => ({ message: 'secret body' }) });
    await expect(firstUseClient({ sessionToken: '' }).read()).rejects.toThrow('当前身份没有此操作权限');
  });
});
