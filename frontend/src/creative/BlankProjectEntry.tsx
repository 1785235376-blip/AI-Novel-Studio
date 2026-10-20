import { useEffect, useRef, useState } from 'react';
import { apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';

export function BlankProjectEntry({ createProject }: { createProject: (title: string) => Promise<void> }) {
  const [title, setTitle] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const pending = useRef(false), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const create = async () => {
    if (!title.trim() || pending.current) return;
    pending.current = true; setBusy(true); setError('');
    try { await createProject(title.trim()); }
    catch (reason) { if (alive.current) setError(apiErrorView(reason, '空白项目尚未打开，请核对项目列表后重试。').message); }
    finally { pending.current = false; if (alive.current) setBusy(false); }
  };
  return <Panel title="独立创作项目" className="independent-project-entry"><p>直接导入图片、视频或声音。无需创建小说、章节或安装模型；创作意图可以以后再选。</p>
    <label>空白项目名称<input aria-label="空白项目名称" maxLength={200} value={title} disabled={busy} onChange={event => setTitle(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void create(); } }} /></label>
    <Button variant="primary" disabled={!title.trim() || busy} onClick={() => void create()}>{busy ? '正在创建空白项目…' : '创建空白项目'}</Button>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
  </Panel>;
}
