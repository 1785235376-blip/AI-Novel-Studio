import { normalizeRevisionLockDocument } from './experimental/revisionLocks';
// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ChapterEditor, editorAnchorText } from './Editor';
const observed = vi.hoisted(() => ({ editor: undefined as any }));
vi.mock('@tiptap/react', async importOriginal => {
  const real = await importOriginal<typeof import('@tiptap/react')>();
  return { ...real, useEditor: (...args: any[]) => { observed.editor = (real.useEditor as any)(...args); return observed.editor; } };
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const document = { type: 'doc', content: [
  { type: 'heading', attrs: { level: 1 }, content: [{ type: 'text', text: '标题' }] },
  { type: 'paragraph', content: [{ type: 'text', text: '甲' }, { type: 'hardBreak' }, { type: 'text', text: '乙😀丙 e\u0301' }] },
  { type: 'blockquote', content: [{ type: 'paragraph', content: [{ type: 'text', text: '引用终点' }] }] },
] };
it('uses the same hardBreak and Unicode codepoint coordinates for capture and restoration', async () => {
  const change = vi.fn(), capture = vi.fn();
  const view = render(<ChapterEditor content="" document={document} onChange={change} onAnchorChange={capture} />);
  await screen.findByRole('textbox');
  const editor = observed.editor;
  const full = editorAnchorText(editor.state.doc, 0, editor.state.doc.content.size);
  expect(full).toBe('标题\n甲\n乙😀丙 e\u0301\n引用终点');
  const offset = Array.from('标题\n甲\n乙😀').length;
  view.rerender(<ChapterEditor content="" document={document} onChange={change} onAnchorChange={capture} restoreAnchor={{ requestId: 1, offset, scroll: 0 }} />);
  await waitFor(() => expect(Array.from(editorAnchorText(editor.state.doc, 0, editor.state.selection.from)).length).toBe(offset));
  expect(editorAnchorText(editor.state.doc, 0, editor.state.selection.from)).toBe('标题\n甲\n乙😀');
  expect(change).not.toHaveBeenCalled();
  act(() => { editor.commands.setTextSelection(2); });
  expect(capture.mock.calls.at(-1)?.[0].offset).toBe(1);
  const selected = editor.state.selection.from;
  view.rerender(<ChapterEditor content="" document={document} onChange={change} onAnchorChange={capture} restoreAnchor={{ requestId: 1, offset, scroll: 0 }} />);
  expect(editor.state.selection.from).toBe(selected);
});
it('changes reading preferences and paragraph emphasis without replacing the editor or undo state', async () => {
  const change = vi.fn();
  const view = render(<ChapterEditor content="" document={document} onChange={change} />);
  await screen.findByRole('textbox');
  const editor = observed.editor, originalView = editor.view;
  act(() => editor.commands.setTextSelection(2));
  const originalSelection = editor.state.selection.from;
  view.rerender(<ChapterEditor content="" document={document} onChange={change} writingPreferences={{ column_width: 'narrow', font_size: 20, line_height: 2, paragraph_focus: true }} />);
  expect(editor.view).toBe(originalView); expect(editor.state.selection.from).toBe(originalSelection);
  expect(editor.view.dom.parentElement?.style.getPropertyValue('--writing-font-size')).toBe('20px');
  expect(editor.view.dom.querySelector('[data-writing-active="true"]')).toBeTruthy();
  expect(normalizeRevisionLockDocument(editor.getJSON())).toEqual(document); expect(change).not.toHaveBeenCalled();
  view.rerender(<ChapterEditor content="" document={document} onChange={change} />);
  expect(editor.view).toBe(originalView); expect(editor.view.dom.querySelector('[data-writing-active]')).toBeNull();
});

it('exposes exact current selection as plain Unicode codepoint offsets without changing editor positions', async () => {
  const selection = vi.fn(); render(<ChapterEditor content="" document={document} onChange={vi.fn()} onSelection={selection} />);
  await screen.findByRole('textbox');
  const editor = observed.editor;
  const fromText = '标题\n甲\n乙', selectedText = '😀丙';
  let from = 0, to = 0;
  for (let pos = 0; pos <= editor.state.doc.content.size; pos++) {
    const value = editorAnchorText(editor.state.doc, 0, pos);
    if (!from && value === fromText) from = pos;
    if (!to && value === fromText + selectedText) to = pos;
  }
  act(() => { editor.commands.setTextSelection({ from, to }); });
  expect(selection.mock.calls.at(-1)?.[0]).toEqual({ from, to, text: selectedText, text_start: Array.from(fromText).length, text_end: Array.from(fromText + selectedText).length });
  expect(editor.state.selection.from).toBe(from); expect(editor.state.selection.to).toBe(to);
});
