import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { createDirectorObservationClient } from './directorObservationClient';
import captured from './directorObservationWire.testFixture.json';

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const project = captured.preview.project_id;
function setup(value: unknown) {
  const json = vi.fn().mockResolvedValue(value);
  return { json, client: createDirectorObservationClient(project, { json }) };
}

describe('staged Director observation client uses actual captured owner receipts', () => {
  it.each(['preview', 'completed', 'pending', 'adopted_status'] as const)('decodes captured %s using GET only', async key => {
    const value = captured[key], { json, client } = setup(value), signal = new AbortController().signal;
    expect(await client.readStatus(value.receipt.proposal_id, signal)).toEqual(value.receipt);
    expect(json.mock.calls).toEqual([[`/api/novels/${encodeURIComponent(project)}/experimental/creative/director-proposals/${value.receipt.proposal_id}/model-v1/status`, 'GET', undefined, signal]]);
  });

  it('reads only the exact adopted draft receipt and returns detached data', async () => {
    const value = clone(captured.adopted), { json, client } = setup(value);
    const receipt = await client.readAdoptedDraft(value.receipt.proposal_id);
    expect(receipt).toEqual(value.receipt);
    receipt.document.version++;
    expect(value.receipt.document.version).toBe(captured.adopted.receipt.document.version);
    expect(json.mock.calls[0][0]).toMatch(/\/model-v1\/adopted-draft$/);
    expect(json.mock.calls[0][1]).toBe('GET'); expect(json).toHaveBeenCalledTimes(1);
  });

  it.each(['contract', 'kind', 'project', 'scope', 'extra-envelope', 'extra-receipt', 'missing', 'proposal',
    'unsafe-version', 'automatic-retry', 'upstream-guarantee', 'preview-job', 'preview-settlement'] as const)('rejects invalid %s without fallback', async change => {
    const value: any = clone(captured.preview);
    if (change === 'contract') value.contract = 'future';
    if (change === 'kind') value.kind = 'adopted-draft';
    if (change === 'project') value.project_id = 'foreign';
    if (change === 'scope') value.scope.branch_id = 'foreign';
    if (change === 'extra-envelope') value.private_prompt = 'secret';
    if (change === 'extra-receipt') value.receipt.raw_job = {};
    if (change === 'missing') delete value.receipt.adoption;
    if (change === 'proposal') value.receipt.proposal_id = 'foreign';
    if (change === 'unsafe-version') value.receipt.version = Number.MAX_SAFE_INTEGER + 1;
    if (change === 'automatic-retry') value.receipt.automatic_retry = true;
    if (change === 'upstream-guarantee') value.receipt.upstream_cancellation_guaranteed = true;
    if (change === 'preview-job') value.receipt.job_id = 'fabricated';
    if (change === 'preview-settlement') value.receipt.settlement_state = 'SETTLED';
    const { json, client } = setup(value);
    await expect(client.readStatus(captured.preview.receipt.proposal_id)).rejects.toBeInstanceOf(ApiError);
    expect(json).toHaveBeenCalledTimes(1);
  });

  it.each(['document-status', 'document-mode', 'document-extra', 'version-gap', 'digest', 'missing-adoption', 'job-mismatch', 'terminal-mismatch'] as const)('refuses invalid adoption %s', async change => {
    const value: any = clone(captured.adopted_status), receipt = value.receipt.adoption;
    if (change === 'document-status') receipt.document.status = 'APPROVED';
    if (change === 'document-mode') receipt.document.mode = 'STORYBOARD';
    if (change === 'document-extra') receipt.document.content = 'private';
    if (change === 'version-gap') receipt.approved_version++;
    if (change === 'digest') receipt.document.digest = 'bad';
    if (change === 'missing-adoption') value.receipt.adoption = null;
    if (change === 'job-mismatch') receipt.job_id = 'foreign';
    if (change === 'terminal-mismatch') receipt.terminal_evidence_digest = '0'.repeat(64);
    const { client } = setup(value);
    await expect(client.readStatus(value.receipt.proposal_id)).rejects.toBeInstanceOf(ApiError);
  });

  it('retains UNKNOWN_UPSTREAM after local cancellation and refuses fabricated confirmation', async () => {
    const value: any = clone(captured.completed);
    Object.assign(value.receipt, { phase: 'CANCELLED', cancellation_requested: true, cancellation_confirmed: false,
      settlement_state: 'UNKNOWN_UPSTREAM', dispatch_state: 'DISPATCHED', terminal_evidence_digest: null });
    const { client } = setup(value);
    expect((await client.readStatus(value.receipt.proposal_id)).cancellation_confirmed).toBe(false);
    value.receipt.cancellation_confirmed = true;
    await expect(client.readStatus(value.receipt.proposal_id)).rejects.toBeInstanceOf(ApiError);
  });

  it('captures the collaboration scope rather than a later mutable navigation object', async () => {
    const scope = { projectId: project, workspaceId: 'w', storylineId: 's', branchId: 'b' };
    const value = { ...clone(captured.preview), scope: { mode: 'collaboration', novel_id: project, workspace_id: 'w', storyline_id: 's', branch_id: 'b' } };
    const json = vi.fn().mockResolvedValue(value), client = createDirectorObservationClient(project, { json }, scope);
    scope.branchId = 'new';
    expect((await client.readStatus(value.receipt.proposal_id)).phase).toBe('PREVIEW');
    value.scope.branch_id = 'new';
    await expect(client.readStatus(value.receipt.proposal_id)).rejects.toMatchObject({ problem: { code: 'DIRECTOR_OBSERVATION_SCOPE_MISMATCH' } });
  });

  it('drops an aborted response even if transport ignores cancellation', async () => {
    const controller = new AbortController(), { client, json } = setup(captured.preview);
    const request = client.readStatus(captured.preview.receipt.proposal_id, controller.signal);
    controller.abort();
    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
    expect(json).toHaveBeenCalledTimes(1);
  });

  it('preserves a transport denial without any retry or alternate request', async () => {
    const denied = new ApiError({ status: 403, code: 'DENIED', message: 'Denied' });
    const json = vi.fn().mockRejectedValue(denied), client = createDirectorObservationClient(project, { json });
    await expect(client.readStatus(captured.preview.receipt.proposal_id)).rejects.toBe(denied);
    expect(json).toHaveBeenCalledTimes(1);
  });
});
