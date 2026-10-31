// @vitest-environment jsdom
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext, type CollaborationContext} from './api';
import {localAiDiscoveryApi as discovery, localAiDiscoveryClient} from './localAiDiscoveryApi';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from './localHostSession';
import {isPackagedDesktopHost} from './packagedHost';
vi.mock('./packagedHost', () => ({isPackagedDesktopHost: vi.fn(() => false)}));
const fetchMock = vi.fn();
const deferred = <T,>() => {let resolve!: (value: T) => void; const promise = new Promise<T>(done => {resolve = done;}); return {promise, resolve};};
const bind = (token = 'original-host') => bindLocalHostSession(token, {session_mode: 'LOCAL_HOST', actor_id: 'host'});
const reply = (status = 200) => new Response(JSON.stringify(status === 200 ? {private_path: '/private/model.gguf'} : {detail: {code: 'INVALID_SESSION', message: '/private/model.gguf'}}), {status});
beforeEach(() => {setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); bind(); vi.mocked(isPackagedDesktopHost).mockReturnValue(false); fetchMock.mockReset().mockImplementation(async () => reply()); vi.stubGlobal('fetch', fetchMock);});
afterEach(() => {vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});});
describe('legacy discovery reuses the existing verified host owner', () => {
  it('uses the local host token with the unchanged explicit legacy snapshot and scan contract', async () => {
    const controller = new AbortController(); await discovery.snapshot(controller.signal); await discovery.scan();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/api/model-center/local-ai', '/api/model-center/local-ai/scan']);
    const read = fetchMock.mock.calls[0][1], scan = fetchMock.mock.calls[1][1];
    expect(read.method).toBe('GET'); expect(read.signal).toBe(controller.signal); expect(read.body).toBeUndefined(); expect(read.headers['Idempotency-Key']).toBeUndefined();
    expect(scan.method).toBe('POST'); expect(scan.body).toBe('{}'); expect(scan.headers['Idempotency-Key']).toBeTruthy();
    for (const [, init] of fetchMock.mock.calls) {expect(init.headers['X-Session-Token']).toBe('original-host'); expect(init.headers['X-Request-ID']).toBeTruthy();}
  });
  it.each([
    ['explicit empty', {sessionToken: '', localHostToken: ''}],
    ['actor metadata', {sessionToken: '', actor: {id: 'actor', displayName: 'Actor', workspaceId: 'w'}}],
    ['collaboration scope', {sessionToken: '', scope: {workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'b'}}],
  ] as [string, CollaborationContext][])('does not borrow local authority for %s', async (_label, context) => {
    setCollaborationContext(context); bind('unrelated-host'); await discovery.snapshot(); expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBeUndefined();
  });
  it('keeps collaboration credentials separate from a locally bound host', async () => {
    setCollaborationContext({sessionToken: 'collaboration-token'}); bind('unrelated-host'); await discovery.snapshot(); expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('collaboration-token');
  });
  it('leaves packaged bootstrap injection to the host without local fallback', async () => {
    vi.mocked(isPackagedDesktopHost).mockReturnValue(true); await discovery.snapshot(); expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBeUndefined();
  });
  it('never resolves a captured empty token against a later host', async () => {
    clearLocalHostSession(); const client = localAiDiscoveryClient({sessionToken: '', localHostToken: ''}); bind('later-host'); await client.snapshot(); expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBeUndefined();
  });
  it.each(['unlink', 'replace', 'ABA'] as const)('rejects both successful and denied responses after host %s', async transition => {
    for (const status of [200, 401, 403]) {
      bind(); const pending = deferred<Response>(); fetchMock.mockImplementationOnce(() => pending.promise); const result = discovery.snapshot(); const assertion = expect(result).rejects.toMatchObject({name: 'AbortError'});
      clearLocalHostSession(); if (transition !== 'unlink') bind('other-host'); if (transition === 'ABA') {clearLocalHostSession(); bind();}
      pending.resolve(reply(status)); await assertion;
    }
  });
  it.each([200, 401, 403])('rejects status %s after deferred body parsing and an A → B → A epoch change', async status => {
    const body = deferred<object>(), parsing = deferred<boolean>();
    fetchMock.mockImplementationOnce(async () => ({ok: status === 200, status, headers: new Headers(), json: () => {parsing.resolve(true); return body.promise;}}));
    const result = discovery.snapshot(), assertion = expect(result).rejects.toMatchObject({name: 'AbortError'}); await parsing.promise;
    clearLocalHostSession(); bind('other-host'); clearLocalHostSession(); bind(); body.resolve({private_path: '/private/model.gguf', detail: {code: 'INVALID_SESSION'}}); await assertion;
  });
  it('rejects an old response when collaboration context changes without a host change', async () => {
    const pending = deferred<Response>(); fetchMock.mockImplementationOnce(() => pending.promise); const result = discovery.snapshot(), assertion = expect(result).rejects.toMatchObject({name: 'AbortError'});
    setCollaborationContext({sessionToken: '', actor: {id: 'other', displayName: 'Other', workspaceId: 'w'}}); pending.resolve(reply()); await assertion;
  });
});
