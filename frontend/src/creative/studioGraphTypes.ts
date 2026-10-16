import type { StoryboardShot } from './studioStoryboardContract';
import type { PlanningSnapshot, PlanningProjection } from './studioProductionGraphContract';
import type { ImageReferencePurpose } from './studioImageRuntimeContract';
import type { StudioGraphResultStorage, StudioGraphTextAssetOutput } from './studioGraphTextAssetTypes';
import type { ProductionJob, ProductionPreview, RecordedMediaCommand } from './studioProductionClient';
import type { GraphTimelineBinding, GraphTimelineCommand, GraphTimelineEdit, GraphTimelineSnapshot } from './studioGraphTimelineContract';
import type { TimelineExportProfile } from './studioTimelineExportTypes';
export const GRAPH_MEDIA_OPERATIONS = ['m5.image.t2i', 'm5.image.i2i', 'm7.video.t2v', 'm7.video.i2v', 'm7.video.v2v',
  'm8.audio.speech', 'm8.audio.music', 'm8.audio.effects', 'm8.audio.trim'] as const;
export type GraphMediaOperation = typeof GRAPH_MEDIA_OPERATIONS[number];
export const GRAPH_IMAGE_OPERATIONS = ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'] as const;
export type GraphImageOperation = typeof GRAPH_IMAGE_OPERATIONS[number];
export const GRAPH_VIDEO_OPERATIONS = ['m7.video.t2v', 'm7.video.i2v', 'm7.video.v2v'] as const;
export type GraphVideoOperation = typeof GRAPH_VIDEO_OPERATIONS[number];
export type GraphUpscaleOperation = 'm5.image.upscale';
/** Finite, code-owned contracts. A catalog entry cannot register executable code. */
export type StudioGraphDefinitionId = 'text_input' | 'text_reference' | 'draft_prepare'
  | 'manual_transform' | 'director_note' | 'human_review' | 'asset_reference' | 'text_generate' | 'media_generate' | 'media_review' | 'timeline_export'
  | 'image_reference' | 'image_prompt' | 'image_generate' | 'image_style' | 'image_upscale' | 'director_plan' | 'storyboard_plan' | 'storyboard_prompt' | 'storyboard_shot' | 'video_generate';
