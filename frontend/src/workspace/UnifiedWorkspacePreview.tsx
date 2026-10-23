// [HERMIA-FE-20261023 M1, applied M1-s2] Opt-in preview host for DockLayout (?uw=1 only).
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {createPreviewPanelRegistry, InspectorPanel, OutlinePanel, pickDefaultNovel, registerNovelPreviewActions, useNovels} from './panels/novelPreviewPanels';
import {DockLayout, type LayoutPanelSpec} from './layout';
import type {PanelRenderApi} from './layout/DockLayout';
import {ActionRegistry} from '../workbench/actions';
import {LifecycleTracker} from '../workbench/lifecycle';
import {CommandSearch} from '../workbench/CommandSearch';
import type {Workbench} from '../workbench/useWorkbench';
import {ShortcutTable} from './actions/layoutActions';

export function unifiedWorkspacePreviewEnabled(): boolean {
  try { return new URLSearchParams(window.location.search).get("uw") === "1"; } catch { return false; }
}

export const PREVIEW_SPECS: LayoutPanelSpec[] = [
  { id: "outline", title: "作品结构", defaultDock: "left", docks: ["left", "right", "main", "float"], defaultSize: 248, minSize: 180 },
  { id: "creative", title: "创作画布", defaultDock: "main", docks: ["main", "float"], defaultSize: 800, minSize: 320 },
  { id: "execution", title: "执行画布", defaultDock: "main", docks: ["main", "float", "right"], defaultSize: 800, minSize: 320 },
  { id: "inspector", title: "章节属性", defaultDock: "right", docks: ["left", "right", "bottom", "float"], defaultSize: 340, minSize: 240, maxSize: 560 },
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
    // [HERMIA-FE-20261023 M1-s3] real panels go through the workbench PanelRegistry (contract §1).
    const panels = createPreviewPanelRegistry();
    workbench.panels = panels as unknown as Workbench['panels'];
    return {tracker, actions, table, workbench, panels};
  }, []);
  // [HERMIA-FE-20261023 M1-s3] shared selection: outline → inspector linkage. GET-only on load.
  const qc = useQueryClient();
  const novels = useNovels();
  const [novelId, setNovelId] = useState<string | null>(null);
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const inspectorDirty = useRef(false);
  const novelRef = useRef(novelId); novelRef.current = novelId;
  useEffect(() => { if (!novelId && novels.data?.length) setNovelId(pickDefaultNovel(novels.data)?.id ?? null); }, [novels.data, novelId]);
  useEffect(() => registerNovelPreviewActions(shared.actions, qc, () => novelRef.current), [shared.actions, qc]);
  const guardSwitch = (apply: () => void) => {
    if (inspectorDirty.current) { setBlocked('「章节属性」里有未保存的标题修改，请先保存或放弃后再切换。'); return; }
    setBlocked(null); apply();
  };
  const ctx = useCallback((input?: unknown) => ({...shared.workbench.context(chapterId), input}), [shared.workbench, chapterId]);
  const renderPanel = (id: string, api: PanelRenderApi) => {
    if (id === 'outline') return <OutlinePanel novelId={novelId} novels={novels} onNovel={v => guardSwitch(() => { setNovelId(v); setChapterId(null); })}
      selectedId={chapterId ?? undefined} onSelect={v => guardSwitch(() => setChapterId(v))} blockedNotice={blocked} ctx={() => ctx()} actions={shared.actions} />;
    if (id === 'inspector') return <InspectorPanel novelId={novelId} chapterId={chapterId} api={api} ctx={ctx} actions={shared.actions} dirtyRef={inspectorDirty} />;
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
      <DockLayout specs={PREVIEW_SPECS} scope={{ userId: "local", projectId: "preview", projectInstanceId: "preview" }}
        storage={window.localStorage} loadOptions={{ inspectorPanelId: "inspector" }}
        actionRegistry={shared.actions} shortcutTable={shared.table} tracker={shared.tracker}
        toolbarStart={<span ref={host} data-testid="uw-command-host" style={{display: 'inline-flex', alignItems: 'center', gap: 6}}>
          <CommandSearch workbench={shared.workbench} onLegacy={() => {}} /><small>Ctrl／⌘+K</small></span>}
        renderPanel={renderPanel} />
  );
}
