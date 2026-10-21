/**
 * [HERMIA-FE-20261022 slice M1-2] Command search (U03 / GRAPH-04 entry). Lists `commandSearch`
 * actions from the shared ActionRegistry and executes through the SAME execute() path as buttons.
 * Ctrl/⌘+K opens; IME composition and text inputs never trigger it (shouldHandleShortcut).
 * Uses DS-v1.0 primitives/tokens only; not a protected surface (mounted inside module sidebar content).
 */
import {useEffect, useRef, useState} from 'react';
import {Search} from 'lucide-react';
import {Button} from '../ui/primitives';
import {shouldHandleShortcut} from './actions';
import type {Workbench} from './useWorkbench';
import './commandSearch.css';

export function CommandSearch({workbench, onLegacy}: {workbench: Workbench; onLegacy: (id: string) => void}) {
  const [open, setOpen] = useState(false); const [q, setQ] = useState(''); const [msg, setMsg] = useState('');
  const input = useRef<HTMLInputElement>(null); const trigger = useRef<HTMLButtonElement>(null);
  // [HERMIA-FE-20261022] Ctrl+K is owned by AppShell "打开全局命令" (protected surface).
  // Feature command search opens via the sidebar button only; do not steal the shortcut.
  useEffect(() => { if (open) input.current?.focus(); else trigger.current?.focus({preventScroll: true}); }, [open]);
  const ctx = workbench.context();
  const items = workbench.actions.list('commandSearch', ctx).filter(a => !q.trim() || a.label.toLowerCase().includes(q.trim().toLowerCase()));
  const run = async (id: string) => {
    const featureId = id.replace(/^panel\.open\./, '');
    const r = await workbench.open(featureId, onLegacy);
    if (r.status === 'done' || r.status === 'legacy') { setOpen(false); setQ(''); setMsg(''); }
    else setMsg(r.status === 'blocked' ? `无法执行：${r.reason}` : r.status === 'stale' ? '项目或章节已切换，请重新选择。' : r.status === 'duplicate' ? '正在打开，请稍候。' : '执行失败，请重试。');
  };
  return <div className="wb-command">
    <Button ref={trigger} variant="ghost" className="wb-command__trigger" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}><Search aria-hidden="true" size={16}/>搜索功能</Button>
    {open && <div className="wb-command__overlay" role="dialog" aria-modal="true" aria-label="搜索功能与命令" onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } }}>
      <input ref={input} className="wb-command__input" aria-label="搜索功能" placeholder="输入功能名称，例如：版本历史" value={q} onChange={e => setQ(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing && items[0]) { e.preventDefault(); void run(items[0].id); } }}/>
      <ul className="wb-command__list" role="listbox" aria-label="匹配的功能">
        {items.map(a => <li key={a.id}><button type="button" role="option" aria-selected={false} data-action-id={a.id} onClick={() => void run(a.id)}>{a.label}</button></li>)}
        {!items.length && <li className="wb-command__empty">没有匹配的功能</li>}
      </ul>
      {msg && <p role="status" className="wb-command__msg">{msg}</p>}
    </div>}
  </div>;
}
