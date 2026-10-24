// @vitest-environment jsdom
// [HERMIA-FE-20261024 VW-fix1] views dialog focus management (jsdom; Tab movement itself is simulated by the trap handler).
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {useState} from 'react';
import {ActionRegistry} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';
import {ShortcutTable} from '../actions/layoutActions';
import {registerViewActions} from '../actions/viewActions';
import {createViewPreferences, type ViewPrefs} from '../state/viewPreferences';
import {captureWorkset} from '../layout/worksets';
import {createDefaultLayout} from '../layout/model';
import {SPECS, VP} from '../layout/testSpecs';
import {WorkspaceViewsPanel} from './WorkspaceViewsPanel';

afterEach(cleanup);
function Harness({prefs, reg, ctx}: {prefs: ViewPrefs; reg: ActionRegistry; ctx: (i?: unknown) => never}) {
  const [open, setOpen] = useState(false);
  return <><button onClick={() => setOpen(true)}>视图</button>{open && <WorkspaceViewsPanel prefs={prefs} actions={reg} ctx={ctx} onClose={() => setOpen(false)} />}</>;
}
function setup() {
  const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker);
  const prefs = createViewPreferences({scope: null, storage: null, isCurrent: () => true, persist: false});
  const r = captureWorkset(createDefaultLayout(SPECS, VP), '写作', []); if (!r.ok) throw 0; prefs.setWorksets(r.value);
  registerViewActions(reg, new ShortcutTable(), {layout: () => null, prefs: () => prefs, focus: () => null, openViews: () => {}, onChange: () => {}});
  const ctx = (input?: unknown) => ({token: tracker.current(), targetId: null, targetVersion: null, permissions: new Set<string>(), input}) as never;
  render(<Harness prefs={prefs} reg={reg} ctx={ctx} />);
  const trigger = screen.getByRole('button', {name: '视图'}); trigger.focus(); fireEvent.click(trigger);
  const dlg = screen.getByTestId('uw-views');
  const items = () => [...dlg.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled])')];
  return {trigger, dlg, items, prefs};
}
const tab = (shift = false) => fireEvent.keyDown(document.activeElement!, {key: 'Tab', shiftKey: shift});

describe('[VW-fix1] views dialog focus', () => {
  it('Tab on the last control wraps to the first; focus stays inside', () => {
    const {dlg, items} = setup();
    expect(document.activeElement).toBe(items()[0]);
    items().at(-1)!.focus(); tab();
    expect(document.activeElement).toBe(items()[0]); expect(dlg.contains(document.activeElement)).toBe(true);
  });
  it('Shift+Tab on the first control wraps to the last', () => {
    const {items} = setup();
    tab(true); expect(document.activeElement).toBe(items().at(-1));
  });
  it('after rename submit focus returns to that row\'s rename button; Esc then closes and focus returns to trigger', async () => {
    const {trigger} = setup();
    fireEvent.click(screen.getByRole('button', {name: '重命名视图「写作」'}));
    const input = screen.getByLabelText('新名称'); expect(document.activeElement).toBe(input);
    fireEvent.change(input, {target: {value: '审稿'}});
    fireEvent.submit(input.closest('form')!);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', {name: '重命名视图「审稿」'})));
    fireEvent.keyDown(document.activeElement!, {key: 'Escape'});
    expect(screen.queryByTestId('uw-views')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
  it('Esc with focus outside the card (body) still closes and returns focus to the trigger', () => {
    const {trigger} = setup();
    act(() => { (document.activeElement as HTMLElement).blur(); });
    expect(document.activeElement).toBe(document.body);
    fireEvent.keyDown(document.body, {key: 'Escape'});
    expect(screen.queryByTestId('uw-views')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
  it('close button returns focus to the trigger; delete confirm focuses cancel, not the destructive button', () => {
    const {trigger} = setup();
    fireEvent.click(screen.getByRole('button', {name: '删除视图「写作」'}));
    expect(document.activeElement?.textContent).toBe('取消');
    fireEvent.click(screen.getByRole('button', {name: '关闭'}));
    expect(document.activeElement).toBe(trigger);
  });
});
