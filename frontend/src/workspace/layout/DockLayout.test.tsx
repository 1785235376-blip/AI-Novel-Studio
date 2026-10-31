// @vitest-environment jsdom
// [HERMIA-FE-20261023 M1] Component-level interaction tests (RTL + jsdom). Real pointer/keyboard events,
// no browser layout engine: geometry is a mocked bounding rect. Real-browser checks are tracked separately.
import {act, cleanup, fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {useEffect, useState} from 'react';
import {DockLayout, type PanelRenderApi} from './DockLayout';
import {workspaceLayoutBackupKey, workspaceLayoutKey} from './persistence';
import {MemStorage, SCOPE, SPECS, VP} from './testSpecs';

afterEach(cleanup);
// jsdom has no PointerEvent; without this clientX/clientY are dropped. Test-env polyfill only.
if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}

function Editor({api, save}: {api: PanelRenderApi; save: () => Promise<void>}) {
  const [text, setText] = useState(''); const [saved, setSaved] = useState('');
  useEffect(() => api.registerDirty({isDirty: () => text !== saved, save: async () => { await save(); setSaved(text); }, discard: () => setText(saved)}), [api, text, saved, save]);
  return <textarea aria-label="草稿" value={text} onChange={e => setText(e.target.value)} />;
}

function setup(opts: {storage?: MemStorage; save?: () => Promise<void>} = {}) {
  const storage = opts.storage ?? new MemStorage();
  const save = opts.save ?? (async () => {});
  const utils = render(<DockLayout specs={SPECS} scope={SCOPE} storage={storage} viewport={VP}
    renderPanel={(id, api) => id === 'inspector' ? <Editor api={api} save={save} /> : <p>{id} 内容</p>} />);
  const root = screen.getByTestId('dock-layout');
  root.getBoundingClientRect = () => ({left: 0, top: 0, width: 1000, height: 800, right: 1000, bottom: 800, x: 0, y: 0, toJSON: () => ({})});
  return {...utils, storage};
}
const saved = (st: MemStorage) => JSON.parse(st.getItem(workspaceLayoutKey(SCOPE))!);
const frame = (st: MemStorage, id: string) => saved(st).panels.find((p: {id: string}) => p.id === id);

