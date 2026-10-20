import type { ProductionRecipe } from './studioProductionClient';

/** Consume only an already-decoded original preview/job recipe. No admission or execution authority. */
export type StudioExecutionRecipeViewInput = {
  recipe?: ProductionRecipe;
  operationId?: string;
  current: boolean;
};
export type StudioExecutionRecipeInput = Readonly<{
  name: string;
  type: string;
  source: string | null;
  component: string | null;
  recordedValue?: number | boolean;
}>;
export type StudioExecutionRecipeStep = Readonly<{
  id: string;
  classType: string;
  title: string;
  known: boolean;
  inputs: readonly StudioExecutionRecipeInput[];
  outputs: readonly string[] | null;
}>;
export type StudioExecutionRecipeView = Readonly<{
  state: 'stale' | 'missing' | 'invalid' | 'mismatch' | 'available';
  message: string;
  operationId: string | null;
  adapter: string | null;
  recipeId: string | null;
  digest: string | null;
  visibility: 'visible' | 'hidden' | 'missing' | 'invalid';
  steps: readonly StudioExecutionRecipeStep[];
  notes: readonly string[];
}>;

type Signature = Readonly<{ title: string; inputs: Readonly<Record<string, string>>; outputs: readonly string[] }>;
// Explanation of the fixed classes emitted by app/services/studio_{image,video}_provider_recipes.py.
// This is deliberately partial. An unrecognised class/port stays unknown; it never gains a capability.
const signatures: Readonly<Record<string, Signature>> = {
  CheckpointLoaderSimple: { title: '载入模型、文本编码器与 VAE', inputs: { ckpt_name: 'STRING' }, outputs: ['MODEL', 'CLIP', 'VAE'] },
  UNETLoader: { title: '载入生成模型', inputs: { unet_name: 'STRING', weight_dtype: 'STRING' }, outputs: ['MODEL'] },
  CLIPLoader: { title: '载入文本编码器', inputs: { clip_name: 'STRING', type: 'STRING', device: 'STRING' }, outputs: ['CLIP'] },
  DualCLIPLoader: { title: '载入双文本编码器', inputs: { clip_name1: 'STRING', clip_name2: 'STRING', type: 'STRING', device: 'STRING' }, outputs: ['CLIP'] },
  VAELoader: { title: '载入 VAE', inputs: { vae_name: 'STRING' }, outputs: ['VAE'] },
  CLIPTextEncode: { title: '编码文本', inputs: { text: 'STRING', clip: 'CLIP' }, outputs: ['CONDITIONING'] },
  EmptyLatentImage: { title: '建立初始潜空间', inputs: { width: 'INT', height: 'INT', batch_size: 'INT' }, outputs: ['LATENT'] },
  EmptySD3LatentImage: { title: '建立初始潜空间', inputs: { width: 'INT', height: 'INT', batch_size: 'INT' }, outputs: ['LATENT'] },
  LoadImage: { title: '读取原来源图片', inputs: { image: 'STRING' }, outputs: ['IMAGE', 'MASK'] },
  ImageBlend: { title: '按权重混合参考像素', inputs: { image1: 'IMAGE', image2: 'IMAGE', blend_factor: 'FLOAT', blend_mode: 'STRING' }, outputs: ['IMAGE'] },
  VAEEncode: { title: '编码图片到潜空间', inputs: { pixels: 'IMAGE', vae: 'VAE' }, outputs: ['LATENT'] },
  VAEEncodeForInpaint: { title: '编码图片及重绘遮罩', inputs: { pixels: 'IMAGE', vae: 'VAE', mask: 'MASK', grow_mask_by: 'INT' }, outputs: ['LATENT'] },
  ImageToMask: { title: '提取遮罩', inputs: { image: 'IMAGE', channel: 'STRING' }, outputs: ['MASK'] },
  InvertMask: { title: '反转遮罩', inputs: { mask: 'MASK' }, outputs: ['MASK'] },
  ImageCompositeMasked: { title: '按遮罩合成原图与结果', inputs: { destination: 'IMAGE', source: 'IMAGE', mask: 'MASK', x: 'INT', y: 'INT', resize_source: 'BOOLEAN' }, outputs: ['IMAGE'] },
  FluxGuidance: { title: '设置条件引导', inputs: { conditioning: 'CONDITIONING', guidance: 'FLOAT' }, outputs: ['CONDITIONING'] },
  ModelSamplingAuraFlow: { title: '设置模型采样参数', inputs: { model: 'MODEL', shift: 'FLOAT' }, outputs: ['MODEL'] },
  ModelSamplingSD3: { title: '设置模型采样参数', inputs: { model: 'MODEL', shift: 'FLOAT' }, outputs: ['MODEL'] },
  KSampler: { title: '采样潜空间', inputs: { model: 'MODEL', positive: 'CONDITIONING', negative: 'CONDITIONING', latent_image: 'LATENT', seed: 'INT', steps: 'INT', cfg: 'FLOAT', sampler_name: 'STRING', scheduler: 'STRING', denoise: 'FLOAT' }, outputs: ['LATENT'] },
  VAEDecode: { title: '解码潜空间到图片', inputs: { samples: 'LATENT', vae: 'VAE' }, outputs: ['IMAGE'] },
  SaveImage: { title: '交由原服务保存图片', inputs: { images: 'IMAGE', filename_prefix: 'STRING' }, outputs: [] },
  SaveWEBM: { title: '交由原服务保存视频', inputs: { images: 'IMAGE', filename_prefix: 'STRING', codec: 'STRING', fps: 'FLOAT', crf: 'FLOAT' }, outputs: [] },
  UpscaleModelLoader: { title: '载入超分模型', inputs: { model_name: 'STRING' }, outputs: ['UPSCALE_MODEL'] },
  ImageUpscaleWithModel: { title: '使用原超分模型处理图片', inputs: { upscale_model: 'UPSCALE_MODEL', image: 'IMAGE' }, outputs: ['IMAGE'] },
  ImageScale: { title: '调整图片尺寸', inputs: { image: 'IMAGE', upscale_method: 'STRING', width: 'INT', height: 'INT', crop: 'STRING' }, outputs: ['IMAGE'] },
};
const componentFields = new Set(['ckpt_name', 'unet_name', 'clip_name', 'clip_name1', 'clip_name2', 'vae_name', 'model_name']);
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown, max = 240): value is string => typeof value === 'string' && value.trim().length > 0 && value.length <= max && !/[\u0000-\u001f\u007f]/.test(value);
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const own = (value: object, key: string) => Object.hasOwn(value, key);
const signature = (classType: string) => own(signatures, classType) ? signatures[classType] : undefined;
type WorkflowNode = { class_type: string; inputs: Record<string, unknown> };

