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
import {createPortal} from 'react-dom'; // [HERMIA-FE-20261022 X-UX-11-FIX] overlay portals to body so it is never clipped/off-screen

function matchesQuery(label: string, id: string, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const hay = `${label} ${id} ${id.replace(/\./g, ' ')}`.toLowerCase();
  return needle.split(/\s+/).every(part => hay.includes(part));
}

// [HERMIA-FE-20261022 X-UX-11] Display-only grouping (写作 / 媒体 / 壳·设置). Every listed action
// lands in exactly one group (unknown ids fall back to 壳·设置), so no command becomes unreachable.
// [HERMIA-FE-20261023 M1-s3] layout.* now has its own 「布局」 group (was 壳·设置).
export type CommandGroup = '写作' | '媒体' | '布局' | '壳·设置';
export const COMMAND_GROUP_ORDER: CommandGroup[] = ['写作', '媒体', '布局', '壳·设置'];
const MEDIA_WORKSPACES = new Set(['image', 'video', 'audio', 'edit', 'assets']);
export function commandGroupOf(id: string): CommandGroup {
  if (id.startsWith('novel.') || id.startsWith('panel.open.') || id === 'workspace.open.novel') return '写作';
  const ws = /^workspace\.open\.(.+)$/.exec(id);
  if (ws && MEDIA_WORKSPACES.has(ws[1])) return '媒体';
  // [HERMIA-FE-20261023 M1-s3fix] 普通/专业 mode switches are settings, not layout: keep them in 壳·设置.
  if (id === 'layout.toggleMode' || id.startsWith('layout.setMode.')) return '壳·设置';
  if (id.startsWith('layout.')) return '布局';
  return '壳·设置';
}

export function CommandSearch({workbench, onLegacy}: {workbench: Workbench; onLegacy: (id: string) => void}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState('');
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  // [HERMIA-FE-20261022] Ctrl+K is owned by AppShell "打开全局命令" (protected surface).
  // [HERMIA-FE-20261024 M4-s1fix] do not steal focus on mount; only return focus to the trigger after the palette closes.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) {
      wasOpen.current = true;
      setActive(0);
      input.current?.focus();
    } else if (wasOpen.current) {
      wasOpen.current = false;
      trigger.current?.focus({preventScroll: true});
    }
  }, [open]);
  const ctx = workbench.context();
  const items = useMemo(
    () => {
      const listed = workbench.actions.list('commandSearch', ctx).filter(a => matchesQuery(a.label, a.id, q));
      // [HERMIA-FE-20261022 X-UX-11] stable sort by group so ↑/↓ order matches the visual groups.
      return COMMAND_GROUP_ORDER.flatMap(g => listed.filter(a => commandGroupOf(a.id) === g));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- list is cheap; epoch covers lifecycle
    [workbench, q, ctx.token.epoch, open], // [HERMIA-FE-20261022 X-UX-11] refresh on open so late-registered actions are listed
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
    {open && createPortal(<div className="wb-command__overlay" data-testid="command-search-overlay" role="dialog" aria-modal="true" aria-label="搜索功能与命令" onKeyDown={onListKey}>
      <input ref={input} className="wb-command__input" aria-label="搜索功能" aria-controls="wb-command-list" aria-activedescendant={items[active] ? `wb-cmd-${items[active].id}` : undefined} placeholder="输入功能名称，例如：版本历史 / 主控 / 专业" value={q} onChange={e => setQ(e.target.value)}/>
      {/* [HERMIA-FE-20261022 X-UX-11] input keys bubble to the overlay handler once (was handled twice → ↓ skipped an item). */}
      <ul id="wb-command-list" className="wb-command__list" role="listbox" aria-label="匹配的功能">
        {COMMAND_GROUP_ORDER.map(g => {
          const groupItems = items.filter(a => commandGroupOf(a.id) === g);
          if (!groupItems.length) return null;
          return <li key={g} role="presentation" className="wb-command__group">
            <div className="wb-command__group-label" id={`wb-cmd-group-${g}`} aria-hidden="true">{g}</div>
            <ul role="group" aria-label={g} data-command-group={g}>
              {groupItems.map(a => { const index = items.indexOf(a);
                // [HERMIA-FE-20261024 M2-s1fix] disabled items are announced (aria-disabled + reason) but stay focusable; Enter still explains why.
                const av = workbench.actions.availability(a.id, ctx); return (
          <li key={a.id}>
            <button
              type="button"
              id={`wb-cmd-${a.id}`}
              role="option"
              aria-selected={index === active}
              aria-disabled={av.enabled ? undefined : true}
              title={av.enabled ? undefined : av.reason}
              data-action-id={a.id}
              className={index === active ? 'is-active' : undefined}
              onMouseEnter={() => setActive(index)}
              onClick={() => void run(a.id)}
            >
              {/* [HERMIA-FE-20261023 M1-s3] internal id no longer shown as visible text; it still matches in search (matchesQuery). */}
              <span>{a.label}</span>
            </button>
          </li>
); })}
            </ul>
          </li>;
        })}
        {/* [HERMIA-FE-20261022 X-UX-11] honest empty state: says what was searched, no fake suggestions. */}
        {!items.length && <li className="wb-command__empty" role="presentation" data-testid="command-search-empty">
          {q.trim() ? <>没有与「{q.trim()}」匹配的功能。可尝试更短的关键词，或按功能 ID（如 history、plugin）搜索。</> : '当前没有可用的命令。'}
        </li>}
      </ul>
      {msg && <p role="status" className="wb-command__msg">{msg}</p>}
    </div>, document.body)}
  </div>;
}
