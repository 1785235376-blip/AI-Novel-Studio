// [HERMIA-FE-20261023 M1, applied M1-s2] Opt-in preview host for DockLayout (?uw=1 only).
import {useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {createPreviewPanelRegistry, InspectorPanel, OutlinePanel, pickDefaultNovel, registerNovelPreviewActions, useNovels} from './panels/novelPreviewPanels';
import {DockLayout, type LayoutPanelSpec} from './layout';
import type {PanelRenderApi} from './layout/DockLayout';
import {ActionRegistry} from '../workbench/actions';
import {LifecycleTracker} from '../workbench/lifecycle';
import {CommandSearch} from '../workbench/CommandSearch';
import type {Workbench} from '../workbench/useWorkbench';
import {actionIdForKey, LAYOUT_ACTION_IDS, ShortcutTable} from './actions/layoutActions';
// [HERMIA-FE-20261024 M2-s1] remaining placeholders replaced by real existing components + their registry actions.
import {layoutSpecs} from './registry/workspaceRegistry'; // [HERMIA-FE-20261025 U2-M10]
import {CreativeCanvasPanel, ExecutionCanvasPanel, registerStudioPreviewActions, STUDIO_ACTION_IDS, STUDIO_PREVIEW_PANELS} from './panels/studioPreviewPanels';
import type {CanvasKind, CvNode, CvViewport} from '../rebuild/canvas/RebuildCanvas';
import {CanvasNodeInspector, readCanvasNode, registerCanvasNodeActions, type CanvasPick} from './panels/canvasInspector'; // [HERMIA-FE-20261024 M3-s1]
import {shouldHandleShortcut} from '../workbench/actions';
import {DraftStore, useBeforeUnloadGuard} from './state/draftStore'; // [HERMIA-FE-20261024 M5-s1]
// [HERMIA-FE-20261024 VW-M1..M4] view prefs (session-only here: no real host scope), worksets, viewport reset, panel focus.
import {useViewPreferences} from './state/useViewPreferences';
import {PREFS_REASON_TEXT} from './state/viewPreferences';
import {registerViewActions, VIEW_ACTION_IDS} from './actions/viewActions';
import {WorkspaceViewsPanel} from './panels/WorkspaceViewsPanel';
import {createPanelFocusTracker, type PanelFocusTracker} from './state/panelFocus';
import type {DockLayoutApi} from './layout/DockLayout';
import {useStudio} from '../store';
import {api} from '../api'; // [HERMIA-FE-20261025 M5] bootstrap read for ?uw=1 (LegacyApp's bootstrap never runs here) // [HERMIA-FE-20261025 U1-M1] real identity source (bootstrap actor + collaboration scope)
import {IDENTITY_TEXT, resolveWorkspaceIdentity} from './state/scopeLease';
import {TasksPanelLive} from './panels/TasksPanelLive'; // [HERMIA-FE-20261025 U3-M3/M4] real task panel (replaces fabricated-identity TasksPanel)
import {canvasHasNode, useLiveTasks} from './tasks/useLiveTasks';
import {ResultsPanel} from './results/ResultsPanel'; // [HERMIA-FE-20261025 U4 wiring]
import {HistoryPanel} from './history/HistoryPanel'; // [HERMIA-FE-20261025 U4 wiring]
import {ProjectPresence, purgeProjectGeometry} from './state/projectPurge';
import {useUnifiedLoop} from './integration/useUnifiedLoop'; // [HERMIA-FE-20261025 INT] u4 deps + param session from real clients
import {ParamEditPanel} from './params/ParamEditPanel';
import {CanvasSelectionLayer} from './registry/CanvasSelectionLayer'; // [HERMIA-FE-20261025 INT] U2 mounts
import {ContextNavBar} from './registry/ContextNavBar';
import {EMPTY_SELECTION, type CanvasSelection} from './registry/selection';
import {INITIAL_NAV, openTask, toggleCompare, type NavState} from './registry/contextNav';
import {registerNavActions} from './actions/navActions';
import type {NavReturnPoint} from './contracts';
import type {ProductionJob} from '../creative/studioProductionClient';

export function unifiedWorkspacePreviewEnabled(): boolean {
  try { return new URLSearchParams(window.location.search).get("uw") === "1"; } catch { return false; }
}

// [HERMIA-FE-20261025 U2-M10] single source: derived from registry/workspaceRegistry (parity-tested)
export const PREVIEW_SPECS: LayoutPanelSpec[] = layoutSpecs();

/**
 * [HERMIA-FE-20261023 M1-s2fix] MUST-FIX 4: the preview shares ONE ActionRegistry + LifecycleTracker between DockLayout
 * and the existing registry-fed command palette (workbench/CommandSearch, same component App mounts). AppShell's own
 * Ctrl/⌘+K palette is a static module list (not registry-fed) and is not mounted under ?uw=1, so here Ctrl/⌘+K opens
 * CommandSearch through its own trigger button. workbench/** is reused unmodified (except [HERMIA-FE-20261024 M2-s1fix]: aria-disabled on disabled options).
 */
/** [HERMIA-FE-20261025 U1-M2] property access to localStorage can throw in a blocked origin. */
function safeLocalStorage(): Storage | null { try { return window.localStorage; } catch { return null; } }

export function UnifiedWorkspacePreview() {
  const shared = useMemo(() => {
    const tracker = new LifecycleTracker(); const actions = new ActionRegistry(tracker); const table = new ShortcutTable();
    const workbench = {
      tracker, actions, panels: undefined as unknown as Workbench['panels'],
      context: (targetId: string | null = null) => ({token: tracker.current(), targetId, targetVersion: null, permissions: new Set<string>()}),
      open: async () => ({status: 'legacy' as const}),
    } satisfies Workbench;
    // [HERMIA-FE-20261023 M1-s3] real panels go through the workbench PanelRegistry (contract §1).
    const panels = createPreviewPanelRegistry();
    for (const d of STUDIO_PREVIEW_PANELS) panels.register(d); // [HERMIA-FE-20261024 M2-s1]
    workbench.panels = panels as unknown as Workbench['panels'];
    return {tracker, actions, table, workbench, panels};
  }, []);
  // [HERMIA-FE-20261023 M1-s3] shared selection: outline → inspector linkage. GET-only on load.
  const qc = useQueryClient();
  const novels = useNovels();
  const [novelId, setNovelId] = useState<string | null>(null);
  const nodeDirtyRef = useRef<{current: boolean}>({current: false});
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const inspectorDirty = useRef(false);
  // [HERMIA-FE-20261024 M5-s1] drafts survive redock/collapse/tab switch; beforeunload only while dirty.
  const drafts = useMemo(() => new DraftStore(), []);
  const anyDirty = useCallback(() => drafts.anyDirty() || inspectorDirty.current || nodeDirtyRef.current.current, [drafts]);
  useBeforeUnloadGuard(anyDirty, drafts);
  const novelRef = useRef(novelId); novelRef.current = novelId;
  useEffect(() => { if (!novelId && novels.data?.length) setNovelId(pickDefaultNovel(novels.data)?.id ?? null); }, [novels.data, novelId]);
  useEffect(() => registerNovelPreviewActions(shared.actions, qc, () => novelRef.current), [shared.actions, qc]);
  // [HERMIA-FE-20261024 M2-s1] canvas selection + execution revision; all local, no model call.
  const [selNode, setSelNode] = useState<CvNode | null>(null);
  const selRef = useRef(selNode); selRef.current = selNode;
  const [execRev, setExecRev] = useState(0);
  const [studioMsg, setStudioMsg] = useState<string | null>(null);
  const [, force] = useState(0);
  // [HERMIA-FE-20261024 M3-s1] per-canvas selection (isolated), inspector target, per-canvas revision + viewport memory.
  const [execSel, setExecSel] = useState<CvNode | null>(null);
  const [inspect, setInspect] = useState<CanvasPick | null>(null);
  const inspectRef = useRef(inspect); inspectRef.current = inspect;
  const [creativeRev, setCreativeRev] = useState(0);
  const nodeDirty = useRef(false);
  nodeDirtyRef.current = nodeDirty; // [HERMIA-FE-20261024 M5-s1] (moved above the M3-s1fix comment [HERMIA-FE-20261024 M6])
  // [HERMIA-FE-20261024 M3-s1fix] MUST-FIX: viewport memory keyed by novelId (a reset in an effect ran after the new project's canvas had
  // already remounted with the old viewport). Switching back to a project restores its own viewport.
  // [HERMIA-FE-20261024 VW-M1/M3] viewports go through the view-prefs adapter. The preview host has NO real
  // user/project/instance scope (DockLayout still uses the placeholder one), so prefs are session-only per novel and
  // nothing is written to storage. Callbacks are bound to the adapter of the novel that rendered them, so a late
  // onViewport from the previous novel's canvas is rejected by that adapter's lease (isCurrent) instead of leaking.
  // [HERMIA-FE-20261025 U1-M1/M2] real scope only from the bootstrap actor + complete collaboration scope; otherwise
  // session-only (never a fabricated user id). Real scope ⇒ prefs/layout persist per user/project/instance (cold reopen).
  const actorId = useStudio(st => st.actor?.id ?? null);
  const collabScope = useStudio(st => st.scope ?? null);
  const identity = useMemo(() => resolveWorkspaceIdentity({actorId, collabScope, projectId: novelId}), [actorId, collabScope, novelId]);
  const realScope = identity.kind === 'real' ? identity.scope : null;
  // [HERMIA-FE-20261025 U3-M3] real session only; no identity ⇒ TasksPanelLive shows "未接通" and performs no read.
  const sessionToken = useStudio(st => st.sessionToken);
  const actor = useStudio(st => st.actor);
  // [HERMIA-FE-20261025 M5] ?uw=1 returns before LegacyApp, whose bootstrap is the only place the server actor is read; without
  // this a signed-in session never became "real" (repro: integration/int.bootstrap.test.tsx, shots/00-repro-*). Same GET as
  // LegacyApp, only with a token + complete scope and no actor yet; the actor comes from the server, never invented. A late
  // answer for a scope/token that is no longer current is dropped.
  useEffect(() => {
    const sc = collabScope;
    if (actor || !sessionToken || !sc?.workspaceId || !sc.projectId || !sc.storylineId || !sc.branchId) return;
    let live = true;
    api.bootstrap(sc).then(b => {
      const st = useStudio.getState();
      if (!live || st.actor || st.sessionToken !== sessionToken || st.scope !== sc || !b?.actor?.actor_id || b.scope?.workspace_id !== sc.workspaceId) return;
      st.setCollaboration(sessionToken, {id: b.actor.actor_id, displayName: '协作账号', workspaceId: b.scope.workspace_id}, sc);
    }, () => undefined);
    return () => { live = false; };
  }, [actor, sessionToken, collabScope]);
  const taskCtx = useMemo(() => (identity.kind === 'real' ? {sessionToken, actor, scope: collabScope ?? undefined} : null), [identity.kind, sessionToken, actor, collabScope]);
  const tasks = useLiveTasks(novelId, taskCtx, identity.kind === 'real' ? JSON.stringify(identity.scope) : null);
  // [HERMIA-FE-20261025 INT] selected production job (from task detail) drives params (M7) and results/history (M8/M9).
  const [selJob, setSelJob] = useState<ProductionJob | null>(null);
  useEffect(() => { setSelJob(null); }, [tasks]);
  const loop = useUnifiedLoop(novelId, taskCtx, tasks.lease, selJob);
  const u4 = loop.u4;
  // [HERMIA-FE-20261025 INT] U2 selection + context nav. Return-to-origin uses U3's navigator (single return system).
  const [sel, setSel] = useState<CanvasSelection>(EMPTY_SELECTION);
  const [nav, setNav] = useState<NavState>(INITIAL_NAV);
  const navRef = useRef(nav); navRef.current = nav;
  const returnRef = useRef<() => void>(() => {});
  useEffect(() => { setSel(EMPTY_SELECTION); setNav(INITIAL_NAV); }, [tasks]);
  const store = realScope ? safeLocalStorage() : null;
  // [HERMIA-FE-20261025 U1-M2 INT] no resurrection: purge own geometry for projects that vanished from a successful list.
  const realUser = useMemo(() => { const r = resolveWorkspaceIdentity({actorId, collabScope, projectId: '\u0001'}); return r.kind === 'real' ? r.scope.userId : null; }, [actorId, collabScope]);
  const presence = useRef<ProjectPresence | null>(null);
  useEffect(() => {
    if (!realUser || !novels.isSuccess || !Array.isArray(novels.data)) return;
    if (presence.current?.identityKey !== realUser) presence.current = new ProjectPresence(realUser);
    const gone = presence.current.observe(novels.data.map(n => n.id));
    for (const id of gone) purgeProjectGeometry(safeLocalStorage(), realUser, id);
    if (novelId && gone.includes(novelId)) setNovelId(null);
  }, [realUser, novels.isSuccess, novels.data, novelId]);
  const prefs = useViewPreferences({scope: realScope, storage: store, persist: !!realScope, sessionKey: novelId});
  // [HERMIA-FE-20261025 U1fix] MUST-FIX 1 + P2: ONE adapter per scope for viewports AND worksets (two adapters on the same
  // key erased each other). Worksets are now per project in both real and session mode (consistent keying).
  const layoutPrefs = prefs;
  const prefsRef = useRef(layoutPrefs); prefsRef.current = layoutPrefs;
  const toCv = (v: {x: number; y: number; zoom: number} | undefined): CvViewport | undefined => (v ? {x: v.x, y: v.y, k: v.zoom} : undefined);
  const vpOf = (k: CanvasKind) => (novelId ? toCv(prefs.getViewport(k)) : undefined);
  const onCreativeVp = useMemo(() => (v: CvViewport) => { prefs.setViewport('image', {x: v.x, y: v.y, zoom: v.k}); }, [prefs]);
  const onExecVp = useMemo(() => (v: CvViewport) => { prefs.setViewport('video', {x: v.x, y: v.y, zoom: v.k}); }, [prefs]);
  const [vpMsg, setVpMsg] = useState<string | null>(null);
  // [HERMIA-FE-20261025 U1fix] MUST-FIX 3: identity can arrive after the canvases mounted with the session (default)
  // viewport. When the real scope changes for the SAME project the canvases must remount with the restored viewport.
  // This is derived DURING render (not in an effect): otherwise the still-mounted old canvas sees the new adapter's
  // onViewport callback first and writes its default 40,40 over the stored viewport before the remount.
  const realKey = realScope ? `${realScope.userId}\u0000${realScope.projectId}\u0000${realScope.projectInstanceId}` : null;
  const [ident, setIdent] = useState({novelId, realKey, epoch: 0});
  if (ident.novelId !== novelId || ident.realKey !== realKey) setIdent({novelId, realKey, epoch: ident.epoch + (ident.novelId === novelId ? 1 : 0)});
  const identEpoch = ident.epoch; // a pending setIdent above discards this render before commit
  const resetVp = (k: CanvasKind) => {
    prefs.resetViewport(k); (k === 'image' ? setCreativeRev : setExecRev)(v => v + 1);
    setVpMsg(`已把${k === 'image' ? '创作' : '执行'}画布的视角恢复为默认（${prefs.status().mode === 'session' ? '仅本次会话' : '已保存'}）。`);
  };
  const layoutApi = useRef<DockLayoutApi | null>(null);
  const [viewsOpen, setViewsOpen] = useState(false);
  const [viewsMsg, setViewsMsg] = useState<string | null>(null);
  const focusRef = useRef<PanelFocusTracker | null>(null);
  useEffect(() => {
    const t = createPanelFocusTracker(() => document.body, id => PREVIEW_SPECS.find(x => x.id === id)?.title ?? '面板');
    focusRef.current = t; return () => { t.dispose(); focusRef.current = null; };
  }, []);
  const [revealExec, setRevealExec] = useState(false);
  const onExecRevealed = useCallback(() => setRevealExec(false), []); // [HERMIA-FE-20261024 M3-s1fix2] one-shot: consumed by the canvas
  // [HERMIA-FE-20261024 M3-s1fix] true only for the remount right after a send
  useEffect(() => { setSelNode(null); setExecSel(null); setInspect(null); lastPick.current = null; setRevealExec(false); setPickBlocked(null); }, [novelId]);
  // [HERMIA-FE-20261024 M5-s1] project switch bumps the lifecycle epoch: in-flight registry actions from the previous
  // project resolve as 'stale' and are not applied. Layout-effect so it lands before any new-project action runs.
  useLayoutEffect(() => { shared.tracker.update({projectId: novelId}); }, [shared, novelId]);
  useEffect(() => registerCanvasNodeActions(shared.actions), [shared.actions]);
  const lastPick = useRef<CanvasPick | null>(null);
  const [pickBlocked, setPickBlocked] = useState<string | null>(null); // [HERMIA-FE-20261024 M3-s1fix]
  const nodeTitle = inspect && novelId ? readCanvasNode(inspect.kind, novelId, inspect.id)?.node.title ?? null : null;
  const dirtyName = () => (nodeDirty.current && inspectRef.current && novelRef.current
    ? `节点「${readCanvasNode(inspectRef.current.kind, novelRef.current, inspectRef.current.id)?.node.title ?? inspectRef.current.id}」` : '「章节属性」');
  // [HERMIA-FE-20261024 M3-s1fix] the inspector panel title names the node while one is shown (DockLayout's dirty prompt uses this title).
  const specs = useMemo(() => PREVIEW_SPECS.map(x => x.id === 'inspector' && inspect ? {...x, title: `节点「${nodeTitle ?? '未命名节点'}」属性` /* [HERMIA-FE-20261025 U2] no raw id on screen */} : x), [inspect, nodeTitle]);
  const pickImpl = (kind: CanvasKind, n: CvNode | null) => {
    (kind === 'image' ? setSelNode : setExecSel)(n);
    const cur = inspectRef.current;
    const next = n ? {kind, id: n.id} : (cur?.kind === kind ? null : cur);
    if (n || lastPick.current?.kind === kind) lastPick.current = n ? next : null;
    if (next?.kind === cur?.kind && next?.id === cur?.id) return;
    // [HERMIA-FE-20261024 M3-s1fix] the notice names what is dirty and is shown inside the inspector too (visible from the execution tab).
    if (anyDirty()) /* [HERMIA-FE-20261024 MERGE] M5 anyDirty (incl. drafts) + M3-s1fix named notice */ { const t = `${dirtyName()}有未保存的修改，请先保存或放弃；属性面板仍显示原对象。`; setStudioMsg(t); setPickBlocked(t); return; }
    inspectRef.current = next; setInspect(next); setPickBlocked(null);
  };
  // stable handlers (RebuildCanvas re-fires onSelect when the callback identity changes)
  const pickRef = useRef(pickImpl); pickRef.current = pickImpl;
  const onPickImage = useCallback((n: CvNode | null) => pickRef.current('image', n), []);
  const onPickVideo = useCallback((n: CvNode | null) => pickRef.current('video', n), []);
  useEffect(() => {
    const r = registerStudioPreviewActions(shared.actions, shared.table, {
      getNovelId: () => novelRef.current, getSelectedNode: () => selRef.current,
      onLinked: n => { setRevealExec(true); setExecRev(v => v + 1); setStudioMsg(`已把「${n.title}」送到执行画布（本机草稿）。`); },
      showPanel: async id => {
        const res = await shared.actions.execute(LAYOUT_ACTION_IDS.show, {...shared.workbench.context(id), input: id});
        if (res.status !== 'done') throw new Error(res.status === 'blocked' ? res.reason : res.status);
        return res.value;
      },
      // [HERMIA-FE-20261024 M2-s1fix] reopen/dock dispatches render next tick; then focus the panel region (tabIndex -1).
      focusPanel: async id => {
        await new Promise(r => setTimeout(r, 0));
        document.querySelector<HTMLElement>(`[data-panel-id="${id}"]`)?.focus({preventScroll: true});
      },
    });
    return r.dispose;
  }, [shared]);
  const runStudio = useCallback(async (id: string) => {
    force(v => v + 1);
    const res = await shared.actions.execute(id, shared.workbench.context(null));
    if (res.status === 'blocked') setStudioMsg(res.reason);
    else if (res.status === 'error') setStudioMsg(`操作失败：${String((res.error as Error)?.message ?? res.error)}`);
    force(v => v + 1);
    return res;
  }, [shared]);
  useEffect(() => {
    const ids = Object.values(STUDIO_ACTION_IDS);
    const onKey = (e: KeyboardEvent) => {
      if (!shouldHandleShortcut(e)) return;
      const id = actionIdForKey(e, shared.table, ids); if (!id) return;
      e.preventDefault(); void runStudio(id);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shared, runStudio]);
  const handleReturn = (rp: NavReturnPoint) => { setNav(n => ({...n, task: null, origin: null, notice: null})); void shared.actions.execute(LAYOUT_ACTION_IDS.show, {...shared.workbench.context(rp.panelId), input: rp.panelId})
        .then(() => document.querySelector<HTMLElement>(`[data-testid="${rp.focusTestId}"]`)?.focus({preventScroll: true})); };
  returnRef.current = () => { const rp = tasks.navigator?.takeReturn(); if (rp) handleReturn(rp); };
  const showPanel = useCallback((pid: string) => shared.actions.execute(LAYOUT_ACTION_IDS.show, {...shared.workbench.context(pid), input: pid}), [shared]);
  const doCompare = useCallback(() => { const r = toggleCompare(navRef.current); setNav(r.state);
    if (r.intent.kind === 'show') { const p = r.intent.preset; void (p === 'compare' ? showPanel('creative').then(() => showPanel('execution')) : showPanel(r.intent.focusPanel)); } }, [showPanel]);
  useEffect(() => registerNavActions(shared.actions, shared.table, {
    canReturn: () => !!tasks.navigator?.canReturn(), returnToOrigin: () => returnRef.current(), hasProject: () => !!novelId, toggleCompare: doCompare,
  }).dispose, [shared, tasks, novelId, doCompare]);
  // [HERMIA-FE-20261024 VW-M2/M4] worksets + panel focus on the shared registry (button / command search / shortcut).
  useEffect(() => registerViewActions(shared.actions, shared.table, {
    layout: () => layoutApi.current, prefs: () => prefsRef.current, focus: () => focusRef.current,
    openViews: () => { setViewsMsg(null); setViewsOpen(true); }, onChange: m => { setViewsMsg(m); setStudioMsg(m); },
  }).dispose, [shared]);
  useEffect(() => {
    const ids = [VIEW_ACTION_IDS.openViews, VIEW_ACTION_IDS.nextPanel, VIEW_ACTION_IDS.prevPanel, VIEW_ACTION_IDS.lastPanel];
    const onKey = (e: KeyboardEvent) => {
      const id = actionIdForKey(e, shared.table, ids); if (!id) return;
      e.preventDefault();
      void shared.actions.execute(id, shared.workbench.context(null)).then(r => {
        if (r.status === 'blocked') setStudioMsg(r.reason);
        else if (r.status === 'error') setStudioMsg(String((r.error as Error)?.message ?? r.error));
      });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shared]);
  const guardSwitch = (apply: () => void) => {
    if (anyDirty()) /* [HERMIA-FE-20261024 MERGE] */ { setBlocked(`${dirtyName()}里有未保存的标题修改，请先保存或放弃后再切换。`); return; }
    setBlocked(null); setPickBlocked(null); apply();
  };
  const ctx = useCallback((input?: unknown) => ({...shared.workbench.context(chapterId), input}), [shared.workbench, chapterId]);
  const renderPanel = (id: string, api: PanelRenderApi) => {
    if (id === 'outline') return <OutlinePanel novelId={novelId} novels={novels} onNovel={v => guardSwitch(() => { setNovelId(v); setChapterId(null); })}
      selectedId={chapterId ?? undefined} onSelect={v => guardSwitch(() => setChapterId(v))} blockedNotice={blocked} ctx={() => ctx()} actions={shared.actions} />;
    if (id === 'inspector' && inspect && novelId) return <>{pickBlocked && <p role="status" className="uw-state" data-testid="uw-inspector-blocked">{pickBlocked}</p>}<CanvasNodeInspector pick={inspect} scope={novelId} actions={shared.actions} ctx={ctx} api={api}
      dirtyRef={nodeDirty} onSaved={k => { if (k === 'video') setRevealExec(false); (k === 'image' ? setCreativeRev : setExecRev)(v => v + 1); }} drafts={drafts} onBack={() => setInspect(null)}
      onSettled={() => { setPickBlocked(null); const lp = lastPick.current; if (lp && (lp.kind !== inspectRef.current?.kind || lp.id !== inspectRef.current?.id)) { inspectRef.current = lp; setInspect(lp); } }} /></>;
    if (id === 'inspector') return <>{pickBlocked && <p role="status" className="uw-state" data-testid="uw-inspector-blocked">{pickBlocked}</p>}<InspectorPanel novelId={novelId} chapterId={chapterId} api={api} ctx={ctx} actions={shared.actions} dirtyRef={inspectorDirty} drafts={drafts} /></>;
    if (id === 'creative') {
      const av = shared.actions.availability(STUDIO_ACTION_IDS.sendToExecution, shared.workbench.context(null));
      const busy = shared.actions.isPending(STUDIO_ACTION_IDS.sendToExecution, null);
      return <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
        <div style={{display: 'flex', gap: 8, alignItems: 'center', padding: '4px 8px'}}>
          <button type="button" className="uw-btn" data-action-id={STUDIO_ACTION_IDS.sendToExecution} disabled={!av.enabled || busy} aria-busy={busy || undefined}
            title={av.enabled ? '把选中的节点作为参考放到执行画布' : av.reason} onClick={() => void runStudio(STUDIO_ACTION_IDS.sendToExecution)}>送到执行画布</button>
          {!av.enabled && <small data-testid="uw-send-reason">{av.reason}</small>}
          <button type="button" className="uw-btn" data-testid="uw-reset-vp-image" disabled={!novelId} title={PREFS_REASON_TEXT[prefs.status().reason]} onClick={() => resetVp('image')}>重置视角</button>
        </div>
        <div style={{flex: 1, minHeight: 0}}><CanvasSelectionLayer canvas="image" selection={sel} onChange={setSel}><CreativeCanvasPanel novelId={novelId} revision={creativeRev + identEpoch} onSelect={onPickImage} selectedId={selNode?.id} viewport={vpOf('image')} onViewport={onCreativeVp} /></CanvasSelectionLayer></div>
      </div>;
    }
    if (id === 'execution') return <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
      <div style={{display: 'flex', gap: 8, alignItems: 'center', padding: '4px 8px'}}><button type="button" className="uw-btn" data-testid="uw-reset-vp-video" disabled={!novelId}
        title={PREFS_REASON_TEXT[prefs.status().reason]} onClick={() => resetVp('video')}>重置视角</button></div>
      <div style={{flex: 1, minHeight: 0}}><CanvasSelectionLayer canvas="video" selection={sel} onChange={setSel}><ExecutionCanvasPanel novelId={novelId} revision={execRev + identEpoch} onSelect={onPickVideo} selectedId={execSel?.id} viewport={vpOf('video')} onViewport={onExecVp} revealLast={revealExec} onRevealed={onExecRevealed} /></CanvasSelectionLayer></div></div>;
    // [HERMIA-FE-20261025 U3-M4] read-only nav: locate source node / open execution canvas / return (selection+focus+viewport).
    if (id === 'tasks') return <TasksPanelLive feed={tasks.feed} navigator={tasks.navigator} active
      hasNode={(c, nid) => !!novelId && canvasHasNode(safeLocalStorage(), novelId, c, nid)}
      captureReturn={() => ({panelId: 'tasks', canvas: 'creative', nodeIds: [selNode?.id, execSel?.id].filter((x): x is string => !!x), focusTestId: 'u3-tasks', viewport: null})}
      onLocate={r => { void shared.actions.execute(LAYOUT_ACTION_IDS.show, {...shared.workbench.context(r.canvas), input: r.canvas}); }}
      onOpenExecution={() => { void shared.actions.execute(LAYOUT_ACTION_IDS.show, {...shared.workbench.context('execution'), input: 'execution'}); }}
      onReturn={handleReturn}
      onDetail={(j, ref) => { setSelJob(j); if (ref) setNav(n => openTask(n, ref, {nodeExists: (c, nid) => !!novelId && canvasHasNode(safeLocalStorage(), novelId, c, nid),
        capture: () => ({panelId: 'tasks', canvas: 'creative', nodeIds: sel.ids.slice(), focusTestId: 'u3-tasks', viewport: null})}).state); }}
      detailExtra={loop.param ? ('session' in loop.param ? <ParamEditPanel session={loop.param.session} targetTitle={loop.param.title} />
        : <p data-testid="int-param-gap">{loop.param.gap}</p>) : null} />;
    // [HERMIA-FE-20261025 U4 wiring] 总控需提供 u4 = {adopt: AdoptDeps (StudioProductionClient + canvasViews + 当前 ScopeLease), target, restore: RestoreDeps, canvasId}；未提供时保持"未接入"。
    // [HERMIA-FE-20261025 INT] connected but nothing selected: honest empty state with the next step (not "not connected").
    if ((id === 'results' || id === 'history') && u4 && !u4.target) return <p style={{padding: 12}} data-state="empty" data-testid={`int-${id}-empty`}>
      {selJob ? '所选任务没有记录作品位置，无法显示结果或历史。' : '先在“任务”里选一个生产任务，这里会显示它的结果和作品历史。'}</p>;
    if (id === 'results' && u4?.adopt && u4.target) return <ResultsPanel deps={u4.adopt} target={u4.target} online={navigator.onLine} />;
    if (id === 'history' && u4?.restore && u4.canvasId) return <HistoryPanel deps={u4.restore} canvasId={u4.canvasId} localDraft={false} />;
    return <p style={{ padding: 12 }} data-state="not-connected">{PREVIEW_SPECS.find((x) => x.id === id)?.title ?? "面板"}：预览里尚未接入实际功能。</p>;
  };
  const host = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.isComposing || !(e.ctrlKey || e.metaKey) || e.altKey || e.key.toLowerCase() !== 'k') return;
      e.preventDefault();
      host.current?.querySelector<HTMLButtonElement>('.wb-command__trigger')?.click();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return (
      <DockLayout specs={specs} scope={realScope ?? { userId: "local", projectId: "preview", projectInstanceId: "preview" }}
        storage={store} loadOptions={{ inspectorPanelId: "inspector" }}
        actionRegistry={shared.actions} shortcutTable={shared.table} tracker={shared.tracker}
        toolbarStart={<span ref={host} data-testid="uw-command-host" style={{display: 'inline-flex', alignItems: 'center', gap: 6}}>
          <CommandSearch workbench={shared.workbench} onLegacy={() => {}} /><small>Ctrl／⌘+K</small>
          {/* [HERMIA-FE-20261024 M2-s1] N5: always-visible execution canvas entry, works even when the panel is closed/hidden. */}
          <button type="button" className="uw-btn uw-btn--primary" data-action-id={STUDIO_ACTION_IDS.openExecution} data-testid="uw-open-execution"
            title="打开执行画布（Ctrl／⌘+Alt+E）" onClick={() => void runStudio(STUDIO_ACTION_IDS.openExecution)}>执行画布</button>
          <button type="button" className="uw-btn" data-action-id={VIEW_ACTION_IDS.openViews} data-testid="uw-open-views" title="保存或切换面板布局（Ctrl／⌘+Alt+V）"
            onClick={() => void shared.actions.execute(VIEW_ACTION_IDS.openViews, shared.workbench.context(null))}>视图</button>
          {studioMsg && <small role="status" data-testid="uw-studio-status">{studioMsg}</small>}
          {vpMsg && <small role="status" data-testid="uw-vp-status">{vpMsg}</small>}
          <ContextNavBar nav={nav} selection={sel} multi={null} capabilities={[]} canReturn={!!tasks.navigator?.canReturn()}
            onReturn={() => returnRef.current()} onCompare={doCompare} onClearSelection={() => setSel(EMPTY_SELECTION)} />
          <small data-testid="uw-identity" data-identity={identity.kind}>{IDENTITY_TEXT[identity.kind === 'real' ? 'real' : identity.reason]}</small>
          {viewsOpen && <WorkspaceViewsPanel prefs={layoutPrefs} actions={shared.actions} ctx={input => ({...shared.workbench.context(null), input})}
            message={viewsMsg} onClose={() => setViewsOpen(false)} />}</span>}
        onLayoutApi={a => { layoutApi.current = a; }}
        renderPanel={renderPanel} />
  );
}