function workflowSteps(workflow: unknown): { steps: StudioExecutionRecipeStep[]; notes: string[] } | null {
  if (!record(workflow)) return null;
  const entries = Object.entries(workflow);
  if (!entries.length || entries.length > 40 || entries.some(([id, node]) => !text(id) || !record(node)
    || !text(node.class_type) || !record(node.inputs) || Object.keys(node.inputs).length > 64
    || Object.keys(node.inputs).some(name => !text(name)))) return null;
  const nodes = workflow as Record<string, WorkflowNode>, notes = new Set<string>();
  const steps = entries.map(([id]) => {
    const node = nodes[id], known = signature(node.class_type);
    const inputs = Object.entries(node.inputs).map(([name, value]): StudioExecutionRecipeInput => {
      let source: string | null = null;
      if (Array.isArray(value)) {
        const [sourceId, index] = value;
        if (value.length === 2 && typeof sourceId === 'string' && own(nodes, sourceId) && Number.isSafeInteger(index) && index >= 0) {
          const outputs = signature(nodes[sourceId].class_type)?.outputs;
          if (outputs && index >= outputs.length) notes.add('部分连线引用了未提供的输出端口；未验证其可执行性。');
          source = `${sourceId}[${index}]`;
        } else {
          source = '来源连线不可用';
          notes.add('部分来源连线不完整；未验证其可执行性。');
        }
      }
      const type = known && own(known.inputs, name) ? known.inputs[name] : 'UNKNOWN';
      const scalar = type === 'INT' && Number.isSafeInteger(value) || type === 'FLOAT' && typeof value === 'number' && Number.isFinite(value)
        || type === 'BOOLEAN' && typeof value === 'boolean';
      return { name, type, source, component: known && componentFields.has(name) && text(value, 256) ? value : null,
        ...(scalar ? { recordedValue: value as number | boolean } : {}) };
    });
    if (!known || inputs.some(input => input.type === 'UNKNOWN')) notes.add('部分步骤或端口没有已知说明，类型保持 UNKNOWN。');
    return { id, classType: node.class_type, title: known?.title ?? '未提供此步骤的说明', known: !!known,
      inputs, outputs: known ? [...known.outputs] : null };
  });
  return { steps, notes: [...notes] };
}

