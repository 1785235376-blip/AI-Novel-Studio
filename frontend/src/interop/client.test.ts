// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { interopClient, interopErrorMessage } from './client';
import { assertCurrentHandoff, currentInteropSurface, interopFeatureRoutes } from './navigation';
const context = { sessionToken: 'secret-browser-session', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'b' } };
afterEach(() => { vi.unstubAllGlobals(); });
it('captures the originating session and sends tokens only in headers, never Tutor URLs', async () => {
  const fetch = vi.fn(async () => new Response(JSON.stringify({}))); vi.stubGlobal('fetch', fetch);
  const source = structuredClone(context), client = interopClient(source); source.sessionToken = 'new-secret'; source.scope.branchId = 'new-branch';
  const controller = new AbortController();
  await client.preview({ request_id: 'request', session_id: 'interop-session', content_kind: 'NONE', metadata_fields: [] }, controller.signal);
  const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe('/api/local-interop/context/preview');
  expect(url).not.toContain('secret'); expect(init.headers).toMatchObject({ 'X-Session-Token': context.sessionToken, 'X-Branch-Id': 'b' });
  expect(init.redirect).toBe('error'); expect(init.signal).toBe(controller.signal);
  expect(String(init.body)).not.toContain('secret');
});
it('cancels a request by bounded request identity before a Tutor session exists', async () => {
  const fetch = vi.fn(async () => new Response('{}')); vi.stubGlobal('fetch', fetch);
  await interopClient(context).cancel('request');
  expect(JSON.parse(String((fetch.mock.calls[0] as any[])[1].body))).toEqual({ request_id: 'request' });
});
it('uses structured protocol error codes, never arbitrary response strings', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ protocol_name: 'PoemSeed Local Interop', protocol_version: '1.0', code: 'PROTOCOL_INCOMPATIBLE', message: 'secret path' }), { status: 409 })));
  let error: unknown; try { await interopClient(context).status(); } catch (value) { error = value; }
  expect(error).toBeInstanceOf(ApiError); expect(interopErrorMessage(error)).toBe('协议版本不兼容，未建立连接。');
  expect(String(error)).not.toContain('secret path');
});
it('does not reveal server HTML on malformed errors', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('<script>credential</script>', { status: 500 })));
  let error: unknown; try { await interopClient(context).status(); } catch (value) { error = value; }
  expect(interopErrorMessage(error)).not.toContain('credential');
});
it('rejects forged cross-project, branch and unsupported action navigation without interpreting URI schemes', () => {
  for (const route of [{ action: 'OPEN_PROJECT', project_id: 'other' }, { action: 'OPEN_FEATURE', feature: 'editor', scope: { workspace_id: 'w', project_id: 'p', storyline_id: 's', branch_id: 'other' } }, { action: 'RUN_MODEL', feature: 'editor' }]) {
    expect(() => assertCurrentHandoff(route as any, context, 'p')).toThrow(ApiError);
  }
  expect(interopFeatureRoutes['javascript:alert(1)']).toBeUndefined(); expect(interopFeatureRoutes['studio://feature/model-center']).toBeUndefined();
  expect(() => assertCurrentHandoff({ action: 'OPEN_PROJECT', project_id: 'p', scope: { workspace_id: 'w', project_id: 'p', storyline_id: 's', branch_id: 'b' } }, context, 'p')).not.toThrow();
});
it('maps the real active Studio surface through a product-independent allowlist', () => {
  expect(currentInteropSurface('NOVEL', 'history')).toBe('editor');
  expect(currentInteropSurface('NOVEL', 'experimental', 'story_simulator_v2')).toBe('story-simulator');
  expect(currentInteropSurface('NOVEL', 'exports')).toBe('export');
  expect(currentInteropSurface('IMAGE', 'history')).toBe('media');
  expect(interopFeatureRoutes['model-center']).toEqual({ module: 'CONTROL', controlTab: 'models' });
});

it('rejects a typed revocation error frame even after success headers were sent', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ protocol_name: 'PoemSeed Local Interop', protocol_version: '1.0', code: 'SESSION_REVOKED', message: 'SESSION_REVOKED' }), { status: 200 })));
  await expect(interopClient(context).status()).rejects.toMatchObject({ problem: { code: 'SESSION_REVOKED' } });
});

it('keeps event preview, positive subscription and revocation separate from one-shot sends', async () => {
  const fetch = vi.fn(async () => new Response('{}')); vi.stubGlobal('fetch', fetch);
  const client = interopClient(context);
  await client.eventPreview('host-session', ['task'], 'event-preview');
  await client.eventSubscribe('host-session', 'immutable-preview', 'event-consent');
  await client.eventUnsubscribe('host-session', 'event-stop');
  const calls = fetch.mock.calls as unknown as [string, RequestInit][];
  expect(calls.map(([url]) => url)).toEqual(['/api/local-interop/events/preview', '/api/local-interop/events/subscribe', '/api/local-interop/events/unsubscribe']);
  expect(JSON.parse(String(calls[0][1].body))).toEqual({ session_id: 'host-session', metadata_fields: ['task'], request_id: 'event-preview' });
  expect(JSON.parse(String(calls[1][1].body))).toEqual({ session_id: 'host-session', preview_id: 'immutable-preview', request_id: 'event-consent', confirmed: true });
  expect(calls.every(([url]) => !url.includes('secret'))).toBe(true);
});
