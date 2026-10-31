// @vitest-environment jsdom
// [HERMIA-FE-20261024 M4-s1fix] CommandSearch must not steal focus on mount; focus returns to the trigger after close.
import {afterEach, describe, expect, it} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {useWorkbench} from './useWorkbench';
import {CommandSearch} from './CommandSearch';
afterEach(cleanup);

function H() {
  const wb = useWorkbench(() => {}, {projectId: 'p1'});
  return <><a href="#m" data-testid="skip">跳到主区域</a><CommandSearch workbench={wb} onLegacy={() => {}}/></>;
}
const trigger = () => screen.getByRole('button', {name: /搜索功能/});

describe('CommandSearch focus (M4-s1fix)', () => {
  it('mount does not focus the trigger; first focusable is still the skip link', () => {
    render(<H/>);
    expect(document.activeElement).not.toBe(trigger());
    expect(document.activeElement).toBe(document.body);
    const first = document.querySelector<HTMLElement>('a,button,input,select,[tabindex="0"]');
    expect(first).toBe(screen.getByTestId('skip'));
  });
  it('Esc closes the palette and returns focus to the trigger', () => {
    render(<H/>);
    fireEvent.click(trigger());
    const input = screen.getByRole('textbox', {name: '搜索功能'});
    expect(document.activeElement).toBe(input);
    fireEvent.keyDown(input, {key: 'Escape'});
    expect(screen.queryByTestId('command-search-overlay')).toBeNull();
    expect(document.activeElement).toBe(trigger());
  });
});
