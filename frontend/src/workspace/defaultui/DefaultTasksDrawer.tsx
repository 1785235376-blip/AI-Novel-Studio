/**
 * [HERMIA-FE-20261025 UWPORT-S2] Default-UI port of the unified task loop: a status-bar "任务与结果" drawer.
 * Reuses TasksPanelLive (real tasks, explicit refresh, no polling; uncertain stays UNKNOWN), ResultsPanel (manual adopt
 * with confirmation, never Canon, UNKNOWN never auto-resends) and HistoryPanel (restore = new version appended).
 * No canvas exists in the default UI, so locate/execution buttons are hidden. No real identity ⇒ 仅本次会话 and no reads.
 */
import {useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent} from 'react';
import type {Actor, CollaborationContext, Scope} from '../../api';
import type {ProductionJob} from '../../creative/studioProductionClient';
import {useT} from '../../i18n';
import {IDENTITY_TEXT, resolveWorkspaceIdentity} from '../state/scopeLease';
import {useLiveTasks} from '../tasks/useLiveTasks';
import {useUnifiedLoop} from '../integration/useUnifiedLoop';
import {TasksPanelLive} from '../panels/TasksPanelLive';
import {ResultsPanel} from '../results/ResultsPanel';
import {HistoryPanel} from '../history/HistoryPanel';

export interface DefaultTasksDrawerProps { novelId: string; actor?: Actor; scope?: Scope; sessionToken: string }
const FOCUSABLE = 'button:not([disabled]),[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]:not([tabindex="-1"])';
/** [UWPORT-P1] keep Tab / Shift+Tab inside the dialog (Vera: focus escaped to body on the 9th Tab). */
function trapTab(e: ReactKeyboardEvent<HTMLElement>, root: HTMLElement) {
  const f = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(el => !el.closest('[inert]') && !(el.closest('details:not([open])') && el.tagName !== 'SUMMARY'));
  if (!f.length) { e.preventDefault(); root.focus(); return; }
  const first = f[0], last = f[f.length - 1], a = document.activeElement as HTMLElement | null;
  const inside = !!a && root.contains(a) && a !== root;
  if (e.shiftKey && (!inside || a === first)) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && (!inside || a === last)) { e.preventDefault(); first.focus(); }
}

function DrawerBody({novelId, actor, scope, sessionToken}: DefaultTasksDrawerProps) {
  const tr = useT();
  const identity = useMemo(() => resolveWorkspaceIdentity({actorId: actor?.id ?? null, collabScope: scope ?? null, projectId: novelId || null}), [actor?.id, scope, novelId]);
  const ctx = useMemo<CollaborationContext | null>(() => (identity.kind === 'real' ? {sessionToken, actor, scope} : null), [identity.kind, sessionToken, actor, scope]);
  const tasks = useLiveTasks(novelId || null, ctx, identity.kind === 'real' ? JSON.stringify(identity.scope) : null);
  const [job, setJob] = useState<ProductionJob | null>(null);
  useEffect(() => { setJob(null); }, [tasks]);
  const loop = useUnifiedLoop(novelId || null, ctx, tasks.lease, job);
  const u4 = loop.u4;
  const noop = () => undefined;
  const extra = job === null ? null : !u4?.target
    ? <p data-testid="dui-results-gap">{tr('dui.noTarget')}</p>
    : <>
      <p style={{margin: '12px 0 4px', opacity: .8}}>{tr('dui.resultsNote')}</p>
      {u4.adopt ? <ResultsPanel deps={u4.adopt} target={u4.target} online={navigator.onLine} /> : null}
      <p style={{margin: '12px 0 4px', opacity: .8}}>{tr('dui.historyNote')}</p>
      {u4.restore && u4.canvasId ? <HistoryPanel deps={u4.restore} canvasId={u4.canvasId} localDraft={false} /> : null}
    </>;
  return <>
    {identity.kind === 'real' ? null : <p data-testid="dui-identity">{IDENTITY_TEXT[identity.reason]}</p>}
    <TasksPanelLive feed={tasks.feed} navigator={tasks.navigator} active hideNav hasNode={() => false}
      captureReturn={() => ({panelId: 'tasks', canvas: 'creative', nodeIds: [], focusTestId: 'u3-tasks', viewport: null})}
      onLocate={noop} onOpenExecution={noop} onReturn={noop} onDetail={j => setJob(j)} detailExtra={extra} />
  </>;
}

export function DefaultTasksDrawer(props: DefaultTasksDrawerProps) {
  const tr = useT();
  const TITLE = tr('dui.title');
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { if (open) panel.current?.focus(); }, [open]);
  const close = () => { setOpen(false); trigger.current?.focus(); };
  const closeRef = useRef(close); closeRef.current = close;
  // Esc also works if focus somehow left the dialog (e.g. a focused button unmounted).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !panel.current?.contains(document.activeElement)) closeRef.current(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);
  return <>
    <button ref={trigger} type="button" className="status-bar__action" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>{TITLE}</button>
    {open ? <div className="task-inspector-overlay" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) close(); }}>
      <section ref={panel} tabIndex={-1} className="task-inspector dui-tasks-drawer" role="dialog" aria-modal="true" aria-labelledby="dui-tasks-title"
        style={{maxHeight: 'calc(100vh - 48px)', overflowY: 'auto'}}
        onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); close(); } else if (e.key === 'Tab' && panel.current) trapTab(e, panel.current); }}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <h3 id="dui-tasks-title" style={{margin: 0}}>{TITLE}</h3>
          <button type="button" onClick={close}>{tr('dui.close')}</button>
        </div>
        <DrawerBody {...props} />
      </section>
    </div> : null}
  </>;
}
