// @vitest-environment jsdom
import {afterEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext} from './api';
import {localAiDiscoveryApi as api} from './localAiDiscoveryApi';

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
