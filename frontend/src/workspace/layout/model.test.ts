// [HERMIA-FE-20261023 M1] Reducer tests (unit level; IDs map to ACCEPTANCE_MATRIX.md).
import {describe, expect, it} from 'vitest';
import type {LayoutState} from './model';
import {closedPanels, createDefaultLayout, layoutReducer, panelsIn, zoneFromPoint} from './model';
import {SPECS, VP} from './testSpecs';

const r = layoutReducer({specs: SPECS, viewport: VP});
const base = () => createDefaultLayout(SPECS, VP);

describe('layout model', () => {
  it('M1-01 float move clamps to viewport, keeps header reachable', () => {
    let s = r(base(), {type: 'dock', id: 'inspector', dock: 'float'});
    s = r(s, {type: 'moveFloat', id: 'inspector', x: 5000, y: -50});
    expect(s.frames.inspector.floatRect!.x).toBe(VP.width - 48);
    expect(s.frames.inspector.floatRect!.y).toBe(0);
  });
  it('M1-02 resize honours minSize, maxSize and viewport fraction', () => {
    expect(r(base(), {type: 'resize', id: 'inspector', size: 10}).frames.inspector.size).toBe(240);
    expect(r(base(), {type: 'resize', id: 'inspector', size: 9999}).frames.inspector.size).toBe(560);
    const small = layoutReducer({specs: SPECS, viewport: {width: 600, height: 400}});
    // [HERMIA-FE-20261023 M1-fix] MF-2: at 600px the 60% cap (360) is now also bounded by main≥320 + inspector 340 → minSize.
    expect(small(base(), {type: 'resize', id: 'outline', size: 9999}).frames.outline.size).toBe(180);
    expect(r(base(), {type: 'resize', id: 'outline', size: NaN}).frames.outline.size).toBe(248);
  });
  it('M1-03/M1-04 dock and redock: old relation removed, orders compacted', () => {
    let s = r(base(), {type: 'dock', id: 'tasks', dock: 'right', index: 0});
    expect(panelsIn(s, 'right').map(f => f.id)).toEqual(['tasks', 'inspector']);
    expect(panelsIn(s, 'bottom')).toEqual([]);
    s = r(s, {type: 'dock', id: 'tasks', dock: 'left'});
    expect(panelsIn(s, 'right').map(f => [f.id, f.order])).toEqual([['inspector', 0]]);
    expect(panelsIn(s, 'left').map(f => f.id)).toEqual(['outline', 'tasks']);
    // disallowed dock is a no-op
    expect(r(s, {type: 'dock', id: 'canvas', dock: 'bottom'})).toBe(s);
  });
  it('M1-05 collapse/expand keeps size', () => {
    let s = r(base(), {type: 'resize', id: 'outline', size: 300});
    s = r(s, {type: 'collapse', id: 'outline'}); expect(s.frames.outline.collapsed).toBe(true);
    s = r(s, {type: 'collapse', id: 'outline'}); expect(s.frames.outline).toMatchObject({collapsed: false, size: 300});
  });
  it('M1-06/M1-23 close + reopen repeatedly never duplicates', () => {
    let s = base();
    for (let i = 0; i < 20; i++) { s = r(s, {type: 'close', id: 'inspector'}); s = r(s, {type: 'reopen', id: 'inspector'}); }
    expect(Object.keys(s.frames).filter(k => k === 'inspector')).toHaveLength(1);
    expect(s.frames.inspector.open).toBe(true);
    s = r(s, {type: 'close', id: 'inspector'});
    expect(closedPanels(s).map(f => f.id)).toEqual(['inspector']);
    expect(r(s, {type: 'reopen', id: 'ghost'})).toBe(s);
  });
  it('M1-07 split switch validates mode', () => {
    expect(r(base(), {type: 'split', mode: 'split-h'}).split).toBe('split-h');
    expect(r(base(), {type: 'split', mode: 'bogus' as never}).split).toBe('single');
  });
  it('M1-08 reset restores defaults and keeps preserved unknown-panel configs', () => {
    let s: LayoutState = {...base(), preserved: {legacyPanel: {id: 'legacyPanel', dock: 'left'}}};
    s = r(s, {type: 'dock', id: 'tasks', dock: 'left'}); s = r(s, {type: 'close', id: 'canvas'});
    const out = r(s, {type: 'reset'});
    expect(out.frames).toEqual(base().frames);
    expect(out.preserved).toEqual({legacyPanel: {id: 'legacyPanel', dock: 'left'}});
  });
  it('M1-10 (focus/z) focus raises z and sets focusId', () => {
    let s = r(base(), {type: 'focus', id: 'outline'}); s = r(s, {type: 'focus', id: 'tasks'});
    expect(s.focusId).toBe('tasks'); expect(s.frames.tasks.z).toBeGreaterThan(s.frames.outline.z);
  });
  it('viewport shrink re-clamps sizes', () => {
    const s = r(base(), {type: 'resize', id: 'inspector', size: 560});
    const small = layoutReducer({specs: SPECS, viewport: {width: 500, height: 400}});
    // [HERMIA-FE-20261023 M1-fix] MF-2: 500px cannot fit main 320 + both columns → shrink to minSize (240), was 300.
    expect(small(s, {type: 'viewport'}).frames.inspector.size).toBe(240);
  });
  it('zoneFromPoint', () => {
    const rect = {left: 0, top: 0, width: 1000, height: 800};
    expect(zoneFromPoint(10, 300, rect)).toBe('left'); expect(zoneFromPoint(990, 300, rect)).toBe('right');
    expect(zoneFromPoint(500, 790, rect)).toBe('bottom'); expect(zoneFromPoint(500, 300, rect)).toBe('main');
  });
});

