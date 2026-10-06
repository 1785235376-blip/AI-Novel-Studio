// @vitest-environment jsdom
import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { JSONContent } from '@tiptap/react';
import { ChapterEditor, proseDocument } from './Editor';
import { normalizeRevisionLockDocument } from './experimental/revisionLocks';

const observed = vi.hoisted(() => ({ editor: undefined as any }));
vi.mock('@tiptap/react', async importOriginal => {
  const real = await importOriginal<typeof import('@tiptap/react')>();
  return { ...real, useEditor: (...args: any[]) => { observed.editor = (real.useEditor as any)(...args); return observed.editor; } };
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function Controlled({ initial = '起点' }: { initial?: string }) {
  const [content, setContent] = useState(initial), [document, setDocument] = useState<JSONContent>();
  return <ChapterEditor content={content} document={document} onChange={(text, doc) => { setContent(text); setDocument(doc); }} />;
}
it('renders manuscript HTML-looking text and full Unicode literally, with paragraphs intact', async () => {
  const content = '<img src=x onerror=alert(1)> & <b>不是标记</b>\n中文，👩🏽‍🚀 e\u0301\n\n结尾';
  render(<ChapterEditor content={content} onChange={vi.fn()} />);
  const textbox = await screen.findByRole('textbox', { name: '章节正文' });
  expect(textbox.querySelector('img,b,script')).toBeNull();
  expect(observed.editor.getText({ blockSeparator: '\n' })).toBe(content);
  expect(normalizeRevisionLockDocument(observed.editor.getJSON())).toEqual(proseDocument(content));
});
it('keeps the same ProseMirror state, selection and undo history on controlled echoes', async () => {
  render(<StrictMode><Controlled /></StrictMode>);
  await screen.findByRole('textbox');
  const editor = observed.editor, view = editor.view;
  act(() => { editor.commands.setTextSelection(3); editor.commands.insertContent({ type: 'text', text: '，你好 👩🏽‍🚀 e\u0301' }); });
  const end = editor.state.selection.from;
  expect(editor.view).toBe(view);
  expect(editor.getText()).toBe('起点，你好 👩🏽‍🚀 e\u0301');
  expect(editor.state.selection.from).toBe(end);
  act(() => { editor.commands.undo(); });
  expect(editor.getText()).toBe('起点');
  act(() => { editor.commands.redo(); });
  expect(editor.getText()).toBe('起点，你好 👩🏽‍🚀 e\u0301');
});
it('does not replace composing text with delayed props and commits the final Chinese candidate', async () => {
  const change = vi.fn(), composition = vi.fn();
  const view = render(<ChapterEditor content="原文" onChange={change} onCompositionChange={composition} />);
  const textbox = await screen.findByRole('textbox');
  fireEvent.compositionStart(textbox, { data: '' });
  view.rerender(<ChapterEditor content="延迟服务端内容" document={proseDocument('延迟服务端内容')} onChange={change} onCompositionChange={composition} />);
  expect(observed.editor.getText()).toBe('原文');
  act(() => { observed.editor.commands.setTextSelection(3); observed.editor.commands.insertContent({ type: 'text', text: '，中文候选' }); });
  fireEvent.compositionEnd(textbox, { data: '中文候选' });
  await waitFor(() => expect(composition).toHaveBeenLastCalledWith(false));
  expect(change).toHaveBeenLastCalledWith('原文，中文候选', proseDocument('原文，中文候选'));
  expect(observed.editor.getText()).toBe('原文，中文候选');
});
it('updates a clean plain-text document when switching to content with no rich document', async () => {
  const view = render(<ChapterEditor content="旧章" document={proseDocument('旧章')} onChange={vi.fn()} />);
  await screen.findByRole('textbox');
  view.rerender(<ChapterEditor content={"新章\n<b>普通文字</b>"} onChange={vi.fn()} />);
  expect(observed.editor.getText({ blockSeparator: '\n' })).toBe('新章\n<b>普通文字</b>');
});
