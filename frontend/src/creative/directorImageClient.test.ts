import { afterEach, describe, expect, it, vi } from 'vitest';
import { creativeClient } from './client';
import { createDirectorImageClient, type ImageAdoptionInput, type ImageCostInput } from './directorImageClient';
import { imageAsset, imageCapabilitiesWire, imagePendingWire, imagePreview, imagePreviewWire, imageRegistration, imageReview, imageReviewWire, imageStatus, imageStatusWire, imageTarget } from './directorImage.testFixtures';
const previewInput = { asset: imagePreview.asset, target: imageTarget, provider_id: imageRegistration.provider_id, model_id: imageRegistration.model_id, instruction: 'human instruction' };
function setup(...responses: unknown[]) { const json = vi.fn(); for (const value of responses) json.mockResolvedValueOnce(value); return { json, client: createDirectorImageClient('project', { json }, { actor: { id: 'actor', workspaceId: 'w', displayName: 'Author' } }, vi.fn()) }; }
afterEach(() => vi.unstubAllGlobals());
describe('IMAGE V3 bounded browser wire boundary', () => {
  it('parses actual nested capability, preview, pending, review and original accounting/adoption projections', async () => {
    const cost: ImageCostInput = { contract: 'DIRECTOR_IMAGE_COST_DECLARATION_V3', request_id: 'cost-id', expected_version: 7, reviewed_terminal_digest: 'd'.repeat(64), declared_microusd: 0, evidence_note: 'human basis', confirmed_declaration: true };
    const adoption: ImageAdoptionInput = { contract: 'DIRECTOR_IMAGE_ADOPTION_INPUT_V1', request_id: 'adopt-id', expected_version: 3, target: imageTarget, reviewed_terminal_digest: imageReview.terminal_digest,
      reviewed_accounting_digest: imageReview.accounting_digest, selected_suggestions: [0], note: 'authored note', human_review_confirmed: true };
    const { client, json } = setup(imageCapabilitiesWire, imagePreviewWire, imageStatusWire, imagePendingWire,
      { status: 'RECONCILED', version: 8, cost_state: 'HUMAN_DECLARED_LOCAL_COST', declared_microusd: 0, measurement_verified: false,
        director_image_cost_declaration: { request_id: 'cost-id', reviewed_terminal_digest: cost.reviewed_terminal_digest } },
      imageReviewWire, { contract: 'DIRECTOR_IMAGE_ADOPTION_RECEIPT_V1', request_id: 'adopt-id', proposal_id: 'proposal', target: { ...imageTarget, version: 3, digest: 'f'.repeat(64) }, committed: true, historical: false, measurement_verified: false });
    const signal = new AbortController().signal;
    expect(await client.capabilities(signal)).toEqual({ enabled: true, registered_choices: [imageRegistration] });
    const preview = await client.preview(previewInput, signal); expect(preview.prompt).toBe('私密完整提示');
    expect(await client.dispatch(preview, signal)).toEqual(imageStatus); const pending = await client.prepare(imageStatus, imageTarget, signal); expect(pending.accounting_version).toBe(7);
    await client.declareCost('proposal', cost, signal); expect(await client.review('proposal', imageTarget, signal)).toEqual(imageReview);
    expect(await client.adopt('proposal', adoption, signal)).toMatchObject({ committed: true, target: { version: 3 } });
    expect(json.mock.calls.map(call => [call[0], call[1]])).toEqual([
      ['/api/novels/project/experimental/creative/director-image-v3/capabilities', 'GET'], ['/api/novels/project/experimental/creative/director-image-v3/preview', 'POST'],
      ['/api/novels/project/experimental/creative/director-image-v3/proposals/proposal/dispatch', 'POST'], ['/api/novels/project/experimental/creative/director-image-v3/proposals/proposal/prepare-review', 'POST'],
      ['/api/novels/project/experimental/creative/director-image-v3/proposals/proposal/declare-cost', 'POST'], ['/api/novels/project/experimental/creative/director-image-v3/proposals/proposal/review', 'POST'],
      ['/api/novels/project/experimental/creative/director-image-v3/proposals/proposal/adopt', 'POST']]);
    expect(json.mock.calls[2][2]).toEqual({ expected_version: 1, reviewed_preview_digest: imagePreview.preview_digest });
    expect(json.mock.calls[4][2]).toEqual(cost); expect(json.mock.calls[6][2]).toEqual(adoption);
  });
  it('captures original project, branch, actor and host credentials without construction-time reads', async () => {
    const context = { sessionToken: 'original', actor: { id: 'actor', workspaceId: 'w', displayName: 'Author' }, scope: { workspaceId: 'w', projectId: 'project', storylineId: 'story', branchId: 'branch' } };
    const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => imageCapabilitiesWire }).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ ...imageAsset, branch_id: 'branch' }] }) }); vi.stubGlobal('fetch', fetch);
    const owner = creativeClient('project', context); context.sessionToken = 'later'; context.actor.id = 'later-actor'; context.scope.branchId = 'later-branch';
    const client = owner.imageDirector(); expect(fetch).not.toHaveBeenCalled(); await client.capabilities(); expect((await client.assets()).items[0].id).toBe('image');
    for (const call of fetch.mock.calls) expect(call[1]).toMatchObject({ method: 'GET', headers: { 'X-Session-Token': 'original', 'X-Branch-Id': 'branch' } });
    expect(fetch.mock.calls[1][0]).toBe('/api/projects/project/studio/assets?include_deleted=false'); expect(fetch.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
  });
  it('does not change unrelated legacy construction with a temporarily mismatched scope', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); const owner = creativeClient('project', { sessionToken: 'token', scope: { projectId: 'other', workspaceId: 'w', storylineId: 's', branchId: 'b' } });
    expect(owner.list).toBeTypeOf('function'); expect(fetch).not.toHaveBeenCalled(); expect(() => owner.imageDirector()).toThrow();
  });
  it.each(['actor', 'scope', 'image', 'model', 'target', 'called'] as const)('rejects mismatched %s preview before rendering any advice', async mutation => {
    const wire = structuredClone(imagePreviewWire);
    if (mutation === 'actor') wire.preview.source.actor_id = 'other';
    if (mutation === 'scope') wire.preview.source.scope.novel_id = 'other';
    if (mutation === 'image') wire.preview.source.asset.sha256 = '9'.repeat(64);
    if (mutation === 'model') wire.preview.model_id = 'text-only';
    if (mutation === 'target') wire.preview.target.version += 1;
    if (mutation === 'called') wire.model_called = true;
    await expect(setup(wire).client.preview(previewInput)).rejects.toMatchObject({ problem: { code: 'DIRECTOR_IMAGE_RESPONSE_INVALID' } });
  });
  it('rejects content in metadata status and never retries a failed dispatch', async () => {
    const { client, json } = setup({ ...imageStatusWire, advice: { private: 'never return this' } }); await expect(client.status('proposal')).rejects.toThrow();
    json.mockRejectedValueOnce(new Error('lost')); await expect(client.dispatch(imagePreview)).rejects.toThrow('lost'); expect(json).toHaveBeenCalledTimes(2);
  });
  it('fails closed on review target, accounting or verified-observation changes', async () => {
    const changed = structuredClone(imageReviewWire); changed.target.scene_id = 'other'; await expect(setup(changed).client.review('proposal', imageTarget)).rejects.toThrow();
    await expect(setup({ ...imageReviewWire, observations_verified: true }).client.review('proposal', imageTarget)).rejects.toThrow();
    await expect(setup({ ...imageReviewWire, accounting: { ...imageReviewWire.accounting, cost_state: 'MEASURED' } }).client.review('proposal', imageTarget)).rejects.toThrow();
  });
  it('rejects unconfirmed declarations, blank/negative accounting, and aborted requests before POST', async () => {
    const { client, json } = setup(); const invalid = { contract: 'DIRECTOR_IMAGE_COST_DECLARATION_V3', request_id: 'req', expected_version: 7, reviewed_terminal_digest: 'd'.repeat(64), declared_microusd: '', evidence_note: 'basis', confirmed_declaration: true };
    await expect(client.declareCost('proposal', invalid as unknown as ImageCostInput)).rejects.toThrow(); await expect(client.declareCost('proposal', { ...invalid, declared_microusd: -1 } as ImageCostInput)).rejects.toThrow();
    const abort = new AbortController(); abort.abort(); await expect(client.dispatch(imagePreview, abort.signal)).rejects.toMatchObject({ name: 'AbortError' }); expect(json).not.toHaveBeenCalled();
  });
  it('keeps historical adoption metadata separate from current review content and cancellation is not stopped', async () => {
    const historical = { request_id: 'adopt', target: { ...imageTarget, version: 3 }, historical: true, committed: true };
    const { client } = setup({ items: [{ ...imageStatusWire, status: 'ADOPTED', adoption_receipt: historical }], limit: 30, truncated: false }, { job_id: 'job', state: 'CANCELLATION_REQUESTED', upstream_stopped: false });
    expect((await client.list()).items[0].adoption_receipt).toEqual(historical); await expect(client.cancel({ ...imageStatus, job_status: 'RUNNING', can_cancel: true })).resolves.toBeUndefined();
  });
});
