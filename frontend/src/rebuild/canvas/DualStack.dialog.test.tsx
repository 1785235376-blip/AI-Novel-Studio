// @vitest-environment jsdom
// [HERMIA-FE-20261030 B1] Vera P2：「接入上画布」确认条 → 真正的对话框：焦点进入、Tab 圈住、Esc 取消、关闭后焦点还给触发按钮。
import {describe, it, expect, beforeEach, afterEach} from 'vitest';
import {render, cleanup, fireEvent, within, screen} from '@testing-library/react';
import {DualStack} from './DualStack';
import {canvasStorageKey, sessionCanvasStore} from './RebuildCanvas';
import {useStudio} from '../../store';

const layer = (l: 'upper' | 'lower') => document.querySelector(`[data-canvas-layer=${l}]`) as HTMLElement;
const setup = () => {
  render(<DualStack kind="image" scope="n1" />);
  fireEvent.contextMenu(within(layer('lower')).getByRole('application'), {clientX: 40, clientY: 40});
  fireEvent.click(layer('lower').querySelector('[data-add-node-menu] [data-node-type=image_style]')!);
  const trigger = layer('lower').querySelector('[data-feed-upper]') as HTMLButtonElement;
  trigger.focus(); fireEvent.click(trigger);
  return trigger;
};
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => cleanup());

describe('DualStack feed confirm is a modal dialog', () => {
  it('opens as role=dialog aria-modal with focus on the confirm button', () => {
    setup();
    const dlg = screen.getByRole('dialog', {name: '接入上画布？'});
    expect(dlg.getAttribute('aria-modal')).toBe('true');
    expect(document.activeElement).toBe(dlg.querySelector('[data-feed-confirm]'));
  });
  it('Esc cancels without writing and returns focus to the trigger', () => {
    const trigger = setup();
    const before = localStorage.getItem(canvasStorageKey('image', 'n1'));
    fireEvent.keyDown(document.activeElement!, {key: 'Escape'});
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(localStorage.getItem(canvasStorageKey('image', 'n1'))).toBe(before);
    expect(document.activeElement).toBe(layer('lower').querySelector('[data-feed-upper]'));
    expect(trigger.isConnected).toBe(true);
  });
  it('Tab and Shift+Tab stay inside the dialog', () => {
    setup();
    const dlg = screen.getByRole('dialog');
    const [cancel, ok] = [dlg.querySelector('[data-cfd-cancel]') as HTMLElement, dlg.querySelector('[data-feed-confirm]') as HTMLElement];
    ok.focus(); fireEvent.keyDown(ok, {key: 'Tab'}); expect(document.activeElement).toBe(cancel);
    fireEvent.keyDown(cancel, {key: 'Tab', shiftKey: true}); expect(document.activeElement).toBe(ok);
  });
  it('confirm copies once, closes and returns focus to the trigger', () => {
    setup();
    fireEvent.click(screen.getByRole('dialog').querySelector('[data-feed-confirm]')!);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(JSON.parse(localStorage.getItem(canvasStorageKey('image', 'n1'))!).nodes).toHaveLength(1);
    expect(document.activeElement).toBe(layer('lower').querySelector('[data-feed-upper]'));
  });
});
