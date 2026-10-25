// [HERMIA-FE-20261024 M2-s1] Real content for the remaining ?uw=1 preview panels, reusing existing components unmodified:
// - 创作画布 → rebuild/canvas/RebuildCanvas kind="image" (same local-draft canvas DualCanvas uses; writes only localStorage)
// - 执行画布 → rebuild/canvas/RebuildCanvas kind="video"
// - 任务     → not connected here (legacy); the live task panel is workspace/panels/TasksPanelLive.tsx [HERMIA-FE-20261025 M5-fix]
// No model/generation call is made by layout, selection, canvas or project switches: these components never call a model
// on mount, and the only cross-panel action (送到执行画布) is the existing local `linkToExecution` draft write.
// [HERMIA-FE-20261025 M5-fix] react hooks no longer needed here (legacy TasksPanel no longer reads)
import type {ActionContext, ActionRegistry, Availability} from '../../workbench/actions';
import {RebuildCanvas, type CvNode, type CvViewport} from '../../rebuild/canvas/RebuildCanvas';
import {linkToExecution} from '../../rebuild/canvas/DualCanvas';
import {LAYOUT_ACTION_IDS, normalizeShortcut, type ShortcutTable} from '../actions/layoutActions';

import {panelDefinitions, shortcutsFor} from '../registry/workspaceRegistry'; // [HERMIA-FE-20261025 U2-M10]
import type {PanelDefinition} from '../../workbench/panels';
/** Capability status is honest: both canvases are browser-local drafts (no server canvas graph yet). */
// (workbench DockZone has no 'float'; floating is a DockLayout-only mode declared in PREVIEW_SPECS.)
// [HERMIA-FE-20261025 U2-M10] derived from the unified registry (parity-tested)
export const STUDIO_PREVIEW_PANELS: PanelDefinition[] = panelDefinitions() // [HERMIA-FE-20261025 INT] includes U4 results/history via registry;

export const STUDIO_ACTION_IDS = {
  sendToExecution: 'canvas.sendToExecution',
  openExecution: 'canvas.openExecution',
  openCreative: 'canvas.openCreative',
  openTasks: 'tasks.open',
} as const;
export const STUDIO_SHORTCUTS: Readonly<Record<string, string>> = shortcutsFor('canvas.open', 'tasks.'); // [HERMIA-FE-20261025 U2-M10]
export const STUDIO_MIN_BUSY_MS = 300;

const NO_NOVEL = '还没有选中作品';

// [HERMIA-FE-20261024 M3-s1] both canvases report selection; `revision` remounts after an inspector write, and the
// host-held viewport/selection are fed back so a remount keeps pan/zoom + selection. Each canvas keeps its own state.
type CanvasPanelProps = {novelId: string | null; revision?: number; onSelect?: (n: CvNode | null) => void; selectedId?: string | null;
  viewport?: CvViewport; onViewport?: (vp: CvViewport) => void; revealLast?: boolean; onRevealed?: () => void}; // [HERMIA-FE-20261024 M3-s1fix] revealLast
export function CreativeCanvasPanel({novelId, revision = 0, onSelect, selectedId, viewport, onViewport}: CanvasPanelProps) {
  if (!novelId) return <p style={{padding: 12}} data-state="empty">{NO_NOVEL}，选中作品后显示它的创作画布（本机草稿）。</p>;
  return <div data-testid="uw-creative-canvas" style={{height: '100%', minHeight: 280}}><RebuildCanvas key={`${novelId}:${revision}`} kind="image" scope={novelId} label="创作画布"
    onSelect={onSelect} initialSelected={selectedId} initialViewport={viewport} onViewport={onViewport} /></div>;
}

export function ExecutionCanvasPanel({novelId, revision = 0, onSelect, selectedId, viewport, onViewport, revealLast, onRevealed}: CanvasPanelProps) {
  if (!novelId) return <p style={{padding: 12}} data-state="empty">{NO_NOVEL}，选中作品后显示它的执行画布（本机草稿）。</p>;
  return <div data-testid="uw-execution-canvas" style={{height: '100%', minHeight: 280}}><RebuildCanvas key={`${novelId}:${revision}`} kind="video" scope={novelId} label="执行画布"
    onSelect={onSelect} initialSelected={selectedId} initialViewport={viewport} onViewport={onViewport} revealLast={revealLast} onRevealed={onRevealed} />{/* [HERMIA-FE-20261024 M3-s1fix2] onRevealed */}</div>;
}

