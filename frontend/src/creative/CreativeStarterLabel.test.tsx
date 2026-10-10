// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { newDocument, newScene } from './types';
afterEach(cleanup);
it('keeps a nonempty starter action label independent of the initial textarea text node', () => {
  const action = '【写作提示】请替换为自己的场景动作。';
  render(<CreativeCanvas draft={{ ...newDocument('SCREENPLAY'), source_independent: true, scenes: [{ ...newScene(1), action }] }} dirty canEdit busy={false} onScene={vi.fn()} onShot={vi.fn()} onChange={vi.fn()} onSave={vi.fn()} onNew={vi.fn()} />);
  const editor = screen.getByRole('textbox', { name: '动作与叙事' }) as HTMLTextAreaElement;
  expect(editor.value).toBe(action); expect(editor.textContent).toBe(action);
  expect(editor.getAttribute('aria-label')).toBe('动作与叙事');
});
