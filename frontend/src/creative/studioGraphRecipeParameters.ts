import type { ProductionProvider } from './studioProductionClient';
import type { StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';

export type GraphRecipeParameterFields = { steps: string; seed: string; cfg?: string };
const recipes = new Set(['comfy-sd-checkpoint-v1', 'comfy-flux1-v1', 'comfy-qwen-image-v1']);
export const GRAPH_RECIPE_PARAMETER_LIMITS = { steps: { min: 1, max: 150 }, seed: { min: 0, max: 2147483647 } } as const;
export function graphRecipeCfgControl(provider?: ProductionProvider) {
  const value = provider?.image_capabilities?.cfg;
  return provider?.local && provider.operation_id === 'm5.image.t2i' && provider.image_capabilities?.recipe_id === 'comfy-sd-checkpoint-v1'
    && provider.supported_parameters.includes('cfg') && value && [value.min, value.max, value.default].every(Number.isFinite)
    && 0 <= value.min && value.min <= 7 && value.default === 7 && 7 <= value.max && value.max <= 100 ? value : null;
}

/** A display/editing scope, never provider admission or a workflow compiler. */
export function graphRecipeParameterSupport(node?: StudioGraphNode, provider?: ProductionProvider): string | null {
  if (node?.definition_id !== 'image_generate' || node.parameters.operation_id !== 'm5.image.t2i')
    return '本首片只编辑图片生成节点的文生图采样参数；其他操作仍使用原节点控件。';
  if (!provider || provider.operation_id !== node.parameters.operation_id || provider.provider_id !== node.parameters.provider_id
    || provider.model_id !== node.parameters.model_id)
    return '请先读取节点服务配置并核对当前服务商与模型；不根据手填标识推断配方能力。';
  if (!provider.local || !provider.image_capabilities || !recipes.has(provider.image_capabilities.recipe_id))
    return '当前配置不属于本首片的本地 Comfy 图片配方。云 API 内部步骤保持不可见，其他适配器不在此编辑。';
  if (!['steps', 'seed'].every(key => provider.supported_parameters.includes(key)))
    return '当前配置未同时声明 steps 与 seed，不能在此应用采样配置。';
  return null;
}

export function graphRecipeParameterFields(node: StudioGraphNode): GraphRecipeParameterFields {
  const parameters = node.parameters.parameters ?? {};
  return { steps: parameters.steps == null ? '' : String(parameters.steps), seed: parameters.seed == null ? '' : String(parameters.seed),
    ...(parameters.cfg == null ? {} : { cfg: String(parameters.cfg) }) };
}

export function checkedGraphRecipeParameters(fields: GraphRecipeParameterFields, provider?: ProductionProvider): Partial<Record<keyof GraphRecipeParameterFields, number>> {
  if (!fields || typeof fields !== 'object' || Array.isArray(fields) || Object.keys(fields).some(key => !['steps', 'seed', 'cfg'].includes(key)))
    throw new Error('采样表单只接受 steps、seed 与已声明的 cfg。');
  const result: Partial<Record<keyof GraphRecipeParameterFields, number>> = {};
  for (const key of ['steps', 'seed'] as const) {
    const input = fields[key];
    if (input === '') continue; // Omission retains the original compiler's default; never invent it here.
    const limit = GRAPH_RECIPE_PARAMETER_LIMITS[key], value = Number(input);
    if (typeof input !== 'string' || !/^\d+$/.test(input) || !Number.isSafeInteger(value) || value < limit.min || value > limit.max)
      throw new Error(`${key === 'steps' ? '采样步数' : '种子'}须为 ${limit.min} 至 ${limit.max} 的整数，或留空使用原配方默认值。`);
    result[key] = value;
  }
  if (Object.hasOwn(fields, 'cfg') && fields.cfg !== '') {
    const control = graphRecipeCfgControl(provider), value = Number(fields.cfg);
    if (!control) throw new Error('当前已绑定配置未声明可编辑 cfg 范围。');
    if (typeof fields.cfg !== 'string' || !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(fields.cfg) || !Number.isFinite(value) || value < control.min || value > control.max)
      throw new Error(`cfg 须为 ${control.min} 至 ${control.max} 的有限数值，或留空使用原默认值。`);
    result.cfg = value;
  }
  return result;
}

/** Patch only the original node parameters. Pins, provider, consent, topology and other fields remain original. */
export function applyGraphRecipeParameters(definition: StudioGraphDefinition, nodeId: string,
  provider: ProductionProvider, fields: GraphRecipeParameterFields): StudioGraphDefinition {
  if (definition.schema_version !== 4) throw new Error('此编辑入口仅接受原图片图 v4。');
  const node = definition.nodes.find(row => row.id === nodeId), reason = graphRecipeParameterSupport(node, provider);
  if (!node || reason) throw new Error(reason ?? '原图片节点不可用。');
  if (Object.hasOwn(fields, 'cfg') && !graphRecipeCfgControl(provider)) throw new Error('当前已绑定配置不支持应用 cfg。');
  const checked = checkedGraphRecipeParameters(fields, provider), parameters = { ...node.parameters.parameters };
  delete parameters.steps; delete parameters.seed;
  if (Object.hasOwn(fields, 'cfg')) delete parameters.cfg;
  Object.assign(parameters, checked);
  return { ...definition, nodes: definition.nodes.map(row => row.id === nodeId
    ? { ...row, parameters: { ...row.parameters, parameters } } : row) };
}
