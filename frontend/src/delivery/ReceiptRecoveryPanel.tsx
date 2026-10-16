import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import {
  DELIVERY_JOB_STATUS_LABELS, DELIVERY_NOTICES, DELIVERY_RECEIPT_STATE_LABELS,
  type DeliveryAttempt, type DeliveryReceiptPage, type DeliveryRequest, type DeliveryRecovery,
  type DeliverySurfaceState,
} from './deliveryTypes';
import './deliveryCenter.css';

/**
 * 回执恢复面：把 `DISPATCHED` / `UNKNOWN` / `RETURNED` 三态显示清楚，并把恢复做成
 * "复原原请求 + 重新读取原回执"。
 *
 * **丢失或未知的回执永远不会显示成成功**：只有原导出 owner 自己返回
 * `status === 'succeeded'` 时才出现"已完成"徽标；`UNKNOWN` 一律显示为"回执未知"，
 * 并给出原请求参数（`dispatched: false`）与只读的重新读取路径。
 *
 * 这里的两个按钮都只调用 `onRecover`（→ `GET /api/exports/{id}` 或
 * `GET /api/exports?novel_id=…`）。面板里没有派发、取消或重试按钮 —— 本目录没有这样的
 * 方法可用。
 */
export type ReceiptRecoveryPanelProps = {
  state: DeliverySurfaceState;
  page: DeliveryReceiptPage | undefined;
  attempts: DeliveryAttempt[];
  lastRequest: DeliveryRequest | null;
  lastRecovery: DeliveryRecovery | null;
  onRecover: (idempotencyKey: string, jobId?: string) => Promise<void> | void;
};

export function ReceiptRecoveryPanel(props: ReceiptRecoveryPanelProps) {
  const receipts = props.page?.items ?? [];
  const unknown = props.attempts.filter(attempt => !attempt.receipt);
  const pending = receipts.filter(receipt => receipt.status === 'queued' || receipt.status === 'running');
  return <section className="delivery-receipts" aria-label="导出回执与恢复">
    <header className="delivery-receipts__head">
      <h3>导出回执与恢复</h3>
      <Badge tone={props.state === 'DENIED' ? 'error' : receipts.length ? 'info' : 'neutral'}>
        {props.state === 'DENIED' ? '无权限' : `${receipts.length} 条回执`}
      </Badge>
    </header>
    <p className="delivery-center__help">{DELIVERY_NOTICES.receiptUnknown}{DELIVERY_NOTICES.readOnlyRecovery}</p>

    {props.state === 'DENIED' && <div className="delivery-center__denied" role="alert">
      <strong>没有权限读取导出回执</strong>
      <p>被拒绝的读取不会显示成"没有记录"：这里不显示空列表，也不显示任何成功状态。</p>
    </div>}

    {!!props.lastRecovery && <div className="delivery-receipts__recovery">
      <h4>原请求的只读复原（{DELIVERY_RECEIPT_STATE_LABELS[props.lastRecovery.state]}）</h4>
      <dl className="delivery-center__counts">
        <div><dt>幂等键</dt><dd><code>{props.lastRequest?.idempotency_key ?? '—'}</code></dd></div>
        <div><dt>格式</dt><dd>{props.lastRequest?.format ?? '—'}</dd></div>
        <div><dt>分支</dt><dd>{props.lastRequest?.branch_id ?? '本地项目范围'}</dd></div>
        <div><dt>请求时刻</dt><dd>{props.lastRequest?.requested_at ?? '—'}</dd></div>
        <div><dt>是否可再次派发</dt><dd>{props.lastRecovery.original_request?.dispatched === false ? '否 — 只复原原请求' : '没有可复原的请求记录'}</dd></div>
        <div><dt>恢复机器码</dt><dd><code>{props.lastRecovery.code}</code></dd></div>
        <div><dt>已确认成功</dt><dd>{props.lastRecovery.confirmed_success ? '是（原 owner 判定）' : '否'}</dd></div>
      </dl>
      <p className="delivery-center__help">{props.lastRecovery.instruction}</p>
      {props.lastRecovery.read && <p className="delivery-center__help">
        只读恢复路径：<code>{props.lastRecovery.read.method} {props.lastRecovery.read.path}</code>
      </p>}
      {props.lastRecovery.owner_retry_path && <p className="delivery-center__help">
        原 owner 的重试端点（{DELIVERY_NOTICES.opOnly}）：<code>{props.lastRecovery.owner_retry_path}</code>
      </p>}
      {props.lastRequest && <Button type="button" variant="secondary"
        onClick={() => void props.onRecover(props.lastRequest!.idempotency_key)}>按同一幂等键重新读取原回执</Button>}
    </div>}

    {!!unknown.length && <div className="delivery-receipts__unknown">
      <h4>尚未拿到回执的请求（{unknown.length} 条）</h4>
      <ul>
        {unknown.map(attempt => <li key={attempt.request.idempotency_key} data-receipt-state="UNKNOWN">
          <code>{attempt.request.idempotency_key}</code> · {attempt.request.format} · {DELIVERY_RECEIPT_STATE_LABELS.UNKNOWN}
          <Button type="button" variant="ghost" onClick={() => void props.onRecover(attempt.request.idempotency_key)}>重新读取原回执</Button>
        </li>)}
      </ul>
      <p className="delivery-center__help">这些请求的结果未知，因此不会显示成功；恢复只重新读取同一幂等键下的原任务。</p>
    </div>}

    {!receipts.length && props.state !== 'DENIED' && <EmptyState title="还没有读取到回执"
      detail="原导出服务在该项目下没有返回任何回执；这不等于导出成功，也不等于项目没有内容。" />}

    {!!receipts.length && <ul className="delivery-receipts__list">
      {receipts.map(receipt => <li key={receipt.id} data-status={receipt.status} className="delivery-receipts__row">
        <strong>{receipt.id.slice(0, 8)}</strong>
        <span>{receipt.format}</span>
        <Badge tone={receipt.status === 'succeeded' ? 'success' : receipt.status === 'failed' ? 'error'
          : receipt.status === 'cancelled' ? 'warning' : 'info'}>
          {receipt.raw_status ? '结果未知' : DELIVERY_JOB_STATUS_LABELS[receipt.status]}
        </Badge>
        <span>{receipt.progress_message || '无进度说明'} · {receipt.progress}%</span>
        <span>第 {receipt.attempt} 次</span>
        <span>原 owner 恢复 {receipt.recovery_count} 次</span>
        <span>{receipt.result_filename ?? '没有文件名（未确认完成）'}</span>
        {receipt.raw_status && <span className="delivery-center__help">原服务返回了未定义状态 <code>{receipt.raw_status}</code>，这里不猜测成完成。</span>}
        {!!receipt.missing_resources.length && <span className="delivery-center__help">缺少 {receipt.missing_resources.length} 项资源，资源包不会生成不完整文件。</span>}
        {receipt.error && <span className="delivery-center__help">原 owner 错误码 <code>{receipt.error.code}</code>：{receipt.error.message}</span>}
        <Button type="button" variant="ghost" disabled={!props.attempts.length}
          onClick={() => void props.onRecover('', receipt.id)}>按回执 id 重新读取</Button>
      </li>)}
    </ul>}

    {!!pending.length && <StatusMessage tone="info">
      原导出服务报告 {pending.length} 条任务尚未终结；本目录不会自动轮询，请按需重新读取。
    </StatusMessage>}
  </section>;
}
