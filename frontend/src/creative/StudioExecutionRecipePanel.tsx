import { Badge, Panel, StatusMessage } from '../ui/primitives';
import { buildStudioExecutionRecipeView, type StudioExecutionRecipeViewInput } from './studioExecutionRecipeView';

export type StudioExecutionRecipePanelProps = StudioExecutionRecipeViewInput;
const stack = { display: 'grid', gap: 'var(--space-2)', margin: 0 } as const;
const list = { ...stack, paddingInlineStart: 'var(--space-4)' };
const fields = { ...stack, gridTemplateColumns: 'max-content minmax(0, 1fr)', columnGap: 'var(--space-3)' };
const value = { margin: 0 };

/** Read-only explanation. Freshness, routing, source checks and all execution stay with the original owner. */
export function StudioExecutionRecipePanel(props: StudioExecutionRecipePanelProps) {
  const view = buildStudioExecutionRecipeView(props);
  if (view.state === 'stale') return null;
  return <Panel title="执行配方说明" className="studio-execution-recipe" aria-label="执行配方说明"
    style={{ minWidth: 0, maxWidth: '100%', overflowWrap: 'anywhere' }}>
    {view.state !== 'available' ? <StatusMessage tone="warning">{view.message}</StatusMessage> : <>
      <p><Badge tone="info">只读配方</Badge> <Badge tone="warning">执行未验证</Badge></p>
      <p>{view.message}</p>
      <dl style={fields}>
        <dt>操作</dt><dd style={value}><code>{view.operationId}</code></dd>
        <dt>适配器</dt><dd style={value}><code>{view.adapter}</code></dd>
        {view.recipeId && <><dt>配方标识</dt><dd style={value}><code>{view.recipeId}</code></dd></>}
        <dt>服务与模型</dt><dd style={value}>配方未提供 provider_id / model_id；见原预览或任务回执。下列组件名称来自原 workflow，不是路由选择。</dd>
        <dt>配方摘要</dt><dd style={value}><code>{view.digest}</code></dd>
      </dl>
      <p>步骤可见性：{view.visibility === 'visible' ? '已提供结构' : view.visibility === 'hidden' ? '内部不可见' : '不可用'}。本面板不执行任务。</p>
      {!!view.steps.length && <details open>
        <summary>原配方步骤（{view.steps.length}）</summary>
        <p>按配方记录展示；来源连线说明依赖，列表顺序不是执行日志。类型仅供说明。</p>
        <ul style={list} aria-label="原配方步骤">
          {view.steps.map(step => <li key={step.id}>
            <strong>{step.title}</strong> · <code>{step.classType}</code> · 节点 <code>{step.id}</code>
            <p><Badge tone={step.known ? 'neutral' : 'warning'}>{step.known ? '配方声明 · 执行未验证' : '未知步骤 · 执行未验证'}</Badge></p>
            <ul style={list} aria-label={`节点 ${step.id} 输入类型`}>
              {step.inputs.map(input => <li key={input.name}>
                <code>{input.name}</code>：<code>{input.type}</code>
                {input.recordedValue !== undefined && <> · 配方记录值 <code>{String(input.recordedValue)}</code></>}
                {input.source && <> · 来源 <code>{input.source}</code></>}
                {input.component && <> · 组件 <code>{input.component}</code></>}
              </li>)}
            </ul>
            {!step.inputs.length && <p>配方未记录输入。</p>}
            <p>输出类型：{step.outputs === null ? 'UNKNOWN（未提供端口说明）' : step.outputs.length
              ? step.outputs.map((type, index) => `${index}:${type}`).join(' / ') : '无数据输出端口；文件由原服务保存。'}</p>
          </li>)}
        </ul>
      </details>}
      <ul style={list} aria-label="配方证据边界">{view.notes.map(note => <li key={note}>{note}</li>)}</ul>
    </>}
  </Panel>;
}
