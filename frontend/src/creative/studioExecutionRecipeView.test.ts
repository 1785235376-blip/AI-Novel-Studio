import { describe, expect, it } from 'vitest';
import type { ProductionRecipe } from './studioProductionClient';
import { buildStudioExecutionRecipeView } from './studioExecutionRecipeView';

const digest = 'a'.repeat(64);
// The original fixed SD recipe: app/services/studio_image_provider_recipes.py:129-185.
const workflow = () => ({
  '4': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: 'recorded-checkpoint.safetensors' } },
  '6': { class_type: 'CLIPTextEncode', inputs: { text: 'author prompt', clip: ['4', 1] } },
  '7': { class_type: 'CLIPTextEncode', inputs: { text: 'negative prompt', clip: ['4', 1] } },
  '5': { class_type: 'EmptyLatentImage', inputs: { width: 1024, height: 1024, batch_size: 1 } },
  '3': { class_type: 'KSampler', inputs: { model: ['4', 0], positive: ['6', 0], negative: ['7', 0], latent_image: ['5', 0],
    seed: 0, steps: 28, cfg: 7, sampler_name: 'euler', scheduler: 'normal', denoise: 1 } },
  '8': { class_type: 'VAEDecode', inputs: { samples: ['3', 0], vae: ['4', 2] } },
  '9': { class_type: 'SaveImage', inputs: { images: ['8', 0], filename_prefix: 'AI-Novel-Studio' } },
});
const recipe = (patch: Partial<ProductionRecipe> = {}): ProductionRecipe => ({
  contract: 'studio-execution-recipe/1', operation_id: 'm5.image.t2i', adapter: 'COMFYUI_BUILTIN_IMAGE',
  recipe_digest: digest, automatic_fallback: false, workflow: workflow(), ...patch,
});
const project = (value: ProductionRecipe, operationId = value.operation_id) => buildStudioExecutionRecipeView({ recipe: value, operationId, current: true });