// [HERMIA-FE-20261025 M5-fix] Vera P2: legacy preview TasksPanel no longer reads with an empty token + fabricated
// `uw-preview:` identity (unmounted path; the live panel is TasksPanelLive). It only states that it is not connected.
export function TasksPanel({novelId}: {novelId: string | null; active: boolean}) {
  if (!novelId) return <p style={{padding: 12}} data-state="empty">{NO_NOVEL}，选中作品后显示它的任务。</p>;
  return <div data-testid="uw-tasks"><p data-state="not-connected" role="status">这里的旧任务面板未接通：请使用工作台里的「任务」面板（需要已登录的协作账号）。</p></div>;
}

export interface StudioActionHost {
  getNovelId(): string | null;
  getSelectedNode(): CvNode | null;
  /** Called after 送到执行画布 wrote the local draft so the execution canvas re-reads it. */
  onLinked(node: CvNode): void;
  /** Execute layout.showPanel through the same registry. */
  showPanel(id: string): Promise<unknown>;
  /** [HERMIA-FE-20261024 M2-s1fix] move DOM focus into the shown panel (e.g. 任务 after Mod+Alt+T). */
  focusPanel?(id: string): void | Promise<void>;
}

const delay = (ms: number) => new Promise(r => setTimeout(r, ms));
const yes: Availability = {enabled: true};

/** Registers the real preview actions (disabled reasons, shortcuts claimed via ShortcutTable, ActionRegistry pending
 * dedupe as the double-trigger guard, kept pending for minBusyMs so a fast double press executes once). */
export function registerStudioPreviewActions(reg: ActionRegistry, table: ShortcutTable, host: StudioActionHost, minBusyMs = STUDIO_MIN_BUSY_MS) {
  const conflicts: {actionId: string; shortcut: string; conflictWith: string}[] = [];
  const undo: (() => void)[] = [];
  const show = (id: string, label: string, actionId: string) => ({
    id: actionId, label, surfaces: ['toolbar', 'shortcut', 'commandSearch'] as const,
    available: (): Availability => reg.get(LAYOUT_ACTION_IDS.show) ? yes : {enabled: false, reason: '布局还没有准备好'},
    run: async () => { const r = await host.showPanel(id); await host.focusPanel?.(id); await delay(minBusyMs); return r; },
  });
  const defs = [
    {
      id: STUDIO_ACTION_IDS.sendToExecution, label: '送到执行画布', surfaces: ['toolbar', 'commandSearch'] as const,
      available: (_ctx: ActionContext): Availability => {
        if (!host.getNovelId()) return {enabled: false, reason: NO_NOVEL};
        if (!host.getSelectedNode()) return {enabled: false, reason: '先在创作画布选中一个节点'};
        return yes;
      },
      run: async () => {
        const id = host.getNovelId(); const n = host.getSelectedNode();
        if (!id || !n) throw new Error('先在创作画布选中一个节点');
        linkToExecution(id, n); host.onLinked(n);
        await delay(minBusyMs);
        return n.id;
      },
    },
    show('execution', '打开执行画布', STUDIO_ACTION_IDS.openExecution),
    show('creative', '打开创作画布', STUDIO_ACTION_IDS.openCreative),
    show('tasks', '打开任务', STUDIO_ACTION_IDS.openTasks),
  ];
  for (const def of defs) {
    let d: typeof def & {shortcut?: string} = def;
    const sc = STUDIO_SHORTCUTS[def.id];
    if (sc) {
      const c = table.claim(sc, def.id);
      if (!c.ok) conflicts.push({actionId: def.id, shortcut: normalizeShortcut(sc), conflictWith: c.conflictWith});
      else { d = {...def, shortcut: sc}; undo.push(() => table.release(sc, def.id)); }
    }
    undo.push(reg.register(d));
  }
  return {conflicts, dispose: () => { while (undo.length) undo.pop()!(); }};
}
