import type { StudioGraphOwner } from './studioGraphTypes';

export type StudioTaskType = 'TEXT_GENERATION' | 'IMAGE_GENERATION' | 'VIDEO_GENERATION';
export type StudioProviderFamily = 'LOCAL_OLLAMA' | 'LM_STUDIO' | 'COMFYUI' | 'LLAMA_CPP' | 'API';
export type StudioTaskRequirement = {
  task_type: StudioTaskType; preferred_route: string | null;
  min_host_ram_mib: number | null; min_host_vram_mib: number | null;
  local_only: true; api_available: false; allow_synthetic: boolean;
};
export type StudioProviderEnvelope = StudioGraphOwner & {
  schema_version: 1; contract: 'creative-model-provider/1'; advisory_only: true;
  dispatch_authorized: false; automatic_fallback: false; quality_verification: 'NOT_RUN';
};
export type StudioProvider = {
  family: StudioProviderFamily;
  capability: { family: StudioProviderFamily; advertised: StudioTaskType[]; verified: StudioTaskType[];
    verification: 'NOT_VERIFIED' | 'REGISTERED_ADAPTER_CONTRACT_ONLY'; inference_verification: 'NOT_RUN' };
  availability: { family: StudioProviderFamily; adapter_available: boolean; status: 'REGISTERED' | 'UNAVAILABLE' | 'RESERVED';
    reasons: string[]; execution_available: false; execution_authority: 'ORIGINAL_REVIEWED_REQUEST_REQUIRED' };
  registered_routes: { provider_id: string; model_id: string }[];
  advisory_only: true; automatic_fallback: false; real_model_verification: 'NOT_RUN';
};
export type StudioProviderCatalog = StudioProviderEnvelope & { task_types: StudioTaskType[]; providers: StudioProvider[] };
export type StudioTaskMatch = {
  route_id: string; provider_id: string; model_id: string; display_name: string; synthetic: boolean;
  task_type: StudioTaskType; eligible: boolean; reasons: string[]; preferred: boolean;
  hardware_state: 'NOT_REQUESTED' | 'UNKNOWN' | 'INSUFFICIENT' | 'TOTAL_CAPACITY_ONLY';
  api_available: false; execution_authority: false; automatic_fallback: false; gpu_fit_verified: false;
};
export type StudioTaskMatchResult = StudioProviderEnvelope & {
  requirement: StudioTaskRequirement; matches: StudioTaskMatch[];
  hardware: { state: 'HOST_TOTAL_CAPACITY' | 'UNAVAILABLE'; ram_mib: number | null; vram_mib: number | null; free_memory: null; warning?: string };
  api_provider: { status: 'RESERVED'; execution_available: false };
};
