import {ApiError, getCollaborationContext, requestToken, type CollaborationContext} from './api';
import {useLocalHostSession} from './localHostSession';

export type LocalRuntimeType = 'OLLAMA' | 'LLAMA_CPP' | 'COMFYUI' | 'AUTOMATIC1111' | 'OPENAI_COMPATIBLE_LOCAL' | 'CUSTOM_HTTP';
export type LocalRuntimeConfiguration = {
  name: string;
  type: LocalRuntimeType;
  endpoint: string;
  model_id?: string;
  modality?: string;
  health_endpoint?: string;
  credential_required: boolean;
  management: 'EXTERNAL' | 'MANAGED';
  executable?: string;
  model_path?: string;
  context_size?: number;
  gpu_layers?: number;
  threads?: number;
  batch_size?: number;
};
export type LocalRuntime = Partial<LocalRuntimeConfiguration> & {
  id: string;
  runtime_type?: LocalRuntimeType;
  status?: string;
  running?: boolean;
  reachable?: boolean;
  version?: string | null;
  executable_exists?: boolean;
  cuda_status?: string;
  notes?: string[];
};
export type LocalModelCandidate = {
  id: string;
  display_name: string;
  model_id: string;
  family: string;
  modality: string;
  declared_capabilities: string[];
  verified_capabilities: string[];
  runtime_id: string;
  runtime_type: string;
  runtime_config?: LocalRuntimeConfiguration & {id: string};
  source: string;
  local?: boolean;
  source_locality?: 'LOCAL_VERIFIED' | 'REMOTE' | 'NOT_VERIFIED';
  model_name: string;
  local_path?: string;
  status: string;
  compatible: string;
  verified: boolean;
  validation_notes: string[];
  validated_at?: string | null;
  evidence: Record<string, unknown>;
  enable_eligible?: boolean;
  enable_blockers?: string[];
  license_required?: boolean;
  license_confirmed?: boolean;
  workflow_adapter_id?: string | null;
};
export type LocalModelRegistration = LocalModelCandidate & {enabled: boolean; candidate_id?: string};
/** Read-only evidence from the same explicitly authorized V2 scan. These
 * observations do not grant registration, compatibility, or routing authority. */
