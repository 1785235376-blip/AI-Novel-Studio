import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, type CreativeDocument } from './types';
import { useLocalHostSession } from '../localHostSession';
import type { CollaborationContext } from '../api';

const context = (): CollaborationContext => ({ sessionToken: 'session-original', actor: { id: 'author', displayName: 'Author', workspaceId: 'w' }, scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'branch-original' } });
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
  vi.stubGlobal('fetch', fetchMock);
  useLocalHostSession.setState({ token: '', actorId: '' });
});
afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });

describe('creative client captured identity and version contracts', () => {
  it('captures session and branch before the caller changes its context', async () => {
    const origin = context();
    const client = creativeClient('novel / one', origin);
    origin.sessionToken = 'session-later'; origin.scope!.branchId = 'branch-later';
    await client.create(newDocument('SCREENPLAY', 'chapter-1'));
    await client.update('doc / one', 7, { ...newDocument('SCREENPLAY'), title: 'Revision' });
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/novels/novel%20%2F%20one/experimental/creative/documents', '/api/novels/novel%20%2F%20one/experimental/creative/documents/doc%20%2F%20one']);
    for (const [, init] of fetchMock.mock.calls) expect(init.headers).toMatchObject({ 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original', 'X-Request-ID': expect.any(String), 'Idempotency-Key': expect.any(String) });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).not.toHaveProperty('expected_version');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ expected_version: 7, title: 'Revision' });
    expect(fetchMock.mock.calls[0][1].headers['Idempotency-Key']).not.toBe(fetchMock.mock.calls[1][1].headers['Idempotency-Key']);
  });

  it('does not borrow local-host credentials for an explicitly captured empty token', async () => {
    useLocalHostSession.setState({ token: 'unrelated-host-session' });
    await creativeClient('n', { sessionToken: '', localHostToken: '' }).capabilities();
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('X-Session-Token');
  });

  it('captures the legacy local-host fallback once and excludes it from scoped requests', async () => {
    useLocalHostSession.setState({ token: 'host-at-capture' });
    const captured = creativeClient('n', { sessionToken: '' });
    useLocalHostSession.setState({ token: 'host-later' });
    await captured.list();
    await creativeClient('n', { sessionToken: '', scope: context().scope }).list();
    expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('host-at-capture');
    expect(fetchMock.mock.calls[1][1].headers).not.toHaveProperty('X-Session-Token');
  });

  it('binds proposal creation, review, and cancellation to source/version/digest', async () => {
    const client = creativeClient('n', context());
    const source = { ...newDocument('SCREENPLAY'), id: 'source', version: 4 } as CreativeDocument;
    const proposal: DirectorProposal = { id: 'proposal / 1', version: 3, status: 'NEEDS_REVIEW', source_document_id: 'source', source_version: 4, title: 'Draft', director_notes: [], output_digest: 'digest-reviewed', provenance: { model_called: false } };
    await client.propose(source); await client.review(proposal, 'Reviewed', []); await client.cancelProposal(proposal);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ source_document_id: 'source', expected_source_version: 4 });
    expect(fetchMock.mock.calls[1][0]).toContain('/director-proposals/proposal%20%2F%201/review');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ expected_version: 3, reviewed_output_digest: 'digest-reviewed', title: 'Reviewed', director_notes: [] });
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ expected_version: 3 });
  });

  it('passes abort signals on reads and never adds mutation keys to GET requests', async () => {
    const signal = new AbortController().signal;
    await creativeClient('n', context()).history('doc', signal);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ signal, method: 'GET' });
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
  });

  it.each([401, 403, 409, 500])('sanitizes untrusted response detail for status %i', async status => {
    fetchMock.mockResolvedValue({ ok: false, status, json: async () => ({ detail: { code: 'VERSION_CONFLICT', message: '<script>private provider secret</script>' } }) });
    const failure = await creativeClient('n', context()).list().catch(error => error);
    expect(failure.status).toBe(status); expect(failure.problem.code).toBe('VERSION_CONFLICT');
    expect(failure.message).not.toContain('private provider secret'); expect(failure.message).not.toContain('<script>');
  });
  it('binds derive and restore requests to the current source version', async () => {
    const client = creativeClient('n', context()), source = { ...newDocument('SCREENPLAY'), id: 'doc-1', version: 7 } as CreativeDocument;
    await client.derive(source, 'STORYBOARD'); await client.restore(source, 3);
    expect(fetchMock.mock.calls[0][0]).toContain('/documents/doc-1/derive'); expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ expected_version: 7, mode: 'STORYBOARD' });
    expect(fetchMock.mock.calls[1][0]).toContain('/documents/doc-1/restore'); expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ expected_version: 7, restore_version: 3 });
  });

  it('binds model dispatch to the reviewed preview digest and current proposal version', async () => {
    const proposal: DirectorProposal = { id: 'proposal-1', version: 3, status: 'NEEDS_REVIEW', source_document_id: 'source', source_version: 4, title: 'Draft', director_notes: [], output_digest: 'output-digest', provenance: { model_called: false }, model_preview: { preview_digest: 'captured-preview', execution_available: true, model_called: false, allow_cloud_fallback: false, automatic_retry: false, timeout_seconds: 30, source_strategy: 'SAVED_SCREENPLAY', request: {}, broker: { chosen: { provider_id: 'local', model_id: 'director' } } } };
    const client = creativeClient('n', context()); await client.previewModel(proposal, 'route-1'); await client.dispatchModel(proposal); await client.refreshModel(proposal);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ expected_version: 3, route_id: 'route-1' });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ expected_version: 3, reviewed_preview_digest: 'captured-preview' });
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ expected_version: 3 });
  });

});
