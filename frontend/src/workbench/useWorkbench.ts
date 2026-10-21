/**
 * [HERMIA-FE-20261022 slice M1-2] React binding: one registry set per App mount.
 * - Lifecycle epoch follows namespace/project/chapter/actor (A→B→A safe).
 * - `open(id, legacy)` routes through ActionRegistry `panel.open.<id>`; if that id is not
 *   registered (e.g. experimental groups) it falls back to the legacy path unchanged.
 * - The latest App navigation callback is read through a ref, so the guarded legacy
 *   flow (styleLeave.request → setPanel) stays the single real navigation path.
 */
import {useEffect, useMemo, useRef} from 'react';
import {ActionRegistry, type ActionContext, type ExecuteResult} from './actions';
import {LifecycleTracker, type LifecycleContext} from './lifecycle';
import {PanelRegistry} from './panels';
import {registerFeaturePanels} from './featureBridge';
import {registerNovelActionAliases} from './novelActions';

export interface Workbench {
  tracker: LifecycleTracker; panels: PanelRegistry; actions: ActionRegistry;
  context: (targetId?: string | null) => ActionContext;
  open: (featureId: string, legacy: (id: string) => void) => Promise<ExecuteResult | {status: 'legacy'}>;
}
export function useWorkbench(navigate: (featureId: string) => void, life: LifecycleContext, permissions: readonly string[] = []): Workbench {
  const nav = useRef(navigate); nav.current = navigate;
  const wb = useMemo(() => {
    const isDev = Boolean((import.meta as {env?: {DEV?: boolean}}).env?.DEV);
    const tracker = new LifecycleTracker(); const panels = new PanelRegistry(isDev); const actions = new ActionRegistry(tracker, isDev);
    registerFeaturePanels(panels, actions, id => nav.current(id));
    registerNovelActionAliases(actions, id => nav.current(id));
    return {tracker, panels, actions};
  }, []);
  // Update synchronously during render so any click after this render already sees the new epoch.
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