describe('DockLayout interactions', () => {
  it('M1-03 pointer-drag a panel header onto the right edge docks it there', () => {
    const {storage} = setup();
    const head = screen.getByTestId('drag-tasks');
    fireEvent.pointerDown(head, {clientX: 500, clientY: 780});
    fireEvent.pointerMove(window, {clientX: 950, clientY: 300});
    expect(screen.getByTestId('drop-hint').dataset.zone).toBe('right');
    fireEvent.pointerUp(window, {clientX: 950, clientY: 300});
    expect(screen.getByTestId('panel-tasks').dataset.dock).toBe('right');
    expect(frame(storage, 'tasks').dock).toBe('right');
  });
  it('M1-04 redock via the dock selector (keyboard-accessible path)', () => {
    setup();
    fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: 'bottom'}});
    expect(screen.getByTestId('panel-inspector').dataset.dock).toBe('bottom');
  });
  it('M1-01 floating panel moves with pointer drag and stays in viewport', () => {
    setup();
    fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: 'float'}});
    const p = screen.getByTestId('panel-inspector');
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 100, clientY: 100});
    fireEvent.pointerMove(window, {clientX: 300, clientY: 250});
    fireEvent.pointerUp(window, {clientX: 300, clientY: 250});
    expect(p.style.left).toBe('280px'); expect(p.style.top).toBe('230px');
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 0, clientY: 0});
    fireEvent.pointerMove(window, {clientX: 99999, clientY: 99999});
    expect(p.style.left).toBe(`${VP.width - 48}px`); expect(p.style.top).toBe(`${VP.height - 48}px`);
    fireEvent.pointerUp(window, {clientX: 99999, clientY: 99999});
  });
  it('M1-02 resize handle via pointer and keyboard respects min size', () => {
    setup();
    const h = screen.getByTestId('resize-inspector');
    fireEvent.pointerDown(h, {clientX: 1000}); fireEvent.pointerMove(window, {clientX: 900}); fireEvent.pointerUp(window, {});
    expect(screen.getByTestId('panel-inspector').style.width).toBe('440px');
    fireEvent.pointerDown(h, {clientX: 1000}); fireEvent.pointerMove(window, {clientX: 1900}); fireEvent.pointerUp(window, {});
    expect(screen.getByTestId('panel-inspector').style.width).toBe('240px');
    fireEvent.keyDown(screen.getByTestId('resize-inspector'), {key: 'ArrowLeft'});
    expect(screen.getByTestId('panel-inspector').style.width).toBe('256px');
  });
  it('M1-05 collapse/expand keeps panel content state', () => {
    setup();
    const ta = screen.getByLabelText('草稿') as HTMLTextAreaElement;
    fireEvent.change(ta, {target: {value: '未保存的一句'}});
    const panel = screen.getByTestId('panel-inspector');
    fireEvent.click(within(panel).getByRole('button', {name: '折叠'}));
    expect(panel.dataset.collapsed).toBe('true');
    fireEvent.click(within(panel).getByRole('button', {name: '展开'}));
    expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('未保存的一句');
  });
  // [HERMIA-FE-20261023 M1-s2] toolbar goes through ActionRegistry; its pending key clears on the next microtask,
  // so rapid separate user events are flushed (as a browser event loop would) instead of counting as a double trigger.
  it('M1-06/M1-19 close clean panel without prompt, reopen from menu, no duplicates', async () => {
    setup();
    for (let i = 0; i < 5; i++) {
      // [HERMIA-FE-20261023 M1-s2fix] reopen stays pending MIN_BUSY_MS (double-trigger guard); next iteration waits it out.
      await act(async () => { await new Promise(r => setTimeout(r, i ? 320 : 0)); });
      fireEvent.click(screen.getByRole('button', {name: '关闭「任务」'}));
      expect(screen.queryByTestId('panel-tasks')).toBeNull();
      expect(screen.queryByRole('dialog')).toBeNull();
      fireEvent.change(screen.getByLabelText('重新打开面板'), {target: {value: 'tasks'}});
      expect(screen.getAllByTestId('panel-tasks')).toHaveLength(1);
    }
  });
  it('M1-07 split switch shows two main panels', () => {
    setup();
    expect(within(screen.getByTestId('main-zone')).queryAllByRole('region')).toHaveLength(1);
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'split-h'}});
    expect(within(screen.getByTestId('main-zone')).getAllByRole('region').map(r => r.getAttribute('aria-label'))).toEqual(['创作画布', '执行画布']);
  });
  it('M1-08 reset default asks first, then restores layout but keeps draft text', async () => {
    setup();
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'keep me'}});
    fireEvent.change(screen.getByLabelText('「任务」停靠位置'), {target: {value: 'left'}});
    fireEvent.click(screen.getByRole('button', {name: '恢复默认布局'}));
    fireEvent.click(screen.getByRole('button', {name: '取消'}));
    expect(screen.getByTestId('panel-tasks').dataset.dock).toBe('left');
    await act(async () => { await new Promise(r => setTimeout(r, 320)); }); // [HERMIA-FE-20261023 M1-s2fix] past MIN_BUSY_MS
    fireEvent.click(screen.getByRole('button', {name: '恢复默认布局'}));
    fireEvent.click(screen.getByRole('button', {name: '恢复默认'}));
    expect(screen.getByTestId('panel-tasks').dataset.dock).toBe('bottom');
    expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('keep me');
  });
  it('M1-09 layout survives unmount/remount (reload)', () => {
    const storage = new MemStorage();
    const a = setup({storage});
    fireEvent.change(screen.getByLabelText('「任务」停靠位置'), {target: {value: 'right'}});
    fireEvent.click(screen.getByRole('button', {name: '关闭「大纲」'}));
    a.unmount();
    setup({storage});
    expect(screen.getByTestId('panel-tasks').dataset.dock).toBe('right');
    expect(screen.queryByTestId('panel-outline')).toBeNull();
  });
  it('M1-10 persist failure: session keeps working and status says so', () => {
    const storage = new MemStorage(); setup({storage}); storage.failSet = true;
    fireEvent.change(screen.getByLabelText('「任务」停靠位置'), {target: {value: 'right'}});
    expect(screen.getByTestId('panel-tasks').dataset.dock).toBe('right');
    expect(screen.getByRole('status').textContent).toMatch(/布局保存失败，仅本次会话有效/);
  });
  it('M1-10 focus raises z-order between floating panels', () => {
    setup();
    fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: 'float'}});
    fireEvent.change(screen.getByLabelText('「大纲」停靠位置'), {target: {value: 'float'}});
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 1, clientY: 1}); fireEvent.pointerUp(window, {clientX: 1, clientY: 1});
    const zi = Number(screen.getByTestId('panel-inspector').style.zIndex), zo = Number(screen.getByTestId('panel-outline').style.zIndex);
    expect(zi).toBeGreaterThan(zo); expect(screen.getByTestId('panel-inspector').dataset.focused).toBe('true');
  });
  it('M1-14 corrupt stored layout: default shown, warning, original + backup kept until user acts', () => {
    const storage = new MemStorage(); storage.setItem(workspaceLayoutKey(SCOPE), 'not json{');
    setup({storage});
    expect(screen.getByTestId('dock-layout').dataset.source).toBe('fallback-corrupt');
    expect(screen.getByRole('status').textContent).toMatch(/原数据已备份/);
    expect(storage.getItem(workspaceLayoutKey(SCOPE))).toBe('not json{');
    expect(storage.getItem(workspaceLayoutBackupKey(SCOPE))).toBe('not json{');
  });
  it('M1-20/M1-21 dirty close prompts; cancel keeps panel and draft', () => {
    setup();
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'abc'}});
    fireEvent.click(screen.getByRole('button', {name: '关闭「属性」'}));
    const dlg = screen.getByRole('dialog', {name: '关闭「属性」'});
    expect(within(dlg).getByRole('button', {name: '保存并关闭'})).toBeTruthy();
    fireEvent.click(within(dlg).getByRole('button', {name: '取消'}));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('abc');
  });
  it('M1-22 discard drops only this panel edits then closes', () => {
    setup();
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'abc'}});
    fireEvent.click(screen.getByRole('button', {name: '关闭「属性」'}));
    fireEvent.click(screen.getByRole('button', {name: '放弃修改'}));
    expect(screen.queryByTestId('panel-inspector')).toBeNull();
    expect(screen.getByText('tasks 内容')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('重新打开面板'), {target: {value: 'inspector'}});
    expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('');
  });
  it('M1-25 save failure keeps panel open, shows real error, never says saved', async () => {
    const save = vi.fn(async () => { throw new Error('网络断开'); });
    setup({save});
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'abc'}});
    fireEvent.click(screen.getByRole('button', {name: '关闭「属性」'}));
    await act(async () => { fireEvent.click(screen.getByRole('button', {name: '保存并关闭'})); });
    expect(save).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('alert').textContent).toMatch(/保存失败：网络断开/);
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();
    expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('abc');
  });
  it('M1-20 save success closes after the real save resolves', async () => {
    let resolve!: () => void; const save = vi.fn(() => new Promise<void>(r => { resolve = r; }));
    setup({save});
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'abc'}});
    fireEvent.click(screen.getByRole('button', {name: '关闭「属性」'}));
    fireEvent.click(screen.getByRole('button', {name: '保存并关闭'}));
    expect(screen.getByRole('button', {name: '保存中…'})).toHaveProperty('disabled', true);
    fireEvent.click(screen.getByRole('button', {name: '保存中…'}));
    expect(save).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();
    await act(async () => { resolve(); });
    expect(screen.queryByTestId('panel-inspector')).toBeNull();
  });
  it('M1-24 late save resolution after unmount does not touch state / warn', async () => {
    let resolve!: () => void; const save = vi.fn(() => new Promise<void>(r => { resolve = r; }));
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const {unmount, storage} = setup({save});
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'abc'}});
    fireEvent.click(screen.getByRole('button', {name: '关闭「属性」'}));
    fireEvent.click(screen.getByRole('button', {name: '保存并关闭'}));
    const before = storage.getItem(workspaceLayoutKey(SCOPE));
    unmount();
    await act(async () => { resolve(); });
    expect(storage.getItem(workspaceLayoutKey(SCOPE))).toBe(before);
    expect(err).not.toHaveBeenCalled(); err.mockRestore();
  });
  it('M1-24 late save after user cancelled is ignored (panel stays open)', async () => {
    let resolve!: () => void; const save = vi.fn(() => new Promise<void>(r => { resolve = r; }));
    setup({save});
    fireEvent.change(screen.getByLabelText('草稿'), {target: {value: 'abc'}});
    fireEvent.click(screen.getByRole('button', {name: '关闭「属性」'}));
    fireEvent.click(screen.getByRole('button', {name: '保存并关闭'}));
    fireEvent.click(screen.getByRole('button', {name: '取消'}));
    await act(async () => { resolve(); });
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();
  });
  it('M1-23 listeners cleaned on unmount (no window listener leak across remounts)', () => {
    const add = vi.spyOn(window, 'addEventListener'); const rem = vi.spyOn(window, 'removeEventListener');
    for (let i = 0; i < 3; i++) setup().unmount();
    const count = (spy: typeof add, t: string) => spy.mock.calls.filter(c => c[0] === t).length;
    expect(count(rem, 'pointermove')).toBe(count(add, 'pointermove'));
    expect(count(rem, 'pointerup')).toBe(count(add, 'pointerup'));
    add.mockRestore(); rem.mockRestore();
  });
});

