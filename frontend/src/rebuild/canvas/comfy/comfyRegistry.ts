// [HERMIA-FE-20261031 DUALCANVAS-COMFY] 下画布节点注册表（数据驱动，字段对齐 ComfyUI /object_info）。
// - 每个节点定义 = ComfyUI object_info 的一条：input.required / input.optional / output / output_name / category / display_name。
// - 大写自定义类型（MODEL / CLIP / VAE / CONDITIONING / LATENT / IMAGE / MASK …）是可连线端口；INT / FLOAT / STRING / BOOLEAN /
//   下拉（数组）是参数控件，不是端口，这一点与 ComfyUI 相同。
// - 这里只是本地结构与草稿：不会执行、不会连 ComfyUI、不会调用任何模型。将来导入真实 object_info 走 parseObjectInfo()。

/** One ComfyUI input spec: [TYPE] | [TYPE, opts] | [[combo values], opts?]. */
export type ComfyInputSpec = [string | string[], Record<string, unknown>?];
/** Shape of one entry of ComfyUI GET /object_info (subset we read). */
export type ComfyObjectInfoEntry = {
  input?: {required?: Record<string, ComfyInputSpec>; optional?: Record<string, ComfyInputSpec>};
  output?: string[]; output_name?: string[]; output_is_list?: boolean[];
  name?: string; display_name?: string; category?: string; description?: string; output_node?: boolean;
};
export type ComfyObjectInfo = Record<string, ComfyObjectInfoEntry>;

export type PortDef = {name: string; type: string; optional?: boolean};
export type WidgetPrimitive = string | number | boolean;
export type WidgetDef = {
  name: string; kind: 'INT' | 'FLOAT' | 'STRING' | 'BOOLEAN' | 'COMBO'; optional?: boolean;
  choices?: string[]; default?: WidgetPrimitive; min?: number; max?: number; step?: number; multiline?: boolean;
};
export type NodeDef = {
  name: string; display_name: string; category: string; group: NodeGroup; inputs: PortDef[]; widgets: WidgetDef[]; outputs: PortDef[];
  output_node: boolean; source: 'builtin' | 'poemseed' | 'imported'; zh?: string; description?: string;
  /** PoemSeed nodes that may be snapshot-copied to the upper canvas keep the upper type id. */
  feedAs?: string;
};

export const NODE_GROUPS = ['poemseed', 'loaders', 'conditioning', 'sampling', 'latent', 'image', 'mask', 'controlnet', 'upscale', 'video', 'utils', 'other'] as const;
export type NodeGroup = typeof NODE_GROUPS[number];
export const GROUP_LABEL: Record<NodeGroup, {zh: string; en: string}> = {
  poemseed: {zh: '创作素材（参考图 / 导演备注 / 变体）', en: 'PoemSeed (reference / director / variants)'},
  loaders: {zh: '加载器', en: 'Loaders'}, conditioning: {zh: '条件', en: 'Conditioning'}, sampling: {zh: '采样', en: 'Sampling'},
  latent: {zh: '潜空间', en: 'Latent'}, image: {zh: '图像', en: 'Image'}, mask: {zh: '遮罩', en: 'Mask'},
  controlnet: {zh: 'ControlNet', en: 'ControlNet'}, upscale: {zh: '放大模型', en: 'Upscaling'}, video: {zh: '视频', en: 'Video'},
  utils: {zh: '工具', en: 'Utils'}, other: {zh: '其他（导入）', en: 'Other (imported)'},
};

