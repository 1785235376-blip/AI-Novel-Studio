import { createHash } from 'node:crypto';
import { modelCapabilities, modelPreviewRun } from './studioGraphModel.testFixtures';
import { storedTextAssetRun } from './studioGraphTextAsset.testFixtures';
import type { StudioGraphTextAsset, StudioGraphTextExecutionReceipt } from './studioGraphTextAssetTypes';

/** Additive fixtures: original v1 fixtures remain unchanged. */
export function textExecutionReceiptRun(state: 'DRAFT' | 'APPROVED' | 'REJECTED' = 'DRAFT', synthetic = false) {
  const run = storedTextAssetRun(state), asset = run.asset_output as StudioGraphTextAsset;
  const route = modelCapabilities().routes[synthetic ? 1 : 0];
  asset.provider_id = route.provider_id; asset.model_id = route.model_id; asset.parameters.synthetic = synthetic;
  run.model_runtime!.execution!.synthetic = synthetic;
  if (run.model_runtime!.preview) run.model_runtime!.preview.route = { route_id: route.route_id, provider_id: route.provider_id,
    model_id: route.model_id, synthetic, verification: route.verification };
  const prompt = run.model_runtime!.preview?.prompt ?? modelPreviewRun().model_runtime!.preview!.prompt;
  const receipt: StudioGraphTextExecutionReceipt = {
    schema_version: 1, contract: 'creative-graph-text-execution/1', prompt, prompt_sha256: createHash('sha256').update(prompt).digest('hex'),
    provider_id: asset.provider_id, model_id: asset.model_id, route_id: route.route_id, route_fingerprint: '1'.repeat(64),
    model_evidence: { kind: synthetic ? 'SYNTHETIC_PROTOCOL' : 'MODEL_CENTER_METADATA',
      model_fingerprint: synthetic ? 'synthetic-protocol-v1' : '2'.repeat(64), runtime_fingerprint: synthetic ? null : '3'.repeat(64), runtime_version: synthetic ? null : 'local-runtime-v1' },
    parameters: { temperature: 0, max_output_tokens: asset.parameters.max_output_tokens, stop_sequences: [] },
    execution_mode: synthetic ? 'mock_standin' : 'real', request_digest: '4'.repeat(64), workflow: { ...asset.source },
    terminal: { status: 'COMPLETED', settlement_id: 'original_settlement', settled_at: asset.source.produced_at }, quality_verification: 'NOT_RUN',
  };
  asset.execution_receipt = receipt;
  return { run, asset, receipt };
}
