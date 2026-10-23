/**
 * [HERMIA-FE-20261023 M1-s2] Layout actions registered through the EXISTING registry
 * `frontend/src/workbench/actions.ts` (ActionRegistry: stable ids, availability + disabled reason, pending
 * de-dup = running state / double-trigger guard, stale lifecycle check) and its `shouldHandleShortcut`
 * text-input / IME guard. workbench/** stays unmodified (FILE_OWNERSHIP.md); the only new piece here is a
 * ShortcutTable for conflict detection, which ActionRegistry does not provide.
 * Contract: docs/architecture/unified-workspace-contract.md §2.
 */
import type {ActionContext, ActionDefinition, ActionRegistry, Availability} from '../../workbench/actions';
import {shouldHandleShortcut} from '../../workbench/actions';
import {closedPanels, SPLIT_MODES, type LayoutAction, type LayoutPanelSpec, type LayoutState, type SplitMode} from '../layout/model';

export const LAYOUT_ACTION_IDS = {
  reset: 'layout.reset',
  reopen: 'layout.reopenPanel',
  toggleCollapse: 'layout.toggleCollapse',
  split: 'layout.switchSplit',
} as const;
export type LayoutActionId = typeof LAYOUT_ACTION_IDS[keyof typeof LAYOUT_ACTION_IDS];

/** Shortcuts already owned elsewhere in the product; layout actions must not take them. */
export const RESERVED_SHORTCUTS: Readonly<Record<string, string>> = {'Mod+K': 'command-search (ui/AppShell.tsx)'};

export const DEFAULT_LAYOUT_SHORTCUTS: Readonly<Record<LayoutActionId, string>> = {
  'layout.reset': 'Mod+Alt+0',
  'layout.reopenPanel': 'Mod+Alt+O',
  'layout.toggleCollapse': 'Mod+Alt+C',
  'layout.switchSplit': 'Mod+Alt+S',
};

/** Canonical form: modifiers in fixed order Mod, Alt, Shift; key upper-cased. Ctrl/Cmd/Meta all map to Mod. */
export function normalizeShortcut(s: string): string {
  const parts = s.split('+').map(p => p.trim()).filter(Boolean);
  const mods = new Set<string>(); let key = '';
  for (const p of parts) {
    const l = p.toLowerCase();
    if (['mod', 'ctrl', 'control', 'cmd', 'meta', 'command'].includes(l)) mods.add('Mod');
    else if (['alt', 'option'].includes(l)) mods.add('Alt');
    else if (l === 'shift') mods.add('Shift');
    else key = p.length === 1 ? p.toUpperCase() : p;
  }
  return [...['Mod', 'Alt', 'Shift'].filter(m => mods.has(m)), key].join('+');
}

export function shortcutFromEvent(e: {key: string; code?: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean; shiftKey?: boolean}): string | null {
  if (['Control', 'Meta', 'Alt', 'Shift'].includes(e.key)) return null;
  // With Alt held, e.key may be a composed symbol (macOS); fall back to the physical key code.
  let key = e.key;
  if (e.code && /^Key[A-Z]$/.test(e.code)) key = e.code.slice(3);
  else if (e.code && /^Digit\d$/.test(e.code)) key = e.code.slice(5);
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push('Mod');
  if (e.altKey) parts.push('Alt');
  if (e.shiftKey) parts.push('Shift');
  parts.push(key);
  return normalizeShortcut(parts.join('+'));
}

export type ClaimResult = {ok: true} | {ok: false; conflictWith: string};
/** One owner per shortcut; a second claim is rejected (never silently overrides). */
export class ShortcutTable {
  private map = new Map<string, string>();
  constructor(reserved: Readonly<Record<string, string>> = RESERVED_SHORTCUTS) {
    for (const [k, v] of Object.entries(reserved)) this.map.set(normalizeShortcut(k), v);
  }
  claim(shortcut: string, actionId: string): ClaimResult {
    const k = normalizeShortcut(shortcut); const owner = this.map.get(k);
    if (owner && owner !== actionId) return {ok: false, conflictWith: owner};
    this.map.set(k, actionId); return {ok: true};
  }
  release(shortcut: string, actionId: string) { const k = normalizeShortcut(shortcut); if (this.map.get(k) === actionId) this.map.delete(k); }
  lookup(shortcut: string): string | undefined { return this.map.get(normalizeShortcut(shortcut)); }
}

export interface LayoutActionHost {
  getState(): LayoutState;
  specs: readonly LayoutPanelSpec[];
  dispatch(a: LayoutAction): void;
  /** Opens the 恢复默认布局 confirm dialog; the reset itself only happens on confirm. */
  requestReset(): void;
}

/** Run synchronously (state changes inside the triggering event), but satisfy ActionDefinition.run's Promise type. */
const sync = (fn: (ctx: ActionContext) => unknown) => (ctx: ActionContext): Promise<unknown> => {
  try { return Promise.resolve(fn(ctx)); } catch (e) { return Promise.reject(e); }
};
const yes: Availability = {enabled: true};
const SPLIT_ORDER: readonly SplitMode[] = SPLIT_MODES;
// run bodies are synchronous: ActionRegistry.execute calls run synchronously and keeps the pending key until the
// awaited result settles (next microtask), so a same-tick double trigger is still reported as 'duplicate'.

