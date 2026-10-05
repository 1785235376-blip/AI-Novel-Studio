import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, setCollaborationContext } from '../api';
import { enabled, experimentalClient, experimentalFeatures } from './api';
afterEach(() => { vi.unstubAllGlobals(); setCollaborationContext({ sessionToken: '' }); });
describe('Experimental request boundaries', () => {
  it('fails closed on missing flags and only accepts exact server booleans', () => {
    expect(enabled(undefined, 'advanced_planning_v2')).toBe(false);
    expect(enabled({ experimental: true, default_enabled: false, features: {} }, 'advanced_planning_v2')).toBe(false);
    expect(enabled({ experimental: true, default_enabled: false, features: { 'experimental.advanced_planning_v2': true } }, 'advanced_planning_v2')).toBe(true);
  });
  it('captures session and branch and retains version-fenced mutation body', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'proposal', version: 3 }), { status: 200 })); vi.stubGlobal('fetch', fetch);
    const scope = { workspaceId: 'w', projectId: 'n', storylineId: 's', branchId: 'branch-old' };
    const context = { sessionToken: 'old-session', scope };
    const client = experimentalClient('n/encoded', context);
    scope.branchId = 'branch-new'; context.sessionToken = 'new-session'; setCollaborationContext(context);
    await client.post('/planning/proposals/p/approve', { expected_version: 2 });
    const [url, request] = fetch.mock.calls[0];
    expect(url).toBe('/api/novels/n%2Fencoded/experimental/planning/proposals/p/approve');
    expect(request.headers['X-Session-Token']).toBe('old-session'); expect(request.headers['X-Branch-Id']).toBe('branch-old');
    expect(request.headers['Idempotency-Key']).toBeTruthy(); expect(request.headers['X-Request-ID']).toBeTruthy(); expect(JSON.parse(request.body)).toEqual({ expected_version: 2 });
  });
  it('preserves abort signals and reports safe conflict details', async () => {
    const controller = new AbortController(); const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ detail: { code: 'STALE_SOURCE', message: 'secret server payload' } }), { status: 409 })); vi.stubGlobal('fetch', fetch);
    const client = experimentalClient('novel', { sessionToken: '' });
    await expect(client.get('/planning/graphs', controller.signal)).rejects.toMatchObject({ problem: { code: 'STALE_SOURCE', status: 409 } });
    expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
    try { await client.get('/planning/graphs'); } catch (error) { expect(error).toBeInstanceOf(ApiError); expect((error as Error).message).not.toContain('secret'); }
  });
  it('uses the explicit login context for feature discovery before global synchronization', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ features: {} }), { status: 200 })); vi.stubGlobal('fetch', fetch);
    setCollaborationContext({ sessionToken: '' }); await experimentalFeatures(undefined, { sessionToken: 'new-login' });
    expect(fetch.mock.calls[0][1].headers['X-Session-Token']).toBe('new-login');
  });
  it('treats unavailable discovery as an error, never enables local fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('unavailable', { status: 501 })));
    await expect(experimentalFeatures()).rejects.toMatchObject({ problem: { status: 501 } });
  });
});
