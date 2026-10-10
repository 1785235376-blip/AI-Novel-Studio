import type { StudioGraphResultStorage, StudioGraphTextAssetOutput } from './studioGraphTextAssetTypes';
/** Finite, code-owned contracts. A catalog entry cannot register executable code. */
export type StudioGraphDefinitionId = 'text_input' | 'text_reference' | 'draft_prepare'
  | 'manual_transform' | 'director_note' | 'human_review' | 'asset_reference' | 'text_generate';
export type StudioGraphPortType = 'TEXT' | 'DIRECTOR_NOTES' | 'DRAFT' | 'ASSET_REF';
export type StudioGraphPort = { id: string; type: StudioGraphPortType; required: boolean; multiple: false };
export type StudioGraphPosition = { x: number; y: number };
export type StudioGraphViewport = StudioGraphPosition & { zoom: number };
/** Only parameters owned by the selected definition are sent or returned. */
export type StudioGraphParameters = {
  text?: string;
  result?: string;
  note?: string;
  instruction?: string;
  max_output_tokens?: number;
  asset_id?: string;
  version?: number;
  digest?: string;
  kind?: 'image' | 'video' | 'audio';
};
export type StudioGraphNode = {
  id: string;
  definition_id: StudioGraphDefinitionId;
  definition_version: 1;
  enabled: boolean;
  position: StudioGraphPosition;
  parameters: StudioGraphParameters;
};
export type StudioGraphEdge = {
  id: string;
  source_node_id: string;
  source_port: string;
  target_node_id: string;
  target_port: string;
};
export type StudioGraphDefinition = {
  schema_version: 1 | 2;
  title: string;
  nodes: StudioGraphNode[];
  edges: StudioGraphEdge[];
  viewport: StudioGraphViewport;
};
export type StudioGraphCreateInput = { request_id: string; expected_version: 0; definition: StudioGraphDefinition };
export type StudioGraphSaveInput = { expected_version: number; definition: StudioGraphDefinition };
export type StudioGraphPreflightInput = { expected_version: number; target_node_ids: string[] };
export type StudioGraphRunCreateInput = {
  expected_graph_version: number;
  reviewed_preflight_digest: string;
  target_node_ids: string[];
  request_id: string;
};
export type StudioGraphAction = 'execute' | 'approve' | 'reject' | 'cancel' | 'pause' | 'resume';
export type StudioGraphActionInput = {
  expected_version: number;
  node_id?: string;
  reviewed_output_digest?: string;
  note?: string;
};
export type StudioGraphParameterSchema = {
  type: 'object';
  additionalProperties: false;
  properties: Record<string, {
    type: 'string' | 'integer';
    title?: string;
    default?: string | number;
    minLength?: number;
    maxLength?: number;
    minimum?: number;
    maximum?: number;
    pattern?: string;
    enum?: string[];
  }>;
  required?: string[];
  title?: string;
};
export type StudioGraphCatalogDefinition = {
  id: StudioGraphDefinitionId;
  version: 1;
  inputs: StudioGraphPort[];
  outputs: StudioGraphPort[];
  parameters_schema: StudioGraphParameterSchema;
  default_parameters: StudioGraphParameters | null;
  executable: boolean;
  model_called: false;
  blockers: string[];
};
export type StudioGraphCatalog = {
  definitions: StudioGraphCatalogDefinition[];
  limits: { nodes: 16; edges: 40; definition_bytes: 96000; output_bytes: 64000; graphs: 25; runs: 100; history: 20; runtime_timeout_seconds: 3600; node_timeout_seconds: 5 };
  capabilities: {
    local_execution: true;
    chapter_required: false;
    model_execution: boolean;
    model_execution_contract?: 'creative-graph-model/1';
    external_reference_execution: false;
    external_reference_detach: false;
    binary_cache: false;
    parallel_execution: false;
    automatic_retry: false;
    actor_private: true;
    cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY';
  };
};
export type StudioGraphScope = { mode: 'local'; novel_id: string }
  | { mode: 'collaboration'; novel_id: string; workspace_id: string; storyline_id: string; branch_id: string };
