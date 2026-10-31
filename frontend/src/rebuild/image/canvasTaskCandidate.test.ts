// @vitest-environment jsdom
// Pure metadata/URI projection only. No HTTP, provider, media decoding or browser acceptance.
import {describe, expect, it, vi} from 'vitest';
import {getCollaborationContext, setCollaborationContext} from '../../api';
import {captureCanvasTaskOwner} from './canvasTaskBinding';
import type {CanvasTaskBinding} from './canvasTaskBinding';
import {checkedCanvasTaskCandidate, sameCanvasTaskCandidate} from './canvasTaskCandidate';

const binding: CanvasTaskBinding = {schema_version: 1, nodeId: 'image-node', taskId: 'server-job', owner: {
  mode: 'local', actorId: 'verified-local-actor', actorWorkspaceId: '', workspaceId: '', projectId: 'project-a',
  storylineId: '', branchId: '', novelId: 'project-a',
}};
const row = (changes: Record<string, unknown> = {}) => ({
  id: 'server-job', novel_id: 'project-a', branch_id: null, owner_actor_id: null, status: 'SUCCEEDED',
  provider_id: 'local-provider', model_id: 'original-model', prompt: 'Original queued prompt\n第二行',
  request_sha256: 'a'.repeat(64), attempt: 1, updated_at: '2026-10-23T13:00:00.123456+00:00', approval_status: 'PENDING',
  asset_uri: 'https://results.invalid/original.png?signature=fixture-signed-value', ...changes,
});

