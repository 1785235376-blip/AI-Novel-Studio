/**
 * [HERMIA-FE-20261025 U2-M6] Context-navigation actions on the shared ActionRegistry (button / command search /
 * shortcut all go through execute). Read-only navigation: no network, no model call, no production write.
 */
import type {ActionRegistry, Availability} from '../../workbench/actions';
import {normalizeShortcut, type ShortcutTable} from './layoutActions';
import {shortcutsFor} from '../registry/workspaceRegistry';

export const NAV_ACTION_IDS = {returnToOrigin: 'nav.returnToOrigin', compare: 'nav.compare'} as const;
export interface NavActionHost { canReturn(): boolean; returnToOrigin(): void; hasProject(): boolean; toggleCompare(): void; }
export function registerNavActions(reg: ActionRegistry, table: ShortcutTable, host: NavActionHost) {
  const sc = shortcutsFor('nav.'); const conflicts: {actionId: string; shortcut: string; conflictWith: string}[] = []; const undo: (() => void)[] = [];
  const defs = [
    {id: NAV_ACTION_IDS.returnToOrigin, label: '返回原位置', surfaces: ['toolbar', 'shortcut', 'commandSearch'] as const,
      available: (): Availability => host.canReturn() ? {enabled: true} : {enabled: false, reason: '还没有可以返回的位置（从任务跳转后才会记录）'},
      run: async () => { host.returnToOrigin(); }},
    {id: NAV_ACTION_IDS.compare, label: '对照创作与执行画布', surfaces: ['toolbar', 'shortcut', 'commandSearch'] as const,
      available: (): Availability => host.hasProject() ? {enabled: true} : {enabled: false, reason: '还没有选中作品'},
      run: async () => { host.toggleCompare(); }},
  ];
  for (const d of defs) {
    const s = sc[d.id]; let def: typeof d & {shortcut?: string} = d;
    if (s) { const c = table.claim(s, d.id); if (!c.ok) conflicts.push({actionId: d.id, shortcut: normalizeShortcut(s), conflictWith: c.conflictWith}); else { def = {...d, shortcut: s}; undo.push(() => table.release(s, d.id)); } }
    undo.push(reg.register(def));
  }
  return {conflicts, dispose: () => { while (undo.length) undo.pop()!(); }};
}