export type WorkflowPrerequisiteObservation = 'observed' | 'not_observed' | 'unknown';
export type WorkflowPrerequisiteEvidence = {
  runtime_id: string;
  adapter_id: string;
  display_name: string;
  evidence_status: 'COMPLETE' | 'UNAVAILABLE' | 'MALFORMED' | 'BOUNDED' | 'CANCELLED' | 'NOT_SCANNED';
  nodes: {node_class: string; observation: WorkflowPrerequisiteObservation}[];
  loader: {
    node_class: string; input_field: string; observation: WorkflowPrerequisiteObservation;
    advertised_count: number | null; candidate_ids: string[];
  };
  metadata_status: 'NOT_VERIFIED';
  inference_status: 'NOT_RUN';
};
export type WorkflowComponentDeclaration = {
  model_id: string;
  model_display_name: string;
  component_id: string;
  component_type: string | null;
  observation: 'unknown';
  reason: 'NO_COMPONENT_IDENTITY_EVIDENCE' | 'COMPONENT_DEFINITION_UNAVAILABLE';
  metadata_status: 'NOT_VERIFIED';
  inference_status: 'NOT_RUN';
};
export type WorkflowPrerequisiteReport = {
  schema_version: 1;
  scan_id: string;
  scan_status: 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'CANCELLED';
  definition_status: 'COMPLETE' | 'BOUNDED' | 'MALFORMED';
  workflows: WorkflowPrerequisiteEvidence[];
  components: WorkflowComponentDeclaration[];
};
export type LocalDiscoveryScan = {
  id: string;
  status: string;
  runtimes: LocalRuntime[];
  candidates: LocalModelCandidate[];
  errors: (string | {runtime_id?: string; code?: string; message?: string})[];
  started_at?: string | null;
  finished_at?: string | null;
  // Additive scan evidence: historical snapshots may not include these fields.
  environment_schema_version?: number;
  model_files?: EnvironmentModelFile[];
  roots?: AIEnvironmentReport['roots'];
  workflow_prerequisites?: WorkflowPrerequisiteReport | null;
};
export type LocalDiscoverySettings = {scan_roots: string[]; runtimes: LocalRuntime[]; include_common_model_dirs?: boolean};
export type HardwareComponentEvidence = {
  status: 'NOT_RUN' | 'NOT_FOUND' | 'COMPONENT_FOUND_NOT_VERIFIED' | 'NOT_VERIFIED';
  source: string;
  inference_verified: false;
};
export type EnvironmentModelFile = {
  id: string;
  path: string;
  name: string;
  format: 'GGUF' | 'SAFETENSORS' | 'DIFFUSERS';
  source: 'CONFIGURED' | 'COMMON';
  root: string;
  size_bytes: number;
  modified_ns: number;
  header_valid: boolean;
  family: string;
  declared_capabilities: string[];
  candidate_ids: string[];
  notes: string[];
  inference_verified: false;
};
export type VideoFileAssociation = {
  status: 'MATCHED' | 'AMBIGUOUS' | 'NOT_OBSERVED' | 'UNKNOWN'; reason: string;
  file_id: string | null; path: string | null; root: string | null; observed_file_bytes: number | null;
  size_semantics: 'WEIGHT_FILE' | 'INDEX_METADATA' | null; runtime_path_verified: false; eligibility_derived: false;
};
export type VideoModelObservation = {
  candidate_id: string; provider_id: string; model_name: string; family: string; runtime_id: string; runtime_type: string;
  registered: boolean; enabled: boolean; enable_eligible: boolean; route_state: 'REGISTERED' | 'NOT_REGISTERED' | 'UNKNOWN';
  structure_validated: boolean; structural_only: true; inference_verified: false; file_association: VideoFileAssociation;
  model_total_bytes: null; required_vram_bytes: null;
};
export type VideoFileObservation = {
  file_id: string; path: string; root: string; source: 'CONFIGURED' | 'COMMON'; format: 'GGUF' | 'SAFETENSORS' | 'DIFFUSERS';
  family: string; header_valid: boolean; observed_file_bytes: number; size_semantics: 'WEIGHT_FILE' | 'INDEX_METADATA';
  model_total_bytes: null; required_vram_bytes: null; inference_verified: false;
};
export type VideoObservationReport = {
  contract: 'local-video-observation/1'; scan_id: string | null; scan_status: 'NOT_SCANNED' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'CANCELLED';
  models: VideoModelObservation[]; files: VideoFileObservation[]; notes: string[];
  health_probed: false; credentials_read: false; automatic_runtime_start: false;
};
/** Only the additive observation is decoded here. Original transports and
 * default-off responses retain their existing compatibility contract. */
