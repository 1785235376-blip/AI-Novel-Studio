// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphNoteEditor, GraphNoteCards } from './GraphCanvasNotes';
import type { StudioGraphDefinition } from './studioGraphTypes';
afterEach(cleanup);
const initial = (): StudioGraphDefinition => ({ schema_version: 1, title: '大空间', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 },
  presentation: { notes: Array.from({ length: 1024 }, (_, i) => ({ id: `note_${i + 1}`, text: `雨夜·镜头${String(i + 1).padStart(4, '0')}`, position: { x: 0, y: 0 } })) } });
function Harness({ change, owner = 'same', size = null }: { change: ReturnType<typeof vi.fn>; owner?: string; size?: { width: number; height: number } | null }) {
  const [definition, setDefinition] = useState(initial), [selected, setSelected] = useState<string | null>(null);
  const props = { definition, selected, owner, blocked: false, onSelect: setSelected, onChange: (next: StudioGraphDefinition) => { change(next); setDefinition(next); }, size };
  return <><GraphNoteEditor {...props} /><GraphNoteCards {...props} /></>;
}
it.each([null, { width: 800, height: 600 }])('bounds the initial/overlapping cards and clearly discloses omissions for %j', size => {
  const change = vi.fn(); render(<Harness change={change} size={size} />);
  expect(document.querySelectorAll('[data-graph-note-id]')).toHaveLength(128);
  expect(screen.getByText(/暂未绘制 896 张/)).toBeTruthy();
  const list = screen.getByRole('listbox', { name: '匹配的空间便笺' }); expect(within(list).getAllByRole('option')).toHaveLength(20);
  const input = screen.getByRole('combobox', { name: '查找空间便笺' }); input.focus();
  fireEvent.keyDown(input, { key: 'PageDown' }); expect(within(list).getAllByRole('option')[0].textContent).toContain('note_21');
  fireEvent.change(input, { target: { value: '镜头1024' } }); expect(within(list).getAllByRole('option')).toHaveLength(1);
  fireEvent.keyDown(input, { key: 'Enter', isComposing: true }); expect(screen.queryByLabelText('便笺文本')).toBeNull();
  fireEvent.keyDown(input, { key: 'Enter' }); expect(document.activeElement).toBe(input);
  expect(document.querySelectorAll('[data-graph-note-id]')).toHaveLength(128);
  expect(document.querySelector('[data-graph-note-id="note_1024"]')).toBeTruthy();
  expect((screen.getByLabelText('便笺文本') as HTMLTextAreaElement).value).toBe('雨夜·镜头1024');
  expect(change).not.toHaveBeenCalled();
});
it('keeps the retained editor and IME draft stable across note search/page changes, then commits once', () => {
  const change = vi.fn(); render(<Harness change={change} />);
  const search = screen.getByRole('combobox', { name: '查找空间便笺' });
  fireEvent.change(search, { target: { value: '镜头1024' } }); fireEvent.keyDown(search, { key: 'Enter' });
  const editor = screen.getByLabelText('便笺文本'); editor.focus(); fireEvent.compositionStart(editor);
  fireEvent.change(editor, { target: { value: '中文输入🎬' } });
  fireEvent.change(search, { target: { value: '' } }); fireEvent.keyDown(search, { key: 'PageDown' });
  expect(screen.getByLabelText('便笺文本')).toBe(editor); expect(document.activeElement).toBe(editor);
  expect((editor as HTMLTextAreaElement).value).toBe('中文输入🎬'); expect(change).not.toHaveBeenCalled();
  fireEvent.compositionEnd(editor, { target: { value: '中文输入🎬' } });
  expect(change).toHaveBeenCalledTimes(1); expect(change.mock.calls[0][0].presentation.notes).toHaveLength(1024);
  expect(change.mock.calls[0][0].presentation.notes[1023].text).toBe('中文输入🎬');
  expect(change.mock.calls[0][0].nodes).toEqual([]);
});
it('uses owner replacement to retire search and the old composing editor', () => {
  const change = vi.fn(), view = render(<Harness change={change} />);
  const search = screen.getByRole('combobox', { name: '查找空间便笺' });
  fireEvent.change(search, { target: { value: '镜头1024' } }); fireEvent.keyDown(search, { key: 'Enter' });
  const editor = screen.getByLabelText('便笺文本'); fireEvent.compositionStart(editor); fireEvent.change(editor, { target: { value: 'private pending' } });
  view.rerender(<Harness change={change} owner="new" />);
  expect((screen.getByRole('combobox', { name: '查找空间便笺' }) as HTMLInputElement).value).toBe('');
  fireEvent.compositionEnd(editor, { target: { value: 'late stale text' } }); expect(change).not.toHaveBeenCalled();
});