export function layoutActionDefinitions(host: LayoutActionHost, shortcuts: Partial<Record<LayoutActionId, string>> = DEFAULT_LAYOUT_SHORTCUTS): ActionDefinition[] {
  const st = () => host.getState();
  const reopenTarget = (ctx: ActionContext): string | null => {
    const closed = closedPanels(st()).map(f => f.id).filter(id => host.specs.some(s => s.id === id));
    const want = (typeof ctx.input === 'string' ? ctx.input : ctx.targetId) ?? null;
    if (want) return closed.includes(want) ? want : null;
    return closed[0] ?? null;
  };
  const collapseTarget = (ctx: ActionContext): string | null => {
    const id = ctx.targetId ?? st().focusId; const f = id ? st().frames[id] : undefined;
    return f && f.open && host.specs.some(s => s.id === id) ? id : null;
  };
  return [
    {
      id: LAYOUT_ACTION_IDS.reset, label: '恢复默认布局', surfaces: ['toolbar', 'shortcut', 'commandSearch'], shortcut: shortcuts['layout.reset'],
      // Confirmation is the DockLayout dialog (contract §2); this action only opens it.
      run: sync(() => { host.requestReset(); return 'confirm-opened'; }),
    },
    {
      id: LAYOUT_ACTION_IDS.reopen, label: '重新打开面板', surfaces: ['toolbar', 'shortcut', 'commandSearch'], shortcut: shortcuts['layout.reopenPanel'],
      available: ctx => {
        if (!closedPanels(st()).length) return {enabled: false, reason: '没有已关闭的面板'};
        return reopenTarget(ctx) ? yes : {enabled: false, reason: '这个面板没有关闭'};
      },
      run: sync(ctx => { const id = reopenTarget(ctx); if (!id) throw new Error('没有可重新打开的面板'); host.dispatch({type: 'reopen', id}); return id; }),
    },
    {
      id: LAYOUT_ACTION_IDS.toggleCollapse, label: '折叠／展开当前面板', surfaces: ['contextMenu', 'shortcut', 'commandSearch'], shortcut: shortcuts['layout.toggleCollapse'],
      available: ctx => collapseTarget(ctx) ? yes : {enabled: false, reason: '先点一下要折叠的面板'},
      run: sync(ctx => { const id = collapseTarget(ctx); if (!id) throw new Error('没有选中的面板'); host.dispatch({type: 'collapse', id}); return id; }),
    },
    {
      id: LAYOUT_ACTION_IDS.split, label: '切换分屏方式', surfaces: ['toolbar', 'shortcut', 'commandSearch'], shortcut: shortcuts['layout.switchSplit'],
      available: ctx => (ctx.input === undefined || SPLIT_ORDER.includes(ctx.input as SplitMode)) ? yes : {enabled: false, reason: '不支持这种分屏方式'},
      run: sync(ctx => {
        const mode = (ctx.input as SplitMode | undefined) ?? SPLIT_ORDER[(SPLIT_ORDER.indexOf(st().split) + 1) % SPLIT_ORDER.length];
        host.dispatch({type: 'split', mode}); return mode;
      }),
    },
  ];
}

export interface RegisteredLayoutActions { dispose(): void; conflicts: {actionId: string; shortcut: string; conflictWith: string}[]; }

/** Registers into the existing ActionRegistry. A conflicting shortcut is dropped (action still registered, no key). */
export function registerLayoutActions(registry: ActionRegistry, table: ShortcutTable, host: LayoutActionHost, shortcuts?: Partial<Record<LayoutActionId, string>>): RegisteredLayoutActions {
  const conflicts: RegisteredLayoutActions['conflicts'] = []; const undo: (() => void)[] = [];
  for (const def of layoutActionDefinitions(host, shortcuts)) {
    let d = def;
    if (def.shortcut) {
      const c = table.claim(def.shortcut, def.id);
      if (!c.ok) { conflicts.push({actionId: def.id, shortcut: normalizeShortcut(def.shortcut), conflictWith: c.conflictWith}); d = {...def, shortcut: undefined}; }
      else { const sc = def.shortcut; undo.push(() => table.release(sc, def.id)); }
    }
    undo.push(registry.register(d));
  }
  return {conflicts, dispose: () => { while (undo.length) undo.pop()!(); }};
}

/** Keyboard dispatch: ignores editable targets / IME (shouldHandleShortcut) and unknown chords. */
export function actionIdForKey(e: Parameters<typeof shortcutFromEvent>[0] & {isComposing?: boolean; keyCode?: number; target?: unknown}, table: ShortcutTable, ids: readonly string[]): string | null {
  if (!shouldHandleShortcut(e)) return null;
  const sc = shortcutFromEvent(e); if (!sc || !sc.startsWith('Mod+')) return null;
  const id = table.lookup(sc);
  return id && ids.includes(id) ? id : null;
}
