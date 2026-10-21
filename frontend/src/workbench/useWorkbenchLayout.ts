/**
 * [HERMIA-FE-20261022 H-P1-01] layout.mode basic|pro — single source via loadLayout/saveLayout.
 * Switching mode must not clear selection / panel (caller enforces pro→basic Tab rule).
 */
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  DEFAULT_LAYOUT,
  loadLayout,
  saveLayout,
  type LayoutScope,
  type StorageLike,
  type WorkbenchLayout,
} from './layout';
import type {PanelRegistry} from './panels';
import type {ActionRegistry} from './actions';

export type ShellMode = WorkbenchLayout['mode'];

function browserStorage(): StorageLike | null {
  if (typeof window === 'undefined') return null;
  try { return window.localStorage; } catch { return null; }
}

export function useWorkbenchLayout(scope: LayoutScope, panels: PanelRegistry) {
  const scopeKey = `${scope.userId}::${scope.projectId}::${scope.projectInstanceId}`;
  const st = useMemo(() => browserStorage(), []);
  const [layout, setLayout] = useState<WorkbenchLayout>(() => {
    if (!st) return structuredClone(DEFAULT_LAYOUT);
    return loadLayout(st, scope, panels).layout;
  });
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  useEffect(() => {
    if (!st) return;
    const report = loadLayout(st, scope, panels);
    setLayout(report.layout);
  }, [scopeKey, st, panels, scope]);

  const persist = useCallback((next: WorkbenchLayout) => {
    setLayout(next);
    layoutRef.current = next;
    if (st) saveLayout(st, scope, next);
  }, [st, scope]);

  const setMode = useCallback((mode: ShellMode) => {
    const prev = layoutRef.current;
    if (prev.mode === mode) return prev;
    const next = {...prev, mode};
    persist(next);
    return next;
  }, [persist]);

  const toggleMode = useCallback(() => {
    const prev = layoutRef.current;
    return setMode(prev.mode === 'pro' ? 'basic' : 'pro');
  }, [setMode]);

  return {layout, mode: layout.mode, setMode, toggleMode, persist};
}

/** Register layout.* actions for CommandSearch (chrome hide ≠ command disable). */
export function registerLayoutActions(
  actions: ActionRegistry,
  api: {
    getMode: () => ShellMode;
    setMode: (mode: ShellMode) => void;
    reset?: () => void;
  },
): () => void {
  const undo: Array<() => void> = [];
  undo.push(actions.register({
    id: 'layout.toggleMode',
    label: '切换普通/专业模式',
    surfaces: ['commandSearch', 'button'],
    run: async () => {
      const next = api.getMode() === 'pro' ? 'basic' : 'pro';
      api.setMode(next);
      return next;
    },
  }));
  undo.push(actions.register({
    id: 'layout.setMode.basic',
    label: '切换到普通模式',
    surfaces: ['commandSearch'],
    run: async () => { api.setMode('basic'); return 'basic'; },
  }));
  undo.push(actions.register({
    id: 'layout.setMode.pro',
    label: '切换到专业模式',
    surfaces: ['commandSearch'],
    run: async () => { api.setMode('pro'); return 'pro'; },
  }));
  if (api.reset) {
    undo.push(actions.register({
      id: 'layout.reset',
      label: '恢复默认布局（不删草稿）',
      surfaces: ['commandSearch'],
      requiresConfirmation: true,
      run: async () => { api.reset!(); return 'reset'; },
    }));
  }
  return () => undo.reverse().forEach(fn => fn());
}

/** Panels / surfaces treated as exec or director chrome for pro→basic Tab rule. */
export const EXEC_OR_DIRECTOR_PANELS = new Set([
  'canvas.exec',
  'director.console',
  'experimental', // creative dual-canvas / director live under experimental workbench
]);

export function shouldLeaveExecOrDirector(panel: string, creativeWorkbenchOpen: boolean): boolean {
  return creativeWorkbenchOpen || EXEC_OR_DIRECTOR_PANELS.has(panel);
}
