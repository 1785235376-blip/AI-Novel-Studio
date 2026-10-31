import { Badge, StatusMessage } from '../ui/primitives';
import type { SyncRecovery, SyncRow } from './offlineSyncClient';

const labels: Record<string, string> = {
  CHECKPOINT_UNCHANGED: '原检查点仍在',
  MATCHES_INTENT_UNCONFIRMED: '当前内容符合预期，但不能证明本次写入已经执行（也可能原本相同）',
  DIVERGED_OR_PARTIAL: '当前状态已分歧或只完成了一部分',
};

/** Presentation of the original recovery observations only. Never inspect or
 * serialize manuscript bodies, hidden snapshots, titles or content fingerprints. */
export function OfflineSyncRecoveryStatus({ row, recovery }: { row: SyncRow; recovery: SyncRecovery }) {
  const current = recovery.id === row.id && recovery.version === row.version;
  const withdrawn = row.selection_withdrawn || recovery.selection_withdrawn;
  const target = row.target_chapter_id;
  const observations = current && !withdrawn ? recovery.observations : [];
  const matches = target ? observations.filter(item => item.chapter_id === target) : [];
  const observation = matches.length === 1 ? matches[0] : undefined;
  return <section aria-label="未知写入状态比较">
    <h4>原服务的当前观察</h4>
    {!current || withdrawn || recovery.target_already_selected ? <StatusMessage tone="warning">
      目前无法核实。{withdrawn ? '此章节已退出交换范围。' : recovery.target_already_selected ? '新增候选已另行加入范围，不能在此重新绑定。' : '观察对应的记录版本已变化，请重新读取。'}
    </StatusMessage> : !target ? <>
      <StatusMessage tone="warning">新增请求尚未绑定原章节，写入结果仍未知；不能把内容相同的候选当作本次写入的完成凭据。</StatusMessage>
      {!!observations.length && <ul>{observations.map(item => <li key={item.chapter_id}>当前可读候选 {item.chapter_id} · v{item.version}</li>)}</ul>}
    </> : observation && labels[observation.state] ? <>
      <Badge>{labels[observation.state]}</Badge>
      <p>当前章节 {observation.chapter_id} · v{observation.version}</p>
      {observation.state === 'CHECKPOINT_UNCHANGED' && <p>当前读回快照与原检查点完全一致；这不是写入完成的凭据。</p>}
      {observation.state === 'DIVERGED_OR_PARTIAL' && <p>当前读回状态既不符合预期，也不等于原检查点；请在原编辑器核对，不要重放未知请求。</p>}
    </> : <StatusMessage tone="warning">目前无法核实目标章节；没有可用于比较的当前授权观察。</StatusMessage>}
    <details><summary>这些状态比较什么</summary>
      <p>原检查点一致比较章节标识、版本、归档状态、标题和正文的完整读回快照。预期一致只比较未归档正文；若预期是归档，则只检查归档状态，不比较标题或版本。</p>
      <p>原服务优先报告预期一致，未另行区分它是否也与检查点一致。内容吻合可能原本就存在，不能证明这次请求执行过。</p>
    </details>
    <p>这里只显示上次明确读取时的原服务状态和版本；后续修改需重新核对。不显示历史检查点或预期正文，详细内容仍须通过原编辑器及其授权历史入口核对。</p>
    <p>是否可人工采用由原服务决定；关闭记录也不证明没有写入。不会自动重试。</p>
  </section>;
}
