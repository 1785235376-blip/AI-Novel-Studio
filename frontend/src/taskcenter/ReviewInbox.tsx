import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import {
  REVIEW_INBOX_ACTION_LABELS, REVIEW_INBOX_ACTIONS, TASK_CENTER_NOTICES, type ReviewInboxAction,
} from './taskCenterTypes';
import { batchActionAvailability, type TaskCenterController } from './useTaskCenter';
import { ReviewItemDetail } from './ReviewItemDetail';

function batchResultOf(controller: TaskCenterController, action: ReviewInboxAction) {
  const result = controller.results[`batch:${action}`];
  return result?.kind === 'batch' ? result : undefined;
}

function BatchPanel({ controller }: { controller: TaskCenterController }) {
  const selected = controller.selectedItems;
  const allowed = controller.reviewSummary.selected_batch_actions;
  /** `inbox.py::list()` 声明的动作全集；某个动作是否存在，只看领域是否真的声明了它。 */
  const exposed = REVIEW_INBOX_ACTIONS.filter(action =>
    (controller.inbox?.items ?? []).some(item => item.batch_actions.includes(action)));
  if (!exposed.length) return <StatusMessage>当前收件箱里没有领域声明可批量执行的动作，因此没有批量按钮。</StatusMessage>;
  return <section className="task-center-batch" aria-label="批量审核">
    <h4>{TASK_CENTER_NOTICES.batchPreviewTitle}</h4>
    {selected.length
      ? <ol>{selected.map(item => <li key={controller.itemKey(item)}>
        <code>{item.domain}:{item.id}</code> · v{item.version} · {item.status}{item.stale ? ' · 来源已变化' : ''}
      </li>)}</ol>
      : <p>尚未勾选任何候选。当前收件箱里原领域声明的批量动作：{exposed.map(action => REVIEW_INBOX_ACTION_LABELS[action]).join('、')}。勾选之后才会出现提交按钮。</p>}
    <p>{TASK_CENTER_NOTICES.batchPerItem}</p>
    <div className="task-center__actions">
      {selected.length > 0 && allowed.map(action => <Button key={action} variant={action === 'reject' ? 'danger' : 'secondary'}
        disabled={controller.pending[`batch:${action}`] === true || !controller.canRead}
        onClick={() => void controller.reviewBatch(selected, action)}>
        批量{REVIEW_INBOX_ACTION_LABELS[action]}（{selected.length} 项）
      </Button>)}
      <Button disabled={!selected.length} onClick={controller.clearSelection}>清空选择</Button>
    </div>
    {selected.length > 0 && allowed.length === 0 && <StatusMessage tone="warning">
      所选候选的原领域批量动作没有交集，或其中有过期/需原领域恢复的候选；因此没有可提交的批量按钮。
    </StatusMessage>}
    <p className="task-center-review__meta">
      只有所有选中项的原领域批量动作都允许时，对应按钮才出现；过期候选不会被批准。
    </p>
    {exposed.map(action => {
      const result = batchResultOf(controller, action);
      if (!result) return null;
      return <section key={action} aria-label={`批量${REVIEW_INBOX_ACTION_LABELS[action]}逐项结果`}>
        <StatusMessage tone={result.state === 'FAILED' ? 'warning' : 'success'}>{result.notice}</StatusMessage>
        {result.receipt && <ul className="task-center-review__fields">
          {result.receipt.results.map(row => <li key={`${row.domain}:${row.id}`}>
            <code>{row.domain}:{row.id}</code>
            <Badge tone={row.status === 'SUCCEEDED' ? 'success' : 'error'}>{row.status}</Badge>
            <span>{row.code ?? '已由原领域处理'}</span>
          </li>)}
        </ul>}
        {!!result.receipt?.results.some(row => row.status === 'FAILED') && <div className="task-center__actions">
          <Button onClick={() => controller.selectFailedFromLastBatch(action)}>只重新勾选失败项</Button>
        </div>}
      </section>;
    })}
  </section>;
}

