import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type AssetRelationship, type AssetRelationshipReference, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { studioClient, type StudioAsset, type StudioReferenceKind, type StudioRelationshipInput, type StudioRelationshipType } from './studioClient';

const projectId = 'project / one', root = '/api/projects/project%20%2F%20one/studio';
const sha = 'a'.repeat(64);
const context = (): CollaborationContext => ({ sessionToken: 'session-original', actor: { id: 'author', displayName: 'Author', workspaceId: 'w' }, scope: { workspaceId: 'w', projectId, storylineId: 's', branchId: 'branch-original' } });
const target = (kind: StudioReferenceKind = 'SCREENPLAY'): AssetRelationshipReference => ({ kind, id: 'target / one', version: 0, digest: sha, label: 'Shared reference', deleted: false });
const relationship = (): AssetRelationship => ({ id: 'relation / one', type: 'REFERENCES', state: 'CURRENT', target: target(), expected: { kind: 'SCREENPLAY', id: 'target / one', version: 0, digest: sha }, reason: 'Keep source context', created_by: 'author', created_at: '2026-10-09T00:00:00Z', semantics: 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION' });
const asset = (overrides: Partial<StudioAsset> = {}): StudioAsset => ({ id: 'asset / one', novel_id: projectId, branch_id: 'branch-original', filename: 'image.png', kind: 'image', media_type: 'image/png', size: 3, sha256: sha, version: 4, created_at: '2026-10-09T00:00:00Z', updated_at: '2026-10-09T00:00:00Z', relationships: [relationship()], ...overrides });
const input = (): StudioRelationshipInput => ({ expected_version: 3, type: 'REFERENCES', target: { kind: 'SCREENPLAY', id: 'target / one', version: 0, digest: sha }, reason: 'Keep source context' });
const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => value });
const graph = () => ({ graph_kind: 'ASSET_RELATIONSHIPS', nodes: [{ id: 'asset / one', kind: 'ASSET', asset_kind: 'image', label: 'image.png', version: 4, digest: sha }], edges: [{ ...relationship(), from: 'asset / one' }], executable: false, knowledge_graph: false, automatic_regeneration: false });
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(reply(asset()));
  vi.stubGlobal('fetch', fetchMock);
  useLocalHostSession.setState({ token: '', actorId: '' });
});
afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });

