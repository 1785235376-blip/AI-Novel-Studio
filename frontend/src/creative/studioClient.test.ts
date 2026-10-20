import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { isPackagedDesktopHost } from '../packagedHost';
import { createStudioProject, studioClient, type StudioAsset, type StudioOverview, type StudioPreferences, type StudioStorage } from './studioClient';

vi.mock('../packagedHost', () => ({ isPackagedDesktopHost: vi.fn(() => false) }));
const projectId = 'project / one';
const root = '/api/projects/project%20%2F%20one/studio';
const context = (): CollaborationContext => ({ sessionToken: 'session-original', actor: { id: 'author', displayName: 'Author', workspaceId: 'w' }, scope: { workspaceId: 'w', projectId, storylineId: 's', branchId: 'branch-original' } });
const preferences = (): StudioPreferences => ({ version: 0, intents: [], preset: 'BLANK', custom_intent: '' });
const asset = (overrides: Partial<StudioAsset> = {}): StudioAsset => ({ id: 'asset / one', novel_id: projectId, branch_id: 'branch-original', filename: 'drawing.png', kind: 'image', media_type: 'image/png', size: 3, sha256: 'digest', version: 1, created_at: '2026-10-09T00:00:00Z', updated_at: '2026-10-09T00:00:00Z', ...overrides });
const overview = (): StudioOverview => ({ project: { id: projectId, title: 'Blank project', entry_kind: 'NEUTRAL_STUDIO' }, preferences: preferences(), capabilities: { can_mutate: true, manual_import: true, manual_export: true, chapter_required: false, model_required: false, media_validator_configured: false, asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } });
const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => value });
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(reply(asset()));
  vi.stubGlobal('fetch', fetchMock);
  vi.mocked(isPackagedDesktopHost).mockReturnValue(false);
  useLocalHostSession.setState({ token: '', actorId: '' });
});
afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });

