// Pure legacy input/configuration observations only. No provider, HTTP or media calls.
import {describe, expect, it, vi} from 'vitest';
import type {CanvasTaskOwner} from '../rebuild/image/canvasTaskBinding';
import {checkedQueuedImageJob, hasImageJobExecutionPermission, matchingExecutionProvider, sameExecutionSnapshot} from './imageJobExecution';

const owner: CanvasTaskOwner = {mode: 'local', actorId: 'verified-host', actorWorkspaceId: '', workspaceId: '', projectId: 'novel-a',
  storylineId: '', branchId: '', novelId: 'novel-a'};
const shared: CanvasTaskOwner = {...owner, mode: 'collaboration', actorId: 'author:甲', actorWorkspaceId: 'workspace:甲',
  workspaceId: 'workspace:甲', storylineId: 'story:甲', branchId: 'branch:甲'};
const row = (changes: Record<string, unknown> = {}) => ({id: 'original-job', novel_id: owner.novelId, branch_id: null,
  owner_actor_id: null, status: 'QUEUED', approval_status: 'PENDING', provider_id: 'provider-a', model_id: 'original-model',
  prompt: 'Original reviewed prompt\n第二行', parameters: {size: '1024x1024', quality: 'auto'}, allow_cloud_prompt: false,
  request_sha256: 'a'.repeat(64), attempt: 0, updated_at: '2026-10-23T13:00:00.123456+00:00', ...changes});
const provider = (changes: Record<string, unknown> = {}) => ({provider_id: 'provider-a', default_model: 'original-model',
  endpoint: 'https://provider.invalid/v1', api_style: 'openai', local: false, configured: true, registered: true, reachable: true,
  enabled: true, requires_credential: true, credential_configured: true, ...changes});
const snapshot = () => {
  const value = checkedQueuedImageJob(owner, row());
  if (!value) throw new Error('Expected valid synthetic queued input');
  return value;
};

