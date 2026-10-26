// @vitest-environment jsdom
// [HERMIA-FE-20261023 M1-s2] precise drop index + indicator, real chrome in main-min math, layout actions in DockLayout.
import {act, cleanup, fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {DockLayout} from './DockLayout';
import {
  createDefaultLayout, crossLimit, DOCK_CHROME_PX, dropAxis, dropIndexFromPoint, layoutReducer, mainArea, MAIN_MIN_HEIGHT, MAIN_MIN_WIDTH, panelsIn,
} from './model';
import {MemStorage, SCOPE, SPECS} from './testSpecs';
import {ShortcutTable} from '../actions/layoutActions';

afterEach(cleanup);
if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const rect = (left: number, top: number, width: number, height: number) =>
  ({left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({})});

describe('M1-s2 model: precise drop index', () => {
  it('axis per zone', () => {
    expect(dropAxis('left', 'single')).toBe('y'); expect(dropAxis('right', 'split-h')).toBe('y');
    expect(dropAxis('bottom', 'single')).toBe('x'); expect(dropAxis('main', 'split-h')).toBe('x'); expect(dropAxis('main', 'split-v')).toBe('y');
  });
  it('index by midpoints of other panels', () => {
    const others = [rect(0, 0, 100, 100), rect(0, 100, 100, 100)];
    expect(dropIndexFromPoint('y', {x: 5, y: 10}, others)).toBe(0);
    expect(dropIndexFromPoint('y', {x: 5, y: 60}, others)).toBe(1);
    expect(dropIndexFromPoint('y', {x: 5, y: 199}, others)).toBe(2);
    expect(dropIndexFromPoint('x', {x: 5, y: 0}, [])).toBe(0);
  });
  it('dock with index reorders inside a zone and keeps orders dense', () => {
    const env = {specs: SPECS, viewport: {width: 1440, height: 900}};
    const r = layoutReducer(env);
    let s = createDefaultLayout(SPECS, env.viewport);
    s = r(s, {type: 'dock', id: 'tasks', dock: 'left', index: 0});
    expect(panelsIn(s, 'left').map(f => f.id)).toEqual(['tasks', 'outline']);
    s = r(s, {type: 'dock', id: 'tasks', dock: 'left', index: 1});
    expect(panelsIn(s, 'left').map(f => f.id)).toEqual(['outline', 'tasks']);
    expect(panelsIn(s, 'left').map(f => f.order)).toEqual([0, 1]);
  });
});

describe('M1-s2 model: chrome subtracted (Vera minor)', () => {
  it('both sides maxed at 1366: main keeps >= 320 including handles + borders', () => {
    const vp = {width: 1366, height: 768, reserveTop: 34};
    const r = layoutReducer({specs: SPECS, viewport: vp});
    let s = createDefaultLayout(SPECS, vp);
    s = r(s, {type: 'resize', id: 'outline', size: 5000});
    s = r(s, {type: 'resize', id: 'inspector', size: 5000});
    expect(mainArea(s.frames, vp).width).toBeGreaterThanOrEqual(MAIN_MIN_WIDTH);
    expect(crossLimit(s.frames, 'outline', 'left', vp)).toBe(1366 - MAIN_MIN_WIDTH - s.frames.inspector.size - 2 * DOCK_CHROME_PX);
  });
  it('800x600 bottom maxed: main keeps >= 200 under toolbar + bottom chrome', () => {
    const vp = {width: 800, height: 600, reserveTop: 64};
    const r = layoutReducer({specs: SPECS, viewport: vp});
    let s = createDefaultLayout(SPECS, vp);
    s = r(s, {type: 'viewport'});
    s = r(s, {type: 'resize', id: 'tasks', size: 5000});
    expect(mainArea(s.frames, vp).height).toBeGreaterThanOrEqual(MAIN_MIN_HEIGHT);
    expect(s.frames.tasks.size).toBe(600 - 64 - MAIN_MIN_HEIGHT - DOCK_CHROME_PX);
  });
  it('viewport shrink re-fits with chrome', () => {
    const big = {width: 1920, height: 1080};
    let s = createDefaultLayout(SPECS, big);
    s = layoutReducer({specs: SPECS, viewport: big})(s, {type: 'resize', id: 'inspector', size: 560});
    const small = {width: 1024, height: 700, reserveTop: 34};
    s = layoutReducer({specs: SPECS, viewport: small})(s, {type: 'viewport'});
    expect(mainArea(s.frames, small).width).toBeGreaterThanOrEqual(MAIN_MIN_WIDTH);
  });
});

function setup(table?: ShortcutTable) {
  const storage = new MemStorage();
  render(<DockLayout specs={SPECS} scope={SCOPE} storage={storage} viewport={{width: 1440, height: 900}} shortcutTable={table}
    renderPanel={id => id === 'inspector' ? <textarea aria-label="草稿" /> : <p>{id} 内容</p>} />);
  screen.getByTestId('dock-layout').getBoundingClientRect = () => rect(0, 0, 1000, 800);
  return {storage};
}
const flush = () => act(async () => {});

describe('M1-s2 DockLayout: precise drop with indicator (M1-01)', () => {
  it('drop above the existing right panel inserts before it; below inserts after', async () => {
    setup();
    screen.getByTestId('panel-inspector').getBoundingClientRect = () => rect(800, 40, 200, 400);
    fireEvent.pointerDown(screen.getByTestId('drag-tasks'), {clientX: 500, clientY: 780});
    fireEvent.pointerMove(window, {clientX: 950, clientY: 100});
    const ind = screen.getByTestId('drop-indicator');
    expect(ind.dataset.zone).toBe('right'); expect(ind.dataset.index).toBe('0'); expect(ind.dataset.allowed).toBe('true');
    expect(ind.style.top).toBe('39px'); expect(ind.style.height).toBe('3px');
    fireEvent.pointerUp(window, {clientX: 950, clientY: 100});
    expect(screen.queryByTestId('drop-indicator')).toBeNull();
    const order = () => Array.from(document.querySelectorAll<HTMLElement>('section[data-dock="right"]')).map(e => e.dataset.panelId);
    expect(order()).toEqual(['tasks', 'inspector']);
    // move it again to below inspector
    screen.getByTestId('panel-inspector').getBoundingClientRect = () => rect(800, 240, 200, 400);
    screen.getByTestId('panel-tasks').getBoundingClientRect = () => rect(800, 40, 200, 200);
    fireEvent.pointerDown(screen.getByTestId('drag-tasks'), {clientX: 900, clientY: 50});
    fireEvent.pointerMove(window, {clientX: 950, clientY: 600});
    expect(screen.getByTestId('drop-indicator').dataset.index).toBe('1');
    fireEvent.pointerUp(window, {clientX: 950, clientY: 600});
    expect(order()).toEqual(['inspector', 'tasks']);
  });
  it('disallowed zone shows a blocked indicator + note and does not move the panel', () => {
    setup();
    fireEvent.pointerDown(screen.getByTestId('drag-canvas'), {clientX: 500, clientY: 300});
    fireEvent.pointerMove(window, {clientX: 20, clientY: 300});
    expect(screen.getByTestId('drop-indicator').dataset.allowed).toBe('false');
    expect(screen.getByText('这个面板不能放到左侧')).toBeTruthy();
    fireEvent.pointerUp(window, {clientX: 20, clientY: 300});
    expect(screen.getByTestId('panel-canvas').dataset.dock).toBe('main');
  });
});

describe('M1-s2 DockLayout: toolbar + shortcuts through ActionRegistry', () => {
  it('toolbar controls carry stable action ids', () => {
    setup();
    for (const id of ['layout.reset', 'layout.reopenPanel', 'layout.switchSplit', 'layout.toggleCollapse'])
      expect(document.querySelector(`[data-action-id="${id}"]`)).not.toBeNull();
  });
  it('reopen shows the disabled reason when nothing is closed', async () => {
    setup(); await flush();
    const sel = screen.getByLabelText('重新打开面板') as HTMLSelectElement;
    expect(sel.disabled).toBe(true); expect(sel.title).toBe('没有已关闭的面板');
  });
  it('Ctrl+Alt+S switches split; Ctrl+Alt+C toggles focused panel; Ctrl+Alt+0 opens reset confirm', async () => {
    setup(); await flush();
    fireEvent.keyDown(window, {key: 's', code: 'KeyS', ctrlKey: true, altKey: true});
    expect(screen.getByTestId('main-zone').dataset.split).toBe('split-h');
    await flush();
    fireEvent.focus(screen.getByTestId('panel-tasks'));
    fireEvent.keyDown(window, {key: 'c', code: 'KeyC', ctrlKey: true, altKey: true});
    expect(screen.getByTestId('panel-tasks').dataset.collapsed).toBe('true');
    await flush();
    fireEvent.keyDown(window, {key: '0', code: 'Digit0', ctrlKey: true, altKey: true});
    expect(within(screen.getByRole('dialog')).getByText(/只恢复面板位置/)).toBeTruthy();
  });
  it('shortcuts are ignored while typing in a text input', async () => {
    setup(); await flush();
    const ta = screen.getByLabelText('草稿');
    fireEvent.keyDown(ta, {key: 's', code: 'KeyS', ctrlKey: true, altKey: true});
    expect(screen.getByTestId('main-zone').dataset.split).toBe('single');
  });
  it('a shortcut conflict is reported in Chinese and the action keeps working without a key', async () => {
    const table = new ShortcutTable({'Mod+K': 'command-search', 'Mod+Alt+S': '其他功能'});
    setup(table); await flush();
    expect(screen.getByRole('status').textContent).toContain('快捷键 Ctrl+Alt+S 已被占用');
    fireEvent.keyDown(window, {key: 's', code: 'KeyS', ctrlKey: true, altKey: true});
    expect(screen.getByTestId('main-zone').dataset.split).toBe('single');
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'split-v'}});
    expect(screen.getByTestId('main-zone').dataset.split).toBe('split-v');
  });
});