describe('original execution_recipe read-only projection', () => {
  it('does not read stale contents, and returns no cached recipe identifiers or steps', () => {
    const value: ProductionRecipe = { contract: 'studio-execution-recipe/1', adapter: 'COMFYUI_BUILTIN_IMAGE',
      recipe_digest: digest, automatic_fallback: false, get operation_id(): never { throw new Error('stale content read'); } };
    expect(buildStudioExecutionRecipeView({ recipe: value, current: false })).toMatchObject({
      state: 'stale', operationId: null, adapter: null, recipeId: null, digest: null, steps: [],
    });
  });

  it('keeps missing recipe unavailable', () => {
    expect(buildStudioExecutionRecipeView({ current: true })).toMatchObject({ state: 'missing', visibility: 'missing', steps: [], digest: null });
  });

  it.each([
    { contract: 'other/1' }, { recipe_digest: '' }, { recipe_digest: 'a'.repeat(63) },
    { adapter: '' }, { operation_id: '' }, { automatic_fallback: true },
  ])('does not make an incomplete base recipe available: %j', patch => {
    const view = project(recipe(patch as Partial<ProductionRecipe>));
    expect(view.state).toBe('invalid'); expect(view.steps).toEqual([]); expect(view.digest).toBeNull();
  });

  it('hides all recipe details on operation mismatch and calls out an absent operation pin', () => {
    expect(project(recipe(), 'm5.image.i2i')).toMatchObject({ state: 'mismatch', adapter: null, digest: null, steps: [] });
    const unpinned = buildStudioExecutionRecipeView({ recipe: recipe(), current: true });
    expect(unpinned.notes.join(' ')).toContain('未核对配方与当前操作的关联');
  });

  it('explains only the actual fixed T2I workflow, with typed links and recorded component names', () => {
    const view = project(recipe());
    expect(view.state).toBe('available'); expect(view.visibility).toBe('visible'); expect(view.steps).toHaveLength(7);
    expect(view.steps.find(step => step.id === '4')).toMatchObject({ outputs: ['MODEL', 'CLIP', 'VAE'],
      inputs: [{ name: 'ckpt_name', type: 'STRING', source: null, component: 'recorded-checkpoint.safetensors' }] });
    expect(view.steps.find(step => step.id === '6')?.inputs).toContainEqual({ name: 'clip', type: 'CLIP', source: '4[1]', component: null });
    expect(view.steps.find(step => step.id === '3')?.outputs).toEqual(['LATENT']);
    expect(view.steps.find(step => step.id === '8')?.outputs).toEqual(['IMAGE']);
    expect(view.steps.some(step => step.classType === 'VAEEncode')).toBe(false);
    expect(view.steps.find(step => step.classType === 'SaveImage')?.outputs).toEqual([]);
    expect(view.notes.join(' ')).toContain('配方不含逐步骤执行回执');
  });

  it('shows actual reference image initialization without claiming consistency', () => {
    const value = recipe({ operation_id: 'm5.image.reference', reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION', workflow: {
      ...workflow(),
      '20': { class_type: 'LoadImage', inputs: { image: 'VERIFIED_SOURCE_UPLOAD_RECEIPT_1' } },
      '21': { class_type: 'LoadImage', inputs: { image: 'VERIFIED_SOURCE_UPLOAD_RECEIPT_2' } },
      '31': { class_type: 'ImageBlend', inputs: { image1: ['20', 0], image2: ['21', 0], blend_factor: 0.5, blend_mode: 'normal' } },
      '5': { class_type: 'VAEEncode', inputs: { pixels: ['31', 0], vae: ['4', 2] } },
    } });
    const view = project(value), encoder = view.steps.find(step => step.classType === 'VAEEncode');
    expect(encoder?.inputs).toContainEqual({ name: 'pixels', type: 'IMAGE', source: '31[0]', component: null });
    expect(view.notes.join(' ')).toContain('不保证角色一致性或多视图效果');
  });

  it.each(['ORIGINAL_HTTP_PROVIDER', 'AUTOMATIC1111_IMAGE', 'FUTURE_ADAPTER'])('does not invent or trust internal workflow for %s', adapter => {
    const view = project(recipe({ adapter, workflow: { '1': { class_type: 'KSampler', inputs: { secret: 'never-display-this' } } } }));
    expect(view.visibility).toBe('hidden'); expect(view.steps).toEqual([]);
    expect(view.notes.join(' ')).toContain('内部步骤不可见');
    expect(JSON.stringify(view)).not.toContain('never-display-this');
  });

  it.each([undefined, null])('keeps a missing Comfy workflow unavailable: %j', workflow => {
    expect(project(recipe({ workflow }))).toMatchObject({ state: 'available', visibility: 'missing', steps: [] });
  });

  it.each([{}, [], 'not a workflow', { '1': null }, { '1': { class_type: 'KSampler' } },
    Object.fromEntries(Array.from({ length: 41 }, (_, i) => [String(i), { class_type: 'KSampler', inputs: {} }]))])(
    'does not treat malformed or oversized workflow as visible: %j', workflow => {
      expect(project(recipe({ workflow }))).toMatchObject({ visibility: 'invalid', steps: [] });
    });

  it('does not derive unknown component/port semantics from a class name or inherited properties', () => {
    const view = project(recipe({ workflow: {
      '1': { class_type: 'FutureDecode', inputs: { model: 'not-a-known-type' } },
      '2': { class_type: 'constructor', inputs: {} },
      '3': { class_type: 'CLIPTextEncode', inputs: { text: 'private author text', toString: 'not-a-type' } },
    } }));
    expect(view.steps[0]).toMatchObject({ known: false, outputs: null, inputs: [{ name: 'model', type: 'UNKNOWN', component: null }] });
    expect(view.steps[1]).toMatchObject({ known: false, outputs: null });
    expect(view.steps[2].inputs.find(input => input.name === 'toString')?.type).toBe('UNKNOWN');
    expect(JSON.stringify(view)).not.toContain('private author text');
  });

  it('marks missing source nodes and absent output ports without repairing the workflow', () => {
    const view = project(recipe({ workflow: {
      '1': { class_type: 'CLIPTextEncode', inputs: { clip: ['missing', 0] } },
      '2': { class_type: 'VAEDecode', inputs: { samples: ['1', 99] } },
    } }));
    expect(view.steps[0].inputs[0].source).toBe('来源连线不可用');
    expect(view.notes.join(' ')).toContain('未提供的输出端口');
    expect(view.notes.join(' ')).toContain('未验证其可执行性');
  });

  it('preserves explicit video structural-only and inference-unverified evidence', () => {
    const view = project(recipe({ operation_id: 'm7.video.t2v', adapter: 'COMFYUI_BUILTIN_VIDEO',
      video_recipe_id: 'comfy-ltx095-video-v1', structural_only: true, inference_verified: false,
      workflow: { '3': { class_type: 'SamplerCustom', inputs: {} }, '8': { class_type: 'VAEDecode', inputs: { samples: ['3', 0] } } } }));
    expect(view.recipeId).toBe('comfy-ltx095-video-v1');
    expect(view.notes.join(' ')).toContain('structural_only=true');
    expect(view.notes.join(' ')).toContain('inference_verified=false');
    expect(view.steps[0]).toMatchObject({ known: false, outputs: null });
    expect(view.steps[1].outputs).toEqual(['IMAGE']);
  });

  it('explains an upscale recipe without synthesizing text encode, sampling or VAE steps', () => {
    const view = project(recipe({ operation_id: 'm5.image.upscale', image_recipe_id: 'comfy-upscale-model-v1', workflow: {
      '4': { class_type: 'UpscaleModelLoader', inputs: { model_name: 'recorded-upscaler.safetensors' } },
      '8': { class_type: 'ImageUpscaleWithModel', inputs: { upscale_model: ['4', 0] } },
    } }));
    expect(view.steps.map(step => step.classType)).toEqual(['UpscaleModelLoader', 'ImageUpscaleWithModel']);
    expect(view.steps[0].outputs).toEqual(['UPSCALE_MODEL']);
  });

  it('is deterministic, accepts frozen owner records, and does not expose arbitrary extension values', () => {
    const value = recipe({ provider_id: 'not-a-validated-route', token: 'never-echo-credentials', job_status: 'SUCCEEDED' });
    for (const node of Object.values(value.workflow as ReturnType<typeof workflow>)) { Object.freeze(node.inputs); Object.freeze(node); }
    Object.freeze(value.workflow); Object.freeze(value);
    const before = JSON.stringify(value), first = project(value), second = project(value);
    expect(first).toEqual(second); expect(JSON.stringify(value)).toBe(before);
    expect(JSON.stringify(first)).not.toContain('never-echo-credentials');
    expect(JSON.stringify(first)).not.toContain('not-a-validated-route');
    expect(JSON.stringify(first)).not.toContain('SUCCEEDED');
    expect(first.notes.join(' ')).toContain('配方未提供 provider_id / model_id');
  });
});
