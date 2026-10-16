import { Badge, EmptyState, StatusMessage } from '../ui/primitives';
import { exportStatus, limitsNotice } from './timelineOps';
import type { NleUsage } from './timelineOpsTypes';
import './timelineWorkspace.css';

/**
 * 交付面板：审核预览画质与交付成片画质**分开陈述**，
 * 任何情况下都不会把预览写成成片；同时在上限到来之前说明既有上限。
 */
export type ExportDeliveryPanelProps = {
  exportReceipt?: unknown;
  limits?: unknown;
  usage?: NleUsage;
};

export function ExportDeliveryPanel(props: ExportDeliveryPanelProps) {
  const status = exportStatus(props.exportReceipt);
  const notice = limitsNotice(props.limits, props.usage ?? null);
  return <section className="nle-delivery" aria-label="交付" data-stage={status.stage} data-delivery-ready={status.deliveryReady}>
    <h3>预览与交付</h3>
    <p className="nle-delivery__head" data-requested-quality={status.requestedQuality ?? 'NONE'}>{status.head}</p>
    <p className="nle-delivery__detail">{status.detail}</p>
    <dl className="nle-delivery__limits">
      <div><dt>渲染超时</dt><dd>{status.limits ? `${status.limits.renderTimeoutSeconds} 秒` : '未提供'}</dd></div>
      <div><dt>输出上限</dt><dd>{status.limits ? `${status.limits.maxOutputBytes} 字节` : '未提供'}</dd></div>
      <div><dt>请求标识</dt><dd><code>{status.requestId ?? '—'}</code></dd></div>
      <div><dt>预览摘要</dt><dd><code>{status.previewDigest ?? '—'}</code></dd></div>
    </dl>
    <div className="nle-delivery__qualities">
      <div className="nle-delivery__quality" data-quality="PREVIEW" data-present={status.previewQuality !== null}>
        <h4>审核预览画质</h4>
        {status.previewQuality
          ? <><p>{status.previewQuality.label}</p><p>{status.previewQuality.detail}</p><Badge tone="warning">{status.previewQuality.preset}</Badge></>
          : <p>本次不是审核预览预设。</p>}
      </div>
      <div className="nle-delivery__quality" data-quality="FINAL" data-present={status.finalExportQuality !== null}>
        <h4>交付成片画质</h4>
        {status.finalExportQuality
          ? <><p>{status.finalExportQuality.label}</p><p>{status.finalExportQuality.detail}</p><Badge tone="info">{status.finalExportQuality.preset}</Badge></>
          : <p>没有交付预设的回执；预设本身不代表已经产成交付成片。</p>}
      </div>
    </div>
    <p className="nle-delivery__honesty" data-honest="true">本界面不声明已交付：产物仍是私有候选，需要在制作任务中预览并人工审核（product_acceptance: LOCAL_REQUIRED）。</p>
    {status.code && <StatusMessage tone="error">回执状态码 {status.code}</StatusMessage>}
    {status.warnings.map(warning => <StatusMessage key={warning} tone="warning">{warning}</StatusMessage>)}
    <h3>既有上限（触界之前说明）</h3>
    {notice.code === 'NLE_LIMITS_SHAPE_INVALID' && <StatusMessage tone="error">上限或用量字段原契约不认识，已按原 owner 的冻结上限显示。</StatusMessage>}
    {notice.raiseRefused && <div data-raise-refused="true">
      <StatusMessage tone="warning">
        收到高于原 owner 的上限值，已拒绝按其提高：
        {notice.refusedRaises.map(item => `${item.key}（提供 ${item.offered} > 原 ${item.ownerLimit}）`).join('；')}。这里始终使用原上限。
      </StatusMessage>
    </div>}
    {notice.nearAny && notice.warnings.map(warning => <StatusMessage key={warning} tone="warning">{warning}</StatusMessage>)}
    <table className="nle-delivery__table">
      <caption>原 owner 上限与当前用量</caption>
      <thead><tr><th scope="col">项目</th><th scope="col">上限</th><th scope="col">已用</th><th scope="col">剩余</th><th scope="col">来源</th></tr></thead>
      <tbody>{notice.rows.map(row => <tr key={row.key} data-limit-key={row.key} data-near={row.near} data-reached={row.reached}>
        <th scope="row">{row.label}</th>
        <td>{row.ownerLimit} {row.unit}</td>
        <td>{row.used === null ? '—' : `${row.used} ${row.unit}`}</td>
        <td>{row.remaining === null ? '—' : `${row.remaining} ${row.unit}`}</td>
        <td><code>{row.source}</code></td>
      </tr>)}</tbody>
    </table>
    <p className="nle-delivery__advice">{notice.splitAdvice}</p>
    {!notice.rows.length && <EmptyState title="上限不可用" detail="没有可核对的上限或用量数据。" />}
  </section>;
}
