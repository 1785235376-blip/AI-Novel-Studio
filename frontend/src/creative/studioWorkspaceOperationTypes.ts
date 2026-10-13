/** Read-only operation descriptions. These are not tasks, executable nodes or grants. */
export const STUDIO_PRODUCTION_STAGES = ['M4', 'M5', 'M6', 'M7', 'M8', 'M9'] as const;
export type StudioProductionStageId = typeof STUDIO_PRODUCTION_STAGES[number];
export const STUDIO_PRODUCTION_STAGE_LABELS: Record<StudioProductionStageId, string> = {
  M4: '文字与执行', M5: '图片', M6: '导演与分镜', M7: '视频', M8: '声音', M9: '剪辑',
};
export const STUDIO_PRODUCTION_OPERATION_IDS = [
  'm4.text.generate',
  'm5.image.generate', 'm5.image.edit', 'm5.image.t2i', 'm5.image.i2i', 'm5.image.cutout',
  'm6.director.propose', 'm6.director.model', 'm6.storyboard.derive',
  'm7.video.plan', 'm7.video.generate', 'm7.video.t2v', 'm7.video.i2v', 'm7.video.v2v',
  'm8.audio.speech', 'm8.audio.import', 'm8.audio.music', 'm8.audio.effects', 'm8.audio.trim',
  'm9.video.assemble', 'm9.timeline.exchange', 'm9.subtitle.edit', 'm9.timeline.multitrack',
] as const;
export type StudioProductionOperationId = typeof STUDIO_PRODUCTION_OPERATION_IDS[number];
export type StudioProductionScope = {
  mode: 'local' | 'collaboration'; novel_id: string;
  workspace_id?: string | null; project_id?: string | null;
  storyline_id?: string | null; branch_id?: string | null;
};
export type StudioProductionOwner = { module: string; class_name: string; methods: string[] };
export const STUDIO_PRODUCTION_INTERFACE_KEYS = [
  'source-snapshot/1', 'provider-reference/1', 'rights-requirements/1', 'timing-requirements/1',
  'track-requirements/1', 'operation-intent/1', 'media-result/1',
] as const;
export type StudioProductionInterfaceKey = typeof STUDIO_PRODUCTION_INTERFACE_KEYS[number];
export type StudioSchemaValue = string | number | boolean | null | StudioSchemaValue[] | { [key: string]: StudioSchemaValue };
export type StudioInterfaceSchema = { [key: string]: StudioSchemaValue };
export const STUDIO_PRODUCTION_INTERFACE_REFERENCES = {
  source_snapshot: 'source-snapshot/1', intent: 'operation-intent/1', result: 'media-result/1',
  rights: 'rights-requirements/1', timing: 'timing-requirements/1', tracks: 'track-requirements/1',
} as const;
export type StudioProductionInterfaceReferences = typeof STUDIO_PRODUCTION_INTERFACE_REFERENCES;
export type StudioProductionActionContract = {
  id: string; method: 'GET' | 'POST' | 'PUT' | 'DELETE'; path: string;
  permission: 'domain.read' | 'domain.write' | 'domain.review';
  input_schema: string | null; owner_method: string;
  requires_original_host_session: boolean; execution_grant: false; conditions: string[];
};
export type StudioProductionOperation = {
  id: StudioProductionOperationId; milestone: StudioProductionStageId; title: string;
  capability_status: 'EXISTING_OWNER_CONTRACT' | 'RESERVED_INTERFACE';
  acceptance_status: 'LOCAL_REQUIRED'; acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT';
  execution_available: false; blocked_reasons: string[];
  owner: StudioProductionOwner | null; actions: StudioProductionActionContract[];
  input_requirements: string[]; source_requirements: string[]; output_requirements: string[];
  review_requirements: string[]; limitations: string[]; interface_contracts: StudioProductionInterfaceReferences;
};
export type StudioWorkspaceProductionContracts = {
  schema_version: 1; contract: 'studio-production-operation-contracts/1';
  project_id: string; scope: StudioProductionScope; studio_entry_kind: 'NEUTRAL_STUDIO';
  advisory_only: true; execution_authority: false;
  acceptance_sequence: StudioProductionStageId[];
  acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT'; operations: StudioProductionOperation[];
  interface_schemas: Record<StudioProductionInterfaceKey, StudioInterfaceSchema>;
};
/** Data-surface states only; original owners retain every execution state transition. */
export type StudioOperationSurfaceState = 'IDLE' | 'LOADING' | 'READY' | 'EMPTY' | 'ERROR' | 'UNAVAILABLE' | 'DENIED';
export type StudioOperationReadProblem = { code: string; message: string };
export type StudioOperationStageProjection = {
  id: StudioProductionStageId; label: string; operations: StudioProductionOperation[];
  execution_available: false; acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT';
};
