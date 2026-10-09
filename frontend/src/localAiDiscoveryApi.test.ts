// @vitest-environment jsdom
import {afterEach, describe, expect, it, vi} from 'vitest';
import {ApiError, setCollaborationContext} from './api';
import {localAiDiscoveryApi as api} from './localAiDiscoveryApi';

describe('authenticated Local AI API', () => {
  afterEach(() => {vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''});});
  it('sends the shared in-memory session and explicit enable confirmation', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({id: 'registered', enabled: true}))); vi.stubGlobal('fetch', fetch);
    setCollaborationContext({sessionToken: 'trusted-desktop'}); await api.enable('model/one');
    const [url, init] = fetch.mock.calls[0]; expect(url).toBe('/api/model-center/local-ai/registrations/model%2Fone/enable'); expect(init.headers['X-Session-Token']).toBe('trusted-desktop'); expect(init.headers['Idempotency-Key']).toBeTruthy(); expect(JSON.parse(init.body)).toEqual({confirmed: true});
  });
  it('encodes scan IDs, forwards cancellation, and removes registration only', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response('{}')); vi.stubGlobal('fetch', fetch); const controller = new AbortController();
    await api.scanStatus('scan/1', controller.signal); expect(fetch.mock.calls[0][0]).toBe('/api/model-center/local-ai/scan/scan%2F1'); expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
    await api.cancelScan('scan/1'); expect(fetch.mock.calls[1][0]).toBe('/api/model-center/local-ai/scan/scan%2F1/cancel'); expect(fetch.mock.calls[1][1].method).toBe('POST');
    await api.remove('model/one'); expect(fetch.mock.calls[2][0]).toBe('/api/model-center/local-ai/registrations/model%2Fone'); expect(fetch.mock.calls[2][1].method).toBe('DELETE');
  });
  it('preserves structured auth errors without echoing arbitrary response details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: {code: 'INVALID_SESSION', message: 'sensitive response'}}), {status: 401})));
    try {await api.snapshot(); throw new Error('expected rejection');} catch (caught) {expect(caught).toBeInstanceOf(ApiError); expect((caught as ApiError).problem.code).toBe('INVALID_SESSION'); expect((caught as Error).message).not.toContain('sensitive');}
  });
});

describe('V2 environment API', () => {
  afterEach(() => {vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''});});
  it('reads typed host report with authentication and abort signal without starting scan', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response('{}')); vi.stubGlobal('fetch', fetch);
    setCollaborationContext({sessionToken:'fixture'}); const controller = new AbortController();
    await api.environment(controller.signal);
    expect(fetch.mock.calls[0][0]).toBe('/api/model-center/local-ai/environment');
    expect(fetch.mock.calls[0][1].method).toBe('GET');
    expect(fetch.mock.calls[0][1].headers['X-Session-Token']).toBe('fixture');
    expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
  });
  it('sends explicit common-directory opt-out only when provided', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response('{}')); vi.stubGlobal('fetch', fetch);
    await api.settings([], false); expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({scan_roots:[],include_common_model_dirs:false});
    await api.settings([]); expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({scan_roots:[]});
  });
});
