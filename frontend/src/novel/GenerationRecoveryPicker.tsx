import { useMemo, useState } from 'react';
import { generationRecovery, type RecoverableGeneration } from '../generationRecovery';
import { Button, Panel } from '../ui/primitives';

const taskIds = (value: RecoverableGeneration) => value.jobId ?? value.variants?.map(item => item.id).join(', ') ?? '';
export function GenerationRecoveryPicker({ namespace, chapterId, actorId, revision, includeCurrent=false, onRecover }: {
  namespace: string; chapterId: string; actorId?: string; revision: number; includeCurrent?: boolean;
  onRecover: (value: RecoverableGeneration) => Promise<void>;
}) {
  const [page, setPage] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const records = useMemo(() => {
    const current = generationRecovery.load(namespace, chapterId);
    const retained = generationRecovery.history(namespace, chapterId).filter(value => taskIds(value) !== (current && taskIds(current))).reverse();
    return [...(includeCurrent && current ? [current] : []), ...retained].filter(value => value.chapterId === chapterId
      && (value.actorId === undefined || value.actorId === actorId));
  }, [namespace, chapterId, actorId, revision, includeCurrent]);
  if (!records.length) return null;
  const currentPage = Math.min(page, Math.floor((records.length - 1) / 5));
  return <Panel title="保留的生成任务" aria-label="保留的生成任务">
    <p>仅列出当前章节的任务编号。重新打开前会向服务端核对权限和来源；不会重新生成或取消任务。</p>
    <ul>{records.slice(currentPage * 5, currentPage * 5 + 5).map(value => <li key={taskIds(value)}>
      <span>任务 {taskIds(value)}</span>{' '}
      <Button disabled={busy} onClick={async () => {
        setBusy(true); setError('');
        try { await onRecover(value); } catch { setError('无法重新打开：权限、来源或任务状态已变化。当前候选仍保留。'); }
        finally { setBusy(false); }
      }}>重新打开保留任务</Button>
    </li>)}</ul>
    {records.length > 5 && <div className="actions">
      <Button disabled={busy || currentPage === 0} onClick={() => setPage(currentPage - 1)}>上一页</Button>
      <span>第 {currentPage + 1} / {Math.ceil(records.length / 5)} 页</span>
      <Button disabled={busy || (currentPage + 1) * 5 >= records.length} onClick={() => setPage(currentPage + 1)}>下一页</Button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </Panel>;
}
