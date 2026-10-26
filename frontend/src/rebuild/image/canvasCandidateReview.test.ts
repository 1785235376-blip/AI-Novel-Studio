import {Blob as NodeBlob} from 'node:buffer';
import {webcrypto} from 'node:crypto';
import {afterEach, describe, expect, it, vi} from 'vitest';
import type {CanvasTaskBinding} from './canvasTaskBinding';
import type {CanvasTaskCandidate} from './canvasTaskCandidate';
import {abortableCanvasCandidateRead, canvasCandidateBlobSha256, canvasCandidateObservationSha256,
  checkedCanvasCandidateAsset, sameCanvasCandidateAsset} from './canvasCandidateReview';

const binding: CanvasTaskBinding = {schema_version: 1, nodeId: 'node-a', taskId: 'job-a', owner: {
  mode: 'local', actorId: 'actor-a', actorWorkspaceId: '', workspaceId: '', projectId: 'project-a',
  storylineId: '', branchId: '', novelId: 'project-a',
}};
const candidate: CanvasTaskCandidate = {jobId: 'job-a', novelId: 'project-a', nodeId: 'node-a', providerId: 'local-image', modelId: 'model-a',
  prompt: 'Fixture historical prompt', requestSha256: 'd'.repeat(64), attempt: 1, updatedAt: '2026-10-24T00:00:00Z',
  approvalStatus: 'APPROVED', assetId: 'asset-a', previewKind: 'asset', sourceUri: 'https://example.invalid/opaque?signature=fixture-secret'};
const asset = {id: 'asset-a', novel_id: 'project-a', branch_id: null, source_job_id: 'job-a', kind: 'image', deleted_at: null,
  version: 2, sha256: 'a'.repeat(64), provider_id: 'local-image', model_id: 'model-a', size: 69, media_type: 'image/png'};
afterEach(() => { vi.unstubAllGlobals(); });

describe('browser-only adopted asset observation checks', () => {
  it('reads the real asset version and digest, without treating the Job timestamp as a version', () => {
    const observed = checkedCanvasCandidateAsset(binding, candidate, asset)!;
    expect(observed.assetVersion).toBe(2);
    expect(observed.assetSha256).toBe(asset.sha256);
    const later = checkedCanvasCandidateAsset(binding, candidate, {...asset, version: 3})!;
    expect(sameCanvasCandidateAsset(observed, later)).toBe(false);
  });
  it.each([
    ['foreign asset', {id: 'asset-b'}], ['foreign project', {novel_id: 'project-b'}], ['foreign branch', {branch_id: 'branch-b'}],
    ['other source Job', {source_job_id: 'job-b'}], ['provider changed independently', {provider_id: 'provider-b'}],
    ['model changed independently', {model_id: 'model-b'}], ['deleted asset', {deleted_at: '2026-10-24T00:01:00Z'}],
    ['wrong kind', {kind: 'video'}], ['missing real version', {version: undefined}], ['invalid version', {version: 0}],
    ['invalid digest', {sha256: 'not-a-content-digest'}], ['zero bytes', {size: 0}], ['oversized bytes', {size: 36 * 1024 * 1024 + 1}],
    ['unsupported media', {media_type: 'image/svg+xml'}],
  ])('refuses %s even when the original Job observation is unchanged', (_label, change) => {
    expect(checkedCanvasCandidateAsset(binding, candidate, {...asset, ...change})).toBeUndefined();
  });
  it('does not make pending or inline candidates locally adoptable', () => {
    expect(checkedCanvasCandidateAsset(binding, {...candidate, approvalStatus: 'PENDING', previewKind: 'inline'}, asset)).toBeUndefined();
  });
  it('measures actual Blob bytes with WebCrypto SHA-256', async () => {
    vi.stubGlobal('crypto', webcrypto);
    expect(await canvasCandidateBlobSha256(new NodeBlob(['hello']) as unknown as Blob))
      .toBe('2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824');
  });
  it('hashes every observed Job source field without returning the prompt or opaque URI', async () => {
    vi.stubGlobal('crypto', webcrypto);
    const observed = await canvasCandidateObservationSha256(candidate);
    expect(observed).toMatch(/^[a-f0-9]{64}$/);
    expect(observed).not.toContain('fixture-secret');
    for (const changed of [{sourceUri: candidate.sourceUri + '&changed=1'}, {prompt: candidate.prompt + ' changed'}, {attempt: 2}]) {
      expect(await canvasCandidateObservationSha256({...candidate, ...changed})).not.toBe(observed);
    }
  });
  it('fails content attestation when WebCrypto is unavailable', async () => {
    vi.stubGlobal('crypto', {});
    await expect(canvasCandidateBlobSha256(new NodeBlob(['hello']) as unknown as Blob)).rejects.toThrow('WebCrypto');
  });
  it('retires an uncooperative pending read on explicit abort without retrying it', async () => {
    const controller = new AbortController();
    const pending = abortableCanvasCandidateRead(new Promise<never>(() => {}), controller.signal);
    controller.abort();
    await expect(pending).rejects.toThrow('aborted');
  });
});
