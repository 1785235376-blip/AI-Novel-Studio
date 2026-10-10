export type StudioGraphResultStorage = { contract: 'creative-graph-text-asset/1'; available: true; owner: 'AssetLibraryService'; actor_private: true; automatic_model_retry: false };
type TextAssetBoundary = { contract: 'creative-graph-text-asset/1'; actor_private: true; applied: false; quality_verification: 'NOT_RUN'; automatic_model_retry: false };
export type StudioGraphTextAssetSource = {
  schema_version: 1; contract: 'creative-graph-text-asset/1'; graph_id: string; graph_version: number; graph_digest: string;
  run_id: string; source_run_version: number; model_node_id: string; job_id: string;
  input_digest: string; output_digest: string; preview_digest: string; produced_at: string;
};
export type StudioGraphTextExecutionReceipt = {
  schema_version: 1; contract: 'creative-graph-text-execution/1'; prompt: string; prompt_sha256: string;
  provider_id: string; model_id: string; route_id: string; route_fingerprint: string;
  model_evidence: {
    kind: 'MODEL_CENTER_METADATA' | 'SYNTHETIC_PROTOCOL'; model_fingerprint: string;
    runtime_fingerprint: string | null; runtime_version: string | null;
  };
  parameters: { temperature: 0; max_output_tokens: number; stop_sequences: [] };
  execution_mode: 'real' | 'mock_standin'; request_digest: string; workflow: StudioGraphTextAssetSource;
  terminal: { status: 'COMPLETED'; settlement_id: string; settled_at: string };
  quality_verification: 'NOT_RUN';
};
export type StudioGraphTextAsset = TextAssetBoundary & {
  state: 'DRAFT' | 'APPROVED' | 'REJECTED'; asset_id: string; version: number; sha256: string; size: number; kind: 'text'; media_type: 'text/plain';
  created_at: string; updated_at: string; provider_id: string; model_id: string;
  parameters: { max_output_tokens: number; temperature: 0; synthetic: boolean; quality_verification: 'NOT_RUN' };
  source: StudioGraphTextAssetSource;
  execution_receipt?: StudioGraphTextExecutionReceipt;
};
export type StudioGraphTextAssetOutput = StudioGraphTextAsset | TextAssetBoundary & {
  state: 'PENDING' | 'INCOMPLETE' | 'NO_ACCEPTED_RESULT'; asset_id: null; version: null; reason?: string;
};