// [HERMIA-FE-20261023 M1-fix] MF-2: main keeps MAIN_MIN_WIDTH against the SUM of side columns.
import {columnExtent, MAIN_MIN_WIDTH, MAIN_MIN_HEIGHT} from './model';
describe('M1-fix MF-2 main-area minimum', () => {
  const mainW = (s: LayoutState, w: number) => w - columnExtent(s.frames, 'left') - columnExtent(s.frames, 'right');
  it('1366 scenario: max outline + max inspector never leaves main < 320', () => {
    const vp = {width: 1366, height: 768}; const rr = layoutReducer({specs: SPECS, viewport: vp});
    let s = createDefaultLayout(SPECS, vp);
    s = rr(s, {type: 'resize', id: 'outline', size: 99999});
    s = rr(s, {type: 'resize', id: 'inspector', size: 99999});
    expect(mainW(s, 1366)).toBeGreaterThanOrEqual(MAIN_MIN_WIDTH);
    s = rr(s, {type: 'resize', id: 'outline', size: 99999});
    expect(mainW(s, 1366)).toBeGreaterThanOrEqual(MAIN_MIN_WIDTH);
  });
  it('combined widths fit for random resize/dock sequences across viewports', () => {
    for (const w of [1024, 1366, 1440, 1920]) {
      const vp = {width: w, height: 800}; const rr = layoutReducer({specs: SPECS, viewport: vp});
      let s = createDefaultLayout(SPECS, vp);
      const ids = ['outline', 'inspector', 'tasks'];
      for (let i = 0; i < 60; i++) {
        const id = ids[i % 3];
        s = i % 4 === 3 ? rr(s, {type: 'dock', id, dock: (['left', 'right'] as const)[i % 2]}) : rr(s, {type: 'resize', id, size: 100 + (i * 397) % 2000});
        expect(mainW(s, w)).toBeGreaterThanOrEqual(MAIN_MIN_WIDTH);
      }
    }
  });
  it('viewport shrink re-fits side columns; bottom keeps main min height', () => {
    const big = layoutReducer({specs: SPECS, viewport: {width: 1920, height: 1080}});
    let s = createDefaultLayout(SPECS, {width: 1920, height: 1080});
    s = big(s, {type: 'resize', id: 'outline', size: 1000}); s = big(s, {type: 'resize', id: 'inspector', size: 560});
    s = big(s, {type: 'resize', id: 'tasks', size: 5000});
    const small = layoutReducer({specs: SPECS, viewport: {width: 1024, height: 600}});
    s = small(s, {type: 'viewport'});
    expect(mainW(s, 1024)).toBeGreaterThanOrEqual(MAIN_MIN_WIDTH);
    expect(s.frames.tasks.size).toBeLessThanOrEqual(600 - MAIN_MIN_HEIGHT);
  });
});