// [HERMIA-FE-20261023 M1-fix] Regression tests for Vera's MF-1 / N2 / N3.
describe('M1-fix: panel content survives layout changes (MF-1)', () => {
  const type = (v: string) => fireEvent.change(screen.getByLabelText('草稿'), {target: {value: v}});
  it('redock to bottom / float / left keeps unsaved input (no remount)', () => {
    setup(); type('abc');
    for (const d of ['bottom', 'float', 'left', 'right']) {
      fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: d}});
      expect(screen.getByTestId('panel-inspector').dataset.dock).toBe(d);
      expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('abc');
    }
  });
  it('pointer-drag redock keeps unsaved input', () => {
    setup(); type('xyz');
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 900, clientY: 300});
    fireEvent.pointerMove(window, {clientX: 500, clientY: 790});
    fireEvent.pointerUp(window, {clientX: 500, clientY: 790});
    expect(screen.getByTestId('panel-inspector').dataset.dock).toBe('bottom');
    expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('xyz');
  });
  it('single-column main switch keeps the hidden panel state', () => {
    const storage = new MemStorage();
    render(<DockLayout specs={SPECS} scope={SCOPE} storage={storage} viewport={VP}
      renderPanel={(id, api) => id === 'canvas' ? <Editor api={api} save={async () => {}} /> : <p>{id} 内容</p>} />);
    type('main draft');
    fireEvent.change(screen.getByLabelText('切换中间面板'), {target: {value: 'exec'}});
    expect(screen.queryByLabelText('草稿')).toBeNull(); // hidden, not visible
    fireEvent.change(screen.getByLabelText('切换中间面板'), {target: {value: 'canvas'}});
    expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('main draft');
  });
  it('explicit close still goes through the dirty guard', () => {
    setup(); type('abc');
    fireEvent.click(screen.getByLabelText('关闭「属性」'));
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});