describe('original image-job candidate observation', () => {
  it('keeps an unapproved network source opaque without creating a preview route, read or execution', () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    try {
      const candidate = checkedCanvasTaskCandidate(binding, row({execution_token: 'not-for-display', secret: 'unrelated-response-field', version: 99}));
      expect(candidate).toEqual({jobId: 'server-job', novelId: 'project-a', nodeId: 'image-node',
        providerId: 'local-provider', modelId: 'original-model', prompt: 'Original queued prompt\n第二行', requestSha256: 'a'.repeat(64),
        attempt: 1, updatedAt: '2026-10-23T13:00:00.123456+00:00', approvalStatus: 'PENDING',
        sourceUri: row().asset_uri, previewKind: undefined, previewUri: undefined});
      expect(Object.isFrozen(candidate)).toBe(true);
      expect(candidate).not.toHaveProperty('execution_token');
      expect(candidate).not.toHaveProperty('secret');
      expect(candidate).not.toHaveProperty('version');
      expect(fetcher).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); }
  });

  it.each(['QUEUED', 'RUNNING', 'FAILED', 'CANCELLED', 'APPROVED'])('does not turn %s into a completed candidate', status => {
    expect(checkedCanvasTaskCandidate(binding, row({status}))).toBeUndefined();
  });

  it.each([
    {id: 'other-job'}, {novel_id: 'other-project'}, {branch_id: 'unexpected-branch'}, {owner_actor_id: 'foreign-actor'},
    {contract: 'studio-image-execution/1'}, {request_sha256: undefined}, {request_sha256: 'not-an-input-digest'},
    {attempt: 0}, {attempt: 1.5}, {attempt: Number.MAX_SAFE_INTEGER + 1}, {updated_at: undefined}, {updated_at: 'invalid-date'},
    {provider_id: ''}, {model_id: ''}, {prompt: ' '}, {approval_status: 'UNKNOWN'}, {asset_id: 'unexpected-pending-asset'},
  ])('rejects a contradictory or incomplete completion row: %j', change => {
    expect(checkedCanvasTaskCandidate(binding, row(change))).toBeUndefined();
  });

  it('requires the exact collaboration branch and actor while keeping File/local semantics separate', () => {
    const shared: CanvasTaskBinding = {...binding, owner: {...binding.owner, mode: 'collaboration', actorId: 'author-a',
      actorWorkspaceId: 'workspace-a', workspaceId: 'workspace-a', storylineId: 'story-a', branchId: 'branch-a'}};
    const candidate = row({branch_id: 'branch-a', owner_actor_id: 'author-a'});
    expect(checkedCanvasTaskCandidate(shared, candidate)).toBeTruthy();
    expect(checkedCanvasTaskCandidate(shared, {...candidate, branch_id: 'branch-b'})).toBeUndefined();
    expect(checkedCanvasTaskCandidate(shared, {...candidate, owner_actor_id: 'author-b'})).toBeUndefined();
    expect(checkedCanvasTaskCandidate(shared, {...candidate, owner_actor_id: null})).toBeUndefined();
  });

  it.each([
    {label: 'colon and dot', novelId: 'project:alpha.v2', actorId: 'author:one.v2', workspaceId: 'workspace:one.v2', storylineId: 'story:one.v2', branchId: 'branch:one.v2'},
    {label: 'Unicode', novelId: '作品-甲', actorId: '作者-甲', workspaceId: '工作区-甲', storylineId: '故事线-甲', branchId: '分支-甲'},
  ])('accepts existing binding owners with $label IDs', ({novelId, actorId, workspaceId, storylineId, branchId}) => {
    const previous = getCollaborationContext();
    try {
      setCollaborationContext({sessionToken: 'fixture-candidate-context',
        actor: {id: actorId, workspaceId, displayName: 'Synthetic candidate author'},
        scope: {workspaceId, projectId: novelId, storylineId, branchId}});
      const owner = captureCanvasTaskOwner(novelId);
      expect(owner).toBeDefined();
      if (!owner) throw new Error('The existing binding contract must accept this fixture owner');
      const candidate = checkedCanvasTaskCandidate({...binding, owner}, row({novel_id: novelId, branch_id: branchId, owner_actor_id: actorId}));
      expect(candidate?.jobId).toBe('server-job');
      expect(candidate?.novelId).toBe(novelId);
    } finally { setCollaborationContext(previous); }
  });

  it('routes approved results only through their original asset ID, even for an inline source', () => {
    expect(checkedCanvasTaskCandidate(binding, row({approval_status: 'APPROVED'}))).toBeUndefined();
    for (const source of [row().asset_uri, 'data:image/png;base64,YWJj', undefined]) {
      const candidate = checkedCanvasTaskCandidate(binding, row({approval_status: 'APPROVED', asset_id: 'approved-asset', asset_uri: source}));
      expect(candidate?.approvalStatus).toBe('APPROVED');
      expect(candidate?.assetId).toBe('approved-asset');
      expect(candidate?.previewKind).toBe('asset');
      expect(candidate?.previewUri).toBeUndefined();
      expect(candidate?.sourceUri).toBe(source);
    }
  });

  it.each(['png', 'jpeg', 'jpg', 'webp', 'gif'])('allows pending %s only as embedded raster/base64 syntax, not media verification', kind => {
    // Synthetic base64 text deliberately establishes only syntax, not image contents.
    const uri = `data:image/${kind};base64,YWJj`;
    const candidate = checkedCanvasTaskCandidate(binding, row({asset_uri: uri}));
    expect(candidate?.previewKind).toBe('inline');
    expect(candidate?.previewUri).toBe(uri);
  });

  it.each([
    undefined, '', 'javascript:alert(1)', 'file:///private/image.png', 'data:image/svg+xml;base64,PHN2Zz4=',
    '//other.invalid/image.png', '/\\other.invalid/image.png', '/path\nwith-control.png',
    'https://user:password@results.invalid/image.png', 'https://results.invalid/with\\backslash.png',
    'blob:https://user:password@results.invalid/image', 'data:image/png;base64,invalid%%', 'blob:not-a-valid-origin',
    'https://results.invalid/ready.png?signature=fixture', 'http://127.0.0.1:8188/view?filename=ready.png',
    '/api/assets/read-only-asset/download?novel_id=project-a', 'blob:https://studio.invalid/browser-owned-image',
    'data:image/png;base64,abc', 'data:image/png;base64,A===', 'data:image/png;base64,YW\nJj', 'data:image/png;base64,YWJ\n',
    ' data:image/png;base64,YWJj', 'data:image/png;base64,YWJj ', 'data:image/png;charset=utf-8;base64,YWJj',
    'data:image/png;base64,',
  ])('retains pending provenance without a direct network/blob/path or malformed inline preview: %s', uri => {
    const candidate = checkedCanvasTaskCandidate(binding, row({asset_uri: uri}));
    expect(candidate?.jobId).toBe('server-job');
    expect(candidate?.previewKind).toBeUndefined();
    expect(candidate?.previewUri).toBeUndefined();
  });

  it('keeps the original36MiB source-URI ceiling without decoding or writing media', () => {
    const source = 'data:image/png;base64,' + 'A'.repeat(36 * 1024 * 1024);
    const candidate = checkedCanvasTaskCandidate(binding, row({asset_uri: source}));
    expect(candidate?.sourceUri).toBe(source);
    expect(candidate?.previewKind).toBeUndefined();
    expect(candidate?.previewUri).toBeUndefined();
  });

  it.each([
    {request_sha256: 'b'.repeat(64)}, {attempt: 2}, {updated_at: '2026-10-23T13:00:01Z'},
    {asset_uri: 'https://results.invalid/replacement.png'}, {prompt: 'Other original prompt'}, {model_id: 'replacement-model'},
    {approval_status: 'APPROVED', asset_id: 'approved-asset'},
  ])('retires an observed preview confirmation when source fields change: %j', change => {
    expect(sameCanvasTaskCandidate(checkedCanvasTaskCandidate(binding, row()), checkedCanvasTaskCandidate(binding, row(change)))).toBe(false);
  });

  it('compares unsupported source URIs exactly without making them previewable or exposing a fake revision', () => {
    const first = checkedCanvasTaskCandidate(binding, row({asset_uri: 'javascript:first'}));
    const second = checkedCanvasTaskCandidate(binding, row({asset_uri: 'javascript:second'}));
    expect(sameCanvasTaskCandidate(first, second)).toBe(false);
    expect(sameCanvasTaskCandidate(first, checkedCanvasTaskCandidate(binding, row({asset_uri: 'javascript:first'})))).toBe(true);
    expect(sameCanvasTaskCandidate(undefined, undefined)).toBe(false);
    expect(sameCanvasTaskCandidate(checkedCanvasTaskCandidate(binding, row()), checkedCanvasTaskCandidate(binding, row()))).toBe(true);
  });
});
