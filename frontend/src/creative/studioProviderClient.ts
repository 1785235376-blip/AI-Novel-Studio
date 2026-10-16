import { ApiError } from '../api';
import type { StudioGraphTransport } from './studioGraphClient';
import type { StudioGraphOwner } from './studioGraphTypes';
import type { StudioProvider, StudioProviderCatalog, StudioProviderEnvelope, StudioProviderFamily, StudioTaskMatch, StudioTaskMatchResult, StudioTaskRequirement, StudioTaskType } from './studioProviderTypes';

const taskTypes: StudioTaskType[] = ['TEXT_GENERATION', 'IMAGE_GENERATION', 'VIDEO_GENERATION'];
const families: StudioProviderFamily[] = ['LOCAL_OLLAMA', 'LM_STUDIO', 'COMFYUI', 'LLAMA_CPP', 'API'];
const envelopeKeys = ['schema_version', 'contract', 'project_id', 'scope', 'advisory_only', 'dispatch_authorized', 'automatic_fallback', 'quality_verification'];
const requirementKeys = ['task_type', 'preferred_route', 'min_host_ram_mib', 'min_host_vram_mib', 'local_only', 'api_available', 'allow_synthetic'];
function invalid(input = false): never {
  throw new ApiError({ status: input ? 400 : 200, code: input ? 'STUDIO_GRAPH_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID',
    message: input ? '任务匹配条件不可用，请核对任务类型与内存要求。' : '服务返回的提供方或匹配说明不可用，请重新读取。' });
}
function object(value: unknown, input = false): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(input); return value as Record<string, unknown>;
}
// Versioned advisory projections reject unknown fields, including future positive
// execution claims. A catalog or match can never widen the original dispatcher.
function keys(row: Record<string, unknown>, allowed: string[], input = false) {
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid(input);
}
function text(value: unknown, maximum = 240): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid(); return value;
}
function bool(value: unknown, input = false): boolean { if (typeof value !== 'boolean') invalid(input); return value; }
function digest(value: unknown, input = false): string { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) invalid(input); return value; }
function integer(value: unknown, min: number, max: number, input = false): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid(input); return value;
}
function array(value: unknown, max = 128): unknown[] { if (!Array.isArray(value) || value.length > max) invalid(); return value; }
function unique<T>(values: T[]): T[] { if (new Set(values).size !== values.length) invalid(); return values; }
function reasons(value: unknown): string[] {
  return unique(array(value).map(item => { const result = text(item, 120); if (!/^[A-Z][A-Z0-9_]{0,119}$/.test(result)) invalid(); return result; }));
}
function task(value: unknown, input = false): StudioTaskType { if (!taskTypes.includes(value as StudioTaskType)) invalid(input); return value as StudioTaskType; }
function tasks(value: unknown): StudioTaskType[] { return unique(array(value, 3).map(item => task(item))); }
function equalSet<T>(left: T[], right: T[]) { return left.length === right.length && left.every(item => right.includes(item)); }
function envelope(row: Record<string, unknown>, owner: (value: Record<string, unknown>) => StudioGraphOwner): StudioProviderEnvelope {
  const ownership = owner(row);
  if (row.schema_version !== 1 || row.contract !== 'creative-model-provider/1' || row.advisory_only !== true
    || row.dispatch_authorized !== false || row.automatic_fallback !== false || row.quality_verification !== 'NOT_RUN') invalid();
  return { ...ownership, schema_version: 1, contract: 'creative-model-provider/1', advisory_only: true,
    dispatch_authorized: false, automatic_fallback: false, quality_verification: 'NOT_RUN' };
}
function requirement(value: unknown, input = false): StudioTaskRequirement {
  const row = object(value, input); keys(row, requirementKeys, input);
  if (row.local_only !== true || row.api_available !== false) invalid(input);
  return { task_type: task(row.task_type, input), preferred_route: row.preferred_route === null ? null : digest(row.preferred_route, input),
    min_host_ram_mib: row.min_host_ram_mib === null ? null : integer(row.min_host_ram_mib, 1, 10 ** 7, input),
    min_host_vram_mib: row.min_host_vram_mib === null ? null : integer(row.min_host_vram_mib, 1, 10 ** 7, input),
    local_only: true, api_available: false, allow_synthetic: bool(row.allow_synthetic, input) };
}
function provider(value: unknown): StudioProvider {
  const row = object(value); keys(row, ['family', 'capability', 'availability', 'registered_routes', 'advisory_only', 'automatic_fallback', 'real_model_verification']);
  const family = row.family as StudioProviderFamily, capability = object(row.capability), availability = object(row.availability);
  keys(capability, ['family', 'advertised', 'verified', 'verification', 'inference_verification']);
  keys(availability, ['family', 'adapter_available', 'status', 'reasons', 'execution_available', 'execution_authority']);
  if (!families.includes(family) || capability.family !== family || availability.family !== family || row.advisory_only !== true
    || row.automatic_fallback !== false || row.real_model_verification !== 'NOT_RUN' || capability.inference_verification !== 'NOT_RUN'
    || availability.execution_available !== false || availability.execution_authority !== 'ORIGINAL_REVIEWED_REQUEST_REQUIRED') invalid();
  const advertised = tasks(capability.advertised), verified = tasks(capability.verified), available = bool(availability.adapter_available), why = reasons(availability.reasons);
  const expected = family === 'API' ? taskTypes : family === 'COMFYUI' ? taskTypes.slice(1) : taskTypes.slice(0, 1);
  const reserved = ['LM_STUDIO', 'COMFYUI', 'API'].includes(family);
  const status = reserved ? 'RESERVED' : available ? 'REGISTERED' : 'UNAVAILABLE';
  const verification = available ? 'REGISTERED_ADAPTER_CONTRACT_ONLY' : 'NOT_VERIFIED';
  if (!equalSet(advertised, expected) || !equalSet(verified, available ? ['TEXT_GENERATION'] : [])
    || capability.verification !== verification || availability.status !== status || reserved && available
    || available !== (why.length === 0)) invalid();
  const reservedReason = family === 'LM_STUDIO' ? 'LMSTUDIO_LOCALITY_UNVERIFIED' : family === 'COMFYUI' ? 'COMFYUI_GRAPH_EXECUTION_NOT_ENABLED' : 'API_PROVIDER_EXECUTION_NOT_ENABLED';
  if (reserved && !why.includes(reservedReason)) invalid();
  const routes = array(row.registered_routes).map(value => { const item = object(value); keys(item, ['provider_id', 'model_id']); return { provider_id: text(item.provider_id), model_id: text(item.model_id) }; });
  unique(routes.map(item => JSON.stringify([item.provider_id, item.model_id])));
  if (available !== (routes.length > 0)) invalid();
  return { family, capability: { family, advertised, verified, verification, inference_verification: 'NOT_RUN' },
    availability: { family, adapter_available: available, status, reasons: why, execution_available: false, execution_authority: 'ORIGINAL_REVIEWED_REQUEST_REQUIRED' },
    registered_routes: routes, advisory_only: true, automatic_fallback: false, real_model_verification: 'NOT_RUN' };
}
function catalog(value: unknown, owner: (value: Record<string, unknown>) => StudioGraphOwner): StudioProviderCatalog {
  const row = object(value); keys(row, [...envelopeKeys, 'task_types', 'providers']); const ownership = envelope(row, owner);
  const advertisedTasks = tasks(row.task_types), providers = array(row.providers, 5).map(provider);
  if (!equalSet(advertisedTasks, taskTypes) || !equalSet(unique(providers.map(item => item.family)), families)) invalid();
  return { ...ownership, task_types: advertisedTasks, providers };
}
function matchResult(value: unknown, expected: StudioTaskRequirement, owner: (value: Record<string, unknown>) => StudioGraphOwner): StudioTaskMatchResult {
  const row = object(value); keys(row, [...envelopeKeys, 'requirement', 'matches', 'hardware', 'api_provider']); const ownership = envelope(row, owner);
  const checked = requirement(row.requirement), hardware = object(row.hardware), api = object(row.api_provider);
  if (requirementKeys.some(key => checked[key as keyof StudioTaskRequirement] !== expected[key as keyof StudioTaskRequirement])) invalid();
  keys(hardware, ['state', 'ram_mib', 'vram_mib', 'free_memory', 'warning']); keys(api, ['status', 'execution_available']);
  if (!['HOST_TOTAL_CAPACITY', 'UNAVAILABLE'].includes(hardware.state as string) || hardware.free_memory !== null
    || api.status !== 'RESERVED' || api.execution_available !== false) invalid();
  const ram = hardware.ram_mib === null ? null : integer(hardware.ram_mib, 0, Number.MAX_SAFE_INTEGER);
  const vram = hardware.vram_mib === null ? null : integer(hardware.vram_mib, 0, Number.MAX_SAFE_INTEGER);
  if (hardware.state === 'UNAVAILABLE' && (ram !== null || vram !== null)) invalid();
  if (hardware.warning !== undefined && hardware.warning !== 'Total capacity is not currently free memory or an inference fit guarantee.') invalid();
  const states = [[checked.min_host_ram_mib, ram], [checked.min_host_vram_mib, vram]].filter(([required]) => required !== null)
    .map(([required, capacity]) => hardware.state !== 'HOST_TOTAL_CAPACITY' || capacity === null ? 'UNKNOWN' : capacity < required! ? 'INSUFFICIENT' : 'TOTAL_CAPACITY_ONLY');
  const hardwareState = (['INSUFFICIENT', 'UNKNOWN', 'TOTAL_CAPACITY_ONLY'] as const).find(state => states.includes(state)) || 'NOT_REQUESTED';
  const matches: StudioTaskMatch[] = array(row.matches).map(value => {
    const item = object(value); keys(item, ['route_id', 'provider_id', 'model_id', 'display_name', 'synthetic', 'task_type', 'eligible', 'reasons', 'preferred', 'hardware_state', 'api_available', 'execution_authority', 'automatic_fallback', 'gpu_fit_verified']);
    const routeId = digest(item.route_id), synthetic = bool(item.synthetic), eligible = bool(item.eligible), why = reasons(item.reasons), preferred = bool(item.preferred);
    if (item.task_type !== checked.task_type || item.api_available !== false || item.execution_authority !== false || item.automatic_fallback !== false
      || item.gpu_fit_verified !== false || eligible !== (why.length === 0) || item.hardware_state !== hardwareState
      || preferred !== (checked.preferred_route !== null && routeId === checked.preferred_route)
      || eligible && (checked.task_type !== 'TEXT_GENERATION' || synthetic && !checked.allow_synthetic || checked.preferred_route !== null && !preferred || ['UNKNOWN', 'INSUFFICIENT'].includes(hardwareState))) invalid();
    return { route_id: routeId, provider_id: text(item.provider_id), model_id: text(item.model_id), display_name: text(item.display_name), synthetic,
      task_type: checked.task_type, eligible, reasons: why, preferred, hardware_state: hardwareState,
      api_available: false, execution_authority: false, automatic_fallback: false, gpu_fit_verified: false };
  });
  unique(matches.map(item => item.route_id));
  return { ...ownership, requirement: checked, matches,
    hardware: { state: hardware.state as StudioTaskMatchResult['hardware']['state'], ram_mib: ram, vram_mib: vram, free_memory: null,
      ...(hardware.warning === undefined ? {} : { warning: hardware.warning as string }) }, api_provider: { status: 'RESERVED', execution_available: false } };
}

export function createStudioProviderClient(base: string, transport: StudioGraphTransport, owner: (value: Record<string, unknown>) => StudioGraphOwner) {
  return {
    providerContracts: (signal?: AbortSignal): Promise<StudioProviderCatalog> => transport.json(`${base}/graphs/provider-contracts`, 'GET', undefined, signal).then(value => catalog(value, owner)),
    modelMatch: (value: StudioTaskRequirement, signal?: AbortSignal): Promise<StudioTaskMatchResult> => {
      const payload = requirement(value, true);
      return transport.json(`${base}/graphs/model-match`, 'POST', payload, signal).then(value => matchResult(value, payload, owner));
    },
  };
}
export type StudioProviderClient = ReturnType<typeof createStudioProviderClient>;
