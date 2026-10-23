// [HERMIA-FE-20261023 M1, applied M1-s2] Opt-in preview host for DockLayout (?uw=1 only).
import {useEffect, useMemo, useRef} from 'react';
import {DockLayout, type LayoutPanelSpec} from './layout';
import {ActionRegistry} from '../workbench/actions';
import {LifecycleTracker} from '../workbench/lifecycle';
import {CommandSearch} from '../workbench/CommandSearch';
import type {Workbench} from '../workbench/useWorkbench';
import {ShortcutTable} from './actions/layoutActions';

export function unifiedWorkspacePreviewEnabled(): boolean {
  try { return new URLSearchParams(window.location.search).get("uw") === "1"; } catch { return false; }
}

export const PREVIEW_SPECS: LayoutPanelSpec[] = [
  { id: "outline", title: "大纲", defaultDock: "left", docks: ["left", "right", "main", "float"], defaultSize: 248, minSize: 180 },
  { id: "creative", title: "创作画布", defaultDock: "main", docks: ["main", "float"], defaultSize: 800, minSize: 320 },
  { id: "execution", title: "执行画布", defaultDock: "main", docks: ["main", "float", "right"], defaultSize: 800, minSize: 320 },
  { id: "inspector", title: "属性", defaultDock: "right", docks: ["left", "right", "bottom", "float"], defaultSize: 340, minSize: 240, maxSize: 560 },
  { id: "tasks", title: "任务", defaultDock: "bottom", docks: ["bottom", "right", "left"], defaultSize: 200, minSize: 120 },
];

/**
 * [HERMIA-FE-20261023 M1-s2fix] MUST-FIX 4: the preview shares ONE ActionRegistry + LifecycleTracker between DockLayout
 * and the existing registry-fed command palette (workbench/CommandSearch, same component App mounts). AppShell's own
 * Ctrl/⌘+K palette is a static module list (not registry-fed) and is not mounted under ?uw=1, so here Ctrl/⌘+K opens
 * CommandSearch through its own trigger button. workbench/** is reused unmodified.
 */
export function UnifiedWorkspacePreview() {
  const shared = useMemo(() => {
    const tracker = new LifecycleTracker(); const actions = new ActionRegistry(tracker); const table = new ShortcutTable();
    const workbench = {
      tracker, actions, panels: undefined as unknown as Workbench['panels'],
      context: (targetId: string | null = null) => ({token: tracker.current(), targetId, targetVersion: null, permissions: new Set<string>()}),
      open: async () => ({status: 'legacy' as const}),
    } satisfies Workbench;
    return {tracker, actions, table, workbench};
  }, []);
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
      <DockLayout specs={PREVIEW_SPECS} scope={{ userId: "local", projectId: "preview", projectInstanceId: "preview" }}
        storage={window.localStorage} loadOptions={{ inspectorPanelId: "inspector" }}
        actionRegistry={shared.actions} shortcutTable={shared.table} tracker={shared.tracker}
        toolbarStart={<span ref={host} data-testid="uw-command-host" style={{display: 'inline-flex', alignItems: 'center', gap: 6}}>
          <CommandSearch workbench={shared.workbench} onLegacy={() => {}} /><small>Ctrl／⌘+K</small></span>}
        renderPanel={(id) => <p style={{ padding: 12 }}>{PREVIEW_SPECS.find((x) => x.id === id)?.title ?? "面板"}（预览占位，尚未接入实际功能）</p>} />
  );
}
