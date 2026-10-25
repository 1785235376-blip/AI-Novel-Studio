/**
 * [HERMIA-FE-20261025 UWPORT-S2] Default-UI port of the unified task loop: a status-bar "任务与结果" drawer.
 * Reuses TasksPanelLive (real tasks, explicit refresh, no polling; uncertain stays UNKNOWN), ResultsPanel (manual adopt
 * with confirmation, never Canon, UNKNOWN never auto-resends) and HistoryPanel (restore = new version appended).
 * No canvas exists in the default UI, so locate/execution buttons are hidden. No real identity ⇒ 仅本次会话 and no reads.
 */
import {useEffect, useMemo, useRef, useState} from 'react';
import type {Actor, CollaborationContext, Scope} from '../../api';
import type {ProductionJob} from '../../creative/studioProductionClient';
import {IDENTITY_TEXT, resolveWorkspaceIdentity} from '../state/scopeLease';
import {useLiveTasks} from '../tasks/useLiveTasks';
import {useUnifiedLoop} from '../integration/useUnifiedLoop';
import {TasksPanelLive} from '../panels/TasksPanelLive';
import {ResultsPanel} from '../results/ResultsPanel';
import {HistoryPanel} from '../history/HistoryPanel';

export interface DefaultTasksDrawerProps { novelId: string; actor?: Actor; scope?: Scope; sessionToken: string }
const TITLE = '任务与结果';

function DrawerBody({novelId, actor, scope, sessionToken}: DefaultTasksDrawerProps) {
  const identity = useMemo(() => resolveWorkspaceIdentity({actorId: actor?.id ?? null, collabScope: scope ?? null, projectId: novelId || null}), [actor?.id, scope, novelId]);
  const ctx = useMemo<CollaborationContext | null>(() => (identity.kind === 'real' ? {sessionToken, actor, scope} : null), [identity.kind, sessionToken, actor, scope]);
  const tasks = useLiveTasks(novelId || null, ctx, identity.kind === 'real' ? JSON.stringify(identity.scope) : null);
  const [job, setJob] = useState<ProductionJob | null>(null);
  useEffect(() => { setJob(null); }, [tasks]);
  const loop = useUnifiedLoop(novelId || null, ctx, tasks.lease, job);
  const u4 = loop.u4;
  const noop = () => undefined;
  const extra = job === null ? null : !u4?.target
    ? <p data-testid="dui-results-gap">这个任务没有记录作品位置，无法在这里采用结果或查看历史。</p>
    : <>
      <p style={{margin: '12px 0 4px', opacity: .8}}>结果（需手动确认采用，不会写入设定）</p>
      {u4.adopt ? <ResultsPanel deps={u4.adopt} target={u4.target} online={navigator.onLine} /> : null}
      <p style={{margin: '12px 0 4px', opacity: .8}}>作品历史（恢复会追加为新版本）</p>
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
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { if (open) panel.current?.focus(); }, [open]);
  const close = () => { setOpen(false); trigger.current?.focus(); };
  return <>
    <button ref={trigger} type="button" className="status-bar__action" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>{TITLE}</button>
    {open ? <div className="task-inspector-overlay" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) close(); }}>
      <section ref={panel} tabIndex={-1} className="task-inspector dui-tasks-drawer" role="dialog" aria-modal="true" aria-labelledby="dui-tasks-title"
        onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); close(); } }}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <h3 id="dui-tasks-title" style={{margin: 0}}>{TITLE}</h3>
          <button type="button" onClick={close}>关闭</button>
        </div>
        <DrawerBody {...props} />
      </section>
    </div> : null}
  </>;
}
