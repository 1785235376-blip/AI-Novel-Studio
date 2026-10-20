import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { GRAPH_RECIPE_PARAMETER_LIMITS } from './studioGraphRecipeParameters';
import type { StudioGraphRecipeParameterState } from './useStudioGraphRecipeParameters';

export function StudioGraphRecipeParameterPanel({ state, nodeId, provider, model, recipeId, canRead, readConfiguration }:
  { state: StudioGraphRecipeParameterState; nodeId: string; provider?: string | null; model?: string | null; recipeId?: string;
    canRead: boolean; readConfiguration: () => void }) {
  return <Panel title="执行流程 · 图片采样配置" aria-label="执行流程参数编辑" style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
    <p><Badge tone={state.formDirty ? 'warning' : 'neutral'}>{state.formDirty ? '表单未应用' : '原图参数'}</Badge> 节点 <code>{nodeId}</code></p>
    <p>服务商 <code>{provider || '未选择'}</code> · 模型 <code>{model || '未选择'}</code>{recipeId && <> · 配方 <code>{recipeId}</code></>}</p>
    <Button disabled={!canRead} onClick={readConfiguration}>核对本节点配置</Button>
    {state.reason && <StatusMessage tone="warning">{state.reason}</StatusMessage>}
    {!state.reason && <p>原 Comfy 配方将 steps / seed 编译到 KSampler 的采样步数与种子。已声明范围的 SD 文生图可编辑 cfg；编码、模型组件、采样算法及解码仍由原固定配方提供，此处不增删内部节点。</p>}
    <fieldset disabled={!state.canEdit}><legend>准备应用的采样参数</legend>
      {(['steps', 'seed'] as const).map(key => <label key={key}>{key === 'steps' ? '执行流程采样步数' : '执行流程种子'}
        <input inputMode="numeric" type="text" maxLength={32} value={state.fields[key]} aria-label={key === 'steps' ? '执行流程采样步数' : '执行流程种子'}
          placeholder={`${GRAPH_RECIPE_PARAMETER_LIMITS[key].min}–${GRAPH_RECIPE_PARAMETER_LIMITS[key].max}；留空用原默认值`}
          onChange={event => state.edit(key, event.target.value)} />
      </label>)}
      {state.cfgControl && <label>执行流程 CFG 引导强度
        <input inputMode="decimal" type="text" maxLength={32} value={state.fields.cfg ?? ''} aria-label="执行流程 CFG 引导强度"
          placeholder={`${state.cfgControl.min}–${state.cfgControl.max}；留空用原默认值 ${state.cfgControl.default}`}
          onChange={event => state.edit('cfg', event.target.value)} />
      </label>}
    </fieldset>
    {!state.reason && !state.cfgControl && <p>当前已绑定配置未声明可编辑 cfg 范围，cfg 保持原配方预设。steps / seed 仍使用原支持范围。</p>}
    {state.stale && <StatusMessage tone="warning">原图、选择、配置或权限已变化，本次表单已过期。请放弃表单后重新核对；旧应用操作不会恢复。</StatusMessage>}
    {state.error && <StatusMessage tone="warning">{state.error}</StatusMessage>}
    <div className="studio-graph-actions">
      <Button variant="primary" disabled={!state.canApply} onClick={state.apply}>应用采样参数到原图草稿</Button>
      <Button disabled={!state.formDirty && !state.stale} onClick={state.clear}>放弃未应用采样参数</Button>
    </div>
    <p>填写只保留在当前会话。应用后可用原图撤销／重做，再明确保存并重开；随后须重新预检和核对真实配方。保存、预览与执行分别确认，不调用模型。</p>
  </Panel>;
}
