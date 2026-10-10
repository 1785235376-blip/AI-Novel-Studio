import { modelAdmittedRun, modelDigest, modelInputDigest } from './studioGraphModel.testFixtures';
import type { StudioGraphRun } from './studioGraphTypes';
import type { StudioGraphResultStorage, StudioGraphTextAsset, StudioGraphTextAssetOutput } from './studioGraphTextAssetTypes';
export const resultStorage = (): StudioGraphResultStorage => ({ contract: 'creative-graph-text-asset/1', available: true, owner: 'AssetLibraryService', actor_private: true, automatic_model_retry: false });
const boundary = () => ({ contract: 'creative-graph-text-asset/1' as const, actor_private: true as const, applied: false as const, quality_verification: 'NOT_RUN' as const, automatic_model_retry: false as const });
export function pendingTextAsset(state: 'PENDING' | 'INCOMPLETE' | 'NO_ACCEPTED_RESULT' = 'PENDING'): StudioGraphTextAssetOutput {
  return { ...boundary(), state, asset_id: null, version: null, ...(state === 'INCOMPLETE' ? { reason: 'ARCHIVE_RECONCILIATION_REQUIRED' } : {}) };
}
export function storedTextAsset(state: 'DRAFT' | 'APPROVED' | 'REJECTED' = 'DRAFT'): StudioGraphTextAsset {
  const output = '8df20b44e9d5e31fe59161b21884971d0fb57ce15c44a80808b6faac05ded3d2';
  return { ...boundary(), state, asset_id: 'private_text_asset', version: state === 'DRAFT' ? 1 : 2, sha256: output, size: 19, kind: 'text', media_type: 'text/plain',
    created_at: '2026-10-10T00:00:02Z', updated_at: '2026-10-10T00:00:02Z', provider_id: 'local', model_id: 'writer',
    parameters: { max_output_tokens: 512, temperature: 0, synthetic: false, quality_verification: 'NOT_RUN' },
    source: { schema_version: 1, contract: 'creative-graph-text-asset/1', graph_id: 'model_graph', graph_version: 1, graph_digest: modelDigest,
      run_id: 'model_run', source_run_version: 4, model_node_id: 'generate', job_id: 'original_job', input_digest: modelInputDigest, output_digest: output,
      preview_digest: modelDigest, produced_at: '2026-10-10T00:00:01Z' } };
}
export function storedTextAssetRun(state: 'DRAFT' | 'APPROVED' | 'REJECTED' = 'DRAFT'): StudioGraphRun {
  const run = modelAdmittedRun(); run.version = state === 'DRAFT' ? 5 : 6; run.updated_at = '2026-10-10T00:00:03Z';
  run.status = state === 'DRAFT' ? 'WAITING_APPROVAL' : state === 'APPROVED' ? 'SUCCEEDED' : 'REJECTED'; run.reviewed = state === 'APPROVED'; run.current_node_id = 'review';
  run.model_called = true; run.model_runtime!.status = state === 'DRAFT' ? 'RESULT_REVIEW' : 'TERMINAL';
  run.model_runtime!.execution!.model_called = true; run.model_runtime!.execution!.status = 'COMPLETED';
  run.node_states.generate = { status: 'SUCCEEDED', output: { draft: { text: 'Saved proposed text', origin: 'MODEL_PROPOSAL' } }, error: null };
  run.review = state === 'DRAFT' ? { node_id: 'review', output_digest: 'f'.repeat(64), draft: { text: 'Saved proposed text', origin: 'MODEL_PROPOSAL' } } : null;
  if (state === 'REJECTED') { run.model_runtime!.preview = null; for (const node of Object.values(run.node_states)) node.output = null; }
  run.asset_output = storedTextAsset(state); return run;
}