describe('explicit legacy text-to-image execution observation', () => {
  it('freezes a detached complete input observation without copying response URI, token or unrelated fields', () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    try {
      const source = row({character_id: null, scene_id: 'scene:甲', images: [], size: 'auto', quality: 'high', output_format: 'png',
        asset_uri: 'https://result.invalid/private?signature=not-for-display', execution_token: 'not-for-display', secret: 'not-for-display', version: 123});
      const observed = checkedQueuedImageJob(owner, source)!;
      expect(observed).toMatchObject({jobId: 'original-job', novelId: 'novel-a', branchId: null, ownerActorId: null,
        providerId: 'provider-a', modelId: 'original-model', prompt: source.prompt, parameters: source.parameters,
        allowCloudPrompt: false, requestSha256: source.request_sha256, attempt: 0, updatedAt: source.updated_at});
      expect(observed.input).toEqual({provider_id: source.provider_id, model_id: source.model_id, prompt: source.prompt, parameters: source.parameters,
        allow_cloud_prompt: false, character_id: null, scene_id: 'scene:甲', images: [], size: 'auto', quality: 'high', output_format: 'png'});
      for (const item of [observed, observed.owner, observed.parameters, observed.input, observed.input.images]) expect(Object.isFrozen(item)).toBe(true);
      source.parameters.quality = 'low';
      expect(observed.parameters.quality).toBe('auto');
      expect(JSON.stringify(observed)).not.toContain('not-for-display');
      expect(observed).not.toHaveProperty('version');
      expect(fetcher).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); }
  });

  it.each(['RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', null, undefined])('rejects status %s', status => {
    expect(checkedQueuedImageJob(owner, row({status}))).toBeUndefined();
  });

  it.each([
    {id: ''}, {id: '../other'}, {novel_id: 'novel-b'}, {branch_id: undefined}, {branch_id: ''}, {owner_actor_id: undefined},
    {owner_actor_id: 'another-actor'}, {contract: 'studio-image-execution/1'}, {contract: 'unknown-contract'},
    {provider_id: ''}, {provider_id: ' provider-a'}, {model_id: ''}, {prompt: '   '}, {prompt: 'bad\u0000prompt'},
    {parameters: undefined}, {parameters: null}, {parameters: []}, {parameters: {unknown: 1}}, {parameters: {scale: 2}},
    {allow_cloud_prompt: undefined}, {allow_cloud_prompt: 'false'}, {request_sha256: 'A'.repeat(64)}, {request_sha256: 'a'.repeat(63)},
    {attempt: -1}, {attempt: true}, {attempt: 1.5}, {attempt: Number.MAX_SAFE_INTEGER + 1},
    {updated_at: 'today'}, {updated_at: undefined}, {images: null}, {images: undefined}, {images: 'unknown'},
    {images: ['data:image/png;base64,YWJj']}, {character_id: ''}, {scene_id: 17}, {size: 'other'}, {quality: 'other'}, {output_format: 'svg'},
  ])('rejects incomplete, ambiguous or unsupported input: %j', change => {
    expect(checkedQueuedImageJob(owner, row(change))).toBeUndefined();
  });

  it('requires the exact collaboration actor and branch, accepting the existing Unicode/colon owner contract', () => {
    const source = row({branch_id: shared.branchId, owner_actor_id: shared.actorId});
    expect(checkedQueuedImageJob(shared, source)?.owner).toEqual(shared);
    expect(checkedQueuedImageJob(shared, {...source, owner_actor_id: 'other-author'})).toBeUndefined();
    expect(checkedQueuedImageJob(shared, {...source, branch_id: 'other-branch'})).toBeUndefined();
    expect(checkedQueuedImageJob(shared, {...source, branch_id: null})).toBeUndefined();
    expect(checkedQueuedImageJob(owner, source)).toBeUndefined();
    const customOwner = {...shared, novelId: '作品:甲.v2', projectId: '作品:甲.v2'};
    expect(checkedQueuedImageJob(customOwner, {...source, novel_id: customOwner.novelId})).toBeDefined();
  });

  it.each([
    {...owner, actorId: ''}, {...owner, projectId: 'novel-b'}, {...owner, branchId: 'unexpected-branch'},
    {...shared, actorWorkspaceId: 'other-workspace'}, {...shared, storylineId: ''},
  ])('rejects an incomplete owner: %j', invalidOwner => expect(checkedQueuedImageJob(invalidOwner, row())).toBeUndefined());

  it.each([
    {width: 64, height: 2048, steps: 1, seed: 0, cfg: 0, denoising_strength: 0.1, negative_prompt: ''},
    {width: 2048, height: 64, steps: 150, seed: 2147483647, cfg: 100, denoising_strength: 1, negative_prompt: 'negative'},
    {}, {size: 'auto', quality: 'hd'},
  ])('preserves legal legacy parameter boundaries: %j', parameters => {
    expect(checkedQueuedImageJob(owner, row({parameters}))?.parameters).toEqual(parameters);
  });

  it.each([
    {width: 63}, {height: 2056}, {width: 65}, {width: true}, {steps: 0}, {steps: 151}, {seed: -1}, {seed: 2147483648},
    {cfg: Number.NaN}, {cfg: Number.POSITIVE_INFINITY}, {cfg: 101}, {cfg: '7'}, {denoising_strength: 0}, {denoising_strength: 1.1},
    {quality: 'unknown'}, {size: 'other'}, {negative_prompt: 1}, {negative_prompt: 'x'.repeat(10001)}, {negative_prompt: {}},
  ])('rejects an unsupported parameter value: %j', parameters => expect(checkedQueuedImageJob(owner, row({parameters}))).toBeUndefined());

  it('compares semantic parameter ordering while preserving optional field presence', () => {
    const original = snapshot();
    expect(sameExecutionSnapshot(original, checkedQueuedImageJob(owner, row({parameters: {quality: 'auto', size: '1024x1024'}})))).toBe(true);
    expect(sameExecutionSnapshot(original, checkedQueuedImageJob(owner, row({character_id: null})))).toBe(false);
    expect(sameExecutionSnapshot(original, checkedQueuedImageJob(owner, row({images: []})))).toBe(false);
    expect(sameExecutionSnapshot(undefined, original)).toBe(false);
    expect(sameExecutionSnapshot(undefined, undefined)).toBe(false);
  });

  it.each([
    {id: 'replacement-job'}, {provider_id: 'provider-b'}, {model_id: 'other-model'}, {prompt: 'Changed prompt'},
    {parameters: {quality: 'low'}}, {allow_cloud_prompt: true}, {request_sha256: 'b'.repeat(64)}, {attempt: 1},
    {updated_at: '2026-10-23T13:00:01Z'}, {character_id: 'character-a'}, {scene_id: 'scene-a'},
    {size: 'auto'}, {quality: 'high'}, {output_format: 'webp'},
  ])('retires confirmation when a reviewed input changes: %j', changes => {
    expect(sameExecutionSnapshot(snapshot(), checkedQueuedImageJob(owner, row(changes)))).toBe(false);
  });

  it('includes the complete owner in its comparison, including local actor changes', () => {
    expect(sameExecutionSnapshot(snapshot(), checkedQueuedImageJob({...owner, actorId: 'different-verified-host'}, row()))).toBe(false);
  });
});

