// [HERMIA-FE-20261025 U2-M10] registry parity + validation + capability + presets + bounded loading (mock/jsdom evidence)
import {describe, expect, it} from 'vitest';
import {capabilityStates, layoutSpecs, LAYOUT_PRESETS, MEDIA_SLICES, panelDefinitions, shortcutsFor, UNIFIED_PANELS, UNIFIED_SHORTCUTS, validateRegistry} from './workspaceRegistry';
import {PREVIEW_SPECS} from '../UnifiedWorkspacePreview';
import {STUDIO_PREVIEW_PANELS, STUDIO_SHORTCUTS} from '../panels/studioPreviewPanels';
import {DEFAULT_LAYOUT_SHORTCUTS} from '../actions/layoutActions';
import {VIEW_SHORTCUTS} from '../actions/viewActions';
import {applyPreset} from './presets';
import {createDefaultLayout} from '../layout/model';
import {pageCap, SubscriptionHub, windowRange} from './boundedList';

describe('U2 registry parity with previously scattered tables', () => {
  it('layoutSpecs() === PREVIEW_SPECS (deep)', () => { expect(layoutSpecs()).toEqual(PREVIEW_SPECS); });
  it('panelDefinitions() === STUDIO_PREVIEW_PANELS (deep)', () => { expect(panelDefinitions()).toEqual(STUDIO_PREVIEW_PANELS); });
  it('every old shortcut is in UNIFIED_SHORTCUTS with the same key', () => {
    for (const t of [DEFAULT_LAYOUT_SHORTCUTS, STUDIO_SHORTCUTS, VIEW_SHORTCUTS] as Record<string, string | undefined>[])
      for (const [id, sc] of Object.entries(t)) expect(UNIFIED_SHORTCUTS[id]).toBe(sc);
    expect(shortcutsFor('canvas.')).toEqual({'canvas.openExecution': 'Mod+Alt+E', 'canvas.openCreative': 'Mod+Alt+I'});
  });
  it('registry validates clean; conflicts, reserved keys, bad docks and unknown preset panels are reported', () => {
    expect(validateRegistry()).toEqual([]);
    const bad = validateRegistry([...UNIFIED_PANELS, {...UNIFIED_PANELS[0]}, {...UNIFIED_PANELS[1], id: 'x', defaultDock: 'bottom'}],
      {...UNIFIED_SHORTCUTS, 'a.b': 'Ctrl+Alt+E', 'a.k': 'Mod+K'}, {...LAYOUT_PRESETS, compare: {...LAYOUT_PRESETS.compare, mainSecond: 'ghost'}});
    expect(bad.map(p => p.kind).sort()).toEqual(['bad-dock', 'duplicate-panel', 'preset-panel', 'reserved-shortcut', 'shortcut-conflict']);
  });
  it('adding a window = one entry: it appears in layout specs without other edits', () => {
    const extra = {...UNIFIED_PANELS[4], id: 'history', title: '历史'};
    expect(layoutSpecs([...UNIFIED_PANELS, extra]).map(s => s.id)).toContain('history');
  });
  it('audio slice is a reserved seam: no audio panel is exposed yet', () => {
    expect(MEDIA_SLICES.audio.state).toBe('reserved');
    const audio = {...UNIFIED_PANELS[1], id: 'audio-canvas', media: 'audio' as const};
    expect(layoutSpecs([...UNIFIED_PANELS, audio]).map(s => s.id)).not.toContain('audio-canvas');
  });
});