export type StudioGraphOwner = { project_id: string; scope: StudioGraphScope };
export type StudioGraphReferenceState = { node_id: string; state: 'CURRENT' | 'STALE' | 'UNAVAILABLE' };
export type StudioGraphRecord = StudioGraphOwner & {
  id: string;
  version: number;
  definition: StudioGraphDefinition;
  definition_digest: string;
  execution_digest: string;
  created_at: string;
  updated_at: string;
  can_edit: boolean;
  reference_states: StudioGraphReferenceState[];
};
export type StudioGraphIssue = { code: string; node_id?: string };
export type StudioGraphPreflight = StudioGraphOwner & {
  graph_id: string;
  valid: true;
  executable: boolean;
  issues: StudioGraphIssue[];
  execution_order: string[];
  selected_closure: string[];
  definition_digest: string;
  preflight_digest: string;
  expected_version: number;
  target_node_ids: string[];
  model_called: false;
  external_calls: 0;
};
export type StudioGraphRunStatus = 'QUEUED' | 'RUNNING' | 'WAITING_APPROVAL' | 'PAUSED'
  | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'REJECTED';
export type StudioGraphDirection = { note: string };
export type StudioGraphDraft = {
  text: string;
  origin: 'USER_SUPPLIED' | 'MANUAL' | 'MODEL_PROPOSAL';
  plan?: { sequence: number; beat: string }[];
  direction?: StudioGraphDirection;
};
export type StudioGraphOutput = { text?: string; direction?: StudioGraphDirection; draft?: StudioGraphDraft };
export type StudioGraphNodeStatus = 'PENDING' | 'WAITING_APPROVAL' | 'QUEUED' | 'WORKING'
  | 'SUCCEEDED' | 'FAILED' | 'SKIPPED' | 'REJECTED';
export type StudioGraphNodeState = {
  status: StudioGraphNodeStatus;
  output: StudioGraphOutput | null;
  error: { code: string } | null;
};
export type StudioGraphRun = StudioGraphOwner & {
  id: string;
  version: number;
  graph_id: string;
  graph_version: number;
  status: StudioGraphRunStatus;
  current_node_id: string | null;
  node_states: Record<string, StudioGraphNodeState>;
  review: { node_id: string; output_digest: string; draft: StudioGraphDraft } | null;
  cache: { hits: number; misses: number; mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' };
  created_at: string;
  updated_at: string;
  model_called: boolean;
  model_runtime?: StudioGraphModelRuntime;
  asset_output?: StudioGraphTextAssetOutput;
  external_calls: 0;
  applied: false;
  stale: boolean;
  reviewed: boolean;
  timeout_seconds: 3600;
  deadline_at: string;
};

export type StudioGraphModelRoute = {
  route_id: string; provider_id: string; model_id: string; display_name: string;
  available: boolean; synthetic: boolean; context_window: number | null; verification: string; reasons: string[];
};
export type StudioGraphModelCapabilities = StudioGraphOwner & {
  schema_version: 1; contract: 'creative-graph-model/1'; adapter_owner: 'TextModelNode'; router_owner: 'ModelBroker';
  scheduler_owner: 'JobManager+WorkflowRun'; local_only: true; automatic_fallback: false;
  api_provider: { status: 'RESERVED'; execution_available: false; reason: 'API_PROVIDER_EXECUTION_NOT_ENABLED' };
  limits: { model_nodes: 1; max_output_tokens: 2048; timeout_seconds: 180 };
  result_storage?: StudioGraphResultStorage;
  routes: StudioGraphModelRoute[]; quality_verification: 'NOT_RUN';
};
export type StudioGraphModelPreview = {
  preview_digest: string; node_id: string; input_digest: string; prompt: string;
  route: Pick<StudioGraphModelRoute, 'route_id' | 'provider_id' | 'model_id' | 'synthetic' | 'verification'> | null;
  execution_available: boolean; reasons: string[];
  limits: { max_output_bytes: 32000; max_output_tokens: number; timeout_seconds: 180 };
  model_called: false; quality_verification: 'NOT_RUN';
};
export type StudioGraphModelExecution = {
  job_id: string; status: string; receipt_state: 'RECORDED' | 'UNKNOWN_NO_AUTOMATIC_REPLAY'; model_called: boolean;
  synthetic: boolean; usage_state: string; failure_code: string | null; quality_verification: 'NOT_RUN';
};
export type StudioGraphModelRuntime = {
  schema_version: 1; contract: 'creative-graph-model/1'; node_id: string;
  status: 'PENDING' | 'AWAITING_PREVIEW' | 'PREVIEWED' | 'ADMITTED' | 'UNKNOWN' | 'RESULT_REVIEW' | 'TERMINAL';
  preview: StudioGraphModelPreview | null; execution: StudioGraphModelExecution | null;
  quality_verification: 'NOT_RUN'; automatic_retry: false; applied: false;
};
export type StudioGraphModelPreviewInput = { expected_version: number; route_id: string; allow_synthetic: boolean };
export type StudioGraphModelDispatchInput = { expected_version: number; reviewed_preview_digest: string; archive_result?: true };
export type StudioGraphModelRefreshInput = { expected_version: number };
