import {ApiError, getCollaborationContext} from './api';

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
};
export type LocalDiscoverySettings = {scan_roots: string[]; runtimes: LocalRuntime[]};
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
async function call<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = {'Content-Type': 'application/json', 'X-Request-ID': requestId()};
  const {sessionToken} = getCollaborationContext();
  if (sessionToken) headers['X-Session-Token'] = sessionToken;
  if (method !== 'GET') headers['Idempotency-Key'] = requestId();
  const response = await fetch(`${BASE}${path}`, {method, headers, signal, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  if (!response.ok) {
    let raw: Record<string, any> = {};
    try {raw = await response.json();} catch { /* Do not echo arbitrary server output. */ }
    const detail = raw.detail ?? raw.error ?? raw;
    const code = raw.code ?? detail?.code ?? (response.status === 401 ? 'SESSION_REQUIRED' : response.status === 403 ? 'FORBIDDEN' : 'LOCAL_AI_REQUEST_FAILED');
    throw new ApiError({status: response.status, code: typeof code === 'string' ? code : 'LOCAL_AI_REQUEST_FAILED', message: '本地 AI 操作未完成。', request_id: raw.request_id ?? response.headers.get('X-Request-ID') ?? undefined});
  }
  return response.status === 204 ? undefined as T : response.json();
}
const id = encodeURIComponent;
export const localAiDiscoveryApi = {
  snapshot: (signal?: AbortSignal) => call<LocalDiscoverySnapshot>('', 'GET', undefined, signal),
  scan: () => call<LocalDiscoveryScan>('/scan', 'POST', {}),
  scanStatus: (scanId: string, signal?: AbortSignal) => call<LocalDiscoveryScan>(`/scan/${id(scanId)}`, 'GET', undefined, signal),
  cancelScan: (scanId: string) => call<LocalDiscoveryScan>(`/scan/${id(scanId)}/cancel`, 'POST', {}),
  settings: (scan_roots: string[]) => call<LocalDiscoverySettings>('/settings', 'PUT', {scan_roots}),
  saveRuntime: (body: LocalRuntimeConfiguration, runtimeId?: string) => call<LocalRuntime>(runtimeId ? `/runtimes/${id(runtimeId)}` : '/runtimes', runtimeId ? 'PUT' : 'POST', body),
  validate: (candidateId: string) => call<LocalModelCandidate>(`/candidates/${id(candidateId)}/validate`, 'POST', {}),
  register: (candidateId: string) => call<LocalModelRegistration>(`/candidates/${id(candidateId)}/register`, 'POST', {}),
  configureRegistration: (registrationId: string, body: {workflow_adapter_id: string; license_confirmed: boolean}) => call<LocalModelRegistration>(`/registrations/${id(registrationId)}`, 'PUT', body),
  enable: (registrationId: string) => call<LocalModelRegistration>(`/registrations/${id(registrationId)}/enable`, 'POST', {confirmed: true}),
  disable: (registrationId: string) => call<LocalModelRegistration>(`/registrations/${id(registrationId)}/disable`, 'POST', {}),
  remove: (registrationId: string) => call<void>(`/registrations/${id(registrationId)}`, 'DELETE'),
};
