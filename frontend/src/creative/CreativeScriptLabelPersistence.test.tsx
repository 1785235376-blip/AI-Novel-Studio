// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { newDocument } from './types';

afterEach(cleanup);
it('keeps the saved Script editor label independent of its initial textarea text node', () => {
  const body = '  Intro\n\nA saved paragraph.\n';
  const draft = { ...newDocument('SCRIPT'), script: { purpose: 'PODCAST' as const, body } };
  render(<CreativeCanvas draft={draft} dirty={false} canEdit={true} busy={false}
    onScene={vi.fn()} onShot={vi.fn()} onChange={vi.fn()} onSave={vi.fn()} onNew={vi.fn()} />);
  const editor = screen.getByRole('textbox', { name: '通用脚本内容' }) as HTMLTextAreaElement;
  expect(editor.value).toBe(body);
  // React initializes the textarea text node from a restored nonempty value.
  // An explicit accessible label cannot absorb that model-independent content.
  expect(editor.textContent).toBe(body);
  expect(editor.getAttribute('aria-label')).toBe('通用脚本内容');
});
