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
  environment: (signal?: AbortSignal) => call<AIEnvironmentReport>('/environment', 'GET', undefined, signal),
  snapshot: (signal?: AbortSignal) => call<LocalDiscoverySnapshot>('', 'GET', undefined, signal),
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
    environment: (signal?: AbortSignal) => request<AIEnvironmentReport>('/environment', 'GET', undefined, signal),
    snapshot: (signal?: AbortSignal) => request<LocalDiscoverySnapshot>('', 'GET', undefined, signal),
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