describe('studio transport captured authority', () => {
  it('captures the session and a copied branch before a caller mutates its origin', async () => {
    const origin = context();
    const client = studioClient(projectId, origin);
    origin.sessionToken = 'session-later'; origin.scope!.branchId = 'branch-later';
    origin.scope = { ...origin.scope!, branchId: 'branch-replaced' };
    await client.asset('asset / one');
    await client.restore('asset / one', 3);
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([`${root}/assets/asset%20%2F%20one`, `${root}/assets/asset%20%2F%20one/restore`]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init.headers).toMatchObject({ 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original', 'X-Request-ID': expect.any(String) });
    }
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
    expect(fetchMock.mock.calls[1][1].headers).toHaveProperty('Idempotency-Key');
    expect(fetchMock.mock.calls[0][0]).not.toContain('session');
  });

  it('captures a local-host fallback once without adopting a later credential', async () => {
    fetchMock.mockResolvedValue(reply(preferences()));
    useLocalHostSession.setState({ token: 'host-at-capture' });
    const captured = studioClient(projectId, { sessionToken: '' });
    useLocalHostSession.setState({ token: 'host-later' });
    await captured.preferences();
    expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('host-at-capture');
  });

  it('respects an explicitly captured empty local token', async () => {
    fetchMock.mockResolvedValue(reply(preferences()));
    useLocalHostSession.setState({ token: 'unrelated-session' });
    await studioClient(projectId, { sessionToken: '', localHostToken: '' }).preferences();
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('X-Session-Token');
  });

  it('does not borrow local credentials for scoped, actor-bound, or packaged sessions', async () => {
    fetchMock.mockResolvedValue(reply(preferences()));
    useLocalHostSession.setState({ token: 'unrelated-session' });
    await studioClient(projectId, { sessionToken: '', scope: context().scope, localHostToken: 'unrelated-explicit' }).preferences();
    await studioClient(projectId, { sessionToken: '', actor: context().actor }).preferences();
    vi.mocked(isPackagedDesktopHost).mockReturnValue(true);
    await studioClient(projectId, { sessionToken: '', localHostToken: 'unrelated-explicit' }).preferences();
    for (const [, init] of fetchMock.mock.calls) expect(init.headers).not.toHaveProperty('X-Session-Token');
  });

  it('prefers an explicit authenticated session over any local credential', async () => {
    await studioClient(projectId, { ...context(), localHostToken: 'local-other' }).asset('asset / one');
    expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('session-original');
  });
});

describe('studio route and payload contracts', () => {
  it('creates a canonical blank project and exposes the shared-scope handoff flags', async () => {
    const result = { id: 'new-id', title: 'Blank', studio_ready: false, requires_scope_selection: true };
    fetchMock.mockResolvedValue(reply(result, 201));
    const origin = context();
    const pending = createStudioProject('Blank', origin);
    origin.sessionToken = 'changed'; origin.scope!.branchId = 'changed';
    expect(await pending).toEqual(result);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/experimental/projects');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST', body: JSON.stringify({ title: 'Blank' }), headers: { 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original', 'Idempotency-Key': expect.any(String) } });
  });

  it('reads the neutral overview and activates only through the explicit mutation', async () => {
    fetchMock.mockResolvedValue(reply(overview()));
    const client = studioClient(projectId, context());
    expect(await client.overview()).toEqual(overview());
    await client.activate();
    expect(fetchMock.mock.calls.map(call => [call[0], call[1].method])).toEqual([[root, 'GET'], [`${root}/activate`, 'POST']]);
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
    expect(fetchMock.mock.calls[1][1].headers).toHaveProperty('Idempotency-Key');
  });

  it('saves preferences with an explicit zero version and only the permitted input fields', async () => {
    fetchMock.mockResolvedValue(reply({ ...preferences(), version: 1 }));
    const client = studioClient(projectId, context());
    const value: StudioPreferences = { version: 99, intents: ['IMAGE_DESIGN', 'CUSTOM'], preset: 'IMAGE', custom_intent: 'Sketch ideas' };
    await client.savePreferences(value, 0);
    expect(fetchMock.mock.calls[0][0]).toBe(`${root}/preferences`);
    expect(fetchMock.mock.calls[0][1].method).toBe('PUT');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ intents: ['IMAGE_DESIGN', 'CUSTOM'], preset: 'IMAGE', custom_intent: 'Sketch ideas', expected_version: 0 });
    expect(value.version).toBe(99);
  });

  it('preserves a stable import key in the body and the HTTP header across retries', async () => {
    const client = studioClient(projectId, context());
    const body = { filename: 'drawing.png', kind: 'image' as const, content_base64: 'YWJj', idempotency_key: 'same-upload' };
    await client.importAsset(body); await client.importAsset(body);
    for (const [url, init] of fetchMock.mock.calls) {
      expect(url).toBe(`${root}/assets`); expect(init.method).toBe('POST');
      expect(JSON.parse(init.body)).toEqual(body);
      expect(init.headers['Idempotency-Key']).toBe('same-upload');
    }
    expect(fetchMock.mock.calls[0][1].headers['X-Request-ID']).not.toBe(fetchMock.mock.calls[1][1].headers['X-Request-ID']);
  });

  it('uses existing lineage declarations and optimistic asset lifecycle versions', async () => {
    const client = studioClient(projectId, context());
    const lineage = { expected_version: 4, origin: 'EXTERNAL_IMPORT' as const, parent_asset_ids: [], chapter_ids: [], license: { label: 'Own work', source: '', note: '' }, operation: '' };
    await client.lineage('asset / one', lineage); await client.remove('asset / one', 5); await client.restore('asset / one', 6);
    expect(fetchMock.mock.calls.map(call => [call[0], call[1].method])).toEqual([
      [`${root}/assets/asset%20%2F%20one/lineage`, 'PUT'],
      [`${root}/assets/asset%20%2F%20one?expected_version=5`, 'DELETE'],
      [`${root}/assets/asset%20%2F%20one/restore`, 'POST'],
    ]);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(lineage);
    expect(fetchMock.mock.calls[1][1]).not.toHaveProperty('body');
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ expected_version: 6 });
    expect(new Set(fetchMock.mock.calls.map(call => call[1].headers['Idempotency-Key'])).size).toBe(3);
  });

  it('forwards abort signals on every read and makes trash inclusion explicit', async () => {
    const client = studioClient(projectId, context()), signal = new AbortController().signal;
    fetchMock.mockResolvedValueOnce(reply(overview())).mockResolvedValueOnce(reply(preferences()))
      .mockResolvedValueOnce(reply({ items: [asset()] })).mockResolvedValueOnce(reply({ items: [] }))
      .mockResolvedValueOnce(reply(asset())).mockResolvedValueOnce(reply({}));
    await client.overview(signal); await client.preferences(signal); await client.assets(false, signal);
    await client.assets(true, signal); await client.asset('asset / one', signal); await client.storage(signal);
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([root, `${root}/preferences`, `${root}/assets?include_deleted=false`, `${root}/assets?include_deleted=true`, `${root}/assets/asset%20%2F%20one`, `${root}/storage`]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init).toMatchObject({ method: 'GET', signal });
      expect(init.headers).not.toHaveProperty('Idempotency-Key');
    }
    fetchMock.mockResolvedValueOnce(reply({ items: [] }));
    await client.assets();
    expect(fetchMock.mock.calls[6][0]).toBe(`${root}/assets?include_deleted=false`);
  });

  it('downloads authenticated bytes with the same captured origin, without navigating to a token URL', async () => {
    const blob = new Blob(['local image'], { type: 'image/png' }), readBlob = vi.fn().mockResolvedValue(blob);
    fetchMock.mockResolvedValue({ ok: true, status: 200, blob: readBlob });
    const origin = context(), client = studioClient(projectId, origin);
    origin.sessionToken = 'new-session'; origin.scope!.branchId = 'new-branch';
    expect(await client.download('asset / one')).toBe(blob);
    expect(fetchMock.mock.calls[0][0]).toBe(`${root}/assets/asset%20%2F%20one/download`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'GET', headers: { 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original' } });
    expect(readBlob).toHaveBeenCalledOnce();
  });

  it('exposes storage counts and ownership labels without implying physical cleanup', async () => {
    const value: StudioStorage = { assets: { count: 1, bytes: 3 }, trash: { count: 2, bytes: 6 }, limits: { asset_bytes: 25 * 1024 * 1024, project_asset_bytes: 512 * 1024 * 1024, project_assets: 1000 }, model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER', export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false };
    fetchMock.mockResolvedValue(reply(value));
    expect(await studioClient(projectId, context()).storage()).toEqual(value);
  });

  it.each([-1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1])('rejects invalid optimistic version %s before any request', value => {
    const client = studioClient(projectId, context());
    expect(() => client.savePreferences(preferences(), value)).toThrow(ApiError);
    expect(() => client.remove('asset / one', value)).toThrow(ApiError);
    expect(() => client.restore('asset / one', value)).toThrow(ApiError);
    expect(() => client.lineage('asset / one', { expected_version: value, origin: 'EXTERNAL_IMPORT' })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('never treats asset version zero as an existing asset version', () => {
    const client = studioClient(projectId, context());
    expect(() => client.remove('asset / one', 0)).toThrow(ApiError);
    expect(() => client.restore('asset / one', 0)).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('studio fail-closed responses', () => {
  it.each([401, 403, 404, 409, 422, 500])('sanitizes untrusted server details for status %i', async status => {
    fetchMock.mockResolvedValue(reply({ detail: { code: 'VERSION_CONFLICT', message: '<script>provider secret /private/file</script>', actual: { token: 'private-token' } } }, status));
    const failure = await studioClient(projectId, context()).asset('asset / one').catch(error => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.problem).toEqual({ status, code: 'VERSION_CONFLICT', message: expect.any(String) });
    expect(JSON.stringify(failure.problem)).not.toMatch(/provider secret|private-token|\/private\/file|<script>/);
  });

  it.each([null, 'server secret', [], { code: '<html>secret</html>' }, { detail: { code: 'x'.repeat(500) } }])('rejects unsafe or missing error codes', async value => {
    fetchMock.mockResolvedValue(reply(value, 500));
    await expect(studioClient(projectId, context()).overview()).rejects.toMatchObject({ problem: { code: 'STUDIO_REQUEST_FAILED', status: 500 } });
  });

  it('sanitizes server HTML on a failed download before reading it as bytes', async () => {
    const blob = vi.fn();
    fetchMock.mockResolvedValue({ ok: false, status: 403, json: async () => { throw new Error('private html'); }, blob });
    await expect(studioClient(projectId, context()).download('asset / one')).rejects.toMatchObject({ problem: { status: 403, code: 'STUDIO_REQUEST_FAILED' } });
    expect(blob).not.toHaveBeenCalled();
  });

  it('sanitizes network and invalid successful response errors', async () => {
    const client = studioClient(projectId, context());
    fetchMock.mockRejectedValueOnce(new Error('private upstream address'));
    await expect(client.overview()).rejects.toMatchObject({ problem: { status: 0, code: 'STUDIO_NETWORK_FAILED' } });
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => { throw new Error('private json'); } });
    await expect(client.preferences()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, blob: async () => { throw new Error('private bytes'); } });
    await expect(client.download('asset / one')).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });

  it('preserves cancellation semantics without reflecting an arbitrary transport message', async () => {
    const controller = new AbortController(); controller.abort();
    fetchMock.mockRejectedValue(new Error('private canceled request URL'));
    const failure = await studioClient(projectId, context()).overview(controller.signal).catch(error => error);
    expect(failure.name).toBe('AbortError'); expect(failure.message).not.toContain('private');
  });

  it('rejects an overview for another canonical project', async () => {
    fetchMock.mockResolvedValue(reply({ ...overview(), project: { ...overview().project, id: 'other-project' } }));
    await expect(studioClient(projectId, context()).overview()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
  });

  it.each([{ novel_id: 'other-project' }, { branch_id: 'other-branch' }, { branch_id: null }])('rejects assets belonging to a different captured owner: %j', async fields => {
    const client = studioClient(projectId, context());
    fetchMock.mockResolvedValueOnce(reply(asset(fields))).mockResolvedValueOnce(reply({ items: [asset(), asset(fields)] }));
    await expect(client.asset('asset / one')).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
    await expect(client.assets()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
  });

  it('allows absent local branch metadata only for the local unscoped origin', async () => {
    fetchMock.mockResolvedValue(reply(asset({ branch_id: undefined })));
    expect(await studioClient(projectId, { sessionToken: '', localHostToken: '' }).asset('asset / one')).toMatchObject({ novel_id: projectId });
  });
});