describe('existing provider configuration observation', () => {
  it.each(['openai', 'comfyui', 'automatic1111'])('matches one configured %s service without claiming actual model verification', api_style => {
    const observed = checkedQueuedImageJob(owner, row({parameters: api_style === 'openai' ? {size: 'auto'} : {width: 1024, steps: 28, seed: 0}}))!;
    const match = matchingExecutionProvider(observed, [provider({api_style, secret: 'not-for-display', arbitrary: 'not-for-display'})]);
    expect(match).toEqual(provider({api_style}));
    expect(Object.isFrozen(match)).toBe(true);
    expect(JSON.stringify(match)).not.toContain('not-for-display');
  });

  it.each([
    {provider_id: 'other'}, {default_model: 'other-model'}, {configured: false}, {configured: 'true'}, {registered: false},
    {reachable: false}, {reachable: undefined}, {local: undefined}, {local: 'false'}, {enabled: false},
    {api_style: 'unknown'}, {api_style: undefined}, {requires_credential: 'false'}, {credential_configured: null}, {endpoint: 42},
  ])('rejects unsupported or unready configuration: %j', changes => {
    expect(matchingExecutionProvider(snapshot(), [provider(changes)])).toBeUndefined();
  });

  it('requires exactly one provider row, ignoring unrelated IDs and rejecting duplicates regardless of their readiness', () => {
    expect(matchingExecutionProvider(snapshot(), [provider(), provider({provider_id: 'other'})])).toBeDefined();
    expect(matchingExecutionProvider(snapshot(), [provider(), provider({configured: false})])).toBeUndefined();
    expect(matchingExecutionProvider(snapshot(), [])).toBeUndefined();
    expect(matchingExecutionProvider(snapshot(), {items: [provider()]})).toBeUndefined();
    const {enabled: _enabled, ...legacyProvider} = provider();
    expect(matchingExecutionProvider(snapshot(), [legacyProvider])).toBeDefined();
    expect(matchingExecutionProvider(snapshot(), [provider({enabled: undefined})])).toBeDefined();
  });

  it.each([
    {api_style: 'openai', parameters: {width: 1024}},
    {api_style: 'automatic1111', parameters: {size: 'auto'}},
    {api_style: 'comfyui', parameters: {cfg: 7}},
    {api_style: 'automatic1111', parameters: {denoising_strength: 0.7}},
  ])('keeps generic inputs readable but refuses unsupported $api_style text-to-image keys', ({api_style, parameters}) => {
    const observed = checkedQueuedImageJob(owner, row({parameters}));
    expect(observed).toBeDefined();
    expect(matchingExecutionProvider(observed!, [provider({api_style})])).toBeUndefined();
  });

  it.each([{endpoint: 'https://replacement.invalid/v1'}, {local: true}, {api_style: 'comfyui'}, {requires_credential: false}, {credential_configured: false}])(
    'retains configuration fields needed to retire old confirmation: %j', changes => {
      expect(JSON.stringify(matchingExecutionProvider(snapshot(), [provider(changes)]))).not.toEqual(JSON.stringify(matchingExecutionProvider(snapshot(), [provider()])));
    });
});

describe('collaboration permission observation', () => {
  const permission = {actor_id: shared.actorId, domain: 'NOVEL', capabilities: {'domain.write': true}};
  it('requires the exact collaboration actor, NOVEL domain and strict write capability', () => {
    expect(hasImageJobExecutionPermission(shared, permission)).toBe(true);
    expect(hasImageJobExecutionPermission(shared, {...permission, actor_id: 'other-actor'})).toBe(false);
    expect(hasImageJobExecutionPermission(shared, {...permission, domain: 'IMAGE'})).toBe(false);
    expect(hasImageJobExecutionPermission(shared, {...permission, capabilities: {'domain.write': 'true'}})).toBe(false);
    expect(hasImageJobExecutionPermission(shared, {...permission, capabilities: {'domain.read': true}})).toBe(false);
    expect(hasImageJobExecutionPermission(shared, undefined)).toBe(false);
  });
  it('never substitutes a permission response for verified local-host authority', () => {
    expect(hasImageJobExecutionPermission(owner, {...permission, actor_id: owner.actorId})).toBe(false);
  });
});
