/**
 * [HERMIA-FE-20261022 slice M1-2 / overnight] React binding: one registry set per App mount.
 * - Lifecycle epoch follows namespace/project/chapter/actor (A→B→A safe).
 * - `open(id, legacy)` routes through ActionRegistry `panel.open.<id>`; unknown ids → legacy.
 * - Novel focus targets (aiWriting / chapterTree / editor) do not invent FL ids.
 */
import {useEffect, useMemo, useRef} from 'react';
import {ActionRegistry, type ActionContext, type ExecuteResult} from './actions';
import {LifecycleTracker, type LifecycleContext} from './lifecycle';
import {PanelRegistry} from './panels';
import {registerFeaturePanels} from './featureBridge';
import {registerNovelActionAliases, type NovelFocusTarget} from './novelActions';

export type {NovelFocusTarget};

export interface Workbench {
  tracker: LifecycleTracker; panels: PanelRegistry; actions: ActionRegistry;
  context: (targetId?: string | null) => ActionContext;
  open: (featureId: string, legacy: (id: string) => void) => Promise<ExecuteResult | {status: 'legacy'}>;
}
export function useWorkbench(
  navigate: (featureId: string) => void,
  life: LifecycleContext,
  permissions: readonly string[] = [],
  focusSurface?: (target: NovelFocusTarget) => void,
): Workbench {
  const nav = useRef(navigate); nav.current = navigate;
  const focus = useRef(focusSurface); focus.current = focusSurface;
  const wb = useMemo(() => {
    const isDev = Boolean((import.meta as {env?: {DEV?: boolean}}).env?.DEV);
    const tracker = new LifecycleTracker(); const panels = new PanelRegistry(isDev); const actions = new ActionRegistry(tracker, isDev);
    registerFeaturePanels(panels, actions, id => nav.current(id));
    registerNovelActionAliases(actions, id => nav.current(id), t => focus.current?.(t));
    return {tracker, panels, actions};
  }, []);
  wb.tracker.update(life);
  const perms = useRef(new Set(permissions)); perms.current = new Set(permissions);
  const api = useRef<Workbench>();
  if (!api.current) api.current = {
    ...wb,
    context: (targetId = null) => ({token: wb.tracker.current(), targetId, targetVersion: null, permissions: perms.current}),
    open: async (featureId, legacy) => {
      if (!wb.actions.get(`panel.open.${featureId}`)) { legacy(featureId); return {status: 'legacy'}; }
      return wb.actions.execute(`panel.open.${featureId}`, api.current!.context(featureId));
    },
  };
  useEffect(() => () => { wb.tracker.invalidate(); }, [wb]);
  return api.current;
}