export type StudioGraphPortType = 'TEXT' | 'DIRECTOR_NOTES' | 'DRAFT' | 'ASSET_REF' | 'MEDIA_CANDIDATE' | 'IMAGE_REFERENCES' | 'IMAGE_PROMPT' | 'DIRECTOR_PLAN' | 'STORYBOARD_DATA' | 'STORYBOARD_SHOT' | 'VIDEO_CANDIDATE';
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
  operation_id?: GraphMediaOperation | GraphImageOperation | GraphUpscaleOperation;
  style?: string; atmosphere?: string; color_palette?: string; document_snapshot?: PlanningSnapshot; shot_id?: string; shot_version?: number; shot_digest?: string; reference_purpose?: 'style' | 'action' | 'camera'; bind_shot?: true;
  bindings?: { port: 'source_1' | 'source_2' | 'source_3' | 'source_4' | 'source_5'; weight: number; purpose?: ImageReferencePurpose; source_note?: string }[];
  provider_id?: string | null;
  model_id?: string | null;
  prompt?: string;
  parameters?: Record<string, string | number | null>;
  allow_cloud?: boolean;
  license_note?: string;
  timeline_snapshot?: GraphTimelineSnapshot;
  edit_operations?: GraphTimelineEdit[];
  source_bindings?: GraphTimelineBinding[];
  export_profile?: TimelineExportProfile;
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
  schema_version: 1 | 2 | 3 | 4 | 5;
  title: string;
  nodes: StudioGraphNode[];
  edges: StudioGraphEdge[];
  viewport: StudioGraphViewport;
  /** Optional display-only annotation and disjoint visual groups; excluded from execution projection. */
  presentation?: { view?: StudioGraphViewPreferences; comment?: string; groups?: { id: string; name: string; node_ids: string[]; parent_id?: string }[] };
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
    type: 'string' | 'integer' | 'object' | 'boolean' | 'array';
    title?: string;
    default?: string | number | boolean | Record<string, string | number | null> | null;
    minLength?: number;
    maxLength?: number;
    minimum?: number;
    maximum?: number;
    pattern?: string;
    const?: true;
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
  media_limits?: { nodes: 24; generators: 4; history: 80 };
  capabilities: {
    local_execution: true;
    chapter_required: false;
    model_execution: boolean;
    model_execution_contract?: 'creative-graph-model/1';
    media_execution?: boolean;
    media_execution_contract?: 'creative-graph-media/1';
    timeline_execution?: boolean;
    timeline_evidence?: 'LOCAL_REQUIRED';
    automatic_timeline_dispatch?: false;
    image_graph?: true;
    image_graph_schema_version?: 4;
    image_graph_evidence?: 'LOCAL_REQUIRED';
    image_reference_semantics?: 'WEIGHTED_PIXEL_INITIALIZATION';
    image_upscale_execution?: boolean;
    production_graph?: true; production_graph_schema_version?: 4; planning_evidence?: 'SOURCE_BOUND'; image_control_execution?: false;
    video_graph?: true; video_graph_schema_version?: 5; video_graph_evidence?: 'LOCAL_REQUIRED'; storyboard_video_approval_required?: true; automatic_video_dispatch?: false;
    external_reference_execution: boolean;
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
export type StudioGraphAssetRef = { asset_id: string; version: number; digest: string; kind: 'image' | 'video' | 'audio' };
export type StudioGraphImageReference = { asset: StudioGraphAssetRef & { kind: 'image' }; weight: number; purpose?: ImageReferencePurpose; source_note?: string };
export type StudioGraphImagePrompt = { prompt: string; references: StudioGraphImageReference[]; document_sources?: RecordedMediaCommand['source_snapshots'] };
export type StudioGraphMediaCandidate = { owner: 'image' | 'video' | 'audio' | 'timeline'; job_id: string; job_version: number; request_digest: string; asset: StudioGraphAssetRef };
export type StudioGraphOutput = { text?: string; direction?: StudioGraphDirection | PlanningProjection; storyboard?: PlanningProjection; shot?: StoryboardShot & { document_snapshot: PlanningSnapshot; approved: boolean }; draft?: StudioGraphDraft; reviewed_draft?: StudioGraphDraft; asset?: StudioGraphAssetRef; candidate?: StudioGraphMediaCandidate;
  references?: StudioGraphImageReference[]; prompt?: StudioGraphImagePrompt };
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
  media_runtime?: StudioGraphMediaRuntime;
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

/** Media receipts remain attached to the original run and original production owner. */
export type StudioGraphMediaNodeRuntime = {
  node_id: string; status: string; preview: StudioGraphMediaPreview | null; execution: StudioGraphMediaExecution | null;
};
export type GraphTimelineProductionPreview = Omit<ProductionPreview, 'command' | 'operation_id' | 'provider' | 'sources'> & {
  operation_id: 'm9.timeline.multitrack'; command: GraphTimelineCommand; provider: null;
  timeline_snapshot: GraphTimelineSnapshot; source_timeline_snapshot: GraphTimelineSnapshot; export_profile: TimelineExportProfile;
  timeline_edit_proof: { request_id: string; request_digest: string; input_version: number; input_digest: string; output_digest: string } | null;
  sources: { snapshot: { id: string; kind: 'ASSET'; asset_kind: 'image' | 'video' | 'audio'; version: number; digest: string }; measured: null }[];
};
export type RecordedGraphMediaCommand = Omit<RecordedMediaCommand, 'operation_id'> & { operation_id: GraphMediaOperation | GraphImageOperation | GraphUpscaleOperation };
export type StudioGraphMediaPreview = { node_id: string; input_digest: string; preview_digest: string; command: RecordedGraphMediaCommand | GraphTimelineCommand; production_preview: ProductionPreview | GraphTimelineProductionPreview };
export type StudioGraphMediaJob = Pick<ProductionJob, 'id' | 'version' | 'status' | 'request_digest' | 'receipt_digest' | 'output_candidate' | 'approved_asset_version' | 'error_code' | 'needs_reconciliation' | 'execution_state' | 'remote_compute_may_continue'> & { cancellation_mode?: string; processing_proof?: import('./studioImageRuntimeContract').ImageUpscaleProof | null };
export type StudioGraphMediaExecution = { node_id: string; owner: 'image' | 'video' | 'audio' | 'timeline'; job_id: string | null; status: string;
  receipt_state: 'RECORDED' | 'UNKNOWN_NO_AUTOMATIC_REPLAY'; send_reserved: boolean; job: StudioGraphMediaJob | null;
  review_state?: 'NONE' | 'REVIEW_RESERVED' | 'APPROVED';
  review_recovery?: { contract: 'creative-graph-review-recovery/1'; job_version: number; request_digest: string } };
export type StudioGraphMediaRuntime = {
  schema_version: 1; contract: 'creative-graph-media/1'; nodes: StudioGraphMediaNodeRuntime[];
  automatic_retry: false; automatic_poll: false; applied: false; product_acceptance: 'LOCAL_REQUIRED';
};
export type StudioGraphMediaPreviewInput = { expected_version: number; node_id: string };
export type StudioGraphMediaDispatchInput = StudioGraphMediaPreviewInput & { reviewed_preview_digest: string };
export type StudioGraphMediaJobInput = StudioGraphMediaPreviewInput & { expected_job_version: number; expected_request_digest: string };
export type StudioGraphMediaReviewInput = StudioGraphMediaJobInput & { reviewed_output_digest: string };

export type StudioGraphViewPreferences = { show_grid: boolean; snap: boolean; grid_step: 8 | 16 | 24 | 32; show_minimap: boolean };