describe('U2 capability states', () => {
  it('without a project: context panels unavailable with an actionable next step, no raw ids', () => {
    const s = capabilityStates({hasProject: false});
    const c = s.find(x => x.id === 'creative')!;
    expect(c.available).toBe(false);
    expect(c.reason).toBe('还没有选中作品。下一步：在「作品结构」里选一部作品后再打开「创作画布」。');
    expect(s.find(x => x.id === 'outline')!.available).toBe(true);
  });
  it('with a project: honest capability text (local-only canvas, unpaged tasks)', () => {
    const s = capabilityStates({hasProject: true});
    expect(s.find(x => x.id === 'creative')!.reason).toBe('仅本机草稿：画布只存在这台浏览器的草稿里，还没有接服务端画布图。');
    expect(s.find(x => x.id === 'tasks')!.reason).toBe('部分可用：任务列表来自现有任务中心接口，没有分页；成本始终显示未知。');
  });
});

describe('U2 presets on the existing v3 layout', () => {
  const vp = {width: 1366, height: 768};
  const base = () => createDefaultLayout(layoutSpecs(), vp);
  it('default main entry is the creative canvas, single view', () => {
    const r = applyPreset(base(), 'creative', {reopen: false}); if (!r.ok) throw new Error(r.reason);
    expect(r.state.split).toBe('single');
    expect(Object.values(r.state.frames).filter(f => f.dock === 'main' && f.open).sort((a, b) => a.order - b.order)[0].id).toBe('creative');
  });
  it('single task → execution alone (no split); compare → split-h creative|execution', () => {
    const one = applyPreset(base(), 'execution-single', {reopen: true}); if (!one.ok) throw new Error();
    expect(one.state.split).toBe('single'); expect(one.state.frames.execution.order).toBe(0);
    const cmp = applyPreset(base(), 'compare', {reopen: true}); if (!cmp.ok) throw new Error();
    expect(cmp.state.split).toBe('split-h'); expect([cmp.state.frames.creative.order, cmp.state.frames.execution.order]).toEqual([0, 1]);
  });
  it('a closed panel is never reopened by a plain preset; explicit jump reopens and reports it', () => {
    const s = base(); s.frames.execution = {...s.frames.execution, open: false};
    const plain = applyPreset(s, 'execution-single', {reopen: false});
    expect(plain).toEqual({ok: false, reason: '目标面板已关闭。', next: '从「重新打开」菜单打开它。'});
    const jump = applyPreset(s, 'execution-single', {reopen: true}); if (!jump.ok) throw new Error();
    expect(jump.reopened).toEqual(['execution']); expect(jump.state.frames.execution.open).toBe(true);
  });
});

describe('U2 bounded loading + controlled subscriptions', () => {
  it('windowRange renders only visible rows + overscan', () => {
    expect(windowRange(10000, 0, 28, 560)).toEqual({start: 0, end: 26});
    expect(windowRange(10000, 28 * 5000, 28, 560)).toEqual({start: 4994, end: 5026});
    expect(windowRange(3, 0, 28, 560)).toEqual({start: 0, end: 3});
    expect(windowRange(0, 0, 28, 560)).toEqual({start: 0, end: 0});
  });
  it('pageCap says how many are hidden and what to do', () => {
    expect(pageCap(1000, 1)).toEqual({shown: 100, hidden: 900, text: '还有 900 项没有显示。下一步：点「再显示 100 项」，或用搜索缩小范围。'});
    expect(pageCap(80, 1)).toEqual({shown: 80, hidden: 0, text: null});
  });
  it('hub coalesces bursts per microtask, caps subscribers, and drops everything after dispose', async () => {
    const h = new SubscriptionHub<number>(3); const got: number[] = [];
    h.subscribe('t1', v => got.push(v)); h.subscribe('t1', () => {}); h.subscribe('t2', () => {});
    const noop = h.subscribe('t3', () => got.push(-1));
    expect(h.size()).toBe(3); expect(h.dropped).toBe(1); noop();
    for (let i = 0; i < 1000; i++) h.publish('t1', i);
    await Promise.resolve();
    expect(got).toEqual([999]); expect(h.notifies).toBe(2);
    h.publish('t1', 5); h.dispose(); await Promise.resolve();
    expect(got).toEqual([999]); expect(h.size()).toBe(0);
  });
});