/** ComfyUI default link colours (litegraph), plus PoemSeed TEXT. Unknown types get a stable hash colour. */
const PORT_COLORS: Record<string, string> = {
  MODEL: '#B39DDB', CLIP: '#FFD500', VAE: '#FF6E6E', CONDITIONING: '#FFA931', LATENT: '#FF9CF9', IMAGE: '#64B5F6', MASK: '#81C784',
  CONTROL_NET: '#00D78D', UPSCALE_MODEL: '#8D6E63', CLIP_VISION: '#A8DADC', CLIP_VISION_OUTPUT: '#AD7452', VIDEO: '#26A69A', AUDIO: '#7E57C2',
  TEXT: '#9AA4B5', '*': '#999999',
};
export function portColor(type: string): string {
  if (PORT_COLORS[type]) return PORT_COLORS[type];
  let h = 0; for (const c of type) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h} 55% 60%)`;
}
const WIDGET_KINDS = new Set(['INT', 'FLOAT', 'STRING', 'BOOLEAN']);

/** Same rule as ComfyUI's frontend: equal type, either side '*', or overlap of comma-separated unions. */
export function typesCompatible(outType: string, inType: string): boolean {
  if (outType === '*' || inType === '*') return true;
  const a = outType.split(',').map(s => s.trim()), b = new Set(inType.split(',').map(s => s.trim()));
  return a.some(t => b.has(t));
}

export function groupOf(category: string): NodeGroup {
  const c = category.toLowerCase().replace(/^advanced\//, '');
  if (c.startsWith('poemseed')) return 'poemseed';
  if (c.includes('controlnet')) return 'controlnet';
  if (c.includes('upscal')) return 'upscale';
  if (c.includes('video') || c.includes('animation')) return 'video';
  const head = c.split('/')[0] as NodeGroup;
  return (NODE_GROUPS as readonly string[]).includes(head) && head !== 'poemseed' && head !== 'other' ? head : 'other';
}

function boundedNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}
function makeWidget(name: string, kind: WidgetDef['kind'], optional: boolean | undefined, opts: Record<string, unknown>): WidgetDef {
  const widget: WidgetDef = {name, kind, optional};
  if (kind === 'INT' || kind === 'FLOAT') {
    const min = boundedNumber(opts.min), max = boundedNumber(opts.max), step = boundedNumber(opts.step);
    const fallback = boundedNumber(opts.default);
    if (min != null) widget.min = min;
    if (max != null) widget.max = max;
    if (step != null && step > 0) widget.step = step;
    if (fallback != null && (kind === 'FLOAT' || Number.isSafeInteger(fallback))) widget.default = fallback;
  } else if (kind === 'STRING') {
    if (typeof opts.default === 'string') widget.default = opts.default.slice(0, 4096);
    widget.multiline = opts.multiline === true;
  } else if (kind === 'BOOLEAN') {
    if (typeof opts.default === 'boolean') widget.default = opts.default;
  }
  return widget;
}

/** Built-in fallback value for one widget (ComfyUI widgets always carry a value). */
export function widgetDefault(widget: WidgetDef): WidgetPrimitive {
  if (widget.default !== undefined) return widget.default;
  if (widget.kind === 'BOOLEAN') return false;
  if (widget.kind === 'INT' || widget.kind === 'FLOAT') return widget.min ?? 0;
  if (widget.kind === 'COMBO') return widget.choices?.[0] ?? '';
  return '';
}

/** Initial params for a newly-added node. Unknown widgets are omitted. */
export function defaultWidgetParams(def: NodeDef | undefined): Record<string, WidgetPrimitive> | undefined {
  if (!def?.widgets.length) return undefined;
  const params: Record<string, WidgetPrimitive> = {};
  for (const widget of def.widgets) params[widget.name] = widgetDefault(widget);
  return params;
}

function validWidgetValue(widget: WidgetDef, value: unknown): WidgetPrimitive | undefined {
  if (widget.kind === 'BOOLEAN') return typeof value === 'boolean' ? value : undefined;
  if (widget.kind === 'INT') return typeof value === 'number' && Number.isSafeInteger(value) ? value : undefined;
  if (widget.kind === 'FLOAT') return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
  if (widget.kind === 'STRING') return typeof value === 'string' ? value.slice(0, 4096) : undefined;
  if (widget.kind === 'COMBO') return typeof value === 'string' ? value.slice(0, 240) : undefined;
  return undefined;
}

/** Restore only known widget params with their expected primitive types; bounded strings. */
export function sanitizeWidgetParams(def: NodeDef | undefined, raw: unknown): Record<string, WidgetPrimitive> | undefined {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return undefined;
  const source = raw as Record<string, unknown>;
  const out: Record<string, WidgetPrimitive> = {};
  if (def) {
    for (const widget of def.widgets) {
      if (!(widget.name in source)) continue;
      const value = validWidgetValue(widget, source[widget.name]);
      if (value !== undefined) out[widget.name] = value;
    }
  } else {
    // Unknown/removed node definitions: keep only a small primitive map, bounded.
    for (const [key, value] of Object.entries(source).slice(0, 64)) {
      if (!/^[A-Za-z0-9_.-]{1,80}$/.test(key)) continue;
      if (typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value)) ||
          (typeof value === 'string' && value.length <= 512)) out[key] = value;
    }
  }
  return Object.keys(out).length ? out : undefined;
}

export type ParseResult = {defs: NodeDef[]; errors: {name: string; reason: string}[]};
/** Pure parser for a ComfyUI object_info JSON (frontend only; never fetched here). */
export function parseObjectInfo(info: unknown, source: NodeDef['source'] = 'imported'): ParseResult {
  const defs: NodeDef[] = [], errors: ParseResult['errors'] = [];
  if (!info || typeof info !== 'object' || Array.isArray(info)) return {defs, errors: [{name: '', reason: 'not_an_object'}]};
  for (const [name, raw] of Object.entries(info as Record<string, unknown>)) {
    if (!raw || typeof raw !== 'object') { errors.push({name, reason: 'entry_not_object'}); continue; }
    const e = raw as ComfyObjectInfoEntry & {zh?: string; feedAs?: string};
    const out = e.output ?? [];
    if (!Array.isArray(out) || out.some(t => typeof t !== 'string')) { errors.push({name, reason: 'bad_output'}); continue; }
    const inputs: PortDef[] = [], widgets: WidgetDef[] = [];
    let bad = '';
    for (const [opt, rec] of [[false, e.input?.required], [true, e.input?.optional]] as const) {
      if (rec == null) continue;
      if (typeof rec !== 'object') { bad = 'bad_input'; break; }
      for (const [inName, spec] of Object.entries(rec)) {
        const t = Array.isArray(spec) ? spec[0] : undefined;
        const opts = Array.isArray(spec) && spec[1] && typeof spec[1] === 'object' && !Array.isArray(spec[1])
          ? spec[1] as Record<string, unknown> : {};
        if (Array.isArray(t)) {
          const choices = t.filter((choice): choice is string => typeof choice === 'string')
            .slice(0, 256).map(choice => choice.slice(0, 240));
          widgets.push({name: inName, kind: 'COMBO', optional: opt || undefined,
            choices, ...(typeof opts.default === 'string' ? {default: opts.default.slice(0, 240)} : {})});
        } else if (typeof t === 'string' && WIDGET_KINDS.has(t)) {
          widgets.push(makeWidget(inName, t as WidgetDef['kind'], opt || undefined, opts));
        } else if (typeof t === 'string' && t) inputs.push({name: inName, type: t, optional: opt || undefined});
        else { bad = `bad_input_spec:${inName}`; break; }
      }
      if (bad) break;
    }
    if (bad) { errors.push({name, reason: bad}); continue; }
    const names = Array.isArray(e.output_name) ? e.output_name : [];
    const category = typeof e.category === 'string' ? e.category : '';
    defs.push({
      name, display_name: typeof e.display_name === 'string' && e.display_name ? e.display_name : name, category, group: groupOf(category),
      inputs, widgets, outputs: out.map((t, i) => ({name: typeof names[i] === 'string' ? names[i] : t, type: t})),
      output_node: !!e.output_node, source, zh: e.zh, description: e.description, feedAs: e.feedAs,
    });
  }
  return {defs, errors};
}

const I = (t: string, o?: Record<string, unknown>): ComfyInputSpec => (o ? [t, o] : [t]);
const C = (v: string[]): ComfyInputSpec => [v];
const N = (category: string, display_name: string, zh: string, required: Record<string, ComfyInputSpec>, output: string[] = [], extra: Partial<ComfyObjectInfoEntry> & {feedAs?: string} = {}) =>
  ({input: {required}, output, category, display_name, zh, ...extra});

/** Built-in ComfyUI core nodes (structure only; names match ComfyUI so a real object_info can replace them 1:1). */
export const BUILTIN_OBJECT_INFO: ComfyObjectInfo = {
  CheckpointLoaderSimple: N('loaders', 'Load Checkpoint', '加载大模型', {ckpt_name: C([])}, ['MODEL', 'CLIP', 'VAE']),
  VAELoader: N('loaders', 'Load VAE', '加载 VAE', {vae_name: C([])}, ['VAE']),
  LoraLoader: N('loaders', 'Load LoRA', '加载 LoRA', {model: I('MODEL'), clip: I('CLIP'), lora_name: C([]), strength_model: I('FLOAT'), strength_clip: I('FLOAT')}, ['MODEL', 'CLIP']),
  CLIPLoader: N('advanced/loaders', 'Load CLIP', '加载 CLIP', {clip_name: C([])}, ['CLIP']),
  ControlNetLoader: N('loaders', 'Load ControlNet Model', '加载 ControlNet 模型', {control_net_name: C([])}, ['CONTROL_NET']),
  UpscaleModelLoader: N('loaders', 'Load Upscale Model', '加载放大模型', {model_name: C([])}, ['UPSCALE_MODEL']),
  CLIPVisionLoader: N('loaders', 'Load CLIP Vision', '加载 CLIP 视觉', {clip_name: C([])}, ['CLIP_VISION']),
  CLIPTextEncode: N('conditioning', 'CLIP Text Encode (Prompt)', '文本编码（提示词）', {text: I('STRING', {multiline: true}), clip: I('CLIP')}, ['CONDITIONING']),
  ConditioningCombine: N('conditioning', 'Conditioning (Combine)', '条件合并', {conditioning_1: I('CONDITIONING'), conditioning_2: I('CONDITIONING')}, ['CONDITIONING']),
  ConditioningSetArea: N('conditioning', 'Conditioning (Set Area)', '条件区域', {conditioning: I('CONDITIONING'), width: I('INT'), height: I('INT'), x: I('INT'), y: I('INT'), strength: I('FLOAT')}, ['CONDITIONING']),
  ConditioningZeroOut: N('advanced/conditioning', 'ConditioningZeroOut', '条件归零', {conditioning: I('CONDITIONING')}, ['CONDITIONING']),
  CLIPSetLastLayer: N('conditioning', 'CLIP Set Last Layer', 'CLIP 跳层', {clip: I('CLIP'), stop_at_clip_layer: I('INT')}, ['CLIP']),
  CLIPVisionEncode: N('conditioning', 'CLIP Vision Encode', 'CLIP 视觉编码', {clip_vision: I('CLIP_VISION'), image: I('IMAGE')}, ['CLIP_VISION_OUTPUT']),
  KSampler: N('sampling', 'KSampler', 'K 采样器', {model: I('MODEL'), seed: I('INT'), steps: I('INT'), cfg: I('FLOAT'), sampler_name: C([]), scheduler: C([]), positive: I('CONDITIONING'), negative: I('CONDITIONING'), latent_image: I('LATENT'), denoise: I('FLOAT')}, ['LATENT']),
  KSamplerAdvanced: N('sampling', 'KSampler (Advanced)', 'K 采样器（高级）', {model: I('MODEL'), add_noise: C(['enable', 'disable']), noise_seed: I('INT'), steps: I('INT'), cfg: I('FLOAT'), sampler_name: C([]), scheduler: C([]), positive: I('CONDITIONING'), negative: I('CONDITIONING'), latent_image: I('LATENT'), start_at_step: I('INT'), end_at_step: I('INT')}, ['LATENT']),
  EmptyLatentImage: N('latent', 'Empty Latent Image', '空潜空间图', {width: I('INT'), height: I('INT'), batch_size: I('INT')}, ['LATENT']),
  VAEDecode: N('latent', 'VAE Decode', 'VAE 解码', {samples: I('LATENT'), vae: I('VAE')}, ['IMAGE']),
  VAEEncode: N('latent', 'VAE Encode', 'VAE 编码', {pixels: I('IMAGE'), vae: I('VAE')}, ['LATENT']),
  VAEEncodeForInpaint: N('latent/inpaint', 'VAE Encode (for Inpainting)', 'VAE 编码（局部重绘）', {pixels: I('IMAGE'), vae: I('VAE'), mask: I('MASK'), grow_mask_by: I('INT')}, ['LATENT']),
  LatentUpscale: N('latent', 'Upscale Latent', '潜空间放大', {samples: I('LATENT'), upscale_method: C([]), width: I('INT'), height: I('INT'), crop: C([])}, ['LATENT']),
  SetLatentNoiseMask: N('latent/inpaint', 'Set Latent Noise Mask', '潜空间噪声遮罩', {samples: I('LATENT'), mask: I('MASK')}, ['LATENT']),
  LatentBlend: N('latent/batch', 'Latent Blend', '潜空间混合', {samples1: I('LATENT'), samples2: I('LATENT'), blend_factor: I('FLOAT')}, ['LATENT']),
  LoadImage: N('image', 'Load Image', '加载图像', {image: C([])}, ['IMAGE', 'MASK']),
  SaveImage: N('image', 'Save Image', '保存图像', {images: I('IMAGE'), filename_prefix: I('STRING')}, [], {output_node: true}),
  PreviewImage: N('image', 'Preview Image', '预览图像', {images: I('IMAGE')}, [], {output_node: true}),
  ImageScale: N('image/upscaling', 'Upscale Image', '图像缩放', {image: I('IMAGE'), upscale_method: C([]), width: I('INT'), height: I('INT'), crop: C([])}, ['IMAGE']),
  ImageScaleBy: N('image/upscaling', 'Upscale Image By', '按倍数缩放', {image: I('IMAGE'), upscale_method: C([]), scale_by: I('FLOAT')}, ['IMAGE']),
  ImageUpscaleWithModel: N('image/upscaling', 'Upscale Image (using Model)', '用模型放大图像', {upscale_model: I('UPSCALE_MODEL'), image: I('IMAGE')}, ['IMAGE']),
  ImageInvert: N('image', 'Invert Image', '反相图像', {image: I('IMAGE')}, ['IMAGE']),
  ImageBlend: N('image/postprocessing', 'Image Blend', '图像混合', {image1: I('IMAGE'), image2: I('IMAGE'), blend_factor: I('FLOAT'), blend_mode: C([])}, ['IMAGE']),
  ImageCrop: N('image/transform', 'Image Crop', '图像裁剪', {image: I('IMAGE'), width: I('INT'), height: I('INT'), x: I('INT'), y: I('INT')}, ['IMAGE']),
  ImageBatch: N('image', 'Batch Images', '图像合批', {image1: I('IMAGE'), image2: I('IMAGE')}, ['IMAGE']),
  LoadImageMask: N('mask', 'Load Image (as Mask)', '加载遮罩图', {image: C([]), channel: C(['alpha', 'red', 'green', 'blue'])}, ['MASK']),
  MaskToImage: N('mask', 'Convert Mask to Image', '遮罩转图像', {mask: I('MASK')}, ['IMAGE']),
  ImageToMask: N('mask', 'Convert Image to Mask', '图像转遮罩', {image: I('IMAGE'), channel: C(['red', 'green', 'blue', 'alpha'])}, ['MASK']),
  InvertMask: N('mask', 'InvertMask', '反相遮罩', {mask: I('MASK')}, ['MASK']),
  GrowMask: N('mask', 'GrowMask', '扩展遮罩', {mask: I('MASK'), expand: I('INT'), tapered_corners: I('BOOLEAN')}, ['MASK']),
  ControlNetApply: N('conditioning/controlnet', 'Apply ControlNet (OLD)', '应用 ControlNet（旧）', {conditioning: I('CONDITIONING'), control_net: I('CONTROL_NET'), image: I('IMAGE'), strength: I('FLOAT')}, ['CONDITIONING']),
  ControlNetApplyAdvanced: N('conditioning/controlnet', 'Apply ControlNet', '应用 ControlNet', {positive: I('CONDITIONING'), negative: I('CONDITIONING'), control_net: I('CONTROL_NET'), image: I('IMAGE'), strength: I('FLOAT'), start_percent: I('FLOAT'), end_percent: I('FLOAT')}, ['CONDITIONING', 'CONDITIONING'], {output_name: ['positive', 'negative']}),
  ImageOnlyCheckpointLoader: N('loaders/video_models', 'Image Only Checkpoint Loader (img2vid model)', '图生视频模型加载', {ckpt_name: C([])}, ['MODEL', 'CLIP_VISION', 'VAE']),
  SVD_img2vid_Conditioning: N('conditioning/video_models', 'SVD_img2vid_Conditioning', '图生视频条件（SVD）', {clip_vision: I('CLIP_VISION'), init_image: I('IMAGE'), vae: I('VAE'), width: I('INT'), height: I('INT'), video_frames: I('INT'), fps: I('INT')}, ['CONDITIONING', 'CONDITIONING', 'LATENT'], {output_name: ['positive', 'negative', 'latent']}),
  LoadVideo: N('image/video', 'Load Video', '加载视频', {file: C([])}, ['VIDEO']),
  CreateVideo: N('image/video', 'Create Video', '图像序列合成视频', {images: I('IMAGE'), fps: I('FLOAT')}, ['VIDEO'], {input: {required: {images: I('IMAGE'), fps: I('FLOAT')}, optional: {audio: I('AUDIO')}}}),
  GetVideoComponents: N('image/video', 'Get Video Components', '拆分视频（帧 / 音频）', {video: I('VIDEO')}, ['IMAGE', 'AUDIO', 'FLOAT'], {output_name: ['images', 'audio', 'fps']}),
  SaveVideo: N('image/video', 'Save Video', '保存视频', {video: I('VIDEO'), filename_prefix: I('STRING')}, [], {output_node: true}),
  SaveAnimatedWEBP: N('image/animation', 'SaveAnimatedWEBP', '保存动图（WEBP）', {images: I('IMAGE'), fps: I('FLOAT')}, [], {output_node: true}),
  Reroute: N('utils', 'Reroute', '转接点', {input: I('*')}, ['*']),
  Note: N('utils', 'Note', '便签', {text: I('STRING', {multiline: true})}, []),
};

/** PoemSeed enrichment nodes (kept from the original lower palette; these can be copied to the upper canvas). */
const PS = (zh: string, en: string, feedAs: string, required: Record<string, ComfyInputSpec>, output: string[], output_name?: string[]) =>
  N('poemseed', en, zh, required, output, {feedAs, output_name});
export const POEMSEED_OBJECT_INFO: Record<'image' | 'video', ComfyObjectInfo> = {
  image: {
    image_reference: PS('参考图', 'Reference image', 'image_reference', {image: C([])}, ['IMAGE']),
    asset_reference: PS('资产引用', 'Asset reference', 'asset_reference', {asset: C([])}, ['IMAGE']),
    image_style: PS('风格', 'Style', 'image_style', {style: I('STRING')}, ['TEXT'], ['style']),
    image_prompt: PS('变体提示词', 'Variant prompt', 'image_prompt', {text: I('STRING', {multiline: true})}, ['TEXT'], ['prompt']),
    text_input: PS('灵感 / 细节文本', 'Idea / detail text', 'text_input', {text: I('STRING', {multiline: true})}, ['TEXT'], ['text']),
  },
  video: {
    image_reference: PS('参考图', 'Reference image', 'image_reference', {image: C([])}, ['IMAGE']),
    director_note: PS('导演备注 / 风格', 'Director note / style', 'director_note', {note: I('STRING', {multiline: true})}, ['TEXT'], ['note']),
    storyboard_prompt: PS('变体镜头提示词', 'Variant shot prompt', 'storyboard_prompt', {text: I('STRING', {multiline: true})}, ['TEXT'], ['prompt']),
    text_input: PS('灵感 / 细节文本', 'Idea / detail text', 'text_input', {text: I('STRING', {multiline: true})}, ['TEXT'], ['text']),
  },
};

export type Registry = {defs: NodeDef[]; byName: Map<string, NodeDef>};
export function makeRegistry(defs: NodeDef[]): Registry { return {defs, byName: new Map(defs.map(d => [d.name, d]))}; }
/** Merge an imported object_info on top: same name replaces the builtin (PoemSeed nodes are never replaced). */
export function mergeImported(reg: Registry, imported: NodeDef[]): Registry {
  const by = new Map(reg.byName);
  for (const d of imported) { if (by.get(d.name)?.source === 'poemseed') continue; by.set(d.name, d); }
  return makeRegistry([...by.values()]);
}
const cache = new Map<string, Registry>();
export function defaultRegistry(kind: 'image' | 'video'): Registry {
  let r = cache.get(kind);
  if (!r) {
    const ps = parseObjectInfo(POEMSEED_OBJECT_INFO[kind], 'poemseed').defs;
    r = makeRegistry([...ps, ...parseObjectInfo(BUILTIN_OBJECT_INFO, 'builtin').defs]);
    cache.set(kind, r);
  }
  return r;
}
export const nodeLabel = (d: NodeDef, locale: string) => (locale.startsWith('zh') && d.zh ? d.zh : d.display_name);

export function searchDefs(reg: Registry, q: string, locale: string): NodeDef[] {
  const s = q.trim().toLowerCase();
  if (!s) return reg.defs;
  return reg.defs.filter(d => [d.name, d.display_name, d.zh ?? '', d.category, GROUP_LABEL[d.group].zh, GROUP_LABEL[d.group].en, nodeLabel(d, locale),
    ...d.inputs.map(p => p.type), ...d.outputs.map(p => p.type)].some(x => x.toLowerCase().includes(s)));
}

// ---- graph ---------------------------------------------------------------------------------------------------------
export type CfNode = {id: string; t: string; x: number; y: number; title: string; params?: Record<string, WidgetPrimitive>};
/** a = source node, as = output slot; b = target node, bs = input slot (index into def.inputs). */
export type CfEdge = {id: string; a: string; as: number; b: string; bs: number};
export type CfGraph = {nodes: CfNode[]; edges: CfEdge[]};
export type ConnectResult = {ok: true; graph: CfGraph; replaced?: string} | {ok: false; reason: 'type' | 'self' | 'slot' | 'cycle'; from?: string; to?: string};

let eseq = 0;
const reaches = (g: CfGraph, from: string, to: string): boolean => {
  const seen = new Set<string>(), st = [from];
  while (st.length) { const n = st.pop()!; if (n === to) return true; if (seen.has(n)) continue; seen.add(n); for (const e of g.edges) if (e.a === n) st.push(e.b); }
  return false;
};
/** Pure. Type-checked connect; like ComfyUI an input holds at most one link (a new link replaces the old one). */
export function connect(g: CfGraph, reg: Registry, a: string, as: number, b: string, bs: number): ConnectResult {
  if (a === b) return {ok: false, reason: 'self'};
  const na = g.nodes.find(n => n.id === a), nb = g.nodes.find(n => n.id === b);
  const out = na && reg.byName.get(na.t)?.outputs[as], inp = nb && reg.byName.get(nb.t)?.inputs[bs];
  if (!out || !inp) return {ok: false, reason: 'slot'};
  if (!typesCompatible(out.type, inp.type)) return {ok: false, reason: 'type', from: out.type, to: inp.type};
  if (reaches(g, b, a)) return {ok: false, reason: 'cycle'};
  const old = g.edges.find(e => e.b === b && e.bs === bs);
  const edge: CfEdge = {id: `e${Date.now().toString(36)}${(eseq++).toString(36)}`, a, as, b, bs};
  return {ok: true, graph: {nodes: g.nodes, edges: [...g.edges.filter(e => e !== old), edge]}, replaced: old?.id};
}
/** Load tolerant of the v1 lower format ({a,b} edges without slots): keeps nodes, re-validates every edge, drops bad ones. */
export function sanitizeGraph(raw: unknown, reg: Registry): CfGraph {
  const r = raw as {nodes?: unknown; edges?: unknown} | null;
  if (!r || !Array.isArray(r.nodes)) return {nodes: [], edges: []};
  const nodes = (r.nodes as CfNode[]).filter(n => n && typeof n.id === 'string' && typeof n.t === 'string')
    .map(n => {
      const params = sanitizeWidgetParams(reg.byName.get(n.t), n.params);
      return {id: n.id, t: n.t, x: Number(n.x) || 0, y: Number(n.y) || 0,
        title: typeof n.title === 'string' ? n.title : n.t, ...(params ? {params} : {})};
    });
  let g: CfGraph = {nodes, edges: []};
  for (const e of (Array.isArray(r.edges) ? r.edges : []) as Partial<CfEdge>[]) {
    if (!e || typeof e.a !== 'string' || typeof e.b !== 'string') continue;
    const res = connect(g, reg, e.a, Number(e.as) || 0, e.b, Number(e.bs) || 0);
    if (res.ok) g = {nodes, edges: res.graph.edges.map(x => (x.a === e.a && x.b === e.b && typeof e.id === 'string' ? {...x, id: e.id} : x))};
  }
  return g;
}
