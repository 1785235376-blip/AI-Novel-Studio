import { useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { DirectorAuthorLocalDraft } from './directorAuthorLocalDraft';
export function DirectorAuthorRecoveryPanel({ candidate, notice, savedAt, enabled, busy, canRestore, onRestore, onDiscard }: {
  candidate?: DirectorAuthorLocalDraft; notice: string; savedAt: string; enabled: boolean; busy: boolean; canRestore: boolean;
  onRestore: () => void; onDiscard: () => void;
}) {
  const [confirmed, setConfirmed] = useState<DirectorAuthorLocalDraft>();
  return <section aria-label="导演作者草稿本机恢复">
    {!enabled && <StatusMessage tone="warning">作者身份或项目代次尚未确认，导演输入只保留在本页；可下载草稿备份。</StatusMessage>}
    {notice && <StatusMessage tone="warning">{notice}</StatusMessage>}
    {savedAt && !notice && !candidate && <StatusMessage>导演作者输入已保留在本机；服务端保存与审核仍需明确操作。</StatusMessage>}
    {candidate && <>
      <p>发现此身份与项目的导演作者恢复草稿。重新核对权限和原文档版本后才显示内容；不会恢复审核或任务授权。</p>
      <Button disabled={!canRestore || busy} onClick={onRestore}>核对并恢复导演作者草稿</Button>
      <label><input type="checkbox" checked={confirmed === candidate} disabled={busy} onChange={e => setConfirmed(e.target.checked ? candidate : undefined)} />确认放弃此导演本机恢复草稿</label>
      <Button disabled={confirmed !== candidate || busy} onClick={() => { if (confirmed === candidate && !busy) onDiscard(); }}>放弃导演本机恢复草稿</Button>
    </>}
  </section>;
}
