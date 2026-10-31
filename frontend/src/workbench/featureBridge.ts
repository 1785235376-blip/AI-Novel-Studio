/**
 * [HERMIA-FE-20261022 slice M1-1] Bridge: existing FeatureLauncher ids → panel + "open panel"
 * actions. Old entry (FeatureLauncher item id) == new panel id, so App.tsx selection keeps working
 * and command search / shortcuts can be added without editing each menu (§7.4).
 * Capability statuses here are 'undetermined' until the capability ledger (M0) is reconciled by Dot.
 */
import {FEATURE_GROUPS} from '../ui/FeatureLauncher';
import type {PanelRegistry} from './panels';
import type {ActionRegistry} from './actions';
export function registerFeaturePanels(panels: PanelRegistry, actions: ActionRegistry, openFeature: (id: string) => void): () => void {
  const undo: Array<() => void> = [];
  for (const g of FEATURE_GROUPS) for (const it of g.items) {
    undo.push(panels.register({id: it.id, kind: 'feature', title: it.label, group: g.id, capability: 'undetermined', instancing: 'singleton', docks: ['main'], defaultDock: 'main'}));
    undo.push(actions.register({id: `panel.open.${it.id}`, label: `打开：${it.label}`, surfaces: ['commandSearch', 'button'], run: async () => { openFeature(it.id); return it.id; }}));
  }
  return () => undo.reverse().forEach(f => f());
}