export function checkedVideoObservations(value: unknown): VideoObservationReport {
  const invalid = (): never => {throw new ApiError({status: 200, code: 'LOCAL_AI_VIDEO_OBSERVATION_INVALID', message: '视频模型观察回执不可用，请重新读取原记录。'});};
  const record = (value: unknown): Record<string, unknown> => {if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(); return value as Record<string, unknown>;};
  const closed = (value: Record<string, unknown>, keys: string[]) => {if (Object.keys(value).length !== keys.length || keys.some(key => !Object.hasOwn(value, key))) invalid();};
  const text = (value: unknown, maximum = 1024): string => {if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid(); return value as string;};
  const bytes = (value: unknown): number => {if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) invalid(); return value as number;};
  const list = (value: unknown, maximum: number): unknown[] => {if (!Array.isArray(value) || value.length > maximum) invalid(); return value as unknown[];};
  const flags = (value: Record<string, unknown>) => {if (value.model_total_bytes !== null || value.required_vram_bytes !== null || value.inference_verified !== false) invalid();};
  const row = record(value); closed(row, ['contract', 'scan_id', 'scan_status', 'models', 'files', 'notes', 'health_probed', 'credentials_read', 'automatic_runtime_start']);
  if (row.contract !== 'local-video-observation/1' || row.health_probed !== false || row.credentials_read !== false || row.automatic_runtime_start !== false
    || !['NOT_SCANNED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'CANCELLED'].includes(String(row.scan_status))) invalid();
  if (row.scan_id !== null) text(row.scan_id, 64);
  const models = list(row.models, 2048).map(value => {
    const model = record(value); closed(model, ['candidate_id', 'provider_id', 'model_name', 'family', 'runtime_id', 'runtime_type', 'registered', 'enabled', 'enable_eligible', 'route_state', 'structure_validated', 'structural_only', 'inference_verified', 'file_association', 'model_total_bytes', 'required_vram_bytes']);
    flags(model); ['candidate_id', 'provider_id', 'model_name', 'family', 'runtime_id', 'runtime_type'].forEach(key => text(model[key]));
    if (model.structural_only !== true || ['registered', 'enabled', 'enable_eligible', 'structure_validated'].some(key => typeof model[key] !== 'boolean')
      || !['REGISTERED', 'NOT_REGISTERED', 'UNKNOWN'].includes(String(model.route_state)) || model.enabled && !model.registered
      || model.route_state === 'REGISTERED' && (!model.registered || !model.enabled || !model.enable_eligible)) invalid();
    const association = record(model.file_association); closed(association, ['status', 'reason', 'file_id', 'path', 'root', 'observed_file_bytes', 'size_semantics', 'runtime_path_verified', 'eligibility_derived']);
    if (!['MATCHED', 'AMBIGUOUS', 'NOT_OBSERVED', 'UNKNOWN'].includes(String(association.status)) || association.runtime_path_verified !== false || association.eligibility_derived !== false) invalid(); text(association.reason, 100);
    if (association.status === 'MATCHED') {text(association.file_id); text(association.path, 32768); text(association.root, 32768); bytes(association.observed_file_bytes); if (association.size_semantics !== 'WEIGHT_FILE') invalid();}
    else if (['file_id', 'path', 'root', 'observed_file_bytes', 'size_semantics'].some(key => association[key] !== null)) invalid();
    return model as unknown as VideoModelObservation;
  });
  const files = list(row.files, 2000).map(value => {
    const file = record(value); closed(file, ['file_id', 'path', 'root', 'source', 'format', 'family', 'header_valid', 'observed_file_bytes', 'size_semantics', 'model_total_bytes', 'required_vram_bytes', 'inference_verified']);
    flags(file); text(file.file_id); text(file.path, 32768); text(file.root, 32768); text(file.family); bytes(file.observed_file_bytes);
    if (!['CONFIGURED', 'COMMON'].includes(String(file.source)) || !['GGUF', 'SAFETENSORS', 'DIFFUSERS'].includes(String(file.format)) || typeof file.header_valid !== 'boolean'
      || file.size_semantics !== (file.format === 'DIFFUSERS' ? 'INDEX_METADATA' : 'WEIGHT_FILE')) invalid();
    return file as unknown as VideoFileObservation;
  });
  if (new Set(models.map(model => model.candidate_id)).size !== models.length || new Set(files.map(file => file.file_id)).size !== files.length) invalid();
  list(row.notes, 16).forEach(value => text(value, 100));
  return {...row, models, files} as unknown as VideoObservationReport;
}
function checkedOptionalVideoObservation<T extends {video_observations?: VideoObservationReport}>(value: T): T {
  if (value?.video_observations === undefined) return value;
  return {...value, video_observations: checkedVideoObservations(value.video_observations)};
}
export type AIEnvironmentReport = {
  schema_version: 2;
  execution_scope: 'BACKEND_HOST';
  inference_status: 'NOT_RUN';
  windows_acceptance: 'NOT_RUN';
  scan_id: string | null;
  status: 'NOT_SCANNED' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'CANCELLED';
  started_at: string | null;
  finished_at: string | null;
  hardware: {
    platform: string;
    architecture: string;
    cpu: string;
    logical_cpu_count: number | null;
    ram_bytes: number | null;
    gpus: {vendor: string; name: string; dedicated_vram_bytes: number | null}[];
    status: string;
    notes: string[];
    cuda: HardwareComponentEvidence;
    directml: HardwareComponentEvidence;
  };
  services: {
    id: string; name: string; type: string; endpoint: string; status: string;
    version: string | null; notes: string[]; available_models: string[];
    candidate_ids: string[]; inference_verified: false;
  }[];
  model_files: EnvironmentModelFile[];
  workflow_prerequisites?: WorkflowPrerequisiteReport | null;
  video_observations?: VideoObservationReport;
  roots: {
    path: string; source: 'CONFIGURED' | 'COMMON';
    status: 'PENDING' | 'SCANNED' | 'NOT_FOUND' | 'UNREADABLE' | 'REJECTED' | 'BOUNDED' | 'CANCELLED';
  }[];
  errors: {code: string; runtime_id: string | null; root: string | null}[];
  limits: {
    scan_budget_seconds: number; request_timeout_seconds: number; max_services: number;
    max_models_per_service: number; max_response_bytes: number; max_roots: number;
    max_entries: number; max_files: number; max_depth: number; max_metadata_bytes: number;
  };
  notes: string[];
};
export type LocalDiscoverySnapshot = {
  scan: LocalDiscoveryScan | null;
  registrations: LocalModelRegistration[];
  settings: LocalDiscoverySettings;
  hardware: Record<string, unknown>;
  persistence_error?: string | null;
  workflow_adapters?: {id: string; display_name?: string; family?: string; capability?: string}[];
  video_observations?: VideoObservationReport;
};

const BASE = '/api/model-center/local-ai';
const requestId = () => globalThis.crypto?.randomUUID?.() || `local-ai-${Date.now()}-${Math.random().toString(16).slice(2)}`;

// Use the shared in-memory desktop session. Runtime credentials are never stored
// here or sent to arbitrary endpoints by the frontend.
async function call<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal, captured?: {sessionToken: string; branchId?: string}): Promise<T> {
  const headers: Record<string, string> = {'Content-Type': 'application/json', 'X-Request-ID': requestId()};
  // Legacy singleton requests capture the same in-memory owner as api.ts.
  // Captured clients already resolved their token, including an explicit empty one.
  const context = getCollaborationContext(), host = useLocalHostSession.getState();
  const contextKey = JSON.stringify(context);
  const checkCurrent = () => {
    if (signal?.aborted || (!captured && (host.epoch !== useLocalHostSession.getState().epoch
      || host.token !== useLocalHostSession.getState().token || contextKey !== JSON.stringify(getCollaborationContext())))) {
      throw new DOMException('检测会话已改变。', 'AbortError');
    }
  };
  const sessionToken = captured ? captured.sessionToken : requestToken(context, `${BASE}${path}`);
  if (sessionToken) headers['X-Session-Token'] = sessionToken;
  if (captured?.branchId) headers['X-Branch-Id'] = captured.branchId;
  if (method !== 'GET') headers['Idempotency-Key'] = requestId();
  checkCurrent();
  const response = await fetch(`${BASE}${path}`, {method, headers, signal, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  checkCurrent();
  if (!response.ok) {
    let raw: Record<string, any> = {};
    try {raw = await response.json();} catch { /* Do not echo arbitrary server output. */ }
    checkCurrent();
    const detail = raw.detail ?? raw.error ?? raw;
    const code = raw.code ?? detail?.code ?? (response.status === 401 ? 'SESSION_REQUIRED' : response.status === 403 ? 'FORBIDDEN' : 'LOCAL_AI_REQUEST_FAILED');
    throw new ApiError({status: response.status, code: typeof code === 'string' ? code : 'LOCAL_AI_REQUEST_FAILED', message: '本地 AI 操作未完成。', request_id: raw.request_id ?? response.headers.get('X-Request-ID') ?? undefined});
  }
  const result = response.status === 204 ? undefined as T : await response.json() as T;
  checkCurrent();
  return result;
}
const id = encodeURIComponent;
export const localAiDiscoveryApi = {
  environment: (signal?: AbortSignal) => call<AIEnvironmentReport>('/environment', 'GET', undefined, signal).then(checkedOptionalVideoObservation),
  snapshot: (signal?: AbortSignal) => call<LocalDiscoverySnapshot>('', 'GET', undefined, signal).then(checkedOptionalVideoObservation),
  scan: () => call<LocalDiscoveryScan>('/scan', 'POST', {}),
  scanStatus: (scanId: string, signal?: AbortSignal) => call<LocalDiscoveryScan>(`/scan/${id(scanId)}`, 'GET', undefined, signal),
  cancelScan: (scanId: string) => call<LocalDiscoveryScan>(`/scan/${id(scanId)}/cancel`, 'POST', {}),
  settings: (scan_roots: string[], include_common_model_dirs?: boolean) => call<LocalDiscoverySettings>('/settings', 'PUT', {scan_roots, ...(include_common_model_dirs === undefined ? {} : {include_common_model_dirs})}),
  saveRuntime: (body: LocalRuntimeConfiguration, runtimeId?: string) => call<LocalRuntime>(runtimeId ? `/runtimes/${id(runtimeId)}` : '/runtimes', runtimeId ? 'PUT' : 'POST', body),
  validate: (candidateId: string) => call<LocalModelCandidate>(`/candidates/${id(candidateId)}/validate`, 'POST', {}),
  register: (candidateId: string) => call<LocalModelRegistration>(`/candidates/${id(candidateId)}/register`, 'POST', {}),
  configureRegistration: (registrationId: string, body: {workflow_adapter_id: string; license_confirmed: boolean}) => call<LocalModelRegistration>(`/registrations/${id(registrationId)}`, 'PUT', body),
  enable: (registrationId: string) => call<LocalModelRegistration>(`/registrations/${id(registrationId)}/enable`, 'POST', {confirmed: true}),
  disable: (registrationId: string) => call<LocalModelRegistration>(`/registrations/${id(registrationId)}/disable`, 'POST', {}),
  remove: (registrationId: string) => call<void>(`/registrations/${id(registrationId)}`, 'DELETE'),
};


/** A preview is display-only evidence, never model readiness or routing authority. */
export type LocalAiScanScope = {
  schema_version: 1;
  execution_scope: 'BACKEND_HOST';
  scope_digest: string;
  include_common_model_dirs: boolean;
  services: {id: string; name: string; type: string; endpoint: string; management: string; probe_paths: string[]}[];
  roots: {path: string; source: 'CONFIGURED' | 'COMMON'}[];
  metadata_inspections: {kind: string; path: string; max_entries: number; max_bytes: number}[];
  hardware_categories: string[];
  limits: Record<string, number>;
  inference_status: 'NOT_RUN';
  requires_confirmation: true;
  side_effects: {launches: false; loads_weights: false; registers: false; enables: false; cloud_calls: false; persists_settings: false; may_disable_stale_registrations: true; persists_registration_safety_updates: true};
};

function checkedScope(value: LocalAiScanScope, includeCommon: boolean): LocalAiScanScope {
  const invalid = () => {throw new ApiError({status: 0, code: 'LOCAL_AI_SCOPE_INVALID', message: '检测范围无法确认，请重新预览。'});};
  const string = (item: unknown) => typeof item === 'string' && item.length > 0 && item.length <= 4096;
  const strings = (items: unknown) => Array.isArray(items) && items.every(string);
  const count = (item: unknown) => typeof item === 'number' && Number.isFinite(item) && item >= 0;
  const effects = ['launches', 'loads_weights', 'registers', 'enables', 'cloud_calls', 'persists_settings', 'may_disable_stale_registrations', 'persists_registration_safety_updates'];
  if (!value || value.schema_version !== 1 || value.execution_scope !== 'BACKEND_HOST'
    || !/^[a-f0-9]{64}$/.test(value.scope_digest) || value.include_common_model_dirs !== includeCommon
    || value.inference_status !== 'NOT_RUN' || value.requires_confirmation !== true
    || !value.side_effects || ['launches', 'loads_weights', 'registers', 'enables', 'cloud_calls', 'persists_settings'].some(key => value.side_effects[key as keyof LocalAiScanScope['side_effects']] !== false)
    || Object.keys(value.side_effects).some(key => !effects.includes(key))
    || value.side_effects.may_disable_stale_registrations !== true || value.side_effects.persists_registration_safety_updates !== true
    || !Array.isArray(value.services) || !value.services.every(item => item && string(item.id) && string(item.name) && string(item.type) && string(item.endpoint) && string(item.management) && strings(item.probe_paths))
    || !Array.isArray(value.roots) || !value.roots.every(item => item && string(item.path) && ['CONFIGURED', 'COMMON'].includes(item.source))
    || (!includeCommon && value.roots.some(item => item.source === 'COMMON'))
    || !Array.isArray(value.metadata_inspections) || !value.metadata_inspections.every(item => item && string(item.kind) && string(item.path) && count(item.max_entries) && count(item.max_bytes))
    || !strings(value.hardware_categories) || !value.limits || Array.isArray(value.limits) || !Object.keys(value.limits).length || !Object.values(value.limits).every(count)) invalid();
  return value;
}

/** Gated V2 transport freezes the original owner once, including an explicitly
 * empty LOCAL_HOST credential, using the same fallback policy as the singleton. */
export function localAiDiscoveryClient(context: CollaborationContext, isCurrent: () => boolean = () => true) {
  const sessionToken = requestToken(context, BASE);
  const captured = {sessionToken, branchId: context.scope?.branchId};
  async function request<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
    if (!isCurrent()) throw new DOMException('检测会话已改变。', 'AbortError');
    const result = await call<T>(path, method, body, signal, captured);
    if (!isCurrent() || signal?.aborted) throw new DOMException('检测会话已改变。', 'AbortError');
    return result;
  }
  return {
    environment: (signal?: AbortSignal) => request<AIEnvironmentReport>('/environment', 'GET', undefined, signal).then(checkedOptionalVideoObservation),
    snapshot: (signal?: AbortSignal) => request<LocalDiscoverySnapshot>('', 'GET', undefined, signal).then(checkedOptionalVideoObservation),
    previewScope: async (includeCommon: boolean, signal?: AbortSignal) => checkedScope(await request<LocalAiScanScope>(`/onboarding/scan-scope?include_common_model_dirs=${includeCommon ? 'true' : 'false'}`, 'GET', undefined, signal), includeCommon),
    confirmScan: (scopeDigest: string, signal?: AbortSignal) => request<LocalDiscoveryScan>('/onboarding/scan', 'POST', {scope_digest: scopeDigest, confirmed: true}, signal),
    scanStatus: (scanId: string, signal?: AbortSignal) => request<LocalDiscoveryScan>(`/scan/${id(scanId)}`, 'GET', undefined, signal),
    cancelScan: (scanId: string) => request<LocalDiscoveryScan>(`/scan/${id(scanId)}/cancel`, 'POST', {}),
    settings: (scan_roots: string[], include_common_model_dirs?: boolean) => request<LocalDiscoverySettings>('/settings', 'PUT', {scan_roots, ...(include_common_model_dirs === undefined ? {} : {include_common_model_dirs})}),
    saveRuntime: (body: LocalRuntimeConfiguration, runtimeId?: string) => request<LocalRuntime>(runtimeId ? `/runtimes/${id(runtimeId)}` : '/runtimes', runtimeId ? 'PUT' : 'POST', body),
    validate: (candidateId: string) => request<LocalModelCandidate>(`/candidates/${id(candidateId)}/validate`, 'POST', {}),
    register: (candidateId: string) => request<LocalModelRegistration>(`/candidates/${id(candidateId)}/register`, 'POST', {}),
    configureRegistration: (registrationId: string, body: {workflow_adapter_id: string; license_confirmed: boolean}) => request<LocalModelRegistration>(`/registrations/${id(registrationId)}`, 'PUT', body),
    enable: (registrationId: string) => request<LocalModelRegistration>(`/registrations/${id(registrationId)}/enable`, 'POST', {confirmed: true}),
    disable: (registrationId: string) => request<LocalModelRegistration>(`/registrations/${id(registrationId)}/disable`, 'POST', {}),
    remove: (registrationId: string) => request<void>(`/registrations/${id(registrationId)}`, 'DELETE'),
  };
}
export type LocalAiDiscoveryClient = ReturnType<typeof localAiDiscoveryClient>;
