import { createHash } from 'node:crypto';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { createStudioGraphClient } from './studioGraphClient';
import { modelAdmittedRun } from './studioGraphModel.testFixtures';
import { pendingTextAsset, storedTextAssetRun } from './studioGraphTextAsset.testFixtures';
import { textExecutionReceiptRun } from './studioGraphTextExecutionReceipt.testFixtures';

function client(value: unknown) {
  const json = vi.fn().mockResolvedValue(value);
  return { json, api: createStudioGraphClient('model_project', {}, { json }) };
}

describe('additive completed TextAsset execution receipt', () => {
  it.each(['DRAFT', 'APPROVED', 'REJECTED'] as const)('keeps legacy %s receipts exactly unchanged when execution evidence is omitted', async state => {
    const raw = storedTextAssetRun(state), { api } = client(raw), result = await api.getRun(raw.id);
    expect(result.asset_output).toEqual(raw.asset_output);
    expect(result.asset_output).not.toHaveProperty('execution_receipt');
  });
  it.each(['DRAFT', 'APPROVED', 'REJECTED'] as const)('accepts an exact real %s execution receipt on the existing read', async state => {
    const { run, asset } = textExecutionReceiptRun(state), { api, json } = client(run);
    expect((await api.getRun(run.id)).asset_output).toEqual(asset);
    expect(json.mock.calls).toEqual([['/api/projects/model_project/studio/graph-runs/model_run', 'GET', undefined, undefined]]);
  });
  it('accepts synthetic protocol evidence only as a mock stand-in', async () => {
    const { run, receipt } = textExecutionReceiptRun('DRAFT', true), { api } = client(run);
    receipt.model_evidence.runtime_version = 'python-3.12.1';
    const result = await api.getRun(run.id);
    expect(result.asset_output).toHaveProperty('execution_receipt', receipt);
    expect(receipt.execution_mode).toBe('mock_standin'); expect(receipt.model_evidence.runtime_fingerprint).toBeNull();
  });
  it('preserves exact multiline Unicode input, whitespace, and a 32000-byte prompt', async () => {
    for (const prompt of ['  继续写作 🌊\n第二行\r\n\t保留空白  ', '界'.repeat(10666) + 'ab']) {
      const { run, receipt } = textExecutionReceiptRun();
      receipt.prompt = prompt; receipt.prompt_sha256 = createHash('sha256').update(prompt).digest('hex');
      run.model_runtime!.preview!.prompt = prompt;
      expect((await client(run).api.getRun(run.id)).asset_output).toHaveProperty('execution_receipt.prompt', prompt);
    }
  });
  it('accepts an unavailable runtime version while retaining the required real runtime fingerprint', async () => {
    const { run, receipt } = textExecutionReceiptRun(); receipt.model_evidence.runtime_version = null;
    expect((await client(run).api.getRun(run.id)).asset_output).toHaveProperty('execution_receipt.model_evidence', receipt.model_evidence);
  });
  it('accepts UTC offset timestamps while preserving their exact representation', async () => {
    const { run, asset, receipt } = textExecutionReceiptRun();
    asset.source.produced_at = receipt.workflow.produced_at = receipt.terminal.settled_at = '2026-10-10T00:00:01.123456+00:00';
    expect((await client(run).api.getRun(run.id)).asset_output).toEqual(asset);
  });
  it.each([
    ['schema version', (r: any) => { r.schema_version = 2; }],
    ['contract', (r: any) => { r.contract = 'creative-graph-text-asset/1'; }],
    ['empty prompt', (r: any) => { r.prompt = ''; }],
    ['non-string prompt', (r: any) => { r.prompt = 1; }],
    ['changed prompt', (r: any) => { r.prompt += ' changed'; r.prompt_sha256 = createHash('sha256').update(r.prompt).digest('hex'); }],
    ['trimmed prompt', (r: any) => { r.prompt = ` ${r.prompt}`; }],
    ['prompt digest shape', (r: any) => { r.prompt_sha256 = 'not-a-digest'; }],
    ['provider binding', (r: any) => { r.provider_id = 'other'; }],
    ['model binding', (r: any) => { r.model_id = 'other'; }],
    ['route binding', (r: any) => { r.route_id = 'e'.repeat(64); }],
    ['route id shape', (r: any) => { r.route_id = 'route'; }],
    ['route fingerprint shape', (r: any) => { r.route_fingerprint = 'route'; }],
    ['real evidence kind', (r: any) => { r.model_evidence.kind = 'SYNTHETIC_PROTOCOL'; }],
    ['full-model-file claim', (r: any) => { r.model_evidence.kind = 'FULL_MODEL_FILE_SHA256'; }],
    ['synthetic model fingerprint under real mode', (r: any) => { r.model_evidence.model_fingerprint = 'synthetic-protocol-v1'; }],
    ['invalid runtime fingerprint', (r: any) => { r.model_evidence.runtime_fingerprint = 'runtime'; }],
    ['missing real runtime fingerprint', (r: any) => { r.model_evidence.runtime_fingerprint = null; }],
    ['invalid runtime version', (r: any) => { r.model_evidence.runtime_version = {}; }],
    ['unsafe runtime version', (r: any) => { r.model_evidence.runtime_version = 'v1\nclaimed'; }],
    ['temperature', (r: any) => { r.parameters.temperature = 0.5; }],
    ['token binding', (r: any) => { r.parameters.max_output_tokens = 511; }],
    ['fractional tokens', (r: any) => { r.parameters.max_output_tokens = 512.5; }],
    ['too many tokens', (r: any) => { r.parameters.max_output_tokens = 2049; }],
    ['nonempty stop list', (r: any) => { r.parameters.stop_sequences = ['stop']; }],
    ['invalid stop list', (r: any) => { r.parameters.stop_sequences = null; }],
    ['mode mismatch', (r: any) => { r.execution_mode = 'mock_standin'; }],
    ['unrecognized mode', (r: any) => { r.execution_mode = 'cloud'; }],
    ['request digest shape', (r: any) => { r.request_digest = 'request'; }],
    ['runtime status', (r: any) => { r.terminal.status = 'RUNNING'; }],
    ['empty settlement', (r: any) => { r.terminal.settlement_id = ''; }],
    ['settlement timestamp binding', (r: any) => { r.terminal.settled_at = '2026-10-10T00:00:02Z'; }],
    ['quality overclaim', (r: any) => { r.quality_verification = 'PASSED'; }],
    ['unknown receipt field', (r: any) => { r.quality_passed = true; }],
    ['unknown evidence field', (r: any) => { r.model_evidence.full_model_file_sha256 = '2'.repeat(64); }],
    ['unknown parameter', (r: any) => { r.parameters.top_p = 1; }],
    ['unknown workflow field', (r: any) => { r.workflow.branch_id = 'private'; }],
    ['unknown terminal field', (r: any) => { r.terminal.quality_passed = true; }],
    ['missing nullable evidence field', (r: any) => { delete r.model_evidence.runtime_version; }],
    ['missing receipt field', (r: any) => { delete r.request_digest; }],
  ] as const)('rejects %s rather than exposing a trusted execution receipt', async (_name, mutate) => {
    const { run, receipt } = textExecutionReceiptRun(); mutate(receipt);
    await expect(client(run).api.getRun(run.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each(Object.keys(textExecutionReceiptRun().receipt.workflow))('rejects changed workflow field %s even when other receipt fields remain valid', async key => {
    const { run, receipt } = textExecutionReceiptRun(); (receipt.workflow as unknown as Record<string, unknown>)[key] = 'different';
    await expect(client(run).api.getRun(run.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each([null, undefined, false, [], {}])('rejects present malformed execution receipts %j', async value => {
    const { run, asset } = textExecutionReceiptRun(); (asset as any).execution_receipt = value;
    await expect(client(run).api.getRun(run.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each(['PENDING', 'INCOMPLETE', 'NO_ACCEPTED_RESULT'] as const)('rejects execution receipts hidden in a %s output', async state => {
    const { receipt } = textExecutionReceiptRun(), run = modelAdmittedRun();
    run.asset_output = { ...pendingTextAsset(state), execution_receipt: receipt } as never;
    if (state === 'INCOMPLETE') run.stale = true;
    if (state === 'NO_ACCEPTED_RESULT') { run.status = 'CANCELLED'; run.model_runtime!.status = 'TERMINAL'; }
    await expect(client(run).api.getRun(run.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each([
    { execution_mode: 'real' },
    { model_evidence: { kind: 'MODEL_CENTER_METADATA', model_fingerprint: '2'.repeat(64), runtime_fingerprint: null, runtime_version: null } },
    { model_evidence: { kind: 'SYNTHETIC_PROTOCOL', model_fingerprint: '2'.repeat(64), runtime_fingerprint: null, runtime_version: null } },
    { model_evidence: { kind: 'SYNTHETIC_PROTOCOL', model_fingerprint: 'synthetic-protocol-v1', runtime_fingerprint: '3'.repeat(64), runtime_version: null } },
  ])('rejects synthetic evidence that claims a real execution or runtime fingerprint %j', async patch => {
    const { run, receipt } = textExecutionReceiptRun('DRAFT', true); Object.assign(receipt, patch);
    await expect(client(run).api.getRun(run.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each(['界'.repeat(10667), 'a'.repeat(32001), 'invalid\u0000prompt', '\ud800', '\udc00', 'a\ud800b', ' \r\n\t '])('bounds rejected-run prompt bytes and valid Unicode without an available preview', async prompt => {
    const { run, receipt } = textExecutionReceiptRun('REJECTED'); receipt.prompt = prompt;
    await expect(client(run).api.getRun(run.id)).rejects.toBeInstanceOf(ApiError);
  });
  it.each(['2026-10-10T01:00:01+01:00', '2026-02-30T00:00:01Z', '2026-10-10T00:00:01-00:00'])('rejects non-UTC or impossible settlement timestamps even when workflow matches %s', async stamp => {
    const { run, asset, receipt } = textExecutionReceiptRun();
    asset.source.produced_at = receipt.workflow.produced_at = receipt.terminal.settled_at = stamp;
    await expect(client(run).api.getRun(run.id)).rejects.toBeInstanceOf(ApiError);
  });
});