describe('M1-fix: N2 persistence writes only on real layout change', () => {
  it('after corrupt load, focus / header click does not overwrite the original key', () => {
    const storage = new MemStorage(); storage.setItem(workspaceLayoutKey(SCOPE), '{bad json');
    setup({storage});
    fireEvent.pointerDown(screen.getByTestId('drag-outline'), {clientX: 10, clientY: 10});
    fireEvent.pointerUp(window, {clientX: 10, clientY: 10});
    fireEvent.focus(screen.getByTestId('panel-outline'));
    expect(storage.getItem(workspaceLayoutKey(SCOPE))).toBe('{bad json');
    expect(storage.getItem(workspaceLayoutBackupKey(SCOPE))).toBe('{bad json');
    fireEvent.click(screen.getAllByText('折叠')[0]);
    expect(saved(storage).version).toBe(3);
    expect(storage.getItem(workspaceLayoutBackupKey(SCOPE))).toBe('{bad json');
  });
});

describe('M1-fix: N3 modal dialog keyboard', () => {
  it('Esc cancels, Tab is trapped, focus returns to the trigger', () => {
    setup();
    // [HERMIA-FE-20261023 M1-s2fix] reset is disabled on the default layout (MUST-FIX 3); make it non-default first.
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'split-h'}});
    const trigger = screen.getByText('恢复默认布局');
    trigger.focus(); fireEvent.click(trigger);
    const dlg = screen.getByRole('dialog');
    const btns = within(dlg).getAllByRole('button');
    expect(document.activeElement).toBe(btns[0]);
    btns[btns.length - 1].focus();
    fireEvent.keyDown(btns[btns.length - 1], {key: 'Tab'});
    expect(document.activeElement).toBe(btns[0]);
    fireEvent.keyDown(btns[0], {key: 'Tab', shiftKey: true});
    expect(document.activeElement).toBe(btns[btns.length - 1]);
    fireEvent.keyDown(dlg, {key: 'Escape'});
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
