import { Badge, Button, StatusMessage } from '../ui/primitives';
import { PRODUCTION_WORKFLOW_CONFLICT_NOTICE, type ProductionWorkflowController } from './useProductionWorkflow';
import { PRODUCTION_WORKFLOW_BOUNDS } from './productionWorkflowTypes';

export type ProductionIntentEditorProps = { controller: ProductionWorkflowController };

/**
 * Multi-select intent plus the owner's custom label and an explicit skip. Intent is a
 * presentation hint: saving it grants nothing and starts nothing.
 */
export function ProductionIntentEditor({ controller }: ProductionIntentEditorProps) {
  const intent = controller.projection?.creative_intent;
  if (!intent) return null;
  const locked = !controller.editable || controller.saving;
  const customLabel = controller.values.find(item => item.intent_id === controller.customId)?.label ?? '';
  return <section className="production-workflow-intent" aria-label="创作意图编辑">
    <header>
      <h3>创作意图</h3>
      <Badge tone="neutral">已保存 v{intent.version}</Badge>
      <Badge tone="info">{intent.history_retained ? '原服务保留历史' : '历史未确认'}</Badge>
    </header>
    <p>创作意图只影响提示与推荐布局，不是权限，也不会选择素材类型或执行任何任务。</p>
    <fieldset className="production-workflow-intent__values" disabled={locked}>
      <legend>创作意图选项</legend>
      {controller.values.map(item => <label key={item.intent_id}>
        <input type="checkbox" checked={item.selected} onChange={() => controller.toggleIntent(item.intent_id)} />
        <span>{item.label}</span>
      </label>)}
    </fieldset>
    {controller.customId && <label className="production-workflow-intent__custom">
      <span>自定义创作意图名称</span>
      <input value={customLabel} maxLength={PRODUCTION_WORKFLOW_BOUNDS.label} disabled={locked} onChange={event => controller.setCustomLabel(event.target.value)} />
    </label>}
    {controller.conflict && <StatusMessage tone="warning">
      版本冲突：{PRODUCTION_WORKFLOW_CONFLICT_NOTICE}
      <Button disabled={controller.saving} onClick={controller.acknowledgeConflict}>已核对，保留我的选择</Button>
    </StatusMessage>}
    {controller.customPending && <StatusMessage tone="warning">自定义创作意图需要 1–120 个字符的名称；当前输入仍保留。</StatusMessage>}
    {controller.problem && controller.state === 'READY' && <StatusMessage tone="error">{controller.problem.message} · {controller.problem.code}</StatusMessage>}
    {controller.notice && controller.state === 'READY' && <StatusMessage>{controller.notice}</StatusMessage>}
    <div className="production-workflow-intent__actions">
      <Button variant="primary" loading={controller.saving} disabled={!controller.canSubmit} onClick={() => void controller.submit()}>保存创作意图</Button>
      <Button disabled={controller.saving} onClick={controller.skip}>跳过（稍后设置）</Button>
    </div>
    {controller.dirty && <p>本地选择尚未保存；离开当前视图前会先确认。保存使用已读取的版本号，不会覆盖他人的更新。</p>}
  </section>;
}