/** 审核收件箱：不可读领域原样保留，批量是逐项 checkpoint，决定绑定候选版本。 */
export function ReviewInbox({ controller, panelId, labelledBy }: {
  controller: TaskCenterController; panelId?: string; labelledBy?: string;
}) {
  const { filters, setFilters } = controller;
  const items = controller.inbox?.items ?? [];
  const open = items.find(item => controller.itemKey(item) === controller.openItem);
  const inboxRead = controller.inbox !== undefined;
  return <section className="task-center-review" role="tabpanel" id={panelId} aria-labelledby={labelledBy} aria-label="审核收件箱">
    <form className="task-center__filters" onSubmit={event => { event.preventDefault(); controller.applyFilters(); }}>
      <label className="task-center__field"><span>审核领域（原服务参数）</span>
        <select value={filters.module} onChange={event => setFilters({ module: event.target.value })}>
          <option value="">全部领域</option>
          {controller.domainOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          {!!filters.module && !controller.domainOptions.some(option => option.value === filters.module)
            && <option value={filters.module}>{filters.module}</option>}
        </select>
      </label>
      <label className="task-center__field"><span>审核状态（领域词表，原样透传）</span>
        <input maxLength={64} value={filters.status} onChange={event => setFilters({ status: event.target.value })} />
      </label>
      <label className="task-center__field"><span>搜索候选</span>
        <input maxLength={400} value={filters.query} onChange={event => setFilters({ query: event.target.value })} />
      </label>
      <div className="task-center__actions">
        <Button type="submit" loading={controller.reviewState === 'LOADING'} disabled={!controller.canRead}>应用筛选并读取</Button>
        <Button type="button" onClick={controller.resetFilters}>清除筛选</Button>
        <Button type="button" onClick={() => void controller.reload()} disabled={!controller.canRead}>重新读取</Button>
      </div>
    </form>
    {controller.filtersDirty && <StatusMessage>筛选已修改，尚未应用；这里不会自动轮询。</StatusMessage>}
    <p>候选、来源版本与审核动作全部来自原领域；统一收件箱只做投影与转发，不改变 Canon、资产或领域状态。</p>
    <div className="task-center-summary__block" role="group" aria-label="审核收件箱概览">
      <h4>收件箱概览</h4>
      {!inboxRead && <p>尚未读取审核收件箱。打开这个队列时才会读取一次。</p>}
      {inboxRead && <>
        <p className="task-center-summary__meta">本页共 {controller.reviewSummary.total} 条审核项 · 来源已变化 {controller.reviewSummary.stale} 条 · 不可读领域 {controller.reviewSummary.unavailable} 个</p>
        <ul className="task-center-summary__counts">
          <li><Badge>{controller.reviewSummary.total}</Badge><span>审核项</span></li>
          <li><Badge tone="warning">{controller.reviewSummary.stale}</Badge><span>来源已变化</span></li>
          <li><Badge tone="error">{controller.reviewSummary.unavailable}</Badge><span>不可读领域</span></li>
        </ul>
        <p className="task-center-summary__meta">审批权属 {controller.reviewSummary.approval_authority} · 批量语义 {controller.reviewSummary.batch_semantics}</p>
        <p>{TASK_CENTER_NOTICES.batchPerItem}</p>
        <p>{TASK_CENTER_NOTICES.executionIsNotDelivery}</p>
      </>}
    </div>
    {!!controller.reviewProblem && <StatusMessage tone="error">{controller.reviewProblem.message} · {controller.reviewProblem.code}</StatusMessage>}
    {controller.reviewState === 'LOADING' && <StatusMessage>正在读取当前项目的审核收件箱…</StatusMessage>}
    {controller.reviewState === 'IDLE' && <EmptyState title="尚未读取审核收件箱" detail="打开队列后会读取一次；读取不会批准或执行任何动作。"/>}
    {controller.reviewState === 'EMPTY' && <EmptyState title="当前筛选下没有审核项" detail="原服务返回了空列表且没有不可读领域；这不是权限被拒绝。"/>}
    {controller.reviewState === 'DENIED' && !controller.reviewProblem && <>
      <EmptyState title="所有审核领域当前都不可读" detail="原领域拒绝了这些领域；空的收件箱不代表没有待审项。"/>
      {controller.inbox?.unavailable.map(entry => <StatusMessage tone="warning" key={entry.domain}>
        领域 {entry.domain} 当前不可读：{entry.reason}。其他被独立授权的领域仍然可用。
      </StatusMessage>)}
    </>}
    {controller.reviewState === 'DENIED' && controller.reviewProblem && <EmptyState title="当前会话无权读取审核收件箱" detail="先前数据已清除。重新核对项目、身份和分支后再打开。"/>}
    {controller.reviewState === 'FAILED' && <EmptyState title="审核收件箱读取失败" detail="可以重新读取；不会自动重试，也不会改变任何审核状态。"/>}
    {inboxRead && <>
      {!!controller.inbox?.unavailable.length && (controller.reviewState === 'READY' || controller.reviewState === 'DENIED')
        && <StatusMessage tone="warning">{TASK_CENTER_NOTICES.unavailableNotFullQueue}：
          {controller.inbox.unavailable.map(entry => `${entry.domain}（${entry.reason}）`).join('、')}
        </StatusMessage>}
      <BatchPanel controller={controller}/>
      <div className="task-center-review__grid">
        <ul className="task-center-review__list">
          {items.map(item => {
            const key = controller.itemKey(item);
            const selectable = batchActionAvailability([item]).length > 0;
            return <li key={key}>
              <article className="task-center-review__item" data-open={controller.openItem === key ? 'true' : 'false'}
                aria-label={`审核项 ${item.domain} ${item.id}`}>
                <header>
                  <h4>{item.preview.kind === 'text' && item.preview.text ? item.preview.text : item.id}</h4>
                  <Badge tone="info">{item.domain}</Badge>
                  <Badge tone={item.stale ? 'warning' : 'neutral'}>{item.status}</Badge>
                  {item.stale && <Badge tone="warning">来源已变化</Badge>}
                  {item.promotion_recovery_required && <Badge tone="warning">需原领域恢复</Badge>}
                </header>
                <p className="task-center-review__meta">
                  v{item.version} · {item.source || '来源未声明'} · 动作 {item.allowed_actions.join('、') || '无'}
                </p>
                <div className="task-center__actions">
                  <Button onClick={() => controller.setOpenItem(controller.openItem === key ? '' : key)}>
                    {controller.openItem === key ? '收起候选详情' : '查看候选详情'}
                  </Button>
                  {selectable && <label className="task-center__check">
                    <input type="checkbox" checked={controller.selected.includes(key)}
                      onChange={() => controller.toggleSelected(key)}/>加入批量集合
                  </label>}
                </div>
              </article>
            </li>;
          })}
          {items.length === 0 && <li><EmptyState title="当前领域/状态过滤下没有候选" detail="原服务的返回里有审核项，但都被筛选条件排除了。清除筛选可以看到全部。"/></li>}
        </ul>
        {open
          ? <ReviewItemDetail controller={controller} item={open}/>
          : <section className="task-center-review__detail" aria-label="审核项详情占位">
            <h4>候选详情</h4>
            <p>选择左侧任意候选以查看它的预览、输入摘要、来源版本与逐项决定；这里不会自动打开或自动决定任何候选。</p>
          </section>}
      </div>
    </>}
  </section>;
}
