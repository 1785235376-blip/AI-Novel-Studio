// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ChapterEditor, currentEditorSelection, editorAnchorText } from './Editor';
import { normalizeRevisionLockDocument } from './experimental/revisionLocks';
import fixture from '../../tests/fixtures/a43_rich_document_coordinates.json';

const observed = vi.hoisted(() => ({ editor: undefined as any }));
vi.mock('@tiptap/react', async importOriginal => {
  const real = await importOriginal<typeof import('@tiptap/react')>();
  return { ...real, useEditor: (...args: any[]) => { observed.editor = (real.useEditor as any)(...args); return observed.editor; } };
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('A43 preserves all StarterKit rich nodes and shares exact Python editor-text projection', async () => {
  render(<ChapterEditor content="stale cached text" document={fixture.document} onChange={vi.fn()} />);
  await screen.findByRole('textbox');
  const editor = observed.editor;
  expect(normalizeRevisionLockDocument(editor.getJSON())).toEqual(fixture.document);
  expect(editorAnchorText(editor.state.doc, 0, editor.state.doc.content.size)).toBe(fixture.plain_text);
  expect(editor.view.dom.querySelectorAll('ul').length).toBe(2);
  expect(editor.view.dom.querySelector('ol')?.getAttribute('start')).toBe('3');
  expect(editor.view.dom.querySelectorAll('blockquote').length).toBe(2);
  expect(editor.view.dom.querySelector('pre code')?.textContent).toContain('CODESECRET');
});

it('A43 matches saved PM UTF-16 positions and Unicode-codepoint anchors for every nested text block', async () => {
  render(<ChapterEditor content="" document={fixture.document} onChange={vi.fn()} />);
  await screen.findByRole('textbox');
  const editor = observed.editor;
  for (const block of fixture.text_blocks) {
    act(() => { editor.commands.setTextSelection({ from: block.start, to: block.end }); });
    const selection = currentEditorSelection(editor);
    expect(selection.text).toBe(block.text);
    expect(selection.from).toBe(block.start);
    expect(selection.to).toBe(block.end);
    expect(Array.from(fixture.plain_text).slice(selection.text_start, selection.text_end).join('')).toBe(block.text);
    expect(block.end - block.start).toBe(block.text.length); // PM UTF-16, not codepoints.
  }
});

it('A43 controlled save/reopen preserves nested marks, lists, quote, code and hardBreak', async () => {
  const change = vi.fn();
  const mounted = render(<ChapterEditor content="" document={fixture.document} onChange={change} />);
  await screen.findByRole('textbox');
  const editor = observed.editor;
  const last = fixture.text_blocks.at(-1)!;
  act(() => { editor.commands.setTextSelection(last.end); editor.commands.insertContent({ type: 'text', text: '🙂新句' }); });
  const saved = change.mock.calls.at(-1)?.[1];
  expect(saved.content.slice(0, -1)).toEqual(fixture.document.content.slice(0, -1));
  mounted.unmount();
  render(<ChapterEditor content="" document={saved} onChange={vi.fn()} />);
  await screen.findByRole('textbox');
  expect(normalizeRevisionLockDocument(observed.editor.getJSON())).toEqual(saved);
  expect(editorAnchorText(observed.editor.state.doc, 0, observed.editor.state.doc.content.size)).toBe(fixture.plain_text + '🙂新句');
});
