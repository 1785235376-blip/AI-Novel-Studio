import { describe, expect, it } from 'vitest';
import type { StudioAsset } from '../../creative/studioClient';
import type { ProductionJob } from '../../creative/studioProductionClient';
import { assertExecutionJob, inspectApprovedAsset, isExecutionIdentifier, projectExecution, type ExecutionSelection } from './executionProvenanceModel';

const a = 'a'.repeat(64), b = 'b'.repeat(64), c = 'c'.repeat(64);
function job(): ProductionJob {
  return {
    contract: 'studio-production-job/1', owner: 'image', id: 'job-original', novel_id: 'project-a', branch_id: 'branch-a', version: 3,
    operation_id: 'm5.image.i2i', request_id: 'request-original', status: 'AWAITING_REVIEW', request_digest: a, receipt_digest: b,
    output_candidate: { id: 'candidate-original', version: 1, digest: c, kind: 'image' },
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false,
    timeline_snapshot: null, sources: [{ id: 'input-original', kind: 'ASSET', asset_kind: 'image', version: 7, digest: b }],
    command: { operation_id: 'm5.image.i2i', request_id: 'request-original', provider_id: 'local-provider', model_id: 'local-model',
      prompt: 'private source text', parameters: { steps: 33, seed: 100, denoising_strength: 0.6 },
      source_snapshots: [{ id: 'input-original', kind: 'ASSET', asset_kind: 'image', version: 7, digest: b }], allow_cloud: false, license_note: 'private note' },
    provider: { provider_id: 'local-provider', model_id: 'local-model', local: true, route_digest: a },
    execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm5.image.i2i', adapter: 'COMFYUI_BUILTIN_IMAGE', recipe_digest: b, automatic_fallback: false },
    approved_asset_version: null, created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z',
  };
}
function selection(value = job()): ExecutionSelection {
  return { projectId: 'project-a', branchId: 'branch-a', identity: 'session-a', job: value };
}
function asset(): StudioAsset {
  return { id: 'candidate-original', novel_id: 'project-a', branch_id: 'branch-a', version: 2, sha256: c, kind: 'image',
    filename: 'result.png', media_type: 'image/png', size: 10, created_at: '', updated_at: '' };
}

