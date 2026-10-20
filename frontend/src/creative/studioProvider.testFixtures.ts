import { modelOwner } from './studioGraphModel.testFixtures';
import type { StudioProvider, StudioProviderCatalog, StudioTaskMatchResult, StudioTaskRequirement, StudioTaskType } from './studioProviderTypes';

export const taskRequirement = (patch: Partial<StudioTaskRequirement> = {}): StudioTaskRequirement => ({ task_type: 'TEXT_GENERATION', preferred_route: null, min_host_ram_mib: null, min_host_vram_mib: null, local_only: true, api_available: false, allow_synthetic: false, ...patch });
const envelope = () => ({ ...modelOwner(), schema_version: 1 as const, contract: 'creative-model-provider/1' as const, advisory_only: true as const, dispatch_authorized: false as const, automatic_fallback: false as const, quality_verification: 'NOT_RUN' as const });
export function providerCatalog(): StudioProviderCatalog {
  const families: StudioProvider['family'][] = ['LOCAL_OLLAMA', 'LM_STUDIO', 'COMFYUI', 'LLAMA_CPP', 'API'];
  const types: StudioTaskType[] = ['TEXT_GENERATION', 'IMAGE_GENERATION', 'VIDEO_GENERATION'];
  return { ...envelope(), task_types: types, providers: families.map(family => {
    const reserved = ['LM_STUDIO', 'COMFYUI', 'API'].includes(family), available = family === 'LOCAL_OLLAMA';
    return { family, capability: { family, advertised: family === 'API' ? types : family === 'COMFYUI' ? types.slice(1) : types.slice(0, 1),
      verified: available ? ['TEXT_GENERATION'] : [], verification: available ? 'REGISTERED_ADAPTER_CONTRACT_ONLY' : 'NOT_VERIFIED', inference_verification: 'NOT_RUN' },
      availability: { family, adapter_available: available, status: reserved ? 'RESERVED' : available ? 'REGISTERED' : 'UNAVAILABLE',
        reasons: available ? [] : [family === 'LM_STUDIO' ? 'LMSTUDIO_LOCALITY_UNVERIFIED' : family === 'COMFYUI' ? 'COMFYUI_GRAPH_EXECUTION_NOT_ENABLED' : family === 'API' ? 'API_PROVIDER_EXECUTION_NOT_ENABLED' : 'EXPLICIT_VERIFIED_LOCAL_ROUTE_UNAVAILABLE'],
        execution_available: false, execution_authority: 'ORIGINAL_REVIEWED_REQUEST_REQUIRED' }, registered_routes: available ? [{ provider_id: 'local', model_id: 'writer' }] : [],
      advisory_only: true, automatic_fallback: false, real_model_verification: 'NOT_RUN' };
  }) };
}
export function taskMatch(requirement = taskRequirement()): StudioTaskMatchResult {
  const hardwareStates = [[requirement.min_host_ram_mib, 16384], [requirement.min_host_vram_mib, 8192]].filter(([min]) => min !== null).map(([min, actual]) => actual! < min! ? 'INSUFFICIENT' as const : 'TOTAL_CAPACITY_ONLY' as const);
  const hardwareState = hardwareStates.includes('INSUFFICIENT') ? 'INSUFFICIENT' : hardwareStates.length ? 'TOTAL_CAPACITY_ONLY' : 'NOT_REQUESTED';
  const preferred = requirement.preferred_route === 'd'.repeat(64), reasons: string[] = [];
  if (requirement.task_type !== 'TEXT_GENERATION') reasons.push('TASK_CAPABILITY_MISMATCH', `GRAPH_${requirement.task_type === 'IMAGE_GENERATION' ? 'IMAGE' : 'VIDEO'}_EXECUTION_NOT_ENABLED`);
  if (requirement.preferred_route !== null && !preferred) reasons.push('EXACT_PREFERRED_ROUTE_REQUIRED');
  if (hardwareState === 'INSUFFICIENT') reasons.push('HOST_RAM_INSUFFICIENT');
  return { ...envelope(), requirement, matches: [{ route_id: 'd'.repeat(64), provider_id: 'local', model_id: 'writer', display_name: '本地写作模型', synthetic: false,
    task_type: requirement.task_type, eligible: !reasons.length, reasons, preferred, hardware_state: hardwareState, api_available: false,
    execution_authority: false, automatic_fallback: false, gpu_fit_verified: false }],
    hardware: { state: 'HOST_TOTAL_CAPACITY', ram_mib: 16384, vram_mib: 8192, free_memory: null, warning: 'Total capacity is not currently free memory or an inference fit guarantee.' }, api_provider: { status: 'RESERVED', execution_available: false } };
}
