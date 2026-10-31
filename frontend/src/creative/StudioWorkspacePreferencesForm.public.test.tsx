// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StudioWorkspacePreferencesForm } from './StudioWorkspacePreferencesForm';
import type { StudioWorkspacePreferencesController } from './useStudioWorkspacePreferences';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('keeps the public-edition placeholder disabled without dispatch or preference mutation', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  const save = vi.fn(), change = vi.fn();
  const controller = {
    draft: { intents: [], preset: 'BLANK', custom_intent: '' },
    base: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
    editable: true, dirty: false, save, change, canCheck: false,
  } as unknown as StudioWorkspacePreferencesController;
  const view = render(<StudioWorkspacePreferencesForm controller={controller} />);
  fireEvent.click(screen.getByText('创作意图与推荐布局'));
  const button = screen.getByRole('button', { name: 'NSFW 模式（本版本不可用）' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(button.type).toBe('button');
  expect(button.title).toBe('公开版本不提供此功能');
  fireEvent.click(button); fireEvent.click(button);
  fireEvent.keyDown(button, { key: 'Enter' }); fireEvent.keyDown(button, { key: ' ' });
  expect(fetch).not.toHaveBeenCalled(); expect(save).not.toHaveBeenCalled(); expect(change).not.toHaveBeenCalled();
  view.rerender(<StudioWorkspacePreferencesForm controller={{ ...controller, editable: false }} locked />);
  expect((screen.getByRole('button', { name: 'NSFW 模式（本版本不可用）' }) as HTMLButtonElement).disabled).toBe(true);
});
