import { Badge, Button, StatusMessage } from '../ui/primitives';
import { STUDIO_ENTRY_CONTRACT, STUDIO_INTENT_CATALOG } from './studioEntryTypes';
import type { StudioEntryController } from './useStudioEntry';
import './studioEntry.css';

/**
 * Multi-select creative intent with an editable custom label and an explicit skip.
 * Intent is a presentation hint only: it never grants a permission, never restricts an
 * available module and never triggers a generation.
 */
export function IntentPicker({ controller }: { controller: StudioEntryController }) {
  const locked = controller.saving || controller.state === 'denied' || controller.state === 'missing';
  const custom = controller.values.find(item => item.intent_id === controller.customId);
  return <section className="studio-entry-intent" aria-label="创作意图设置">
    <header className="studio-entry-intent__header">
      <h3>创作意图</h3>
      {controller.intent
        ? <Badge tone="neutral">已保存 v{controller.intent.version}</Badge>
        : <Badge tone="neutral">尚未保存</Badge>}
      {controller.dirty && <Badge tone="info">未保存的本地选择</Badge>}
    </header>
    <p className="studio-entry-intent__scope">{STUDIO_ENTRY_CONTRACT.notices.intent_scope}</p>
    <fieldset className="studio-entry-intent__values" disabled={locked}>
      <legend>可多选，可随时修改或跳过</legend>
      {controller.values.map(item => <label key={item.intent_id} className="studio-entry-intent__value">
        <input type="checkbox" checked={item.selected} onChange={() => controller.toggleIntent(item.intent_id)} />
        <span>{item.label}</span>
      </label>)}
    </fieldset>
    {custom && <label className="studio-entry-intent__custom">
      <span>自定义创作意图名称</span>
      <input
        value={custom.label} maxLength={STUDIO_ENTRY_CONTRACT.bounds.label} disabled={locked}
        onChange={event => controller.setCustomLabel(event.target.value)}
      />
    </label>}
    {controller.customPending && <StatusMessage tone="warning">{STUDIO_ENTRY_CONTRACT.messages.custom_incomplete}当前输入仍保留。</StatusMessage>}
    {controller.conflict && <StatusMessage tone="warning">
      版本冲突：{STUDIO_ENTRY_CONTRACT.messages.conflict_reread}
      <Button disabled={controller.saving} onClick={controller.acknowledgeConflict}>已核对，保留我的选择</Button>
    </StatusMessage>}
    {controller.problem && <StatusMessage tone="error">{controller.problem.message} · {controller.problem.code}</StatusMessage>}
    {controller.notice && <StatusMessage>{controller.notice}</StatusMessage>}
    <div className="studio-entry-intent__actions">
      <Button variant="primary" loading={controller.saving} disabled={!controller.canSave} onClick={() => void controller.saveIntent()}>保存创作意图</Button>
      <Button disabled={controller.saving} onClick={controller.skipIntent}>跳过（稍后设置）</Button>
    </div>
    {controller.dirty && <p className="studio-entry-intent__dirty">本地选择尚未保存。保存使用已读取的版本号，不会覆盖其他会话的更新。</p>}
  </section>;
}

/** The declared vocabulary, rendered for callers that need a legend without a controller. */
export const STUDIO_INTENT_OPTIONS = STUDIO_INTENT_CATALOG;
