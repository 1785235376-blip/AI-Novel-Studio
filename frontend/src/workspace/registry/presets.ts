/**
 * [HERMIA-FE-20261025 U2-M6] Apply a layout preset to the EXISTING v3 LayoutState (no parallel layout owner): only the
 * main-zone order and split mode change. Closed target panels are reopened only when the caller says the user
 * explicitly asked (task jump / compare button); a plain preset never resurrects a panel the user closed.
 */
import type {LayoutState} from '../layout/model';
import {LAYOUT_PRESETS, type LayoutPresetId} from './workspaceRegistry';

export type PresetResult = {ok: true; state: LayoutState; reopened: string[]} | {ok: false; reason: string; next: string};
export function applyPreset(state: LayoutState, id: LayoutPresetId, opts: {reopen: boolean}): PresetResult {
  const p = LAYOUT_PRESETS[id]; const want = [p.mainFront, p.mainSecond].filter(Boolean) as string[];
  const frames = {...state.frames}; const reopened: string[] = [];
  for (const w of want) {
    const f = frames[w]; if (!f) return {ok: false, reason: '这个面板在当前布局里不存在。', next: '可以点「恢复默认布局」后再试。'};
    if (!f.open) { if (!opts.reopen) return {ok: false, reason: '目标面板已关闭。', next: '从「重新打开」菜单打开它。'}; frames[w] = {...f, open: true}; reopened.push(w); }
  }
  const main = Object.values(frames).filter(f => f.dock === 'main' && f.open).sort((a, b) => a.order - b.order).map(f => f.id);
  const ordered = [...want.filter(w => main.includes(w)), ...main.filter(m => !want.includes(m))];
  ordered.forEach((mid, i) => { frames[mid] = {...frames[mid], order: i}; });
  const split = p.split === 'split-h' && ordered.length < 2 ? 'single' : p.split;
  return {ok: true, state: {...state, frames, split, focusId: want.find(w => frames[w].dock === 'main') ?? want[0]}, reopened};
}
