/**
 * [HERMIA-FE-20261022 §7.4] Isolated extension proof. devOnly=true → invisible in production
 * listings. Registers ONE panel + ONE action without editing menus/toolbars/command search.
 * Not a business object; creates no task, asset or server state.
 */
import type {PanelRegistry} from './panels';
import type {ActionRegistry} from './actions';
export const DEMO_PANEL_ID = 'dev.demo.extension';
export function registerDemoExtension(panels: PanelRegistry, actions: ActionRegistry, log: string[]): () => void {
  const a = panels.register({id: DEMO_PANEL_ID, kind: 'demo', title: '扩展示范面板（仅开发）', capability: 'local-only', instancing: 'per-object', docks: ['right', 'main'], defaultDock: 'right', requiresContext: ['node'], devOnly: true, onDispose: k => log.push(`dispose:${k}`)});
  const b = actions.register({id: 'dev.demo.inspect', label: '示范：检查选中节点', surfaces: ['contextMenu', 'commandSearch'], devOnly: true, permissions: ['canvas.read'],
    available: ctx => ctx.targetId ? {enabled: true} : {enabled: false, reason: '请先选中一个节点'},
    run: async ctx => { log.push(`inspect:${ctx.targetId}`); return ctx.targetId; }});
  return () => { b(); a(); };
}