describe('original Studio execution provenance projection', () => {
  it('preserves actual request, job and input pins without fabricating hidden model evidence', () => {
    const value = projectExecution(job());
    expect(value).toMatchObject({ jobId: 'job-original', requestId: 'request-original', version: 3, status: 'AWAITING_REVIEW', requestDigest: a,
      receiptDigest: b, sources: [{ id: 'input-original', kind: 'ASSET', version: 7, digest: b }], approvedAssetVersion: null });
    expect(value.parameters).toEqual([{ name: 'steps', value: '33' }, { name: 'seed', value: '100' }, { name: 'denoising_strength', value: '0.6' }]);
    expect(value.executionKind).toContain('不等于真实模型推理验证');
  });

  it.each(['novel_id', 'branch_id', 'owner', 'id', 'request_id', 'request_digest'] as const)('rejects changed original %s before displaying', key => {
    const original = job(), changed = { ...original, [key]: key === 'request_digest' ? c : key === 'owner' ? 'video' : 'other-value' } as ProductionJob;
    expect(() => assertExecutionJob(changed, selection(original))).toThrow('范围不匹配');
  });

  it('allows newer read-only job state but refuses a version rollback', () => {
    const original = job();
    expect(() => assertExecutionJob({ ...original, version: 4, status: 'APPROVED' }, selection(original))).not.toThrow();
    expect(() => assertExecutionJob({ ...original, version: 2 }, selection(original))).toThrow('版本已退回');
  });

  it('preserves input version and digest when the current source would have changed', () => {
    const original = job(), projection = projectExecution(original);
    expect(projection.sources[0]).toEqual({ id: 'input-original', kind: 'ASSET', version: 7, digest: b });
    original.sources[0].version = 8;
    expect(projection.sources[0].version).toBe(7);
  });

  it('drops unknown fields, free text and sensitive values even when nested in the recipe', () => {
    const original = job();
    original.command!.parameters = { steps: 33, negative_prompt: 'Bearer top-secret-negative', width: 'sk-secret-width',
      token: 'sk-secret-token', quality: 'secret-quality', seed: Number.NaN, output_format: 'PNG', size: '1024x1024' };
    original.execution_recipe.workflow = { credential: 'secret-workflow', node: { api_key: 'secret-node' } };
    original.command!.prompt = 'secret-prompt'; original.command!.license_note = 'secret-license';
    (original as ProductionJob & { token: string }).token = 'secret-root';
    const projected = projectExecution(original), text = JSON.stringify(projected);
    expect(projected.parameters).toEqual([{ name: 'steps', value: '33' }, { name: 'output_format', value: 'PNG' }, { name: 'size', value: '1024x1024' }]);
    expect(text).not.toMatch(/secret|Bearer|workflow|negative_prompt|license_note|api_key|token/);
  });

  it('does not expose identity metadata embedded in comic source pins', () => {
    const original = job();
    original.sources = [{ id: 'panel-source', kind: 'COMIC_PANEL', version: 4, digest: b, reference_only: true,
      comic_panel: { panel_id: 'panel-a', panel_digest: a, brief_digest: c, actor: 'private-actor', scope_key: a, incarnation: 'private-incarnation' } }];
    expect(JSON.stringify(projectExecution(original))).not.toMatch(/private-actor|private-incarnation|scope_key/);
  });

  it('withholds credentials from permitted provider/model slots and does not infer missing routes', () => {
    const original = job();
    original.provider!.provider_id = 'sk-secret-provider';
    expect(projectExecution(original).provider).toBeNull();
    original.provider = null;
    expect(projectExecution(original).provider).toBeNull();
    expect(projectExecution(original).executionKind).toContain('未提供');
  });

  it('describes a cloud provider as an API call without inventing internal nodes', () => {
    const original = job();
    original.provider!.local = false;
    original.execution_recipe.adapter = 'ORIGINAL_HTTP_PROVIDER';
    original.execution_recipe.workflow = { fake: { class_type: 'FakeCloudInternalNode' } };
    const projected = projectExecution(original);
    expect(projected.executionKind).toContain('接口调用');
    expect(projected.executionKind).toContain('内部节点不可见');
    expect(JSON.stringify(projected)).not.toContain('FakeCloudInternalNode');
  });

  it.each(['UNKNOWN', 'FAILED', 'CANCELLED'] as const)('keeps %s without any replay permission', status => {
    const original = job(); original.status = status;
    const projected = projectExecution(original);
    expect(projected.recoveryReason).toMatch(/禁止重放|不能重放|没有恢复或重试契约/);
    expect(projected).not.toHaveProperty('retry');
    expect(projected).not.toHaveProperty('execute');
  });

  it('never upgrades an unreviewed candidate merely because an asset happens to exist', () => {
    const original = job(); original.approved_asset_version = 2;
    expect(projectExecution(original).approvedAssetVersion).toBeNull();
    expect(() => inspectApprovedAsset(original, asset(), selection(original))).toThrow();
  });

  it('accepts only the original approved asset version, preserving the separate candidate version', () => {
    const original = job(); original.status = 'APPROVED'; original.approved_asset_version = 2;
    expect(inspectApprovedAsset(original, asset(), selection(original))).toEqual({ id: 'candidate-original', version: 2, digest: c, kind: 'image' });
    expect(projectExecution(original).candidate?.version).toBe(1);
    expect(projectExecution(original).approvedAssetVersion).toBe(2);
  });

  it.each(['novel_id', 'branch_id', 'id', 'version', 'sha256', 'kind', 'deleted_at'] as const)('rejects changed approved asset %s', key => {
    const original = job(); original.status = 'APPROVED'; original.approved_asset_version = 2;
    const changed = { ...asset(), [key]: key === 'version' ? 3 : key === 'sha256' ? a : 'changed' };
    expect(() => inspectApprovedAsset(original, changed, selection(original))).toThrow();
  });

  it('does not expose raw error details or malformed IDs as provenance', () => {
    const original = job(); original.error_code = 'Authorization: Bearer secret-error';
    expect(projectExecution(original).errorCode).toBeNull();
    original.id = 'https://provider?token=secret-id';
    expect(() => projectExecution(original)).toThrow();
  });

  it.each(['STUDIO_IMAGE_CUTOUT_FAILED', 'STUDIO_VIDEO_REMOTE_STATE_UNKNOWN', 'STUDIO_AUDIO_EXECUTION_FAILED'])(
    'error-code display preserves known static owner code %s', errorCode => {
      const original = job(); original.error_code = errorCode;
      expect(projectExecution(original).errorCode).toBe(errorCode);
    });

  it.each(['UNKNOWN_PUBLIC_LOOKING_CODE', 'STUDIO_IMAGE_DYNAMIC_ERROR', 'STUDIO_IMAGE_CUTOUT_FAILED_SK_SECRET',
    'SK_SECRET_PROBE_123456', 'API_KEY_PROBE_123456', 'Authorization: Bearer synthetic-error'])(
    'error-code display withholds unknown, credential-shaped or free-text value %s', errorCode => {
      const original = job(); original.error_code = errorCode;
      const projected = projectExecution(original);
      expect(projected.errorCode).toBeNull();
      expect(JSON.stringify(projected)).not.toContain(errorCode);
    });

  it('does not turn missing or oversized source evidence into an empty valid input list', () => {
    const original = job();
    original.sources = undefined as unknown as ProductionJob['sources'];
    expect(() => projectExecution(original)).toThrow();
    original.sources = Array.from({ length: 31 }, () => job().sources[0]);
    expect(() => projectExecution(original)).toThrow();
  });

  it('refuses credential-shaped request identifiers rather than displaying them as trace IDs', () => {
    const original = job(); original.request_id = 'sk-secret-request';
    expect(() => projectExecution(original)).toThrow();
  });

  it.each(['sk-live-secret', 'token-secret', 'api_key_secret', 'Bearer-secret', 'secret-key', 'https://host', 'safe?token=secret', 'user:password@host'])('rejects sensitive original identifier %s', value => {
    expect(isExecutionIdentifier(value)).toBe(false);
  });

  it.each(['user:password@host', 'sk-live-secret', 'Bearer-secret', 'api_key_secret', 'https://host', 'org/model?token=secret'])('withholds sensitive route identifier %s', value => {
    const original = job(); original.provider!.model_id = value;
    expect(projectExecution(original).provider).toBeNull();
    original.provider!.model_id = 'org/model.safetensors'; original.provider!.provider_id = value;
    expect(projectExecution(original).provider).toBeNull();
  });

  it('preserves safe original identifiers and supported path-style model names', () => {
    expect(isExecutionIdentifier('canvas-original_123')).toBe(true);
    const original = job(); original.provider!.model_id = 'org/model.safetensors';
    expect(projectExecution(original).provider?.modelId).toBe('org/model.safetensors');
  });
});
