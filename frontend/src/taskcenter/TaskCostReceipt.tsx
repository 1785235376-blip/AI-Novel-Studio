import { Button, StatusMessage } from '../ui/primitives';
import { receiptAmount } from './taskCostReceipt';
import type { TaskCenterController } from './useTaskCenter';
import type { TaskCenterTask } from './taskCenterTypes';

const reasons = {
  UNSUPPORTED: '此任务没有已接入的原 broker 费用回执（媒体等来源仍为未知）。',
  MISSING: '当前可读历史中没有精确匹配的原任务回执；历史最多包含最近 100 条。',
  AMBIGUOUS: '同一原任务 ID 匹配到多条回执，不能确定归属。',
  INVALID: '回执字段、范围或费用语义无法验证。',
  UNREADABLE: '原 broker 回执当前不可读或功能未启用。',
};
export function TaskCostReceiptView({ controller, task }: { controller: TaskCenterController; task: TaskCenterTask }) {
  const selected = controller.costReceipt.selection;
  if (selected?.task !== task) return null;
  const value = selected.receipt;
  return <section className="task-center-batch" aria-label={`原任务费用回执 ${task.id}`}>
    <h4>原任务费用回执 · {task.id}</h4>
    <p>仅按原任务 ID 精确匹配当前身份、项目及分支下的 broker 账本；不改变任务或账本，不调用提供商。</p>
    {selected.loading && <StatusMessage>正在读取原 broker 费用回执…</StatusMessage>}
    {value?.kind === 'UNKNOWN' && <StatusMessage tone="warning">费用 UNKNOWN（未知）：{reasons[value.reason]}未知不代表免费。</StatusMessage>}
    {value?.kind === 'RECEIPT' && <>
      <dl>
        <div><dt>原账本回执</dt><dd>{value.id} · {value.status}</dd></div>
        <div><dt>回执 Provider / Model</dt><dd>{value.provider} · {value.model}（原账本记录，不是连接验证）</dd></div>
        <div><dt>预留预估</dt><dd>{receiptAmount(value.estimate)}</dd></div>
        <div><dt>实际金额记录</dt><dd>{receiptAmount(value.actual)}</dd></div>
        <div><dt>费用证据</dt><dd>{value.costState}</dd></div>
        <div><dt>价格来源 / 版本</dt><dd>{value.source ?? '未知'} · {value.priceVersion ?? '未提供'}</dd></div>
        <div><dt>合成状态</dt><dd>{value.synthetic === true ? '合成确定性适配器；合成零费用不是提供商账单' : value.synthetic === false ? '非合成价格记录' : '未知'}</dd></div>
      </dl>
      {value.costState === 'CALCULATED_FROM_REPORTED_USAGE' && <p>实际金额依据上游报告用量计算，不是提供商发票或账单。</p>}
      {value.costState === 'USER_REPORTED_UPSTREAM_BILL' && <p>此金额由用户登记，未由这里独立核验上游账单。</p>}
      {value.costState === 'NOT_DISPATCHED' && <p>原账本记录未派发，因此释放预留并记录零；不表示其他任务免费。</p>}
      {(value.actual === null || value.costState === 'UNKNOWN_UPSTREAM') && <StatusMessage tone="warning">实际费用 UNKNOWN（未知），不代表免费；预留预估不能当作最终费用。请在原服务核对，不会自动重试。</StatusMessage>}
    </>}
    <div className="task-center__actions">
      <Button disabled={!controller.canRead || selected.loading} onClick={() => void controller.costReceipt.read(task)}>重新读取此费用回执</Button>
      <Button onClick={controller.costReceipt.close}>关闭费用回执</Button>
    </div>
  </section>;
}
