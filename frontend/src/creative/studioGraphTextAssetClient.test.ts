import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { createStudioGraphClient } from './studioGraphClient';
import { modelAdmittedRun, modelCapabilities, modelGraph, modelPreviewRun } from './studioGraphModel.testFixtures';
import { pendingTextAsset, resultStorage, storedTextAssetRun } from './studioGraphTextAsset.testFixtures';
function setup(value: unknown) { const json = vi.fn().mockResolvedValue(value), client = createStudioGraphClient('model_project', {}, { json }); return { json, client }; }
describe('optional private graph TextAsset result contract', () => {
  it('preserves the old capabilities exactly when result storage is not advertised', async () => {
    const raw = modelCapabilities(), { client } = setup(raw); expect(await client.modelCapabilities()).toEqual(raw);
  });
  it('requires the exact original asset owner and explicit privacy/no-retry boundaries', async () => {
    const raw = { ...modelCapabilities(), result_storage: resultStorage() }, { client, json } = setup(raw); expect(await client.modelCapabilities()).toEqual(raw);
    for (const patch of [{ contract: 'other' }, { available: false }, { owner: 'NewAssetStore' }, { actor_private: false }, { automatic_model_retry: true }, { execution_available: true }]) {
      json.mockResolvedValue({ ...raw, result_storage: { ...resultStorage(), ...patch } }); await expect(client.modelCapabilities()).rejects.toBeInstanceOf(ApiError);
    }
  });
  it('adds archive_result to the same dispatch only when explicitly provided and demands an archival receipt', async () => {
    const raw = { ...modelAdmittedRun(), asset_output: pendingTextAsset() }, { client, json } = setup(raw);
    await client.dispatchModel('model_run', { expected_version: 3, reviewed_preview_digest: 'a'.repeat(64), archive_result: true });
    expect(json.mock.calls[0]).toEqual(['/api/projects/model_project/studio/graph-runs/model_run/model/dispatch', 'POST', { expected_version: 3, reviewed_preview_digest: 'a'.repeat(64), archive_result: true }]);
    json.mockResolvedValue(modelAdmittedRun()); await expect(client.dispatchModel('model_run', { expected_version: 3, reviewed_preview_digest: 'a'.repeat(64), archive_result: true })).rejects.toBeInstanceOf(ApiError);
    await client.dispatchModel('model_run', { expected_version: 3, reviewed_preview_digest: 'a'.repeat(64) }); expect(json.mock.calls[2][2]).not.toHaveProperty('archive_result');
  });
  it.each([false, 'true', 1, null])('rejects malformed archival consent %j without making a request', archive_result => {
    const { client, json } = setup(modelAdmittedRun()); expect(() => client.dispatchModel('model_run', { expected_version: 3, reviewed_preview_digest: 'a'.repeat(64), archive_result } as never)).toThrow(ApiError); expect(json).not.toHaveBeenCalled();
  });
  it.each(['DRAFT', 'APPROVED', 'REJECTED'] as const)('accepts a scoped, bound %s asset receipt without publishing or exporting', async state => {
    const raw = storedTextAssetRun(state), { client, json } = setup(raw); expect((await client.getRun('model_run')).asset_output).toEqual(raw.asset_output);
    expect(json.mock.calls).toEqual([['/api/projects/model_project/studio/graph-runs/model_run', 'GET', undefined, undefined]]);
  });
  it('compares the source graph digest to the previously observed exact graph version', async () => {
    const { client, json } = setup(modelGraph()); await client.get('model_graph'); const raw = storedTextAssetRun(); json.mockResolvedValue(raw); expect((await client.getRun(raw.id)).asset_output).toEqual(raw.asset_output);
    (raw.asset_output as any).source.graph_digest = 'b'.repeat(64); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each([
    (x: any) => { x.asset_output.contract = 'other'; }, (x: any) => { x.asset_output.actor_private = false; },
    (x: any) => { x.asset_output.applied = true; }, (x: any) => { x.asset_output.automatic_model_retry = true; },
    (x: any) => { x.asset_output.quality_verification = 'PASSED'; }, (x: any) => { x.asset_output.execution_available = true; },
    (x: any) => { x.asset_output.state = 'PUBLISHED'; }, (x: any) => { x.asset_output.state = 'APPROVED'; },
    (x: any) => { x.asset_output.state = 'REJECTED'; }, (x: any) => { x.asset_output.version = 0; },
    (x: any) => { x.asset_output.asset_id = null; }, (x: any) => { x.asset_output.sha256 = 'wrong'; },
    (x: any) => { x.asset_output.size = 20; }, (x: any) => { x.asset_output.size = 32001; },
    (x: any) => { x.asset_output.kind = 'image'; }, (x: any) => { x.asset_output.media_type = 'text/html'; },
    (x: any) => { x.asset_output.provider_id = 'other'; }, (x: any) => { x.asset_output.model_id = 'other'; },
    (x: any) => { x.asset_output.created_at = '2026-10-09T00:00:00Z'; }, (x: any) => { x.asset_output.updated_at = 'invalid'; },
    (x: any) => { x.asset_output.parameters.temperature = 1; }, (x: any) => { x.asset_output.parameters.synthetic = true; },
    (x: any) => { x.asset_output.parameters.max_output_tokens = 511; }, (x: any) => { x.asset_output.parameters.quality_verification = 'PASSED'; },
    (x: any) => { x.asset_output.parameters.future_authority = true; }, (x: any) => { x.asset_output.source.schema_version = 2; },
    (x: any) => { x.asset_output.source.graph_id = 'other'; }, (x: any) => { x.asset_output.source.graph_version = 2; },
    (x: any) => { x.asset_output.source.run_id = 'other'; }, (x: any) => { x.asset_output.source.source_run_version = 6; },
    (x: any) => { x.asset_output.source.model_node_id = 'review'; }, (x: any) => { x.asset_output.source.job_id = 'other'; },
    (x: any) => { x.asset_output.source.input_digest = 'c'.repeat(64); }, (x: any) => { x.asset_output.source.output_digest = 'b'.repeat(64); },
    (x: any) => { x.asset_output.source.preview_digest = 'c'.repeat(64); }, (x: any) => { x.asset_output.source.produced_at = 'invalid'; },
    (x: any) => { x.asset_output.source.scope = { branch: 'other' }; }, (x: any) => { x.model_runtime.execution.status = 'RUNNING'; },
    (x: any) => { x.stale = true; },
  ])('fails closed on malformed, cross-source or authoritative HTTP-200 asset metadata %j', async mutate => {
    const raw = storedTextAssetRun(); mutate(raw); const { client } = setup(raw); await expect(client.getRun('model_run')).rejects.toBeInstanceOf(ApiError);
  });
  it('requires incomplete storage to mask output and keeps the original reload route', async () => {
    const raw = storedTextAssetRun(); raw.asset_output = pendingTextAsset('INCOMPLETE'); raw.stale = true;
    const { client, json } = setup(raw), result = await client.getRun('model_run');
    expect(result.asset_output?.state).toBe('INCOMPLETE'); expect(result.review).toBeNull(); expect(result.model_runtime?.preview).toBeNull(); expect(Object.values(result.node_states).every(node => node.output === null)).toBe(true);
    json.mockResolvedValue({ ...raw, stale: false }); await expect(client.getRun('model_run')).rejects.toBeInstanceOf(ApiError);
  });
  it('accepts NO_ACCEPTED_RESULT only for failed or cancelled runs', async () => {
    const raw = modelAdmittedRun(); raw.asset_output = pendingTextAsset('NO_ACCEPTED_RESULT'); raw.status = 'CANCELLED'; raw.model_runtime!.status = 'TERMINAL';
    const { client, json } = setup(raw); expect((await client.getRun(raw.id)).asset_output?.state).toBe('NO_ACCEPTED_RESULT');
    json.mockResolvedValue({ ...raw, status: 'RUNNING' }); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
  it('rejects an asset projection before an original model execution exists', async () => {
    const raw = { ...modelPreviewRun(), asset_output: pendingTextAsset() }, { client } = setup(raw); await expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each([{ asset_id: 'leak' }, { version: 1 }, { sha256: 'a'.repeat(64) }, { reason: 'unrequested' }])('rejects metadata hidden inside a pending asset %j', patch => {
    const raw = { ...modelAdmittedRun(), asset_output: { ...pendingTextAsset(), ...patch } }, { client } = setup(raw); return expect(client.getRun(raw.id)).rejects.toBeInstanceOf(ApiError);
  });
});
