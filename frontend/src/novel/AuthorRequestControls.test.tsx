// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthorRequestControls } from './AuthorRequestControls';
import { defaultAuthorRequestScope } from './authorContextClient';

afterEach(cleanup);

it('binds the source select to only its visible label, excluding option descriptions from exact browser label matching', () => {
  const change = vi.fn();
  render(<AuthorRequestControls source="保存的选区🙂" operation="continue" onChange={change} />);
  const select = screen.getByRole('combobox', { name: '正文范围' });
  // Playwright getByLabel reads a native label's full text, including nested
  // options. Testing Library strips that content, so its label query alone
  // did not catch the hosted regression. Assert the explicit naming boundary.
  const labelId = select.getAttribute('aria-labelledby');
  expect(labelId).toBeTruthy();
  const visibleLabel = document.getElementById(labelId!);
  expect(visibleLabel?.textContent).toBe('正文范围');
  expect(visibleLabel?.querySelector('option')).toBeNull();
  expect(select.closest('label')?.contains(visibleLabel!)).toBe(true);
  expect(screen.getByLabelText('正文范围', { exact: true })).toBe(select);
  fireEvent.change(select, { target: { value: 'SELECTION_ONLY' } });
  expect(change).toHaveBeenCalledWith({ ...defaultAuthorRequestScope, source_mode: 'SELECTION_ONLY' });
});

it('uses distinct label bindings when writing and broker scope controls are both mounted', () => {
  render(<>
    <AuthorRequestControls source="正文" operation="continue" onChange={vi.fn()} />
    <AuthorRequestControls source="" operation="brainstorm" onChange={vi.fn()} />
  </>);
  const selects = screen.getAllByRole('combobox', { name: '正文范围' });
  const labelIds = selects.map(select => select.getAttribute('aria-labelledby'));
  expect(new Set(labelIds).size).toBe(2);
  for (const [index, select] of selects.entries()) {
    expect(document.getElementById(labelIds[index]!)?.textContent).toBe('正文范围');
    expect((select.querySelector('option[value="SELECTION_ONLY"]') as HTMLOptionElement).disabled).toBe(index === 1);
  }
});