describe('studio relationship captured transport', () => {
  it('binds relationship creation and removal to the captured project, session, branch and CAS version', async () => {
    const origin = context(), client = studioClient(projectId, origin);
    origin.sessionToken = 'later-session'; origin.scope!.branchId = 'later-branch';
    await client.addRelationship('asset / one', input());
    await client.removeRelationship('asset / one', 'relation / one', 4);
    expect(fetchMock.mock.calls.map(call => [call[0], call[1].method])).toEqual([
      [`${root}/assets/asset%20%2F%20one/relationships`, 'POST'],
      [`${root}/assets/asset%20%2F%20one/relationships/relation%20%2F%20one?expected_version=4`, 'DELETE'],
    ]);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(input());
    expect(fetchMock.mock.calls[1][1]).not.toHaveProperty('body');
    for (const [, init] of fetchMock.mock.calls) expect(init.headers).toMatchObject({ 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original', 'Idempotency-Key': expect.any(String) });
    expect(fetchMock.mock.calls[0][1].headers['Idempotency-Key']).not.toBe(fetchMock.mock.calls[1][1].headers['Idempotency-Key']);
  });

  it.each<StudioReferenceKind>(['ASSET', 'CHAPTER', 'SCREENPLAY'])('reads only the requested %s reference index with an abort signal', async kind => {
    const signal = new AbortController().signal, row = target(kind);
    fetchMock.mockResolvedValue(reply({ items: [row], read_only: true, content_copied: false }));
    expect(await studioClient(projectId, context()).references(kind, signal)).toEqual({ items: [row], read_only: true, content_copied: false });
    expect(fetchMock.mock.calls[0][0]).toBe(`${root}/references?kind=${kind}`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'GET', signal, headers: { 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original' } });
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
  });

  it('reads a descriptive relationship graph without issuing an execution request', async () => {
    const signal = new AbortController().signal;
    fetchMock.mockResolvedValue(reply(graph()));
    expect(await studioClient(projectId, context()).relationships(signal)).toEqual(graph());
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toBe(`${root}/relationships`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'GET', signal });
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
  });

  it('captures local-host credentials before later session changes', async () => {
    useLocalHostSession.setState({ token: 'host-captured' });
    const client = studioClient(projectId, { sessionToken: '' });
    useLocalHostSession.setState({ token: 'host-later' });
    fetchMock.mockResolvedValue(reply({ items: [], read_only: true, content_copied: false }));
    await client.references('ASSET');
    expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('host-captured');
    await studioClient(projectId, { sessionToken: '', localHostToken: '' }).references('ASSET');
    expect(fetchMock.mock.calls[1][1].headers).not.toHaveProperty('X-Session-Token');
  });

  it.each([{ novel_id: 'other-project' }, { branch_id: 'other-branch' }])('rejects foreign-owner relationship mutation responses: %j', async fields => {
    fetchMock.mockResolvedValue(reply(asset(fields)));
    const client = studioClient(projectId, context());
    await expect(client.addRelationship('asset / one', input())).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
    await expect(client.removeRelationship('asset / one', 'relation / one', 4)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
  });

  it('does not infer review authority from write authority or creator identity', async () => {
    const overview = { project: { id: projectId, title: 'Project', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 0, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } };
    fetchMock.mockResolvedValue(reply(overview));
    const value = await studioClient(projectId, context()).overview();
    expect(value.capabilities.can_mutate).toBe(true);
    expect(value.capabilities.can_review === true).toBe(false);
    expect(value.capabilities).not.toHaveProperty('can_review');
  });
});

describe('studio relationship narrow inputs', () => {
  it('accepts screenplay version zero and sends no target content, labels or hidden fields', async () => {
    const value = { ...input(), private_note: 'private-source-note', target: { ...target(), manuscript: 'private-manuscript', session_token: 'private-session' } };
    await studioClient(projectId, context()).addRelationship('asset / one', value);
    const sent = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sent).toEqual(input());
    expect(sent.target.version).toBe(0);
    expect(JSON.stringify(sent)).not.toMatch(/private|manuscript|label|deleted/);
  });

  it.each<StudioRelationshipType>(['SOURCE_OF', 'DERIVED_FROM', 'REFERENCES', 'USED_IN', 'ALTERNATE_VERSION', 'APPROVED_FOR', 'LINKED_CONTEXT'])('transports the explicit %s declaration without changing its semantics', async type => {
    await studioClient(projectId, context()).addRelationship('asset / one', { ...input(), type });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).type).toBe(type);
  });

  it.each(['', 'asset', 'ASSET&kind=CHAPTER', 'ALL', 'ASSET\n', undefined])('rejects invalid reference query kind %j before sending', kind => {
    expect(() => studioClient(projectId, context()).references(kind as StudioReferenceKind)).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([-1, 0, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, '3', true])('rejects invalid source CAS version %j', expectedVersion => {
    const client = studioClient(projectId, context());
    expect(() => client.addRelationship('asset / one', { ...input(), expected_version: expectedVersion as number })).toThrow(ApiError);
    expect(() => client.removeRelationship('asset / one', 'relation / one', expectedVersion as number)).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([-1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, '0', false])('rejects invalid target snapshot version %j', targetVersion => {
    expect(() => studioClient(projectId, context()).addRelationship('asset / one', { ...input(), target: { ...input().target, version: targetVersion as number } })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each(['', 'a'.repeat(63), 'a'.repeat(65), 'G'.repeat(64), 'A'.repeat(64)])('rejects malformed target digest %j', digest => {
    expect(() => studioClient(projectId, context()).addRelationship('asset / one', { ...input(), target: { ...input().target, digest } })).toThrow(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('rejects unknown relationship types, oversized reasons, invalid targets and identifiers', () => {
    const client = studioClient(projectId, context());
    for (const value of [null, { ...input(), type: 'EXECUTE' }, { ...input(), reason: 'x'.repeat(1001) }, { ...input(), reason: null }, { ...input(), target: null }, { ...input(), target: { ...input().target, id: '' } }, { ...input(), target: { ...input().target, kind: 'HIDDEN' } }]) {
      expect(() => client.addRelationship('asset / one', value as StudioRelationshipInput)).toThrow(ApiError);
    }
    for (const id of ['', ' ', 'x'.repeat(241), 'id\nsecret']) {
      expect(() => client.addRelationship(id, input())).toThrow(ApiError);
      expect(() => client.removeRelationship('asset / one', id, 4)).toThrow(ApiError);
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('studio relationship public projections', () => {
  it('strips hidden fields from a reference index rather than copying source contents', async () => {
    fetchMock.mockResolvedValue(reply({ items: [{ ...target(), content: 'private-manuscript', parameters: { private: 'hidden' } }], read_only: true, content_copied: false, source_document: 'private-manuscript' }));
    const value = await studioClient(projectId, context()).references('SCREENPLAY');
    expect(value).toEqual({ items: [target()], read_only: true, content_copied: false });
    expect(JSON.stringify(value)).not.toContain('private');
  });

  it('strips unavailable target identifiers, reasons, authors and expected snapshots from every asset projection', async () => {
    const unavailable = { ...relationship(), state: 'UNAVAILABLE', target: { ...target(), label: 'private-target-title' }, reason: 'private-reason', created_by: 'private-author', expected: { ...target(), id: 'private-id' } };
    const responseAsset = { ...asset(), relationships: [unavailable] };
    fetchMock.mockResolvedValueOnce(reply(responseAsset)).mockResolvedValueOnce(reply({ items: [responseAsset] })).mockResolvedValueOnce(reply(responseAsset));
    const client = studioClient(projectId, context());
    for (const value of [await client.asset('asset / one'), (await client.assets()).items[0], await client.addRelationship('asset / one', input())]) {
      expect(value.relationships).toEqual([{ id: 'relation / one', type: 'REFERENCES', state: 'UNAVAILABLE', target: { label: '关联内容不可用或无权访问' } }]);
      expect(JSON.stringify(value.relationships)).not.toContain('private');
      expect(value.relationships![0]).not.toHaveProperty('expected');
    }
  });

  it('keeps current, stale and deleted declarations while dropping non-public metadata', async () => {
    const rows = ['CURRENT', 'STALE', 'DELETED'].map(state => ({ ...relationship(), state, token: 'private-token', target: { ...target(), content: 'private-content' } }));
    fetchMock.mockResolvedValue(reply({ ...asset(), relationships: rows }));
    const value = await studioClient(projectId, context()).asset('asset / one');
    expect(value.relationships?.map(row => row.state)).toEqual(['CURRENT', 'STALE', 'DELETED']);
    expect(JSON.stringify(value.relationships)).not.toContain('private');
  });

  it('represents original lineage edges separately and redacts unavailable graph targets', async () => {
    const value = graph();
    const edges = [value.edges[0], { id: 'lineage-visible', from: 'asset / one', type: 'DERIVED_FROM', owner: 'ASSET_LINEAGE', state: 'CURRENT', target: target('ASSET'), private: 'hidden' },
      { id: 'lineage-hidden', from: 'asset / one', type: 'DERIVED_FROM', owner: 'ASSET_LINEAGE', state: 'UNAVAILABLE', target: { ...target('ASSET'), label: 'private-name' }, expected: { id: 'private-id' } },
      { ...value.edges[0], id: 'declared-hidden', state: 'UNAVAILABLE', target: { ...target(), label: 'private-name' }, reason: 'private-reason' }];
    fetchMock.mockResolvedValue(reply({ ...value, nodes: value.nodes.map(node => ({ ...node, content: 'private-content' })), edges, execution_plan: 'private-plan' }));
    const actual = await studioClient(projectId, context()).relationships();
    expect(actual.edges[1]).toEqual({ id: 'lineage-visible', from: 'asset / one', type: 'DERIVED_FROM', owner: 'ASSET_LINEAGE', state: 'CURRENT', target: target('ASSET') });
    expect(actual.edges[2]).toEqual({ id: 'lineage-hidden', from: 'asset / one', type: 'DERIVED_FROM', owner: 'ASSET_LINEAGE', state: 'UNAVAILABLE', target: { label: '来源不可用或无权访问' } });
    expect(actual.edges[3]).toEqual({ id: 'declared-hidden', from: 'asset / one', type: 'REFERENCES', state: 'UNAVAILABLE', target: { label: '关联内容不可用或无权访问' } });
    expect(JSON.stringify(actual)).not.toMatch(/private|execution_plan/);
  });

  it.each([{ read_only: false, content_copied: false, items: [] }, { read_only: true, content_copied: true, items: [] }, { read_only: true, content_copied: false, items: [target('CHAPTER')] }, { read_only: true, content_copied: false, items: [{ ...target(), version: -1 }] }])('rejects invalid reference guarantees or snapshot metadata', async value => {
    fetchMock.mockResolvedValue(reply(value));
    await expect(studioClient(projectId, context()).references('SCREENPLAY')).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });

  it.each([{ executable: true }, { knowledge_graph: true }, { automatic_regeneration: true }, { edges: [{ ...relationship(), from: 'foreign-owner' }] }, { nodes: [{ id: 'invalid-node', kind: 'HIDDEN' }] }])('rejects executable or invalid graph projections: %j', async fields => {
    fetchMock.mockResolvedValue(reply({ ...graph(), ...fields }));
    await expect(studioClient(projectId, context()).relationships()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });

  it('keeps conflicts and permission failures sanitized without disclosing target evidence', async () => {
    const client = studioClient(projectId, context());
    for (const status of [403, 409]) {
      fetchMock.mockResolvedValue(reply({ code: status === 409 ? 'CREATIVE_RELATIONSHIP_TARGET_CHANGED' : 'PERMISSION_DENIED', detail: { target: { id: 'private-id', content: 'private-manuscript' }, message: 'private-provider-error' } }, status));
      const failure = await client.addRelationship('asset / one', input()).catch(error => error);
      expect(failure).toBeInstanceOf(ApiError);
      expect(failure.status).toBe(status);
      expect(JSON.stringify(failure.problem)).not.toContain('private');
    }
  });
});
