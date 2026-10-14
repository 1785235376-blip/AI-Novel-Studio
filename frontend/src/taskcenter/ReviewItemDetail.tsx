import { Badge, Button, StatusMessage } from '../ui/primitives';
import {
  REVIEW_INBOX_ACTION_LABELS, TASK_CENTER_NOTICES, type ReviewInboxField, type ReviewInboxItem,
} from './taskCenterTypes';
import { reviewActionAvailability, type TaskCenterController } from './useTaskCenter';

function Fields({ label, fields }: { label: string; fields: ReviewInboxField[] }) {
  if (!fields.length) return <p>{label}：原服务未提供。</p>;
  return <section aria-label={label}>
    <h4>{label}</h4>
    <ul className="task-center-review__fields">{fields.map(field => <li key={field.key}>
      <code>{field.key}</code><span>{field.value === '' ? '—' : field.value}</span>
    </li>)}</ul>
  </section>;
}

/**
 * 单个审核候选：候选预览、输入与来源摘要、来源版本、结果差异与绑定到实际版本+摘要的决定。
 * 按钮只来自 `allowed_actions`；领域要求自己的恢复流程时一个普通审核按钮都不显示。
 */
export function ReviewItemDetail({ controller, item }: { controller: TaskCenterController; item: ReviewInboxItem }) {
  const key = controller.itemKey(item);
  const result = controller.results[`review:${key}`];
  const pending = controller.pending[`review:${key}`] === true;
  const actions = reviewActionAvailability(item);
  const submitted = result?.kind === 'review' && result.state === 'SUCCEEDED' && result.expected_version === item.version;
  return <section className="task-center-review__detail" aria-label={`审核项详情 ${item.domain} ${item.id}`}>
    <header className="task-center-review__item">
      <h4>{item.preview.kind === 'text' && item.preview.text ? item.preview.text : item.id}</h4>
      <Badge tone="info">{item.domain}</Badge>
      <Badge tone={item.stale ? 'warning' : 'neutral'}>{item.status}</Badge>
      {item.stale && <Badge tone="warning">来源已变化</Badge>}
      <span className="task-center-review__meta">v{item.version}</span>
    </header>
    {item.preview.kind === 'text'
      ? <p className="task-center-review__preview">{item.preview.text || '原服务没有提供候选预览文本。'}</p>
      : <Fields label="候选预览" fields={item.preview.fields}/>}
    <Fields label="输入与来源摘要" fields={[
      { key: 'source', value: item.source },
      { key: 'created_by', value: item.created_by },
      { key: 'risk', value: item.risk },
      { key: 'privacy_state', value: item.privacy_state },
      { key: 'project', value: item.project },
      { key: 'workspace', value: item.workspace ?? '—' },
      { key: 'branch', value: item.branch ?? '—' },
      { key: 'scope', value: `${item.scope.mode} · ${item.scope.novel_id}` },
    ]}/>
    <Fields label="来源版本" fields={item.source_versions}/>
    <Fields label="目标与结果差异" fields={[
      ...item.target,
      { key: 'source_hash', value: item.source_hash || '原服务未提供摘要' },
      ...(item.target_navigation_contract ? [{ key: 'navigation_contract', value: item.target_navigation_contract }] : []),
      ...(item.recovery_state ? [{ key: 'recovery_state', value: item.recovery_state }] : []),
    ]}/>
    <p>这是等待人工审核的候选与它的来源证据，不是已交付的正式结果；决定由原领域审核服务执行。</p>
    {item.promotion_recovery_required && <StatusMessage tone="warning">
      此候选的原领域把批准写入标记为未完成（状态 {item.status}{item.recovery_state ? ` · ${item.recovery_state}` : ''}）。
      这里的恢复按钮不存在：请回到原领域面板完成它自己的恢复流程，本视图不会自动重试、恢复或批准。
    </StatusMessage>}
    {actions.length === 0 && !item.promotion_recovery_required && <StatusMessage>
      此领域当前状态仅供查看：原 owner 没有声明可用的审核动作，因此这里没有按钮。
    </StatusMessage>}
    {actions.length > 0 && <div className="task-center__actions">
      {actions.map(action => <Button key={action} variant={action === 'reject' ? 'danger' : 'primary'}
        disabled={pending || submitted || !controller.canRead}
        onClick={() => void controller.reviewItem(item, action)}>
        {REVIEW_INBOX_ACTION_LABELS[action]}
      </Button>)}
    </div>}
    <p className="task-center-review__meta">
      提交决定时会绑定当前候选版本 v{item.version} 与来源摘要 {item.source_hash || '（原服务未提供）'}；版本已变化时原领域会拒绝，本地也不会重复提交同一版本。
    </p>
    <div className="task-center__actions">
      <Button disabled={!controller.canRead} onClick={() => controller.navigateItem(item)}>定位原审核项</Button>
    </div>
    {submitted && <StatusMessage tone="success">
      {TASK_CENTER_NOTICES.reviewDuplicateGuard}（已提交版本 v{item.version}）
    </StatusMessage>}
    {result?.kind === 'review' && !submitted && <StatusMessage tone={result.state === 'FAILED' ? 'error' : 'info'}>
      {result.notice}
    </StatusMessage>}
  </section>;
}
