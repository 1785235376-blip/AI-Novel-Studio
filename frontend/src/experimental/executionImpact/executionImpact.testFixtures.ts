import type { MediaCommand, ProductionJob, ProductionRecipe } from '../../creative/studioProductionClient';
import type { ExecutionImpactInput } from './executionImpact';

export function impactInput(): ExecutionImpactInput {
  const command: MediaCommand = { operation_id: 'm5.image.i2i', request_id: 'synthetic-impact-request', provider_id: 'synthetic-local', model_id: 'synthetic-sd',
    prompt: 'Synthetic original prompt', parameters: { steps: 20, seed: 7, denoising_strength: 0.5 }, allow_cloud: false, license_note: 'Synthetic author declaration',
    source_snapshots: [{ id: 'synthetic-image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: 'a'.repeat(64) }] };
  const recipe: ProductionRecipe = { contract: 'studio-execution-recipe/1', operation_id: command.operation_id, adapter: 'COMFYUI',
    recipe_id: 'comfy-sd-checkpoint-v1', parameters: { ...command.parameters }, automatic_fallback: false, recipe_digest: 'b'.repeat(64) };
  const previousJob: ProductionJob = { contract: 'studio-production-job/1', owner: 'image', id: 'synthetic-job', novel_id: 'synthetic-project', branch_id: null, version: 1,
    operation_id: command.operation_id, request_id: command.request_id, status: 'QUEUED', request_digest: 'c'.repeat(64), receipt_digest: null, output_candidate: null,
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null, sources: structuredClone(command.source_snapshots),
    command: structuredClone(command), provider: { provider_id: 'synthetic-local', model_id: 'synthetic-sd', local: true, route_digest: 'd'.repeat(64) },
    execution_recipe: structuredClone(recipe), approved_asset_version: null, created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z' };
  return { scope: { novel_id: previousJob.novel_id, branch_id: null, incarnation: 'synthetic-incarnation' }, editScope: 'TASK', command, recipe, previousJob };
}
