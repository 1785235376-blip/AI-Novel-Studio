/**
 * [HERMIA-FE-20261024 VW-M2/M4] Workset + panel-focus actions on the shared ActionRegistry. Buttons, command search
 * and shortcuts all go through registry.execute (availability re-checked at execution, pending dedupe).
 * Pure UI/local actions: no network, no model calls.
 */
import type {ActionRegistry, Availability} from '../../workbench/actions';
import {normalizeShortcut, type ShortcutTable} from './layoutActions';
import {shortcutsFor} from '../registry/workspaceRegistry';
import type {DockLayoutApi} from '../layout/DockLayout';
import type {ViewPrefs} from '../state/viewPreferences';
import {captureWorkset, deleteWorkset, renameWorkset, resolveWorkset} from '../layout/worksets';
import type {PanelFocusTracker} from '../state/panelFocus';

export const VIEW_ACTION_IDS = {
  openViews: 'view.worksets.open', save: 'view.worksets.save', apply: 'view.worksets.apply',
  rename: 'view.worksets.rename', remove: 'view.worksets.delete',
  nextPanel: 'view.panel.next', prevPanel: 'view.panel.prev', lastPanel: 'view.panel.last',
} as const;
/** Checked against layout (Mod+Alt+0/O/C/S/P), studio (Mod+Alt+E/I/T) and reserved Mod+K. */
// [HERMIA-FE-20261025 INT] single source of truth: the unified registry (U2 parity-tested values).
export const VIEW_SHORTCUTS: Partial<Record<string, string>> = shortcutsFor('view.');
export interface ViewActionHost {
  layout(): DockLayoutApi | null;
  prefs(): ViewPrefs;
  focus(): PanelFocusTracker | null;
  openViews(): void;
  onChange(msg: string): void;
}
const yes: Availability = {enabled: true};
const LAYOUT_NOT_READY = '布局还没有准备好';

export function registerViewActions(reg: ActionRegistry, table: ShortcutTable, host: ViewActionHost) {
  const conflicts: {actionId: string; shortcut: string; conflictWith: string}[] = [];
  const undo: (() => void)[] = [];
  const needLayout = (): Availability => (host.layout() ? yes : {enabled: false, reason: LAYOUT_NOT_READY});
  const str = (v: unknown, what: string) => { if (typeof v !== 'string' || !v) throw new Error(`缺少${what}`); return v; };
  const commit = (r: {ok: true; value: import('../state/viewPreferences').StoredWorkset[]} | {ok: false; reason: string}, done: string) => {
    if (!r.ok) throw new Error(r.reason);
    if (!host.prefs().setWorksets(r.value)) throw new Error('项目已经切换，这次修改没有保存。');
    const st = host.prefs().status();
    host.onChange(st.reason === 'write-failed' ? `${done}，但没能写入本机存储，只在本次会话有效。` : st.mode === 'session' ? `${done}（仅本次会话有效）。` : `${done}。`);
  };
  const focusRun = (f: (t: PanelFocusTracker) => {ok: true; id: string} | {ok: false; reason: string}) => async () => {
    const t = host.focus(); if (!t) throw new Error(LAYOUT_NOT_READY);
    const r = f(t); if (!r.ok) throw new Error(r.reason); return r.id;
  };
  const defs = [
    {id: VIEW_ACTION_IDS.openViews, label: '打开视图管理', surfaces: ['toolbar', 'shortcut', 'commandSearch'] as const,
      available: needLayout, run: async () => { host.openViews(); return true; }},
    {id: VIEW_ACTION_IDS.save, label: '把当前布局保存为视图', surfaces: ['button'] as const, available: needLayout,
      run: async (ctx: {input?: unknown}) => {
        const name = str(ctx.input, '视图名称'); const api = host.layout(); if (!api) throw new Error(LAYOUT_NOT_READY);
        commit(captureWorkset(api.getState(), name, host.prefs().getWorksets()), `已保存视图「${name.trim()}」`); return name;
      }},
    {id: VIEW_ACTION_IDS.apply, label: '应用视图', surfaces: ['button'] as const, available: needLayout,
      run: async (ctx: {input?: unknown}) => {
        const id = str(ctx.input, '视图'); const api = host.layout(); if (!api) throw new Error(LAYOUT_NOT_READY);
        const w = host.prefs().getWorksets().find(x => x.id === id); if (!w) throw new Error('这个视图已经不存在。');
        const r = resolveWorkset(w, api.specs(), api.viewport(), api.getState()); if (!r.ok) throw new Error(r.reason);
        const a = api.apply(r.value); if (!a.ok) throw new Error(a.reason);
        host.onChange(`已应用视图「${w.name}」。`); return id;
      }},
    {id: VIEW_ACTION_IDS.rename, label: '重命名视图', surfaces: ['button'] as const,
      run: async (ctx: {input?: unknown}) => {
        const {id, name} = (ctx.input ?? {}) as {id?: string; name?: string};
        commit(renameWorkset(host.prefs().getWorksets(), str(id, '视图'), name ?? ''), `已重命名为「${(name ?? '').trim()}」`); return id;
      }},
    {id: VIEW_ACTION_IDS.remove, label: '删除视图', surfaces: ['button'] as const,
      run: async (ctx: {input?: unknown}) => {
        const id = str(ctx.input, '视图'); const w = host.prefs().getWorksets().find(x => x.id === id);
        commit(deleteWorkset(host.prefs().getWorksets(), id), `已删除视图「${w?.name ?? ''}」`); return id;
      }},
    {id: VIEW_ACTION_IDS.nextPanel, label: '焦点移到下一个面板', surfaces: ['shortcut', 'commandSearch'] as const, available: needLayout, run: focusRun(t => t.next(1))},
    {id: VIEW_ACTION_IDS.prevPanel, label: '焦点移到上一个面板', surfaces: ['shortcut', 'commandSearch'] as const, available: needLayout, run: focusRun(t => t.next(-1))},
    {id: VIEW_ACTION_IDS.lastPanel, label: '返回刚才的面板', surfaces: ['shortcut', 'commandSearch'] as const, available: needLayout, run: focusRun(t => t.returnToLast())},
  ];
  for (const def of defs) {
    let d: typeof def & {shortcut?: string} = def;
    const sc = VIEW_SHORTCUTS[def.id];
    if (sc) {
      const c = table.claim(sc, def.id);
      if (!c.ok) conflicts.push({actionId: def.id, shortcut: normalizeShortcut(sc), conflictWith: c.conflictWith});
      else { d = {...def, shortcut: sc}; undo.push(() => table.release(sc, def.id)); }
    }
    undo.push(reg.register(d as never));
  }
  return {conflicts, dispose: () => { while (undo.length) undo.pop()!(); }};
}
