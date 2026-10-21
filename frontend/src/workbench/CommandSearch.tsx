/**
 * [HERMIA-FE-20261022 slice M1-2 / X-UX-02 / X-UX-05] Command search (U03 / GRAPH-04 entry).
 * Lists `commandSearch` actions from the shared ActionRegistry and executes through the SAME
 * execute() path as buttons — panel.open.* + workspace.open.* + layout.* + novel.*.
 * Ctrl/⌘+K is owned by AppShell global command (protected); this overlay opens via sidebar only.
 * Chrome-hidden modules remain searchable (chromium hide ≠ command disable).
 */
import {useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent} from 'react';
import {Search} from 'lucide-react';
import {Button} from '../ui/primitives';
import type {Workbench} from './useWorkbench';
import './commandSearch.css';

function matchesQuery(label: string, id: string, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const hay = `${label} ${id} ${id.replace(/\./g, ' ')}`.toLowerCase();
  return needle.split(/\s+/).every(part => hay.includes(part));
}

export function CommandSearch({workbench, onLegacy}: {workbench: Workbench; onLegacy: (id: string) => void}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState('');
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  // [HERMIA-FE-20261022] Ctrl+K is owned by AppShell "打开全局命令" (protected surface).
  useEffect(() => {
    if (open) {
      setActive(0);
      input.current?.focus();
    } else {
      trigger.current?.focus({preventScroll: true});
    }
  }, [open]);
  const ctx = workbench.context();
  const items = useMemo(
    () => workbench.actions.list('commandSearch', ctx).filter(a => matchesQuery(a.label, a.id, q)),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- list is cheap; epoch covers lifecycle
    [workbench, q, ctx.token.epoch],
  );
  useEffect(() => { setActive(0); }, [q]);

  const run = async (id: string) => {
    // X-UX-02: always execute registry actions (workspace / layout / novel / panel.open).
    if (workbench.actions.get(id)) {
      const r = await workbench.actions.execute(id, workbench.context());
      if (r.status === 'done') { setOpen(false); setQ(''); setMsg(''); return; }
      setMsg(
        r.status === 'blocked' ? `无法执行：${r.reason}`
          : r.status === 'stale' ? '项目或章节已切换，请重新选择。'
          : r.status === 'duplicate' ? '正在打开，请稍候。'
          : r.status === 'needs-confirmation' ? '需要确认后才能执行。'
          : '执行失败，请重试。',
      );
      return;
    }
    // Unlisted / legacy-only ids
    const featureId = id.replace(/^panel\.open\./, '');
    onLegacy(featureId);
    setOpen(false); setQ(''); setMsg('');
  };

  const onListKey = (e: ReactKeyboardEvent) => {
    if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); return; }
    if (e.key === 'ArrowDown' && items.length) {
      e.preventDefault();
      setActive(i => (i + 1) % items.length);
    } else if (e.key === 'ArrowUp' && items.length) {
      e.preventDefault();
      setActive(i => (i - 1 + items.length) % items.length);
    } else if (e.key === 'Enter' && !e.nativeEvent.isComposing && items[active]) {
      e.preventDefault();
      void run(items[active].id);
    }
  };

  return <div className="wb-command">
    <Button ref={trigger} variant="ghost" className="wb-command__trigger" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}><Search aria-hidden="true" size={16}/>搜索功能</Button>
    {open && <div className="wb-command__overlay" role="dialog" aria-modal="true" aria-label="搜索功能与命令" onKeyDown={onListKey}>
      <input ref={input} className="wb-command__input" aria-label="搜索功能" aria-controls="wb-command-list" aria-activedescendant={items[active] ? `wb-cmd-${items[active].id}` : undefined} placeholder="输入功能名称，例如：版本历史 / 主控 / 专业" value={q} onChange={e => setQ(e.target.value)}
        onKeyDown={onListKey}/>
      <ul id="wb-command-list" className="wb-command__list" role="listbox" aria-label="匹配的功能">
        {items.map((a, index) => (
          <li key={a.id}>
            <button
              type="button"
              id={`wb-cmd-${a.id}`}
              role="option"
              aria-selected={index === active}
              data-action-id={a.id}
              className={index === active ? 'is-active' : undefined}
              onMouseEnter={() => setActive(index)}
              onClick={() => void run(a.id)}
            >
              <span>{a.label}</span>
              <small className="wb-command__id">{a.id}</small>
            </button>
          </li>
        ))}
        {!items.length && <li className="wb-command__empty">没有匹配的功能</li>}
      </ul>
      {msg && <p role="status" className="wb-command__msg">{msg}</p>}
    </div>}
  </div>;
}