/** Pure display projection. It never verifies digests, probes providers, schedules steps or changes its input. */
export function buildStudioExecutionRecipeView({ recipe, operationId, current }: StudioExecutionRecipeViewInput): StudioExecutionRecipeView {
  const empty = (state: StudioExecutionRecipeView['state'], message: string): StudioExecutionRecipeView => ({
    state, message, operationId: null, adapter: null, recipeId: null, digest: null, visibility: 'missing', steps: [], notes: [],
  });
  // Freshness is supplied by the existing owner. Never inspect or retain stale recipe contents.
  if (!current) return empty('stale', '当前来源已失效，旧配方已隐藏。');
  if (recipe == null) return empty('missing', '执行配方不可用：原预览或任务尚未提供 execution_recipe。');
  if (!record(recipe) || recipe.contract !== 'studio-execution-recipe/1' || !text(recipe.operation_id)
    || !text(recipe.adapter) || !digest(recipe.recipe_digest) || recipe.automatic_fallback !== false) {
    return empty('invalid', '执行配方信息不完整，无法解释；请读取原记录核对。');
  }
  if (operationId !== undefined && operationId !== recipe.operation_id) {
    return empty('mismatch', '当前操作与配方 operation_id 不一致，旧配方内容已隐藏。');
  }
  const notes = ['来源为原 ProductionPreview / ProductionJob 的 execution_recipe；本面板不重新校验摘要或授予执行权限。',
    '配方不含逐步骤执行回执；下列步骤均未验证执行，实际任务状态请核对原 Job。',
    '配方未提供 provider_id / model_id、Agent 调度或素材版本；请核对原预览与任务来源记录。'];
  if (operationId === undefined) notes.push('未提供当前操作标识，未核对配方与当前操作的关联。');
  if (recipe.structural_only === true) notes.push('此配方明确标记 structural_only=true，仅提供结构证据。');
  if (recipe.inference_verified === false) notes.push('此配方明确标记 inference_verified=false，推理验证未完成。');
  if (recipe.reference_semantics === 'WEIGHTED_PIXEL_INITIALIZATION') notes.push('参考图用于加权像素初始化，不保证角色一致性或多视图效果。');
  const result = { state: 'available' as const, message: '原配方已提供；可阅读结构，执行未验证。',
    operationId: recipe.operation_id, adapter: recipe.adapter, digest: recipe.recipe_digest,
    recipeId: text(recipe.image_recipe_id) ? recipe.image_recipe_id : text(recipe.video_recipe_id) ? recipe.video_recipe_id : null,
    notes };
  // This is the original CPU adapter's fixed mapping, not an editable workflow or execution evidence.
  const parameters=recipe.parameters;
  if(recipe.adapter==='LOCAL_FFMPEG'&&recipe.operation_id==='m8.audio.trim'&&recipe.output_profile==='PCM_S16LE_WAV_48000_STEREO'
    &&record(parameters)&&Object.keys(parameters).length===2&&['in_ms','out_ms'].every(k=>own(parameters,k))
    &&Number.isSafeInteger(parameters.in_ms)&&Number.isSafeInteger(parameters.out_ms)&&Number(parameters.in_ms)>=0
    &&Number(parameters.out_ms)>Number(parameters.in_ms)&&Number(parameters.out_ms)-Number(parameters.in_ms)<=120000){
    return {...result,visibility:'visible',steps:[{id:'local-ffmpeg-trim',classType:'LOCAL_FFMPEG',title:'按来源起止毫秒截取并输出 PCM16 WAV',known:true,
      inputs:[{name:'in_ms',type:'INT',source:null,component:null,recordedValue:Number(parameters.in_ms)},
        {name:'out_ms',type:'INT',source:null,component:null,recordedValue:Number(parameters.out_ms)}],outputs:['AUDIO_PCM_S16LE_WAV_48000_STEREO']}],
      notes:[...notes,'这是原 FFmpeg 适配器的固定参数映射说明，不是可编辑节点图，也不代表已经执行。来源 pin 以原 Job 为准；执行后另核对真实时长、采样率、声道和输出摘要。不调用 TTS 或模型。']};
  }
  // HTTP and A1111 have no internal workflow contract here, even if an extension happens to be named workflow.
  if (recipe.adapter !== 'COMFYUI_BUILTIN_IMAGE' && recipe.adapter !== 'COMFYUI_BUILTIN_VIDEO') {
    return { ...result, visibility: 'hidden', steps: [], notes: [...notes,
      '当前适配器的内部步骤不可见；不推断编码、采样或解码过程。'] };
  }
  if (recipe.workflow == null) return { ...result, visibility: 'missing', steps: [], notes: [...notes, 'Comfy 配方未提供 workflow，内部步骤不可用。'] };
  const workflow = workflowSteps(recipe.workflow);
  if (!workflow) return { ...result, visibility: 'invalid', steps: [], notes: [...notes, 'workflow 结构不完整或超出只读展示范围，内部步骤不可用。'] };
  return { ...result, visibility: 'visible', steps: workflow.steps, notes: [...notes, ...workflow.notes] };
}
